"""Harness adapter seam tests (#1182; docs/runtimes/harness-adapters.md#adapter-modules), stdlib only.

A copy of this bundle gets one extra file, harnesses/fake/adapter.py, and nothing else. Against fake binaries the fake
harness is then an engine and coordinator choice, `mdstack up` launches and resumes it as the coordinator, `mdstack spawn`
launches a worker with it, `mdstack upgrade` reloads it, the probe, watcher wake, dialog, transient-error and composer
rules use its declarations, bootstrap installs its pointer, and `mdstack doctor` and remote readiness check its CLI.
The shipped tables keep their order, each shipped adapter's title, CLI, login check and screen rules match its spec
section (#1443), and the contributor-tier check stays in the core; Claude's transient text matches connection loss and the gateway capacity
line, never tool output or quoted text (#1633). Run in CI.
"""
from argparse import ArgumentParser, Namespace
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import SCRIPTS, SpawnBase

FAKE = '''"""Fake harness adapter: test only."""
import re

EXECUTABLE = "fake-agent"
TITLE = "Fake"
LOGIN_STATUS = ["whoami"]
PERMISSION = {"bypass": ["--yes"]}
RESUME = ["--continue"]
PROMPTS = [(r"Allow fake tool\\?$", r"y/n$")]
TRANSIENT = re.compile(r"fake overloaded")
COMPOSER = "»"
INSTALL_TARGETS = [".fake/crew.md"]


def role_argv(model, effort, wt, state, flags):
    return ["fake-agent", *flags, "--model", model, "--effort", effort]


def coordinator_argv(project_dir, state, flags):
    return ["fake-agent", *flags]


def install_targets(project, state, pointer, check):
    path = project.parent / ".fake/crew.md"
    check(path)
    return {path: pointer("coordinator") + "\\n"}
'''
BUNDLE = None


def setUpModule():
    global BUNDLE
    BUNDLE = tempfile.mkdtemp()
    root = os.path.join(BUNDLE, "mdstack")
    shutil.copytree(os.path.dirname(SCRIPTS), root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".crew"))
    os.makedirs(os.path.join(root, "harnesses", "fake"))
    with open(os.path.join(root, "harnesses", "fake", "adapter.py"), "w") as f:
        f.write(FAKE)


def tearDownModule():
    shutil.rmtree(BUNDLE)


