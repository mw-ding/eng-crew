"""Shared ownership guard: trusted control-item handoff markers, in backend post order.

No control item or no marker preserves legacy operation; a failed read is read-only. The control item is read and
posted through the GitHub calls or the recorded `markers.read-item` and `markers.write-item` bindings (docs/handoff.md).
The first claim wins, one handoff may be open, and stopped never changes ownership.
`status` adds `lost`: another runtime owns and no handoff to this one is open (prompt stop, docs/handoff.md).
"""
import json
import os
import re
import shlex
import subprocess
import tempfile

LINE = re.compile(r"<!-- crew:v1 ([^>]*?) -->")
CREATED = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")


def owner_record(posts, trusted):
    owner, opened, phase = None, None, None
    for post in posts:
        if post["author"] not in trusted:
            continue
        for line in LINE.findall(post["body"] or ""):
            m = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if m.get("role") != "coordinator" or m.get("pass") != "handoff" or not all(
                    m.get(k) for k in ("handoff", "state", "from", "to", "cmd-id")) or not re.fullmatch(
                    r"[0-9a-f]{40}", m.get("sha", "")) or not re.fullmatch(
                    r"[0-9]{8}-[0-9a-f]{6}", m["handoff"]) or m.get("round") != "n/a" or m.get("verdict") != "n/a":
                continue
            if not re.fullmatch(r"[a-z][a-z0-9-]*@[a-z0-9-]{1,63}", m["to"]) or (
                    m["from"] != "none" and not re.fullmatch(r"[a-z][a-z0-9-]*@[a-z0-9-]{1,63}", m["from"])):
                continue
            state = m["state"]
            if state == "claimed" and owner is None and opened is None and m["from"] == "none":
                owner = m["to"]
            elif state in ("draining", "takeover") and m["from"] == owner and (
                    opened is None or state == "takeover" and all(m[k] == opened[k] for k in ("handoff", "from", "to"))):
                opened, phase = m, state
            elif opened and all(m[k] == opened[k] for k in ("handoff", "from", "to")):
                if state == "offered" and phase == "draining":
                    phase = state
                elif state in ("acked", "aborted"):
                    owner = m["to"] if state == "acked" else m["from"]
                    opened = phase = None
    return owner, phase, opened


# What crew handoff reads live through declared operations for a non-GitHub tracker or change backend (handoff.md).
LIVE_READS = (("tracker", "list-items"), ("change", "list-open"), ("change", "read-head"),
              ("change", "read-branch-head"), ("markers", "read"))


def native(values):
    """True when crew handoff reads live state through the recorded operations rather than `gh api`."""
    return values["backends.tracker.name"] != "github" or values["backends.change.name"] != "github"


def binding_path(values):
    """Where crew up records a non-GitHub backend's rendered operations for the ownership guard and crew handoff."""
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (values["repo.owner"], values["repo.name"]))
    return os.path.join(state, "render", "bindings.json")


def bound(values, op, fill):
    """The recorded `op` command split into arguments, with `fill` placeholders substituted; no shell.

    A missing binding raises OSError or KeyError. A string control item fills only `<control-item>`, never `<n>`,
    so a map with only `<n>` leaves it unbound (ValueError)."""
    with open(binding_path(values), encoding="utf-8") as f:
        cmd = json.load(f)[op]
    item = values["repo.control_item"]
    subst = {"<control-item>": str(item), "<owner>": values["repo.owner"], "<repo>": values["repo.name"],
             "<default-branch>": values["repo.default_branch"], **fill}
    if op.endswith("-item"):
        if "<control-item>" not in cmd and isinstance(item, str):
            raise ValueError("%s has no <control-item> for the string id %s" % (op, item))
        if not isinstance(item, str):
            subst.setdefault("<n>", str(item))
    return [re.sub("|".join(map(re.escape, subst)), lambda m: subst[m.group(0)], a) for a in shlex.split(cmd)]


def read_argv(values):
    """The control-item read: the GitHub binding, or the configured backend's recorded read-item command."""
    if values["backends.markers.name"] == "github":
        return ["gh", "api", "--paginate", "--slurp", "repos/%s/%s/issues/%s/comments" % (
            values["repo.owner"], values["repo.name"], values["repo.control_item"])]
    return bound(values, "markers.read-item", {})


def posts(out):
    """A read-item output as posts `{author, body, created, id}` in backend post order; ValueError when unreadable.

    The native shape is a flat array of `{author, body, created[, id]}`. The GitHub comment shape (`user.login`, `body`,
    optional `created_at`, `id`), as one array or `--slurp` pages, is normalized; one output never mixes the two."""
    data = json.loads(out)
    if not isinstance(data, list):
        raise ValueError("read-item output is not an array")
    flat = [c for page in data for c in page] if data and all(isinstance(p, list) for p in data) else data
    if not all(isinstance(c, dict) for c in flat) or len({"author" in c for c in flat}) > 1:
        raise ValueError("read-item output mixes shapes")
    result = []
    for c in flat:
        if "author" in c:
            post = {"author": c["author"], "body": c["body"], "created": c["created"], "id": c.get("id")}
            if not isinstance(post["created"], str) or not CREATED.fullmatch(post["created"]):
                raise ValueError("read-item post has no RFC 3339 UTC created time")
        else:
            post = {"author": c["user"]["login"], "body": c["body"], "created": c.get("created_at"),
                    "id": None if c.get("id") is None else str(c["id"])}
        if not isinstance(post["author"], str) or not isinstance(post["body"], (str, type(None))):
            raise ValueError("read-item post needs a string author and body")
        result.append(post)
    return result


def read_posts(values):
    """Every control-item post in backend post order; raises ValueError, KeyError or OSError when unreadable."""
    r = subprocess.run(read_argv(values), capture_output=True, text=True)
    if r.returncode:
        raise ValueError("control item unreadable")
    return posts(r.stdout)


def trusted(values):
    return set(values["identities.owners"]) | {v for k, v in values.items() if k.endswith(".gh_user")}


def write_item(values, body):
    """Post `body` on the control item; True only on exit 0. Any failure is uncertain, so the caller re-reads before
    posting again (docs/handoff.md write-item contract). An unbound write raises OSError, KeyError or ValueError."""
    if values["backends.markers.name"] == "github":
        argv = ["gh", "api", "repos/%s/%s/issues/%s/comments" % (
            values["repo.owner"], values["repo.name"], values["repo.control_item"]), "-F", "body=@-"]
        return subprocess.run(argv, input=body, capture_output=True, text=True).returncode == 0
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as f:
        f.write(body)
        f.flush()
        argv = bound(values, "markers.write-item", {"<file>": f.name})
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True).returncode == 0


def read_record(values):
    """(owner, phase, opened) from the control item; raises ValueError (or OSError, KeyError) when unreadable."""
    return owner_record(read_posts(values), trusted(values))


def status(values):
    if not values.get("repo.control_item"):
        return "active"
    try:
        owner, phase, opened = read_record(values)
    except (OSError, ValueError, KeyError, TypeError):
        return "read-only"
    runtime = values["runtime.name"] + "@" + values.get("runtime.instance", "")
    if owner is not None and owner != runtime and not (opened and opened["to"] == runtime):
        return "lost"
    if phase in ("offered", "takeover") or owner is not None and owner != runtime:
        return "read-only"
    return "draining" if phase else "active"


def ownership(values):
    mode = status(values)
    return "read-only" if mode == "lost" else mode


def require_ownership(values, action="start"):
    mode = ownership(values)
    if mode == "active" or mode == "draining" and action == "write":
        return True
    print("crew: ownership: %s; refusing %s" % (mode, action))
    return False
