"""`mdstack down` stops a repo's tmux crew (SIGTERM then SIGKILL each pane process group first).

Usage: mdstack down --project FILE [--org-profile FILE] [--preserve]

Runs on a role host (#345) stop through the host's kill, which keeps unlanded work there; one the host cannot stop
(unlanded work, or the host unreachable) keeps its record, and down exits 1 naming it. Remote runs are stopped even
when the primary's session is gone.

Both modes first stop the armed watcher (SIGTERM; refuses if it outlives the grace), also with no session left (#1346).
--preserve is the maintenance stop before a migration (#1178): it stops the watcher and every pane's processes, but keeps each run's worktree, record, claim, inbox and status file.
"""
import fcntl
import os
import signal
import time
from crew_shared import commands, kill_run, profile, remote_run, runs, stop_pane, tmux

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
    live = tmux.has_session(session)
    remote = any(remote_run.host_of(rec) for _, rec in runs(state))  # they outlive the primary's session
    watching = commands()["watch"].armed(os.path.join(state, "wake", "watcher.pid"))
    if not live and not preserve and not remote and not watching:
        print("crew: %s not running" % session)
        return 0
    lock = land_locked(state)
    if lock:
        print("crew: refusing down: the land lock %s is held" % lock)
        return 1
    pid = stop_watcher(state)  # first: a persistent watcher would restart what down stops (#1346)
    if pid:
        print("crew: refusing down: the watcher (pid %d) is still armed" % pid)
        return 1
    if preserve:
        args.keep_work = True
    if not live and not remote:
        print("crew: %s not running; watcher stopped" % session)
        return 0
    windows = tmux.list_windows(session) if live else []
    if getattr(args, "keep_work", False):  # Offboarding stops writers before checking and archiving their work.
        held = [name for index, name in sorted(windows, reverse=True)
                if index != 0 and stop_pane(session, index)]
        held += [name for name, rec in runs(state) if remote_run.host_of(rec) and
                 remote_run.kill(values, name, rec, keep=True)["result"] != "ok"]
        if held:
            print("crew: refusing down: pane processes survived, or their host did not answer, in %s" % ", ".join(held))
            return 1
    else:
        held = [name for index, name in sorted(windows, reverse=True)  # coordinator last
                if index != 0 and kill_run(values, session, state, name)]
        held += [name for name, rec in list(runs(state)) if remote_run.host_of(rec) and kill_run(values, session, state, name)]
    if held:
        print("crew: refusing down: unlanded work or an unreachable host in %s; land it or mdstack kill --discard "
              "--reason" % ", ".join(held))
        return 1
    pgid = stop_pane(session, 0) if live else None
    if pgid:
        print("crew: refusing down: process group %d in window 0 survived SIGKILL" % pgid)
        return 1
    if live:
        tmux.kill_session(session)
    for _, rec in commands()["lead"].records(state):
        os.remove(commands()["lead"].record_path(state, rec["role"].removesuffix("-lead")))
    print("crew: stopped %s" % session if live else "crew: %s not running; its remote runs stopped" % session)
    return 0
