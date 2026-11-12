"""`mdstack dequeue` spawns the oldest request `mdstack spawn` queued beyond the profile band cap; a reflection request
keeps its run ID, log issue, input SHA and window (#1520).

Usage: mdstack dequeue [--ref #N] [--timeout SECS] --project FILE [--org-profile FILE]
"""
import argparse
import json
import os
import shutil
import time
from crew_shared import (
    BANDS, commands, idle_builder, kill_run, NAMES, over_cap, pool_cap, profile, queue_lock, remember_pr, runs, tmux, unlanded)

# A queued reflection request's fields and their spawn arguments, carried intact (#1520).
REFLECTION = (("reflection", "window"), ("run_id", "run"), ("log", "log"), ("input_sha", "sha"))


def reclaim(values, session, state, windows, expired=False):
    ttl = values.get("runtime.options.idle_builder_ttl", 1800)
    if expired and not ttl:
        return
    idle = sorted((beat, name, rec) for name, rec in runs(state) if rec["role"] == "builder" and
                  name in windows and (beat := idle_builder(state, name)) is not None)
    for beat, name, rec in idle:
        if expired and time.time() - beat < ttl:
            continue
        status = os.path.join(state, "status", name + ".status")
        with open(status) as f:
            for line in f.read().splitlines():
                remember_pr(rec, line)
        if unlanded(values, rec, rec["worktree"]):
            continue
        retained = os.path.join(state, "retained", "builders", name + "-" + str(int(beat)))
        os.makedirs(retained, exist_ok=True)
        shutil.copy2(status, os.path.join(retained, "status.txt"))
        with open(os.path.join(retained, "output.txt"), "w") as f:
            f.write(tmux.capture(session, windows[name]))
        with open(os.path.join(retained, "run.json"), "w") as f:  # route consumes this run's later stale wake (#1552)
            json.dump({"window": name, "run": commands()["watch"].run_identity(rec)}, f)
        summaries = os.path.join(rec["worktree"], ".crew", "runs")
        if os.path.isdir(summaries):
            shutil.copytree(summaries, os.path.join(retained, "summaries"), dirs_exist_ok=True)
        if not kill_run(values, session, state, name):
            print("crew: reclaimed idle builder %s; output retained at %s" % (name, retained))
            windows.pop(name)
            if not expired:
                return


def register(sub):
    p = sub.add_parser("dequeue")
    p.add_argument("--timeout", type=float, default=15.0, help="seconds to see the harness in the foreground")
    p.add_argument("--idle-only", action="store_true", help="reclaim expired idle builders without spawning")
    p.add_argument("--ref", help="spawn only this request: #issue for a build, else #PR (a `schedule decide` grant)")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args, role=None):
    """Spawn the oldest queued request whose band has a free slot; kill limits this to the freed role band and --ref
    to one request."""
    role = role or getattr(args, "role", None)
    values, session, state = profile(args)
    path = os.path.join(state, "spawn-queue.jsonl")
    entries = []
    if os.path.exists(path):
        with open(path) as f:
            entries = [json.loads(line) for line in f if line.strip()]
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    builder_pool = not commands()["lead"].enabled(state, "builder") or os.environ.get("CREW_POOL") == "builder"
    if (role is None or role == "builder") and builder_pool:
        with queue_lock(state):
            if getattr(args, "idle_only", False):
                reclaim(values, session, state, windows, expired=True)
            used = sum(BANDS["builder"][0] <= i <= BANDS["builder"][1] for i in windows.values())
            busy = sum(idle_builder(state, n) is None for n, i in windows.items()
                       if BANDS["builder"][0] <= i <= BANDS["builder"][1])
            if not getattr(args, "idle_only", False) and any(e["role"] == "builder" for e in entries) and \
                    used == BANDS["builder"][1] - BANDS["builder"][0] + 1 and busy < pool_cap(values, "builder", state):
                reclaim(values, session, state, windows)
    if getattr(args, "idle_only", False):
        return 0
    ref = getattr(args, "ref", None)
    matching = [e for e in entries if (role is None or e["role"] == role) and
                (ref is None or ref == ("train-%d" % e["train"] if e.get("train") else "#%s" % (e["issue"] if e["pass"] == "build" else e["pr"])))]
    owned = [e for e in matching if commands()["lead"].enabled(state, e["role"]) and os.environ.get("CREW_POOL") != e["role"]]
    pick = next((e for e in matching if e not in owned and not over_cap(values, e["role"], windows, state)), None)

    if pick is None:
        if not entries:
            print("crew: spawn queue empty")
            return 0
        # Name why nothing started: a lead-owned pool is not a capacity problem (#1100).
        why = ["%s pool is lead-managed (use the %s lead or CREW_POOL=%s)" % (r, r, r)
               for r in sorted(set(e["role"] for e in owned))]
        if len(owned) < len(matching):
            why.append("no free slot")
        if not matching:
            why.append("none match --ref %s" % ref if ref else "none for %s" % role)
        print("crew: nothing to dequeue (%d queued, %s)" % (len(entries), "; ".join(why)))
        return 0
    entries.remove(pick)
    with open(path, "w") as f:
        f.writelines(json.dumps(e) + "\n" for e in entries)
    spawn = commands()["spawn"].run
    rc = spawn(argparse.Namespace(role=pick["role"], issue=pick["issue"], pr=pick["pr"], sweep=pick.get("sweep", False),
                                    docs_pass=pick.get("docs_pass", False), train=pick.get("train"), pass_=None if pick.get("train") else pick["pass"],
                                    **{k: (pick.get("reflection") or {}).get(f) for k, f in REFLECTION},
                                    head=pick.get("head"), rereview_id=pick.get("rereview_id"), round=pick["round"], tier=pick["tier"],
                                    host=pick.get("host"), reason=pick.get("override_reason"),
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
