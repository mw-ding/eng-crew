"""Tests for crew spawn, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers, against a temp git repo: unique worktree, next free band index, identity by
`CREW_IDENTITY` only, reviewer engine != builder engine (no trailer counts as non-Claude), the
synthesizer engine ignores the builder engine, review and validate claims and worktrees per
round and pass coexist, failed start cleaned up, a dead pane reads `dead` and fails fast, a
Claude Code pane whose command reads as its version (`2.1.314`, a symlinked install) starts on
the tty's foreground names or the resolved `claude` name but not on the version alone (#286),
no token in argv, `-e` or files, Codex `-s workspace-write --add-dir <state>`, `CREW_BIN`,
`CREW_PROJECT` and the sandbox variable in Claude Code windows, layout pinned, run identity
recorded. Run in CI.
"""
import json
import os
import shlex
import shutil
import time
import unittest
from crew_testlib import CREW, LivenessBase, SECRET, SpawnBase


class Spawn(SpawnBase):
    def test_solo_refused_before_claim_queue_or_window(self):
        self.env["FAKE_SOLO_ISSUE"] = "7"
        for args in (("--issue", "7"), ("--issue", "7", "--pr", "12", "--pass", "fix")):
            result = self.spawn("builder", *args)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("solo item", result.stdout)
        self.assertEqual(self.windows(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
        self.assertFalse(os.path.exists(os.path.join(self.state, "spawn-queue.jsonl")))
        self.env["FAKE_SOLO_ISSUE"] = ""
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)

    def test_cursor_launches_each_worker_with_model_and_no_effort_flag(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["cursor/composer-1", "codex/gpt-6.1-sol"]\n')
        binary = os.path.join(self.tmp, "bin", "cursor-agent")
        with open(binary, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(binary, 0o755)
        self.pr(9, "codex gpt-6.1-sol medium")
        for role, ref, name in (("builder", "--issue", "ben-7"),
                                ("reviewer", "--pr", "vera-9-r1-review"),
                                ("synthesizer", "--pr", "sam")):
            r = self.spawn(role, ref, "7" if role == "builder" else "9")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            launch = self.windows()[-1][-1]
            self.assertEqual(launch, 'export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec '
                             'cursor-agent --force --model composer-1 '
                             '"Read your brief at $CREW_BRIEF and follow it."')
            self.assertEqual((self.record(name)["engine"], self.record(name)["harness"]), ("cursor", "cursor-agent"))
            self.assertNotIn(SECRET, launch)

    def test_cursor_builder_engine_is_excluded_from_review(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["cursor/composer-1", "codex/gpt-6.1-sol"]\n')
        self.pr(9, "cursor composer-1 medium")
        r = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.record("vera-9-r1-review")["engine"], "codex")

    def test_cursor_refuses_unsupported_permission_modes_and_cleans_up(self):
        for mode in ("auto", "safe"):
            with self.subTest(mode=mode):
                self.write_profile()
                with open(self.project, "a") as f:
                    f.write('\n[engines.default]\norder = ["cursor/composer-1"]\n'
                            '\n[runtime.options]\npermission_mode = "%s"\n' % mode)
                r = self.spawn("builder", "--issue", "7")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("Cursor supports only permission_mode=bypass", r.stdout)
                self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
                self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
                self.assertEqual(self.windows(), [])

    def test_pi_launches_each_worker_with_provider_model_and_effort(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["pi/anthropic/claude-sonnet-4-5", "codex/gpt-6.1-sol"]\n')
        binary = os.path.join(self.tmp, "bin", "pi")
        with open(binary, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(binary, 0o755)
        self.pr(9, "codex gpt-6.1-sol medium")
        for role, ref, name in (("builder", "--issue", "ben-7"),
                                ("reviewer", "--pr", "vera-9-r1-review"),
                                ("synthesizer", "--pr", "sam")):
            r = self.spawn(role, ref, "7" if role == "builder" else "9")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            launch = self.windows()[-1][-1]
            self.assertEqual(launch, 'export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec '
                             'pi --approve --model anthropic/claude-sonnet-4-5 --thinking medium '
                             '"Read your brief at $CREW_BRIEF and follow it."')
            self.assertEqual((self.record(name)["engine"], self.record(name)["harness"]), ("pi", "pi"))
            self.assertNotIn(SECRET, launch)

    def test_pi_builder_engine_is_excluded_from_review(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["pi/anthropic/claude-sonnet-4-5", "codex/gpt-6.1-sol"]\n')
        self.pr(9, "pi anthropic/claude-sonnet-4-5 medium")
        r = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.record("vera-9-r1-review")["engine"], "codex")

    def test_pi_refuses_unsupported_permission_modes_and_cleans_up(self):
        for mode in ("auto", "safe"):
            with self.subTest(mode=mode):
                self.write_profile()
                with open(self.project, "a") as f:
                    f.write('\n[engines.default]\norder = ["pi/anthropic/claude-sonnet-4-5"]\n'
                            '\n[runtime.options]\npermission_mode = "%s"\n' % mode)
                r = self.spawn("builder", "--issue", "7")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("Pi supports only permission_mode=bypass", r.stdout)
                self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
                self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
                self.assertEqual(self.windows(), [])

    def test_runtime_notes_per_role_in_order_and_refreshed_at_spawn(self):
        paths = {}
        for role in ("builder", "reviewer", "synthesizer"):
            paths[role] = os.path.join(self.tmp, role + ".md")
            with open(paths[role], "w") as f:
                f.write(role + " standing policy\n")
        with open(os.path.join(self.state, "second.md"), "w") as f:
            f.write("second note\n")
        with open(self.project, "a") as f:
            f.write('\n[runtime.options.notes]\n' + "".join(
                '%s = [%s, "second.md"]\n' % (role, json.dumps(path)) for role, path in paths.items()))
        self.pr(9, "codex gpt-6.1-sol medium")
        for role, ref, name in (("builder", "--issue", "ben-9"),
                                ("reviewer", "--pr", "vera-9-r1-review"),
                                ("synthesizer", "--pr", "sam")):
            r = self.spawn(role, ref, "9")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            with open(os.path.join(self.state, "runs", name + ".brief.md")) as f:
                brief = f.read()
            expected = "\n## Runtime note: %s\n\n%s standing policy\n\n## Runtime note: second.md\n\nsecond note\n" % (
                paths[role], role)
            self.assertTrue(brief.endswith(expected), brief)
            for other in paths.keys() - {role}:
                self.assertNotIn(other + " standing policy", brief)
        with open(paths["builder"], "w") as f:
            f.write("updated policy\n")
        self.assertEqual(self.spawn("builder", "--issue", "10").returncode, 0)
        with open(os.path.join(self.state, "runs", "ben-10.brief.md")) as f:
            self.assertIn("updated policy", f.read())

    def test_runtime_notes_missing_or_unreadable_fail_before_claim_or_window(self):
        with open(self.project, "a") as f:
            f.write('\n[runtime.options.notes]\nbuilder = ["policy.md"]\n')
        path = os.path.join(self.state, "policy.md")
        for unreadable in (False, True):
            if unreadable:
                os.mkdir(path)
            r = self.spawn("builder", "--issue", "7")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("cannot read runtime.options.notes.builder file policy.md", r.stdout)
            self.assertEqual(self.windows(), [])
            self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
            self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))

    def test_no_runtime_notes_leaves_brief_unchanged(self):
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("ben-7")
        with open(os.path.join(self.state, "render", "briefs", "builder.md")) as f:
            expected = f.read() + "\n## This run\n\n" + "".join("- %s: %s\n" % kv for kv in [
                ("Window", "ben-7"), ("Item", "issue #7"), ("Pass", "build"), ("Worktree", rec["worktree"]),
                ("Base", rec["head"]), ("Engine", "codex gpt-6.1-sol medium"), ("Claim", rec["claim"])])
        with open(os.path.join(self.state, "runs", "ben-7.brief.md")) as f:
            self.assertEqual(f.read(), expected)

    def test_profile_sandbox_env_reaches_every_role_and_env_wins(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"', 'name = "tmux"\noptions = { sandbox_env = "CREW_TEST_SANDBOX=profile" }'))
        self.env.pop("CREW_SANDBOX_ENV", None)
        self.pr(9, "codex gpt-6.1-sol medium")
        for role, ref in (("builder", "--issue"), ("reviewer", "--pr"), ("synthesizer", "--pr")):
            result = self.spawn(role, ref, "9")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            call = self.windows()[-1]
            env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
            self.assertEqual(env["CREW_TEST_SANDBOX"], "profile")
            self.assertEqual(env["CREW_SANDBOX_ENV"], "CREW_TEST_SANDBOX=profile")
        self.env["CREW_SANDBOX_ENV"] = "CREW_TEST_SANDBOX=override"
        self.assertEqual(self.spawn("builder", "--issue", "10").returncode, 0)
        self.assertIn("CREW_TEST_SANDBOX=override", self.windows()[-1])

    def test_recheck_spawns_one_fresh_reviewer_session(self):
        sha = self.pr(9, "codex gpt-6.1-sol medium")
        r = self.spawn("reviewer", "--pr", "9", "--pass", "recheck", "--round", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.windows()), 1)
        rec = self.record("vera-9-r2-recheck")
        self.assertEqual((rec["pass"], rec["engine"]), ("recheck", "claude-code"))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=rec["worktree"]), sha)
        self.assertTrue(rec["worktree"].endswith("9-%s-reviewer-r2-recheck" % sha[:7]))
        self.assertTrue(rec["claim"].endswith("reviewer-pr9-%s-r2-recheck" % sha[:7]))
        self.assertTrue(rec["verdict"].endswith("pr9-%s-r2-recheck.md" % sha[:7]))
        with open(os.path.join(self.state, "runs", "vera-9-r2-recheck.brief.md")) as f:
            self.assertIn("- Pass: recheck", f.read())
        self.assertEqual(self.spawn("reviewer", "--pr", "9", "--pass", "recheck", "--round", "2").returncode, 1)

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
        self.assertEqual(env["CREW_PROJECT"], self.project)  # #234 N5, #139 F5
        launch = call[-1]
        self.assertIn('"%s"={trust_level="trusted"}' % os.path.realpath(wt), launch)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox --add-dir %s " % self.state, launch)  # #293
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
        self.assertIn("--add-dir %s " % self.state, call[-1])  # writes status, verdicts (#234 F15)
        self.assertNotIn("read-only", call[-1])
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

    def test_role_engine_override_beats_tier_order(self):  # #597
        with open(self.project, "a") as f:
            f.write('\n[engines.roles]\nsynthesizer = { order = ["claude-code/opus"] }\n')
        self.pr(12, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        self.assertEqual((self.record("sam")["engine"], self.record("sam")["model"]), ("claude-code", "opus"))
        self.assertIn("exec claude --model opus --effort medium", self.windows()[0][-1])
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)  # no builder override: tier order
        self.assertEqual(self.record("ben-7")["engine"], "codex")

    def test_reviewer_override_still_independent_of_builder(self):  # #597
        with open(self.project, "a") as f:
            f.write('\n[engines.roles]\nreviewer = { order = ["codex/gpt-6.1-sol", "claude-code/opus"] }\n')
        self.pr(9, "codex gpt-6.1-sol medium")
        r = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.record("vera-9-r1-review")["engine"], self.record("vera-9-r1-review")["model"]),
                         ("claude-code", "opus"))
        self.write_profile()
        with open(self.project, "a") as f:
            f.write('\n[engines.roles]\nreviewer = { order = ["codex/gpt-6.1-sol"] }\n')
        self.pr(10, "codex gpt-6.1-sol medium")
        r = self.spawn("reviewer", "--pr", "10")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("engine in engines.roles.reviewer.order differs from the builder's ['codex']", r.stdout)

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


