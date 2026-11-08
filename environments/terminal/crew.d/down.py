"""`mdstack down` stops a repo's tmux crew (SIGTERM then SIGKILL each pane process group first).

Usage: mdstack down --project FILE [--org-profile FILE] [--preserve]

--preserve is the maintenance stop before a migration (#1178): it stops the armed watcher (SIGTERM; refuses if it
outlives the grace) and every pane's processes, but keeps each run's worktree, record, claim, inbox and status file.
"""
import fcntl
import os
import signal
import time
from crew_shared import commands, kill_run, profile, stop_pane, tmux

WATCHER_GRACE = 5.0


def register(sub):
    p = sub.add_parser("down")
    p.add_argument("--project")
    p.add_argument("--org-profile")
    p.add_argument("--preserve", action="store_true", help="stop the watcher and panes; keep every run's work")


def stop_watcher(state):
    """SIGTERM the armed watcher and wait for it to exit; its PID if it is still armed after the grace."""
    armed = commands()["watch"].armed
    pidfile = os.path.join(state, "wake", "watcher.pid")
    pid = armed(pidfile)
    if pid:
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + WATCHER_GRACE
        while armed(pidfile) and time.monotonic() < deadline:
            time.sleep(0.1)
    return armed(pidfile)


def land_locked(state):
    """The land lock's path while another process holds it, else None."""
    lock = os.path.join(state, "locks", "merge.lock")
    if os.path.exists(lock):
        with open(lock) as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return lock
    return None


def run(args):
    values, session, state = profile(args, "worktree_root")
    preserve = getattr(args, "preserve", False)
    if not tmux.has_session(session) and not preserve:
        print("crew: %s not running" % session)
        return 0
    lock = land_locked(state)
    if lock:
        print("crew: refusing down: the land lock %s is held" % lock)
        return 1
    if preserve:
        args.keep_work = True
        pid = stop_watcher(state)
        if pid:
            print("crew: refusing down: the watcher (pid %d) is still armed" % pid)
            return 1
        if not tmux.has_session(session):
            print("crew: %s not running; watcher stopped" % session)
            return 0
    if getattr(args, "keep_work", False):  # Offboarding stops writers before checking and archiving their work.
        held = [name for index, name in sorted(tmux.list_windows(session), reverse=True)
                if index != 0 and stop_pane(session, index)]
        if held:
            print("crew: refusing down: pane processes survived in %s" % ", ".join(held))
            return 1
    else:
        held = [name for index, name in sorted(tmux.list_windows(session), reverse=True)  # coordinator last
                if index != 0 and kill_run(values, session, state, name)]
    if held:
        print("crew: refusing down: unlanded work in %s; land it or mdstack kill --discard --reason" % ", ".join(held))
        return 1
    pgid = stop_pane(session, 0)
    if pgid:
        print("crew: refusing down: process group %d in window 0 survived SIGKILL" % pgid)
        return 1
    tmux.kill_session(session)
    for _, rec in commands()["lead"].records(state):
        os.remove(commands()["lead"].record_path(state, rec["role"].removesuffix("-lead")))
    print("crew: stopped %s" % session)
    return 0
