"""Tests for crew restart, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import os
import unittest
from crew_testlib import HEAD, LivenessBase


class Restart(LivenessBase):
    def test_restart_only_dead_or_missing_and_once(self):
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ben-7 is alive", r.stdout)
        self.set_pane(10, dead="1")
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.windows()), 2)
        self.assertEqual(self.record("ben-7")["restarts"], 1)
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already restarted once; escalate", r.stdout)
        self.assertEqual(len(self.windows()), 2)

    def test_restart_refuses_finished_run(self):
        self.set_pane(10, dead="1")
        wt = self.record("ben-7")["worktree"]
        with open(os.path.join(wt, "notes.txt"), "w") as f:  # unlanded work does not change the refusal
            f.write("draft\n")
        self.put("status/ben-7.status", "failed: tests red\n")
        r = self.crew("restart", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("finished", r.stdout)
        self.assertEqual(len(self.windows()), 1)
        self.assertTrue(os.path.exists(os.path.join(wt, "notes.txt")))
        self.pr(9, "codex gpt-6.1-sol medium")  # done: is terminal for a reviewer run
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)
        self.set_pane(20, dead="1")
        self.put("status/vera-9-r1-review.status", "done: #9 %s review pass\n" % HEAD)
        r = self.crew("restart", "vera-9-r1-review", "--project", self.project)
        self.assertEqual((r.returncode, "finished" in r.stdout), (1, True), r.stdout)

    def test_restart_builder_dead_after_done(self):  # #139 F4: a builder stays for fix rounds after done:
        self.set_pane(10, dead="1")
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % HEAD)
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.record("ben-7")["restarts"], 1)

    def test_restart_dead_run_with_unlanded_work_relaunches_in_its_worktree(self):
        before = self.record("ben-7")
        wt = before["worktree"]
        self.git("commit", "-q", "--allow-empty", "-m", "local only", cwd=wt)
        with open(os.path.join(wt, "notes.txt"), "w") as f:
            f.write("draft\n")
        self.set_pane(10, dead="1")
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("keeping unlanded work", r.stdout)
        self.assertIn("uncommitted: ?? notes.txt", r.stdout)
        self.assertIn("commit: ", r.stdout)
        self.assertIn(["kill-window", "-t", "=crew-acme-widgets:10"], self.calls())
        call = self.windows()[-1]
        self.assertEqual((len(self.windows()), call[3], call[call.index("-c") + 1]), (2, "=crew-acme-widgets:10", wt))
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual(env["CREW_BRIEF"], os.path.join(self.state, "runs", "ben-7.brief.md"))
        self.assertNotIn("GH_TOKEN", env)
        after = self.record("ben-7")
        self.assertEqual((after["worktree"], after["claim"], after["restarts"]), (wt, before["claim"], 1))
        self.assertTrue(os.path.exists(os.path.join(wt, "notes.txt")))
        self.assertTrue(os.path.exists(before["claim"]))
        self.assertEqual(self.git("log", "-1", "--format=%s", cwd=wt), "local only")
        self.assertIn(wt, self.git("worktree", "list"))
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already restarted once; escalate", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(wt, "notes.txt")))

    def test_restart_dead_run_with_clean_worktree_respawns_fresh(self):
        wt = self.record("ben-7")["worktree"]
        with open(os.path.join(self.project_dir, ".git", "info", "exclude"), "a") as f:
            f.write("build-out/\n")  # ignored build output: the worktree still counts as clean
        os.makedirs(os.path.join(wt, "build-out"))
        self.set_pane(10, dead="1")
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew: started ben-7", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(wt, "build-out")))  # removed by crew kill, then re-created
        self.assertNotIn("keeping unlanded work", r.stdout)
        rec = self.record("ben-7")
        self.assertEqual((rec["restarts"], rec["worktree"]), (1, wt))  # same base SHA, so the same fresh path
        self.assertEqual(self.git("status", "--porcelain", cwd=wt), "")
        self.assertEqual(len(self.windows()), 2)


if __name__ == "__main__":
    unittest.main()
