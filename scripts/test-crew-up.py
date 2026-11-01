"""Tests for crew up, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: session created, engine command, brief path (default inputs give the tmux briefs
from `templates/`), Stop hook install, idempotent, other runtime refused, a pre-trusted
Codex coordinator (projects table: the project dir and a linked worktree's repo root),
`CREW_BIN`, `CREW_PROJECT` and the sandbox variable in window 0, no render chatter,
rebuilding `ash` from disk without respawning runs. Run in CI.
"""
import json
import os
import shlex
import subprocess
import unittest
from crew_testlib import Base, CREW, LivenessBase


class Up(Base):
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


class UpLiveness(LivenessBase):
    def test_up_rebuilds_ash_from_disk_without_respawning_runs(self):
        self.crew("down", "--project", self.project)
        self.put("runs/ben-7.json", json.dumps({"index": 10, "role": "builder", "item": "issue #7"}))
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded runs now probe missing: ben-7", r.stdout)
        self.assertEqual(len(self.windows()), 1)  # only the original spawn, no respawn


if __name__ == "__main__":
    unittest.main()
