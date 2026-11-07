"""`crew action` is the terminal binding of the actions contract (actions/cli.md): one generic verb per call, carried
out over the files and commands the tmux and herdr runtimes already use, with the contract's exit code and JSON result.

Usage: crew action NAME [OP] [--project FILE] [--actor RUN] [--role ROLE] [--item REF] [--head SHA] [--key KEY]
                   [action flags] [--json]
       crew action --capabilities [--project FILE] [--json]

Supported here (every other action is refused as unsupported, exit 6):
  check-ownership [--for start|write|land]   the control item, as `crew ownership` reads it
  heartbeat [--claim HANDLE]                 rewrites the `heartbeat:` line in the run's claim file
  notify --to RUN --kind KIND --ref REF...   `crew send` (tmux runtime only); pending until the receiver's ack
  ack --message ID                           appends `ack: <id>` to status/<run>.status
  report --status S --ref REF... [--reason TEXT]   appends `<status>: <refs> <reason>` to status/<run>.status

The run is --actor (default $CREW_ID); --project defaults to $CREW_PROJECT. Reason codes this binding adds:
`not-held` (heartbeat: the claim is missing or is not the run's), `no-recipient` (notify: no such window) and `solo`
(notify: a solo item's fix refs are never delivered to a builder; post them on the change instead).
"""
import argparse
import contextlib
import functools
import io
import json
import os
import re
import sys
import time
from crew_shared import acked, commands, crew_render, load, ownership, ownership_module

EXIT = {"completed": 0, "pending": 3, "unknown": 4, "stale": 5, "refused": 6, "failed": 7}
SUPPORTED = ("check-ownership", "heartbeat", "notify", "ack", "report")
STATUSES = ("ack", "done", "blocked", "paused", "failed")
SHA = re.compile(r"[0-9a-f]{40}")
RUN = re.compile(r"[A-Za-z0-9][\w.-]*")
MSG = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{6}")


class Usage(Exception):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Usage(message)


class Outcome(Exception):
    def __init__(self, outcome, code=None, text="", refs=None, result=None):
        super().__init__(text)
        self.outcome, self.code, self.text = outcome, code, text
        self.refs, self.result = refs or {}, result or {}


@functools.cache
def contract():
    """actions/contract.py (the action table), loaded on use so other commands never depend on it."""
    return load("crew_actions_contract", "actions/contract.py")


def capabilities(values):
    tmux = bool(values) and values.get("runtime.name") == "tmux"
    return {a: "supported" if a in SUPPORTED and (a != "notify" or tmux) else "unsupported" for a in contract().ACTIONS}


def register(sub):
    p = sub.add_parser("action")
    p.add_argument("--capabilities", action="store_true")
    p.add_argument("--project")
    p.add_argument("--json", action="store_true")
    p.add_argument("argv", nargs=argparse.REMAINDER)


def resolve(project):
    values, problems = crew_render.resolve(project, None) if project else (None, ["no --project or $CREW_PROJECT"])
    if problems:
        raise Outcome("failed", "unreadable", "; ".join(problems)[:300])
    state_dir = str(values.get("paths.state_dir", ""))
    if re.search(r"<[^<>]+>", state_dir):
        raise Outcome("failed", "unreadable", "paths.state_dir is still the placeholder %s" % state_dir)
    return values, os.path.join(os.path.abspath(state_dir), "%s__%s" % (values["repo.owner"], values["repo.name"]))


