"""Linux host OS adapter (docs/runtimes/multi-device.md#host-os-adapters): the runner as a systemd user unit with
Restart=always and lingering, procfs start times and the SSH listener read from ss.

A host without systemd (a lab container) is supervised only when its image says so: a root-owned SUPERVISED file
naming the PID-1 supervisor. Then the adapter writes no unit, refuses start and stop, and reports `supervised`; a
host with neither systemd nor that file reports its missing user manager instead of falling back.
crew-remote.py loads it by path when `hosts.<name>.capabilities.os` is `linux` and the host's uname is Linux.
Every call takes the commands it runs through `run(argv) -> (exit, output)`, so tests pass a fake.
"""
import ipaddress
import os
import time

NAME, UNAME = "linux", "Linux"
UNIT = "mdstack-runner.service"
SUPERVISED = "/etc/mdstack/supervised"  # written by the lab image (environments/terminal/remote/lab/Dockerfile)
STATES = {"active", "inactive", "failed", "activating", "deactivating", "reloading"}


def supervisor():
    """The supervisor the image names, or None on a systemd host."""
    try:
        with open(SUPERVISED) as f:
            return f.read().strip() or "unnamed"
    except OSError:
        return None


TOOLS = [] if supervisor() else ["systemctl", "loginctl"]


def unit_path(home):
    return os.path.join(home, ".config", "systemd", "user", UNIT)


def quote(arg):
    return '"%s"' % arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")


def install(run, home, uid, python, script, root):
    """Write the unit (Restart=always), enable and start it, and ask for lingering; idempotent. Returns the file
    written, or `n/a: supervised`. A refused linger is left to status's warn."""
    if supervisor():
        return "n/a: supervised"
    path = unit_path(home)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        f.write("[Unit]\nDescription=mdstack runner\n\n[Service]\nExecStart=%s\nWorkingDirectory=%s\n"
                "Restart=always\nRestartSec=5\n\n[Install]\nWantedBy=default.target\n"
                % (" ".join(map(quote, [python, script, "--root", root, "runner"])), quote(root)))
    os.replace(path + ".tmp", path)
    for argv in (["systemctl", "--user", "daemon-reload"], ["systemctl", "--user", "enable", "--now", UNIT]):
        code, out = run(argv)
        if code:
            raise RuntimeError(" ".join(argv[:3]) + ": " + out.strip()[-200:])
    run(["loginctl", "enable-linger", str(uid)])
    return path


def start(run, uid):
    return False if supervisor() else run(["systemctl", "--user", "start", UNIT])[0] == 0


def stop(run, uid):
    return False if supervisor() else run(["systemctl", "--user", "stop", UNIT])[0] == 0


def status(run, uid):
    """The service manager's state, reported beside the heartbeat: supervised, a systemd unit state, or
    `no user manager` when systemctl --user cannot reach one."""
    if supervisor():
        return "supervised"
    out = run(["systemctl", "--user", "is-active", UNIT])[1].strip()
    return out if out in STATES else "no user manager"


def linger(run, uid):
    return run(["loginctl", "show-user", str(uid), "--property=Linger", "--value"])[1].strip() == "yes"


def service_rows(run, uid):
    """Lingering keeps the user unit up after logout; a supervised host has no session to outlive."""
    if supervisor():
        return []
    if linger(run, uid):
        return [dict(status="ok", check="linger", detail="Linger=yes")]
    return [dict(status="warn", check="linger", detail="Linger is off: the runner stops at logout",
                 hint="loginctl enable-linger <runner account>")]


def uninstall(run, home, uid):
    if supervisor():
        return
    run(["systemctl", "--user", "disable", "--now", UNIT])
    if os.path.exists(unit_path(home)):
        os.remove(unit_path(home))


def start_time(run, pid, proc="/proc"):
    """The process start in whole epoch seconds on this host's clock: procfs start ticks plus boot time, else
    `ps -o lstart=`, else `missing`."""
    try:
        with open(os.path.join(proc, str(pid), "stat")) as f:
            ticks = int(f.read().rsplit(")", 1)[1].split()[19])
        with open(os.path.join(proc, "stat")) as f:
            boot = next(int(line.split()[1]) for line in f if line.startswith("btime "))
        return boot + ticks // os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, StopIteration):
        pass
    code, out = run(["env", "LC_ALL=C", "ps", "-o", "lstart=", "-p", str(pid)])
    try:
        return int(time.mktime(time.strptime(" ".join(out.split()), "%a %b %d %H:%M:%S %Y"))) if code == 0 else "missing"
    except ValueError:
        return "missing"


def listeners(run, port):
    """Local addresses with a TCP listener on port; `*` is the wildcard (0.0.0.0, :: or *)."""
    found = set()
    for line in run(["ss", "-Hltn"])[1].splitlines():
        fields = line.split()
        if len(fields) < 4 or ":" not in fields[3]:
            continue
        address, _, listen_port = fields[3].rpartition(":")
        address = address.strip("[]").split("%")[0]
        if listen_port == str(port):
            found.add("*" if address in ("*", "0.0.0.0", "::") else address)
    return sorted(found)


def private(address):
    """Not globally routable: RFC 1918, loopback, link-local and the 100.64/10 range overlays such as Tailscale use."""
    try:
        return not ipaddress.ip_address(address).is_global
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
