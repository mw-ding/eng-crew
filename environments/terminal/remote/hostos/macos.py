"""macOS host OS adapter (docs/runtimes/multi-device.md#host-os-adapters): the runner as a launchd agent with
KeepAlive in the account's gui/<uid> domain, Darwin `ps` start times and the SSH listener read from netstat.

crew-remote.py loads it by path when `hosts.<name>.capabilities.os` is `macos` and the host's uname is Darwin.
Every call takes the commands it runs through `run(argv) -> (exit, output)`, so tests pass a fake.
"""
import ipaddress
import os
import plistlib
import re
import time

NAME, UNAME = "macos", "Darwin"
LABEL = "dev.mdstack.runner"
TOOLS = ["launchctl"]
LISTEN = re.compile(r"^tcp[46]*\s+\d+\s+\d+\s+(\S+)\.(\d+)\s+\S+\s+LISTEN\b")


def plist_path(home):
    return os.path.join(home, "Library", "LaunchAgents", LABEL + ".plist")


def target(uid):
    return "gui/%d/%s" % (uid, LABEL)


def install(run, home, uid, python, script, root):
    """Write the agent (KeepAlive, RunAtLoad) and bootstrap it into gui/<uid>; idempotent. Returns the file written."""
    path = plist_path(home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as f:
        plistlib.dump(dict(Label=LABEL, ProgramArguments=[python, script, "--root", root, "runner"],
                           KeepAlive=True, RunAtLoad=True, WorkingDirectory=root,
                           StandardOutPath=os.path.join(root, "runner.log"),
                           StandardErrorPath=os.path.join(root, "runner.log")), f)
    os.replace(path + ".tmp", path)
    if run(["launchctl", "print", target(uid)])[0] == 0:
        run(["launchctl", "bootout", target(uid)])
    code, out = run(["launchctl", "bootstrap", "gui/%d" % uid, path])
    if code:
        raise RuntimeError("launchctl bootstrap: " + out.strip()[-200:])
    return path


def start(run, uid):
    return run(["launchctl", "kickstart", "-k", target(uid)])[0] == 0


def stop(run, uid):
    return run(["launchctl", "bootout", target(uid)])[0] == 0


def status(run, uid):
    """The service manager's state, reported beside the heartbeat: running, loaded (not running) or absent."""
    code, out = run(["launchctl", "print", target(uid)])
    if code:
        return "absent"
    return "running" if re.search(r"^\s*state = running\s*$", out, re.M) else "loaded"


def uninstall(run, home, uid):
    stop(run, uid)
    if os.path.exists(plist_path(home)):
        os.remove(plist_path(home))


def start_time(run, pid):
    """The process start in whole epoch seconds on this host's clock, or `missing`."""
    code, out = run(["env", "LC_ALL=C", "ps", "-o", "lstart=", "-p", str(pid)])
    try:
        return int(time.mktime(time.strptime(" ".join(out.split()), "%a %b %d %H:%M:%S %Y"))) if code == 0 else "missing"
    except ValueError:
        return "missing"


def listeners(run, port):
    """Local addresses with a TCP listener on port; `*` is the wildcard."""
    out = run(["netstat", "-an", "-p", "tcp"])[1]
    return sorted({m.group(1) for m in map(LISTEN.match, out.splitlines()) if m and m.group(2) == str(port)})


def private(address):
    """Not globally routable: RFC 1918, loopback, link-local and the 100.64/10 range overlays such as Tailscale use."""
    try:
        return not ipaddress.ip_address(address.split("%")[0]).is_global
    except ValueError:  # `*` and anything unparsable
        return False


def listener_row(run, port):
    """N4, read-only: warn on a wildcard or non-private listener on the SSH port; never fail, never fix."""
    found = listeners(run, port)
    bad = [a for a in found if not private(a)]
    if bad:
        return dict(status="warn", check="ssh listener", detail="port %s listens on %s" % (port, ", ".join(bad)),
                    hint="bind sshd to the overlay address only (N4)")
    return dict(status="ok", check="ssh listener", detail="port %s on %s" % (port, ", ".join(found) or "none seen"))
