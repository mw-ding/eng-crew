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
    tmux("move-window", "-s", "=" + name, "-t", "=%s:0" % name)  # window 0 even with a user base-index


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
