#!/usr/bin/env python3
"""Hardened remote call: host entrypoint, runner and primary-side client (docs/runtimes/multi-device.md#remote-call-and-runner).

Usage: crew-remote.py --root DIR                                  (forced command: JSON request on stdin, reply on stdout)
       crew-remote.py --root DIR runner [--once] [--interval SECS]  (the host's user-level runner service)

Install on a host: the crew key's authorized_keys line is
`command="python3 <bundle>/scripts/crew-remote.py --root <root>",restrict <key>`. The client (`call`) runs
`ssh <host> crew-host` with batch mode, strict host keys, no forwarding, no SendEnv of its own and bounded dead-peer timeouts;
the entrypoint reads no environment but SSH_ORIGINAL_COMMAND.
A request is one JSON object {verb, version, request_id?, ...}, never a shell string, never evaluated. Every reply
is {"result": "ok", ...}, {"result": "refused", "reason"} or {"result": "failed", "error"}, exit 0; only the client
yields {"result": "unreachable"}, on a transport failure. Refused: a verb outside the closed set or not built yet, a
different eng-crew version, an SSH command other than crew-host, a `root` or path outside root, and a mutating verb
without a request id. A retried request id returns its first reply. The runner keeps the host's crew tmux session
alive, so runs outlive the SSH session, and writes runner.json under root as its heartbeat.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
VERBS = {"version", "check", "prepare", "spawn", "probe", "pull", "send", "kill", "logs", "capture", "attach",
         "seed", "job", "result"}
MUTATING = {"prepare", "spawn", "send", "kill", "seed", "job"}
REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
SESSION, INTERVAL = "crew-host", 30
SSH = ["ssh", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ClearAllForwardings=yes",
       "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2"]


def version():
    path = os.path.join(os.path.dirname(HERE), "VERSION")  # the release bundle's tag; a checkout is "dev"
    if not os.path.exists(path):
        return "dev"
    with open(path) as f:
        return f.read().strip()


def tmux():
    spec = importlib.util.spec_from_file_location("crew_tmux", os.path.join(HERE, "crew-tmux.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runner_state(root):
    try:
        with open(os.path.join(root, "runner.json")) as f:
            beat = json.load(f)
        fresh = time.time() - beat["beat"] <= 3 * beat["interval"]
    except (OSError, ValueError, KeyError, TypeError):
        return "down"
    return "up" if fresh and tmux().has_session(SESSION) else "down"


HANDLERS = {"version": lambda request, root: dict(result="ok", version=version(), runner=runner_state(root))}


def confined(root, path):
    real = os.path.realpath(os.path.join(root, path))
    return real == os.path.realpath(root) or real.startswith(os.path.realpath(root) + os.sep)


def handle(request, root, command=None):
    if command not in (None, "", "crew-host"):
        return dict(result="refused", reason="SSH command must be crew-host")
    if not isinstance(request, dict) or request.get("verb") not in VERBS:
        return dict(result="refused", reason="unknown verb")
    verb = request["verb"]
    if verb != "version" and request.get("version") != version():
        return dict(result="refused", reason="version skew: host %s, call %s" % (version(), request.get("version")))
    if "root" in request and os.path.realpath(os.path.expanduser(str(request["root"]))) != os.path.realpath(root):
        return dict(result="refused", reason="root differs from the host's root")
    paths = [v for k, v in request.items() if k == "path" or k.endswith("_path")]
    if any(not isinstance(p, str) or not confined(root, p) for p in paths):
        return dict(result="refused", reason="path outside root")
    rid = request.get("request_id")
    if verb in MUTATING and not (isinstance(rid, str) and REQUEST_ID.fullmatch(rid)):
        return dict(result="refused", reason="mutating verb needs a request id")
    if verb not in HANDLERS:
        return dict(result="refused", reason="verb %s not built on this host" % verb)
    done = os.path.join(root, "requests", "%s.json" % rid) if verb in MUTATING else None
    if done and os.path.exists(done):
        with open(done) as f:
            return json.load(f)
    try:
        reply = HANDLERS[verb](request, root)
    except Exception as e:  # noqa: BLE001 - the caller gets a structured failure, never a traceback
        reply = dict(result="failed", error="%s: %s" % (type(e).__name__, e))
    if done:
        os.makedirs(os.path.dirname(done), exist_ok=True)
        with open(done + ".tmp", "w") as f:
            json.dump(reply, f)
        os.replace(done + ".tmp", done)
    return reply


def runner(root, once=False, interval=INTERVAL):
    adapter = tmux()
    while True:
        if not adapter.has_session(SESSION):
            adapter.new_session(SESSION, "runner", root, {}, "tail -f /dev/null")
        with open(os.path.join(root, "runner.json.tmp"), "w") as f:
            json.dump(dict(pid=os.getpid(), beat=time.time(), interval=interval, session=SESSION), f)
        os.replace(os.path.join(root, "runner.json.tmp"), os.path.join(root, "runner.json"))
        if once:
            return 0
        time.sleep(interval)


def call(host, verb, request_id=None, timeout=45, **fields):
    """One hardened SSH call; a mutating verb gets a request id, reused on retry so the host acts once."""
    request = dict(fields, verb=verb, version=version())
    if verb in MUTATING:
        request["request_id"] = request_id or uuid.uuid4().hex
    try:
        r = subprocess.run([*SSH, host, "crew-host"], input=json.dumps(request), capture_output=True, text=True,
                           timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        return dict(result="unreachable", error="%s: %s" % (type(e).__name__, e), request_id=request.get("request_id"))
    if r.returncode == 255:
        return dict(result="unreachable", error=r.stderr.strip()[-200:], request_id=request.get("request_id"))
    try:
        reply = json.loads(r.stdout)
        if r.returncode == 0 and reply.get("result") in ("ok", "refused", "failed"):
            return reply
    except (ValueError, AttributeError):
        pass
    return dict(result="failed", error="entrypoint exit %d: no structured reply" % r.returncode)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", required=True)
    p.add_argument("mode", nargs="?", choices=["runner"])
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=INTERVAL)
    args = p.parse_args()
    root = os.path.expanduser(args.root)
    os.makedirs(root, exist_ok=True)
    if args.mode == "runner":
        return runner(root, args.once, args.interval)
    try:
        request = json.load(sys.stdin)
    except ValueError:
        request = None
    print(json.dumps(handle(request, root, os.environ.get("SSH_ORIGINAL_COMMAND"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
