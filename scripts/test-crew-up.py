"""Tests for crew up, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: session created, engine command, brief path (default inputs give the tmux briefs
from `templates/`), Stop hook install, idempotent, other runtime refused, a pre-trusted
Codex coordinator (projects table: the project dir and a linked worktree's repo root),
`CREW_BIN`, `CREW_PROJECT` and the sandbox variable in window 0, no render chatter,
rebuilding `ash` from disk without respawning runs. Run in CI.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import unittest
from crew_testlib import Base, CREW, LivenessBase


class Up(Base):
    def setUp(self):
        super().setUp()
        self.env["CODEX_HOME"] = os.path.join(self.tmp, "codex-home")

    def test_up_creates_session_with_engine_and_brief(self):
        self.env["CREW_SANDBOX_ENV"] = "CREW_TEST_SANDBOX=1"
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")  # no render chatter (#139 F19)
        call = self.new_session()
        brief = os.path.join(self.state, "render", "briefs", "coordinator.md")
        self.assertTrue(os.path.isfile(brief))
        self.assertEqual(call[call.index("-s") + 1], "crew-acme-widgets")
        self.assertEqual(call[call.index("-n") + 1], "ash")
        self.assertEqual(call[call.index("-c") + 1], self.project_dir)
        env = [call[i + 1] for i, a in enumerate(call) if a == "-e"]
        self.assertIn("CREW_BRIEF=" + brief, env)
        self.assertIn("CREW_IDENTITY=acme-bot", env)
        self.assertIn("CREW_ROLE=coordinator", env)
        self.assertIn("CREW_STATE=" + self.state, env)
        self.assertIn("CREW_BIN=" + CREW, env)
        self.assertIn("CREW_PROJECT=" + self.project, env)  # #234 N5
        self.assertIn("CREW_TEST_SANDBOX=1", env)
        launch = call[-1]
        self.assertIn('GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"', launch)
        self.assertIn('exec claude "Read your brief at $CREW_BRIEF and follow it."', launch)
        self.assertNotIn("GH_TOKEN", " ".join(env))
        self.assertIn(["move-window", "-s", "=crew-acme-widgets", "-t", "=crew-acme-widgets:0"], self.calls())
        opts = [c for c in self.calls() if c[0] == "set-option"]
        self.assertEqual(opts, [["set-option", "-t", "=crew-acme-widgets:", "renumber-windows", "off"],
                                ["set-option", "-t", "=crew-acme-widgets:", "base-index", "0"]])

    def test_profile_sandbox_env_survives_coordinator_rebuild_and_env_wins(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"', 'name = "tmux"\noptions = { sandbox_env = "CREW_TEST_SANDBOX=profile" }'))
        self.env.pop("CREW_SANDBOX_ENV", None)
        for setting in (None, "CREW_TEST_SANDBOX=override", ""):
            if setting is not None:
                self.env["CREW_SANDBOX_ENV"] = setting
            for _ in range(2):  # rebuild coordinator from its profile, without a parent environment
                self.assertEqual(self.up().returncode, 0)
                call = [c for c in self.calls() if c[0] == "new-session"][-1]
                env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
                if setting == "":
                    self.assertNotIn("CREW_TEST_SANDBOX", env)
                else:
                    self.assertEqual(env["CREW_TEST_SANDBOX"], "profile" if setting is None else "override")
                    self.assertEqual(env["CREW_SANDBOX_ENV"], setting or "CREW_TEST_SANDBOX=profile")
                self.assertEqual(self.crew("down", "--project", self.project).returncode, 0)

    def test_up_defaults_to_tmux_briefs_from_templates(self):
        r = self.crew("up", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        brief = os.path.join(self.state, "render", "runtime", "coordinator.md")
        call = self.new_session()
        self.assertIn("CREW_BRIEF=" + brief, [call[i + 1] for i, a in enumerate(call) if a == "-e"])
        with open(brief) as f:
            self.assertIn("You are Ash, in window 0", f.read())
        self.assertFalse(os.path.exists(os.path.join(self.state, "render", "briefs")))

    def test_up_installs_stop_hook_once_and_keeps_settings(self):
        os.makedirs(os.path.join(self.project_dir, ".claude"))
        with open(os.path.join(self.project_dir, ".claude", "settings.local.json"), "w") as f:
            json.dump({"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "other"}]}]}}, f)
        self.assertEqual(self.up().returncode, 0)
        self.crew("down", "--project", self.project)
        self.assertEqual(self.up().returncode, 0)
        s = self.settings()
        self.assertEqual(s["model"], "x")
        commands = [h["command"] for e in s["hooks"]["Stop"] for h in e["hooks"]]
        guard = [c for c in commands if " guard --state " in c]
        self.assertEqual(len(guard), 1, commands)
        self.assertIn("other", commands)
        self.assertIn(self.state, guard[0])

    def test_up_codex_engine_no_claude_settings(self):
        self.write_profile(engine="codex")
        self.assertEqual(self.up().returncode, 0)
        trust = shlex.quote('projects={"%s"={trust_level="trusted"}}' % os.path.realpath(self.project_dir))
        self.assertIn('exec codex -c %s "Read your brief at $CREW_BRIEF and follow it."' % trust, self.new_session()[-1])
        self.assertFalse(os.path.exists(os.path.join(self.project_dir, ".claude")))

    def test_up_codex_coordinator_pretrusts_project_dir_and_repo_root(self):
        """The projects table, not the projects."<dir>" key form that left the trust dialog up (#262), for the real
        project dir and the repo root, where Codex applies a linked worktree's trust (#288)."""
        repo, self.project_dir = self.project_dir, os.path.join(self.tmp, "wt")
        for args in (["init", "-q", "-b", "main"], ["commit", "-q", "--allow-empty", "-m", "base"],
                     ["worktree", "add", "-q", self.project_dir]):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t", *args], cwd=repo, check=True)
        self.write_profile(engine="codex")
        self.assertEqual(self.up().returncode, 0)
        launch = self.new_session()[-1]
        trust = 'projects={"%s"={trust_level="trusted"},"%s"={trust_level="trusted"}}' % (
            os.path.realpath(self.project_dir), os.path.realpath(repo))
        self.assertIn("exec codex -c %s " % shlex.quote(trust), launch)
        self.assertNotIn('projects."', launch)

    def test_up_is_idempotent(self):
        self.assertEqual(self.up().returncode, 0)
        r = self.up()
        self.assertEqual(r.returncode, 0)
        self.assertIn("already running", r.stdout)
        self.new_session()

    def test_up_refuses_other_runtime(self):
        self.write_profile(runtime="grok-bot")
        r = self.up()
        self.assertEqual(r.returncode, 1)
        self.assertIn("runtime.name is grok-bot", r.stdout)
        self.assertEqual(self.calls(), [])


class HostHooks(Base):
    def setUp(self):
        super().setUp()
        self.codex = os.path.join(self.tmp, "codex-home")
        os.makedirs(self.codex)
        self.env["CODEX_HOME"] = self.codex
        self.hooks_path = os.path.join(self.codex, "hooks.json")
        self.config_path = os.path.join(self.codex, "config.toml")

    def hooks(self, trusted=False, inline=False):
        hooks = {"SessionStart": [{"hooks": [{"type": "command", "command": "never-run"}]}]}
        if not inline:
            with open(self.hooks_path, "w") as f:
                json.dump({"hooks": hooks}, f)
        text = '[[hooks.SessionStart]]\n[[hooks.SessionStart.hooks]]\ntype = "command"\ncommand = "never-run"\n' if inline else ""
        source = self.config_path if inline else self.hooks_path
        if trusted:
            text += '[hooks.state.%s]\ntrusted_hash = "sha256:stored-not-recomputed"\n' % json.dumps(source + ":session_start:0:0")
        with open(self.config_path, "w") as f:
            f.write(text)

    def test_missing_trust_refuses_before_any_writes(self):
        for inline in (False, True):
            with self.subTest(inline=inline):
                self.hooks(inline=inline)
                before = {p: Path(p).read_bytes() for p in (self.config_path, self.hooks_path) if os.path.exists(p)}
                r = self.up()  # Claude coordinator, Codex in a tier order
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("1 untrusted in " + (self.config_path if inline else self.hooks_path), r.stdout)
                self.assertIn("run codex once on the host", r.stdout)
                self.assertFalse(os.path.exists(self.state))
                self.assertFalse(os.path.exists(os.path.join(self.project_dir, ".claude")))
                self.assertEqual([c for c in self.calls() if c[0] != "has-session"], [])
                self.assertEqual({p: Path(p).read_bytes() for p in before}, before)
                if os.path.exists(self.hooks_path):
                    os.remove(self.hooks_path)

    def test_stored_trust_passes_without_recomputing_or_writing(self):
        for inline in (False, True):
            with self.subTest(inline=inline):
                self.hooks(trusted=True, inline=inline)
                before = Path(self.config_path).read_bytes()
                self.assertEqual(self.up().returncode, 0)
                self.assertEqual(Path(self.config_path).read_bytes(), before)
                self.crew("down", "--project", self.project)
                if os.path.exists(self.hooks_path):
                    os.remove(self.hooks_path)

    def claude_only_profile(self):
        with open(self.project, "a") as f:
            for tier in ("trivial", "default", "deep"):
                f.write('\n[engines.%s]\norder = ["claude-code/sonnet"]\n' % tier)
        text = Path(self.project).read_text().replace('[engines]\n', '[engines]\nfallback_engine = "claude-code"\n')
        Path(self.project).write_text(text)

    def test_no_codex_profile_skips_host_hooks(self):
        self.hooks()
        self.claude_only_profile()
        self.assertEqual(self.up().returncode, 0)

    def test_coordinator_and_fallback_codex_are_checked(self):
        self.hooks()
        self.claude_only_profile()
        original = Path(self.project).read_text()
        for key in ("coordinator", "fallback_engine"):
            with self.subTest(key=key):
                Path(self.project).write_text(original.replace(key + ' = "claude-code"', key + ' = "codex"'))
                self.assertEqual(self.up().returncode, 1)
                self.assertFalse(os.path.exists(self.state))

    def test_every_hook_index_and_event_is_checked(self):
        self.hooks(trusted=True)
        Path(self.hooks_path).write_text(json.dumps({"hooks": {
            "SessionStart": [{"hooks": [{"command": "trusted"}, {"command": "new-handler"}]},
                             {"hooks": [{"command": "new-group"}]}],
            "PreToolUse": [{"hooks": [{"command": "new-event"}]}]}}))
        r = self.up()
        self.assertEqual(r.returncode, 1)
        self.assertIn("3 untrusted in " + self.hooks_path, r.stdout)

    def test_existing_session_is_unchanged(self):
        self.assertEqual(self.up().returncode, 0)
        self.hooks()
        self.assertEqual(self.up().returncode, 0)
        self.assertEqual(len([c for c in self.calls() if c[0] == "new-session"]), 1)


class UpLiveness(LivenessBase):
    def test_up_rebuilds_ash_from_disk_without_respawning_runs(self):
        rec = self.record("ben-7")
        self.crew("down", "--project", self.project)
        self.put("runs/ben-7.json", json.dumps(rec))
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded runs now probe missing: ben-7", r.stdout)
        self.assertEqual(len(self.windows()), 1)  # only the original spawn, no respawn


if __name__ == "__main__":
    unittest.main()
