"""`crew handoff` posts the coordinator's side of an owner handoff command on the control item (protocol §9).

Usage: crew handoff to RUNTIME_ID [--mode drain|stop] [--deadline MINUTES] --sign TEXT --project FILE
       crew handoff abort --sign TEXT --project FILE
       crew handoff takeover RUNTIME_ID --sign TEXT --project FILE
`to` posts `draining` and, in drain mode, writes `asks/handoff.json` so the watcher wakes the coordinator at
the deadline (delete it once the drain ends). Each subcommand re-reads the record first and refuses an illegal
transition; `--dry-run` prints the post instead. The manifest and `offered` are `crew handoff manifest` (#211).
"""
import datetime
import json
import os
import re
import subprocess
from crew_shared import ownership_module, profile

RUNTIME_ID = r"[a-z][a-z0-9-]*@[a-z0-9-]{1,63}"


def register(sub):
    p = sub.add_parser("handoff")
    p.add_argument("command", choices=["to", "abort", "takeover"])
    p.add_argument("runtime", nargs="?", help="target runtime id for to; outgoing runtime id for takeover")
    p.add_argument("--mode", choices=["drain", "stop"], default="drain")
    p.add_argument("--deadline", type=int, default=30, help="drain deadline in minutes (default 30)")
    p.add_argument("--sign", required=True, help="the signature line: '— <emoji> <bot> (<title>) · <harness> · <model>'")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def transition(args, me, owner, phase, opened, now):
    """(state, handoff id, from, to, reason line, drain deadline or None) for the command, or a refusal string."""
    if args.command != "abort" and not re.fullmatch(RUNTIME_ID, args.runtime or ""):
        return "needs a runtime id <runtime>@<instance>"
    if args.command == "to":
        if owner != me or opened:
            return "only the owning runtime with no open handoff may hand off (owner %s)" % owner
        if args.runtime == me or args.deadline < 1:
            return "target must be another runtime and the deadline at least 1 minute"
        until = (now + datetime.timedelta(minutes=args.deadline)).strftime("%Y-%m-%dT%H:%M:%SZ")
        tail = ", deadline %d min (%s)" % (args.deadline, until) if args.mode == "drain" else ""
        return ("draining", "%s-%s" % (now.strftime("%Y%m%d"), os.urandom(3).hex()), me, args.runtime,
                "Owner command (chat): handoff to %s, mode %s%s." % (args.runtime, args.mode, tail),
                until if args.mode == "drain" else None)
    if args.command == "abort":
        if not opened or me != (opened["from"] if opened["state"] == "draining" else opened["to"]):
            return "no open handoff opened by %s" % me
        return "aborted", opened["handoff"], opened["from"], opened["to"], "Owner command (chat): handoff abort.", None
    reuse = opened and opened["from"] == args.runtime and opened["to"] == me
    if owner != args.runtime or me == args.runtime or (opened and not reuse):
        return "takeover needs %s to own the repo and no other open handoff (owner %s)" % (args.runtime, owner)
    return ("takeover", opened["handoff"] if reuse else "%s-%s" % (now.strftime("%Y%m%d"), os.urandom(3).hex()),
            args.runtime, me, "Owner command (chat): takeover from %s." % args.runtime, None)


def run(args):
    values, _, state = profile(args)
    if not values.get("repo.control_item"):
        print("crew: handoff: repo.control_item is not set")
        return 1
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    me = values["runtime.name"] + "@" + values.get("runtime.instance", "")
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        result = transition(args, me, *ownership_module.read_record(values), now)
        sha = subprocess.run(["gh", "api", "repos/%s/commits/HEAD" % repo, "--jq", ".sha"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as e:
        print("crew: handoff: record or default branch unreadable: %s" % e)
        return 1
    if isinstance(result, str):
        print("crew: handoff: refusing %s: %s" % (args.command, result))
        return 1
    st, hid, frm, to, reason, until = result
    body = "[%s/handoff] %s %s → %s (%s)\n%s\n\n<!-- crew:v1 role=coordinator pass=handoff handoff=%s state=%s " \
        "from=%s to=%s cmd-id=chat sha=%s round=n/a verdict=n/a -->\n%s\n" % (
            values.get("identities.coordinator.name", "Ash"), st, frm, to, hid, reason, hid, st, frm, to, sha, args.sign)
    if args.dry_run:
        print(body, end="")
        return 0
    if subprocess.run(["gh", "issue", "comment", str(values["repo.control_item"]), "-R", repo, "--body-file", "-"],
                      input=body, text=True).returncode:
        print("crew: handoff: post failed; re-read the record and retry with the same id %s" % hid)
        return 1
    asks = os.path.join(state, "asks", "handoff.json")
    if until:
        os.makedirs(os.path.dirname(asks), exist_ok=True)
        with open(asks, "w") as f:
            json.dump({"deadline": until.replace("Z", "+00:00"), "handoff": hid}, f)
    elif st == "aborted" and os.path.exists(asks):
        os.remove(asks)
    print("crew: handoff: posted %s %s" % (st, hid))
    return 0
