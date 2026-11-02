"""`crew dequeue` spawns the oldest request `crew spawn` queued beyond the profile band cap.

Usage: crew dequeue [--timeout SECS] --project FILE [--org-profile FILE]
"""
import argparse
import json
import os
from crew_shared import (
    BANDS, CAPS, commands, idle_builder, kill_run, NAMES, over_cap, profile, queue_lock, remember_pr, runs, tmux, unlanded)


def register(sub):
    p = sub.add_parser("dequeue")
    p.add_argument("--timeout", type=float, default=15.0, help="seconds to see the harness in the foreground")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args, role=None):
    """Spawn the oldest queued request whose band has a free slot; kill limits this to the freed role band."""
    role = role or getattr(args, "role", None)
    values, session, state = profile(args)
    path = os.path.join(state, "spawn-queue.jsonl")
    entries = []
    if os.path.exists(path):
        with open(path) as f:
            entries = [json.loads(line) for line in f if line.strip()]
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    if (role is None or role == "builder") and any(e["role"] == "builder" for e in entries) and \
            (not commands()["lead"].enabled(state, "builder") or os.environ.get("CREW_POOL") == "builder"):
        with queue_lock(state):
            idle = sorted((beat, name) for name, rec in runs(state) if rec["role"] == "builder" and
                          name in windows and (beat := idle_builder(state, name)) is not None)
            used = sum(BANDS["builder"][0] <= i <= BANDS["builder"][1] for i in windows.values())
            if used == BANDS["builder"][1] - BANDS["builder"][0] + 1 and used - len(idle) < values[CAPS["builder"]]:
                for _, name in idle:
                    rec = dict(runs(state))[name]
                    with open(os.path.join(state, "status", name + ".status")) as f:
                        for line in f.read().splitlines():
                            remember_pr(rec, line)
                    if not unlanded(values, rec, rec["worktree"]) and not kill_run(values, session, state, name):
                        print("crew: reclaimed idle builder " + name)
                        windows.pop(name)
                        break
    pick = next((e for e in entries if (role is None or e["role"] == role) and
                 (not commands()["lead"].enabled(state, e["role"]) or os.environ.get("CREW_POOL") == e["role"]) and
                 not over_cap(values, e["role"], windows, state)), None)

    if pick is None:
        print("crew: nothing to dequeue (%d queued, no free slot)" % len(entries) if entries else
              "crew: spawn queue empty")
        return 0
    entries.remove(pick)
    with open(path, "w") as f:
        f.writelines(json.dumps(e) + "\n" for e in entries)
    spawn = commands()["spawn"].run
    rc = spawn(argparse.Namespace(role=pick["role"], issue=pick["issue"], pr=pick["pr"], pass_=pick["pass"],
                                    head=pick.get("head"), round=pick["round"], tier=pick["tier"],
                                    timeout=getattr(args, "timeout", 15.0),
                                    project=args.project, org_profile=args.org_profile, messages=pick.get("messages", [])))
    name = values.get("identities.builder.name", NAMES["builder"]).lower() + "-%s" % pick["issue"]
    if not rc and pick["role"] == "builder" and name in dict(runs(state)):
        for message in pick.get("messages", []):
            rc = commands()["send"].run(argparse.Namespace(window=name, kind=message["kind"], refs=message["refs"],
                                       wait_ack=None, project=args.project, org_profile=args.org_profile))
            if rc not in (0, 4):
                return rc
    return 0 if rc == 4 else rc
