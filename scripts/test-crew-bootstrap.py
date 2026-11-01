"""Offline bootstrap tests on a fake host and extracted bundle, including dry-run, confirmation, failures,
tmux record/idempotency, Grok Bot deployment, protected targets and clone version selection. Run in CI.
Use --evidence for a deterministic install/verify/delete CLI transcript, with temporary paths scrubbed.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("doctor_tests", HERE / "test-crew-doctor.py")
doctor_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor_tests)


class Bootstrap(doctor_tests.DoctorBase):
    def setUp(self):
        super().setUp()
        self.bundle = Path(self.tmp) / "eng-crew-v2.1.0"
        for name in ("scripts", "profiles", "templates", "packs"):
            shutil.copytree(HERE.parent / name, self.bundle / name)
        (self.bundle / "VERSION").write_text("v2.1.0\n")
        self.project_path = Path(self.project)
        self.project_path.write_text(self.project_path.read_text() +
                                     'eng_crew = "%s/eng-crew"\nlive_dir = "%s/live"\n' % (self.state, self.tmp))
        self.cli = self.bundle / "scripts" / "crew"
        self.manifest = Path(self.state) / "install.json"
        self.tool("git", 'case "$1" in --version) echo 1.0;; *) exit 1;; esac')

    def bootstrap(self, *args):
        return subprocess.run([sys.executable, str(self.cli), "bootstrap", "--project", self.project, *args],
                              input="", capture_output=True, text=True, env=self.env)

    def test_dry_run_and_confirmation_leave_no_install(self):
        r = self.bootstrap("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for text in ("Plan: v2.1.0 (tmux)", "Render preview:", "Human step:", "no install written"):
            self.assertIn(text, r.stdout)
        self.assertIn("render/runtime/coordinator.md (planned)", r.stdout)
        self.assertFalse(self.manifest.exists())
        self.assertFalse((Path(self.state) / "eng-crew").exists())
        r = self.bootstrap()
        self.assertEqual(r.returncode, 1)
        self.assertIn("confirmation required", r.stderr)
        self.assertFalse(self.manifest.exists())

    def test_apply_records_and_reruns_without_starting_tmux(self):
        # Real git is used only for .git/info/exclude and tracked-file checks.
        os.remove(Path(self.bindir) / "git")
        os.symlink(shutil.which("git"), Path(self.bindir) / "git")
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        for _ in range(2):
            r = self.bootstrap("--yes")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["runtime"], record["status"]), ("v2.1.0", "tmux", "installed"))
        self.assertEqual((Path(self.state) / "VERSION").read_text(), "v2.1.0\n")
        self.assertEqual((Path(self.state) / "crew.toml").read_text(), self.project_path.read_text())
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), self.bundle.resolve())
        self.assertFalse((Path(self.state) / "render").exists())
        self.assertEqual((Path(self.project_dir) / ".git/info/exclude").read_text().count(".crew/"), 1)
        self.assertEqual(self.calls(), [])

    def test_grok_deploys_and_refuses_edited_targets(self):
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"'))
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        live = Path(self.tmp) / "live"
        files = list(live.rglob("*.md"))
        self.assertTrue(files)
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        files[0].write_text("owner edit\n")
        before = self.manifest.read_text()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("target edited or unowned", r.stderr)
        self.assertEqual(files[0].read_text(), "owner edit\n")
        self.assertEqual(self.manifest.read_text(), before)

    def test_failures_do_not_write_install(self):
        for version in (None, "v2.2.0-rc.1"):
            path = self.bundle / "VERSION"
            if version is None:
                path.unlink()
            else:
                path.write_text(version)
            self.assertEqual(self.bootstrap("--yes").returncode, 1)
            self.assertFalse(self.manifest.exists())
        (self.bundle / "VERSION").write_text("v2.1.0\n")
        os.remove(Path(self.bindir) / "claude")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Plan:", r.stdout)
        self.assertFalse(self.manifest.exists())

    def test_placeholder_and_resolve_failures(self):
        self.project_path.write_text(self.project_path.read_text().replace('eng_crew = "' + self.state + '/eng-crew"',
                                                                         'eng_crew = "<eng-crew>"'))
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("placeholder", r.stderr)
        self.project_path.write_text("[repo]\nowner = 1\n")
        self.assertEqual(self.bootstrap("--yes").returncode, 1)
        self.assertFalse(self.manifest.exists())

    def real_git(self):
        os.remove(Path(self.bindir) / "git")
        os.symlink(shutil.which("git"), Path(self.bindir) / "git")

    def test_clone_requires_exact_stable_tag_or_explicit_dev(self):
        self.real_git()
        argv = ["git", "-C", str(self.bundle), "-c", "user.name=t", "-c", "user.email=t"]
        for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "base"]):
            subprocess.run(argv + args, check=True)
        self.assertEqual(self.bootstrap("--dry-run").returncode, 1)
        sha = subprocess.check_output(argv + ["rev-parse", "HEAD"], text=True).strip()
        r = self.bootstrap("--dev", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Plan: " + sha, r.stdout)
        subprocess.run(argv + ["tag", "v2.1.0"], check=True)
        self.assertEqual(self.bootstrap("--dry-run").returncode, 0)

    def test_missing_state_layout_fails_before_plan(self):
        shutil.rmtree(Path(self.state) / "inbox")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("fail  state dir", r.stdout)
        self.assertNotIn("Plan:", r.stdout)
        self.assertFalse((Path(self.state) / "inbox").exists())
        self.assertFalse(self.manifest.exists())

    def test_tracked_target_is_not_overwritten(self):
        self.real_git()
        live = Path(self.tmp) / "live"
        live.mkdir()
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"'))
        subprocess.run(["git", "init", "-q", str(live)], check=True)
        target = live / "runtime" / "builder-b1.md"
        target.parent.mkdir()
        target.write_text("tracked owner content\n")
        subprocess.run(["git", "-C", str(live), "add", "runtime/builder-b1.md"], check=True)
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(target.read_text(), "tracked owner content\n")
        self.assertFalse(self.manifest.exists())


class HarnessTargets(Bootstrap):
    def setUp(self):
        super().setUp()
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.claude = Path(self.project_dir) / ".claude"
        self.exclude = Path(self.project_dir) / ".git/info/exclude"

    def test_harness_plan_and_repeat_install(self):
        before = self.exclude.read_text()
        flags = ("--harness", "claude-code", "--harness", "codex")
        r = self.bootstrap(*flags, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew-coordinator/SKILL.md (planned)", r.stdout)
        self.assertIn("Codex launch", r.stdout)
        self.assertIn('trust_level="trusted"', r.stdout)
        self.assertFalse(self.claude.exists())
        self.assertFalse((Path(self.state) / "render").exists())
        self.assertEqual(self.exclude.read_text(), before)
        r = self.bootstrap(*flags, "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        files = list(self.claude.rglob("*"))
        files = [p for p in files if p.is_file()]
        self.assertEqual(len(files), 5)
        for path in files:
            self.assertIn(str(path), record["targets"])
            self.assertIn("/" + str(path.relative_to(self.project_dir)), self.exclude.read_text().splitlines())
            if path.suffix == ".md":
                pointer = path.read_text().split("Read your brief at ")[1].split(" and follow it.")[0]
                self.assertTrue(Path(pointer).is_file())
                self.assertLess(len(path.read_text().splitlines()), 9)
        self.assertIn("runtime/coordinator.md", record["launches"][0])
        settings = json.loads((self.claude / "settings.local.json").read_text())
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        before = {p: p.read_bytes() for p in files}
        excluded = self.exclude.read_text()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(self.manifest.read_text()), record)
        self.assertEqual({p: p.read_bytes() for p in files}, before)
        self.assertEqual(self.exclude.read_text(), excluded)
        self.assertEqual(self.calls(), [])

    def test_codex_installs_no_project_files(self):
        before = {p: p.read_bytes() for p in Path(self.home).rglob("*") if p.is_file()}
        for name in ("AGENTS.md", "CLAUDE.md"):
            (Path(self.project_dir) / name).write_text("owner instructions\n")
        subprocess.run(["git", "-C", self.project_dir, "add", "AGENTS.md", "CLAUDE.md"], check=True)
        r = self.bootstrap("--harness", "codex", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.claude.exists())
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertEqual((Path(self.project_dir) / name).read_text(), "owner instructions\n")
        self.assertEqual({p: p.read_bytes() for p in Path(self.home).rglob("*") if p.is_file()}, before)
        self.assertTrue((Path(self.state) / "render/runtime/coordinator.md").is_file())

    def test_tracked_edited_and_symlink_targets_are_preserved(self):
        target = self.claude / "agents/crew-builder.md"
        target.parent.mkdir(parents=True)
        target.write_text("tracked\n")
        subprocess.run(["git", "-C", self.project_dir, "add", str(target)], check=True)
        for flags in (("--dry-run",), ("--yes",)):
            r = self.bootstrap("--harness", "claude-code", *flags)
            self.assertEqual(r.returncode, 1)
            self.assertEqual(target.read_text(), "tracked\n")
            self.assertFalse(self.manifest.exists())
        subprocess.run(["git", "-C", self.project_dir, "rm", "-f", str(target)], check=True,
                       capture_output=True)
        target.parent.parent.mkdir(parents=True, exist_ok=True)
        target.parent.symlink_to(self.home, target_is_directory=True)
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("symlink", r.stderr)
        self.assertFalse((Path(self.home) / target.name).exists())
        target.parent.unlink()
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        target.write_text("owner edit\n")
        before = self.manifest.read_text()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("target edited or unowned", r.stderr)
        self.assertEqual(target.read_text(), "owner edit\n")
        self.assertEqual(self.manifest.read_text(), before)

    def test_harness_requires_role_render(self):
        self.project_path.write_text(self.project_path.read_text().replace('name = "tmux"', 'name = "grok-bot"'))
        r = self.bootstrap("--harness", "claude-code", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("session binding", r.stderr)
        self.assertFalse(self.claude.exists())


def evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        fixture.real_git()
        subprocess.run(["git", "init", "-q", fixture.project_dir], check=True)
        for flags in (("--dry-run",), ("--yes",), ("--yes",)):
            result = fixture.bootstrap(*flags)
            assert result.returncode == 0, result.stdout + result.stderr
            if flags == ("--dry-run",):
                assert not fixture.manifest.exists()
            print("crew bootstrap %s: exit %d" % (" ".join(flags), result.returncode))
            print(result.stdout.splitlines()[-1].replace(str(fixture.manifest), "<state>/install.json"))
        record = json.loads(fixture.manifest.read_text())
        assert record["tag"] == "v2.1.0" and record["status"] == "installed"
        assert (Path(fixture.state) / "crew.toml").read_text() == fixture.project_path.read_text()
        assert (Path(fixture.state) / "eng-crew").resolve() == fixture.bundle.resolve()
        print("record: v2.1.0 tmux installed; profile copy and bundle link verified")
        (Path(fixture.state) / "VERSION").write_text("owner edit\n")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 1 and "target edited or unowned" in result.stderr
        assert (Path(fixture.state) / "VERSION").read_text() == "owner edit\n"
        print("crew bootstrap --yes after owner edit: exit 1; edit preserved")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, install and bundle removed")
    fixture = HarnessTargets()
    fixture.setUp()
    try:
        flags = ("--harness", "claude-code", "--harness", "codex")
        result = fixture.bootstrap(*flags, "--dry-run")
        assert result.returncode == 0 and not fixture.claude.exists(), result.stdout + result.stderr
        print("harness dry-run: exit 0; no pointers or render written")
        result = fixture.bootstrap(*flags, "--yes")
        assert result.returncode == 0, result.stdout + result.stderr
        record = json.loads(fixture.manifest.read_text())
        pointers = [p for p in fixture.claude.rglob("*.md")]
        for path in pointers:
            brief = path.read_text().split("Read your brief at ")[1].split(" and follow it.")[0]
            assert Path(brief).is_file()
            assert str(path) in record["targets"]
            assert "/" + str(path.relative_to(fixture.project_dir)) in fixture.exclude.read_text().splitlines()
        assert len(pointers) == 4 and len(record["launches"]) == 1
        print("harness apply: exit 0; 3 subagents + coordinator skill resolve to deployed briefs")
        print("record: all 5 Claude targets hash-recorded and excluded; Codex launch carries pointer + trust")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 0 and json.loads(fixture.manifest.read_text()) == record
        print("harness repeat: exit 0; same manifest, no duplicate hook or excludes")
        pointers[0].write_text("owner edit\n")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 1 and pointers[0].read_text() == "owner edit\n"
        print("harness owner edit: exit 1; edit and manifest preserved")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary harness pointers, project, render and bundle removed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--evidence"]:
        evidence()
    else:
        unittest.main()