class LaunchPolicy(SpawnBase):
    """runtime.options.permission_mode sets each engine's role-window permission argv (#293, #288, #269)."""
    FLAGS = {"bypass": ("--permission-mode bypassPermissions --settings "
                        + shlex.quote('{"skipDangerousModePermissionPrompt":true}'),
                        "--dangerously-bypass-approvals-and-sandbox"),
             "auto": ("--permission-mode auto",
                      "-s workspace-write -a on-request -c sandbox_workspace_write.network_access=true"),
             "safe": ("--permission-mode acceptEdits", "-s workspace-write -c sandbox_workspace_write.network_access=true")}
    POINTER = ' "Read your brief at $CREW_BRIEF and follow it."'

    def assert_launches(self, mode, option=None):
        if option:
            with open(self.project, "a") as f:
                f.write('[runtime.options]\npermission_mode = "%s"\n' % option)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)  # Codex: first in engines.default
        self.pr(9, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)  # Claude Code: differs from the builder
        codex, claude = (c[-1].split("; exec ", 1)[1] for c in self.windows())
        claude_flags, codex_flags = self.FLAGS[mode]
        # --add-dir before the mode flags: Claude's --add-dir is variadic and would take the prompt as a directory
        self.assertEqual(claude, "claude --model sonnet --effort medium --add-dir %s %s%s" % (
            self.state, claude_flags, self.POINTER))
        trust = ",".join('"%s"={trust_level="trusted"}' % os.path.realpath(d)
                         for d in (self.record("ben-7")["worktree"], self.project_dir))
        common = os.path.realpath(os.path.join(self.project_dir, ".git"))  # refs of a linked worktree (#384)
        self.assertEqual(codex, "codex -m gpt-6.1-sol -c model_reasoning_effort=medium -c %s %s --add-dir %s --add-dir %s%s" % (
            shlex.quote("projects={%s}" % trust), codex_flags, self.state, common, self.POINTER))  # repo root too (#288)

    def test_default_is_bypass(self):
        self.assert_launches("bypass")

    def test_bypass(self):
        self.assert_launches("bypass", "bypass")

    def test_auto(self):
        self.assert_launches("auto", "auto")

    def test_safe(self):
        self.assert_launches("safe", "safe")

    def test_unknown_mode_refused_before_any_window(self):
        with open(self.project, "a") as f:
            f.write('[runtime.options]\npermission_mode = "yolo"\n')
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("runtime.options.permission_mode: unknown value 'yolo' (expected one of: bypass, auto, safe)",
                      r.stdout)
        self.assertEqual(self.windows(), [])


