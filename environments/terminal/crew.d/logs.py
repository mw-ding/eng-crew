"""`mdstack logs` tails a run's step summary, on this host or, through its `logs` verb, the run's role host.

Usage: mdstack logs WINDOW [-n N] [-f] --project FILE [--org-profile FILE]
"""
import glob
import json
import os
from crew_shared import profile, remote_run


def register(sub):
    p = sub.add_parser("logs")
    p.add_argument("window")
    p.add_argument("-n", "--lines", type=int, default=20)
    p.add_argument("-f", "--follow", action="store_true")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    """Print the tail of the newest step summary under the run's worktree; never raw logs (docs/observe.md)."""
    values, session, state = profile(args)
    path = os.path.join(state, "runs", args.window + ".json")
    if not os.path.exists(path):
        print("crew: no run %s" % args.window)
        return 1
    with open(path) as f:
        rec = json.load(f)
    if remote_run.host_of(rec):
        return remote_logs(values, args, rec)
    wt = rec.get("worktree")
    found = glob.glob(os.path.join(wt, ".crew", "runs", "**", "summary.md"), recursive=True) if wt else []
    if not found:
        print("crew: no step summary yet under %s" % os.path.join(str(wt), ".crew", "runs"))
        return 1
    summary = max(found, key=os.path.getmtime)
    if args.follow:
        os.execvp("tail", ["tail", "-n", str(args.lines), "-f", summary])
    with open(summary, encoding="utf-8") as f:
        lines = f.read().splitlines()
    print("==> %s <==" % summary)
    print("\n".join(lines[-args.lines:]))
    return 0


def remote_logs(values, args, rec):
    """The same tail from the run's host (multi-device.md#observability); `-f` is local only."""
    if args.follow:
        print("crew: logs -f is not supported for a run on %s; rerun without -f" % rec["host"])
        return 1
    reply = remote_run.logs(values, args.window, rec, args.lines)
    if reply["result"] != "ok":
        print("crew: %s %s: %s" % (rec["host"], reply["result"], reply.get("reason") or reply.get("error", "")))
        return 1
    if not reply["path"]:
        print("crew: no step summary yet under %s on %s" % (os.path.join(rec["worktree"], ".crew", "runs"), rec["host"]))
        return 1
    print("==> %s:%s <==" % (rec["host"], reply["path"]))
    print("\n".join(reply["lines"]))
    return 0
