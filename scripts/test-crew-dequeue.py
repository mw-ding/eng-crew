"""Tests for crew dequeue (and the spawn band cap queue), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers the band caps: spawn beyond the cap queues, `dequeue` spawns the oldest request with a free slot after a
kill, bands capped separately. Run in CI.
"""
import json
import os
import unittest
from crew_testlib import SpawnBase


class CapQueue(SpawnBase):
    """Per-band caps (#136): beyond the profile cap, crew spawn queues; crew dequeue spawns when a slot frees."""

    def setUp(self):
        super().setUp()
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"\n', 'name = "tmux"\noptions = { builders = 2 }\n'))

    def queue(self):
        path = os.path.join(self.state, "spawn-queue.jsonl")
        with open(path) as f:
            return [json.loads(line) for line in f]

    def test_cap_reached_queues_and_dequeue_spawns_after_kill(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        r = self.spawn("builder", "--issue", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("queued: builder build issue #9"), r.stdout)
        self.assertEqual(len(self.windows()), 2)
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue9")))
        q = self.queue()
        self.assertEqual([(e["role"], e["issue"], e["pass"]) for e in q], [("builder", 9, "build")])
        r = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertIn("no free slot", r.stdout)
        self.assertEqual(self.queue(), q)
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)
        r = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("started ben-9 (window 10", r.stdout)
        self.assertEqual(self.queue(), [])

    def test_bands_capped_separately_and_dequeue_skips_full_band(self):
        self.pr(5, "claude-code opus-5.5 default")
        self.pr(6, "claude-code opus-5.5 default")
        self.pr(4, "claude-code opus-5.5 default")
        for issue in ["7", "8", "9"]:
            self.spawn("builder", "--issue", issue)
        for pr in ["5", "6", "4"]:
            self.spawn("reviewer", "--pr", pr)
        self.assertEqual([(e["role"], e["issue"] or e["pr"]) for e in self.queue()], [("builder", 9), ("reviewer", 4)])
        self.assertEqual(self.crew("kill", "vera-5-r1-review", "--project", self.project).returncode, 0)
        r = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertIn("started vera-4-r1-review (window 20", r.stdout)
        self.assertEqual([e["issue"] for e in self.queue()], [9])


if __name__ == "__main__":
    unittest.main()
