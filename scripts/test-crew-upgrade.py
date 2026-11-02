"""Upgrade tests: fake-host CLI install transitions and in-flight/reload checks without live sessions."""
from argparse import Namespace
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
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

    def test_pin_changed_with_same_rules(self):
        (self.bundle / "VERSION").write_text("v2.2.0\n")
        result = self.upgrade("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.manifest.read_text())["tag"], "v2.2.0")

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

    def test_inflight_timeout_leaves_install_untouched(self):
        (self.bundle / "VERSION").write_text("v2.2.0\n")
        self.tool("tmux", 'case "$1" in list-windows) echo "10 ben-7";; esac')
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
                mock.patch.dict(os.environ, self.env):
            self.assertEqual(upgrade.run(args), 0)
            self.assertEqual(busy.call_count, 2)
            sleep.assert_called_once_with(0.2)
            self.assertEqual(apply.call_count, 2)
            reload.assert_called_once()

    def test_active_pane_waits_after_terminal_status(self):
        self.put("status/ben-7.status", "done: #7 #9 head\n")
        with mock.patch.object(upgrade, "runs", return_value=[("ben-7", {"role": "builder"})]), \
                mock.patch.object(cli.commands()["lead"], "records", return_value=[]), \
                mock.patch.object(upgrade.tmux, "pane", return_value={"pid": "123", "command": "claude"}), \
                mock.patch.object(upgrade.tmux, "live_child", return_value=False):
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
                mock.patch.object(upgrade.tmux, "tmux", return_value=Namespace(returncode=0)) as respawn, \
                mock.patch.object(upgrade, "wait_harness"):
            upgrade.reload(values, "session", self.state, Namespace(project=self.project, timeout=1),
                           [(0, "ash"), (10, "ben-7")])
        self.assertEqual([c.args[3] for c in respawn.call_args_list], ["=session:10", "=session:0"])
        self.assertIn("## This run\n\n- Worktree: kept", brief.read_text())
        saved = json.loads((state / "runs/ben-7.json").read_text())
        self.assertEqual((saved["claim"], saved["restarts"], saved["pane_id"]), ("kept", 1, "%new"))


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
