"""`crew poll` turns GitHub state changes into one-consumer wake records in `wake/queue.jsonl` (`new-head` and the
evidence-only `fix-at-head` carry the round `k`; approved default-branch merges emit `merge-up` with the previous
head and approval round). Non-active ownership emits one coordinator ownership wake per
mode change and no work events.

Usage: crew poll [--once] --project FILE
"""
import json
import os
import re
import subprocess
import time
from crew_shared import ownership, profile, queue_lock, ROLES


# crew poll (tmux.md Q1, C2): one wake source. Read-only gh JSON for open crew PRs and crew:ready items is diffed
# against poll-state.json; each change becomes one wake record in wake/queue.jsonl naming one consuming role
# (protocol §8). The coordinator drains the queue and routes each record by crew send or crew spawn.
CONSUMER = {event: role for role, data in ROLES.items() for event in data["events"]["tmux"]}
PR_FIELDS = "number,state,headRefOid,labels,statusCheckRollup,reviews"
CREW_LINE = re.compile(r"<!-- crew:v1 ([^>]*?) -->")
CI_OK, CI_BAD = {"SUCCESS", "NEUTRAL", "SKIPPED"}, {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED",
                                                    "STARTUP_FAILURE"}


def landing_steers(reviews):
    """Read recorded coordinator urgency and outstanding project stops in review order."""
    urgent, stops = [], set()
    for review in reviews:
        for line in CREW_LINE.findall(review["body"]):
            marker = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if (marker.get("role"), marker.get("pass")) != ("coordinator", "steer"):
                continue
            cmd, cmd_id = marker.get("cmd"), marker.get("cmd-id")
            if cmd == "urgent":
                urgent.append(marker)
            elif cmd == "stop-landing" and cmd_id:
                stops.add(cmd_id)
            elif cmd == "resume-landing":
                stops.discard(marker.get("stop-id"))
    return {"urgent": urgent, "stops": sorted(stops)}


def pr_snapshot(pr):
    """Head, CI rollup, the latest verdict at head, round k (protocol §5) and whether a builder fix note sits at head
    after a changes verdict there (an evidence-only fix), from the hidden crew:v1 lines only (protocol §4)."""
    head = pr["headRefOid"]
    results = [c.get("state") if c.get("__typename") == "StatusContext" else
               c.get("conclusion") if c.get("status") == "COMPLETED" else "PENDING" for c in pr["statusCheckRollup"]]
    ci = "failed" if CI_BAD & set(results) else "passed" if results and set(results) <= CI_OK else "pending"
    verdict, fixed, changes = None, False, 0
    for review in pr["reviews"]:
        for line in CREW_LINE.findall(review["body"]):
            m = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if m.get("pass") in ("cutover", "resume"):
                changes = 0
            elif m.get("role") == "reviewer-validator" and m.get("pass") == "verdict":
                changes += m.get("verdict") == "changes"
                if m.get("sha") == head:
                    verdict, fixed = m.get("verdict"), False
            elif m.get("role") == "builder" and m.get("pass") == "fix" and m.get("sha") == head:
                fixed = True
    return {"head": head, "ci": ci, "verdict": verdict, "round": 1 + changes, "fixed": fixed and verdict == "changes"}


def decide(prev, prs, issues, merge_ups=None):
    """Pure: previous poll state plus gh JSON (open PRs, tracked PRs now merged or closed, open issues) -> (events,
    new state). A change emits one event; no change emits nothing."""
    events, state = [], {"prs": {}, "issues": []}

    def emit(event, *refs, **extra):
        events.append({"event": event, "consumer": CONSUMER[event], "refs": list(refs), **extra})

    for pr in prs:
        n, cur = str(pr["number"]), pr_snapshot(pr)
        if pr["state"] != "OPEN":
            emit("pr-merged" if pr["state"] == "MERGED" else "pr-closed", "#" + n, cur["head"])
            continue
        if not any(label["name"].startswith("crew:") for label in pr["labels"]):
            continue
        old = prev.get("prs", {}).get(n, {})
        state["prs"][n] = cur
        if cur["head"] != old.get("head"):
            approved = (merge_ups or {}).get(n)
            if approved:
                emit("merge-up", "#" + n, cur["head"], previous_head=approved["head"], round=approved["round"])
            else:
                emit("new-head", "#" + n, cur["head"], round=cur["round"])
        if cur["ci"] in ("passed", "failed") and (cur["head"], cur["ci"]) != (old.get("head"), old.get("ci")):
            emit("ci-" + cur["ci"], "#" + n, cur["head"])
        if cur["verdict"] and (cur["head"], cur["verdict"]) != (old.get("head"), old.get("verdict")):
            emit("review-approved" if cur["verdict"] == "pass" else "review-changes-requested", "#" + n, cur["head"])
        if cur["fixed"] and (cur["head"], True) != (old.get("head"), old.get("fixed")):  # no new-head will come (B2)
            emit("fix-at-head", "#" + n, cur["head"], round=cur["round"])
    state["issues"] = sorted(i["number"] for i in issues if i["assignees"] and
                             any(label["name"] == "crew:ready" for label in i["labels"]))
    for n in state["issues"]:
        if n not in prev.get("issues", []):
            emit("issue-assigned", "#%d" % n)
    return events, state


