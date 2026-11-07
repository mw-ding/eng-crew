#!/usr/bin/env python3
"""Fake actions/ binding for the fixture connector: keeps the actions/cli.md contract over a fake state dir.

Usage: action.py --capabilities [--json] | action.py <action> [<op>] [--flag value]... [--json]

State lives under $CREW_ACTIONS_FAKE. `read` completes; `claim acquire` writes a claim file and refuses a second
acquire; every other action is refused as unsupported (exit 6).
"""
import json
import os
import re
import sys
import time

DECLARED = {"read": "supported", "claim": "emulated"}
EXIT = {"completed": 0, "refused": 6, "stale": 5, "pending": 3, "failed": 7, "unknown": 4}


def finish(action, op, outcome, code=None, text="", refs=None, as_json=True, exit_code=None):
    reason = None if outcome == "completed" else {"code": code, "text": text}
    record = {"contract": "eng-crew.actions/0.1", "action": action, "op": op, "outcome": outcome, "reason": reason,
              "refs": refs or {}, "result": {}, "capability": DECLARED.get(action, "unsupported"),
              "key": ":".join(filter(None, (action, op))), "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print(json.dumps(record) if as_json else "%s: %s%s %s" % (outcome, action, " " + op if op else "", text or "ok"))
    return EXIT[outcome] if exit_code is None else exit_code


def main(argv):
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if argv == ["--capabilities"]:
        print(json.dumps({"contract": "eng-crew.actions/0.1", "capabilities": DECLARED}))
        return 0
    words = (argv[:next((i for i, a in enumerate(argv) if a.startswith("--")), len(argv))])[:2]
    action = words[0] if words else None
    known = ["read", "resolve-policy", "check-ownership", "claim", "heartbeat", "notify", "ack", "wait", "report",
             "spawn-worker", "supervise", "workspace", "artifact", "post-marker", "tracker", "run-check",
             "publish-change", "update-base", "compare-content", "land", "owner-channel", "knowledge-read",
             "knowledge-propose-edit"]
    if action not in known:
        return finish(action, None, "refused", "usage", "unknown action", as_json=as_json, exit_code=2)
    op = words[1] if len(words) > 1 else None
    flags = {}
    for i, a in enumerate(argv):
        if a.startswith("--") and i + 1 < len(argv):
            flags[a] = argv[i + 1]
    if action not in DECLARED:
        return finish(action, op, "refused", "unsupported", "declared unsupported", as_json=as_json)
    if "--head" in flags and not re.fullmatch(r"[0-9a-f]{40}", flags["--head"]):
        return finish(action, op, "refused", "invalid-ref", "short or malformed head", as_json=as_json)
    if action == "claim" and op == "acquire":
        path = os.path.join(os.environ["CREW_ACTIONS_FAKE"], "claim-" + flags.get("--item", "none"))
        if os.path.exists(path):
            return finish(action, op, "refused", "claimed", "live claim held", as_json=as_json)
        open(path, "w").close()
        return finish(action, op, "completed", refs={"claim": os.path.basename(path)}, as_json=as_json)
    return finish(action, op, "completed", refs={"item": flags.get("--item", "")}, as_json=as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
