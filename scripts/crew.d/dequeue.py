"""crew dequeue [--timeout SECS] --project FILE [--org-profile FILE]"""
import argparse
import json
import os
from crew_shared import commands, over_cap, profile, tmux


def register(sub):
    p = sub.add_parser("dequeue")
    p.add_argument("--timeout", type=float, default=15.0, help="seconds to see the harness in the foreground")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    """Spawn the oldest queued request whose band has a free slot; leave the rest queued."""
    values, session, state = profile(args)
    path = os.path.join(state, "spawn-queue.jsonl")
    entries = []
    if os.path.exists(path):
        with open(path) as f:
            entries = [json.loads(line) for line in f if line.strip()]
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    pick = next((e for e in entries if not over_cap(values, e["role"], windows)), None)
    if pick is None:
        print("crew: nothing to dequeue (%d queued, no free slot)" % len(entries) if entries else
              "crew: spawn queue empty")
        return 0
    entries.remove(pick)
    with open(path, "w") as f:
        f.writelines(json.dumps(e) + "\n" for e in entries)
    spawn = commands()["spawn"].run
    return spawn(argparse.Namespace(role=pick["role"], issue=pick["issue"], pr=pick["pr"], pass_=pick["pass"],
                                    round=pick["round"], tier=pick["tier"], timeout=args.timeout,
                                    project=args.project, org_profile=args.org_profile))