def gh_json(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("crew: gh %s failed: %s" % (" ".join(args[:2]), r.stderr.strip()))
    return json.loads(r.stdout)


def merge_up(pr, old, repo, default_branch):
    """Recognize one merge atop the previously observed, still-approved head; its second parent must belong to
    the default branch. Read the verdict live, so a later changes verdict cannot inherit a cached approval."""
    if not old.get("head") or old["head"] == pr["headRefOid"]:
        return None
    approved = pr_snapshot({**pr, "headRefOid": old["head"]})
    if approved["verdict"] != "pass":
        return None
    for review in pr["reviews"]:
        for line in CREW_LINE.findall(review["body"]):
            marker = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if (marker.get("role"), marker.get("pass"), marker.get("sha")) == (
                    "reviewer-validator", "verdict", old["head"]):
                approved["round"] = int(marker["round"])
    commit = gh_json("api", "repos/%s/commits/%s" % (repo, pr["headRefOid"]))
    parents = [p["sha"] for p in commit["parents"]]
    if len(parents) != 2 or parents[0] != old["head"]:
        return None
    comparison = gh_json("api", "repos/%s/compare/%s...%s" % (repo, parents[1], default_branch))
    return approved if comparison["status"] in ("ahead", "identical") else None


def poll_once(values, state):
    mode = ownership(values)
    ownership_path = os.path.join(state, "ownership.json")
    previous = json.load(open(ownership_path)) if os.path.exists(ownership_path) else "active"
    if mode != "active":
        if previous != mode:
            with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a") as f:
                f.write(json.dumps({"id": "ownership-" + os.urandom(6).hex(), "source": "poll",
                                   "reason": "ownership:", "event": "ownership", "consumer": "coordinator",
                                   "refs": [mode]}) + "\n")
        with open(ownership_path, "w") as f:
            json.dump(mode, f)
        print("crew: ownership: %s; poll emits no work" % mode)
        return
    if previous != "active":
        with open(ownership_path, "w") as f:
            json.dump(mode, f)
    repo, path = "%s/%s" % (values["repo.owner"], values["repo.name"]), os.path.join(state, "poll-state.json")
    prev = None
    if os.path.exists(path):
        with open(path) as f:
            prev = json.load(f)
    prs = gh_json("pr", "list", "-R", repo, "--state", "open", "--limit", "200", "--json", PR_FIELDS)
    gone = set((prev or {}).get("prs", {})) - {str(pr["number"]) for pr in prs}
    prs += [gh_json("pr", "view", n, "-R", repo, "--json", PR_FIELDS) for n in sorted(gone)]
    issues = gh_json("issue", "list", "-R", repo, "--state", "open", "--label", "crew:ready", "--limit", "200",
                     "--json", "number,labels,assignees")
    merge_ups = {}
    for pr in prs:
        if pr["state"] == "OPEN" and any(l["name"].startswith("crew:") for l in pr["labels"]):
            approved = merge_up(pr, (prev or {}).get("prs", {}).get(str(pr["number"]), {}),
                                repo, values["repo.default_branch"])
            if approved:
                merge_ups[str(pr["number"])] = approved
    events, new = decide(prev or {}, prs, issues, merge_ups)
    if prev is None:  # first run: record a baseline only; the §6 step 3 sweep covers what happened before it
        events = []
        print("crew: poll: baseline of %d PRs, %d issues" % (len(new["prs"]), len(new["issues"])))
    with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a", encoding="utf-8") as f:  # at-least-once
        for e in events:
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            f.write(json.dumps({"id": "poll-%s-%s" % (ts, os.urandom(3).hex()), "source": "poll", "reason": "poll", **e, "ts": ts}) + "\n")
            print("crew: poll: %s -> %s %s" % (e["event"], e["consumer"], " ".join(e["refs"])))
    with open(path + ".tmp", "w") as f:
        json.dump(new, f, indent=2)
    os.replace(path + ".tmp", path)


def register(sub):
    p = sub.add_parser("poll")
    p.add_argument("--once", action="store_true", help="one poll, then exit (default: every poll_interval seconds)")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    values, _, state = profile(args)
    while True:
        try:
            poll_once(values, state)
        except RuntimeError as e:
            print(e)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(values["runtime.options.poll_interval"])
