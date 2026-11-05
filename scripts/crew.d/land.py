"""`crew land status` / `request` drives an asynchronous land (docs/interfaces.md#asynchronous-land-design, #873 B2).

Usage: crew land status|request --project FILE [--org-profile FILE] --pr N --head SHA

Only for a change backend that declares land.mode = "async"; a sync backend is refused. The commands come from
the backend map's change.land-status, change.read-head and change.land, with <n> and <head-sha> filled.
status: one land-status read for the change at the pinned head; prints the state, exit 1 when unknown.
request: run after the final §7 gate check. Reads land-status and requests only on `none`, and only while the
change head still equals --head. A failed request call (a lost acknowledgement) is resolved by reading the
status again, never by a resend. Then polls every runtime.options.land_poll_interval seconds until `landed`
(exit 0, prints the landed revision) or `failed`, an unknown status or runtime.options.land_timeout (exit 1,
`blocked:`). Takes no land lock and builds no train. Persisted intent and restart read-back are B3 (#931).
"""
import os
import re
import subprocess
import time
from crew_shared import crew_render, profile, require_ownership

STATUS = re.compile(r"(none|queued|landing)|landed ([0-9a-f]{40}|[0-9a-f]{64})|failed (\S.*)")
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def register(sub):
    p = sub.add_parser("land")
    p.add_argument("action", choices=["status", "request"])
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument("--head", required=True)


def command(renderer, op, pr, head):
    """The backend map's change.<op> with install-time placeholders, <n> and <head-sha> filled, on one line."""
    cmd = renderer.line("<op:change.%s>" % op).replace("<n>", str(pr)).replace("<head-sha>", head)
    left = crew_render.TOKEN.search(cmd)
    if left:
        raise ValueError("change.%s keeps an unfilled placeholder %s" % (op, left.group(0)))
    return re.sub(r"\s*\n\s*", " ", cmd)


def call(cmd):
    """(exit code, first stdout line) of a backend command; a hung call counts as failed."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 124, ""
    return r.returncode, (r.stdout.strip().splitlines() or [""])[0].strip()


def read_status(cmds):
    """("none"|"queued"|"landing"|"landed"|"failed", detail), or ("unknown", why); unknown never means none."""
    code, out = call(cmds["land-status"])
    m = STATUS.fullmatch(out) if code == 0 else None
    if not m:
        return "unknown", "exit %d, output %r" % (code, out)
    if m.group(1):
        return m.group(1), ""
    return ("landed", m.group(2)) if m.group(2) else ("failed", m.group(3))


def run(args):
    values, _, _ = profile(args)
    tag = "#%d @ %s" % (args.pr, args.head[:7])
    if not SHA.fullmatch(args.head):
        print("crew: --head must be a full lowercase commit SHA, got %r" % args.head)
        return 1
    meta = {}
    crew_render.crew_config.resolve_profile(args.project, args.org_profile, meta=meta)
    if meta.get("land.mode", ("sync",))[0] != "async":
        print("crew: refusing land %s: the change backend's land.mode is sync; land with change.land" % tag)
        return 1
    if args.action == "request" and not require_ownership(values, "land"):
        return 1
    renderer = crew_render.Renderer(values, os.path.join(os.path.dirname(crew_render.HERE), "templates"),
                                    overlay=crew_render.pack_overlay(args.project, args.org_profile, values))
    try:
        cmds = {op: command(renderer, op, args.pr, args.head) for op in ("land-status", "read-head", "land")}
    except ValueError as e:
        print("crew: refusing land %s: %s" % (tag, e))
        return 1
    state, detail = read_status(cmds)
    if args.action == "status":
        print(" ".join(filter(None, (state, detail))))
        return 1 if state == "unknown" else 0
    if state == "none":
        code, head = call(cmds["read-head"])
        if code != 0 or head != args.head:
            print("blocked: land %s: stale head, change head is %r; no request sent, rerun the §7 gates at the "
                  "new head" % (tag, head))
            return 1
        if call(cmds["land"])[0] != 0:  # lost acknowledgement: read back, never resend
            state, detail = read_status(cmds)
            if state == "none":
                print("blocked: land %s: request failed and land-status is none; rerun the §7 gate check "
                      "before a new request" % tag)
                return 1
        else:
            state, detail = read_status(cmds)
    deadline = time.monotonic() + values["runtime.options.land_timeout"]
    while state in ("queued", "landing"):
        if time.monotonic() >= deadline:
            print("blocked: land %s: timeout after %ds, still %s" % (tag, values["runtime.options.land_timeout"], state))
            return 1
        print("crew: land %s: %s" % (tag, state), flush=True)
        time.sleep(values["runtime.options.land_poll_interval"])
        state, detail = read_status(cmds)
    if state == "landed":
        print("crew: landed %s as %s" % (tag, detail))
        return 0
    print("blocked: land %s: %s%s" % (tag, state, ": " + detail if detail else ""))
    return 1
