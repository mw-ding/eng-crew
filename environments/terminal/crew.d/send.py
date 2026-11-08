"""`mdstack send` messages a role window by reference: a refs-only inbox line and a fixed nudge, typed once with its
submit confirmed (earlier nudges stacked in the composer cleared, `Enter` retried, exit 4 when it never submits; no
key at all into a window showing a dialog, #315).
The window lookup and inbox append share the queue lock with route's synthesizer check and reap.
Solo findings/CI/merge-up refs are never delivered to builder windows. An `unblocked` to the coordinator that matches an
earlier `blocked` message's refs is recorded in its inbox without a nudge (#578).

Usage: mdstack send WINDOW KIND REF... [--wait-ack SECS] --project FILE
"""
import json
import os
import re
import time
from crew_shared import commands, COMPOSER, dialog, NAMES, profile, queue_lock, tmux, wait_ack, runs, synthesizer_work


# mdstack send (tmux.md C3): refs only. A ref is an issue/PR number, a full SHA, an https link or a path; no whitespace,
# so no diff or log fits, and lines that open a diff hunk or a traceback are refused outright.
KIND = re.compile(r"[a-z][a-z0-9-]{0,31}")
REF = re.compile(r"#\d+|[0-9a-f]{40}|https://[^\s]+|[\w.~/-]+")
MARKER = re.compile(r"^(---|\+\+\+|@@)|Traceback")
MAX_REF, MAX_LINE = 200, 1024
# Verified nudge (#308): a composer's first row opens with a harness adapter's prompt glyph (Codex `›`, Claude Code
# `❯` and a no-break space) and later rows are indented two spaces; a stale nudge is a whole composer line
# `inbox: <msg-id>`.
GLYPH = COMPOSER
NUDGE = re.compile(r"inbox: \d{8}T\d{6}Z-[0-9a-f]{6}")
RETRIES, PAUSE = 3, 0.5


def composer_draft(screen, at):
    """The composer rows from the prompt-glyph row down to the cursor row at (column, row), glyph and indent
    stripped; None when the cursor is not in a composer (no glyph row above it through blank or indented rows)."""
    rows = screen.split("\n")
    if not at or at[1] >= len(rows):
        return None
    for top in range(at[1], -1, -1):
        if GLYPH.match(rows[top]):
            return [GLYPH.sub("", rows[top], 1).strip()] + [r.strip() for r in rows[top + 1:at[1] + 1]]
        if rows[top].strip() and not rows[top].startswith("  "):
            return None
    return None


def stale_nudges(screen, at):
    """The earlier nudge lines a composer holds when they are all it holds and the cursor ends them; else [] (an
    empty composer, other text, a cursor inside the draft or an unknown screen: nothing is cleared)."""
    lines, rows = composer_draft(screen, at), screen.split("\n")
    below = rows[at[1] + 1] if lines is not None and at[1] + 1 < len(rows) else ""
    if not lines or at[0] < len(rows[at[1]].rstrip()) or below.startswith("  ") and below.strip():
        return []
    text = [line for line in lines if line]
    return lines if text and all(NUDGE.fullmatch(line) for line in text) else []


def nudge(session, index, text):
    """Type the nudge once and confirm the submit (firstmate's pattern): clear earlier nudges stacked in the
    composer, type, Enter, and while the nudge is still in the composer retry Enter only, never retyping. None when
    submitted (or no composer is on screen to tell), else why not. A dialog on screen gets no key at all: a
    permission or approval prompt preselects yes, so the nudge's Enter could approve it (#315)."""
    def view():
        return tmux.capture(session, index), tmux.cursor(session, index)
    if dialog(session, index):
        return "dialog: a prompt is on its screen; nothing typed"
    if "doorbell" in tmux.CAPABILITIES:
        return tmux.doorbell(session, index, text)
    stale = stale_nudges(*view())
    if stale:
        tmux.press(session, index, *["C-u"] * (2 * len(stale)))  # C-u clears a line, then joins it to the one above
        time.sleep(PAUSE)
        if any(NUDGE.fullmatch(line) for line in composer_draft(*view()) or []):
            return "its composer still holds earlier inbox lines after the clear; nothing typed"
        print("crew: cleared %d earlier inbox line(s) from the composer" % sum(1 for line in stale if line))
    tmux.send_keys(session, index, text)
    for retry in range(RETRIES + 1):
        time.sleep(PAUSE)
        if text not in (composer_draft(*view()) or []):
            return None
        if retry < RETRIES:
            if dialog(session, index):
                return "dialog: a prompt came up after the nudge was typed; Enter not retried"
            tmux.press(session, index, "Enter")
    return "`%s` is still in its composer after %d Enter retries" % (text, RETRIES)


