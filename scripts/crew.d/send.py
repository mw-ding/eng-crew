"""crew send WINDOW KIND REF... [--wait-ack SECS] --project FILE"""
import json
import os
import re
import time
from crew_shared import profile, tmux, wait_ack


# crew send (tmux.md C3): refs only. A ref is an issue/PR number, a full SHA, an https link or a path; no whitespace,
# so no diff or log fits, and lines that open a diff hunk or a traceback are refused outright.
KIND = re.compile(r"[a-z][a-z0-9-]{0,31}")
REF = re.compile(r"#\d+|[0-9a-f]{40}|https://[^\s]+|[\w.~/-]+")
MARKER = re.compile(r"^(---|\+\+\+|@@)|Traceback")
MAX_REF, MAX_LINE = 200, 1024


def register(sub):
    p = sub.add_parser("send")
    p.add_argument("window")
    p.add_argument("kind")
    p.add_argument("refs", nargs="+")
    p.add_argument("--wait-ack", type=float, help="seconds to wait for ack: <msg-id> in the status file")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    values, session, state = profile(args)
    bad = [r for r in args.refs if len(r) > MAX_REF or not REF.fullmatch(r) or MARKER.search(r)]
    if not KIND.fullmatch(args.kind) or bad:
        print("crew: refusing send: refs only (issue/PR #n, full SHA, https link, path; max %d chars each): %s" %
              (MAX_REF, ", ".join(repr(r[:40]) for r in bad) or "bad kind %r" % args.kind[:40]))
        return 2
    msg = {"id": "%s-%s" % (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), os.urandom(3).hex()), "kind": args.kind,
           "refs": args.refs, "from": os.environ.get("CREW_ID") or os.environ.get("CREW_ROLE") or "coordinator",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    line = json.dumps(msg) + "\n"
    if len(line.encode()) > MAX_LINE:
        print("crew: refusing send: message is %d bytes, over %d; send fewer refs" % (len(line.encode()), MAX_LINE))
        return 2
    index = dict((n, i) for i, n in tmux.list_windows(session)).get(args.window) if tmux.has_session(session) else None
    if index is None:
        print("crew: refusing send: no window %s in %s" % (args.window, session))
        return 1
    os.makedirs(os.path.join(state, "inbox"), exist_ok=True)
    with open(os.path.join(state, "inbox", args.window + ".jsonl"), "a", encoding="utf-8") as f:
        f.write(line)
    tmux.send_keys(session, index, "inbox: " + msg["id"])  # a nudge only; the inbox file is the message
    print("crew: sent %s to %s" % (msg["id"], args.window))
    return wait_ack(state, args.window, msg["id"], args.wait_ack) if args.wait_ack is not None else 0
