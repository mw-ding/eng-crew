"""Tests for crew dequeue (and the spawn band cap queue), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers the band caps: spawn beyond the cap queues, `dequeue` spawns the oldest request with a free slot after a
kill, bands capped separately. Run in CI.
"""
import json
import os
import sys
import unittest
from crew_testlib import SpawnBase

TRANSCRIPT = "--transcript" in sys.argv


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
        self.assertEqual(len(self.windows()), 3)
        self.assertEqual(self.record("ben-9")["index"], 10)
        self.assertEqual(self.queue(), [])

    def test_idle_builders_do_not_count_toward_busy_cap(self):
        self.spawn("builder", "--issue", "7")
        self.spawn("builder", "--issue", "8")
        self.put("status/ben-7.status", "done: #7 #12 " + "a" * 40 + "\n")
        result = self.spawn("builder", "--issue", "9")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("started ben-9", result.stdout)
        self.assertTrue(os.path.exists(self.record("ben-7")["worktree"]))
        self.assertIn("queued:", self.spawn("builder", "--issue", "10").stdout)

    def test_physical_band_pressure_reclaims_oldest_idle_builder(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace("builders = 2", "builders = 10"))
        for issue in range(7, 17):
            self.assertEqual(self.spawn("builder", "--issue", str(issue)).returncode, 0)
        self.assertIn("queued:", self.spawn("builder", "--issue", "17").stdout)
        oldest = self.record("ben-8")["worktree"]
        for issue in (7, 8):
            self.put("status/ben-%d.status" % issue, "done: #%d #12 %s\n" % (issue, "a" * 40))
            stamp = 200 if issue == 7 else 100
            os.utime(os.path.join(self.state, "status", "ben-%d.status" % issue), (stamp, stamp))
        self.put("render/runtime/builder-lead.md", "Manage the builder pool.\n")
        deferred = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(deferred.returncode, 0, deferred.stdout + deferred.stderr)
        self.assertTrue(os.path.exists(oldest))
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-17.json")))
        os.unlink(os.path.join(self.state, "render", "runtime", "builder-lead.md"))
        result = self.crew("route", "--project", self.project, "--timeout", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reclaimed idle builder ben-8", result.stdout)
        self.assertFalse(os.path.exists(oldest))
        self.assertEqual(self.record("ben-17")["index"], 11)
        self.assertTrue(os.path.exists(self.record("ben-7")["worktree"]))
        self.assertEqual(self.queue(), [])
        retained = self.record("ben-7")["worktree"]
        with open(os.path.join(retained, "unpushed.txt"), "w") as f:
            f.write("retain this work\n")
        self.assertIn("queued:", self.spawn("builder", "--issue", "18").stdout)
        self.crew("route", "--project", self.project, "--timeout", "1")
        self.assertEqual(self.record("ben-7")["worktree"], retained)
        self.assertTrue(os.path.exists(os.path.join(retained, "unpushed.txt")))
        self.assertEqual([e["issue"] for e in self.queue()], [18])
        if TRANSCRIPT:
            print("create: 10 builders; queue issue #17; ben-8 is longest idle")
            print("dequeue: pushed ben-8 reclaimed, output retained; ben-17 started at index 11")
            print("after reclaim: ben-8 worktree absent; busy workers retained")
            print("unpushed ben-7 retained; issue #18 stays queued")

    def test_idle_expiry_retains_output_without_queue_and_can_be_disabled(self):
        self.spawn("builder", "--issue", "7")
        rec = self.record("ben-7")
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % ("a" * 40))
        status = os.path.join(self.state, "status", "ben-7.status")
        os.utime(status, (100, 100))
        with open(self.project, "r") as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace("builders = 2", "builders = 2, idle_builder_ttl = 0"))
        result = self.crew("dequeue", "--idle-only", "--project", self.project)
        self.assertTrue(os.path.exists(rec["worktree"]))
        with open(self.project, "w") as f:
            f.write(text.replace("builders = 2", "builders = 2, idle_builder_ttl = 30"))
        summaries = os.path.join(rec["worktree"], ".crew", "runs", "issue-7", "build")
        os.makedirs(summaries)
        with open(os.path.join(summaries, "summary.md"), "w") as f:
            f.write("build: ok\n")
        result = self.crew("dequeue", "--idle-only", "--project", self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reclaimed idle builder ben-7", result.stdout)
        self.assertFalse(os.path.exists(rec["worktree"]))
        retained = os.path.join(self.state, "retained", "builders", "ben-7-100")
        self.assertTrue(os.path.exists(os.path.join(retained, "output.txt")))
        with open(os.path.join(retained, "summaries", "issue-7", "build", "summary.md")) as f:
            self.assertEqual(f.read(), "build: ok\n")
        self.assertTrue(os.path.exists(os.path.join(retained, "status.txt")))
        if TRANSCRIPT:
            print("idle-only: ttl=0 retains builder; ttl=30 reclaims without queued work")
            print("after expiry: builder worktree absent; status, output and build summary retained")

    def test_unacknowledged_message_keeps_done_builder_busy(self):
        self.spawn("builder", "--issue", "7")
        self.spawn("builder", "--issue", "8")
        self.put("status/ben-7.status", "done: #7 #12 " + "a" * 40 + "\n")
        self.put("inbox/ben-7.jsonl", json.dumps(dict(id="pending", kind="fix", refs=["#12"])) + "\n")
        self.assertIn("queued:", self.spawn("builder", "--issue", "9").stdout)

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
        self.assertEqual(self.record("vera-4-r1-review")["index"], 20)
        self.assertEqual([e["issue"] for e in self.queue()], [9])

    def test_kill_dequeues_only_the_freed_band(self):
        for issue in ("7", "8", "9"):
            self.assertEqual(self.spawn("builder", "--issue", issue).returncode, 0)
        for pr in (5, 6, 4):
            self.pr(pr, "claude-code opus-5.5 default")
            self.assertEqual(self.spawn("reviewer", "--pr", str(pr)).returncode, 0)
        # Another band becomes free without crew kill; killing a reviewer
        # must not spend its automatic dequeue on the older builder request.
        with open(self.state_file) as f:
            state = json.load(f)
        del state["crew-acme-widgets"]["10"]
        with open(self.state_file, "w") as f:
            json.dump(state, f)
        self.assertEqual(self.crew("kill", "vera-5-r1-review", "--project", self.project).returncode, 0)
        self.assertEqual(self.record("vera-4-r1-review")["index"], 20)
        self.assertEqual([e["issue"] for e in self.queue()], [9])
        result = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.record("ben-9")["index"], 10)
        self.assertEqual(self.queue(), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "CapQueue.test_physical_band_pressure_reclaims_oldest_idle_builder",
                       "CapQueue.test_idle_expiry_retains_output_without_queue_and_can_be_disabled"] if TRANSCRIPT else None)
