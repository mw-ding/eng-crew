"""Tests for crew up, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: session created, engine command, brief path (default inputs give the tmux briefs
from `templates/`), Stop hook install, idempotent, other runtime refused, a pre-trusted
Codex coordinator (projects table: the project dir and a linked worktree's repo root),
`CREW_BIN`, `CREW_PROJECT` and the sandbox variable in window 0, no render chatter,
rebuilding `ash` from disk without respawning runs, the crew's own tmux server (#818: `-L <session>`, a pre-#818
session kept on the default server named by path, never an inherited $TMUX, and a stopped lead orphaned by a lost server, never another process), and `crew up --team` (one session and coordinator for every
repo of a team file, a render per repo under the team state root), and the #606 launch topology (hosted or no
role windows, preflight-only coordinator, resume, schema refusals, the pack ownership read). Run in CI.
"""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, CREW, SCRIPTS, INPUTS, LivenessBase, write_pack


class Up(Base):
    def test_cursor_coordinator_uses_pointer_and_no_model_override(self):
        self.write_profile(engine="cursor")
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('exec cursor-agent --force "Read your brief at $CREW_BRIEF and follow it."', self.new_session()[-1])
        self.assertFalse(os.path.exists(os.path.join(self.project_dir, ".claude")))

    def test_cursor_coordinator_refuses_safe_and_auto_without_session(self):
        for mode in ("safe", "auto"):
            self.write_profile(engine="cursor")
            with open(self.project, "a") as f:
                f.write('\n[runtime.options]\npermission_mode = "%s"\n' % mode)
            r = self.up()
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("Cursor supports only permission_mode=bypass", r.stdout)
            self.assertFalse(any(c[0] == "new-session" for c in self.calls()))

    def test_pi_coordinator_uses_pointer_and_no_model_override(self):
        self.write_profile(engine="pi")
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('exec pi --approve "Read your brief at $CREW_BRIEF and follow it."', self.new_session()[-1])
        self.assertFalse(os.path.exists(os.path.join(self.project_dir, ".claude")))

    def test_pi_coordinator_refuses_safe_and_auto_without_session(self):
        for mode in ("safe", "auto"):
            self.write_profile(engine="pi")
            with open(self.project, "a") as f:
                f.write('\n[runtime.options]\npermission_mode = "%s"\n' % mode)
            r = self.up()
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("Pi supports only permission_mode=bypass", r.stdout)
            self.assertFalse(any(c[0] == "new-session" for c in self.calls()))

    def test_coordinator_runtime_notes_and_missing_file(self):
        with open(self.project, "a") as f:
            f.write('\n[runtime.options.notes]\ncoordinator = ["policy.md"]\n')
        r = self.up()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("cannot read runtime.options.notes.coordinator file policy.md", r.stdout)
        self.assertFalse(any(c[0] == "new-session" for c in self.calls()))
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, "policy.md"), "w") as f:
            f.write("coordinator policy\n")
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.state, "render", "briefs", "coordinator.md")) as f:
            self.assertTrue(f.read().endswith("\n## Runtime note: policy.md\n\ncoordinator policy\n"))

    def test_up_renders_pack_overlay(self):
        write_pack(os.path.join(self.tmp, "pack"))
        with open(self.project, "a") as f:
            f.write('pack = "../pack"\n')
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.state, "render", "runtime", "solo.md")) as f:
            self.assertTrue(f.read().endswith("\nPack rule.\n"))

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

    def test_up_through_link_keeps_one_guard_and_repoints_stale_ones(self):
        """#1088: a guard from an older bundle is re-pointed, and crew up through the eng-crew link leaves the file
        byte-identical, so bootstrap's target hash still matches."""
        stale = "python3 /old/eng-crew-9.9.8/scripts/crew guard --state " + self.state
        other_state = "python3 /old/eng-crew-9.9.8/scripts/crew guard --state /elsewhere"
        os.makedirs(os.path.join(self.project_dir, ".claude"))
        with open(os.path.join(self.project_dir, ".claude", "settings.local.json"), "w") as f:
            json.dump({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": stale}]},
                                          {"hooks": [{"type": "command", "command": other_state}]},
                                          {"hooks": [{"type": "command", "command": stale.replace("9.9.8", "9.9.9")},
                                                     {"type": "command", "command": "other"}]}]}}, f)
        self.assertEqual(self.up().returncode, 0)
        guard = shlex.join(["python3", os.path.realpath(CREW), "guard", "--state", self.state])
        commands = [[h["command"] for h in e["hooks"]] for e in self.settings()["hooks"]["Stop"]]
        self.assertEqual(commands, [[guard], [other_state], ["other"]])
        path = os.path.join(self.project_dir, ".claude", "settings.local.json")
        before = Path(path).read_bytes()
        link = os.path.join(self.tmp, "eng-crew")
        os.symlink(os.path.dirname(os.path.dirname(os.path.realpath(CREW))), link)
        self.crew("down", "--project", self.project)
        r = subprocess.run([sys.executable, os.path.join(link, "scripts", "crew"), "up", "--project", self.project,
                            "--inputs", INPUTS], input="", capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(Path(path).read_bytes(), before)

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

    def launch(self, table):
        with open(self.project, "a") as f:
            f.write("\n[runtime.options.launch]\n" + table + "\n")

    def test_hosted_roles_open_only_the_tagged_coordinator(self):
        """#606: roles = hosted (or --coordinator-only) starts window 0 tagged as today and no lead windows."""
        r = self.crew("up", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        baseline = self.calls()
        self.assertTrue(any(c[0] == "new-window" for c in baseline))  # today: lead windows
        self.crew("down", "--project", self.project)
        for args, table in ((["--coordinator-only"], ""), ([], 'roles = "hosted"'), ([], 'roles = "none"')):
            with self.subTest(args=args, table=table):
                self.write_profile()
                self.launch(table)
                os.remove(self.log)
                r = self.crew("up", "--project", self.project, *args)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("started no role windows", r.stdout)
                self.assertFalse(any(c[0] == "new-window" for c in self.calls()), self.calls())
                self.assertEqual(self.new_session(), [c for c in baseline if c[0] == "new-session"][0])
                self.crew("down", "--project", self.project)

    def test_coordinator_none_is_preflight_only(self):
        self.launch('coordinator = "none"\nroles = "hosted"')
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("launch.coordinator = none, so no session started", r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.state, "render", "briefs", "coordinator.md")))
        self.assertEqual([c for c in self.calls() if c[0] != "has-session"], [])
        self.assertFalse(os.path.exists(os.path.join(self.project_dir, ".claude")))

    def test_resume_session_id_and_ask(self):
        cases = [("claude-code", "abc-123", 'exec claude --resume abc-123 "Read your brief at $CREW_BRIEF and follow it."'),
                 ("claude-code", "ask", "exec claude --resume"),
                 ("codex", "abc-123", ' resume abc-123 "Read your brief at $CREW_BRIEF and follow it."'),
                 ("codex", "ask", " resume")]
        for engine, resume, expected in cases:
            with self.subTest(engine=engine, resume=resume):
                self.write_profile(engine=engine)
                self.launch('resume = "%s"' % resume)
                if os.path.exists(self.log):
                    os.remove(self.log)
                self.assertEqual(self.up().returncode, 0)
                launch = self.new_session()[-1]
                if resume == "ask":
                    self.assertTrue(launch.endswith(expected), launch)
                    self.assertNotIn("Read your brief", launch)
                else:
                    self.assertIn(expected, launch)
                self.crew("down", "--project", self.project)

    def test_resume_refused_for_other_engines_before_any_writes(self):
        self.write_profile(engine="pi")
        self.launch('resume = "ask"')
        r = self.up()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("launch.resume needs a claude-code or codex coordinator, not pi", r.stdout)
        self.assertFalse(os.path.exists(self.state))

    def test_launch_schema_refuses_bad_values(self):
        for table, expected in (('roles = "remote"', "launch.roles: unknown value 'remote'"),
                                ('coordinator = "none"', "launch.roles: roles = tmux needs coordinator = tmux"),
                                ('resume = "a b"', "launch.resume: expected fresh, ask or a session id"),
                                ('reconcile = "github"', "launch.reconcile: unknown value 'github'"),
                                ('extra = 1', "launch.extra: unknown key")):
            with self.subTest(table=table):
                self.write_profile()
                self.launch(table)
                r = self.up()
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(expected, r.stdout)
                self.assertEqual(self.calls(), [])


