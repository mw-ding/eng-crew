"""Session backend adapter seam tests (#1183; docs/runtimes/session-backends.md#adapter-modules), stdlib only.

A copy of this bundle gets one extra file, environments/terminal/sessions/fake/adapter.py, and nothing else. The fake
backend is then a session_backend choice the profile schema accepts, `crew doctor` looks for its CLI, and the probe,
doorbell, lock owner check, attach hint and upgrade refusal follow its declared capabilities and results. The shipped
adapters keep their order and capabilities. Run in CI.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from crew_testlib import HERE, SpawnBase

FAKE = '''"""Fake session backend adapter: test only. Windows live in memory; the pid is gone once a run exits."""
EXECUTABLE = "fake-mux"
CAPABILITIES = {"doorbell"}
WINDOWS = {}
RUNG = []


def bind(session):
    pass


def has_session(name):
    return any(n == name for n, _ in WINDOWS)


def new_window(name, index, window, cwd, env, command):
    WINDOWS[(name, index)] = window


def new_session(name, window, cwd, env, command, private_env=None):
    new_window(name, 0, window, cwd, env, command)


def pin_layout(name):
    pass


def list_windows(name):
    return sorted((i, w) for (n, i), w in WINDOWS.items() if n == name)


def has_window(name, index):
    return None  # this backend never answers a window query


def kill_window(name, index):
    WINDOWS.pop((name, index), None)


def kill_session(name):
    for key in [k for k in WINDOWS if k[0] == name]:
        WINDOWS.pop(key)


def pane(name, index):
    if (name, index) not in WINDOWS:
        return None
    return {"id": "fake-%d" % index, "pid": "", "dead": "1", "activity": "0", "tty": "fake", "command": ""}


def pane_command(name, index):
    return "dead"


def foreground(tty):
    return []


def capture(name, index):
    return ""


def cursor(name, index):
    return None


def press(name, index, *keys):
    raise AssertionError("the doorbell capability never drives keys")


def send_keys(name, index, text, settle=0.3):
    raise AssertionError("the doorbell capability never drives keys")


def doorbell(name, index, text):
    RUNG.append((name, index, text))


def attach(target, read_only=True):
    return 0


def attach_hint(session):
    return "fake-mux attach " + session


def view(name, commands):
    raise RuntimeError("fake: tiled attach unsupported")
'''
BUNDLE = None


def setUpModule():
    global BUNDLE
    BUNDLE = tempfile.mkdtemp()
    root = os.path.join(BUNDLE, "eng-crew")
    shutil.copytree(os.path.dirname(HERE), root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".crew"))
    os.makedirs(os.path.join(root, "environments", "terminal", "sessions", "fake"))
    with open(os.path.join(root, "environments", "terminal", "sessions", "fake", "adapter.py"), "w") as f:
        f.write(FAKE)


def tearDownModule():
    shutil.rmtree(BUNDLE)


def bundle(*parts):
    return os.path.join(BUNDLE, "eng-crew", "scripts", *parts)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cli():
    """The bundle copy's crew CLI, in process, with the fake backend selected."""
    spec = importlib.util.spec_from_loader("crew_fake_session_cli", SourceFileLoader("crew_fake_session_cli",
                                                                                     bundle("crew")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.tmux.name = "fake"
    return mod


class ShippedBackends(unittest.TestCase):
    def test_order_and_capabilities(self):
        s = load("crew_session_shipped", os.path.join(HERE, "crew-session.py"))
        self.assertEqual(s.CHOICES, ["tmux", "herdr"])
        self.assertEqual({n: (a.EXECUTABLE, a.CAPABILITIES) for n, a in s.ADAPTERS.items()},
                         {"tmux": ("tmux", {"reload", "dead-keeps-pid"}), "herdr": ("herdr", {"doorbell"})})


class FakeBackend(SpawnBase):
    """The fake adapter, added as one file, through the schema, doctor and every capability branch."""

    def crew(self, *args, stdin="", **env):
        return subprocess.run([sys.executable, bundle("crew"), *args], input=stdin, capture_output=True, text=True,
                              env=dict(self.env, **env))

    def select_fake(self):
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\nsession_backend = "fake"\n')

    def test_schema_choice_doctor_and_upgrade_refusal(self):
        self.assertEqual(load("crew_session_fake", bundle("crew-session.py")).CHOICES, ["tmux", "herdr", "fake"])
        self.select_fake()
        binary = os.path.join(self.tmp, "bin", "fake-mux")
        with open(binary, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(binary, 0o755)
        r = self.crew("doctor", "--project", self.project)
        self.assertIn(binary, r.stdout)
        r = self.crew("upgrade", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("fake: in-place upgrade unsupported", r.stdout)

    def test_probe_doorbell_lock_owner_and_attach_hint(self):
        crew = cli()
        fake = crew.tmux.backends["fake"]
        fake.WINDOWS[("s", 10)] = "ben-7"
        rec = {"index": 10, "pane_id": "fake-10", "pane_pid": "123", "pane_start": "t", "harness": "claude"}
        self.assertEqual(crew.probe("s", "ben-7", rec, {"ben-7": 10}), "dead")  # no dead-keeps-pid
        self.assertEqual(crew.probe("s", "ben-7", dict(rec, pane_id="other"), {"ben-7": 10}), "missing")
        self.assertIsNone(crew.commands()["send"].nudge("s", 10, "wake: watcher"))
        self.assertEqual(fake.RUNG, [("s", 10, "wake: watcher")])
        lock = crew.commands()["land-lock"]
        start = subprocess.run(["ps", "-o", "lstart=", "-p", str(os.getpid())], capture_output=True,
                               text=True).stdout.strip()
        owner = {"pid": os.getpid(), "start": start, "pane_id": "fake-3", "session": "s", "index": 3}
        self.assertTrue(lock.owner_alive(owner))  # no pane and no window answer: never proof of death
        self.assertEqual(crew.commands()["up"].attach_hint("s"), "fake-mux attach s")


if __name__ == "__main__":
    unittest.main()
