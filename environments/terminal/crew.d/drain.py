"""`mdstack drain` prints and empties `wake/queue.jsonl` without losing a concurrent append.

Usage: mdstack drain --project FILE [--org-profile FILE]
"""
import glob
import os
import sys
from crew_shared import profile, queue_lock


def register(sub):
    p = sub.add_parser("drain")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    """Print every queued wake record as a JSON line and empty the queue (renamed first, so none is lost)."""
    _, _, state = profile(args)
    queue = os.path.join(state, "wake", "queue.jsonl")
    with queue_lock(state):
        if os.path.exists(queue):
            os.rename(queue, "%s.drain-%d-%s" % (queue, os.getpid(), os.urandom(3).hex()))
    for path in sorted(glob.glob(queue + ".drain-*"), key=os.path.getmtime):  # also an interrupted drain's file
        with open(path, encoding="utf-8") as f:
            sys.stdout.writelines(line if line.endswith("\n") else line + "\n" for line in f if line.strip())
        sys.stdout.flush()
        os.remove(path)
    return 0