def parse(argv):
    """(name, op, args) for one call; Usage for an unknown action, op or flag, or a missing required flag."""
    name = argv[0] if argv and not argv[0].startswith("-") else None
    if name not in contract().ACTIONS:
        raise Usage("unknown action %r" % (name or ""))
    ops = contract().ACTIONS[name]
    op = argv[1] if ops and len(argv) > 1 else None
    if ops and op not in ops:
        raise Usage("%s needs an op: %s" % (name, ", ".join(ops)))
    p = Parser(prog="crew action " + name, add_help=False)
    p.add_argument("--project", default=os.environ.get("CREW_PROJECT"))
    p.add_argument("--actor", default=os.environ.get("CREW_ID"))
    p.add_argument("--role", default=os.environ.get("CREW_ROLE"))
    for flag in ("--item", "--head", "--key"):
        p.add_argument(flag)
    p.add_argument("--json", action="store_true")
    if name == "check-ownership":
        p.add_argument("--for", dest="for_", choices=["start", "write", "land"], default="start")
    elif name == "heartbeat":
        p.add_argument("--claim")
    elif name == "notify":
        p.add_argument("--to", required=True)
        p.add_argument("--kind", required=True)
        p.add_argument("--ref", action="append", required=True)
    elif name == "ack":
        p.add_argument("--message", required=True)
    elif name == "report":
        p.add_argument("--status", choices=STATUSES, required=True)
        p.add_argument("--ref", action="append", default=[])
        p.add_argument("--reason")
    rest = argv[1 + bool(op):]
    return name, op, p.parse_args(rest) if name in SUPPORTED else p.parse_known_args(rest)[0]


def status_path(state, args):
    if not args.actor:
        raise Usage("no --actor or $CREW_ID")
    if not RUN.fullmatch(args.actor):
        raise Outcome("refused", "invalid-ref", "bad run name %r" % args.actor[:40])
    return os.path.join(state, "status", args.actor + ".status")


def append(path, line):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def do_check_ownership(args, values, state):
    mode = ownership(values)
    result = {"state": mode, "runtime": "%s@%s" % (values["runtime.name"], values.get("runtime.instance", ""))}
    if not ownership_module.permits(mode, args.for_):
        raise Outcome("refused", "not-owner", "ownership %s; refusing %s" % (mode, args.for_), result=result)
    return {}, result


def do_heartbeat(args, values, state):
    record = os.path.join(state, "runs", "%s.json" % args.actor) if args.actor else None
    try:
        with open(record) as f:
            held = json.load(f).get("claim")
    except (TypeError, OSError, ValueError):
        held = None
    claim = args.claim or held
    if not claim:
        raise Usage("no --claim and no run record naming one")
    path = os.path.realpath(claim if "/" in claim else os.path.join(state, "claims", claim))
    if os.path.dirname(path) != os.path.realpath(os.path.join(state, "claims")) or not os.path.isfile(path) or \
            held and os.path.realpath(held) != path:
        raise Outcome("refused", "not-held", "claim %s is not held by %s" % (claim, args.actor or "this run"))
    beat = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(path, encoding="utf-8") as f:
        lines = [line for line in f.read().splitlines() if not line.startswith("heartbeat:")]
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write("\n".join(lines + ["heartbeat: " + beat]) + "\n")
    os.replace(path + ".tmp", path)
    return {"claim": os.path.basename(path)}, {"heartbeat": beat}


def do_notify(args, values, state):
    if values["runtime.name"] != "tmux":
        raise Outcome("refused", "unsupported", "notify needs the tmux runtime, not %s" % values["runtime.name"])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        if not ownership_module.require_ownership(values, "start"):
            raise Outcome("refused", "not-owner", out.getvalue().strip())
        try:
            code = commands()["send"].run(argparse.Namespace(window=args.to, kind=args.kind, refs=args.ref,
                                                             wait_ack=None, project=args.project, org_profile=None))
        except SystemExit:
            code = None
    said = out.getvalue().strip()
    print(said, file=sys.stderr)
    found = MSG.search(said)
    refs = {"to": args.to, "message": found.group(0)} if found else {"to": args.to}
    if code == 0 and found:
        raise Outcome("pending", "queued" if "queued" in said else "no-receipt", said.splitlines()[-1], refs)
    if code == 0:
        raise Outcome("refused", "solo", said.splitlines()[-1], refs)
    raise Outcome(*{2: ("refused", "invalid-ref"), 1: ("refused", "no-recipient"), 4: ("unknown", "uncertain-write")}
                  .get(code, ("failed", "unreadable")), (said.splitlines() or [""])[-1], refs)


