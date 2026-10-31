"""Tests for crew land-lock, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import fcntl
import json
import os
import subprocess
import unittest
from crew_testlib import Base


class LandLock(Base):
    """crew land-lock (#136): serial land under flock on locks/merge.lock."""

    def lock(self, action):
        return self.crew("land-lock", action, "--project", self.project)

    def test_second_acquire_fails_fast_and_down_refuses_until_release(self):
        self.addCleanup(self.lock, "release")
        r = self.lock("acquire")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("acquired", r.stdout)
        r = self.lock("acquire")
        self.assertEqual(r.returncode, 1)
        self.assertIn("is held", r.stdout)
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "1": "sam"}}, f)
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("land lock", r.stdout)
        r = self.lock("release")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.state, "locks", "merge.pid")))
        self.assertEqual(self.lock("acquire").returncode, 0)
        self.assertEqual(self.lock("release").returncode, 0)
        self.assertEqual(self.crew("down", "--project", self.project).returncode, 0)

    def test_acquire_fails_fast_against_another_holder(self):
        os.makedirs(os.path.join(self.state, "locks"))
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.lock("acquire")
            self.assertEqual(r.returncode, 1)
            r = self.lock("release")
            self.assertEqual(r.returncode, 1)
            self.assertIn("nothing signalled", r.stdout)
        self.assertEqual(self.lock("release").returncode, 0)

    def pidfile(self, rec=None):
        path = os.path.join(self.state, "locks", "merge.pid")
        if rec is not None:
            with open(path, "w") as f:
                json.dump(rec, f)
        with open(path) as f:
            return json.load(f)

    def test_matching_holder_released_and_recorded_with_start_time(self):
        self.assertEqual(self.lock("acquire").returncode, 0)
        rec = self.pidfile()
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(rec["pid"])], capture_output=True, text=True).stdout
        self.assertEqual(rec["start"], out.strip())
        r = self.lock("release")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("released", r.stdout)

    def test_stale_pid_file_with_other_holder_signals_nothing(self):
        bystander = subprocess.Popen(["sleep", "30"])
        self.addCleanup(bystander.wait)
        self.addCleanup(bystander.kill)
        start = subprocess.run(["ps", "-o", "lstart=", "-p", str(bystander.pid)], capture_output=True,
                               text=True).stdout.strip()
        os.makedirs(os.path.join(self.state, "locks"))
        self.pidfile({"pid": bystander.pid, "start": start})  # live PID, matching start, but not a lock holder
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.lock("release")
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing signalled", r.stdout)
        self.assertIsNone(bystander.poll())

    def test_reused_pid_with_other_start_time_signals_nothing(self):
        self.addCleanup(self.lock, "release")
        self.assertEqual(self.lock("acquire").returncode, 0)
        rec = self.pidfile()
        self.pidfile(dict(rec, start="Thu Jan  1 00:00:00 1970"))
        r = self.lock("release")
        self.assertEqual(r.returncode, 1)
        self.assertIn("nothing signalled", r.stdout)
        os.kill(rec["pid"], 0)  # holder still alive
        self.assertEqual(self.lock("acquire").returncode, 1)
        self.pidfile(rec)
        self.assertEqual(self.lock("release").returncode, 0)


if __name__ == "__main__":
    unittest.main()
