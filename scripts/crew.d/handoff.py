"""`crew handoff` builds the runtime handoff manifest and the incoming side's transfer plan (docs/handoff.md).

Usage: crew handoff manifest --project FILE [--org-profile FILE] [--mode drain|stop] [--post --signature TEXT]
       crew handoff reconcile --project FILE [--org-profile FILE]

`manifest` reads this runtime's open handoff on the control item and the live open items, groups them into
dependency-closed sets and fills templates/handoff-manifest.md: references only, secret-scanned, one post. With
--post it re-reads the record before each attempt and posts `offered` only while no post for that handoff id
exists, so a retry is never a second handoff; once acked it posts nothing. `reconcile` is the incoming side's
read-only plan for the offered manifest: per set `adopt`, `hold` (a head moved) or `skip` (all claimed here).
"""
import glob
import json
import os
import re
import subprocess

from crew_shared import HERE, crew_render, ownership_module, profile

LIMIT = 65536  # GitHub's comment size
LINKS = re.compile(r"(?i)\b(?:depends on|closes|fixes|resolves) #(\d+)")
STAGES = ("ready", "in-review", "changes", "approved", "hold", "escalated", "needs-md")
TEMPLATE = os.path.join(os.path.dirname(HERE), "templates", "handoff-manifest.md")


def register(sub):
    p = sub.add_parser("handoff")
    p.add_argument("action", choices=["manifest", "reconcile"])
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--mode", choices=["drain", "stop"], default="drain")
    p.add_argument("--post", action="store_true")
    p.add_argument("--signature", default="")


