"""`mdstack resume` ends a project pause (#1714).

Usage: mdstack resume --project FILE [--org-profile FILE]

Refuses unless ownership permits start, and while the pause state is unreadable (mdstack pause rewrites it). It removes
only `pause.json`, never another hold, round count or landing stop, and leaves window 0 alone. Then it restarts each
run the pause stopped, once, through mdstack restart's own rechecks (a finished run or a refused host stays stopped)
and without spending that run's one restart. Before each restart it re-reads the run's issue and PR live: a closed
item, a `crew:hold` or `crew:escalated` label, a reviewer whose PR head moved from its recorded head, or a failed read
keeps the run stopped, as does an open ask, `held` in poll-state.json or a last line `done:`; the lead or the
coordinator admits it later. It ensures the
enabled leads on their kept inboxes and the lifecycle floors as mdstack up does, and queues one `resume` wake naming
what restarted and what stayed stopped, so the coordinator rechecks CI and the remaining demand. With no pause it
prints `not paused` and exits 0.
"""
import argparse
import json
import os
import re
import time
from crew_shared import commands, paused, profile, queue_lock, require_ownership, runs


def register(sub):
    p = sub.add_parser("resume")
    p.add_argument("--timeout", type=float, default=15.0, help="seconds to see each restarted harness")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def last_line(state, name):
    """The run's last status line that is not a supervisor heartbeat."""
    path = os.path.join(state, "status", name + ".status")
    with open(path) if os.path.exists(path) else open(os.devnull) as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("heartbeat:")]
    return lines[-1] if lines else ""


def live_block(values, rec):
    """Why live state keeps a stopped run stopped, else None: its issue or PR closed or held, a reviewer's PR head moved
    off its recorded head, or an unreadable read (fail closed)."""
    a, repo = rec.get("args", {}), "%s/%s" % (values["repo.owner"], values["repo.name"])
    try:
        for kind, n in (("pr", a.get("pr")), ("issue", a.get("issue"))):
            if not n:
                continue
            item = commands()["route"].gh(kind, "view", str(n), "-R", repo, "--json",
                                          "state,labels" + (",headRefOid" if kind == "pr" else ""))
            if item.get("state") != "OPEN":
                return "%s #%s %s" % (kind, n, str(item.get("state")).lower())
            if {label["name"] for label in item["labels"]} & {"crew:hold", "crew:escalated"}:
                return "held"
            if kind == "pr" and rec["role"] == "reviewer" and item.get("headRefOid") != rec.get("head"):
                return "head moved"
    except (RuntimeError, ValueError, KeyError, TypeError) as e:
        return "unreadable: %s" % str(e).replace("crew: ", "")
    return None


def run(args):
    values, _, state = profile(args, "worktree_root")
    rec = paused(state)
    if rec is None:
        print("crew: not paused")
        return 0
    if "unreadable" in rec:
        print("crew: refusing resume: pause state unreadable (%s); mdstack pause rewrites it" % rec["unreadable"])
        return 1
    if not require_ownership(values):
        return 1
    os.remove(os.path.join(state, "pause.json"))
    parked, recs, started, kept = commands()["watch"].held(state), dict(runs(state)), [], []
    for name in rec.get("stopped", []):
        if name not in recs:
            continue
        if set(re.findall(r"#\d+", str(recs[name].get("item")))) & parked:
            kept.append(name + " (held)")
        elif last_line(state, name).startswith("done:"):
            kept.append(name + " (done)")
        elif why := live_block(values, recs[name]):
            kept.append("%s (%s)" % (name, why))
        elif commands()["restart"].run(argparse.Namespace(
                window=name, timeout=args.timeout, project=args.project, org_profile=args.org_profile, resume=None,
                unpause=True)):
            kept.append(name + " (restart refused)")
        else:
            started.append(name)
    code = commands()["up"].start_roles(argparse.Namespace(
        project=args.project, org_profile=args.org_profile, coordinator_only=False, timeout=args.timeout), values, state)
    event = "restarted %s; stopped %s" % (", ".join(started) or "none", ", ".join(kept) or "none")
    with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a") as f:
        f.write(json.dumps({"reason": "resume", "event": event, "action": "recheck",
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    print("crew: resumed; %s%s" % (event, "; a lead or lifecycle floor did not start" if code else ""))
    return 1 if code else 0
