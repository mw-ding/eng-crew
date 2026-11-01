"""Tests for crew drain, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: prints and empties the queue (an interrupted drain's file first) and waits for an
append holding the queue lock. Run in CI.
"""
import fcntl
import os
import subprocess
import sys
import time
import unittest
from crew_testlib import CREW, LivenessBase


class Drain(LivenessBase):
    def drain(self):
        return self.crew("drain", "--project", self.project)

    def test_drain_prints_records_and_empties_queue(self):
        self.assertEqual((self.drain().returncode, self.drain().stdout), (0, ""))  # no queue: nothing
        self.put("wake/queue.jsonl.drain-1-aa", '{"n": 0}\n')  # an interrupted drain's file comes first
        os.utime(os.path.join(self.state, "wake", "queue.jsonl.drain-1-aa"), (1, 1))
        self.put("wake/queue.jsonl", '{"n": 1}\n{"n": 2}\n')
        r = self.drain()
        self.assertEqual(r.stdout, '{"n": 0}\n{"n": 1}\n{"n": 2}\n', r.stderr)
        self.assertEqual(os.listdir(os.path.join(self.state, "wake")), ["queue.lock"])

    def test_drain_waits_for_an_append_in_progress(self):
        self.put("wake/queue.jsonl", '{"n": 1}\n')
        with open(os.path.join(self.state, "wake", "queue.lock"), "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)  # a writer holds the lock mid-append
            d = subprocess.Popen([sys.executable, CREW, "drain", "--project", self.project], stdout=subprocess.PIPE,
                                 text=True, env=self.env)
            time.sleep(0.5)
            self.assertIsNone(d.poll())
            with open(os.path.join(self.state, "wake", "queue.jsonl"), "a") as f:
                f.write('{"n": 2}\n')
        out, _ = d.communicate(timeout=10)
        self.assertEqual(out, '{"n": 1}\n{"n": 2}\n')


if __name__ == "__main__":
    unittest.main()