def gh(values, path, body=None):
    url = "repos/%s/%s/%s" % (values["repo.owner"], values["repo.name"], path)
    cmd = ["gh", "api", url, "-F", "body=@-"] if body else ["gh", "api", "--paginate", "--slurp", url]
    r = subprocess.run(cmd, input=body, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("crew: handoff: gh api %s failed" % path)
    if body:  # POST prints the created comment object; nothing reads it
        return None
    pages = json.loads(r.stdout)
    return [x for page in pages for x in page] if isinstance(pages[0], list) else pages[0]


def record(values):
    trusted = set(values["identities.owners"]) | {v for k, v in values.items() if k.endswith(".gh_user")}
    comments = [c for c in gh(values, "issues/%s/comments" % values["repo.control_item"])
                if c["user"]["login"] in trusted]
    return comments, ownership_module.owner_record(comments, trusted)


def live(values):
    """Open items, open PR heads, dependency-closed sets of crew items, and the open issues outside every set."""
    heads = {p["number"]: p["head"]["sha"] for p in gh(values, "pulls?state=open&per_page=100")}
    items = {i["number"]: i for i in gh(values, "issues?state=open&per_page=100")}
    edges = {n: {int(m) for m in LINKS.findall(i["body"] or "") if int(m) in items} for n, i in items.items()}
    for n in items:
        for m in edges[n]:
            edges[m].add(n)
    seen, sets = set(), []
    for n in sorted(items):
        if n not in seen and (n in heads or any(lb["name"].startswith("crew:") for lb in items[n]["labels"])):
            group, todo = set(), [n]
            while todo:
                m = todo.pop()
                if m not in group:
                    group.add(m)
                    todo += edges[m]
            seen |= group
            sets.append(sorted(group))
    return items, heads, sets, [n for n in sorted(items) if n not in seen]


def cells(s, key, width):
    return " ".join(str(i[key] or "-")[:width] for i in s["items"])


def manifest(values, state, opened, mode, signature):
    items, heads, sets, backlog = live(values)
    runs = {}
    for path in sorted(glob.glob(os.path.join(state, "runs", "*.json"))):
        with open(path) as f:
            r = json.load(f)
        runs.setdefault(int(r["item"].split("#")[1]), []).append(
            {"role": r["role"], "pass": r["pass"], "end": "kept", "worktree": os.path.basename(r["worktree"])})
    branch = values["repo.default_branch"]
    sha = gh(values, "commits/" + branch)["sha"]
    version = os.path.join(os.path.dirname(HERE), "VERSION")
    data = {"schema": "crew-handoff/1", "handoff": opened["handoff"], "from": opened["from"], "to": opened["to"],
            "repo": "%s/%s" % (values["repo.owner"], values["repo.name"]), "mode": mode,
            "eng_crew_version": open(version).read().strip() if os.path.exists(version) else "unreleased",
            "default_branch": {"name": branch, "sha": sha}, "sets": [], "holds_added": [],
            "rules": [{"key": k, "value": v} for k, v in sorted(values.items())
                      if k.startswith("flavor.") or k == "runtime.options.merge_grant"],
            "backlog": ["#%d" % n for n in backlog]}
    for k, group in enumerate(sets, 1):
        data["sets"].append({"id": "s%d" % k, "order": k, "items": [{
            "item": "#%d" % n, "pr": n in heads, "head": heads.get(n),
            "stage": next((lb["name"][5:] for lb in items[n]["labels"] if lb["name"][5:] in STAGES),
                          "build" if items[n]["assignees"] else "none"),
            "labels": sorted(lb["name"] for lb in items[n]["labels"]),
            "depends_on": ["#" + m for m in LINKS.findall(items[n]["body"] or "")],
            "runs": runs.get(n, [])} for n in group]})
    with open(TEMPLATE) as f:
        template = f.read()
    row = next(line for line in template.splitlines() if "<set>" in line)  # repeated once per set
    template = template.replace(row, "\n".join(
        row.replace("<set>", s["id"]).replace("<set-items>", cells(s, "item", 9)).replace(
            "<set-stages>", cells(s, "stage", 9)).replace("<set-heads>", cells(s, "head", 7)) for s in data["sets"]))
    for shrink in (False, True):
        if shrink:  # one link per milestone instead; an open item is never dropped
            data["backlog"] = sorted({(items[n]["milestone"] or {}).get("html_url", "none") for n in backlog})
        fill = {"CoordinatorBot": values["identities.coordinator.name"], "handoff-id": opened["handoff"],
                "from": opened["from"], "to": opened["to"], "items": str(sum(map(len, sets))),
                "sets": str(len(sets)), "mode": mode, "backlog": str(len(backlog)),
                "default-branch-head-sha": sha, "manifest": json.dumps(data, indent=1), "signature": signature}
        post = re.sub(r"<([A-Za-z-]+)>", lambda m: fill.get(m.group(1), m.group(0)), template)
        if len(post) <= LIMIT:
            break
    else:
        raise RuntimeError("crew: handoff: manifest exceeds %d characters" % LIMIT)
    reasons = crew_render.crew_config.token_reasons(post)
    if reasons:
        raise RuntimeError("crew: handoff: secret scan refused the manifest: " + "; ".join(reasons))
    return post


def run(args):
    try:
        return handoff(args)
    except RuntimeError as e:  # a failed read or a refused manifest; nothing was posted
        print(e)
        return 1


def handoff(args):
    values, _, state = profile(args)
    runtime = values["runtime.name"] + "@" + values.get("runtime.instance", "")
    if not values.get("repo.control_item") or args.post and not args.signature:
        print("crew: handoff: needs repo.control_item, and --signature with --post")
        return 1
    if args.action == "reconcile":
        return reconcile(values, state, runtime)
    for attempt in range(1, 4):
        _, (owner, phase, opened) = record(values)
        if opened is None and owner not in (None, runtime):
            print("crew: handoff: owned by %s; nothing to post" % owner)
            return 0
        if opened is None or opened["from"] != runtime or phase == "takeover":
            print("crew: handoff: no open handoff from %s" % runtime)
            return 1
        if phase == "offered":
            print("crew: handoff: %s already offered; waiting for the ack" % opened["handoff"])
            return 0
        post = manifest(values, state, opened, args.mode, args.signature)
        if not args.post:
            print(post)
            return 0
        try:
            gh(values, "issues/%s/comments" % values["repo.control_item"], post)
        except RuntimeError as e:
            print("%s; re-reading (attempt %d)" % (e, attempt))
    return 1


def reconcile(values, state, runtime):
    comments, (_, phase, opened) = record(values)
    if not opened or opened["to"] != runtime or phase != "offered":
        print("crew: handoff: no offered handoff to %s" % runtime)
        return 1
    key = "handoff=%s state=offered " % opened["handoff"]
    offer = next((c["body"] for c in comments if key in (c["body"] or "")), "")
    block = re.search(r"```json\n(.*?)\n```", offer, re.S)
    data = json.loads(block.group(1)) if block else {}
    if data.get("schema") != "crew-handoff/1":
        print("crew: handoff: no crew-handoff/1 manifest for %s; ask the owner" % opened["handoff"])
        return 1
    _, heads, sets, _ = live(values)
    claims = os.listdir(os.path.join(state, "claims")) if os.path.isdir(os.path.join(state, "claims")) else []
    mine = {int(m) for c in claims for m in re.findall(r"(?:issue|pr)(\d+)", c)}
    listed = set()
    for s in data["sets"]:
        nums = [int(i["item"][1:]) for i in s["items"]]
        listed |= set(nums)
        moved = [i["item"] for i in s["items"] if i["pr"] and heads.get(int(i["item"][1:]), i["head"]) != i["head"]]
        verb = "skip" if all(n in mine for n in nums) else "hold" if moved else "adopt"
        moved = ["moved:", *moved] if verb == "hold" else []
        print(" ".join([s["id"], verb, *(i["item"] for i in s["items"]), *moved]))
    for n in sorted({n for group in sets for n in group} - listed):
        print("missed #%d adopt" % n)
    return 0
