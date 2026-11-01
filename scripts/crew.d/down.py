"""`crew down` stops a repo's tmux crew (SIGTERM then SIGKILL each pane process group first).

Usage: crew down --project FILE [--org-profile FILE]
"""
import fcntl
import os
from crew_shared import kill_run, profile, stop_pane, tmux


def register(sub):
    p = sub.add_parser("down")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    values, session, state = profile(args, "worktree_root")
    if not tmux.has_session(session):
        print("crew: %s not running" % session)
        return 0
    lock = os.path.join(state, "locks", "merge.lock")
    if os.path.exists(lock):
        with open(lock) as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("crew: refusing down: the land lock %s is held" % lock)
                return 1
    held = [name for index, name in sorted(tmux.list_windows(session), reverse=True)  # coordinator last
            if index != 0 and kill_run(values, session, state, name)]
    if held:
        print("crew: refusing down: unlanded work in %s; land it or crew kill --discard --reason" % ", ".join(held))
        return 1
    pgid = stop_pane(session, 0)
    if pgid:
        print("crew: refusing down: process group %d in window 0 survived SIGKILL" % pgid)
        return 1
    tmux.kill_session(session)
    print("crew: stopped %s" % session)
    return 0
