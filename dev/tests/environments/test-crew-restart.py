"""Tests for mdstack restart, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: only when dead or missing and only once (fresh worktree when clean, relaunch in place
keeping unlanded work), a finished run refused, a builder after `done:` restarts as its PR's fix
pass (fresh or in place), an in-place relaunch accepts a Claude Code pane whose command reads as
its version (#286). Run in CI.
"""
import json
import os
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import HEAD, LivenessBase


class Restart(LivenessBase):
    def test_restart_passes_profile_sandbox_env_fresh_and_in_place(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"', 'name = "tmux"\noptions = { sandbox_env = "CREW_TEST_SANDBOX=profile" }'))
        self.env.pop("CREW_SANDBOX_ENV", None)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        with open(os.path.join(self.record("ben-8")["worktree"], "notes.txt"), "w") as f:
            f.write("keep\n")
        for name, index in (("ben-7", 10), ("ben-8", 11)):
            self.set_pane(index, dead="1")
            result = self.crew("restart", name, "--project", self.project, "--timeout", "1")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            call = self.windows()[-1]
            env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
            self.assertEqual(env["CREW_TEST_SANDBOX"], "profile")
            self.assertEqual(env["CREW_SANDBOX_ENV"], "CREW_TEST_SANDBOX=profile")

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
        sha = self.pr(12, "claude-code opus-5.5 default")
        self.set_pane(10, dead="1")
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % sha)
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("ben-7")  # #234 N2: the PR's fix pass, never a second build pass
        self.assertEqual((rec["restarts"], rec["pass"], rec["item"]), (1, "fix", "issue #7, PR #12"))
        self.assertEqual(rec["args"], {"issue": 7, "pr": 12, "pass": "fix", "round": 1, "tier": "default"})
        self.assertEqual(os.path.basename(rec["worktree"]), "12-%s-builder-fix" % sha[:7])
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=rec["worktree"]), sha)
        with open(os.path.join(self.state, "runs", "ben-7.brief.md")) as f:
            self.assertIn("- Pass: fix\n", f.read())

    def test_restart_builder_after_done_with_unlanded_work_relaunches_as_fix(self):  # #234 N2
        wt = self.record("ben-7")["worktree"]
        with open(os.path.join(wt, "notes.txt"), "w") as f:
            f.write("draft\n")
        self.set_pane(10, dead="1")
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % HEAD)
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("keeping unlanded work", r.stdout)
        rec = self.record("ben-7")
        self.assertEqual((rec["pass"], rec["item"], rec["args"]["pr"], rec["worktree"]), ("fix", "issue #7, PR #12", 12, wt))
        with open(os.path.join(self.state, "runs", "ben-7.brief.md")) as f:
            self.assertIn("- Restarted after done: as Pass fix, Item issue #7, PR #12\n", f.read())

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
        self.assertIn("--dangerously-bypass-approvals-and-sandbox --add-dir %s " % self.state, call[-1])  # #293
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
        self.assertFalse(os.path.exists(os.path.join(wt, "build-out")))  # removed by mdstack kill, then re-created
        self.assertNotIn("keeping unlanded work", r.stdout)
        rec = self.record("ben-7")
        self.assertEqual((rec["restarts"], rec["worktree"]), (1, wt))  # same base SHA, so the same fresh path
        self.assertEqual(self.git("status", "--porcelain", cwd=wt), "")
        self.assertEqual(len(self.windows()), 2)

    def test_restart_in_place_accepts_claude_version_pane(self):  # #286: the relaunch takes spawn's start evidence
        self.assertEqual(self.spawn("builder", "--issue", "8", "--tier", "trivial").returncode, 0)
        wt = self.record("ben-8")["worktree"]
        self.assertEqual(self.record("ben-8")["harness"], "claude")
        with open(os.path.join(wt, "notes.txt"), "w") as f:
            f.write("draft\n")
        self.set_pane(11, dead="1")
        claude = os.path.join(self.tmp, "bin", "claude")  # a plain `claude` on PATH: only the foreground names match
        with open(claude, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(claude, 0o755)
        self.env["FAKE_TMUX_PANE"] = "2.1.314"
        with open(self.ps, "w") as f:
            json.dump({"fg": {"/dev/ttyp11": [["S+", "claude"]]}}, f)
        r = self.crew("restart", "ben-8", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew: restarted ben-8 (window 11) in its worktree", r.stdout)
        self.assertEqual(self.record("ben-8")["restarts"], 1)


if __name__ == "__main__":
    unittest.main()
