"""Tests for crew spawn, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import json
import os
import shlex
import shutil
import time
import unittest
from crew_testlib import CREW, LivenessBase, SECRET, SpawnBase


class Spawn(SpawnBase):
    def test_builder_spawn_unique_worktree_identity_engine(self):
        self.env["CREW_SANDBOX_ENV"] = "CREW_TEST_SANDBOX=1"  # the org pack names the real variable
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        base = self.git("rev-parse", "origin/main")
        wt = os.path.join(self.tmp, "state", "wt", "7-%s-builder-build" % base[:7])
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=wt), base)
        call = self.windows()[0]
        self.assertEqual(call[:4], ["new-window", "-d", "-t", "=crew-acme-widgets:10"])
        self.assertEqual(call[call.index("-n") + 1], "ben-7")
        self.assertEqual(call[call.index("-c") + 1], wt)
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual(env["CREW_IDENTITY"], "acme-bot")
        self.assertEqual(env["CREW_ROLE"], "builder")
        self.assertEqual(env["CREW_ID"], "ben-7")
        self.assertEqual(env["CREW_INBOX"], os.path.join(self.state, "inbox", "ben-7.jsonl"))
        self.assertEqual(env["CREW_STATUS"], os.path.join(self.state, "status", "ben-7.status"))
        self.assertNotIn("GH_TOKEN", env)
        self.assertEqual(env["CREW_TEST_SANDBOX"], "1")
        self.assertEqual(env["CREW_BIN"], CREW)
        launch = call[-1]
        self.assertIn(shlex.quote('projects."%s".trust_level="trusted"' % wt), launch)
        self.assertTrue(launch.startswith('export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec codex '))
        self.assertIn("-m gpt-6.1-sol -c model_reasoning_effort=medium", launch)
        self.assertIn('"Read your brief at $CREW_BRIEF and follow it."', launch)
        with open(env["CREW_BRIEF"]) as f:
            brief = f.read()
        self.assertIn("Item: issue #7", brief)
        self.assertIn(wt, brief)
        rec = self.record("ben-7")
        self.assertEqual((rec["index"], rec["engine"], rec["harness"]), (10, "codex", "codex"))
        self.assertTrue(os.path.isfile(os.path.join(self.state, "claims", "builder-issue7")))

    def test_spawn_uses_runtime_brief_without_core(self):
        shutil.rmtree(os.path.join(self.state, "render"))
        self.crew("down", "--project", self.project)
        self.assertEqual(self.crew("up", "--project", self.project).returncode, 0)
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.state, "runs", "ben-7.brief.md")) as f:
            brief = f.read()
        self.assertIn("Fix rounds arrive in this same window via your inbox", brief)
        self.assertIn("- Item: issue #7", brief)

    def test_next_free_index_and_duplicate_refused(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        self.assertEqual([c[3] for c in self.windows()], ["=crew-acme-widgets:10", "=crew-acme-widgets:11"])
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already", r.stdout)
        self.assertEqual(len(self.windows()), 2)

    def test_reviewer_engine_differs_from_builder_engine(self):
        self.env["CREW_SANDBOX_ENV"] = "CREW_TEST_SANDBOX=1"
        sha = self.pr(9, "claude-code opus-5.5 default")
        r = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.windows()[0]
        self.assertEqual(call[call.index("-n") + 1], "vera-9-r1-review")
        self.assertEqual(call[3], "=crew-acme-widgets:20")
        self.assertIn("exec codex ", call[-1])
        self.assertIn("-s read-only", call[-1])
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual(env["CREW_IDENTITY"], "acme-reviewer")
        wt = self.record("vera-9-r1-review")["worktree"]
        self.assertTrue(wt.endswith("9-%s-reviewer-r1-review" % sha[:7]))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=wt), sha)
        self.pr(10, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("reviewer", "--pr", "10", "--pass", "validate", "--round", "2").returncode, 0)
        call = self.windows()[1]
        self.assertEqual(call[call.index("-n") + 1], "vera-10-r2-validate")
        self.assertIn("exec claude --model sonnet --effort medium", call[-1])
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual((env["CREW_BIN"], env["CREW_TEST_SANDBOX"]), (CREW, "1"))  # Claude windows too (#139 F8)

    def test_review_validate_and_next_round_coexist_at_one_head(self):  # #139 F3, F18
        sha = self.pr(9, "claude-code opus-5.5 default")
        for args in [(), ("--pass", "validate")]:
            r = self.spawn("reviewer", "--pr", "9", *args)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name, run in [("vera-9-r1-review", "r1-review"), ("vera-9-r1-validate", "r1-validate")]:
            rec = self.record(name)
            self.assertEqual(os.path.basename(rec["claim"]), "reviewer-pr9-%s-%s" % (sha[:7], run))
            self.assertEqual(os.path.basename(rec["worktree"]), "9-%s-reviewer-%s" % (sha[:7], run))
            self.assertTrue(os.path.isfile(rec["claim"]))
        self.assertEqual(self.spawn("reviewer", "--pr", "9", "--pass", "validate").returncode, 1)  # same run

    def test_synthesizer_engine_ignores_builder_engine(self):  # #139 F17
        self.pr(12, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        self.assertIn("exec codex ", self.windows()[0][-1])

    def test_dead_pane_reads_dead_not_its_launch_word(self):  # #139 F20
        self.env["FAKE_TMUX_PANE"] = "dead"
        start = time.monotonic()
        r = self.crew("spawn", "builder", "--issue", "7", "--project", self.project, "--timeout", "30")
        self.assertLess(time.monotonic() - start, 15)  # fails fast, without waiting out the timeout
        self.assertEqual(r.returncode, 1)
        self.assertIn("foreground is 'dead'", r.stdout)
        shown = [c for c in self.calls() if c[0] == "display-message"]
        self.assertEqual(shown[0][-1], "#{?pane_dead,dead,#{pane_current_command}}")

    def test_reviewer_unknown_builder_engine_treated_as_non_claude(self):
        self.git("commit", "-q", "--allow-empty", "-m", "no trailer")
        self.git("push", "-q", "origin", "HEAD:refs/pull/11/head")
        self.assertEqual(self.spawn("reviewer", "--pr", "11").returncode, 0)
        self.assertIn("exec claude ", self.windows()[0][-1])

    def test_no_token_in_argv_env_or_files(self):
        self.pr(9, "claude-code opus-5.5 default")
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)
        with open(self.log) as f:
            self.assertNotIn(SECRET, f.read())
        for c in self.windows():
            self.assertFalse([a for i, a in enumerate(c) if c[i - 1] == "-e" and "TOKEN" in a], c)
        for root, dirs, names in os.walk(self.tmp):
            dirs[:] = [d for d in dirs if d not in ("objects", "bin")]  # bin: the fake gh holds the value
            for n in names:
                with open(os.path.join(root, n), "rb") as f:
                    self.assertNotIn(SECRET.encode(), f.read(), os.path.join(root, n))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "gh.log")))

    def test_refuses_primary_checkout_and_missing_session(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('worktree_root = "%s/wt"' % os.path.join(self.tmp, "state"),
                                 'worktree_root = "%s"' % self.project_dir))
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("primary checkout", r.stdout)
        self.crew("down", "--project", self.project)
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not reachable", r.stdout)
        self.assertEqual(self.windows(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))

    def test_failed_start_cleans_up(self):
        self.env["FAKE_TMUX_PANE"] = "bash"
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("failed:", r.stdout)
        self.assertIn(["kill-window", "-t", "=crew-acme-widgets:10"], self.calls())
        self.assertEqual(os.listdir(os.path.join(self.tmp, "state", "wt")), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))

    def test_layout_pinned_on_spawn_and_ash_stays_0_after_kill(self):
        self.env["FAKE_TMUX_USER_CONF"] = "1"
        with open(self.state_file) as f:  # session made before pinning existed: no session options yet
            state = json.load(f)
        state.pop("_opts", None)
        with open(self.state_file, "w") as f:
            json.dump(state, f)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)
        with open(self.state_file) as f:
            self.assertEqual(json.load(f)["crew-acme-widgets"], {"0": "ash", "11": "ben-8"})
        opts = [c for c in self.calls() if c[0] == "set-option"]
        self.assertTrue(opts and all(c[1:3] == ["-t", "=crew-acme-widgets:"] and "-g" not in c for c in opts), opts)


class SpawnLiveness(LivenessBase):
    def test_spawn_records_run_identity(self):
        rec = self.record("ben-7")
        self.assertEqual((rec["pane_id"], rec["pane_pid"], rec["pane_start"]), ("%10", "9000010", "Fri Oct 30 10:00:00 2026"))
        self.assertEqual(rec["args"], {"issue": 7, "pr": None, "pass": "build", "round": 1, "tier": "default"})


if __name__ == "__main__":
    unittest.main()