def register(sub):
    p = sub.add_parser("send")
    p.add_argument("window")
    p.add_argument("kind")
    p.add_argument("refs", nargs="+")
    p.add_argument("--wait-ack", type=float, help="seconds to wait for ack: <msg-id> in the status file")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    values, session, state = profile(args)
    bad = [r for r in args.refs if len(r) > MAX_REF or not REF.fullmatch(r) or MARKER.search(r)]
    if not KIND.fullmatch(args.kind) or bad:
        print("crew: refusing send: refs only (issue/PR #n, full SHA, https link, path; max %d chars each): %s" %
              (MAX_REF, ", ".join(repr(r[:40]) for r in bad) or "bad kind %r" % args.kind[:40]))
        return 2
    builder = values.get("identities.builder.name", NAMES["builder"]).lower()
    if re.fullmatch(re.escape(builder) + r"-\d+", args.window) and args.kind in ("fix", "ci-red", "merge-up") and \
            re.fullmatch(r"#\d+", args.refs[0]):
        if commands()["lead"].solo(values, pr=int(args.refs[0][1:])):
            print("crew: solo item; skip builder delivery; post findings/CI on the PR for the owner's session")
            return 0
    msg = {"id": "%s-%s" % (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()), os.urandom(3).hex()), "kind": args.kind,
           "refs": args.refs, "from": os.environ.get("CREW_ID") or os.environ.get("CREW_ROLE") or "coordinator",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    line = json.dumps(msg) + "\n"
    if len(line.encode()) > MAX_LINE:
        print("crew: refusing send: message is %d bytes, over %d; send fewer refs" % (len(line.encode()), MAX_LINE))
        return 2
    with queue_lock(state):
        index = dict((n, i) for i, n in tmux.list_windows(session)).get(args.window) if tmux.has_session(session) else None
        if index is None:
            builder = values.get("identities.builder.name", NAMES["builder"]).lower()
            if re.fullmatch(re.escape(builder) + r"-\d+", args.window) and args.kind in ("fix", "ci-red") and \
                    len(args.refs) >= 2 and re.fullmatch(r"#\d+", args.refs[0]) and re.fullmatch(r"[0-9a-f]{40}", args.refs[1]):
                with open(os.path.join(state, "wake", "queue.jsonl"), "a") as f:
                    f.write(json.dumps(dict(event="builder-message", window=args.window, kind=args.kind,
                                           refs=args.refs, reason="send", id=msg["id"])) + "\n")
                print("crew: queued builder message %s for route" % msg["id"])
                return 0
            print("crew: refusing send: no window %s in %s" % (args.window, session))
            return 1
        os.makedirs(os.path.join(state, "inbox"), exist_ok=True)
        inbox = os.path.join(state, "inbox", args.window + ".jsonl")
        resolved = False
        if args.kind == "unblocked" and args.window == values.get("identities.coordinator.name", "ash").lower() and \
                os.path.exists(inbox):
            with open(inbox, encoding="utf-8") as f:
                resolved = any(m["kind"] == "blocked" and m["refs"] == args.refs for m in map(json.loads, f))
        with open(inbox, "a", encoding="utf-8") as f:
            f.write(line)
        if dict(runs(state)).get(args.window, {}).get("role") == "synthesizer":
            synthesizer_work(state, args.window)
    if resolved:  # a self-resolved block closes its own blocked message; the coordinator reads it on its next wake
        print("crew: recorded %s to %s; block resolved itself, no nudge" % (msg["id"], args.window))
        return 0
    failed = nudge(session, index, "inbox: " + msg["id"])  # a nudge only; the inbox file is the message
    if failed:
        print("crew: nudge not submitted: %s to %s: %s; the message is in the inbox; treat %s as ambiguous" % (
            msg["id"], args.window, failed, args.window))
        return 4
    print("crew: sent %s to %s" % (msg["id"], args.window))
    return wait_ack(state, args.window, msg["id"], args.wait_ack) if args.wait_ack is not None else 0
