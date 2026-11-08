#!/usr/bin/env python3
"""Local lab test host: bundle activation, the run's forced key and the PID-1 supervisor (M20.1 lab B, #1356).

Usage: crew-lab-host.py activate --stage DIR --tag TAG [--bundle DIR] [--record FILE] [--source-sha SHA]
       crew-lab-host.py authorize --user NAME --key-file FILE [--bundle DIR]
       crew-lab-host.py supervise --user NAME [--bundle DIR]
       crew-lab-host.py ready --user NAME

Runs inside the lab image built from the Dockerfile beside it (docs/runtimes/multi-device.md, Remote acceptance
criteria and the local lab). `activate` checks the release bundle and SHA256SUMS that `docker cp` put in --stage
with the shared verifier (scripts/crew-install.py), moves the bundle to --bundle only after every check passes, then
writes --record: tag, bundle and SHA256SUMS digests, and the source SHA, which a non-release (dev) tag must name.
`authorize` writes the run's public key as the user's only authorized_keys line, forced to the entrypoint with
`restrict`. `supervise` is PID 1: it starts sshd (as root) and the runner (as the non-root user, in a scrubbed env),
restarts either when it exits and reaps every other child. `ready` exits 0 only while the runner's runner.json
heartbeat is fresh; it is the image's HEALTHCHECK. Nothing here reads or copies a login, token, SSH agent or home:
the image creates the user's home empty and the runner gets only PATH, HOME, USER, LOGNAME and LANG.
"""
import argparse
import importlib.util
import json
import os
import pwd
import re
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
RELEASE = re.compile(r"v\d+\.\d+\.\d+(-rc\.\d+)?")
KEY = re.compile(r"(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) [A-Za-z0-9+/]+=*( [\w.@-]+)?")
SSHD = ["/bin/sh", "-c", "mkdir -p /run/sshd && ssh-keygen -A && exec /usr/sbin/sshd -D -e -f /etc/ssh/crew-lab.conf"]
ENTRY = "environments/terminal/remote/crew-remote.py"


def crew_install():
    spec = importlib.util.spec_from_file_location("crew_install", os.path.join(ROOT, "scripts", "crew-install.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def activate(stage, tag, bundle, record, source_sha=None):
    """Verify, then move the bundle into place and record what was activated. Raises ValueError before any move."""
    if not RELEASE.fullmatch(tag) and not (source_sha and re.fullmatch(r"[0-9a-f]{40}", source_sha)):
        raise ValueError("a dev tag %s needs --source-sha, the full commit both ends record" % tag)
    if os.path.exists(bundle):
        raise ValueError("bundle already active at %s; a lab host activates once" % bundle)
    sha, sums_sha = crew_install().verify(stage, tag, bundle)
    with open(record, "w") as f:
        json.dump(dict(tag=tag, bundle_sha256=sha, sha256sums_sha256=sums_sha, source_sha=source_sha), f)
    return sha


def authorize(home, key, bundle):
    """Write the forced-command line for key as home/.ssh/authorized_keys, replacing any earlier run's line."""
    key = key.strip()
    if not KEY.fullmatch(key):
        raise ValueError("key file must hold one public key line, with no options")
    line = 'command="python3 %s --root %s",restrict %s\n' % (
        os.path.join(bundle, ENTRY), os.path.join(home, ".mdstack"), key)
    ssh = os.path.join(home, ".ssh")
    os.makedirs(ssh, mode=0o700, exist_ok=True)
    path = os.path.join(ssh, "authorized_keys")
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(line)
    os.replace(path + ".tmp", path)
    return line


def runner_service(user, bundle):
    """(argv, env, start) for the runner as user; refuses root."""
    if user.pw_uid == 0:
        raise ValueError("the runner never runs as root")
    root = os.path.join(user.pw_dir, ".mdstack")
    argv = ["python3", os.path.join(bundle, ENTRY), "--root", root, "runner"]
    env = dict(PATH="/usr/local/bin:/usr/bin:/bin", HOME=user.pw_dir, USER=user.pw_name, LOGNAME=user.pw_name,
               LANG="C.UTF-8")
    # Clearing supplementary groups needs root; as root, keeping them would leave root's groups on the runner.
    groups = [] if os.geteuid() == 0 else None
    return argv, env, lambda: subprocess.Popen(argv, env=env, cwd=user.pw_dir, user=user.pw_uid, group=user.pw_gid,
                                               extra_groups=groups, stdin=subprocess.DEVNULL)


def supervise(services, stop, pause=1.0, log=sys.stderr):
    """Start each service, restart it after it exits, reap every other child; when stop() is true, end them all."""
    running = {}
    while not stop():
        for name, start in services.items():
            if name not in (n for n, _ in running.values()):
                proc = start()
                running[proc.pid] = (name, proc)
                print("lab: started %s pid %d" % (name, proc.pid), file=log, flush=True)
        try:
            while True:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if not pid:
                    break
                if pid in running:
                    name, proc = running.pop(pid)
                    proc.returncode = os.waitstatus_to_exitcode(status)
                    print("lab: %s exited %d; restarting" % (name, proc.returncode), file=log, flush=True)
        except ChildProcessError:
            pass
        time.sleep(pause)
    for _, proc in running.values():
        proc.terminate()
    for _, proc in running.values():
        proc.wait()


def ready(home):
    try:
        with open(os.path.join(home, ".mdstack", "runner.json")) as f:
            beat = json.load(f)
        return time.time() - beat["beat"] <= 3 * beat["interval"]
    except (OSError, ValueError, KeyError, TypeError):
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["activate", "authorize", "supervise", "ready"])
    p.add_argument("--user")
    p.add_argument("--bundle", default="/opt/mdstack")
    p.add_argument("--stage")
    p.add_argument("--tag")
    p.add_argument("--record", default="/opt/mdstack-lab.json")
    p.add_argument("--source-sha")
    p.add_argument("--key-file")
    args = p.parse_args()
    try:
        if args.mode == "activate":
            print("lab: activated %s sha256 %s" % (args.tag, activate(args.stage, args.tag, args.bundle, args.record,
                                                                     args.source_sha)))
            return 0
        user = pwd.getpwnam(args.user)
        if args.mode == "authorize":
            with open(args.key_file) as f:
                authorize(user.pw_dir, f.read(), args.bundle)
            os.chown(os.path.join(user.pw_dir, ".ssh"), user.pw_uid, user.pw_gid)
            os.chown(os.path.join(user.pw_dir, ".ssh", "authorized_keys"), user.pw_uid, user.pw_gid)
            return 0
        if args.mode == "ready":
            return 0 if ready(user.pw_dir) else 1
        stop = []
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.append(sig))
        supervise({"sshd": lambda: subprocess.Popen(SSHD, stdin=subprocess.DEVNULL),
                   "runner": runner_service(user, args.bundle)[2]}, lambda: bool(stop))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as e:
        print("lab: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
