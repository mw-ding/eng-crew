"""crew land-lock acquire|release --project FILE [--org-profile FILE]"""
import fcntl
import json
import os
import signal
import subprocess
import time
from crew_shared import profile


def proc_identity(pid):
    """(start time, command line) of a live process from ps, or None; the start time tells a reused PID apart."""
    out = [subprocess.run(["ps", "-o", col + "=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
           for col in ("lstart", "command")]
    return tuple(out) if all(out) else None


def register(sub):
    p = sub.add_parser("land-lock")
    p.add_argument("action", choices=["acquire", "release"])
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    """Serial land (tmux.md C7): acquire takes an flock on locks/merge.lock, held by a detached child until
    release; a second acquire fails fast."""
    _, _, state = profile(args)
    lock, pidfile = os.path.join(state, "locks", "merge.lock"), os.path.join(state, "locks", "merge.pid")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    if args.action == "acquire":
        fd = os.open(lock, os.O_CREAT | os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("crew: land lock %s is held; another land is in progress" % lock)
            return 1
        pid = os.fork()
        if pid == 0:  # holder: keeps the lock's open file until release signals it
            os.setsid()
            null = os.open(os.devnull, os.O_RDWR)
            for n in (0, 1, 2):
                os.dup2(null, n)
            while True:
                signal.pause()
        with open(pidfile, "w") as f:
            json.dump({"pid": pid, "start": proc_identity(pid)[0]}, f)
        print("crew: land lock acquired (holder pid %d)" % pid)
        return 0
    with open(lock, "a") as f:
        for attempt in range(50):  # signal the holder, then await the unlock
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if attempt == 0:  # signal only our holder: same PID, same start time, a land-lock acquire
                    try:
                        with open(pidfile) as p:
                            rec = json.load(p)
                        live = proc_identity(int(rec["pid"]))
                    except (OSError, ValueError, TypeError, KeyError):
                        live = rec = None
                    if not live or live[0] != rec["start"] or "land-lock acquire" not in live[1]:
                        print("crew: refusing release: land lock %s is held, but not by the holder recorded in "
                              "merge.pid (stale or reused PID); nothing signalled" % lock)
                        return 1
                    os.kill(int(rec["pid"]), signal.SIGTERM)
                time.sleep(0.1)
        else:
            print("crew: land lock %s still held after release" % lock)
            return 1
    if os.path.exists(pidfile):
        os.remove(pidfile)
    print("crew: land lock released" if attempt else "crew: land lock not held")
    return 0