class PackOwnershipRead(Base):
    """#606 AC4: a non-GitHub markers backend's control-item read uses its rendered `markers.read-item`
    binding, never `gh api`; an unreadable or unbound read stays fail-closed (read-only)."""

    def setUp(self):
        super().setUp()
        pack = Path(self.project_dir) / "pack"
        pack.mkdir()
        manifest = Path(os.path.dirname(CREW), "..", "packs", "github", "manifest.toml").read_text()
        (pack / "manifest.toml").write_text(manifest.replace('name = "github"', 'name = "example"').replace(
            "[pack]\n", '[pack]\neng_crew_version = "v1.0.0"\n'))
        (pack / "profile.toml").write_text('[backends.markers]\nname = "example"\n')
        text = Path(self.project).read_text().replace('name = "tmux"', 'name = "tmux"\ninstance = "local"').replace(
            'name = "widgets"', 'name = "widgets"\ncontrol_item = 123\n')
        Path(self.project).write_text(text + '\npack = "pack"\n')
        self.inputs = Path(self.tmp) / "inputs"
        shutil.copytree(Path(os.path.dirname(CREW), "..", "templates"), self.inputs)
        self.log_dir = Path(self.tmp) / "reads"
        self.log_dir.mkdir()
        self.env["READ_LOG"] = str(self.log_dir)
        for name in ("gh", "example-cli"):
            code = "1" if name == "gh" else "${EXAMPLE_EXIT:-0}"  # example-cli prints no markers: ownership active
            Path(self.tmp, "bin", name).write_text('#!/bin/sh\necho "$*" >> "$READ_LOG/%s"\n[ %s = 0 ] && echo "[]"\n'
                                                   'exit %s\n' % (name, code, code))
            os.chmod(Path(self.tmp, "bin", name), 0o755)

    def mapping(self, read_item=True):
        """The GitHub map as the example backend's, with read-item bound to example-cli (or unbound)."""
        text = (self.inputs / "backends" / "github.toml").read_text()
        line = next(ln for ln in text.splitlines() if ln.startswith("read-item = "))
        (self.inputs / "backends" / "example.toml").write_text(text.replace(line + "\n", (
            'read-item = "example-cli item comments <n> --repo <owner>/<repo> --with-author"\n' if read_item else "")))

    def reads(self, name):
        path = self.log_dir / name
        return path.read_text().splitlines() if path.exists() else []

    def test_read_item_goes_through_the_pack_binding(self):
        self.mapping()
        r = self.crew("up", "--project", self.project, "--inputs", str(self.inputs))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.reads("gh"), [])
        self.assertIn("item comments 123 --repo acme/widgets --with-author", self.reads("example-cli"))
        self.assertTrue(any(c[0] == "new-window" for c in self.calls()))  # ownership active: leads start
        bindings = json.loads(Path(self.tmp, "state", "acme__widgets", "render", "bindings.json").read_text())
        self.assertEqual(bindings, {  # #937: write-item is recorded beside read-item, unfilled
            "markers.read-item": "example-cli item comments <n> --repo <owner>/<repo> --with-author",
            "markers.write-item": "gh issue comment <n> --body-file <file>"})
        self.assertEqual(self.crew("ownership", "--project", self.project).returncode, 0)

    def test_native_tracker_records_the_handoff_live_reads(self):
        """#937: a non-GitHub tracker and change backend also record crew handoff's live reads; an unmapped one
        is left out and named."""
        self.mapping()
        pack = Path(self.project_dir) / "pack"
        (pack / "profile.toml").write_text('[backends.markers]\nname = "example"\n[backends.tracker]\nname = "example"\n'
                                           '[backends.change]\nname = "example"\n')
        r = self.crew("up", "--project", self.project, "--inputs", str(self.inputs))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew: ownership change.read-branch-head unbound", r.stdout)
        self.assertIn("crew: ownership tracker.unlabel unbound", r.stdout)
        path = Path(self.tmp, "state", "acme__widgets", "render", "bindings.json")
        self.assertEqual(sorted(json.loads(path.read_text())), [
            "change.list-open", "change.read-head", "markers.read", "markers.read-item", "markers.write-item",
            "tracker.list-items"])
        self.crew("down", "--project", self.project)
        manifest = (pack / "manifest.toml").read_text()
        (pack / "manifest.toml").write_text(manifest.replace("[capabilities.change]\n",
                                                             '[capabilities.change]\nread-branch-head = "supported"\n'))
        example = self.inputs / "backends" / "example.toml"
        example.write_text(example.read_text().replace("[change]\n", '[change]\nread-branch-head = "example-cli branch '
                                                                      'head <branch>"\n'))
        r = self.crew("up", "--project", self.project, "--inputs", str(self.inputs))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(path.read_text())["change.read-branch-head"], "example-cli branch head <branch>")
        self.assertEqual(self.reads("gh"), [])

    def test_pack_render_overlay_map_supplies_the_read(self):
        """#580 overlay: the pack's render/backends/example.toml binds the read with the shipped inputs."""
        self.mapping()
        overlay = Path(self.project_dir) / "pack" / "render" / "backends"
        overlay.mkdir(parents=True)
        (self.inputs / "backends" / "example.toml").rename(overlay / "example.toml")
        r = self.crew("up", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("item comments 123 --repo acme/widgets --with-author", self.reads("example-cli"))
        self.assertEqual(self.reads("gh"), [])

    def test_failed_or_unbound_read_is_read_only(self):
        for read_item, exit_code in ((True, "1"), (False, "0")):
            with self.subTest(read_item=read_item):
                self.mapping(read_item)
                if os.path.exists(self.log):
                    os.remove(self.log)
                r = self.crew("up", "--project", self.project, "--inputs", str(self.inputs), EXAMPLE_EXIT=exit_code)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("ownership: read-only; refusing start", r.stdout)
                if not read_item:
                    self.assertIn("ownership read unbound", r.stdout)
                self.assertFalse(any(c[0] == "new-window" for c in self.calls()))
                self.assertEqual(self.reads("gh"), [])
                self.crew("down", "--project", self.project)

    def test_team_records_the_binding_for_every_repo(self):
        """#606 AC4 with --team: each repo's ownership read uses the pack binding after startup."""
        self.mapping()
        with open(Path(self.project_dir) / "pack" / "profile.toml", "a") as f:
            f.write("\n[repo]\ncontrol_item = 123\n")
        team = Path(self.project_dir) / "ext.toml"
        team.write_text('[team]\naccounts = { all = "acme-bot", reviewer = "acme-reviewer" }\n'
                        '[team.runtime]\nname = "tmux"\ninstance = "local"\n'
                        '[team.paths]\npack = "%s"\nstate_dir = "%s"\nworktree_root = "%s/wt"\n'
                        '[team.identities]\nowners = ["acme-owner"]\n'
                        '[repos.widgets]\nrepo = "acme/widgets"\n[repos.gadgets]\nrepo = "acme/gadgets"\n'
                        % (Path(self.project_dir) / "pack", Path(self.tmp) / "state", Path(self.tmp) / "state"))
        r = self.crew("up", "--team", str(team), "--inputs", str(self.inputs))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for repo in ("widgets", "gadgets"):
            r = self.crew("ownership", "--project", "%s#%s" % (team, repo))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("item comments 123 --repo acme/%s --with-author" % repo, self.reads("example-cli"))
        self.assertEqual(self.reads("gh"), [])


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


class TeamUp(Base):
    def write_team(self):
        team = os.path.join(self.project_dir, "teams", "ext.toml")
        os.makedirs(os.path.dirname(team))
        with open(team, "w") as f:
            f.write('[team]\npersonas = { builder = "Ben" }\naccounts = { all = "acme-bot", reviewer = "acme-reviewer" }\n'
                    '[team.runtime]\nname = "tmux"\n[team.identities]\nowners = ["acme-owner"]\n'
                    '[team.paths]\nstate_dir = "%s"\nworktree_root = "%s/wt"\ntoolchain_bin = "/opt/node/bin"\n'
                    '[repos.widgets]\nrepo = "acme/widgets"\n[repos.gadgets]\nrepo = "acme/gadgets"\ntrain_window = 120\n'
                    % ((os.path.join(self.tmp, "state"),) * 2))
        return team

    def test_team_up_starts_one_instance_for_every_repo(self):
        team = self.write_team()
        r = self.crew("up", "--team", team, "--inputs", INPUTS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        root = os.path.join(self.tmp, "state", "ext")
        call = self.new_session()
        self.assertEqual((call[call.index("-s") + 1], call[call.index("-c") + 1]), ("crew-team-ext", os.path.dirname(team)))
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual((env["CREW_STATE"], env["CREW_TEAM"], env["CREW_PROJECT"], env["CREW_BRIEF"]),
                         (root, team, team + "#widgets", os.path.join(root, "coordinator.md")))
        with open(env["CREW_BRIEF"]) as f:
            brief = f.read()
        for repo in ("widgets", "gadgets"):
            state = os.path.join(root, "acme__" + repo)
            rendered = os.path.join(state, "render", "briefs", "coordinator.md")  # fixture inputs render briefs/
            self.assertIn("| acme/%s | `%s#%s` | `%s` | `%s` |" % (repo, team, repo, state, rendered), brief)
            with open(rendered) as f:
                self.assertIn("acme/" + repo, f.read())
        with open(os.path.join(os.path.dirname(team), ".claude", "settings.local.json")) as f:
            guards = [h["command"] for e in json.load(f)["hooks"]["Stop"] for h in e["hooks"]]
        self.assertEqual([g.rsplit(" ", 1)[1] for g in guards],
                         [os.path.join(root, "acme__widgets"), os.path.join(root, "acme__gadgets")])
        r = self.crew("up", "--team", team, "--inputs", INPUTS)
        self.assertEqual(r.returncode, 0)
        self.assertIn("crew-team-ext already running", r.stdout)
        self.new_session()

    def test_team_coordinator_none_is_preflight_only(self):
        """#606: launch.coordinator = none renders every repo and starts no session or Stop hook in team mode too."""
        team = self.write_team()
        with open(team, "a") as f:
            f.write('\n[team.runtime.options.launch]\ncoordinator = "none"\nroles = "hosted"\n')
        r = self.crew("up", "--team", team, "--inputs", INPUTS)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("launch.coordinator = none, so no session started", r.stdout)
        for repo in ("widgets", "gadgets"):
            self.assertTrue(os.path.isfile(os.path.join(self.tmp, "state", "ext", "acme__" + repo, "render", "briefs",
                                                        "coordinator.md")))
        self.assertEqual([c for c in self.calls() if c[0] != "has-session"], [])
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(team), ".claude")))

    def test_team_up_refuses_a_legacy_profile_or_a_bad_repo(self):
        r = self.crew("up", "--team", self.project, "--inputs", INPUTS)
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not a team file", r.stdout)
        team = self.write_team()
        with open(team, "a") as f:
            f.write("builders = 9\n")
        r = self.crew("up", "--team", team, "--inputs", INPUTS)
        self.assertEqual(r.returncode, 1)
        self.assertIn("ext.toml:repos.gadgets.builders: not allowed in a repo section", r.stdout)
        self.assertEqual(self.calls(), [])


