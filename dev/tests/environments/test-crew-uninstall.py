"""Offline offboarding tests: dry-run, confirmation, holds, archive, target protection, labels and unlanded work.

Run with --evidence for a deterministic bootstrap/install/offboard transcript. All tools and repositories are fixtures.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import unittest

spec = importlib.util.spec_from_file_location("bootstrap_tests", Path(__file__).with_name("test-crew-bootstrap.py"))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class Uninstall(fixtures.doctor_tests.DoctorBase):
    bootstrap = fixtures.Bootstrap.bootstrap
    real_git = fixtures.Bootstrap.real_git

    def setUp(self):
        super().setUp()
        self.bundle = Path(self.tmp) / "eng-crew-v2.1.0"
        for name in ("scripts", "cli", "core", "environments", "harnesses", "connectors", "profiles", "templates",
                     "packs", "roles", "docs"):
            shutil.copytree(fixtures.HERE.parent / name, self.bundle / name)
        (self.bundle / "VERSION").write_text("v2.1.0\n")
        self.project_path = Path(self.project)
        self.project_path.write_text(self.project_path.read_text() +
                                     'eng_crew = "%s/eng-crew"\nlive_dir = "%s/live"\n' % (self.state, self.tmp))
        self.cli = self.bundle / "scripts" / "crew"
        self.manifest = Path(self.state) / "install.json"
        self.real_git()
        os.symlink(sys.executable, Path(self.bindir) / "python3")
        self.tool("git-upload-pack", 'exec "%s" upload-pack "$@"' % shutil.which("git"))
        subprocess.run(["git", "init", "-q", "-b", "main", self.project_dir], check=True)
        result = self.bootstrap("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        Path(self.log).unlink(missing_ok=True)
        self.gh_log = Path(self.tmp) / "gh-calls.jsonl"
        self.doctor_gh = (Path(self.bindir) / "gh").read_bytes()
        self.tool("gh", "")
        (Path(self.bindir) / "gh").write_text("#!" + sys.executable + '''
import json, sys
from pathlib import Path
a = sys.argv[1:]
with Path(''' + repr(str(self.gh_log)) + ''').open('a') as f:
    f.write(json.dumps(a) + '\\n')
if a[:2] == ['pr', 'list']:
    print(json.dumps([dict(number=7, labels=[dict(name='crew:in-review')], body=''),
                      dict(number=8, labels=[], body='<!-- crew:v1 role=builder issue=8 -->'),
                      dict(number=9, labels=[], body='ordinary PR')]))
elif a[:2] == ['issue', 'list']:
    print('[{"number": 10}]')
elif a[:2] == ['label', 'list']:
    print('[{"name":"crew:ready"},{"name":"crew:hold"},{"name":"bug"}]')
''')
        (Path(self.state) / "wiring.md").write_text("routine IDs and removal history\n")
        (Path(self.state) / "evidence.txt").write_text("installation evidence\n")

    def uninstall(self, *flags):
        return self.bootstrap("--uninstall", *flags)

    def mutations(self):
        return [a for a in map(json.loads, self.gh_log.read_text().splitlines()) if a[1] != "list"]

    def archive(self):
        return next(Path(self.state).parent.glob(Path(self.state).name + ".offboarded-*"))

    def test_preview_and_confirmation_do_not_mutate(self):
        for flags, code in ((("--dry-run",), 0), ((), 1)):
            result = self.uninstall(*flags)
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
            self.assertTrue(self.manifest.exists())
            self.assertEqual(self.mutations(), [])
        self.assertEqual(self.calls(), [])

    def test_apply_pauses_archives_and_preserves_edited_targets(self):
        (Path(self.state) / "VERSION").write_text("owner edit\n")
        result = self.uninstall("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        archive = self.archive()
        self.assertFalse(Path(self.state).exists())
        self.assertEqual((archive / "VERSION").read_text(), "owner edit\n")
        self.assertFalse((archive / "crew.toml").exists())
        self.assertFalse((archive / "eng-crew").is_symlink())
        self.assertTrue((archive / "wiring.md").exists())
        self.assertTrue((archive / "evidence.txt").exists())
        self.assertTrue(self.bundle.exists())
        record = json.loads((archive / "install.json").read_text())
        self.assertEqual(record["status"], "offboarded")
        self.assertEqual(record["offboarding"]["paused_prs"], [7, 8])
        self.assertEqual([a[:3] for a in self.mutations()],
                         [["pr", "edit", "7"], ["pr", "edit", "8"], ["issue", "edit", "10"]])
        self.assertNotIn(".crew/", (Path(self.project_dir) / ".git/info/exclude").read_text().splitlines())

    def test_harness_and_registry_targets_leave_with_their_anchored_excludes(self):
        fixtures.HarnessTargets.registry(self, fixtures.HarnessTargets.REGISTRY, fixtures.HarnessTargets.FILES)
        uninstall_gh = (Path(self.bindir) / "gh").read_bytes()
        (Path(self.bindir) / "gh").write_bytes(self.doctor_gh)
        result = self.bootstrap("--harness", "claude-code", "--harness", "codex", "--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (Path(self.bindir) / "gh").write_bytes(uninstall_gh)
        exclude = Path(self.project_dir) / ".git/info/exclude"
        pointers = json.loads(self.manifest.read_text())["harness_pointers"]
        self.assertEqual(len(pointers), 3)
        anchored = [line for line in exclude.read_text().splitlines() if line.startswith("/")]
        self.assertEqual(len(anchored), 8)
        result = self.uninstall("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in pointers:
            self.assertFalse(Path(path).exists())
        self.assertFalse(list((Path(self.project_dir) / ".claude").rglob("*.md")))
        self.assertEqual([line for line in exclude.read_text().splitlines() if line.startswith("/")], [])

    def test_tracked_target_and_work_output_are_kept(self):
        target = Path(self.project_dir) / "pointer.md"
        target.write_text("tracked pointer\n")
        subprocess.run(["git", "-C", self.project_dir, "add", target.name], check=True)
        record = json.loads(self.manifest.read_text())
        import hashlib
        record["targets"][str(target)] = hashlib.sha256(target.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(record))
        (Path(self.project_dir) / ".crew").mkdir()
        self.assertEqual(self.uninstall("--yes").returncode, 0)
        self.assertTrue(target.exists())
        self.assertIn(".crew/", (Path(self.project_dir) / ".git/info/exclude").read_text().splitlines())

    def test_label_removal_is_explicit_and_namespace_only(self):
        self.assertEqual(self.uninstall("--yes", "--remove-labels").returncode, 0)
        self.assertEqual([a[:3] for a in self.mutations() if a[0] == "label"],
                         [["label", "delete", "crew:ready"], ["label", "delete", "crew:hold"]])

    def test_stop_keeps_run_evidence_for_archive(self):
        Path(self.state_file).write_text(json.dumps({"crew-acme-widgets": {"0": "ash", "10": "ben-7"}}))
        runs = Path(self.state) / "runs"
        runs.mkdir()
        (runs / "ben-7.json").write_text(json.dumps(dict(item="issue #7")))
        (runs / "ben-7.body.md").write_text("runtime evidence\n")
        result = self.uninstall("--yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.archive() / "runs/ben-7.body.md").read_text(), "runtime evidence\n")
        self.assertIn("kill-session", [a[0] for a in self.calls()])
        self.assertNotIn("kill-window", [a[0] for a in self.calls()])

    def test_grok_waits_for_routine_removal(self):
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"'))
        shutil.rmtree(Path(self.project_dir) / ".git")
        record = json.loads(self.manifest.read_text())
        record["runtime"] = "grok-bot"
        self.manifest.write_text(json.dumps(record))
        result = self.uninstall("--yes")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--routines-removed", result.stderr)
        self.assertTrue(self.manifest.exists())
        self.assertEqual(self.uninstall("--yes", "--routines-removed").returncode, 0)

    def test_pushed_unmerged_work_blocks_cleanup_even_without_session(self):
        argv = ["git", "-C", self.project_dir, "-c", "user.name=t", "-c", "user.email=t"]
        subprocess.run(argv + ["commit", "-q", "--allow-empty", "-m", "base"], check=True)
        remote = str(Path(self.tmp) / "remote.git")
        subprocess.run(["git", "clone", "-q", "--bare", self.project_dir, remote], check=True)
        subprocess.run(argv + ["remote", "add", "origin", remote], check=True)
        subprocess.run(argv + ["checkout", "-q", "-b", "builder/7"], check=True)
        subprocess.run(argv + ["commit", "-q", "--allow-empty", "-m", "unmerged"], check=True)
        subprocess.run(argv + ["push", "-q", "origin", "builder/7"], check=True)
        runs = Path(self.state) / "runs"
        runs.mkdir()
        (runs / "ben-7.json").write_text(json.dumps(dict(worktree=self.project_dir)))
        result = self.uninstall("--yes")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("unlanded work retained", result.stderr)
        self.assertTrue(self.manifest.exists())
        self.assertTrue((Path(self.state) / "eng-crew").is_symlink())
        self.assertTrue(Path(self.project_dir).exists())


def evidence():
    fixture = Uninstall()
    fixture.setUp()
    try:
        print("create: bootstrap --yes exit 0; v2.1.0 installed")
        result = fixture.uninstall("--dry-run")
        assert result.returncode == 0 and fixture.manifest.exists() and not fixture.mutations()
        print("preview: uninstall --dry-run exit 0; install retained; no mutations")
        result = fixture.uninstall("--yes")
        assert result.returncode == 0 and not Path(fixture.state).exists()
        archive = fixture.archive()
        assert (archive / "wiring.md").exists() and (archive / "evidence.txt").exists()
        assert not (archive / "crew.toml").exists() and not (archive / "eng-crew").is_symlink()
        print("delete: uninstall --yes exit 0; holds on PRs 7/8 and issue 10; owned targets removed")
        print("archive: offboarded record, wiring and evidence kept; bundle and labels kept")
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    if sys.argv[1:] == ["--evidence"]:
        evidence()
    else:
        unittest.main()
