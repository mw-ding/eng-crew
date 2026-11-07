"""Tests for mdstack down, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: kill order and the land-lock refusal, no-op without a session, names windows holding
unlanded work, ends a real pane process that ignores SIGHUP and SIGTERM (SIGKILL) for every
window. Run in CI.
"""
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, KillLandedBase, LivenessBase


def fake_watcher(tmp):
    """A detached process whose command line names `watch`, as `mdstack watch` does; returns its pid."""
    code = ("import os, sys, time\nif os.fork(): sys.exit(0)\nos.setsid()\nprint(os.getpid(), flush=True)\n"
            "null = os.open(os.devnull, os.O_RDWR)\nos.dup2(null, 1), os.dup2(null, 2)\ntime.sleep(60)\n")
    out = subprocess.run([sys.executable, "-c", code, "watch"], capture_output=True, text=True, timeout=10, cwd=tmp)
    return int(out.stdout.split()[0])


class Down(Base):
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
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "1": "sam"}}, f)
        os.makedirs(os.path.join(self.state, "locks"))
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("land lock", r.stdout)
        self.assertEqual([c for c in self.calls() if c[0].startswith("kill-")], [])

    def test_down_without_session_is_noop(self):
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0)
        self.assertIn("not running", r.stdout)


class DownLanded(KillLandedBase):
    def test_down_refuses_and_names_windows_with_unlanded_work(self):
        wt = self.builder()
        with open(os.path.join(wt, "wip.txt"), "w") as f:
            f.write("x\n")
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ben-7", r.stdout)
        self.assertIn("refusing down", r.stdout)
        self.assertTrue(os.path.isdir(wt))
        self.assertNotIn("kill-session", [c[0] for c in self.calls()])


class DownPreserve(KillLandedBase):  # #1178: the maintenance stop before a migration
    def test_preserve_stops_watcher_and_panes_and_keeps_every_run(self):
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
        for rel in ("runs/ben-7.json", "claims/builder-issue7"):
            self.assertTrue(os.path.exists(os.path.join(self.state, rel)), rel)

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


if __name__ == "__main__":
    unittest.main()