class UpLiveness(LivenessBase):
    def test_up_rebuilds_ash_from_disk_without_respawning_runs(self):
        rec = self.record("ben-7")
        self.crew("down", "--project", self.project)
        self.put("runs/ben-7.json", json.dumps(rec))
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded runs now probe missing: ben-7", r.stdout)
        self.assertEqual(len(self.windows()), 1)  # only the original spawn, no respawn


class OwnServer(Base):
    """#818: every crew tmux call names the crew's own server, so an agent's tmux mistake stays off the owner's."""
    def test_up_puts_every_call_on_the_session_socket(self):
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(self.log + ".sockets") as f:
            sockets = f.read().split()
        default = os.path.join(self.env.get("TMUX_TMPDIR") or "/tmp", "tmux-%d" % os.getuid(), "default")
        self.assertEqual(sockets[1], default)  # the one probe for a pre-#818 session (server()), by path, never $TMUX
        self.assertEqual(set(sockets[:1] + sockets[2:]), {"crew-acme-widgets"})  # the fake logs each -L/-S apart
        bare = ["has-session", "-t", "=crew-acme-widgets"]
        self.assertEqual(len(sockets), len(self.calls()))
        self.assertEqual(self.calls()[:3], [bare, bare, bare])  # server(): own and default probes; has_session
        self.assertIn("attach with: tmux -L crew-acme-widgets attach -t crew-acme-widgets", r.stdout)

    def server(self, lives_on):
        """session.d/tmux.py server() against a fake tmux whose session lives on `own` (-L), the `default` server or none,
        with an inherited $TMUX naming a decoy server; probes show the default socket as DEFAULT."""
        bindir = tempfile.mkdtemp(dir=self.tmp)
        with open(os.path.join(bindir, "tmux"), "w") as f:
            f.write("#!/bin/sh\necho \"$*\" >> %s/probes\ncase \"$1 $LIVES_ON\" in\n"
                    "  '-L own'|'-S default') exit 0 ;;\nesac\nexit 1\n" % bindir)
        os.chmod(os.path.join(bindir, "tmux"), 0o755)
        spec = importlib.util.spec_from_file_location("crew_tmux_818", os.path.join(SCRIPTS, "session.d", "tmux.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.SOCKET = "crew-acme-widgets"
        with mock.patch.dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], LIVES_ON=lives_on,
                             TMUX="/decoy/default,1,0", TMUX_TMPDIR=bindir):
            first, second = mod.server(), mod.server()
        self.assertEqual(first, second)
        default = os.path.join(bindir, "tmux-%d" % os.getuid(), "default")
        with open(os.path.join(bindir, "probes")) as f:
            return [a.replace(default, "DEFAULT") for a in first], f.read().replace(default, "DEFAULT").splitlines()

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_bare_kill_server_in_a_crew_pane_spares_the_owners_default_server(self):
        """The #817/#818 failure: a crew pane's bare `tmux kill-server` took down the owner's server twice."""
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        env["TMUX_TMPDIR"] = self.tmp  # this test's default server, not the developer's
        owner = ["tmux", "-f", os.devnull]
        self.addCleanup(subprocess.run, owner + ["kill-server"], env=env, capture_output=True)
        self.addCleanup(subprocess.run, owner + ["-L", "crew-acme-widgets", "kill-server"], env=env, capture_output=True)
        subprocess.run(owner + ["new-session", "-d", "-s", "owner", "sleep 300"], env=env, check=True)
        spec = importlib.util.spec_from_file_location("crew_tmux_818_live", os.path.join(SCRIPTS, "session.d", "tmux.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.SOCKET = "crew-acme-widgets"
        with mock.patch.dict(os.environ, env, clear=True):
            mod.new_session("crew-acme-widgets", "ash", self.tmp, {}, "tmux kill-server; sleep 300")
            for _ in range(100):
                if not mod.has_session("crew-acme-widgets"):
                    break
                time.sleep(0.05)
            self.assertFalse(mod.has_session("crew-acme-widgets"), "the pane's kill-server ran on the crew server")
        alive = subprocess.run(owner + ["has-session", "-t", "=owner"], env=env, capture_output=True)
        self.assertEqual(alive.returncode, 0, "the owner's default server survived")

    def test_server_is_the_session_socket_unless_a_pre_818_session_runs_on_the_default_server(self):
        own = ["-L", "crew-acme-widgets"]
        probe = "has-session -t =crew-acme-widgets"
        self.assertEqual(self.server("own"), (own, ["-L crew-acme-widgets " + probe]))  # cached: one probe
        self.assertEqual(self.server("none"), (own, ["-L crew-acme-widgets " + probe, "-S DEFAULT " + probe]))
        self.assertEqual(self.server("default"), (["-S", "DEFAULT"],
                                                  ["-L crew-acme-widgets " + probe, "-S DEFAULT " + probe]))

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_inherited_tmux_decoy_is_never_followed(self):
        """Riley's finding 2: a legacy-named session on the server an inherited $TMUX names (here a throwaway decoy)
        is neither chosen nor killed; the crew's calls stay on its own -L server."""
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        env["TMUX_TMPDIR"] = tempfile.mkdtemp(prefix="t818.", dir="/tmp")  # short: socket paths are length-limited
        self.addCleanup(shutil.rmtree, env["TMUX_TMPDIR"], True)
        decoy = os.path.join(env["TMUX_TMPDIR"], "decoy")
        real = ["tmux", "-f", os.devnull]
        self.addCleanup(subprocess.run, real + ["-S", decoy, "kill-server"], env=env, capture_output=True)
        self.addCleanup(subprocess.run, real + ["-L", "crew-acme-widgets", "kill-server"], env=env, capture_output=True)
        subprocess.run(real + ["-S", decoy, "new-session", "-d", "-s", "crew-acme-widgets", "sleep 300"], env=env,
                       check=True)
        pid = subprocess.run(real + ["-S", decoy, "display-message", "-p", "#{pid}"], env=env, capture_output=True,
                             text=True, check=True).stdout.strip()
        spec = importlib.util.spec_from_file_location("crew_tmux_818_decoy", os.path.join(SCRIPTS, "session.d", "tmux.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.SOCKET = "crew-acme-widgets"
        with mock.patch.dict(os.environ, dict(env, TMUX="%s,%s,0" % (decoy, pid)), clear=True):
            self.assertEqual(mod.server(), ["-L", "crew-acme-widgets"])
            self.assertFalse(mod.has_session("crew-acme-widgets"))
            mod.kill_session("crew-acme-widgets")
        alive = subprocess.run(real + ["-S", decoy, "has-session", "-t", "=crew-acme-widgets"], env=env,
                               capture_output=True)
        self.assertEqual(alive.returncode, 0, "the decoy's session survived")


class OrphanLeads(Base):
    """#818: after a server loss, crew up stops a recorded lead whose pane process ignored SIGHUP, and nothing else."""
    def spawn(self, orphan):
        """A real `sleep`: orphaned (its parent exits, so init adopts it) or a child of this test (parent alive)."""
        if orphan:
            out = subprocess.run([sys.executable, "-c", "import subprocess; print(subprocess.Popen(['sleep', '60'], "
                                  "start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).pid)"],
                                 capture_output=True, text=True, check=True).stdout
            pid = int(out)
        else:
            child = subprocess.Popen(["sleep", "60"], start_new_session=True)
            self.addCleanup(child.wait)
            pid = child.pid
        self.addCleanup(lambda: subprocess.run(["kill", "-9", str(pid)], capture_output=True))
        return str(pid)

    def ps(self, field, pid):
        return subprocess.run(["ps", "-o", field + "=", "-p", pid], capture_output=True, text=True).stdout.strip()

    def gone(self, pid):
        for _ in range(100):
            if not self.ps("stat", pid) or self.ps("stat", pid).startswith("Z"):
                return True
            time.sleep(0.05)
        return False

    def lead(self, role, name, pid, start):
        self.put("leads/%s.json" % role, json.dumps(dict(name=name, index=2, role=role + "-lead", harness="sleep",
                                                         restarts=0, pane_id="%2", pane_pid=pid, pane_start=start)))

    def up_coordinator(self):
        r = self.crew("up", "--project", self.project, "--inputs", INPUTS, "--coordinator-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_up_stops_the_recorded_orphaned_lead_but_not_a_reused_pid(self):
        orphan, reused = self.spawn(True), self.spawn(True)
        if self.ps("ppid", orphan) != "1":
            self.skipTest("orphans are adopted by a subreaper here, not init")
        self.lead("builder", "ben-lead", orphan, self.ps("lstart", orphan))
        self.lead("reviewer", "vera-lead", reused, "Mon Jan  1 00:00:00 2001")  # recorded start differs
        out = self.up_coordinator()
        self.assertIn("crew: stopped orphaned lead ben-lead (pid %s" % orphan, out)
        self.assertNotIn("vera-lead", out)
        self.assertTrue(self.gone(orphan))
        self.assertTrue(self.ps("stat", reused))

    def test_up_leaves_a_recorded_lead_whose_parent_is_alive(self):
        child = self.spawn(False)
        self.lead("builder", "ben-lead", child, self.ps("lstart", child))
        self.assertNotIn("ben-lead", self.up_coordinator())
        self.assertTrue(self.ps("stat", child))


if __name__ == "__main__":
    unittest.main()
