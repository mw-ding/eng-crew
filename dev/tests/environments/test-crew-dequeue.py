"""Tests for mdstack dequeue (and the spawn band cap queue), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers the band caps: spawn beyond the cap queues, `dequeue` spawns the oldest request with a free slot after a
kill, bands capped separately. Run in CI.
"""
import json
import os
import sys
import time
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import SpawnBase

TRANSCRIPT = "--transcript" in sys.argv


class CapQueue(SpawnBase):
    """Per-band caps (#136): beyond the profile cap, mdstack spawn queues; mdstack dequeue spawns when a slot frees."""

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

    def test_queued_request_keeps_the_item_tier_resolved_at_enqueue(self):  # #1830
        record = "<!-- crew:v1 role=coordinator pass=flavor issue=9 flavor=standard default=standard tier=%s -->\n— 🔥 Ash (CTO) · x"
        self.env["FAKE_COMMENTS_9"] = json.dumps([{"author": {"login": "acme-bot"}, "body": record % "deep"}])
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        self.assertTrue(self.spawn("builder", "--issue", "9").stdout.startswith("queued: builder build issue #9"))
        self.assertEqual([e["tier"] for e in self.queue()], ["deep"])
        self.env["FAKE_COMMENTS_9"] = json.dumps([{"author": {"login": "acme-bot"}, "body": record % "trivial"}])
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)  # dequeues ben-9
        rec = self.record("ben-9")
        self.assertEqual((rec["args"]["tier"], rec["effort"]), ("deep", "high"))  # no silent reallocation
        self.assertEqual(self.queue(), [])

    def test_dequeue_starts_a_queued_docs_pass(self):  # #1026
        with open(self.project, "a") as f:
            f.write("\n[docs]\nenabled = true\n")
        for n in ("7", "8"):
            self.assertEqual(self.spawn("researcher", "--issue", n).returncode, 0)
        self.assertTrue(self.spawn("researcher", "--docs-pass").stdout.startswith("queued: researcher research docs pass"))
        self.assertEqual(self.crew("kill", "riley-7", "--project", self.project).returncode, 0)
        self.assertEqual(self.record("riley-docs")["args"]["docs_pass"], True)
        self.assertEqual(self.queue(), [])

    def test_queued_reflection_keeps_its_request_through_dequeue(self):  # #1520
        for n in ("7", "8"):
            self.assertEqual(self.spawn("researcher", "--issue", n).returncode, 0)
        r = self.spawn("researcher", "--reflection", "close-3", "--log", "5")
        self.assertTrue(r.stdout.startswith("queued: researcher research reflection close-3"), r.stdout)
        queued = self.queue()[0]["reflection"]
        self.assertEqual((queued["window"], queued["log"], queued["sha"]), ("close-3", 5, self.git("rev-parse", "HEAD")))
        self.assertTrue(queued["run"].startswith("close-3-"))
        self.git("commit", "-q", "--allow-empty", "-m", "newer")  # the head moves while it waits
        self.git("push", "-q", "origin", "main")
        time.sleep(1)  # a re-minted run ID would differ
        self.assertEqual(self.crew("kill", "riley-7", "--project", self.project).returncode, 0)
        rec = self.record("riley-reflection")
        self.assertEqual((rec["args"]["reflection"], rec["head"]), (queued, queued["sha"]))
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

    def test_reclaim_uses_present_cap_below_full_cap(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace("builders = 2", "builders = 10, present_builders = 8"))
        for issue in range(7, 15):
            self.assertEqual(self.spawn("builder", "--issue", str(issue)).returncode, 0)
        self.assertIn("queued:", self.spawn("builder", "--issue", "15").stdout)
        for issue, stamp in ((7, 200), (8, 100)):
            self.put("status/ben-%d.status" % issue, "done: #%d #12 %s\n" % (issue, "a" * 40))
            os.utime(os.path.join(self.state, "status", "ben-%d.status" % issue), (stamp, stamp))
        self.assertEqual(self.crew("dequeue", "--project", self.project, "--timeout", "1").returncode, 0)
        self.assertEqual(self.record("ben-15")["index"], 18)
        self.assertEqual(self.spawn("builder", "--issue", "16").returncode, 0)
        self.assertEqual(len(self.windows()), 10)
        self.assertIn("queued:", self.spawn("builder", "--issue", "17").stdout)
        oldest = self.record("ben-8")["worktree"]
        held = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(held.returncode, 0, held.stdout + held.stderr)
        self.assertNotIn("reclaimed", held.stdout)
        self.assertTrue(os.path.exists(oldest))
        self.assertEqual([e["issue"] for e in self.queue()], [17])
        self.put("status/ben-9.status", "done: #9 #12 %s\n" % ("a" * 40))
        result = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reclaimed idle builder ben-8", result.stdout)
        self.assertFalse(os.path.exists(oldest))
        self.assertEqual(self.queue(), [])
        if TRANSCRIPT:
            print("present cap 8 of 10: band full, 8 busy, issue #17 queued -> dequeue keeps idle ben-8")
            print("ben-9 done, 7 busy -> dequeue reclaims ben-8 and starts ben-17")

    def test_idle_expiry_retains_output_without_queue_and_can_be_disabled(self):
        self.spawn("builder", "--issue", "7")
        rec = self.record("ben-7")
        self.put("inbox/ben-7.jsonl", json.dumps(dict(id="policy", kind="owner-policy", refs=[])) + "\n")
        self.put("status/ben-7.status", "done: #7 #12 %s\nack: policy\n" % ("a" * 40))
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
        with open(os.path.join(retained, "run.json")) as f:  # the reclaim identity route matches (#1552)
            self.assertEqual(json.load(f), {"window": "ben-7", "run": [rec.get(k) for k in (
                "start", "pane_id", "pane_pid", "pane_start", "worktree")]})
        if TRANSCRIPT:
            print("idle-only: ttl=0 retains builder; ttl=30 reclaims without queued work")
            print("after expiry: builder worktree absent; status, output and build summary retained")

    def test_unacknowledged_message_keeps_done_builder_busy(self):
        self.spawn("builder", "--issue", "7")
        self.spawn("builder", "--issue", "8")
        self.put("status/ben-7.status", "done: #7 #12 " + "a" * 40 + "\n")
        for kind in ("fix", "ci-red", "merge-up"):
            with self.subTest(kind=kind):
                self.put("inbox/ben-7.jsonl", json.dumps(dict(id="pending", kind=kind, refs=["#12"])) + "\n")
                self.assertIn("queued:", self.spawn("builder", "--issue", "9").stdout)
                result = self.crew("dequeue", "--idle-only", "--project", self.project)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(os.path.exists(self.record("ben-7")["worktree"]))

    def test_policy_idle_reclaim_preserves_unlanded_work(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        wt = self.record("ben-7")["worktree"]
        path = os.path.join(wt, "work.txt")
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % ("a" * 40))
        self.put("inbox/ben-7.jsonl", json.dumps(dict(id="policy", kind="owner-policy", refs=[])) + "\n")
        status = os.path.join(self.state, "status", "ben-7.status")
        os.utime(status, (100, 100))
        with open(path, "w") as f:
            f.write("work\n")
        for kind in ("untracked", "unpublished", "dirty"):
            with self.subTest(kind=kind):
                if kind == "unpublished":
                    self.git("add", "work.txt", cwd=wt)
                    self.git("commit", "-qm", "unpublished work", cwd=wt)
                elif kind == "dirty":
                    self.git("push", "-q", "origin", "HEAD:refs/pull/12/head", cwd=wt)
                    with open(path, "a") as f:
                        f.write("dirty\n")
                result = self.crew("dequeue", "--idle-only", "--project", self.project)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("reclaimed idle builder", result.stdout)
                self.assertTrue(os.path.exists(path))
        self.git("checkout", "--", "work.txt", cwd=wt)
        result = self.crew("dequeue", "--idle-only", "--project", self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reclaimed idle builder ben-7", result.stdout)
        self.assertFalse(os.path.exists(wt))

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

    def test_queued_reviewer_keeps_its_rereview_id_through_dequeue(self):  # #1477
        for pr in ["5", "6"]:
            self.spawn("reviewer", "--pr", pr, "--head", self.pr(int(pr), "claude-code opus-5.5 v" + pr))
        sha = self.pr(4, "claude-code opus-5.5 v4")
        r = self.spawn("reviewer", "--pr", "4", "--head", sha, "--rereview-id", "42")
        self.assertTrue(r.stdout.startswith("queued: reviewer review PR #4"), r.stdout)
        self.assertEqual([(e["pr"], e["head"], e["rereview_id"]) for e in self.queue()], [(4, sha, "42")])
        self.assertEqual(self.crew("kill", "vera-5-r1-review", "--project", self.project).returncode, 0)
        self.assertEqual((self.record("vera-4-r1-review")["rereview_id"], self.record("vera-4-r1-review")["head"]),
                         ("42", sha))
        self.assertEqual(self.queue(), [])

    def test_kill_dequeues_only_the_freed_band(self):
        for issue in ("7", "8", "9"):
            self.assertEqual(self.spawn("builder", "--issue", issue).returncode, 0)
        for pr in (5, 6, 4):
            self.pr(pr, "claude-code opus-5.5 default")
            self.assertEqual(self.spawn("reviewer", "--pr", str(pr)).returncode, 0)
        # Another band becomes free without mdstack kill; killing a reviewer
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

    def test_ref_spawns_the_scheduler_grant_not_the_oldest(self):
        """#691 R1: with an older queued build #9 and a later queued fix of PR #5, `--ref #5` (the grant `schedule
        decide` returns) starts the fix and keeps #9 queued."""
        self.pr(5, "claude-code opus-5.5 default")
        for issue in ("7", "8", "9"):
            self.assertEqual(self.spawn("builder", "--issue", issue).returncode, 0)
        r = self.spawn("builder", "--pass", "fix", "--issue", "10", "--pr", "5")
        self.assertTrue(r.stdout.startswith("queued:"), r.stdout + r.stderr)
        self.put("render/runtime/builder-lead.md", "Manage the builder pool.\n")
        self.put("status/ben-7.status", "done: #7 #12 " + "a" * 40 + "\n")
        self.assertEqual([(e["issue"], e["pass"]) for e in self.queue()], [(9, "build"), (10, "fix")])
        result = self.crew("dequeue", "--ref", "#5", "--project", self.project, "--timeout", "1", CREW_POOL="builder")
        self.assertEqual((result.returncode, result.stderr), (0, "mdstack: config %s\n" % self.project), result.stdout)
        self.assertEqual(self.record("ben-10")["pass"], "fix")
        self.assertEqual([(e["issue"], e["pass"]) for e in self.queue()], [(9, "build")])
        result = self.crew("dequeue", "--ref", "#9", "--project", self.project, "--timeout", "1", CREW_POOL="builder")
        self.assertEqual(result.stdout, "crew: nothing to dequeue (1 queued, no free slot)\n")

    def test_lead_owned_pool_is_named_not_reported_as_no_free_slot(self):
        """#1100: a free builder slot held back by the builder lead names the pool; a full band still says no free
        slot, mixed pools say both, an unmatched --ref says so and the empty queue stays empty."""
        empty = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(empty.stdout, "crew: spawn queue empty\n")
        for issue in ("7", "8", "9"):
            self.assertEqual(self.spawn("builder", "--issue", issue).returncode, 0)
        self.put("render/runtime/builder-lead.md", "Manage the builder pool.\n")
        self.put("status/ben-7.status", "done: #7 #12 " + "a" * 40 + "\n")
        lead = "builder pool is lead-managed (use the builder lead or CREW_POOL=builder)"
        result = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(result.stdout, "crew: nothing to dequeue (1 queued, %s)\n" % lead)
        for pr in (5, 6, 4):
            self.pr(pr, "claude-code opus-5.5 default")
            self.assertEqual(self.spawn("reviewer", "--pr", str(pr)).returncode, 0)
        mixed = self.crew("dequeue", "--project", self.project, "--timeout", "1")
        self.assertEqual(mixed.stdout, "crew: nothing to dequeue (2 queued, %s; no free slot)\n" % lead)
        reviewer = self.crew("dequeue", "--ref", "#4", "--project", self.project, "--timeout", "1")
        self.assertEqual(reviewer.stdout, "crew: nothing to dequeue (2 queued, no free slot)\n")
        missing = self.crew("dequeue", "--ref", "#99", "--project", self.project, "--timeout", "1")
        self.assertEqual(missing.stdout, "crew: nothing to dequeue (2 queued, none match --ref #99)\n")
        self.assertEqual([(e["role"], e["issue"] or e["pr"]) for e in self.queue()], [("builder", 9), ("reviewer", 4)])
        started = self.crew("dequeue", "--ref", "#9", "--project", self.project, "--timeout", "1", CREW_POOL="builder")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.assertIn("ben-9", started.stdout)
        self.assertEqual([e["pr"] for e in self.queue()], [4])



if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "CapQueue.test_physical_band_pressure_reclaims_oldest_idle_builder",
                       "CapQueue.test_idle_expiry_retains_output_without_queue_and_can_be_disabled",
                       "CapQueue.test_reclaim_uses_present_cap_below_full_cap"] if TRANSCRIPT else None)
