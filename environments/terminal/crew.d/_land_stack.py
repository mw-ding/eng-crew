"""Session stack land (docs/interfaces.md#stack-land, #1605), driven by `mdstack land stack|stack-done|resume`.

A change backend declaring land.stack = true lands a linear stack of changes in one atomic request:
change.land-stack with <stack> filled as space-separated <change>:<head-sha> pairs, base first; change.stack-status
reads it back with one line per member, in stack order, `<change> none|queued|landing|landed <revision>|failed
<reason>`, then, when the backend has run its combined-stack check, a last `check <reference>` line. Under
land.stack_tests_against_tip a landed stack without that line is unknown: the declaration alone is no receipt.

Atomic means every member reads the same state: all none (never requested), all queued or landing (poll), all
landed (each with a full revision), all failed. A mixed state, a missing, extra or reordered member line or a
malformed line is unknown, never none, and records no merge. The request runs only on all none, after
change.read-head returns each member's checked head; a lost acknowledgement is read back, never resent. The intent
land/stack/<base change>-<base head>.json is recorded before the first read; `landed` marks it and prints one merge
record line and marker per member; failed, a stale member head and a request reading none drop it; a timeout or an
unknown state keeps it for `mdstack land resume`, which never requests. stack-done clears an intent marked landed.
"""
import datetime
import glob
import json
import os
import re
import time

MEMBER = re.compile(r"(\S+) (?:(none|queued|landing)|landed ([0-9a-f]{40}|[0-9a-f]{64})|failed (\S.*))")
CHECK = re.compile(r"check (\S+)")
SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def parse(text):
    """--stack N:SHA,N:SHA,... (base first) -> [(change, head)]; ValueError unless two or more distinct changes."""
    members = []
    for part in (text or "").split(","):
        change, _, head = part.partition(":")
        if not change.isdigit() or not SHA.fullmatch(head):
            raise ValueError("--stack member %r is not <n>:<full lowercase head sha>" % part)
        members.append((int(change), head))
    if len(members) < 2 or len({c for c, _ in members}) != len(members):
        raise ValueError("--stack needs two or more distinct changes, base first")
    return members


def tag(members):
    return "stack " + ", ".join("#%d @ %s" % (c, h[:7]) for c, h in members)


def intent_path(state, members):
    return os.path.join(state, "land", "stack", "%d-%s.json" % members[0])


def commands(renderer, members, single):
    """change.land-stack and change.stack-status with <stack> filled, plus each member's change.read-head; single
    builds one member's command as `mdstack land` does."""
    stack = " ".join("%d:%s" % m for m in members)
    cmds = {}
    for op in ("land-stack", "stack-status"):
        cmd = renderer.line("<op:change.%s>" % op)
        if "<stack>" not in cmd:
            raise ValueError("change.%s carries no <stack> placeholder" % op)
        cmd = cmd.replace("<stack>", stack)
        left = re.search(r"<([^<>\s!/=-][^<>\n]*)>", cmd)
        if left:
            raise ValueError("change.%s keeps an unfilled placeholder %s" % (op, left.group(0)))
        cmds[op] = re.sub(r"\s*\n\s*", " ", cmd)
    cmds["read-head"] = {c: single("read-head", c, h) for c, h in members}
    return cmds


def read(call, cmds, members, need_check):
    """("none"|"landing"|"failed", detail), ("landed", ([revision per member], check or None)) or ("unknown", why)."""
    code, out = call(cmds["stack-status"])
    if code != 0:
        return "unknown", "exit %d, output %r" % (code, out)
    lines = [ln.strip(" \t\r") for ln in out.split("\n")]
    check = CHECK.fullmatch(lines[-1]) if lines else None
    if check:
        lines = lines[:-1]
    if len(lines) != len(members):
        return "unknown", "readback names %d member lines, expected %d" % (len(lines), len(members))
    states = []
    for line, (change, _) in zip(lines, members):
        m = MEMBER.fullmatch(line)
        if not m or m.group(1) != str(change):
            return "unknown", "readback line %r is not #%d's state" % (line, change)
        states.append(m.group(2) or ("landed" if m.group(3) else "failed"))
    kinds = set(states)
    if kinds == {"landed"}:
        if need_check and not check:
            return "unknown", "landed, but no `check <reference>` line for the declared combined-stack test"
        revisions = [MEMBER.fullmatch(ln).group(3) for ln in lines]
        return "landed", (revisions, check.group(1) if check else None)
    if kinds == {"none"}:
        return "none", ""
    if kinds <= {"queued", "landing"}:
        return "landing", ""
    if kinds == {"failed"}:
        return "failed", MEMBER.fullmatch(lines[0]).group(4)
    return "unknown", "members disagree (%s); an atomic stack land never splits" % ", ".join(states)