class SpawnLiveness(LivenessBase):
    def test_spawn_records_run_identity(self):
        rec = self.record("ben-7")
        self.assertEqual((rec["pane_id"], rec["pane_pid"], rec["pane_start"]), ("%10", "9000010", "Fri Oct 30 10:00:00 2026"))
        self.assertEqual(rec["args"], {"issue": 7, "pr": None, "pass": "build", "round": 1, "tier": "default"})

    def claude_on_path(self, target=None):
        """`claude` first on PATH: a plain file, or a symlink to target, as a native install's versions/<version>."""
        path = os.path.join(self.tmp, "bin", "claude")
        if target:
            os.makedirs(os.path.dirname(target))
            os.symlink(target, path)
        with open(target or path, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(target or path, 0o755)

    def spawn_version_pane(self, fg):
        """A Claude Code reviewer whose pane command reads as its version (#286), with foreground names fg."""
        self.pr(9, "codex gpt-6.1-sol medium")
        self.env["FAKE_TMUX_PANE"] = "2.1.314"
        with open(self.ps, "w") as f:
            json.dump({"fg": {"/dev/ttyp20": fg}}, f)
        return self.spawn("reviewer", "--pr", "9")

    def test_claude_version_pane_starts_on_foreground_names(self):  # #286
        self.claude_on_path()
        r = self.spawn_version_pane([["Ss", "-zsh"], ["S+", "/opt/bin/claude"]])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew: started vera-9-r1-review", r.stdout)
        self.assertEqual(self.record("vera-9-r1-review")["harness"], "claude")

    def test_claude_version_pane_starts_on_resolved_symlink_name(self):  # #286
        self.claude_on_path(os.path.join(self.tmp, "versions", "2.1.314"))
        r = self.spawn_version_pane([])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew: started vera-9-r1-review", r.stdout)

    def test_version_pane_without_claude_evidence_fails(self):  # #286: no version-shaped match on its own
        self.claude_on_path()
        r = self.spawn_version_pane([["S+", "node"]])
        self.assertEqual(r.returncode, 1)
        self.assertIn("failed: vera-9-r1-review: foreground is '2.1.314', not claude", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "vera-9-r1-review.json")))


if __name__ == "__main__":
    unittest.main()
