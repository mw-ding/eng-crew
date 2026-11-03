"""Shared ownership guard: trusted control-item handoff markers, in backend post order.

No control item or no marker preserves legacy operation; a failed read is read-only.
The first claim wins, one handoff may be open, and stopped never changes ownership.
"""
import json
import os
import re
import shlex
import subprocess

LINE = re.compile(r"<!-- crew:v1 ([^>]*?) -->")


def owner_record(comments, trusted):
    owner, opened, phase = None, None, None
    for comment in comments:
        if comment["user"]["login"] not in trusted:
            continue
        for line in LINE.findall(comment["body"] or ""):
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


def binding_path(values):
    """Where crew up records a non-GitHub markers backend's rendered `markers.read-item` command (#606)."""
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (values["repo.owner"], values["repo.name"]))
    return os.path.join(state, "render", "bindings.json")


def read_argv(values):
    """The control-item read: the GitHub binding, or the configured backend's recorded read-item command."""
    if values["backends.markers.name"] == "github":
        return ["gh", "api", "--paginate", "--slurp", "repos/%s/%s/issues/%s/comments" % (
            values["repo.owner"], values["repo.name"], values["repo.control_item"])]
    with open(binding_path(values), encoding="utf-8") as f:  # missing: OSError, so read-only
        cmd = json.load(f)["markers.read-item"]
    subst = {"<n>": str(values["repo.control_item"]), "<owner>": values["repo.owner"], "<repo>": values["repo.name"]}
    return [re.sub("|".join(subst), lambda m: subst[m.group(0)], a) for a in shlex.split(cmd)]


def read_record(values):
    """(owner, phase, opened) from the control item; raises ValueError (or OSError) when unreadable.

    The read prints the item's comments in post order as JSON, `[{"user": {"login": ...}, "body": ...}]`,
    or pages of them (`gh api --slurp`)."""
    trusted = set(values["identities.owners"]) | {v for k, v in values.items() if k.endswith(".gh_user")}
    r = subprocess.run(read_argv(values), capture_output=True, text=True)
    if r.returncode:
        raise ValueError("control item unreadable")
    out = json.loads(r.stdout)
    return owner_record([c for page in out for c in (page if isinstance(page, list) else [page])], trusted)


def ownership(values):
    if not values.get("repo.control_item"):
        return "active"
    try:
        owner, phase, _ = read_record(values)
    except (OSError, ValueError, KeyError, TypeError):
        return "read-only"
    runtime = values["runtime.name"] + "@" + values.get("runtime.instance", "")
    if phase in ("offered", "takeover") or owner is not None and owner != runtime:
        return "read-only"
    return "draining" if phase else "active"


def require_ownership(values, action="start"):
    mode = ownership(values)
    if mode == "active" or mode == "draining" and action == "write":
        return True
    print("crew: ownership: %s; refusing %s" % (mode, action))
    return False