def do_ack(args, values, state):
    path = status_path(state, args)
    if not MSG.fullmatch(args.message):
        raise Outcome("refused", "invalid-ref", "bad message id %r" % args.message[:40])
    try:
        with open(os.path.join(state, "inbox", args.actor + ".jsonl"), encoding="utf-8") as f:
            known = any(json.loads(line).get("id") == args.message for line in f if line.strip())
    except (OSError, ValueError):
        known = False
    if not known:
        raise Outcome("refused", "invalid-ref", "no message %s in the inbox of %s" % (args.message, args.actor))
    if not acked(state, args.actor, args.message):
        append(path, "ack: " + args.message)
    return {"message": args.message, "status": path}, {"line": "ack: " + args.message}


def do_report(args, values, state):
    path = status_path(state, args)
    send = commands()["send"]
    bad = [r for r in args.ref if len(r) > send.MAX_REF or not send.REF.fullmatch(r) or send.MARKER.search(r)]
    if bad or args.reason and ("\n" in args.reason or len(args.reason) > send.MAX_LINE):
        raise Outcome("refused", "invalid-ref", "refs only, and a one-line reason: %r" % (bad[:1] or args.reason[:40]))
    if args.status == "done" and not args.ref:
        raise Outcome("refused", "invalid-ref", "done needs an output reference")
    if args.status in ("blocked", "paused", "failed") and not args.reason:
        raise Usage("--status %s needs --reason" % args.status)
    line = "%s: %s" % (args.status, " ".join(args.ref + ([args.reason] if args.reason else [])))
    append(path, line.rstrip())
    return {"status": path}, {"line": line.rstrip()}


def run(args):
    as_json, op, call, key, cap = args.json or "--json" in args.argv, None, None, "", "supported"
    try:
        if args.capabilities:
            try:
                values = resolve(args.project or os.environ.get("CREW_PROJECT"))[0]
            except Outcome:
                values = None
            caps = capabilities(values)
            print(json.dumps({"contract": contract().CONTRACT, "capabilities": caps}) if as_json else
                  "\n".join("%s: %s" % kv for kv in caps.items()))
            return 0
        name = (args.argv or [None])[0]
        name, op, call = parse(args.argv)
        call.project = call.project or args.project
        key = call.key or ":".join(str(v) for v in (name, op, call.item, call.head, call.role) if v)
        if call.head is not None and not SHA.fullmatch(call.head):
            raise Outcome("refused", "invalid-ref", "--head must be a full 40-character SHA")
        values, state = resolve(call.project)
        cap = capabilities(values)[name]
        if cap == "unsupported":
            raise Outcome("refused", "unsupported", "%s is unsupported in this environment" % name)
        refs, result = globals()["do_" + name.replace("-", "_")](call, values, state)
        outcome = Outcome("completed", refs=refs, result=result)
    except Usage as e:
        outcome, code = Outcome("refused", "usage", str(e)), 2
    except Outcome as e:
        outcome = e
    code = 2 if outcome.code == "usage" else EXIT[outcome.outcome]
    refs = dict({k: v for k, v in (("item", call and call.item), ("head", call and call.head)) if v}, **outcome.refs)
    if as_json:
        print(json.dumps({
            "contract": contract().CONTRACT, "action": name, "op": op, "outcome": outcome.outcome,
            "reason": {"code": outcome.code, "text": outcome.text} if outcome.outcome != "completed" else None,
            "refs": refs, "result": outcome.result, "capability": cap, "key": key,
            "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
    else:
        primary = outcome.text or next(iter(refs.values()), "")
        print(("%s: %s%s %s" % (outcome.outcome, name or "", " " + op if op else "", primary)).rstrip())
    return code