def bundle(*parts):
    return os.path.join(BUNDLE, "mdstack", *parts)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cli():
    """The bundle copy's crew CLI, in process (its crew_shared replaces any other in sys.modules)."""
    spec = importlib.util.spec_from_loader("crew_fake_cli", SourceFileLoader("crew_fake_cli", os.path.join(BUNDLE, "mdstack", "cli", "mdstack")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ShippedTables(unittest.TestCase):
    """The shipped adapters derive the tables the schema and commands used to spell out."""

    def test_order_and_aliases(self):
        h = load("crew_harness_shipped", os.path.join(os.path.dirname(SCRIPTS), "harnesses", "crew-harness.py"))
        self.assertEqual(h.ENGINES, ["claude-code", "codex", "muse", "opencode", "pi", "cursor"])
        self.assertEqual(h.LAUNCHABLE, ["claude-code", "codex", "pi", "cursor", "muse"])
        self.assertEqual(h.ENGINE_CMD, {"claude-code": "claude", "codex": "codex", "pi": "pi",
                                        "cursor": "cursor-agent", "muse": "muse"})
        self.assertEqual((h.RESUMABLE, h.INSTALLS, h.LAUNCH_NOTES), (["claude-code", "codex"],) * 2 + (["codex"],))
        self.assertEqual(h.login_status("codex"), ["codex", "login", "status"])
        self.assertEqual(h.login_status("cursor"), ["cursor-agent", "auth", "status"])

    def test_declared_rows_per_shipped_adapter(self):
        """Each shipped adapter's own value, not the union every consumer reads (#1443, A19): its spec heading's title,
        its CLI, its login check (default `auth status`), and Claude Code's and Codex's mid-turn, composer and fatal
        error rules on their documented screens."""
        h = load("crew_harness_rows", os.path.join(os.path.dirname(SCRIPTS), "harnesses", "crew-harness.py"))
        names = {"claude-code": ("Claude Code", "claude"), "codex": ("Codex", "codex"), "pi": ("Pi", "pi"),
                 "cursor": ("Cursor", "cursor-agent"), "muse": ("Muse", "muse"), "opencode": ("OpenCode", "opencode")}
        for engine, (title, cli) in names.items():
            with self.subTest(engine):
                self.assertEqual((h.ADAPTERS[engine].TITLE, h.CLI[engine]), (title, cli))
                self.assertEqual(h.login_status(engine), [cli] + (["login"] if engine == "codex" else ["auth"]) + ["status"])
        claude, codex = h.ADAPTERS["claude-code"], h.ADAPTERS["codex"]
        idle = "❯ \n  ? for shortcuts"
        self.assertTrue(claude.BUSY.search("✽ recombobulating… (5s · ↓ 159 tokens)"))
        self.assertTrue(codex.BUSY.search("• working (12s • esc to interrupt)"))
        self.assertFalse(claude.BUSY.search(idle) or codex.BUSY.search(idle))
        self.assertEqual((claude.COMPOSER, codex.COMPOSER), ("❯", "›"))
        self.assertRegex('⎿  API Error: 400 {"type":"error","error":{}}', claude.FATAL)
        self.assertRegex('■ {"type":"error","status":503,"message":"x"}', codex.FATAL)
        self.assertNotRegex('■ {"type":"error","status":503}', claude.FATAL)
        self.assertNotRegex('⎿  API Error: 400 {"type":"error"}', codex.FATAL)
        for line in ["  ⎿  API Error (529 …) · Retrying in 2 seconds…", "  ⎿  API Error: Connection lost mid-response",
                     "429 The shared model capacity behind AI Gateway is temporarily exhausted upstream",
                     "  ⎿  API Error: 429 The shared model capacity behind AI Gateway is temporarily exhausted upstream"]:
            self.assertRegex(line, claude.TRANSIENT)  # #1633: connection loss and the gateway capacity line
        for line in ["     ⎿  API Error: Connection lost mid-response", "> 429 The shared model capacity is exhausted",
                     "  ⎿  title: API Error: Connection lost mid-response", "• 429 capacity exhausted, quoted"]:
            self.assertNotRegex(line, claude.TRANSIENT)  # tool output, a quoted prompt or issue text (#1366)

    def test_contributor_tier_is_core_policy(self):
        """Muse declares only CONTRIBUTOR_TIER; the core reads visibility and refuses before the adapter runs."""
        shared = cli().harness.__globals__
        values = {"repo.owner": "acme", "repo.name": "widgets"}
        muse = shared["harnesses"].ADAPTERS["muse"]
        with mock.patch.object(muse, "role_argv") as argv, \
                mock.patch.object(shared["subprocess"], "run", return_value=Namespace(returncode=0, stdout='{"private": true}')):
            with self.assertRaisesRegex(RuntimeError, "Muse requires a verified public repository"):
                shared["harness"]("muse", "m", "high", "/wt", "/state", "bypass", values)
        argv.assert_not_called()
        with mock.patch.object(shared["subprocess"], "run", return_value=Namespace(returncode=0, stdout='{"private": false}')):
            self.assertEqual(shared["harness"]("muse", "m", "high", "/wt", "/state", "bypass", values),
                             ["muse", "--yolo", "--model", "m", "--reasoning-effort", "high"])


class FakeHarness(SpawnBase):
    """The fake adapter, added as one file, through spawn, coordinator start, wake, reload, install and readiness."""

    def crew(self, *args, stdin="", **env):
        return subprocess.run([sys.executable, os.path.join(BUNDLE, "mdstack", "cli", "mdstack"), *args], input=stdin, capture_output=True, text=True,
                              env=dict(self.env, **env))

    def setUp(self):
        super().setUp()
        binary = os.path.join(self.tmp, "bin", "fake-agent")
        with open(binary, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(binary, 0o755)

    def test_engine_and_coordinator_choice(self):
        h = load("crew_harness_fake", bundle("harnesses", "crew-harness.py"))
        self.assertEqual(h.ENGINES[-1], "fake")
        self.assertEqual((h.LAUNCHABLE[-1], h.ENGINE_CMD["fake"], h.INSTALLS[-1]), ("fake", "fake-agent", "fake"))
        self.assertIn(".fake/crew.md", h.INSTALL_BUILTINS)
        self.assertEqual(h.login_status("fake"), ["fake-agent", "whoami"])

    def test_up_launches_and_resumes_the_fake_coordinator(self):
        for table, line in (("", 'exec fake-agent --yes "Read your brief at $CREW_BRIEF and follow it."'),
                            ('\n[runtime.options.launch]\nresume = "s-1"\n',
                             'exec fake-agent --yes --continue s-1 "Read your brief at $CREW_BRIEF and follow it."')):
            with self.subTest(table=table):
                self.crew("down", "--project", self.project)
                os.remove(self.log)
                self.write_profile(engine="fake")
                with open(self.project, "a") as f:
                    f.write(table)
                r = self.up()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn(line, self.new_session()[-1])

    def test_spawn_launches_a_worker_on_the_fake_harness(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["fake/f-1", "codex/gpt-6.1-sol"]\n')
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.windows()[-1][-1], 'export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec '
                         'fake-agent --yes --model f-1 --effort medium "Read your brief at $CREW_BRIEF and follow it."')
        self.assertEqual((self.record("ben-7")["engine"], self.record("ben-7")["harness"]), ("fake", "fake-agent"))

    def test_reload_probe_wake_and_screen_rules(self):
        crew = cli()
        upgrade, shared = crew.commands()["upgrade"], crew.commands()["upgrade"].reload.__globals__
        render = Path(self.state) / "render" / "runtime"
        render.mkdir(parents=True, exist_ok=True)
        (render / "coordinator.md").write_text("brief\n")
        values = {"engines.coordinator": "fake", "runtime.options.permission_mode": "bypass"}
        with mock.patch.object(upgrade, "runs", return_value=[]), \
                mock.patch.object(crew.commands()["lead"], "records", return_value=[]), \
                mock.patch.object(upgrade, "stop_pane", return_value=None), \
                mock.patch.object(upgrade, "window_env", return_value={}), \
                mock.patch.object(upgrade, "role_notes", return_value=""), \
                mock.patch.object(upgrade.tmux.backends["tmux"], "tmux", return_value=Namespace(returncode=0)) as respawn, \
                mock.patch.object(upgrade, "wait_harness") as wait:
            upgrade.reload(values, "session", self.state, Namespace(project=self.project, timeout=1), [(0, "ash")])
        self.assertIn('exec fake-agent --yes "Read your brief at $CREW_BRIEF and follow it."',
                      respawn.call_args_list[1].args[-1])
        wait.assert_called_once_with("session", 0, "ash", "fake-agent", 1)
        # Probe and the watcher's coordinator wake: the fake executable in the foreground of window 0.
        self.assertTrue(crew.foreground_matches(crew.ENGINE_CMD.values(), {"zsh", "fake-agent"}))
        with mock.patch.object(shared["tmux"], "capture", return_value="» Allow fake tool?\n  y/n"):
            self.assertTrue(crew.dialog("session", 0))
        self.assertEqual(crew.transient_lines("ok\n  fake overloaded, retrying\n", "fake-agent"),
                         ["fake overloaded, retrying"])
        self.assertEqual(crew.commands()["send"].composer_draft("» inbox: x", (10, 0)), ["inbox: x"])

    def test_bootstrap_doctor_and_remote_readiness(self):
        crew = cli()
        bootstrap = crew.commands()["bootstrap"]
        sub = ArgumentParser().add_subparsers(dest="cmd")
        bootstrap.register(sub)
        self.assertEqual(sub.choices["bootstrap"].parse_args(["--project", "p", "--harness", "fake"]).harness, ["fake"])
        preview, live = Path(self.tmp) / "preview", Path(self.state) / "render"
        (preview / "runtime").mkdir(parents=True)
        (preview / "runtime" / "coordinator.md").write_text("brief\n")
        targets, launches = bootstrap.harness_targets(["fake"], Path(self.project), self.state, live, preview, {},
                                                      crew.commands()["doctor"])
        self.assertEqual(targets, {Path(self.project_dir) / ".fake/crew.md":
                                   "Read your brief at %s and follow it.\n" % (live / "runtime/coordinator.md")})
        self.assertEqual(launches, [])
        with mock.patch.dict(os.environ, self.env):
            rows = crew.commands()["doctor"].engines({"engines.coordinator": "fake",
                                                      "engines.default.order": ["codex/gpt-6.1-sol"]})
        self.assertIn(("ok", "engine fake", "fake-agent", ""), rows)
        remote = load("crew_remote_fake", bundle("environments", "terminal", "remote", "crew-remote.py"))
        with mock.patch.dict(os.environ, self.env):
            reply = remote.check_verb({"project": "acme__widgets", "default_branch": "main", "forge": False,
                                       "capabilities": {"engines": ["fake"]}}, self.tmp)
        self.assertIn("fake-agent", json.dumps(reply["checks"][0]))


if __name__ == "__main__":
    unittest.main()
