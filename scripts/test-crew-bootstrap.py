"""Offline bootstrap tests on a fake host and extracted bundle, including dry-run, confirmation, failures,
tmux record/idempotency, Grok Bot deployment, protected targets and clone version selection. Run in CI.
Use --evidence or --fetch-evidence for deterministic install/verify/delete CLI transcripts, with paths scrubbed.
"""
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
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


    def release(self, tag="v2.2.0", checksum=True, version=None, unsafe=False):
        assets = Path(self.tmp) / "assets"
        assets.mkdir(exist_ok=True)
        name = "eng-crew-" + tag[1:]
        archive = assets / (name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            for path in sorted(self.bundle.rglob("*")):
                if path.is_file():
                    data = ((version or tag) + "\n").encode() if path.name == "VERSION" else path.read_bytes()
                    info = tarfile.TarInfo(name + "/" + str(path.relative_to(self.bundle)))
                    info.mode, info.size = path.stat().st_mode & 0o777, len(data)
                    tar.addfile(info, io.BytesIO(data))
            if unsafe:
                info = tarfile.TarInfo(name + "/../../escape")
                tar.addfile(info, io.BytesIO())
        sha = hashlib.sha256(archive.read_bytes()).hexdigest()
        (assets / "SHA256SUMS").write_text((sha if checksum else "0" * 64) + "  " + archive.name + "\n")
        original = Path(self.bindir) / "gh-doctor"
        if not original.exists():
            (Path(self.bindir) / "gh").rename(original)
        self.tool("gh", "exec %s - \"$@\" <<'PY'\n" % sys.executable +
                  "import json, os, pathlib, shutil, sys\n"
                  "args = sys.argv[1:]\n"
                  "if args[:2] != ['release', 'download']:\n"
                  "    os.execv(%r, [%r] + args)\n" % (str(original), str(original)) +
                  "pathlib.Path(%r).write_text(json.dumps(args))\n" % str(assets / "argv.json") +
                  "for name in %r:\n" % [archive.name, "SHA256SUMS"] +
                  "    shutil.copyfile(pathlib.Path(%r) / name, pathlib.Path(args[args.index('--dir')+1]) / name)\n"
                  "PY" % str(assets))
        return Path(self.tmp) / name, sha

    def org(self, pin):
        org = Path(self.tmp) / "org"
        org.mkdir(exist_ok=True)
        (org / "profile.toml").write_text("")
        (org / "manifest.toml").write_text('[pack]\neng_crew_version = "%s"\n' % pin)
        return str(org / "profile.toml")

    def test_fetch_verifies_runs_selected_bundle_and_records_digest(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        destination, sha = self.release()
        r = self.bootstrap("--version", "v2.2.0", "--yes", "--org-profile", self.org("v2.2.0"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        record = json.loads(self.manifest.read_text())
        self.assertEqual((record["tag"], record["source"], record["bundle_sha256"]),
                         ("v2.2.0", str(destination.resolve()), sha))
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), destination.resolve())
        self.assertEqual((self.bundle / "VERSION").read_text(), "v2.1.0\n")
        argv = json.loads((Path(self.tmp) / "assets/argv.json").read_text())
        self.assertEqual(argv[:5], ["release", "download", "v2.2.0", "-R", "mw-ding/eng-crew"])
        self.assertIn("eng-crew-2.2.0.tar.gz", argv)
        self.assertIn("SHA256SUMS", argv)
        self.cli = destination / "scripts/crew"
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        self.assertEqual(json.loads(self.manifest.read_text())["bundle_sha256"], sha)

    def test_fetch_dry_run_preserves_live_install_and_existing_versions(self):
        self.real_git()
        subprocess.run(["git", "init", "-q", self.project_dir], check=True)
        self.assertEqual(self.bootstrap("--yes").returncode, 0)
        previous = self.manifest.read_text()
        destination, _ = self.release()
        r = self.bootstrap("--version", "v2.2.0", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Plan: v2.2.0", r.stdout)
        self.assertTrue(destination.is_dir())
        self.assertEqual(self.manifest.read_text(), previous)
        self.assertEqual((Path(self.state) / "eng-crew").resolve(), self.bundle.resolve())
        marker = destination / "owner-file"
        marker.write_text("preserve")
        r = self.bootstrap("--version", "v2.2.0", "--yes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("already exists", r.stderr)
        self.assertEqual(marker.read_text(), "preserve")

    def test_fetch_rejects_checksum_version_and_unsafe_archive_before_publish(self):
        for options, message in ((dict(checksum=False), "SHA256SUMS mismatch"),
                                 (dict(version="v9.9.9"), "VERSION"),
                                 (dict(unsafe=True), "unsafe release archive")):
            destination, _ = self.release(**options)
            r = self.bootstrap("--version", "v2.2.0", "--yes")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn(message, r.stderr)
            self.assertFalse(destination.exists())
            self.assertFalse(self.manifest.exists())
            self.assertFalse(list(Path(self.tmp).glob(".crew-fetch-*")))
        self.assertFalse((Path(self.tmp) / "escape").exists())

    def test_prereleases_need_pre_and_never_satisfy_pin(self):
        destination, _ = self.release(tag="v2.2.0-rc.1")
        r = self.bootstrap("--version", "v2.2.0-rc.1", "--dry-run")
        self.assertEqual(r.returncode, 1)
        self.assertIn("require --pre", r.stderr)
        self.assertFalse(destination.exists())
        r = self.bootstrap("--version", "v2.2.0-rc.1", "--pre", "--dry-run",
                           "--org-profile", self.org("v2.2.0-rc.1"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("pack.eng_crew_version", r.stderr)
        self.assertFalse(destination.exists())
        r = self.bootstrap("--version", "v2.2.0-rc.1", "--pre", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Plan: v2.2.0-rc.1", r.stdout)
        (self.bundle / "VERSION").write_text("v2.1.0-rc.1\n")
        self.assertEqual(self.bootstrap("--pre", "--dry-run").returncode, 0)

    def test_pack_pin_and_invalid_flags_fail_before_download(self):
        for flags in (("--version", "v2.2.0", "--org-profile", self.org("v2.1.0")),
                      ("--org-profile", self.org("v9.9.9")),
                      ("--version", "../../escape"), ("--version", "v2.2.0", "--dev")):
            r = self.bootstrap(*flags, "--dry-run")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertFalse(self.manifest.exists())
        org = self.org("v2.1.0")
        (Path(org).parent / "manifest.toml").unlink()
        self.assertEqual(self.bootstrap("--org-profile", org, "--dry-run").returncode, 1)
        self.assertEqual(self.bootstrap("--version", "v2.2.0", "--dry-run").returncode, 1)


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


def fetch_evidence():
    fixture = Bootstrap()
    fixture.setUp()
    try:
        fixture.real_git()
        subprocess.run(["git", "init", "-q", fixture.project_dir], check=True)
        r = fixture.bootstrap("--yes")
        assert r.returncode == 0, r.stdout + r.stderr
        print("create: crew bootstrap --yes -> exit 0; v2.1.0 installed")
        destination, sha = fixture.release()
        r = fixture.bootstrap("--version", "v2.2.0", "--yes", "--org-profile", fixture.org("v2.2.0"))
        assert r.returncode == 0, r.stdout + r.stderr
        record = json.loads(fixture.manifest.read_text())
        assert record["tag"] == "v2.2.0" and record["bundle_sha256"] == sha
        assert (Path(fixture.state) / "eng-crew").resolve() == destination.resolve()
        assert (fixture.bundle / "VERSION").read_text() == "v2.1.0\n"
        print("update: crew bootstrap --version v2.2.0 --yes --org-profile <pack>/profile.toml -> exit 0")
        print("verified SHA256SUMS; extracted eng-crew-2.2.0 beside original; matching pack pin accepted")
        print("record: v2.2.0 installed; checksum and selected bundle link verified; original v2.1.0 preserved")
        previous = fixture.manifest.read_text()
        for tag, options, flags, message in (
                ("v2.3.0", dict(checksum=False), (), "SHA256SUMS mismatch"),
                ("v2.4.0", {}, ("--org-profile", fixture.org("v9.9.9")), "pack.eng_crew_version"),
                ("v2.5.0-rc.1", {}, (), "require --pre")):
            rejected, _ = fixture.release(tag=tag, **options)
            r = fixture.bootstrap("--version", tag, "--dry-run", *flags)
            assert r.returncode == 1 and message in r.stderr, r.stdout + r.stderr
            assert not rejected.exists() and fixture.manifest.read_text() == previous
            print("reject: %s -> exit 1; %s; live install preserved" % (tag, message))
        rejected, _ = fixture.release(tag="v2.5.0-rc.1")
        r = fixture.bootstrap("--version", "v2.5.0-rc.1", "--pre", "--dry-run")
        assert r.returncode == 0 and rejected.is_dir(), r.stdout + r.stderr
        assert fixture.manifest.read_text() == previous
        print("preview: crew bootstrap --version v2.5.0-rc.1 --pre --dry-run -> exit 0; live install preserved")
    finally:
        fixture.doCleanups()
    assert not Path(fixture.tmp).exists()
    print("delete: temporary project, releases and install removed; absent=True")


if __name__ == "__main__":
    if sys.argv[1:] == ["--evidence"]:
        evidence()
    elif sys.argv[1:] == ["--fetch-evidence"]:
        fetch_evidence()
    else:
        unittest.main()
