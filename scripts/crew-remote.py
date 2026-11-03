#!/usr/bin/env python3
"""Hardened remote call: host entrypoint, runner and primary-side client (docs/runtimes/multi-device.md#remote-call-and-runner).

Usage: crew-remote.py --root DIR                                  (forced command: JSON request on stdin, reply on stdout)
       crew-remote.py --root DIR runner [--once] [--interval SECS]  (the host's user-level runner service)

Install on a host: the crew key's authorized_keys line is
`command="python3 <bundle>/scripts/crew-remote.py --root <root>",restrict <key>`. The client (`call`) runs
`ssh <host> crew-host` with batch mode, strict host keys, no forwarding and bounded dead-peer timeouts. It takes only
the host's auth and host-key settings from the SSH config (`ssh -G`) and then runs with `-F none`, so no SendEnv,
SetEnv, forwarding or proxy from any config reaches the call; the entrypoint reads no environment but SSH_ORIGINAL_COMMAND.
A request is one JSON object {verb, version, request_id?, ...}, never a shell string, never evaluated. Every reply
is {"result": "ok", ...}, {"result": "refused", "reason"} or {"result": "failed", "error"}, exit 0; only the client
yields {"result": "unreachable"}, on a transport failure. Refused: a verb outside the closed set or not built yet, a
different eng-crew version, an SSH command other than crew-host, a `root` or path outside root, and a mutating verb
without a request id. Built verbs: `version`; `prepare` (create or fetch mirrors/<owner>__<repo>.git
with the host's gh login) and `seed` (a forge-less host: fetch the primary's base64 one-ref git bundle into the mirror
as refs/crew/heads/<sha>, and refs/heads/<branch> when given); both then make wt/ and state/<owner>__<repo>/, and a
failed reply names its `step`. A retried request id returns its first reply. The runner keeps the host's crew tmux session
alive, so runs outlive the SSH session, and writes runner.json under root as its heartbeat.
"""
import argparse
import base64
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
PROJECT = re.compile(r"[A-Za-z0-9-]+__[A-Za-z0-9._-]+")  # owner__repo; a GitHub owner has no underscore
PREPARE_TIMEOUT = 600
SESSION, INTERVAL = "crew-host", 30
SSH = ["ssh", "-F", "none", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
       "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5",
       "-o", "ServerAliveCountMax=2"]
KEEP = {"hostname", "user", "port", "identityfile", "identitiesonly", "certificatefile", "identityagent",
        "userknownhostsfile", "globalknownhostsfile", "hostkeyalias"}  # auth and host keys; never env, forwards, proxies


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


def sh(step, *argv):
    r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=PREPARE_TIMEOUT)
    if r.returncode:
        raise Failed(step, r.stderr.strip()[-200:] or "exit %d" % r.returncode)
    return r.stdout


class Failed(Exception):
    def __init__(self, step, error):
        super().__init__(error)
        self.reply = dict(result="failed", step=step, error=error)


def project_step(handler):
    """Shared by prepare and seed: an owner__repo check, a failure that names its step, then the run directories."""
    def run(request, root):
        project = request.get("project")
        if not isinstance(project, str) or not PROJECT.fullmatch(project):
            return dict(result="refused", reason="project must be owner__repo")
        mirror = os.path.join(root, "mirrors", project + ".git")
        try:
            reply = handler(request, root, project, mirror)
        except Failed as e:
            return e.reply
        for path in ("wt", *(os.path.join("state", project, d) for d in ("status", "inbox", "verdicts"))):
            os.makedirs(os.path.join(root, path), exist_ok=True)
        return dict(reply, result="ok", mirror=os.path.relpath(mirror, root))
    return run


@project_step
def prepare(request, root, project, mirror):
    """Create the project mirror with the host's own gh login, or fetch it."""
    if os.path.isdir(mirror):
        sh("fetch", "git", "-C", mirror, "fetch", "--quiet", "--prune", "origin")
        return dict(step="fetch")
    sh("clone", "gh", "repo", "clone", project.replace("__", "/", 1), mirror, "--", "--mirror", "--quiet")
    return dict(step="clone")


@project_step
def seed(request, root, project, mirror):
    """Forge-less host: fetch the primary's one-ref bundle into the mirror as refs/crew/heads/<sha> (and `branch`)."""
    data = base64.b64decode(request.get("bundle", ""), validate=True)
    bundle = os.path.join(root, "requests", request["request_id"] + ".bundle")
    os.makedirs(os.path.dirname(bundle), exist_ok=True)
    with open(bundle, "wb") as f:
        f.write(data)
    try:
        if not os.path.isdir(mirror):
            sh("init", "git", "init", "--quiet", "--bare", mirror)
        heads = sh("verify", "git", "-C", mirror, "bundle", "list-heads", bundle).split()
        if len(heads) != 2:
            raise Failed("verify", "bundle must carry exactly one ref")
        sh("fetch", "git", "-C", mirror, "fetch", "--quiet", bundle, heads[1])
        sh("fetch", "git", "-C", mirror, "update-ref", "refs/crew/heads/" + heads[0], heads[0])
        if request.get("branch"):
            sh("branch", "git", "-C", mirror, "update-ref", "refs/heads/" + str(request["branch"]), heads[0])
    finally:
        os.remove(bundle)
    return dict(step="seed", tip=heads[0])


HANDLERS = {"version": lambda request, root: dict(result="ok", version=version(), runner=runner_state(root)),
            "prepare": prepare, "seed": seed}


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


def ssh_argv(host, config=None):
    """The hardened argv, or None if the SSH config does not resolve. The config only supplies KEEP settings."""
    r = subprocess.run(["ssh", "-G", *(["-F", config] if config else []), host], capture_output=True, text=True,
                       timeout=10)
    settings = [line.split(" ", 1) for line in r.stdout.splitlines() if line.split(" ", 1)[0] in KEEP]
    return None if r.returncode else [*SSH, *[x for k, v in settings for x in ("-o", k + "=" + v)], host, "crew-host"]


def call(host, verb, request_id=None, timeout=45, config=None, **fields):
    """One hardened SSH call; a mutating verb gets a request id, reused on retry so the host acts once."""
    request = dict(fields, verb=verb, version=version())
    if verb in MUTATING:
        request["request_id"] = request_id or uuid.uuid4().hex
    try:
        argv = ssh_argv(host, config)
        if argv is None:
            return dict(result="failed", error="ssh -G: SSH config does not resolve " + host)
        r = subprocess.run(argv, input=json.dumps(request), capture_output=True, text=True, timeout=timeout)
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
