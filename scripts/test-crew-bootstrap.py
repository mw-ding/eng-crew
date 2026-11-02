"""Offline bootstrap tests on a fake host and extracted bundle, including dry-run, confirmation, failures,
tmux record/idempotency, Grok Bot deployment, protected targets and clone version selection. Run in CI.
Use --evidence for a deterministic install/verify/delete CLI transcript, with temporary paths scrubbed.
Use --self-test-evidence for post-apply success, failure and opt-in smoke evidence on a fake host.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest import mock

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
        self.assertEqual(record["self_test"], dict(profile="ok", render="ok", briefs="ok",
                                                deploy="pending crew up", targets="ok", doctor="ok"))

    def test_missing_brief_records_failed_self_test(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        (self.bundle / "templates/runtimes/tmux/reviewer.md").unlink()
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("self-test failed: briefs", r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["self_test"]["briefs"], "fail")

    def test_post_apply_doctor_failure_is_recorded(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        counter = Path(self.tmp) / "claude-calls"
        self.tool("claude", 'echo call >> "%s"\n[ "$(wc -l < "%s")" -lt 3 ] && echo 1.0' %
                  (counter, counter))
        # The fake PATH has no wc; use the host tool without changing the fixture PATH.
        os.symlink(shutil.which("wc"), Path(self.bindir) / "wc")
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["self_test"]["doctor"], "fail")

    def test_deploy_drift_and_target_hash_failure(self):
        loader = importlib.machinery.SourceFileLoader("bootstrap_cli", str(self.cli))
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("bootstrap_cli", loader))
        loader.exec_module(mod)
        bootstrap = mod.commands()["bootstrap"]
        live = Path(self.state) / "render"
        target = Path(self.tmp) / "target"
        target.write_text("installed\n")
        record = dict(runtime="tmux", targets={str(target): bootstrap.digest(target)})
        argv = ["--project", self.project, "--out", str(live)]
        with mock.patch.dict(os.environ, self.env), mock.patch.object(bootstrap.commands()["doctor"], "run", return_value=0):
            self.assertEqual(bootstrap.crew_render.main(argv), 0)
            doctor = bootstrap.commands()["doctor"]
            checks = bootstrap.self_test(self.project_path, None, live, record, doctor)
            self.assertEqual(set(checks.values()), {"ok"})
            (live / "runtime/reviewer.md").write_text("drift\n")
            target.write_text("changed\n")
            checks = bootstrap.self_test(self.project_path, None, live, record, doctor)
            self.assertEqual((checks["deploy"], checks["targets"]), ("fail", "fail"))

    def smoke_host(self):
        self.real_git()
        os.symlink(sys.executable, Path(self.bindir) / "python3")
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.issue_log = Path(self.tmp) / "issues"
        gh = Path(self.bindir) / "gh"
        text = gh.read_text().replace('*) exit 1;;',
            '"issue create") echo "$*" >> "%s"\n%s\n;;\n*) exit 1;;' %
            (self.issue_log, 'echo https://github.com/acme/widgets/issues/123'))
        gh.write_text(text)
        Path(self.state_file).write_text(json.dumps({"crew-acme-widgets": {"0": "ash"}}))

    def test_smoke_is_opt_in_dry_run_safe_and_queued_once(self):
        self.smoke_host()
        for flags in (("--dry-run", "--smoke"), ("--yes",)):
            r = self.bootstrap(*flags)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertFalse(self.issue_log.exists())
            self.assertEqual(self.calls(), [])
        for _ in range(2):
            r = self.bootstrap("--yes", "--smoke")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.issue_log.read_text().splitlines()), 1)
        self.assertIn("--label crew:ready --assignee acme-bot", self.issue_log.read_text())
        record = json.loads(self.manifest.read_text())
        self.assertEqual(record["smoke"], dict(issue="https://github.com/acme/widgets/issues/123", status="queued"))
        self.assertEqual(self.calls(), [["has-session", "-t", "=crew-acme-widgets"]])

    def test_smoke_requires_started_tmux_and_records_creation_failure(self):
        self.smoke_host()
        Path(self.state_file).unlink()
        r = self.bootstrap("--yes", "--smoke")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("requires a started crew", r.stderr)
        self.assertFalse(self.issue_log.exists())
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["status"], record["self_test"]["smoke"]), ("failed", "fail"))
        Path(self.state_file).write_text(json.dumps({"crew-acme-widgets": {"0": "ash"}}))
        gh = Path(self.bindir) / "gh"
        gh.write_text(gh.read_text().replace('echo https://github.com/acme/widgets/issues/123', 'exit 1'))
        r = self.bootstrap("--yes", "--smoke")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("smoke issue creation failed", r.stderr)
        self.assertNotIn("smoke", json.loads(self.manifest.read_text()))

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

    def test_missing_repo_labels_fail_before_install(self):
        self.tool("gh", 'case "$1 $2" in\n"auth token") echo fixture-token;;\n'
                  '"api repos/acme/widgets/labels?per_page=100") echo \'[[]]\';;\n*) exit 1;;\nesac')
        r = self.bootstrap("--yes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("fail  crew labels", r.stdout)
        self.assertNotIn("Plan:", r.stdout)
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


def self_test_evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        fixture.smoke_host()
        result = fixture.bootstrap("--dry-run", "--smoke")
        assert result.returncode == 0 and not fixture.issue_log.exists()
        print("dry-run --smoke: exit 0; no install or issue created")
        result = fixture.bootstrap("--yes")
        assert result.returncode == 0 and not fixture.issue_log.exists(), result.stdout + result.stderr
        print("apply: exit 0; no smoke issue by default")
        for line in result.stdout.splitlines():
            if line.startswith("Self-test:"):
                print(line)
        for _ in range(2):
            result = fixture.bootstrap("--yes", "--smoke")
            assert result.returncode == 0, result.stdout + result.stderr
            print(result.stdout.splitlines()[-1])
        assert len(fixture.issue_log.read_text().splitlines()) == 1
        print("smoke: one docs-only issue, crew:ready, assigned to builder; result queued")
        (fixture.bundle / "templates/runtimes/tmux/reviewer.md").unlink()
        result = fixture.bootstrap("--yes")
        record = json.loads(fixture.manifest.read_text())
        assert result.returncode == 1 and record["status"] == "failed" and record["self_test"]["briefs"] == "fail"
        print("missing reviewer brief: exit 1; install status failed; briefs fail")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, install and fake issue log removed")


if __name__ == "__main__":
    if sys.argv[1:] == ["--evidence"]:
        evidence()
    elif sys.argv[1:] == ["--self-test-evidence"]:
        self_test_evidence()
    else:
        unittest.main()