def save(path, intent):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(intent, f)
    os.replace(path + ".tmp", path)


def drop(path):
    if os.path.exists(path):
        os.remove(path)


def poll(call, cmds, members, values, need, state, detail):
    deadline = time.monotonic() + values["runtime.options.land_timeout"]
    while state == "landing":
        if time.monotonic() >= deadline:
            return "timeout", "after %ds, still landing" % values["runtime.options.land_timeout"]
        print("crew: land %s: landing" % tag(members), flush=True)
        time.sleep(values["runtime.options.land_poll_interval"])
        state, detail = read(call, cmds, members, need)
    return state, detail


def finish(path, intent, members, values, state, detail):
    """Report a terminal or given-up stack land; one merge record line and marker per member, exit 0, only on landed."""
    if state == "landed":
        revisions, check = detail
        save(path, dict(intent, landed=revisions, check=check))
        names = ", ".join("#%d" % c for c, _ in members)
        tested = ("; tested as a combined stack on `%s` by the backend's stack land check `%s` "
                  "(`land.stack_tests_against_tip`)" % (values["repo.default_branch"], check)) if check else ""
        for (change, head), revision in zip(members, revisions):
            print("crew: landed #%d @ %s as %s" % (change, head[:7], revision))
            print("record: #%d: Landed revision: `%s` (checked head `%s`); stack land of %d (%s)%s."
                  % (change, revision, head, len(members), names, tested))
            print("marker: #%d: <!-- crew:v1 role=synthesizer pass=merge pr=%d sha=%s round=n/a verdict=n/a "
                  "landed=%s -->" % (change, change, head, revision))
        return 0
    if state in ("timeout", "unknown"):
        print("blocked: land %s: %s %s; intent kept, mdstack land resume reads it back" % (tag(members), state, detail))
        return 1
    drop(path)
    print("blocked: land %s: %s%s" % (tag(members), state, ": " + detail if detail else ""))
    return 1


def request(call, cmds, members, values, need, state_dir):
    path = intent_path(state_dir, members)
    intent = {"members": [list(m) for m in members],
              "recorded": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if os.path.exists(path):
        with open(path) as f:
            if [tuple(m) for m in json.load(f).get("members", [])] != members:
                print("blocked: land %s: another stack intent from this base is recorded; mdstack land resume "
                      "reads it back" % tag(members))
                return 1
    else:
        save(path, intent)  # intent first: a restart reads the stack back before anything else
    state, detail = read(call, cmds, members, need)
    if state == "none":
        for change, head in members:
            code, live = call(cmds["read-head"][change])
            if code != 0 or live != head:
                drop(path)
                print("blocked: land %s: stale head, #%d head is %r; no request sent for any member, rerun the §7 "
                      "gates at the new head" % (tag(members), change, live))
                return 1
        sent = call(cmds["land-stack"])[0] == 0  # a lost acknowledgement is read back, never resent
        state, detail = read(call, cmds, members, need)
        if state == "none":
            drop(path)
            print("blocked: land %s: request %s and stack-status is none; rerun the §7 gate check for every member "
                  "before a new request" % (tag(members), "sent" if sent else "failed"))
            return 1
    state, detail = poll(call, cmds, members, values, need, state, detail)
    return finish(path, intent, members, values, state, detail)


def resume(call, build, values, need, state_dir):
    """Read every recorded stack intent back; never requests. build(members) -> cmds."""
    code = 0
    for path in sorted(glob.glob(os.path.join(state_dir, "land", "stack", "*.json"))):
        try:
            with open(path) as f:
                intent = json.load(f)
            members = [(int(c), h) for c, h in intent["members"]]
            cmds = build(members)
        except (OSError, ValueError, KeyError, TypeError) as e:
            print("blocked: stack land intent %s unreadable (%s); nothing requested" % (os.path.basename(path), e))
            code = 1
            continue
        state, detail = read(call, cmds, members, need)
        if state == "none":
            drop(path)
            print("blocked: land %s: never requested at these heads; intent dropped, rerun the §7 gate check for "
                  "every member before a request" % tag(members))
            code = 1
            continue
        state, detail = poll(call, cmds, members, values, need, state, detail)
        code = finish(path, intent, members, values, state, detail) or code
    return code


def done(members, state_dir):
    path = intent_path(state_dir, members)
    try:
        with open(path) as f:
            intent = json.load(f)
    except (OSError, ValueError):
        intent = {}
    if not intent.get("landed") or [tuple(m) for m in intent.get("members", [])] != members:
        print("crew: refusing stack-done %s: no matching intent marked landed; only a confirmed landed stack "
              "completes a land" % tag(members))
        return 1
    drop(path)
    print("crew: land %s done; intent cleared" % tag(members))
    return 0
