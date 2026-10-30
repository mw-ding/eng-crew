"""tmux adapter for scripts/crew: every tmux call goes through here, so tests can put a fake `tmux` on PATH."""
import subprocess


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
    return tmux("display-message", "-p", "-t", "=%s:%d" % (name, index), "#{pane_current_command}").stdout.strip()


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


def foreground(tty):
    """Names of the processes in the tty's foreground process group (ps stat has '+')."""
    out = subprocess.run(["ps", "-o", "stat=", "-o", "comm=", "-t", tty], capture_output=True, text=True).stdout
    return [c.strip().rsplit("/", 1)[-1] for s, _, c in (line.strip().partition(" ") for line in out.splitlines())
            if "+" in s]
