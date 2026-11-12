"""`mdstack resume` ends a project pause (#1714).

Usage: mdstack resume --project FILE [--org-profile FILE]

Refuses unless ownership permits start, and while the pause state is unreadable (mdstack pause rewrites it). It removes
only `pause.json`, never another hold, round count or landing stop, and leaves window 0 alone. Then it restarts each
run the pause stopped, once, through mdstack restart's own rechecks (a reviewer whose PR head moved, a finished run or
a refused host stays stopped) and without spending that run's one restart. A run whose item is held (an open ask, or
`held` in poll-state.json) or whose last line is `done:` stays stopped for its lead or the coordinator. It ensures the
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
