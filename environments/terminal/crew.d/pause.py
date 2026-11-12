"""`mdstack pause` stops a repo's crew work and keeps its coordinator and watcher (#1714).

Usage: mdstack pause --project FILE [--org-profile FILE] [--reason TEXT]

It first writes the durable project barrier `pause.json` in the state dir and reads it back. Every dispatch, review,
land, restart, routine and cleanup path refuses while it exists or is unreadable, and the watcher keeps scanning in
observation mode: it queues events but routes nothing, nudges no model and runs no timer. While another process holds
the land lock (an atomic land already started) pause prints `pausing` and exits 75 before stopping anything; run it
again once the land ends. Then it stops every window but window 0 (SIGTERM, then SIGKILL) and each run on a role host,
keeping every worktree, run record, claim, inbox and status file; it drops lead records as mdstack down does, so resume
starts fresh leads on their kept inboxes. A surviving process or a host that does not answer is an incomplete pause:
exit 1, barrier kept, pause again. Pausing a paused project is safe. Only mdstack resume ends a pause.
"""
import json
import os
import time
from crew_shared import commands, paused, profile, remote_run, runs, stop_pane, tmux


def register(sub):
    p = sub.add_parser("pause")
    p.add_argument("--reason", default="owner pause", help="recorded in pause.json")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def write(state, rec):
    """Write pause.json durably (fsync, then an atomic rename); True when it reads back as written."""
    path = os.path.join(state, "pause.json")
    os.makedirs(state, exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(rec, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(path + ".tmp", path)
    return paused(state) == rec


def run(args):
    values, session, state = profile(args)
    rec = paused(state)
    if rec is None or "unreadable" in rec:  # a damaged barrier is rewritten, still paused
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "reason": args.reason, "stopped": []}
    rec["state"] = "pausing"
    if not write(state, rec):
        print("crew: refusing pause: %s does not read back as written" % os.path.join(state, "pause.json"))
        return 1
    if lock := commands()["down"].land_locked(state):
        print("crew: pausing: a land holds %s; nothing stopped yet; run mdstack pause again when it ends" % lock)
        return 75
    leads, recs, stopped, held = dict(commands()["lead"].records(state)), dict(runs(state)), set(rec["stopped"]), []
    for index, name in sorted(tmux.list_windows(session) if tmux.has_session(session) else [], reverse=True):
        if index == 0:
            continue
        if stop_pane(session, index):
            held.append(name)
            continue
        tmux.kill_window(session, index)
        if name in leads:
            os.remove(commands()["lead"].record_path(state, leads[name]["role"].removesuffix("-lead")))
        elif name in recs:
            stopped.add(name)
    for name, r in recs.items():
        if remote_run.host_of(r):
            if remote_run.kill(values, name, r, keep=True)["result"] == "ok":
                stopped.add(name)
            else:
                held.append(name)
    rec.update(stopped=sorted(stopped), state="pausing" if held else "paused")
    if not write(state, rec):
        print("crew: pause incomplete: %s does not read back as written" % os.path.join(state, "pause.json"))
        return 1
    if held:
        print("crew: pause incomplete: pane processes survived, or their host did not answer, in %s; barrier kept, "
              "run mdstack pause again" % ", ".join(held))
        return 1
    print("crew: paused; window 0 and the watcher kept; stopped %s; work kept (mdstack resume)" % (
        ", ".join(rec["stopped"]) or "no runs"))
    return 0
