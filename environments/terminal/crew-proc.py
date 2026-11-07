"""OS process helpers for scripts/crew, shared by every session backend: start time, parent pid and the process
tree beneath a session object's first process, read from ps. Python 3.11+ stdlib only."""
import os
import shutil
import subprocess


def proc_start(pid):
    """Start time of a process, so a reused pid never passes for the recorded run; empty when it is gone."""
    return subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


def proc_parent(pid):
    """Parent pid of a process, or None when it is gone: 1 marks an orphan whose tmux server died (#818)."""
    out = subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def live_child(pid, harness):
    """A live tool session beneath the pane; persistent helpers in the harness session do not count."""
    wrappers = {harness, harness + ".real", os.path.basename(os.path.realpath(shutil.which(harness) or harness))}
    result = subprocess.run(["ps", "-axo", "pid=,ppid=,stat=,comm="], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("crew: process probe unavailable")
    out = result.stdout
    processes = [line.split(None, 3) for line in out.splitlines() if len(line.split(None, 3)) == 4]
    parents = {str(pid)}
    while parents:
        next_ = set()
        for child, parent, stat, command in processes:
            if parent in parents and not stat.startswith("Z"):
                if "s" in stat and os.path.basename(command) not in wrappers:
                    return True
                next_.add(child)
        parents = next_
    return False


def descendants(pid):
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,stat=,comm="], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError("crew: process probe unavailable")
    rows = [line.split(None, 3) for line in out.stdout.splitlines() if len(line.split(None, 3)) == 4]
    found, parents = set(), {str(pid)}
    while parents:
        parents = {child for child, parent, stat, _ in rows if parent in parents and not stat.startswith("Z")}
        found.update(parents)
    return found
