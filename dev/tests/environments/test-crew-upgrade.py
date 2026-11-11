"""Upgrade tests: fake-host CLI install transitions and in-flight/reload checks without live sessions."""
from argparse import Namespace
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import CREW

spec = importlib.util.spec_from_file_location("bootstrap_tests", Path(__file__).with_name("test-crew-bootstrap.py"))
bootstrap_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap_tests)
# The extensionless CLI uses the source loader.
spec = importlib.util.spec_from_loader("crew_cli", SourceFileLoader("crew_cli", CREW))
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
upgrade = cli.commands()["upgrade"]


class Upgrade(bootstrap_tests.Bootstrap):
    share_bundle = False  # edits its bundle

    def test_reload_cursor_coordinator_preserves_harness(self):
        values = {"engines.coordinator": "cursor", "runtime.options.permission_mode": "bypass"}
        with mock.patch.object(upgrade, "runs", return_value=[]), \
                mock.patch.object(cli.commands()["lead"], "records", return_value=[]), \
                mock.patch.object(upgrade, "stop_pane", return_value=None), \
                mock.patch.object(upgrade, "window_env", return_value={}), \
                mock.patch.object(upgrade, "role_notes", return_value=""), \
                mock.patch.object(upgrade.tmux.backends["tmux"], "tmux", return_value=Namespace(returncode=0)) as respawn, \
                mock.patch.object(upgrade, "wait_harness") as wait:
            upgrade.reload(values, "session", self.state, Namespace(project=self.project, timeout=1), [(0, "ash")])
        self.assertIn('exec cursor-agent --force "Read your brief at $CREW_BRIEF and follow it."', respawn.call_args_list[1].args[-1])
        wait.assert_called_once_with("session", 0, "ash", "cursor-agent", 1)

    def test_reload_pi_coordinator_preserves_harness(self):
        values = {"engines.coordinator": "pi", "runtime.options.permission_mode": "bypass"}
        with mock.patch.object(upgrade, "runs", return_value=[]), \
                mock.patch.object(cli.commands()["lead"], "records", return_value=[]), \
                mock.patch.object(upgrade, "stop_pane", return_value=None), \
                mock.patch.object(upgrade, "window_env", return_value={}), \
                mock.patch.object(upgrade, "role_notes", return_value=""), \
                mock.patch.object(upgrade.tmux.backends["tmux"], "tmux", return_value=Namespace(returncode=0)) as respawn, \
                mock.patch.object(upgrade, "wait_harness") as wait:
            upgrade.reload(values, "session", self.state, Namespace(project=self.project, timeout=1), [(0, "ash")])
        self.assertIn('exec pi --approve "Read your brief at $CREW_BRIEF and follow it."', respawn.call_args_list[1].args[-1])
        wait.assert_called_once_with("session", 0, "ash", "pi", 1)

    def setUp(self):
        super().setUp()
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        result = self.bootstrap("--yes", "--harness", "codex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def upgrade(self, *args):
        return subprocess.run([sys.executable, str(self.cli), "upgrade", "--project", self.project, *args],
                              input="", capture_output=True, text=True, env=self.env)

    def test_no_change_writes_nothing(self):
        before = self.manifest.stat().st_mtime_ns
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no changes", result.stdout)
        self.assertEqual(self.manifest.stat().st_mtime_ns, before)
        self.assertEqual(self.calls(), [])

    def test_rules_changed_preview_and_apply(self):
        source = self.bundle / "templates/runtimes/tmux/builder.md"
        source.write_text(source.read_text() + "\nNew reviewed rule.\n")
        before = self.manifest.read_bytes()
        result = self.upgrade("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("+New reviewed rule.", result.stdout)
        self.assertEqual(self.manifest.read_bytes(), before)
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("New reviewed rule.", (Path(self.state) / "render/runtime/builder.md").read_text())

    def test_core_memory_near_its_limits_upgrades_and_deploys(self):  # #1230 review R1
        memory = Path(self.project).parent / "memory"
        (memory / "roles").mkdir(parents=True)
        (memory / "owner.md").write_text("# Owner\n\n" + "A" * 2980 + "\n")
        (memory / "roles/coordinator.md").write_text("# C\n\n" + "B" * 1990 + "\n")
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("exceeds", result.stdout)
        brief = (Path(self.state) / "render/runtime/coordinator.md").read_text()
        self.assertIn("\n## Core memory\n", brief)
        self.assertIn("B" * 1990, brief)

    def test_pin_changed_with_same_rules(self):
        (self.bundle / "VERSION").write_text("v2.2.0\n")
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.manifest.read_text())["tag"], "v2.2.0")

    def test_pack_version_only_change_updates_record(self):
        self.pack_version("0.5.0")
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        self.assertIn("crew upgrade: no changes", self.upgrade("--yes").stdout)
        self.pack_version("0.6.0")
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("no changes", result.stdout)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["pack"]), ("v2.1.0", {"name": "github", "version": "0.6.0"}))
        self.assertIn("no changes", self.upgrade("--yes").stdout)

    def test_pack_toml_framework_and_commit_pin(self):
        """#1236: install records the pack.toml pack's commit; upgrade re-plans on a new commit and refuses a dirty
        checkout or a framework range that excludes the installed tag."""
        pack = Path(self.tmp) / "plugin-pack"
        shutil.copytree(Path(__file__).resolve().parents[1] / "core/fixtures/packs/example", pack)

        def commit(framework):
            text = (pack / "pack.toml").read_text()
            (pack / "pack.toml").write_text(re.sub(r'framework = ".*"', 'framework = "%s"' % framework, text))
            git = ["git", "-C", str(pack), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run(git + ["init", "-q"], check=True)
            subprocess.run(git + ["add", "-A"], check=True)
            subprocess.run(git + ["commit", "-qm", framework], check=True)
            return subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        head = commit(">=2.0.0, <3.0.0")
        self.project_path.write_text(self.project_path.read_text() +
                                     'pack = "%s"\n' % os.path.relpath(pack, self.project_path.parent))
        result = self.bootstrap("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.manifest.read_text())["pack"], {
            "name": "example", "version": "0.1.0", "framework": ">=2.0.0, <3.0.0", "commit": head})
        self.assertIn("no changes", self.upgrade("--yes").stdout)
        head = commit(">=2.1.0, <3.0.0")
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.manifest.read_text())["pack"]["commit"], head)
        (pack / "profile.toml").write_text("")
        result = self.upgrade("--dry-run")
        self.assertEqual(result.returncode, 1)
        self.assertIn("has uncommitted changes", result.stdout + result.stderr)
        before = self.manifest.read_bytes()
        commit(">=3.0.0")
        result = self.upgrade("--dry-run")
        self.assertEqual(result.returncode, 1)
        self.assertIn("pack example supports mdstack >=3.0.0; v2.1.0 is incompatible", result.stdout + result.stderr)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_pack_toml_declared_vcs_commit_pin(self):
        """#1326: a pack in a non-git working copy pins through its declared [vcs] commands; a dirty one is refused."""
        pack = Path(self.tmp) / "vcs-pack"
        shutil.copytree(Path(__file__).resolve().parents[1] / "core/fixtures/packs/example", pack)
        fake = [sys.executable, str(Path(__file__).resolve().parents[1] / "core/fixtures/vcs/fake-vcs.py")]
        text = re.sub(r'framework = ".*"', 'framework = ">=2.0.0, <3.0.0"', (pack / "pack.toml").read_text())
        (pack / "pack.toml").write_text(text + "\n[vcs]\nclean = %s\ncommit = %s\n" % (
            json.dumps(fake + ["status"]), json.dumps(fake + ["rev"])))
        subprocess.run(fake + ["commit"], cwd=pack, check=True)
        rev = json.loads((pack / ".fakevcs/state.json").read_text())["rev"]
        self.project_path.write_text(self.project_path.read_text() +
                                     'pack = "%s"\n' % os.path.relpath(pack, self.project_path.parent))
        result = self.bootstrap("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.manifest.read_text())["pack"]["commit"], rev)
        (pack / "profile.toml").write_text("")
        result = self.upgrade("--dry-run")
        self.assertEqual(result.returncode, 1)
        self.assertIn("has uncommitted changes", result.stdout + result.stderr)

    mirror_release = bootstrap_tests.ReleaseSources.mirror_release
    source = bootstrap_tests.ReleaseSources.source

    def test_source_change_without_version_is_refused(self):
        before = self.manifest.read_bytes()
        mirror = Path(self.tmp) / "mirror"
        self.source("mirror", mirror)
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("install source changed to mirror %s; this bundle was not fetched from it" % mirror, result.stdout)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_version_fetch_from_mirror_records_transport_then_no_changes(self):
        self.mirror, self.gh_log = Path(self.tmp) / "mirror", Path(self.tmp) / "gh.log"
        destination, sha = self.mirror_release()
        self.source("mirror", self.mirror)
        result = self.upgrade("--version", "v2.2.0", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["bundle_sha256"], record["transport"]["kind"]), ("v2.2.0", sha, "mirror"))
        self.cli = destination / "cli/mdstack"
        self.assertIn("crew upgrade: no changes", self.upgrade("--yes").stdout)
        self.assertFalse(self.gh_log.exists())

    def test_version_after_dry_run_reuses_verified_bundle_and_records_transport(self):
        """#1089: --dry-run leaves the bundle extracted; --yes and later retries re-verify it and keep provenance."""
        self.mirror, self.gh_log = Path(self.tmp) / "mirror", Path(self.tmp) / "gh.log"
        destination, sha = self.mirror_release()
        self.source("mirror", self.mirror)
        result = self.upgrade("--version", "v2.2.0", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(destination.is_dir())
        (destination / "scripts/__pycache__").mkdir(exist_ok=True)
        (destination / "scripts/__pycache__/x.pyc").write_bytes(b"cache")
        result = self.upgrade("--version", "v2.2.0", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("reusing matching %s" % destination.resolve(), result.stdout)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["bundle_sha256"], record["transport"]["kind"]), ("v2.2.0", sha, "mirror"))
        # A record that lost its provenance (the old direct-run hint) is repaired by --version, not looped.
        del record["transport"]
        record["bundle_sha256"] = None
        self.manifest.write_text(json.dumps(record))
        self.cli = destination / "cli/mdstack"
        self.assertIn("install source changed to mirror", self.upgrade("--dry-run").stdout)
        result = self.upgrade("--version", "v2.2.0", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["bundle_sha256"], record["transport"]["kind"]), (sha, "mirror"))
        self.assertIn("crew upgrade: no changes", self.upgrade("--yes").stdout)
        self.assertFalse(list(Path(self.tmp).glob(".crew-refetch-*")))
        self.assertFalse(self.gh_log.exists())

    def test_upgrade_deploys_without_harness_pointers(self):
        record = json.loads(self.manifest.read_text())
        record["harnesses"] = []
        record["targets"] = {p: sha for p, sha in record["targets"].items()
                             if not Path(p).is_relative_to(Path(self.state) / "render")}
        self.manifest.write_text(json.dumps(record))
        (self.bundle / "VERSION").write_text("v2.2.0\n")
        source = self.bundle / "templates/runtimes/tmux/builder.md"
        source.write_text(source.read_text() + "\nNew reviewed rule.\n")
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.manifest.read_text())["self_test"]["deploy"], "ok")
        self.assertIn("New reviewed rule.", (Path(self.state) / "render/runtime/builder.md").read_text())

    def test_session_profile_applies_without_tmux(self):  # #1541
        record = json.loads(self.manifest.read_text())
        record["harnesses"] = []
        self.manifest.write_text(json.dumps(record))
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "session"'))
        result = self.bootstrap("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.tool("tmux", 'case "$1" in -L|-S) shift 2;; esac; case "$1" in list-windows) echo "10 ben-7";; esac')
        source = self.bundle / "templates/runtimes/session/builder.md"
        source.write_text(source.read_text() + "\nNew reviewed rule.\n")
        before = self.manifest.read_bytes()
        result = self.upgrade("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("+New reviewed rule.", result.stdout)
        self.assertEqual(self.manifest.read_bytes(), before)
        result = self.upgrade("--yes", "--wait-timeout", "0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("in-flight", result.stdout)
        self.assertIn("session runtime: restart the coordinator", result.stdout)
        self.assertIn("New reviewed rule.", (Path(self.tmp) / "live/runtime/builder.md").read_text())
        self.assertEqual(json.loads(self.manifest.read_text())["runtime"], "session")
        self.assertIn("no changes", self.upgrade("--yes").stdout)

    def test_inflight_timeout_leaves_install_untouched(self):
        (self.bundle / "VERSION").write_text("v2.2.0\n")
        self.tool("tmux", 'case "$1" in -L|-S) shift 2;; esac; case "$1" in list-windows) echo "10 ben-7";; esac')
        before = self.manifest.read_bytes()
        result = self.upgrade("--yes", "--wait-timeout", "0")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("in-flight pass ben-7", result.stdout)
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_waits_then_applies_and_reloads(self):
        args = Namespace(project=self.project, org_profile=None, version=None, dev=False, pre=False,
                         uninstall=False, remove_labels=False, routines_removed=False, smoke=False,
                         dry_run=False, yes=True, wait_timeout=5, timeout=1)
        bootstrap = cli.commands()["bootstrap"]
        values, _ = cli.crew_render.resolve(self.project, None)
        with mock.patch.object(upgrade, "profile", return_value=(values, "session", self.state)), \
                mock.patch.object(upgrade, "require_ownership", return_value=True), \
                mock.patch.object(bootstrap, "source", return_value="v2.2.0"), \
                mock.patch.object(bootstrap, "run", return_value=0) as apply, \
                mock.patch.object(upgrade, "busy", side_effect=["ben-7", None]) as busy, \
                mock.patch.object(upgrade, "reload") as reload, \
                mock.patch.object(upgrade.time, "sleep") as sleep, \
                mock.patch.object(cli.commands()["down"], "stop_watcher", return_value=None) as stop, \
                mock.patch.object(cli.commands()["up"], "watcher") as start, \
                mock.patch.dict(os.environ, self.env):
            calls = mock.Mock()
            calls.attach_mock(stop, "stop"), calls.attach_mock(reload, "reload"), calls.attach_mock(start, "start")
            self.assertEqual(upgrade.run(args), 0)
            self.assertEqual(busy.call_count, 2)
            sleep.assert_called_once_with(0.2)
            self.assertEqual(apply.call_count, 2)
            reload.assert_called_once()
            # #1346: the watcher is stopped before the install and started again after the reload
            self.assertEqual([c[0] for c in calls.mock_calls], ["stop", "reload", "start"])
            apply.reset_mock(), start.reset_mock()
            stop.return_value = 4242
            busy.side_effect = [None]
            self.assertEqual(upgrade.run(args), 1)  # a watcher outliving its grace: nothing installed
            self.assertEqual(apply.call_count, 1)  # the dry run only
            start.assert_not_called()

    def test_upgrade_stops_a_lock_holding_watcher_whose_pid_file_was_lost(self):  # #1346 review R2
        wake = Path(self.state) / "wake"
        wake.mkdir(parents=True, exist_ok=True)
        code = ("import fcntl, os, sys, time\nf = open(sys.argv[1], 'w')\nfcntl.flock(f, fcntl.LOCK_EX)\n"
                "f.write('%d\\n' % os.getpid()); f.flush()\nprint('ready', flush=True)\ntime.sleep(60)\n")
        holder = subprocess.Popen([sys.executable, "-c", code, str(wake / "watcher.lock"), "watch"],
                                  stdout=subprocess.PIPE, text=True)  # a watcher with no wake/watcher.pid
        self.addCleanup(lambda: holder.poll() is None and holder.kill())
        self.assertEqual(holder.stdout.readline(), "ready\n")
        args = Namespace(project=self.project, org_profile=None, version=None, dev=False, pre=False,
                         uninstall=False, remove_labels=False, routines_removed=False, smoke=False,
                         dry_run=False, yes=True, wait_timeout=5, timeout=1)
        bootstrap = cli.commands()["bootstrap"]
        values, _ = cli.crew_render.resolve(self.project, None)
        installs = []

        def apply(a):
            installs.append(a.dry_run or holder.poll())  # the real install runs only once the watcher exited
            return 0
        with mock.patch.object(upgrade, "profile", return_value=(values, "session", self.state)), \
                mock.patch.object(upgrade, "require_ownership", return_value=True), \
                mock.patch.object(bootstrap, "source", return_value="v2.2.0"), \
                mock.patch.object(bootstrap, "run", side_effect=apply), \
                mock.patch.object(upgrade, "busy", return_value=None), \
                mock.patch.object(upgrade, "reload"), \
                mock.patch.object(cli.commands()["up"], "watcher"), \
                mock.patch.dict(os.environ, dict(self.env, PATH=self.env["PATH"] + os.pathsep + "/bin")):  # ps
            self.assertEqual(upgrade.run(args), 0)
        self.assertEqual(installs, [True, -15])  # the dry run, then the install after SIGTERM

    def test_active_pane_waits_after_terminal_status(self):
        self.put("status/ben-7.status", "done: #7 #9 head\n")
        with mock.patch.object(upgrade, "runs", return_value=[("ben-7", {"role": "builder"})]), \
                mock.patch.object(cli.commands()["lead"], "records", return_value=[]), \
                mock.patch.object(upgrade.tmux, "pane", return_value={"pid": "123", "command": "claude"}), \
                mock.patch.object(upgrade.proc, "live_child", return_value=False):
            for screen in ("✽ Recombobulating… (5s · ↓ 159 tokens)", "Working (esc to interrupt)"):
                with mock.patch.object(upgrade.tmux, "capture", return_value=screen):
                    self.assertEqual(upgrade.busy(self.state, "session", [(10, "ben-7")]), "ben-7")

    def test_reload_keeps_metadata_and_coordinator_last(self):
        state = Path(self.state)
        brief = state / "runs/ben-7.brief.md"
        brief.parent.mkdir(exist_ok=True)
        brief.write_text("Old rule\n\n## This run\n\n- Worktree: kept\n")
        rec = dict(role="builder", index=10, worktree=self.project_dir, engine="codex", model="gpt-6.1-sol",
                   effort="medium", claim="kept", restarts=1)
        values = {"engines.coordinator": "claude-code", "runtime.options.permission_mode": "safe"}
        with mock.patch.object(upgrade, "runs", return_value=[("ben-7", rec)]), \
                mock.patch.object(cli.commands()["lead"], "records", return_value=[]), \
                mock.patch.object(upgrade, "stop_pane", return_value=None), \
                mock.patch.object(upgrade, "window_env", return_value={}), \
                mock.patch.object(upgrade, "identity", return_value={"pane_id": "%new"}), \
                mock.patch.object(upgrade, "role_notes", return_value=""), \
                mock.patch.object(upgrade.tmux.backends["tmux"], "tmux", return_value=Namespace(returncode=0)) as respawn, \
                mock.patch.object(upgrade, "wait_harness"), \
                mock.patch.object(upgrade.tmux.backends["tmux"], "server", return_value=[]):  # the shim pins -S
            upgrade.reload(values, "session", self.state, Namespace(project=self.project, timeout=1),
                           [(0, "ash"), (10, "ben-7")])
        self.assertEqual([c.args[3] for c in respawn.call_args_list if c.args[0] == "respawn-window"],
                         ["=session:10", "=session:0"])
        self.assertEqual([c.args[:5] for c in respawn.call_args_list if c.args[0] == "set-option"][:2],
                         [("set-option", "-w", "-t", "=session:10", "remain-on-exit"),
                          ("set-option", "-w", "-u", "-t", "=session:10")])
        self.assertIn("## This run\n\n- Worktree: kept", brief.read_text())
        saved = json.loads((state / "runs/ben-7.json").read_text())
        self.assertEqual((saved["claim"], saved["restarts"], saved["pane_id"]), ("kept", 1, "%new"))

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_reload_on_real_tmux_keeps_the_window(self):
        sock, shim = Path(self.tmp) / "tmux.sock", Path(self.tmp) / "real-tmux"
        shim.mkdir()
        (shim / "tmux").write_text('#!/bin/sh\nexec %s -f /dev/null -S %s "$@"\n' % (shutil.which("tmux"), sock))
        (shim / "tmux").chmod(0o755)
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        env["PATH"] = "%s:%s" % (shim, env["PATH"])
        brief = Path(self.state) / "runs/ben-7.brief.md"
        brief.parent.mkdir(exist_ok=True)
        brief.write_text("Old rule\n\n## This run\n\n- Worktree: kept\n")
        rec = dict(role="builder", index=1, worktree=self.project_dir, engine="codex", model="m", effort="e")
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(upgrade, "runs", return_value=[("ben-7", rec)]), \
                mock.patch.object(cli.commands()["lead"], "records", return_value=[]), \
                mock.patch.object(upgrade, "window_env", return_value={}), \
                mock.patch.object(upgrade, "role_notes", return_value=""), \
                mock.patch.object(upgrade, "harness", return_value=["sleep", "300"]), \
                mock.patch.object(upgrade, "LAUNCH", "exec %s #%s"), \
                mock.patch.object(upgrade, "wait_harness"), \
                mock.patch.object(upgrade.tmux.backends["tmux"], "server", return_value=[]):  # the shim pins -S
            self.addCleanup(subprocess.run, [str(shim / "tmux"), "kill-server"], capture_output=True)
            tmux = upgrade.tmux.tmux
            self.assertEqual(tmux("new-session", "-d", "-s", "s", "sleep 300").returncode, 0)
            self.assertEqual(tmux("new-window", "-d", "-t", "=s:1", "-n", "ben-7", "exec sleep 300").returncode, 0)
            before = upgrade.tmux.pane("s", 1)["pid"]
            upgrade.reload({"runtime.options.permission_mode": "safe"}, "s", self.state,
                           Namespace(project=self.project, timeout=1), [(1, "ben-7")])
            self.assertIn((1, "ben-7"), upgrade.tmux.list_windows("s"))
            self.assertNotEqual(upgrade.tmux.pane("s", 1)["pid"], before)
            self.assertEqual(tmux("show-options", "-w", "-v", "-t", "=s:1", "remain-on-exit").stdout, "")


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(Upgrade(name) for name in Upgrade.__dict__ if name.startswith("test_"))


def evidence():
    fixture = Upgrade()
    fixture.setUp()
    try:
        print("create: bootstrap --yes --harness codex; exit 0; installed v2.1.0")
        result = fixture.upgrade("--yes")
        assert result.returncode == 0 and "no changes" in result.stdout
        print("upgrade --yes: exit 0; crew upgrade: no changes")
        source = fixture.bundle / "templates/runtimes/tmux/builder.md"
        source.write_text(source.read_text() + "\nNew reviewed rule.\n")
        result = fixture.upgrade("--dry-run")
        assert result.returncode == 0 and "+New reviewed rule." in result.stdout
        print("upgrade --dry-run: exit 0; +New reviewed rule.; install unchanged")
        result = fixture.upgrade("--yes")
        assert result.returncode == 0
        assert "New reviewed rule." in (Path(fixture.state) / "render/runtime/builder.md").read_text()
        print("upgrade --yes: exit 0; changed rule deployed; install self-test ok")
        (fixture.bundle / "VERSION").write_text("v2.2.0\n")
        fixture.tool("tmux", 'case "$1" in list-windows) echo "10 ben-7";; esac')
        before = fixture.manifest.read_bytes()
        result = fixture.upgrade("--yes", "--wait-timeout", "0")
        assert result.returncode == 1 and fixture.manifest.read_bytes() == before
        print("upgrade --yes --wait-timeout 0: exit 1; in-flight pass ben-7; install unchanged")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, install, state and fake host removed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--evidence"]:
        evidence()
    else:
        unittest.main()
