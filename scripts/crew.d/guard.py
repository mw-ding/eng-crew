"""`crew guard` is the coordinator's Claude Code turn-end guard (a no-op unless `CREW_ROLE=coordinator`): it
blocks a stop while work is in flight (a run record in `runs/`, a non-empty `wake/queue.jsonl` or an open owner
ask in `asks/<n>.json`) and no watcher is armed. Read-only or draining ownership permits ending the turn.

Usage: crew guard --state DIR   (Claude Code Stop hook; reads the hook JSON on stdin)
"""
import json
import os
import sys
from crew_shared import crew_render, ownership, runs


def register(sub):
    sub.add_parser("guard").add_argument("--state", required=True)


def run(args):
    """Block a turn end while work is in flight (a run record, a queued wake or an open owner ask record in
    asks/) and no watcher is armed.

    At most one block per stop cycle: with stop_hook_active true (already continuing for this hook), allow
    with a warning. Malformed or empty stdin counts as not active. A no-op outside the
    coordinator window: the hook file sits in the project, so role windows load it too (#139 F5)."""
    if os.environ.get("CREW_ROLE") != "coordinator":
        return 0
    project = os.environ.get("CREW_PROJECT")
    if project:
        values, problems = crew_render.resolve(project, None)
        if problems or ownership(values) != "active":
            return 0
    try:
        active = json.loads(sys.stdin.read()).get("stop_hook_active") is True
    except (ValueError, AttributeError):
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
    if busy and not armed:
        print(json.dumps({"systemMessage": "crew guard: " + msg} if active else {"decision": "block", "reason": msg}))
    return 0
