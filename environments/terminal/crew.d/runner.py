"""Run the targeted local set on a forge-less host, falling back to a local run (docs/runtimes/multi-device.md).

Usage: mdstack runner run --head SHA [--host HOST] [--poll SECS] [--project FILE] [--org-profile FILE] -- CHECK...
       mdstack runner logs JOB_ID [COMMAND] [--project FILE] [--org-profile FILE]

CHECK is `check-repo` or a dev/tests/*/test-*.py name; the tests become one `tests` command. The checkout must be at
--head. Host: --host, else the ready forge-less host with the lowest load against max_runs. run seeds a bundle of
HEAD (`seed`), starts a `job` and polls `result` every --poll seconds, then stores the result under
$CREW_STATE/runner/<job_id>/ and prints `runner:<host>/<job_id> head=<sha>` and each command's exit. A transport
failure on 3 calls in a row, a refused or a failed reply runs the same commands locally and prints
`runner: <host> <unreachable|refused: reason|failed: error>; ran locally`; a late remote result is discarded. No
forge-less host: run locally. A red remote command is a red run. Exit 1 if any command exits non-zero.
logs prints the stored job's capped log tails, fetched again from its host, for one command or all.
"""
import base64
import json
import os
import subprocess
import tempfile
import time
import uuid
from crew_shared import commands, load, profile

REMOTE = load("crew_remote", "environments/terminal/remote/crew-remote.py")


def register(sub):
    p = sub.add_parser("runner", help="run the targeted local set on a forge-less host, else locally")
    actions = p.add_subparsers(dest="action", required=True)
    p = actions.add_parser("run")
    p.add_argument("--head", required=True)
    p.add_argument("--host")
    p.add_argument("--poll", type=float, default=3)
    commands()["host"].options(p)
    p.add_argument("checks", nargs="+")
    p = actions.add_parser("logs")
    p.add_argument("job_id")
    p.add_argument("command", nargs="?")
    commands()["host"].options(p)


def remote(values, host, verb, poll, **fields):
    """One call to host's address, retried with the same request id while the transport fails, at most 3 calls in a
    row."""
    for attempt in range(3):
        time.sleep(poll if attempt else 0)
        reply = REMOTE.call(commands()["host"].address(values, host), verb, **fields)
        if reply["result"] != "unreachable":
            return reply
        fields["request_id"] = reply.get("request_id")
    return reply


def pick(args, values, session, state):
    host = commands()["host"]
    if args.host:
        return args.host
    ready = []
    for name in host.inventory(values):
        cap = host.setting(values, name, "max_runs", 1)
        if not host.setting(values, name, "forge", True):
            facts = host.inspect_host(args, values, session, state, name)
            if facts["ready"] and facts["load"] < cap:
                ready.append((facts["load"] / cap, name))
    return min(ready)[1] if ready else None


def run_remote(host, values, head, spec, poll):
    """The job's result, or the fallback reason as a string."""
    project, job_id = values["repo.owner"] + "__" + values["repo.name"], head[:7] + "-" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "bundle", "create", "-q", os.path.join(tmp, "head.bundle"), "HEAD"], check=True)
        with open(os.path.join(tmp, "head.bundle"), "rb") as f:
            bundle = base64.b64encode(f.read()).decode()
    root = commands()["host"].setting(values, host, "root", "~/.mdstack")
    reply = remote(values, host, "seed", poll, timeout=660, project=project, root=root, bundle=bundle)
    if reply["result"] == "ok":
        reply = remote(values, host, "job", poll, project=project, root=root, job_id=job_id, head=head, commands=spec)
    while reply["result"] == "ok" and "commands" not in reply:  # a retried job_id replies done without results
        time.sleep(poll)
        reply = remote(values, host, "result", poll, root=root, job_id=job_id)
    if reply["result"] == "unreachable":
        return "unreachable"
    if reply["result"] != "ok":
        return "%s: %s" % (reply["result"], reply.get("reason") or reply.get("error", ""))
    return dict(reply, host=host, job_id=job_id, head=head, spec=spec)


def run(args):
    values, session, state = profile(args)
    if args.action == "logs":
        stored = os.path.join(state, "runner", os.path.basename(args.job_id), "result.json")
        if not os.path.exists(stored):
            print("crew runner: no stored job " + args.job_id)
            return 1
        with open(stored) as f:
            host = json.load(f)["host"]
        reply = remote(values, host, "result", 3, root=commands()["host"].setting(values, host, "root", "~/.mdstack"),
                       job_id=args.job_id)
        if reply["result"] != "ok":
            print("crew runner: %s %s" % (reply["result"], reply.get("reason") or reply.get("error", "")))
        for c in reply.get("commands", []):
            if args.command in (None, c["command"]):
                print("== %s exit %d (%s)\n%s" % (c["command"], c["exit"], c["log"], c["tail"]))
        return 0 if reply["result"] == "ok" else 1
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if subprocess.run(["git", "rev-parse", "--verify", "-q", args.head + "^{commit}"], capture_output=True,
                      text=True).stdout.strip() != head:
        print("crew runner: the checkout is at %s, not --head %s" % (head or "no commit", args.head))
        return 2
    bad = [c for c in args.checks if c != "check-repo" and not REMOTE.TEST_NAME.fullmatch(os.path.basename(c))]
    if bad:
        print("crew runner: not check-repo or a dev/tests/*/test-*.py name: " + " ".join(bad))
        return 2
    tests = [os.path.basename(c) for c in args.checks if c != "check-repo"]
    spec = [dict(command="check-repo")] * ("check-repo" in args.checks) \
        + [dict(command="tests", files=tests)] * bool(tests)
    if args.host and args.host not in commands()["host"].inventory(values):
        print("crew runner: unknown inventory host " + args.host)
        return 2
    host = pick(args, values, session, state)
    done = run_remote(host, values, head, spec, args.poll) if host else "no forge-less host"
    if isinstance(done, dict):
        os.makedirs(os.path.join(state, "runner", done["job_id"]), exist_ok=True)
        with open(os.path.join(state, "runner", done["job_id"], "result.json"), "w") as f:
            json.dump(done, f)
        print("runner:%s/%s head=%s" % (host, done["job_id"], done["head"]))
        codes = [(c["command"], c["exit"]) for c in done["commands"]]
    else:
        print("runner: %s; ran locally" % " ".join(filter(None, (host, done))))
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
        print("local head=%s" % head, flush=True)
        codes = [(c["command"], subprocess.run(REMOTE.job_argv(c, top), cwd=top, stdin=subprocess.DEVNULL).returncode)
                 for c in spec]
    for command, code in codes:
        print("%s exit %d" % (command, code))
    return 1 if any(code for _, code in codes) else 0
