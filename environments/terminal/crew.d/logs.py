"""`mdstack logs` tails a run's step summary.

Usage: mdstack logs WINDOW [-n N] [-f] --project FILE [--org-profile FILE]
"""
import glob
import json
import os
from crew_shared import profile


def register(sub):
    p = sub.add_parser("logs")
    p.add_argument("window")
    p.add_argument("-n", "--lines", type=int, default=20)
    p.add_argument("-f", "--follow", action="store_true")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    """Print the tail of the newest step summary under the run's worktree; never raw logs (docs/observe.md)."""
    values, session, state = profile(args)
    path = os.path.join(state, "runs", args.window + ".json")
    if not os.path.exists(path):
        print("crew: no run %s" % args.window)
        return 1
    with open(path) as f:
        wt = json.load(f).get("worktree")
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
