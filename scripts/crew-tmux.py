"""tmux adapter for scripts/crew: every tmux call goes through here, so tests can put a fake `tmux` on PATH."""
import subprocess
import os
import shutil
import time


def tmux(*args):
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def has_session(name):
    return tmux("has-session", "-t", "=" + name).returncode == 0


def new_session(name, window, cwd, env, command):
    """Detached session whose first window runs command; env holds names and logins only, never tokens."""
    flags = [x for k, v in env.items() for x in ("-e", "%s=%s" % (k, v))]
    r = tmux("new-session", "-d", "-s", name, "-n", window, "-c", cwd, *flags, command)
    if r.returncode:
        raise RuntimeError("tmux new-session failed: " + r.stderr.strip())
    pin_layout(name)
    tmux("move-window", "-s", "=" + name, "-t", "=%s:0" % name)  # window 0 even with a user base-index


def pin_layout(name):
    """Keep the index bands stable against a user renumber-windows / base-index: this session only, never -g."""
    for option, value in [("renumber-windows", "off"), ("base-index", "0")]:
        tmux("set-option", "-t", "=%s:" % name, option, value)  # set-option -t is a pane target


def list_windows(name):
    out = tmux("list-windows", "-t", "=" + name, "-F", "#{window_index} #{window_name}").stdout
    return [(int(i), n) for i, _, n in (line.partition(" ") for line in out.splitlines())]


def kill_window(name, index):
    tmux("kill-window", "-t", "=%s:%d" % (name, index))


def kill_session(name):
    tmux("kill-session", "-t", "=" + name)


def new_window(name, index, window, cwd, env, command):
    """Background window (focus stays on the coordinator); env holds names, paths and logins only, never tokens."""
    flags = [x for k, v in env.items() for x in ("-e", "%s=%s" % (k, v))]
    r = tmux("new-window", "-d", "-t", "=%s:%d" % (name, index), "-n", window, "-c", cwd, *flags, command)
    if r.returncode:
        raise RuntimeError("tmux new-window failed: " + r.stderr.strip())


def pane_command(name, index):
    """The pane's foreground command, or `dead` for a dead pane, whose command would read as the launch's first word."""
    return tmux("display-message", "-p", "-t", "=%s:%d" % (name, index),
                "#{?pane_dead,dead,#{pane_current_command}}").stdout.strip()


def capture(name, index):
    """The pane's visible screen, for the trust-dialog check (tmux.md Q7)."""
    return tmux("capture-pane", "-p", "-t", "=%s:%d" % (name, index)).stdout


def cursor(name, index):
    """The pane's cursor as (column, row) on its visible screen, for the nudge's composer check (#308); None when
    tmux cannot answer."""
    out = tmux("display-message", "-p", "-t", "=%s:%d" % (name, index), "#{cursor_x} #{cursor_y}").stdout.split()
    return (int(out[0]), int(out[1])) if len(out) == 2 and all(p.isdigit() for p in out) else None


def press(name, index, *keys):
    """Named keys (Enter, C-u), which tmux interprets; text goes through send_keys."""
    tmux("send-keys", "-t", "=%s:%d" % (name, index), *keys)


def send_keys(name, index, text, settle=0.3):
    """Type a fixed nudge line literally (-l, so no key names are interpreted), then Enter after settle seconds: an
    Enter right behind the typed text lands in Codex's paste burst and adds a newline instead of submitting (#308)."""
    tmux("send-keys", "-t", "=%s:%d" % (name, index), "-l", text)
    time.sleep(settle)
    press(name, index, "Enter")


def attach(target, read_only=True):
    """Attach the caller's terminal (no capture); -r makes the client read-only, it can still detach."""
    return subprocess.run(["tmux", "attach-session", *(["-r"] if read_only else []), "-t", target]).returncode


def view(name, commands):
    """Temporary detached session, one tiled pane per command; a session of its own, so no crew window moves."""
    r = tmux("new-session", "-d", "-s", name, "-n", "view", commands[0])
    if r.returncode:
        raise RuntimeError("tmux new-session failed: " + r.stderr.strip())
    for command in commands[1:]:
        tmux("split-window", "-t", "=%s:" % name, command)
        tmux("select-layout", "-t", "=%s:" % name, "tiled")


def pane(name, index):
    """Pane identity and state for the liveness probe (tmux.md Q7); None when tmux cannot answer."""
    r = tmux("display-message", "-p", "-t", "=%s:%d" % (name, index),
             "#{pane_id} #{pane_pid} #{pane_dead} #{window_activity} #{pane_tty} #{pane_current_command}")
    parts = r.stdout.strip().split(None, 5)
    if r.returncode or len(parts) < 5:
        return None
    return dict(zip(["id", "pid", "dead", "activity", "tty", "command"], parts + [""]))


def proc_start(pid):
    """Start time of a process, so a reused pid never passes for the recorded run; empty when it is gone."""
    return subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()


def live_child(pid, harness):
    """A live tool session beneath the pane; persistent helpers in the harness session do not count."""
    wrappers = {harness, harness + ".real", os.path.basename(os.path.realpath(shutil.which(harness) or harness))}
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,stat=,comm="], capture_output=True, text=True).stdout
    processes = [line.split(None, 3) for line in out.splitlines() if len(line.split(None, 3)) == 4]
    parents = {str(pid)}
    while parents:
        next_ = set()
        for child, parent, stat, command in processes:
            if parent in parents and not stat.startswith("Z"):
                if "s" in stat and os.path.basename(command) not in wrappers:
                    return True
                next_.add(child)
        parents = next_
    return False


def foreground(tty):
    """Names of the processes in the tty's foreground process group (ps stat has '+')."""
    out = subprocess.run(["ps", "-o", "stat=", "-o", "comm=", "-t", tty], capture_output=True, text=True).stdout
    return [c.strip().rsplit("/", 1)[-1] for s, _, c in (line.strip().partition(" ") for line in out.splitlines())
            if "+" in s]
