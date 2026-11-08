"""Session backend adapter discovery (docs/runtimes/session-backends.md#adapter-modules). Python 3.11+ stdlib only.

Each sessions/<name>/adapter.py is one session backend's adapter module, named by its
runtime.options.session_backend value; _-prefixed directories are not adapters. This module loads them once in sorted
directory order, so adding a backend adds its adapter module and tests only. Each adapter declares:

- EXECUTABLE: the CLI `mdstack doctor` looks for on PATH;
- RANK: its place in the session_backend choices (an adapter with no rank sorts after the ranked ones, by name);
- CAPABILITIES: the optional behaviours consumers branch on, never on the backend's name:
  - doorbell: doorbell(name, index, text) rings a run itself (no cursor to drive the core's composer nudge);
  - reload: hold(name, index) and respawn(name, index, cwd, env, command) restart a run in place (mdstack upgrade);
  - dead-keeps-pid: an exited object still reports its pid, so a dead probe compares the pid too.

Every adapter provides the same operations: bind, has_session, new_session, new_window, pin_layout, list_windows,
has_window, kill_window, kill_session, pane, pane_command, foreground, capture, cursor, press, send_keys, attach,
attach_hint and view. OS process helpers live in crew-proc.py."""
import glob
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))  # environments/terminal/


def discover(directory):
    """The adapter modules in directory by backend name, <name>/adapter.py, loaded in sorted name order."""
    paths = {os.path.basename(os.path.dirname(p)): p for p in glob.glob(os.path.join(directory, "[!_]*", "adapter.py"))}
    found = {}
    for name, path in sorted(paths.items()):
        spec = importlib.util.spec_from_file_location("crew_session_" + name.replace("-", "_"), path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        found[name] = mod
    return found


ADAPTERS = discover(os.path.join(HERE, "sessions"))
CHOICES = sorted(ADAPTERS, key=lambda n: (getattr(ADAPTERS[n], "RANK", None) is None,
                                         getattr(ADAPTERS[n], "RANK", 0), n))  # session_backend choices
