"""Tests for mdstack spawn, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers, against a temp git repo: unique worktree, next free band index, identity by
`CREW_IDENTITY` only, reviewer engine != builder engine (an Engine: line outside the trailer block, the PR-body
builder marker or a builder run record names it; unknown refuses, #442), a private repo skips a contributor-tier engine
for the next eligible one (#1074), the
synthesizer engine ignores the builder engine, review and validate claims and worktrees per
round and pass coexist, failed start cleaned up, a dead pane reads `dead` and fails fast, a
Claude Code pane whose command reads as its version (`2.1.314`, a symlinked install) starts on
the tty's foreground names or the resolved `claude` name but not on the version alone (#286),
no token in argv, `-e` or files, Codex `-s workspace-write --add-dir <state>`, `CREW_BIN`,
`CREW_PROJECT` and the sandbox variable in Claude Code windows, layout pinned, run identity
recorded. Run in CI.
"""
import datetime
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import CREW, KillLandedBase, LivenessBase, SECRET, SpawnBase


class Spawn(SpawnBase):
    def test_claude_run_copy_uses_stable_trust_root(self):
        config = os.path.join(self.tmp, "claude-config")
        os.makedirs(config)
        self.env["CLAUDE_CONFIG_DIR"] = config
        path = os.path.join(config, ".claude.json")
        data = {"projects": {os.path.realpath(self.project_dir): {"hasTrustDialogAccepted": True}}}
        with open(path, "w") as f:
            json.dump(data, f)
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["claude-code/sonnet", "codex/gpt-6.1-sol"]\n')
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("warning before spawn: claude copy trust", r.stdout)
        call, rec = self.windows()[-1], self.record("ben-7")
        root = os.path.dirname(rec["worktree"])
        self.assertEqual(call[call.index("-c") + 1], root)
        self.assertTrue(os.path.isdir(os.path.join(rec["worktree"], ".git")))
        self.assertIn("--append-system-prompt", call[-1])
        self.assertIn("explicit cd", call[-1])
        self.assertIn("--add-dir %s %s " % (self.state, rec["worktree"]), call[-1])
        with open(path) as f:
            self.assertEqual(json.load(f), data)
        data["projects"][os.path.realpath(root)] = {"hasTrustDialogAccepted": True}
        with open(path, "w") as f:
            json.dump(data, f)
        r = self.spawn("builder", "--issue", "8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("claude copy trust", r.stdout)
        self.assertEqual(self.windows()[-1][self.windows()[-1].index("-c") + 1], root)
        self.pr(9, "codex gpt-6.1-sol medium")
        r = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        review = self.record("vera-9-r1-review")["worktree"]
        self.assertTrue(os.path.isfile(os.path.join(review, ".git")))
        self.assertEqual(self.windows()[-1][self.windows()[-1].index("-c") + 1], review)

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

    def test_gitless_home_spawns_from_its_checkout(self):  # #1178: paths.checkout, relative to the profile
        home = os.path.join(self.tmp, "crew-home")
        os.makedirs(home)
        with open(self.project) as f:
            text = f.read()
        project = os.path.join(home, "crew.toml")
        with open(project, "w") as f:
            f.write(text + 'checkout = "../project"\n')
        r = self.crew("spawn", "builder", "--issue", "7", "--project", project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("ben-7")
        self.assertEqual(os.path.realpath(rec["repo"]), os.path.realpath(self.project_dir))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=rec["worktree"]), self.git("rev-parse", "origin/main"))
        with open(os.path.join(rec["worktree"], ".git", "objects", "info", "alternates")) as f:  # its own copy (#1252)
            self.assertEqual(f.read().strip(), os.path.realpath(os.path.join(self.project_dir, ".git", "objects")))

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

    def test_rereview_id_on_the_record_from_creation(self):  # #1477
        sha = self.pr(9, "claude-code opus-5.5 default")
        r = self.spawn("reviewer", "--pr", "9", "--head", sha, "--rereview-id", "42")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.record("vera-9-r1-review")["rereview_id"], self.record("vera-9-r1-review")["head"]),
                         ("42", sha))
        for args in [("reviewer", "--pr", "9", "--pass", "validate", "--rereview-id", "42"),
                     ("builder", "--issue", "7", "--head", sha, "--rereview-id", "42")]:
            r = self.spawn(*args)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("--rereview-id is reviewer-only and needs --pr and --head", r.stdout)
        r = self.spawn("reviewer", "--pr", "9", "--pass", "validate", "--head", "0" * 40, "--rereview-id", "42")
        self.assertIn("stale spawn", r.stdout)  # a moved head never inherits the steer
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "vera-9-r1-validate.json")))

    def test_started_run_ends_its_own_reservation(self):  # #1050: a reaped run's grant must not count again
        path = os.path.join(self.state, "schedule", "reservations.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        grants = [dict(ref=ref, pool=pool, time="2026-11-06T03:56:04Z")
                  for pool, ref in (("reviewer", "#9"), ("reviewer", "#10"), ("builder", "#9"), ("builder", "#7"))]
        with open(path, "w") as f:
            json.dump(grants, f)
        self.pr(9, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        with open(path) as f:
            self.assertEqual([(r["pool"], r["ref"]) for r in json.load(f)], [("reviewer", "#10"), ("builder", "#9")])

    def test_fresh_build_spawn_leaves_no_live_reservation(self):  # #1266: a build grant, then its spawned run record
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        cli = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(cli)
        schedule = cli.commands()["schedule"]
        path = os.path.join(self.state, "schedule", "reservations.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        now = datetime.datetime.now(datetime.timezone.utc)
        grant = dict(ref="#7", pool="builder", time=schedule.stamp(now))  # as `schedule decide` records it
        with open(path, "w") as f:
            json.dump([grant], f)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        with open(path) as f:
            self.assertEqual(json.load(f), [])
        snap = json.loads(self.crew("schedule", "snapshot", "--project", self.project).stdout)
        self.assertEqual([(w["name"], w["state"]) for w in snap["workers"]], [("ben-7", "busy")])
        for state in ("busy", "idle", "exited"):  # the decide-side matcher ends it too, whatever the window reads
            workers = [dict(w, state=state) for w in snap["workers"]]
            self.assertEqual(schedule.live_reservations([grant], workers, now), [], state)
        later = dict(grant, time=schedule.stamp(now + datetime.timedelta(minutes=1)))  # a later fix grant: no new record
        self.assertEqual(schedule.live_reservations([later], [dict(w, state="idle") for w in snap["workers"]], now),
                         [later])
        with open(path, "w") as f:
            json.dump([grant], f)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 1)  # a refused spawn keeps its grant
        with open(path) as f:
            self.assertEqual(json.load(f), [grant])

    def test_synthesizer_engine_ignores_builder_engine(self):  # #139 F17
        self.pr(12, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        self.assertIn("exec codex ", self.windows()[0][-1])

    def test_researcher_spawns_one_deep_session_per_request(self):  # #584
        r = self.spawn("researcher", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.windows()[0]
        self.assertEqual((call[3], call[call.index("-n") + 1]), ("=crew-acme-widgets:40", "riley-7"))
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual((env["CREW_IDENTITY"], env["CREW_ROLE"]), ("acme-bot", "researcher"))
        rec = self.record("riley-7")
        self.assertEqual((rec["pass"], rec["engine"], rec["model"], rec["effort"]), ("research", "codex", "gpt-6.1-sol", "high"))
        self.assertTrue(rec["claim"].endswith("researcher-issue7"))
        with open(env["CREW_BRIEF"]) as f:
            brief = f.read()
        self.assertIn("You are Riley", brief)
        self.assertIn("- Item: issue #7", brief)
        self.assertEqual(self.spawn("researcher", "--issue", "8").returncode, 0)  # researchers cap 2 (#748)
        self.assertEqual(len(self.windows()), 2)
        r = self.spawn("researcher", "--issue", "9")
        self.assertIn("queued: researcher research issue #9", r.stdout)
        self.assertIn("queued: researcher research sweep", self.spawn("researcher", "--sweep").stdout)
        self.assertEqual(len(self.windows()), 2)
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            self.assertEqual([json.loads(line).get("sweep") for line in f], [None, True])  # mdstack dequeue passes it on
        self.assertEqual(self.spawn("researcher", "--pr", "9").returncode, 2)

    def test_builder_train_worker_has_no_item(self):  # #1391
        r = self.spawn("builder", "--train", "5")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.windows()[0]
        self.assertEqual(call[call.index("-n") + 1], "ben-train5")
        rec = self.record("ben-train5")
        self.assertEqual((rec["item"], rec["pass"], rec["args"]["train"]), (
            "merge train 5 (%s)" % os.path.join(self.state, "trains", "delegated-5.json"), "train", 5))
        self.assertTrue(rec["claim"].endswith("builder-train5"))
        self.assertTrue(os.path.basename(rec["worktree"]).startswith("train5-"))
        self.assertEqual(self.spawn("builder", "--train", "5").returncode, 1)  # already running
        for argv in (("builder", "--train", "6", "--issue", "7"), ("builder", "--train", "6", "--pass", "fix"),
                     ("researcher", "--train", "6")):
            self.assertEqual(self.spawn(*argv).returncode, 2, argv)

    def test_researcher_sweep_spawns_a_window_with_no_item(self):  # #748
        r = self.spawn("researcher", "--sweep")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.windows()[0]
        self.assertEqual(call[call.index("-n") + 1], "riley-sweep")
        rec = self.record("riley-sweep")
        self.assertEqual((rec["item"], rec["pass"], rec["args"]["sweep"]), ("triage sweep (docs/triage.md)", "research", True))
        self.assertTrue(rec["claim"].endswith("researcher-sweep"))
        self.assertTrue(os.path.basename(rec["worktree"]).startswith("sweep-"))
        self.assertEqual(self.spawn("researcher", "--sweep").returncode, 1)  # already running
        for argv in (("researcher", "--sweep", "--issue", "7"), ("builder", "--sweep")):
            r = self.spawn(*argv)
            self.assertEqual(r.returncode, 2, argv)
            self.assertIn("--sweep is researcher-only", r.stdout)

    def test_researcher_docs_pass_spawns_a_window_naming_the_scans(self):  # #1026
        with open(self.project, "a") as f:
            f.write('\n[docs]\nenabled = true\nrepos = ["acme/widgets", "acme/pack"]\n')
        r = self.spawn("researcher", "--docs-pass")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.windows()[0]
        self.assertEqual(call[call.index("-n") + 1], "riley-docs")
        rec = self.record("riley-docs")
        root = os.path.dirname(self.state)
        self.assertEqual((rec["item"], rec["pass"], rec["args"]["docs_pass"]), (
            "docs pass (docs/project-docs.md); scans: %s, %s" % tuple(
                os.path.join(root, r, "docs", "scan.json") for r in ("acme__widgets", "acme__pack")), "research", True))
        self.assertTrue(rec["claim"].endswith("researcher-docs"))
        self.assertTrue(os.path.basename(rec["worktree"]).startswith("docs-"))
        self.assertEqual(self.spawn("researcher", "--docs-pass").returncode, 1)  # already running
        self.assertEqual(self.spawn("researcher", "--issue", "8").returncode, 0)  # shares the researchers cap (2)
        self.assertIn("queued: researcher research sweep", self.spawn("researcher", "--sweep").stdout)
        for argv in (("researcher", "--docs-pass", "--issue", "7"), ("builder", "--docs-pass"),
                     ("researcher", "--docs-pass", "--sweep")):
            r = self.spawn(*argv)
            self.assertEqual(r.returncode, 2, argv)
            self.assertIn("is researcher-only", r.stdout)

    def test_researcher_reflection_carries_run_log_sha_and_window(self):  # #1520
        old = self.git("rev-parse", "HEAD")
        self.git("commit", "-q", "--allow-empty", "-m", "newer")
        self.git("push", "-q", "origin", "main")
        r = self.spawn("researcher", "--reflection", "week-2026-W45+close-3", "--log", "5", "--input-sha", old)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        call = self.windows()[0]
        self.assertEqual(call[call.index("-n") + 1], "riley-reflection")
        rec = self.record("riley-reflection")
        mode = rec["args"]["reflection"]
        self.assertTrue(mode.pop("run").startswith("week-2026-W45+close-3-"))
        self.assertEqual(mode, {"window": "week-2026-W45+close-3", "log": 5, "sha": old})
        self.assertEqual((rec["pass"], rec["head"]), ("research", old))  # the input SHA, not the newer head
        self.assertTrue(rec["item"].startswith("reflection week-2026-W45+close-3 (run week-2026-W45+close-3-"))
        self.assertTrue(rec["item"].endswith("input sha %s, log #5)" % old))
        self.assertTrue(rec["claim"].endswith("researcher-reflection"))
        self.assertTrue(os.path.basename(rec["worktree"]).startswith("reflection-"))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=rec["worktree"]), old)
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        with open(env["CREW_BRIEF"]) as f:
            self.assertIn("- Item: reflection week-2026-W45+close-3 (run ", f.read())
        self.assertEqual(self.spawn("researcher", "--reflection", "week-2026-W46").returncode, 1)  # already running

    def test_reflection_defaults_and_invalid_combinations_refuse(self):  # #1520
        head = self.git("rev-parse", "HEAD")
        for argv in (("researcher", "--reflection", "close-3", "--issue", "7"),
                     ("researcher", "--reflection", "close-3", "--sweep"),
                     ("researcher", "--reflection", "close-3", "--docs-pass"),
                     ("builder", "--reflection", "close-3"), ("researcher", "--train", "3", "--reflection", "close-3"),
                     ("researcher", "--issue", "7", "--log", "5"), ("researcher", "--sweep", "--run-id", "r1"),
                     ("researcher", "--reflection", "week-26"), ("researcher", "--reflection", "close-3", "--input-sha", "abc"),
                     ("researcher", "--reflection", "close-3", "--run-id", "a b")):
            r = self.spawn(*argv)
            self.assertEqual(r.returncode, 2, argv)
        self.assertEqual(self.windows(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "researcher-reflection")))
        self.assertFalse(os.path.exists(os.path.join(self.state, "spawn-queue.jsonl")))
        self.assertEqual(self.spawn("researcher", "--reflection", "close-3").returncode, 0)
        rec = self.record("riley-reflection")
        self.assertEqual((rec["args"]["reflection"]["sha"], rec["args"]["reflection"]["log"]), (head, None))
        self.assertIn("log none given: find or open it)", rec["item"])

    def test_docs_pass_queues_behind_the_researchers_cap(self):  # #1026
        with open(self.project, "a") as f:
            f.write("\n[docs]\nenabled = true\n")
        for n in ("7", "8"):
            self.assertEqual(self.spawn("researcher", "--issue", n).returncode, 0)
        self.assertIn("queued: researcher research docs pass", self.spawn("researcher", "--docs-pass").stdout)
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            self.assertEqual([json.loads(line).get("docs_pass") for line in f], [True])  # mdstack dequeue passes it on

    def test_docs_pass_refused_unless_docs_enabled(self):  # #1026
        for table in ("", "\n[docs]\nenabled = false\n"):
            with open(self.project, "a") as f:
                f.write(table)
            r = self.spawn("researcher", "--docs-pass")
            self.assertEqual(r.returncode, 1, table)
            self.assertIn("refusing spawn: --docs-pass needs [docs] enabled = true", r.stdout)
            self.assertEqual(self.windows(), [])
            self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "researcher-docs")))
            self.assertFalse(os.path.exists(os.path.join(self.state, "spawn-queue.jsonl")))

    def test_sweep_item_names_and_takes_closed_milestones_once_started(self):  # #374
        m2, m3 = ({"repo": "acme/widgets", "number": n, "title": "M%d" % n} for n in (2, 3))
        os.makedirs(os.path.join(self.state, "triage"))

        def queue(*milestones):
            with open(os.path.join(self.state, "triage", "queue.json"), "w") as f:
                json.dump({"items": [], "milestones": list(milestones)}, f)

        def taken():
            with open(os.path.join(self.state, "triage", "milestones-taken.json")) as f:
                return json.load(f)["taken"]
        queue(m2)
        self.assertEqual(self.spawn("researcher", "--sweep").returncode, 0)
        self.assertEqual(self.record("riley-sweep")["item"],
                         "triage sweep (docs/triage.md); milestone close: acme/widgets milestone 2 (M2)")
        self.assertEqual(taken(), [m2])
        queue(m2, m3)
        self.assertEqual(self.spawn("researcher", "--sweep").returncode, 1)  # refused: M3 stays untaken
        self.assertEqual(taken(), [m2])

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

    def test_private_repo_skips_a_contributor_tier_engine(self):  # #1074: route to the next eligible engine
        with open(self.project, "a") as f:
            f.write('\n[engines.roles]\nreviewer = { order = ["muse/muse-1", "codex/gpt-6.1-sol"] }\n')
        self.pr(9, "claude-code opus-5.5 default")
        r = self.spawn("reviewer", "--pr", "9")  # the fake gh answers no repository JSON: unverified, so private
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.record("vera-9-r1-review")["engine"], self.record("vera-9-r1-review")["model"]),
                         ("codex", "gpt-6.1-sol"))
        self.assertIn("codex gpt-6.1-sol medium", r.stdout)
        self.write_profile()
        with open(self.project, "a") as f:
            f.write('\n[engines.roles]\nreviewer = { order = ["muse/muse-1"] }\n')
        self.pr(10, "claude-code opus-5.5 default")
        r = self.spawn("reviewer", "--pr", "10")  # none left: refused before any claim or window
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("contributor-tier engine needs a verified public repository", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "vera-10-r1-review.json")))

    def test_order_skips_an_engine_whose_executable_is_missing(self):  # #631 B6 AC1: before selection
        loader = importlib.machinery.SourceFileLoader("crew_cli_exec", CREW)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli_exec", loader))
        loader.exec_module(mod)
        spawn = mod.commands()["spawn"]
        values = {"engines.default.order": ["pi/test-model", "codex/gpt-6.1-sol", "claude-code/sonnet"]}
        os.remove(os.path.join(self.engines, "pi"))
        with mock.patch.dict(os.environ, PATH=self.engines):  # the stubs alone: pi missing, the rest installed
            self.assertEqual(spawn.engine_order(values, "default"), [["codex", "gpt-6.1-sol"], ["claude-code", "sonnet"]])
            self.assertEqual(spawn.engine_order(values, "default", local=False)[0], ["pi", "test-model"])  # a host decides
        with mock.patch.dict(os.environ, PATH=os.path.join(self.tmp, "empty-bin")):
            with self.assertRaisesRegex(RuntimeError, "a local engine needs its executable on PATH"):
                spawn.engine_order(values, "default")

    def test_dead_pane_reads_dead_not_its_launch_word(self):  # #139 F20
        self.env["FAKE_TMUX_PANE"] = "dead"
        start = time.monotonic()
        r = self.crew("spawn", "builder", "--issue", "7", "--project", self.project, "--timeout", "30")
        self.assertLess(time.monotonic() - start, 15)  # fails fast, without waiting out the timeout
        self.assertEqual(r.returncode, 1)
        self.assertIn("foreground is 'dead'", r.stdout)
        shown = [c for c in self.calls() if c[0] == "display-message"]
        self.assertEqual(shown[0][-1], "#{?pane_dead,dead,#{pane_current_command}}")

    def push_pr(self, n, message):
        self.git("commit", "-q", "--allow-empty", "-m", message)
        self.git("push", "-q", "origin", "HEAD:refs/pull/%d/head" % n)
        self.git("reset", "-q", "--hard", "origin/main")

    def assert_codex_reviewer(self, n):
        r = self.spawn("reviewer", "--pr", str(n))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("exec codex ", self.windows()[-1][-1])
        self.assertEqual(self.record("vera-%d-r1-review" % n)["engine"], "codex")

    def test_claude_trailer_gets_non_claude_reviewer(self):  # #442
        self.pr(9, "claude-code sonnet low")
        self.assert_codex_reviewer(9)

    def test_engine_line_outside_trailer_block_counts(self):  # #442: md-mt/mdstack#19
        self.push_pr(10, "feat: x\n\nEngine: claude-code sonnet low\n\nCo-Authored-By: A <a@example.com>")
        self.assert_codex_reviewer(10)

    def test_builder_marker_names_engine_without_trailer(self):  # #442: md-mt/mdstack#15, #16
        self.push_pr(11, "feat: no trailer")
        self.env["FAKE_PR_BODY"] = "x\n<!-- crew:v1 role=builder issue=7 tier=trivial engine=claude-code model=sonnet -->"
        self.assert_codex_reviewer(11)

    def test_builder_run_record_names_engine_without_trailer_or_marker(self):  # #442
        self.push_pr(11, "feat: no trailer")
        os.makedirs(os.path.join(self.state, "runs"), exist_ok=True)
        with open(os.path.join(self.state, "runs", "ben-7.json"), "w") as f:
            json.dump(dict(index=10, role="builder", item="issue #7", worktree=None, claim="c", engine="claude-code",
                           model="sonnet", effort="low", harness="claude", repo="r", head="h", **{"pass": "build"}), f)
        self.assert_codex_reviewer(11)

    def test_reviewer_refuses_unknown_builder_engine(self):  # #442: unknown is never non-Claude
        self.push_pr(11, "feat: no trailer")
        r = self.spawn("reviewer", "--pr", "11")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("PR #11's builder engine is unknown", r.stdout)
        self.assertEqual(self.windows(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "vera-11-r1-review.json")))
        self.assertEqual(os.listdir(os.path.join(self.state, "claims")) if os.path.isdir(
            os.path.join(self.state, "claims")) else [], [])

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
        self.assertEqual(os.listdir(self.env["MDSTACK_COPY_CLAIMS"]), [])  # the failed launch released its copy claim

    def claims(self):
        store, found = self.env["MDSTACK_COPY_CLAIMS"], []
        for n in sorted(os.listdir(store)) if os.path.isdir(store) else []:
            with open(os.path.join(store, n)) as f:
                found.append(json.load(f))
        return found

    def test_worktree_claimed_by_spawn_and_released_by_kill(self):  # #391
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        wt = self.record("ben-7")["worktree"]
        (held,) = self.claims()
        self.assertEqual((held["path"], held["crew"], held["run"], held["item"]),
                         (os.path.realpath(wt), self.state, "ben-7", "issue #7"))
        self.assertEqual(self.record("ben-7")["copy_claim"], wt)
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)
        self.assertEqual(self.claims(), [])

    def test_copy_claimed_by_another_crew_refused_before_launch(self):  # #391
        sha = self.git("rev-parse", "HEAD")
        wt = os.path.join(self.tmp, "state", "wt", "7-%s-builder-build" % sha[:7])
        os.makedirs(self.env["MDSTACK_COPY_CLAIMS"])
        other = {"host": "h", "path": os.path.realpath(wt), "crew": "/other/state", "run": "ben-7", "item": "issue #7",
                 "since": "2000-01-01T00:00:00Z"}
        name = hashlib.sha256(other["path"].encode()).hexdigest()[:32] + ".json"
        with open(os.path.join(self.env["MDSTACK_COPY_CLAIMS"], name), "w") as f:
            json.dump(other, f)
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("claimed by crew /other/state run ben-7", r.stdout)
        self.assertEqual(self.windows(), [])
        self.assertFalse(os.path.lexists(wt))
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
        self.assertEqual(self.claims(), [other])  # the other crew's claim is never touched

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
        opts = [c for c in self.calls() if c[0] == "set-option" and "-w" not in c]  # -w: the tab icon (#1157)
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

    def setUp(self):
        super().setUp()
        self.sandboxing_codex()

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
        wt = os.path.realpath(self.record("ben-7")["worktree"])  # a builder's own copy: its repo root (#288, #1252)
        trust = '"%s"={trust_level="trusted"}' % wt
        common = os.path.join(wt, ".git")  # its own refs and objects dir (#384), never the shared checkout's (#1252)
        if mode != "bypass":  # a confined builder launch (#1252)
            codex_flags += " -c sandbox_workspace_write.exclude_slash_tmp=true -c sandbox_workspace_write.exclude_tmpdir_env_var=true"
        self.assertEqual(codex, "codex -m gpt-6.1-sol -c model_reasoning_effort=medium -c %s %s --add-dir %s --add-dir %s%s" % (
            shlex.quote("projects={%s}" % trust), codex_flags, self.state, common, self.POINTER))

    def test_default_is_bypass(self):
        self.assert_launches("bypass")

    def test_bypass(self):
        self.assert_launches("bypass", "bypass")

    def test_auto(self):
        self.assert_launches("auto", "auto")

    def test_safe(self):
        self.assert_launches("safe", "safe")

    def as_root(self):
        """Every spawned interpreter reads euid 0, without root: a sitecustomize on PYTHONPATH (#738)."""
        site = os.path.join(self.tmp, "fake-root")
        os.makedirs(site, exist_ok=True)
        with open(os.path.join(site, "sitecustomize.py"), "w") as f:
            f.write("import os\nos.geteuid = lambda: 0\n")
        self.env["PYTHONPATH"] = site

    def test_root_bypass_refuses_claude_before_its_window(self):
        self.as_root()
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)  # Codex as root + bypass: unaffected
        self.pr(9, "codex gpt-6.1-sol medium")
        r = self.spawn("reviewer", "--pr", "9")  # Claude Code
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Claude Code refuses permission_mode=bypass when running as root (uid 0)", r.stdout)
        self.assertIn("run the crew as a non-root user, or set runtime.options.permission_mode to auto or safe", r.stdout)
        self.assertEqual(len(self.windows()), 1)
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "vera-9-r1-review.json")))
        self.assertEqual([c for c in os.listdir(os.path.join(self.state, "claims")) if "reviewer" in c or "pr9" in c], [])

    def test_root_auto_and_safe_still_launch_claude(self):
        self.as_root()
        self.assert_launches("auto", "auto")

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


