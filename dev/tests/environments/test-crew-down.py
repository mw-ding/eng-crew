"""Tests for mdstack down, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: kill order and the land-lock refusal, no-op without a session, names windows holding
unlanded work, ends a real pane process that ignores SIGHUP and SIGTERM (SIGKILL) for every
window; the watcher stopped first by plain down too, even with no session left (#1346); a watcher that
exits between the PID read and the signal counts as stopped (#1757). Run in CI.
"""
import fcntl
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import CREW, Base, KillLandedBase, LivenessBase

spec = importlib.util.spec_from_loader("crew_cli", SourceFileLoader("crew_cli", CREW))
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
down = cli.commands()["down"]


def fake_watcher(tmp):
    """A detached process whose command line names `watch`, as `mdstack watch` does; returns its pid."""
    code = ("import os, sys, time\nif os.fork(): sys.exit(0)\nos.setsid()\nprint(os.getpid(), flush=True)\n"
            "null = os.open(os.devnull, os.O_RDWR)\nos.dup2(null, 1), os.dup2(null, 2)\ntime.sleep(60)\n")
    out = subprocess.run([sys.executable, "-c", code, "watch"], capture_output=True, text=True, timeout=10, cwd=tmp)
    return int(out.stdout.split()[0])


class Down(Base):
    def test_down_removes_only_coordinator_scratch_with_or_without_session(self):
        for live in (True, False):
            with self.subTest(live=live):
                with open(self.state_file, "w") as f:
                    json.dump({"crew-acme-widgets": {"0": "ash"}} if live else {}, f)
                scratch = ("coordinator.body.md", "coordinator.brief.md", "coordinator.status")
                for name in scratch + ("ben-7.body.md", "coordinator-other.body.md"):
                    self.put("runs/" + name, "scratch\n")
                r = self.crew("down", "--project", self.project)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(r.stderr, "mdstack: config %s\n" % self.project)
                self.assertEqual(r.stdout, "crew: stopped crew-acme-widgets\n" if live else
                                 "crew: crew-acme-widgets not running\n")
                for name in scratch:
                    self.assertFalse(os.path.exists(os.path.join(self.state, "runs", name)), name)
                for name in ("ben-7.body.md", "coordinator-other.body.md"):
                    self.assertTrue(os.path.isfile(os.path.join(self.state, "runs", name)), name)

    def test_down_kills_role_windows_then_session(self):
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "1": "sam", "10": "ben-7", "20": "vera-9-r1-review"}}, f)
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        kills = [c for c in self.calls() if c[0].startswith("kill-")]
        self.assertEqual(kills, [["kill-window", "-t", "=crew-acme-widgets:20"],
                                 ["kill-window", "-t", "=crew-acme-widgets:10"],
                                 ["kill-window", "-t", "=crew-acme-widgets:1"],
                                 ["kill-session", "-t", "=crew-acme-widgets"]])

    def test_down_refuses_while_land_lock_held(self):
        self.put("runs/coordinator.body.md", "scratch\n")
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "1": "sam"}}, f)
        os.makedirs(os.path.join(self.state, "locks"))
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("land lock", r.stdout)
        self.assertEqual([c for c in self.calls() if c[0].startswith("kill-")], [])
        self.assertTrue(os.path.isfile(os.path.join(self.state, "runs", "coordinator.body.md")))

    def test_down_without_session_is_noop(self):
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0)
        self.assertIn("not running", r.stdout)


class DownLanded(KillLandedBase):
    def test_down_refuses_and_names_windows_with_unlanded_work(self):
        self.put("runs/coordinator.body.md", "scratch\n")
        wt = self.builder()
        with open(os.path.join(wt, "wip.txt"), "w") as f:
            f.write("x\n")
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ben-7", r.stdout)
        self.assertIn("refusing down", r.stdout)
        self.assertTrue(os.path.isdir(wt))
        self.assertNotIn("kill-session", [c[0] for c in self.calls()])
        self.assertTrue(os.path.isfile(os.path.join(self.state, "runs", "coordinator.body.md")))


class DownPreserve(KillLandedBase):  # #1178: the maintenance stop before a migration
    def test_preserve_stops_watcher_and_panes_and_keeps_every_run(self):
        self.put("runs/coordinator.body.md", "scratch\n")
        wt = self.builder()
        with open(os.path.join(wt, "wip.txt"), "w") as f:
            f.write("x\n")
        pid = fake_watcher(self.tmp)
        self.addCleanup(lambda: subprocess.run(["kill", "-9", str(pid)], capture_output=True))
        self.put("wake/watcher.pid", "%d\n" % pid)
        r = self.crew("down", "--project", self.project, "--preserve")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        deadline = time.monotonic() + 5
        while subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip() \
                and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertEqual(subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True,
                                        text=True).stdout.strip(), "")
        self.assertIn("kill-session", [c[0] for c in self.calls()])
        self.assertTrue(os.path.isfile(os.path.join(wt, "wip.txt")))
        for rel in ("runs/ben-7.json", "claims/builder-issue7", "runs/coordinator.body.md"):
            self.assertTrue(os.path.exists(os.path.join(self.state, rel)), rel)

    def test_down_stops_the_watcher_even_with_no_session_left(self):  # #1346: a persistent watcher outlives it
        self.put("runs/coordinator.body.md", "scratch\n")
        pid = fake_watcher(self.tmp)
        self.addCleanup(lambda: subprocess.run(["kill", "-9", str(pid)], capture_output=True))
        self.put("wake/watcher.pid", "%d\n" % pid)
        with open(self.state_file, "w") as f:
            json.dump({}, f)
        r = self.crew("down", "--project", self.project)
        self.assertEqual((r.returncode, r.stdout), (0, "crew: crew-acme-widgets not running; watcher stopped\n"),
                         r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "coordinator.body.md")))
        deadline = time.monotonic() + 5
        while subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.1)

    def test_preserve_refuses_while_land_lock_held_before_stopping_anything(self):
        os.makedirs(os.path.join(self.state, "locks"), exist_ok=True)
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.crew("down", "--project", self.project, "--preserve")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("land lock", r.stdout)
        self.assertNotIn("kill-session", [c[0] for c in self.calls()])


class DownLiveness(LivenessBase):
    def test_down_escalates_to_sigkill_for_every_window(self):
        ben, ben_log = self.stubborn(signal.SIGHUP, signal.SIGTERM)
        ash, _ = self.stubborn(signal.SIGHUP)
        with open(self.panes, "w") as f:
            json.dump({"crew-acme-widgets:10": {"pid": str(ben)}, "crew-acme-widgets:0": {"pid": str(ash)}}, f)
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.alive(ben), self.alive(ash)), (False, False))
        with open(ben_log) as f:
            self.assertEqual(f.read().split(), [str(int(signal.SIGTERM))])  # TERM first, then KILL


class StopWatcherRace(unittest.TestCase):  # #1757: the watcher exits between the PID read and the signal
    def exited_pid(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait(timeout=10)
        return p.pid  # reaped: signalling it raises ProcessLookupError

    def test_a_watcher_gone_before_the_signal_counts_as_stopped(self):
        pid = self.exited_pid()
        with mock.patch.object(down, "watcher", side_effect=[pid, None, None]):
            self.assertIsNone(down.stop_watcher("/unused"))

    def test_other_signal_errors_still_raise(self):
        with mock.patch.object(down, "watcher", return_value=4242), \
                mock.patch.object(down.os, "kill", side_effect=PermissionError(1, "Operation not permitted")):
            with self.assertRaises(PermissionError):
                down.stop_watcher("/unused")


if __name__ == "__main__":
    unittest.main()
