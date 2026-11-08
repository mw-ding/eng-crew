"""Local herdr session adapter for cli/mdstack (docs/runtimes/session-backends.md).

Uses only workspace/pane CLI operations over the existing local socket; no hooks or agent-reported state.
Each run owns one background workspace, labelled <crew-session>:<index>:<window>. OS process helpers are shared
in crew-proc.py. Private coordinator environment, tiled attach and in-place upgrade are unsupported.
"""
import json
import re
import shlex
import subprocess
import time

EXECUTABLE = "herdr"
RANK = 1
CAPABILITIES = {"doorbell"}  # no cursor coordinates: it rings with its own screen-only doorbell


def bind(session, tmux_server="default"):
    pass  # The local default server; nothing is bound per session.


def call(*args):
    r = subprocess.run(["herdr", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("herdr %s failed: %s" % (args[0], r.stderr.strip()))
    return json.loads(r.stdout)["result"] if r.stdout.strip() else {}


def workspaces(name):
    return [w for w in call("workspace", "list")["workspaces"] if w["label"].startswith(name + ":")]


def workspace(name, index):
    return next((w for w in workspaces(name) if w["label"].split(":", 2)[1] == str(index)), None)


def list_windows(name):
    return [(int(w["label"].split(":", 2)[1]), w["label"].split(":", 2)[2]) for w in workspaces(name)]


def has_window(name, index):
    """Whether a run workspace holds index; None when herdr cannot answer."""
    try:
        return index in dict(list_windows(name))
    except RuntimeError:
        return None


def has_session(name):
    return bool(workspaces(name))


def pin_layout(name):
    pass  # Runtime bands live in labels; herdr workspace numbers never determine run identity.


def pane_id(name, index):
    w = workspace(name, index)
    if w is None:
        raise RuntimeError("herdr: workspace missing")
    panes = call("pane", "list", "--workspace", w["workspace_id"])["panes"]
    if len(panes) != 1:
        raise RuntimeError("herdr: run workspace must contain exactly one pane")
    return panes[0]["pane_id"]


def new_window(name, index, window, cwd, env, command):
    if workspace(name, index):
        raise RuntimeError("herdr: run index occupied")
    flags = [a for k, v in env.items() for a in ("--env", "%s=%s" % (k, v))]
    call("workspace", "create", "--cwd", cwd, "--label", "%s:%d:%s" % (name, index, window),
         "--no-focus", *flags)
    try:
        call("pane", "run", pane_id(name, index), "exec " + command)
    except (RuntimeError, ValueError):
        kill_window(name, index)
        raise


def new_session(name, window, cwd, env, command, private_env=None):
    if private_env:
        raise RuntimeError("herdr: private coordinator environment unsupported")
    new_window(name, 0, window, cwd, env, command)


def pane(name, index):
    try:
        handle = pane_id(name, index)
        p = call("pane", "get", handle)["pane"]
        info = call("pane", "process-info", "--pane", handle)["process_info"]
        pid = info["shell_pid"]
        return {"id": p["terminal_id"], "pid": str(pid) if pid else "", "dead": "0" if pid else "1",
                "activity": "0", "tty": handle, "command": next(iter(foreground(handle)), "")}
    except (RuntimeError, ValueError, KeyError):
        return None


def foreground(handle):
    info = call("pane", "process-info", "--pane", handle)["process_info"]
    return [p["name"] for p in info.get("foreground_processes", [])]


def pane_command(name, index):
    p = pane(name, index)
    return "dead" if p and p["dead"] == "1" else p["command"] if p else ""


def capture(name, index):
    r = subprocess.run(["herdr", "pane", "read", pane_id(name, index), "--source", "visible", "--format", "text"],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("herdr pane read failed: " + r.stderr.strip())
    return r.stdout


def cursor(name, index):
    return None  # The CLI exposes screen text, but no cursor coordinates.


def press(name, index, *keys):
    call("pane", "send-keys", pane_id(name, index), *[{"Enter": "enter", "C-u": "ctrl+u"}[k] for k in keys])


def send_keys(name, index, text, settle=0.3):
    call("pane", "send-text", pane_id(name, index), text)
    time.sleep(settle)
    press(name, index, "Enter")


def doorbell(name, index, text):
    if not re.fullmatch(r"inbox: \d{8}T\d{6}Z-[0-9a-f]{6}|wake: watcher", text):
        return "fixed doorbell lines only; nothing typed"
    if not re.search(r"(?m)^[›❯]\s*$", capture(name, index)):
        return "no empty composer visible; nothing typed"
    send_keys(name, index, text)
    time.sleep(0.5)
    screen = capture(name, index)
    if re.search(r"(?m)^[›❯]\s*$", screen) and not re.search(r"(?m)^[›❯]\s*" + re.escape(text), screen):
        return None
    return "doorbell submission ambiguous; text not retyped"


def kill_window(name, index):
    from crew_shared import stop_pane
    w = workspace(name, index)
    if w:
        if pane(name, index) is None:
            raise RuntimeError("herdr: process probe unavailable; workspace retained")
        if stop_pane(name, index):
            raise RuntimeError("herdr: process group survived; workspace retained")
        if any(current["workspace_id"] == w["workspace_id"] for current in workspaces(name)):
            call("workspace", "close", w["workspace_id"])


def kill_session(name):
    for index, _ in list_windows(name):
        kill_window(name, index)


def attach(target, read_only=True):
    name, index = target.lstrip("=").rsplit(":", 1)
    if read_only:
        try:
            while True:
                print("\033[H\033[2J" + capture(name, int(index)), end="", flush=True)
                time.sleep(1)
        except KeyboardInterrupt:
            return 0
    call("workspace", "focus", workspace(name, int(index))["workspace_id"])
    return subprocess.run(["herdr"]).returncode


def attach_hint(session):
    return shlex.join(["tmux", "attach", "-t", session])


def view(name, commands):
    raise RuntimeError("herdr: tiled builders attach unsupported; attach one run")


def tmux(*args):
    raise RuntimeError("herdr: tmux-specific operation unsupported")