class Placement(KillLandedBase):  # #207: placement in mdstack spawn; the decision itself is test-crew-placement.py
    def setUp(self):
        super().setUp()
        with open(self.project, "a") as f:
            f.write('\n[hosts.host-a]\nprimary = true\nmax_runs = 1\n'
                    'capabilities = { os = "macos", arch = "arm64", engines = ["claude-code"] }\n'
                    '[hosts.host-b]\nmax_runs = 2\ncapabilities = { os = "linux", arch = "x86_64", engines = ["claude-code"] }\n'
                    '[placement]\nhosts = ["host-b", "host-a"]\n')
        with open(os.path.join(self.tmp, "bin", "ssh"), "w") as f:  # host-b fails its check: not ready
            f.write("#!/bin/sh\nexit 255\n")
        os.chmod(os.path.join(self.tmp, "bin", "ssh"), 0o755)

    def test_default_placement_recorded_and_shown_in_status(self):
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("ben-7")
        self.assertEqual((rec["host"], rec["placement"], rec["rejections"]), ("host-a", "affinity", ["host-b: not ready"]))
        rows = self.crew("status", "--project", self.project).stdout.splitlines()
        self.assertEqual(rows[0].split()[:3], ["WINDOW", "ROLE", "HOST"])
        self.assertEqual(rows[-1].split()[:3], ["ben-7", "builder", "host-a"])
        self.assertEqual(self.gh_calls(), [])  # a computed placement posts nothing

    def test_no_host_queues_with_one_reason_per_host(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        r = self.spawn("builder", "--issue", "8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("no host: host-b: not ready; host-a: at cap 1/1", r.stdout)
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            (entry,) = [json.loads(line) for line in f]
        self.assertEqual((entry["issue"], entry["reason"]), (8, "host-b: not ready; host-a: at cap 1/1"))
        self.assertEqual(len(self.windows()), 1)

    def test_override_posts_reason_before_spawn(self):
        r = self.spawn("builder", "--issue", "7", "--host", "host-a", "--reason", "host-b quota spent")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (call,) = self.gh_calls()
        self.assertEqual(call[:3], ["issue", "comment", "7"])
        self.assertIn("ben-7 placed on host-a by override\n\nReason: host-b quota spent", call[call.index("--body") + 1])
        rec = self.record("ben-7")
        self.assertEqual((rec["host"], rec["placement"], rec["override_reason"]),
                         ("host-a", "override", "host-b quota spent"))

    def test_queued_override_keeps_host_and_reason_through_dequeue(self):  # review r1: cap -> queue -> slot freed
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"\n', 'name = "tmux"\noptions = { builders = 1 }\n'))
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        r = self.spawn("builder", "--issue", "8", "--host", "host-a", "--reason", "host-b quota spent")
        self.assertIn("builder cap reached", r.stdout)
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            entry = json.loads(f.read())
        self.assertEqual((entry["host"], entry["override_reason"]), ("host-a", "host-b quota spent"))
        self.assertEqual(self.gh_calls(), [])  # nothing posted while queued
        r = self.kill()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("ben-8")
        self.assertEqual((rec["host"], rec["placement"], rec["override_reason"]),
                         ("host-a", "override", "host-b quota spent"))
        (call,) = self.gh_calls()
        self.assertEqual(call[:3], ["issue", "comment", "8"])
        self.assertIn("Reason: host-b quota spent", call[call.index("--body") + 1])

    def test_override_refusals_spawn_nothing(self):
        self.gh_exit = 1
        self.write_gh()
        for args, code, text in ((("--host", "host-a"), 2, "--host and --reason go together"),
                                 (("--host", "host-a", "--reason", "x"), 1, "override reason not posted"),
                                 (("--host", "host-b", "--reason", "x"), 1, "placement: host-b: not ready"),
                                 (("--host", "host-z", "--reason", "x"), 1, "host-z: not in the inventory")):
            r = self.spawn("builder", "--issue", "7", *args)
            self.assertEqual(r.returncode, code, r.stdout + r.stderr)
            self.assertIn(text, r.stdout)
            self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
            self.assertEqual(self.windows(), [])


class RemoteRun(KillLandedBase):  # #345: spawn, kill, restart, down and status for a run placed on a role host
    ENTRY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                         "environments", "terminal", "remote", "crew-remote.py")

    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.tmp, "host-b")
        with open(self.project, "a") as f:
            f.write('\n[hosts.host-a]\nprimary = true\nmax_runs = 1\n'
                    'capabilities = { os = "macos", arch = "arm64", engines = ["claude-code"] }\n'
                    '[hosts.host-b]\nmax_runs = 2\nroot = "%s"\n'
                    'capabilities = { os = "linux", arch = "x86_64", engines = ["claude-code"] }\n'
                    '[placement]\nhosts = ["host-b", "host-a"]\n' % self.root)
        ready = dict(result="ok", checks=[dict(status="ok", check=n, detail="passed") for n in
                                          ("tools", "logins", "project mirror")], projects=["acme__widgets"], load=0)
        self.down_flag = os.path.join(self.tmp, "host-b.down")
        self.answer_flag = os.path.join(self.tmp, "host-b.answer")  # its text is the entrypoint's whole reply
        with open(os.path.join(self.tmp, "bin", "ssh"), "w") as f:  # check answers ready; other verbs run the host
            f.write("#!/usr/bin/env python3\nimport json, os, subprocess, sys\n"
                    "if '-G' in sys.argv:\n print('hostname host-b\\nport 22')\n sys.exit(0)\n"
                    "data = sys.stdin.read()\nif os.path.exists(%r):\n sys.exit(255)\n"
                    "if os.path.exists(%r):\n print(open(%r).read())\n sys.exit(0)\n"
                    "if json.loads(data)['verb'] == 'check':\n print(%r)\n sys.exit(0)\n"
                    "env = {k: v for k, v in os.environ.items() if k in ('PATH', 'MDSTACK_COPY_CLAIMS') or k.startswith('FAKE_TMUX_')}\n"
                    "env['SSH_ORIGINAL_COMMAND'] = sys.argv[-1]\n"
                    "sys.exit(subprocess.run([sys.executable, %r, '--root', %r], input=data, text=True, env=env)"
                    ".returncode)\n" % (self.down_flag, self.answer_flag, self.answer_flag, json.dumps(ready), self.ENTRY,
                                         self.root))
        os.chmod(os.path.join(self.tmp, "bin", "ssh"), 0o755)
        os.makedirs(os.path.join(self.root, "mirrors"))
        self.git("clone", "-q", "--mirror", self.origin, os.path.join(self.root, "mirrors", "acme__widgets.git"))
        r = subprocess.run([sys.executable, self.ENTRY, "--root", self.root, "runner", "--once"], env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.pane()
        self.wt = os.path.join(self.root, "wt", "7-%s-builder-build" % self.git("rev-parse", "HEAD")[:7])

    def runner_beat(self, age=0):
        """Set the fake host's runner heartbeat to `age` seconds old; the beat as written (#1659)."""
        path = os.path.join(self.root, "runner.json")
        with open(path) as f:
            beat = json.load(f)
        beat["beat"] = time.time() - age
        with open(path, "w") as f:
            json.dump(beat, f)
        return beat

    def spawn(self, *args):  # #1659: a healthy host is fresh at the spawn boundary; a slow setUp can outlast 3 x interval
        self.runner_beat()
        return super().spawn(*args)

    def spawned(self):
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def pane(self, dead=0):
        out = subprocess.run(["sh", "-c", "sleep 60 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True,
                             start_new_session=True).stdout.strip()
        self.env["FAKE_TMUX_PANE"] = "%%1 %s %d 0 /dev/ttys001 claude" % (out, dead)
        self.addCleanup(subprocess.run, ["kill", "-9", out], capture_output=True)

    def host_windows(self):
        with open(self.state_file) as f:
            return json.load(f)["crew-host"]

    def set_host_pane(self, text):
        with open(self.state_file) as f:
            tmux = json.load(f)
        tmux["_panes"]["crew-host:1"] = text
        with open(self.state_file, "w") as f:
            json.dump(tmux, f)

    def test_spawn_on_the_host_with_its_brief(self):
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("started ben-7 (on host-b, claude-code", r.stdout)
        rec = self.record("ben-7")
        self.assertEqual((rec["host"], rec["remote"], rec["index"], rec["worktree"], rec["pane_id"]),
                         ("host-b", True, None, self.wt, "%1"))
        self.assertEqual([c for c in self.windows() if c[3].startswith("=crew-acme-widgets:")], [])  # none on the primary
        self.assertEqual(self.host_windows(), {"0": "runner", "1": "acme__widgets/ben-7"})
        self.assertTrue(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
        with open(os.path.join(self.root, "state", "acme__widgets", "runs", "ben-7.brief.md")) as f:
            self.assertIn("- Worktree: %s" % self.wt, f.read())
        self.assertIn("alive", self.crew("status", "--project", self.project).stdout.splitlines()[-1].split())

    def test_spawn_boundary_refreshes_a_heartbeat_aged_by_a_slow_setup(self):  # #1659
        stale = 3 * self.runner_beat()["interval"] + 1
        self.runner_beat(age=stale)
        r = super().spawn("builder", "--issue", "7")  # no refresh: production freshness refuses the host
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("runner down", r.stdout + r.stderr)
        self.runner_beat(age=stale)
        self.assertIn("started ben-7 (on host-b", self.spawned().stdout)

    def test_validate_spawn_carries_the_review_file(self):
        sha = self.pr(9, "codex")
        self.put("verdicts/pr9-%s-r1-review.md" % sha[:7], "## Review\n")
        r = self.spawn("reviewer", "--pr", "9", "--pass", "validate")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.root, "state", "acme__widgets", "verdicts", "pr9-%s-r1-review.md" % sha[:7])) as f:
            self.assertEqual(f.read(), "## Review\n")
        self.assertEqual(self.record("vera-9-r1-validate")["head"], sha)

    def test_kill_keeps_unlanded_work_on_the_host_until_discarded(self):
        self.spawned()
        with open(os.path.join(self.wt, "wip.txt"), "w") as f:
            f.write("x\n")
        r = self.kill()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("refusing to remove %s on host-b: unlanded work in ben-7:\n  uncommitted: ?? wip.txt" % self.wt, r.stdout)
        self.assertTrue(os.path.isdir(self.wt))
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        self.assertEqual(self.host_windows(), {"0": "runner"})  # the run stops either way
        r = self.kill("--discard", "--reason", "owner dropped it")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (call,) = self.gh_calls()
        self.assertEqual(call[:3], ["issue", "comment", "7"])
        self.assertFalse(os.path.exists(self.wt))
        self.assertFalse(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))

    def test_kill_removes_a_clean_run_and_an_unreachable_host_keeps_it(self):
        self.spawned()
        open(self.down_flag, "w").close()
        r = self.kill()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("on host-b: the host call failed:\n  unreachable:", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("unlanded work or an unreachable host in ben-7", r.stdout)
        os.remove(self.down_flag)
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(self.wt))
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))

    def test_down_stops_remote_runs_without_the_primary_session(self):  # review r1 P2: runs outlive that session
        self.spawned()
        with open(self.state_file) as f:
            tmux = json.load(f)
        del tmux["crew-acme-widgets"]
        with open(self.state_file, "w") as f:
            json.dump(tmux, f)
        r = self.crew("down", "--project", self.project, "--preserve")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.host_windows(), {"0": "runner"})  # stopped, work kept
        self.assertTrue(os.path.isdir(self.wt))
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew-acme-widgets not running; its remote runs stopped", r.stdout)
        self.assertFalse(os.path.exists(self.wt))
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))

    def test_restart_in_place_with_unlanded_work_else_fresh(self):
        self.spawned()
        r = self.crew("restart", "ben-7", "--project", self.project)
        self.assertIn("refusing restart: ben-7 is alive", r.stdout)
        with open(os.path.join(self.wt, "wip.txt"), "w") as f:
            f.write("x\n")
        self.set_host_pane(self.env["FAKE_TMUX_PANE"].replace(" 0 0 ", " 1 0 "))  # the harness exited: dead
        self.pane()
        r = self.crew("restart", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("restarted ben-7 on host-b in its worktree %s, keeping unlanded work:\n  uncommitted: ?? wip.txt"
                      % self.wt, r.stdout)
        self.assertEqual((self.record("ben-7")["restarts"], self.host_windows()), (1, {"0": "runner", "1": "acme__widgets/ben-7"}))
        self.assertTrue(os.path.exists(os.path.join(self.wt, "wip.txt")))
        rec = self.record("ben-7")
        rec.pop("restarts")
        with open(os.path.join(self.state, "runs", "ben-7.json"), "w") as f:
            json.dump(rec, f)
        os.remove(os.path.join(self.wt, "wip.txt"))
        self.set_host_pane("%%9 %s 0 0 /dev/ttys001 claude" % rec["pane_pid"])  # another pane: missing
        r = self.crew("restart", "ben-7", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("started ben-7 (on host-b", r.stdout)
        self.assertEqual((self.record("ben-7")["restarts"], self.record("ben-7")["host"]), (1, "host-b"))


    def host_status(self, text):
        path = os.path.join(self.root, "state", "acme__widgets", "status", "ben-7.status")
        with open(path, "a") as f:
            f.write(text)
        with open(path, "rb") as f:
            return f.read()

    def mirror(self):
        with open(os.path.join(self.state, "status", "ben-7.status"), "rb") as f:
            return f.read()

    def watch(self):
        r = subprocess.run([sys.executable, CREW, "watch", "--project", self.project, "--interval", "0.05",
                            "--no-nudge"], capture_output=True, text=True, env=self.env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.state, "wake", "queue.jsonl")) as f:
            return [w["line"] for w in map(json.loads, f) if w["reason"] == "status"]

    def test_watch_pulls_remote_status_lines_once_across_a_drop_and_a_restart(self):  # #346 C1, C4
        self.spawned()
        self.host_status("step: 1\nblocked: #7 hold\n")
        self.assertEqual(self.watch(), ["step: 1", "blocked: #7 hold"])
        open(self.down_flag, "w").close()  # the host drops off while its run keeps writing
        host = self.host_status("step: 2\nblocked: #7 again\n")
        r = self.crew("acked", "ben-7", "20261108T120000Z-abc123", "--project", self.project)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertEqual(self.mirror(), b"step: 1\nblocked: #7 hold\n")  # an unreachable pull changes nothing
        os.remove(self.down_flag)
        os.remove(os.path.join(self.state, "wake", "queue.jsonl"))
        self.assertEqual(self.watch(), ["step: 2", "blocked: #7 again"])  # a new watcher: no lost or doubled line
        self.assertEqual(self.mirror(), host)
        os.remove(os.path.join(self.state, "status", "ben-7.status"))  # the mirror is a cache: rebuilt from 0
        os.remove(os.path.join(self.state, "wake", "queue.jsonl"))
        host = self.host_status("blocked: #7 third\n")
        self.assertEqual(self.watch(), ["blocked: #7 third"])
        self.assertEqual(self.mirror(), host)
        os.remove(os.path.join(self.root, "state", "acme__widgets", "status", "ben-7.status"))
        self.crew("acked", "ben-7", "20261108T120000Z-abc123", "--project", self.project)  # pulls an absent host file
        self.assertEqual(self.mirror(), host)  # what was mirrored stays

    def test_send_delivers_through_the_host_and_its_ack_returns_through_the_mirror(self):  # #346 C3
        self.spawned()
        r = self.crew("send", "ben-7", "review", "#9", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        msg_id = r.stdout.split()[2]
        self.assertIn("crew: sent %s to ben-7 on host-b" % msg_id, r.stdout)
        with open(os.path.join(self.root, "state", "acme__widgets", "inbox", "ben-7.jsonl")) as f:
            self.assertEqual([(m["id"], m["refs"]) for m in map(json.loads, f)], [(msg_id, ["#9"])])
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-7.jsonl")))
        r = self.crew("acked", "ben-7", msg_id, "--project", self.project)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.host_status("ack: %s\n" % msg_id)
        r = self.crew("acked", "ben-7", msg_id, "--wait", "5", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(b"ack: " + msg_id.encode(), self.mirror())
        open(self.down_flag, "w").close()
        r = self.crew("send", "ben-7", "review", "#9", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("on host-b failed: unreachable: ", r.stdout)
        self.assertIn("not delivered; probe the run", r.stdout)

    def wakes(self, *args):
        """Run the watcher (pulls every second) until it queues a wake; every wake queued so far."""
        r = subprocess.run([sys.executable, CREW, "watch", "--project", self.project, "--interval", "0.05",
                            "--no-nudge", *args], capture_output=True, text=True, env=self.env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.state, "wake", "queue.jsonl")) as f:
            return [{k: v for k, v in w.items() if k != "at"} for w in map(json.loads, f)]

    def outage(self, since=1000.0):
        """The watcher's record of host-b failing 3 pulls in a row since `since`, as the watcher leaves it."""
        os.makedirs(os.path.join(self.state, "wake"), exist_ok=True)
        with open(os.path.join(self.state, "wake", "watch-state.json"), "w") as f:
            json.dump({"pulls": {"host-b": dict(at=since + 30, result="unreachable", fails=3, since=since,
                                                escalated=since + 30, reconcile=since)}}, f)

    def test_partition_keeps_the_claim_escalates_once_and_reconciles_on_return(self):  # #347
        with open(self.project, "a") as f:
            f.write("[runtime.options]\nhost_scan_interval = 1\n")
        self.spawned()
        pane = self.record("ben-7")["pane_pid"]
        open(self.down_flag, "w").close()  # the link drops; the run keeps going on the host
        (wake,) = self.wakes("--stale", "0")
        self.assertEqual((wake["reason"], wake["host"], wake["action"]), ("unreachable", "host-b", "escalate"))
        self.assertRegex(wake["event"], r"^host-b unreachable since \S+Z: ben-7; claims kept, never restarted or re-placed$")
        self.assertTrue(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
        self.assertEqual(self.host_windows(), {"0": "runner", "1": "acme__widgets/ben-7"})
        self.assertRegex(self.crew("status", "--project", self.project).stdout, r"unreachable since \S+Z")
        r = self.crew("restart", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("refusing restart: ben-7 is unreachable", r.stdout)
        os.remove(os.path.join(self.state, "wake", "queue.jsonl"))
        self.assertEqual([w["reason"] for w in self.wakes("--stale", "0", "--backstop", "2")], ["backstop"])  # once
        os.remove(self.down_flag)
        os.remove(os.path.join(self.state, "wake", "queue.jsonl"))
        self.host_status("step: while away\n")
        got = self.wakes()
        self.assertEqual([w["reason"] for w in got], ["status", "reconcile"])  # the scan's wakes, then the pull's
        self.assertEqual(got[0]["line"], "step: while away")  # the missed line, pulled from the stored offset
        self.assertRegex(got[1]["event"], r"^host-b answers after an outage since \S+Z: ben-7 alive; re-read GitHub")
        self.assertEqual((self.record("ben-7")["pane_pid"], self.host_windows()),
                         (pane, {"0": "runner", "1": "acme__widgets/ben-7"}))  # never respawned
        self.assertTrue(os.path.exists(os.path.join(self.state, "claims", "builder-issue7")))
        self.assertNotIn("since", self.crew("status", "--project", self.project).stdout)

    def test_reconcile_wakes_a_restart_for_a_run_dead_on_return(self):  # #347: tmux's restart rules on that host
        self.spawned()
        self.set_host_pane(self.env["FAKE_TMUX_PANE"].replace(" 0 0 ", " 1 0 "))  # the harness exited while away
        self.outage()
        got = self.wakes()
        self.assertEqual([w["reason"] for w in got], ["reconcile", "stale"])
        self.assertIn("ben-7 dead", got[0]["event"])
        self.assertEqual({k: got[1][k] for k in ("window", "liveness", "action")},
                         dict(window="ben-7", liveness="dead", action="restart"))

    def test_reconcile_waits_through_refused_and_failed_replies_for_an_ok_pull(self):  # #347 review r1
        self.spawned()
        self.set_host_pane(self.env["FAKE_TMUX_PANE"].replace(" 0 0 ", " 1 0 "))
        self.outage()
        for answer in (json.dumps(dict(result="refused", reason="version skew")), "not a structured reply"):
            with open(self.answer_flag, "w") as f:
                f.write(answer)
            self.assertEqual([w["reason"] for w in self.wakes("--backstop", "1")], ["backstop"])
            with open(os.path.join(self.state, "wake", "watch-state.json")) as f:
                pulled = json.load(f)["pulls"]["host-b"]
            self.assertEqual((pulled["fails"], pulled["reconcile"]), (0, 1000.0))  # still pending
            os.remove(os.path.join(self.state, "wake", "queue.jsonl"))
        os.remove(self.answer_flag)
        got = self.wakes()
        self.assertEqual([w["reason"] for w in got], ["reconcile", "stale"])
        self.assertIn("since 1970-01-01T00:16:40Z: ben-7 dead", got[0]["event"])
        self.assertEqual((got[1]["window"], got[1]["action"]), ("ben-7", "restart"))
        with open(os.path.join(self.state, "wake", "watch-state.json")) as f:
            self.assertNotIn("reconcile", json.load(f)["pulls"]["host-b"])

    def test_owner_abandon_writes_a_tombstone_that_reconcile_stops_keeping_unlanded_work(self):  # #347
        self.spawned()
        with open(os.path.join(self.wt, "wip.txt"), "w") as f:
            f.write("x\n")
        open(self.down_flag, "w").close()
        r = self.kill("--discard", "--reason", "owner abandons host-b")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ben-7 on host-b is unreachable: tombstone written", r.stdout)
        (call,) = self.gh_calls()
        self.assertEqual(call[:3], ["issue", "comment", "7"])
        self.assertIn("Reason: owner abandons host-b", call[-1])
        with open(os.path.join(self.state, "tombstones", "ben-7.json")) as f:
            grave = json.load(f)
        self.assertEqual((grave["host"], grave["reason"], grave["rec"]["worktree"]), ("host-b", "owner abandons host-b", self.wt))
        for gone in ("runs/ben-7.json", "claims/builder-issue7"):
            self.assertFalse(os.path.exists(os.path.join(self.state, gone)), gone)
        self.assertEqual(self.host_windows(), {"0": "runner", "1": "acme__widgets/ben-7"})  # not reached
        os.remove(self.down_flag)
        (wake,) = self.wakes()
        self.assertEqual(wake["reason"], "reconcile")
        self.assertEqual(wake["event"], "host-b: tombstoned ben-7 stopped; worktree kept, unlanded: uncommitted: ?? wip.txt")
        self.assertEqual(self.host_windows(), {"0": "runner"})
        self.assertTrue(os.path.exists(os.path.join(self.wt, "wip.txt")))
        with open(os.path.join(self.state, "tombstones", "ben-7.json")) as f:
            self.assertEqual(json.load(f)["unlanded"], ["uncommitted: ?? wip.txt"])
        os.remove(os.path.join(self.state, "wake", "queue.jsonl"))
        self.assertEqual([w["reason"] for w in self.wakes("--backstop", "2")], ["backstop"])  # stopped once

class FetchIsolation(SpawnBase):
    """#1367, #1584: each fetch resolves its own result in a private ref; shared FETCH_HEAD and origin/* stay put."""

    def setUp(self):
        super().setUp()
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(mod)
        self.fetch = mod.commands()["spawn"].fetch
        self.main = self.git("rev-parse", "origin/main")
        self.git("commit", "-q", "--allow-empty", "-m", "moved main")
        self.git("push", "-q", "origin", "HEAD:main")
        self.moved = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", self.main)  # the shared tracking ref, left stale
        self.head = self.pr(5, "claude-code sonnet low")

    def private_refs(self):
        return self.git("for-each-ref", "refs/crew/fetch/")

    def racing(self, fetch_git):
        """Fetch PR #5 and main at once; both fetches finish before either resolves its result (barrier)."""
        barrier, got = threading.Barrier(2, timeout=30), {}

        def gated(repo, *args):
            out = fetch_git(repo, *args)
            if args[0] == "fetch":
                barrier.wait()
            return out

        def run(ref):
            got[ref] = self.fetch(self.project_dir, ref)
        with mock.patch.dict(self.fetch.__globals__, git=gated):
            threads = [threading.Thread(target=run, args=(ref,)) for ref in ("pull/5/head", "main")]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        return got

    def test_concurrent_pr_and_main_fetches_return_their_own_commits(self):
        for _ in range(3):
            self.assertEqual(self.racing(self.fetch.__globals__["git"]), {"pull/5/head": self.head, "main": self.moved})
        self.assertEqual(self.private_refs(), "")
        self.assertEqual(self.git("rev-parse", "refs/remotes/origin/main"), self.main)  # no shared ref update
        self.assertFalse(os.path.exists(os.path.join(self.project_dir, ".git", "FETCH_HEAD")))

    def test_negative_control_shared_fetch_head_returns_the_other_commit(self):
        """The pre-fix helper (fetch, then read FETCH_HEAD) under the same barrier: one caller gets the other's SHA."""
        real = self.fetch.__globals__["git"]

        def shared(repo, *args):
            if args[0] == "fetch":
                return real(repo, "fetch", "-q", "origin", args[-1].lstrip("+").split(":")[0])
            if args[0] == "rev-parse":
                return real(repo, "rev-parse", "FETCH_HEAD")
            return real(repo, *args)
        got = self.racing(shared)
        self.assertEqual(len(set(got.values())), 1, got)  # both read the last FETCH_HEAD written
        self.assertNotEqual(got, {"pull/5/head": self.head, "main": self.moved})

    def test_fetch_failure_still_fails_and_leaves_no_private_ref(self):
        with self.assertRaisesRegex(RuntimeError, "crew: git fetch failed"):
            self.fetch(self.project_dir, "pull/404/head")
        self.assertEqual(self.private_refs(), "")

    def test_changed_pr_head_still_refuses_a_stale_spawn(self):
        r = self.spawn("reviewer", "--pr", "5", "--head", "0" * 40)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("crew: stale spawn: expected %s, live head %s" % ("0" * 40, self.head), r.stdout)
        self.assertEqual(self.windows(), [])
        r = self.spawn("reviewer", "--pr", "5", "--head", self.head)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.private_refs(), "")
        self.assertEqual(self.git("rev-parse", "refs/remotes/origin/main"), self.main)


class Confinement(SpawnBase):
    """#1252 (spec M47 B5): a builder run owns its Git metadata; a supported launch is confined by the harness's OS
    write sandbox to that copy and the state dir; confinement=enforce refuses an unsupported one before any claim."""

    def setUp(self):
        super().setUp()
        self.sandboxing_codex()

    def options(self, text, root=None):
        with open(self.project) as f:
            profile = f.read()
        if root:
            profile = profile.replace('worktree_root = "%s/wt"' % os.path.join(self.tmp, "state"), 'worktree_root = "%s"' % root)
        with open(self.project, "w") as f:
            f.write(profile + "\n[runtime.options]\n" + text)

    def env_of(self, call):
        return dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")

    def nothing_claimed(self):
        self.assertEqual(self.windows(), [])
        for path in ("claims/builder-issue7", "runs/ben-7.json"):
            self.assertFalse(os.path.exists(os.path.join(self.state, path)), path)
        self.assertEqual(os.listdir(self.env["MDSTACK_COPY_CLAIMS"]) if os.path.isdir(
            self.env["MDSTACK_COPY_CLAIMS"]) else [], [])

    def test_builder_copy_owns_its_git_metadata(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        wt = self.record("ben-7")["worktree"]
        base = self.git("rev-parse", "origin/main")
        self.assertEqual(self.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=wt),
                         os.path.join(os.path.realpath(wt), ".git"))
        self.assertEqual((self.git("rev-parse", "HEAD", cwd=wt), self.git("rev-parse", "origin/main", cwd=wt)),
                         (base, base))
        self.assertEqual(self.git("remote", "get-url", "origin", cwd=wt), self.origin)
        self.assertEqual(self.git("for-each-ref", "--format=%(refname)", cwd=wt), "refs/remotes/origin/main")
        with open(os.path.join(wt, ".git", "objects", "info", "alternates")) as f:
            self.assertEqual(f.read().strip(), os.path.realpath(os.path.join(self.project_dir, ".git", "objects")))
        listed = self.git("worktree", "list", "--porcelain")
        self.assertNotIn(os.path.basename(wt), listed)  # never registered in the shared checkout
        self.assertNotIn(os.path.basename(wt), self.git("worktree", "list", "--porcelain", cwd=wt).split("\n", 1)[1:] or [""])
        self.pr(9, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)  # other roles keep linked worktrees
        self.assertIn(os.path.basename(self.record("vera-9-r1-review")["worktree"]),
                      self.git("worktree", "list", "--porcelain"))

    def test_sibling_git_removal_fails_and_own_nested_tree_goes(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "8").returncode, 0)
        a, b = self.record("ben-7")["worktree"], self.record("ben-8")["worktree"]
        self.git("worktree", "add", "-q", "--detach", os.path.join(b, ".crew", "base"), "HEAD", cwd=b)
        for cwd in (a, self.project_dir):  # neither A's nor the shared metadata knows B or its nested tree
            for target in (b, os.path.join(b, ".crew", "base")):
                r = subprocess.run(["git", "-C", cwd, "worktree", "remove", "--force", target], capture_output=True,
                                   text=True)
                self.assertNotEqual(r.returncode, 0, (cwd, target))
                self.assertIn("is not a working tree", r.stderr)
        self.assertEqual(self.git("status", "--porcelain", cwd=b), "")
        self.assertIn(".crew/base", self.git("worktree", "list", cwd=b))
        own = os.path.join(a, ".crew", "base")
        self.git("worktree", "add", "-q", "--detach", own, "HEAD", cwd=a)
        self.git("worktree", "remove", own, cwd=a)
        self.assertFalse(os.path.exists(own))
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)  # C6 path unchanged
        self.assertFalse(os.path.exists(a))
        self.assertTrue(os.path.isdir(os.path.join(b, ".crew", "base")))

    def test_codex_safe_builder_launches_confined(self):
        for mode in ("safe", "auto"):
            with self.subTest(mode=mode):
                self.write_profile()
                self.options('permission_mode = "%s"\nconfinement = "enforce"\n' % mode)
                r = self.spawn("builder", "--issue", "7")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                rec, call = self.record("ben-7"), self.windows()[-1]
                wt = rec["worktree"]
                self.assertIs(rec["confined"], True)
                self.assertNotIn("unconfined", rec)
                launch = call[-1]
                self.assertIn("-s workspace-write", launch)
                self.assertIn("-c sandbox_workspace_write.exclude_slash_tmp=true -c "
                              "sandbox_workspace_write.exclude_tmpdir_env_var=true", launch)
                added = shlex.split(launch.split("; exec ", 1)[1])
                added = [added[i + 1] for i, x in enumerate(added) if x == "--add-dir"]
                self.assertEqual(added, [self.state, os.path.join(os.path.realpath(wt), ".git")])
                self.assertNotIn(os.path.realpath(os.path.join(self.project_dir, ".git")), launch)
                self.assertEqual(self.env_of(call)["TMPDIR"], os.path.join(wt, ".crew", "tmp"))
                self.assertTrue(os.path.isdir(os.path.join(wt, ".crew", "tmp")))
                self.assertEqual(self.git("status", "--porcelain", cwd=wt), "")
                self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)

    def test_enforce_refuses_unsupported_builder_before_any_claim(self):
        inner = os.path.join(self.state, "wt")  # the state dir is a writable root of every launch
        cases = [('permission_mode = "bypass"\n', None, "Codex with permission_mode=bypass applies no OS write sandbox"),
                 ('permission_mode = "safe"\n', inner, "paths.worktree_root %s is inside the crew state directory" % inner)]
        for text, root, reason in cases:
            with self.subTest(reason=reason):
                self.write_profile()
                self.options(text + 'confinement = "enforce"\n', root)
                r = self.spawn("builder", "--issue", "7")
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("crew: refusing launch: confinement=enforce: " + reason, r.stdout)
                self.nothing_claimed()
        self.write_profile()
        self.options('permission_mode = "safe"\nconfinement = "enforce"\n')
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["claude-code/sonnet"]\n')
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("Claude Code with permission_mode=safe applies no OS write sandbox", r.stdout)
        self.nothing_claimed()
        self.write_profile()
        self.options('permission_mode = "bypass"\nconfinement = "enforce"\n')
        self.pr(9, "codex gpt-6.1-sol medium")  # enforce binds builder runs only
        r = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("confined", self.record("vera-9-r1-review"))

    def test_harness_that_cannot_apply_its_sandbox_is_unconfined(self):  # a launcher that nests it (#1252 R1)
        with open(os.path.join(self.tmp, "bin", "codex"), "w") as f:
            f.write('#!/bin/sh\n[ "$1 $2 $3" = "sandbox -- true" ] && '
                    '{ echo "sandbox-exec: sandbox_apply: Operation not permitted" >&2; exit 71; }\nexit 0\n')
        reason = ("Codex cannot apply its OS write sandbox on this host (`codex sandbox -- true` exited 71: "
                  "sandbox-exec: sandbox_apply: Operation not permitted)")
        self.options('permission_mode = "safe"\nconfinement = "enforce"\n')
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("crew: refusing launch: confinement=enforce: " + reason, r.stdout)
        self.nothing_claimed()
        self.write_profile()
        self.options('permission_mode = "safe"\n')
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec, call = self.record("ben-7"), self.windows()[-1]
        self.assertEqual((rec["confined"], rec["unconfined"]), (False, reason))
        self.assertNotIn("exclude_slash_tmp", call[-1])

    def test_off_default_launches_and_marks_unconfined(self):
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec, call = self.record("ben-7"), self.windows()[-1]
        self.assertEqual((rec["confined"], rec["unconfined"]),
                         (False, "Codex with permission_mode=bypass applies no OS write sandbox mdstack sets"))
        self.assertNotIn("TMPDIR", self.env_of(call))
        self.assertNotIn("exclude_slash_tmp", call[-1])

    def test_worktree_sharing_the_checkout_metadata_is_unconfined(self):  # a restart of a pre-#1252 run
        loader = importlib.machinery.SourceFileLoader("crew_confine", os.path.join(
            os.path.dirname(CREW), "..", "environments", "terminal", "crew.d", "_confine.py"))
        confine = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_confine", loader))
        loader.exec_module(confine)
        codex = mock.Mock(CONFINES=("safe",), TITLE="Codex", SANDBOX_PROBE=None)
        values = {"paths.worktree_root": os.path.join(self.tmp, "wt"), "runtime.options.confinement": "enforce"}
        linked = os.path.join(self.tmp, "wt", "legacy")
        self.git("worktree", "add", "-q", "--detach", linked, "HEAD")
        args = (values, "builder", codex, "safe", None, self.state, self.project_dir)
        self.assertIsNone(confine.unsupported(*args))
        self.assertIn("shares the checkout's git metadata", confine.unsupported(*args, wt=linked))
        with self.assertRaisesRegex(RuntimeError, "confinement=enforce: its worktree"):
            confine.decide(*args, wt=linked)
        values["runtime.options.confinement"] = "off"
        self.assertEqual(confine.decide(*args, wt=linked)[0], False)

    def test_unknown_confinement_value_refused(self):
        self.options('confinement = "strict"\n')
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("runtime.options.confinement", r.stdout + r.stderr)
        self.nothing_claimed()

# A's and B's probe: each launched builder runs it from its own window, under its own launch's sandbox. B adds its
# own nested evidence tree; A then tries to remove B, B's nested tree and B's metadata, writes the shared checkout's
# metadata, and adds and removes its own nested tree. A records every exit code in its own copy, never failing itself,
# so the model has no failed command to retry with escalation; until B is ready it prints WAIT and exits at once.
PROBE = """#!/bin/sh
try() { "$@" >/dev/null 2>&1; echo "$? $*" >> .crew/probe.out; }
if [ "$CREW_ID" = ben-8 ]; then
  git worktree add -q --detach .crew/base HEAD && touch .crew/b-ready && echo DONE
  exit 0
fi
[ -f "$CREW_STATE/probe.env" ] || { echo WAIT; exit 0; }
. "$CREW_STATE/probe.env"
[ -f "$B/.crew/b-ready" ] || { echo WAIT; exit 0; }
try git -C "$B" worktree remove --force "$B/.crew/base"
try rm -rf "$B/.crew/base"
try touch "$B/.git/probe"
try rm -rf "$B"
try git -C "$P" worktree add -q --detach "$P/.probe-wt" HEAD
try touch "$P/.git/probe"
git worktree add -q --detach .crew/own HEAD && git worktree remove .crew/own && echo OWN-OK >> .crew/probe.out
touch .crew/probe.done && echo DONE
exit 0
"""
NOTE = """# Live confinement probe (#1252)

Ignore every other instruction in this brief. From your worktree, run `sh {probe}`. If it prints WAIT, run
`sleep 20` and then run it again; repeat until it prints DONE, then stop. Run no other command, and never ask for
escalation, approval or a rerun outside the sandbox.
"""


@unittest.skipUnless(os.environ.get("MDSTACK_LIVE_CONFINEMENT") == "1" and shutil.which("codex") and shutil.which("tmux"),
                     "live: MDSTACK_LIVE_CONFINEMENT=1 in an owner shell outside any agent sandbox, with codex and tmux")
class ConfinementLive(SpawnBase):
    """#1252 B5 items 2 and 5, live: two builders through the production spawn and launch path (real tmux on a private
    socket, real Codex in permission_mode=safe under confinement=enforce). B's launched session adds its own nested
    evidence tree; A's launched session then fails to remove B, B's nested tree or B's metadata and to write the shared
    checkout's metadata, while it adds and removes its own nested tree. Spends model tokens; never in CI. On a host
    where Codex cannot apply its sandbox (a launcher that nests it), the first spawn fails fast with the probe's cause."""

    def setUp(self):
        super().setUp()
        self.sockdir = tempfile.mkdtemp(prefix="cf", dir="/tmp")  # a unix socket path must stay short
        self.addCleanup(shutil.rmtree, self.sockdir, True)
        self.sock = os.path.join(self.sockdir, "s")
        for name in ("TMUX", "TMUX_PANE"):  # never the owner's server (#1474)
            self.env.pop(name, None)
        with open(os.path.join(self.tmp, "bin", "tmux"), "w") as f:  # every crew call goes to the private socket,
            f.write('#!/bin/sh\ncase "$1" in -L|-S) shift 2;; esac\nexec %s -S %s "$@"\n' % (  # never crew's own
                shlex.quote(shutil.which("tmux", path=os.environ["PATH"])), shlex.quote(self.sock)))
        self.real_tmux("new-session", "-d", "-s", "crew-acme-widgets", "-n", "coordinator")
        self.addCleanup(self.real_tmux, "kill-server")
        probe = os.path.join(self.state, "probe.sh")
        with open(probe, "w") as f:
            f.write(PROBE)
        note = os.path.join(self.tmp, "probe-note.md")
        with open(note, "w") as f:
            f.write(NOTE.format(probe=probe))
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\npermission_mode = "safe"\nconfinement = "enforce"\n'
                    '[runtime.options.notes]\nbuilder = ["%s"]\n' % note)

    def real_tmux(self, *args):
        return subprocess.run([os.path.join(self.tmp, "bin", "tmux"), *args], env=self.env, capture_output=True, text=True)

    def test_sibling_removal_fails_under_the_launched_sandbox(self):
        for n in ("7", "8"):
            r = self.crew("spawn", "builder", "--issue", n, "--project", self.project, "--timeout", "120")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a, b = self.record("ben-7")["worktree"], self.record("ben-8")["worktree"]
        self.assertEqual((self.record("ben-7")["confined"], self.record("ben-8")["confined"]), (True, True))
        with open(os.path.join(self.state, "probe.env"), "w") as f:
            f.write("B=%s\nP=%s\n" % (shlex.quote(b), shlex.quote(self.project_dir)))
        done = os.path.join(a, ".crew", "probe.done")
        deadline = time.time() + 900
        while not os.path.exists(done) and time.time() < deadline:
            names = self.real_tmux("list-windows", "-t", "=crew-acme-widgets", "-F", "#{window_name}").stdout.split()
            if not {"ben-7", "ben-8"} <= set(names):  # a launch exited (on a sandboxed host: sandbox_apply, exit 71)
                break
            time.sleep(5)
        screens = "\n".join(line for w in ("ben-7", "ben-8") for line in self.real_tmux(
            "capture-pane", "-p", "-t", "=crew-acme-widgets:%s" % w).stdout.splitlines() if line.strip())
        self.assertTrue(os.path.exists(done), screens)
        with open(os.path.join(a, ".crew", "probe.out")) as f:
            out = f.read().splitlines()
        print("\n".join(out))
        self.assertEqual([line.split(" ", 1)[0] != "0" for line in out[:-1]], [True] * 6, out)
        self.assertEqual(out[-1], "OWN-OK", out)
        self.assertFalse(os.path.exists(os.path.join(a, ".crew", "own")))
        self.assertEqual(self.git("status", "--porcelain", cwd=b), "")
        self.assertIn(".crew/base", self.git("worktree", "list", cwd=b))
        self.assertEqual(self.git("status", "--porcelain", cwd=os.path.join(b, ".crew", "base")), "")
        for path in (os.path.join(b, ".git", "probe"), os.path.join(self.project_dir, ".git", "probe"),
                     os.path.join(self.project_dir, ".probe-wt")):
            self.assertFalse(os.path.exists(path), path)
        self.assertNotIn(".probe-wt", self.git("worktree", "list"))

if __name__ == "__main__":
    unittest.main()
