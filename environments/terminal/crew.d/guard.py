"""`mdstack guard` is the coordinator's Claude Code turn-end guard (a no-op unless `CREW_ROLE=coordinator`): it
blocks a stop while work is in flight (a run record in `runs/`, a non-empty `wake/queue.jsonl` or an open owner
ask in `asks/<n>.json`) and no watcher is armed. A live watcher holding `wake/watcher.lock` whose PID file is missing gets
a specific warning instead of a block (#399). Read-only ownership permits ending the turn; draining keeps the block until in-flight runs end.

Usage: mdstack guard --state DIR   (Claude Code Stop hook, or the Codex notify recipe; reads the hook JSON on stdin)
"""
import fcntl
import json
import os
import sys
from crew_shared import crew_render, ownership

WAKE = "wake: turn-end guard"  # the Codex notify recipe's fixed wake line (tmux.md mdstack guard)


def lock_held(state):
    """Whether a live watcher holds wake/watcher.lock (#399); the probe takes it for an instant, which a starting
    watcher's short retry outlasts."""
    try:
        fd = os.open(os.path.join(state, "wake", "watcher.lock"), os.O_RDONLY)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


def register(sub):
    sub.add_parser("guard").add_argument("--state", required=True)


def run(args):
    """Block a turn end while work is in flight (a run record, a queued wake or an open owner ask record in
    asks/) and no watcher is armed.

    At most one block per stop cycle: with stop_hook_active true (already continuing for this hook), or a Codex
    notify payload whose turn input ends with the recipe's own wake line (#170), allow with a warning. Malformed or
    empty stdin counts as not active. A no-op outside the
    coordinator window: the hook file sits in the project, so role windows load it too (#139 F5)."""
    if os.environ.get("CREW_ROLE") != "coordinator":
        return 0
    project = os.environ.get("CREW_PROJECT")
    if project:
        values, problems = crew_render.resolve(project, None)
        if problems or ownership(values) == "read-only":
            return 0
    try:
        hook = json.loads(sys.stdin.read())
        active = hook.get("stop_hook_active") is True or hook.get("input-messages", [])[-1:] == [WAKE]
    except (ValueError, AttributeError, TypeError):
        active = False
    queue = os.path.join(args.state, "wake", "queue.jsonl")
    records = [os.path.join(args.state, d) for d in ("runs", "asks", "leads")]  # asks/<n>.json: open owner asks (C8, #301)
    busy = any(os.path.isdir(d) and any(n.endswith(".json") for n in os.listdir(d)) for d in records) or \
        (os.path.exists(queue) and os.path.getsize(queue) > 0)
    try:
        with open(os.path.join(args.state, "wake", "watcher.pid")) as f:
            os.kill(int(f.read().strip()), 0)
        armed = True
    except (OSError, ValueError):
        armed = False
    msg = "Work is in flight and no watcher is armed: drain wake/queue.jsonl and re-arm the watcher " \
        "before ending the turn (docs/runtimes/tmux.md Q1)."
    if busy and not armed and lock_held(args.state):  # armed, but its PID file was lost: say so, never block (#399)
        print(json.dumps({"systemMessage": "crew guard: a live watcher holds wake/watcher.lock but wake/watcher.pid "
                          "is missing or stale; leave it running (mdstack down stops it)"}))
    elif busy and not armed:
        print(json.dumps({"systemMessage": "crew guard: " + msg} if active else {"decision": "block", "reason": msg}))
    return 0
