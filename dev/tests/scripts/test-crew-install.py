#!/usr/bin/env python3
"""Offline tests for scripts/crew-install.py (stdlib only): the shared release verifier on a staged fake bundle
(a good bundle moves into place; a SHA256SUMS pin mismatch, missing, duplicate and mismatched entries, unsafe
members (escape, absolute path, symlink, hard link, device, FIFO, other root) and a bad VERSION are refused before
the destination exists, with nothing extracted before the checksum checks; the same holds without tarfile's
data_filter, as on Python 3.11.0 to 3.11.3, #1447), the git source on a local bare repository (a tag that peels to the pinned commit is built by
that commit's own release-bundle.py; a moved tag, a missing tag and a bad built bundle are refused, and nothing
from the commit runs before the pin check) and the install.json transport record (none for github; url, mirror
and git fields; an old record reads as github). Run in CI.
"""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
spec = importlib.util.spec_from_file_location("crew_install", os.path.join(SCRIPTS, "crew-install.py"))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

TAG, NAME = "v5.1.0", "mdstack-5.1.0"


class NoDataFilter:
    """Python 3.11.0 to 3.11.3 (#1447): tarfile has no data_filter, and extractall takes no filter argument."""

    def __enter__(self):
        self.saved, self.real, self.calls = tarfile.data_filter, tarfile.TarFile.extractall, []
        del tarfile.data_filter
        real, calls = self.real, self.calls

        def extractall(tar, path=".", members=None, *, numeric_owner=False, **kw):
            calls.append(kw)
            if kw:
                raise TypeError("extractall() got an unexpected keyword argument %r" % next(iter(kw)))
            return real(tar, path, members, numeric_owner=numeric_owner, filter="fully_trusted")

        tarfile.TarFile.extractall = extractall
        return self

    def __exit__(self, *exc):
        tarfile.data_filter, tarfile.TarFile.extractall = self.saved, self.real


def unsafe_members():
    """One member of each refused kind: a `..` escape, an absolute path, a symlink, a hard link, a device, a FIFO
    and a file outside the bundle root."""
    escape, absolute = tarfile.TarInfo(NAME + "/../../escape"), tarfile.TarInfo("/" + NAME + "/abs")
    symlink, hardlink = tarfile.TarInfo(NAME + "/link"), tarfile.TarInfo(NAME + "/hard")
    symlink.type, symlink.linkname = tarfile.SYMTYPE, "/etc/passwd"
    hardlink.type, hardlink.linkname = tarfile.LNKTYPE, NAME + "/VERSION"
    device, fifo = tarfile.TarInfo(NAME + "/dev"), tarfile.TarInfo(NAME + "/fifo")
    device.type, fifo.type = tarfile.CHRTYPE, tarfile.FIFOTYPE
    return escape, absolute, symlink, hardlink, device, fifo, tarfile.TarInfo("other/file")


def stage_bundle(stage, version=TAG, extra=None, sums=None, name=NAME):
    """Write <name>.tar.gz (VERSION, cli/mdstack, optional extra member) and SHA256SUMS into stage."""
    archive = Path(stage) / (name + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for path, data in (("VERSION", version + "\n"), ("cli/mdstack", "#!/bin/sh\n")):
            info = tarfile.TarInfo(name + "/" + path)
            info.size = len(data.encode())
            tar.addfile(info, io.BytesIO(data.encode()))
        if extra:
            tar.addfile(extra)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    lines = sums(sha) if sums else [sha + "  " + archive.name]
    (Path(stage) / "SHA256SUMS").write_text("".join(line + "\n" for line in lines))
    return sha


class VerifyTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.stage = Path(tmp.name) / "stage"
        self.stage.mkdir()
        self.dest = Path(tmp.name) / NAME

    def refused(self, message, pin=None, extracted=True):
        with self.assertRaisesRegex(ValueError, message):
            ci.verify(self.stage, TAG, self.dest, pin)
        self.assertFalse(self.dest.exists())
        self.assertEqual((self.stage / "extract").exists(), extracted)

    def test_good_bundle_moves_into_place_with_both_digests(self):
        sha = stage_bundle(self.stage)
        pin = ci.digest(self.stage / "SHA256SUMS")
        self.assertEqual(ci.verify(self.stage, TAG, self.dest, pin), (sha, pin))
        self.assertEqual((self.dest / "VERSION").read_text(), TAG + "\n")
        self.assertTrue((self.dest / "cli/mdstack").is_file())

    def test_checksum_refusals_happen_before_extraction(self):
        stage_bundle(self.stage)
        self.refused("does not match the pinned sha256sums_digest", pin="0" * 64, extracted=False)
        for sums, case in ((lambda sha: [], "missing"),
                           (lambda sha: [sha + "  " + NAME + ".tar.gz"] * 2, "duplicate"),
                           (lambda sha: ["0" * 64 + "  " + NAME + ".tar.gz"], "mismatch"),
                           (lambda sha: [sha + "  other.tar.gz"], "other file only")):
            with self.subTest(case):
                stage_bundle(self.stage, sums=sums)
                self.refused("SHA256SUMS mismatch or missing entry", extracted=False)

    def test_unsafe_members_and_bad_version_are_refused(self):
        for member in unsafe_members():
            with self.subTest(member.name):
                stage_bundle(self.stage, extra=member)
                self.refused("unsafe release archive member", extracted=False)
        stage_bundle(self.stage, version="v5.0.0")
        self.refused("VERSION or bootstrap entry point does not match")

    def test_without_data_filter_unsafe_members_are_refused_and_a_good_bundle_installs(self):
        with NoDataFilter() as nd:
            for member in unsafe_members():
                with self.subTest(member.name):
                    stage_bundle(self.stage, extra=member)
                    self.refused("unsafe release archive member", extracted=False)
            self.assertEqual(nd.calls, [])
            sha = stage_bundle(self.stage)
            self.assertEqual(ci.verify(self.stage, TAG, self.dest)[0], sha)
            self.assertEqual(nd.calls, [{}])
        self.assertEqual((self.dest / "VERSION").read_text(), TAG + "\n")
        self.assertTrue((self.dest / "cli/mdstack").is_file())

    def test_with_data_filter_the_extract_passes_it(self):
        real, calls = tarfile.TarFile.extractall, []
        tarfile.TarFile.extractall = lambda tar, *a, **kw: calls.append(kw) or real(tar, *a, **kw)
        try:
            stage_bundle(self.stage)
            ci.verify(self.stage, TAG, self.dest)
        finally:
            tarfile.TarFile.extractall = real
        self.assertEqual(calls, [{"filter": "data"}])


class BundleNameTest(unittest.TestCase):
    """#1312: every release's bundle and toolkit is mdstack-<v>; no eng-crew-<v> name is looked up."""

    def test_name_is_mdstack(self):
        for tag, name in (("v7.0.0", "mdstack-7.0.0"), ("v7.1.0-rc.1", "mdstack-7.1.0-rc.1"), ("v6.2.0", "mdstack-6.2.0")):
            with self.subTest(tag):
                self.assertEqual(ci.bundle_name(tag), name)

    def test_a_7x_bundle_verifies_under_its_new_name_and_an_old_name_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage, dest = Path(tmp) / "stage", Path(tmp) / "mdstack-7.0.0"
            stage.mkdir()
            sha = stage_bundle(stage, "v7.0.0", name="mdstack-7.0.0")
            self.assertEqual(ci.verify(stage, "v7.0.0", dest)[0], sha)
            self.assertEqual((dest / "VERSION").read_text(), "v7.0.0\n")
            (stage / "mdstack-7.0.0.tar.gz").unlink()
            stage_bundle(stage, "v7.0.0", name="eng-crew-7.0.0")  # an old-named asset is never read
            with self.assertRaisesRegex(FileNotFoundError, "mdstack-7.0.0.tar.gz"):
                ci.verify(stage, "v7.0.0", Path(tmp) / "other")

    def test_github_stage_downloads_the_named_asset_from_the_renamed_repo(self):
        calls = []
        real = ci.subprocess.run
        ci.subprocess.run = lambda argv, **kw: calls.append(argv) or subprocess.CompletedProcess(argv, 0, "", "")
        try:
            ci.stage({}, "v7.0.0", "/nowhere")
        finally:
            ci.subprocess.run = real
        self.assertEqual([c[:5] for c in calls], [["gh", "release", "download", "v7.0.0", "-R"]])
        self.assertEqual([(c[5], c[7]) for c in calls], [("mw-ding/mdstack", "mdstack-7.0.0.tar.gz")])


STUB = """import io, os, sys, tarfile
version, out = sys.argv[1], sys.argv[sys.argv.index("--out") + 1]
open(os.environ["BUILD_LOG"], "a").write(" ".join(sys.argv[1:]) + "\\n")
name = "mdstack-" + version
with tarfile.open(os.path.join(out, name + ".tar.gz"), "w:gz") as tar:
    for path, data in (("VERSION", "%s\\n"), ("cli/mdstack", "#!/bin/sh\\n")):
        info = tarfile.TarInfo(name + "/" + path)
        info.size = len(data.encode())
        tar.addfile(info, io.BytesIO(data.encode()))
"""


class GitSourceTest(unittest.TestCase):
    """build_git and fetch on a local bare repository whose commits carry a stub scripts/release-bundle.py."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.remote, self.work = self.tmp / "remote.git", self.tmp / "work"
        self.log = self.tmp / "build.log"
        os.environ["BUILD_LOG"] = str(self.log)
        self.addCleanup(os.environ.pop, "BUILD_LOG", None)
        self.git("init", "-q", "--bare", str(self.remote), cwd=self.tmp)
        self.git("init", "-q", str(self.work), cwd=self.tmp)
        self.good = self.commit("v" + TAG[1:])
        self.git("push", "-q", str(self.remote), "HEAD:refs/heads/main")

    def git(self, *args, cwd=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t", *args], cwd=cwd or self.work,
                              env=env, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, version):
        (self.work / "scripts").mkdir(exist_ok=True)
        (self.work / "scripts/release-bundle.py").write_text(STUB.replace("%s", version))
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", version)
        return self.git("rev-parse", "HEAD")

    def tag(self, commit, annotated=False):
        self.git("tag", "-f", *(["-a", "-m", "release"] if annotated else []), TAG, commit)
        self.git("push", "-q", "-f", str(self.remote), "refs/tags/" + TAG)

    def fetch(self, commit):
        install = {"source": "git", "location": str(self.remote), "git_commit": commit}
        return ci.fetch(install, TAG, self.tmp / NAME)

    def test_tag_at_the_pinned_commit_is_built_by_its_own_script(self):
        for annotated in (False, True):
            with self.subTest(annotated=annotated):
                self.tag(self.good, annotated)
                sha, sums, commit = self.fetch(self.good)
                self.assertEqual((sums, commit), (None, self.good))
                self.assertRegex(sha, "^[0-9a-f]{64}$")
                self.assertEqual((self.tmp / NAME / "VERSION").read_text(), TAG + "\n")
                self.assertIn("--ref %s --repo mw-ding/mdstack" % self.good, self.log.read_text())
                self.assertFalse(list(self.tmp.glob(".crew-fetch-*")))
                (self.tmp / NAME / "VERSION").unlink()
                (self.tmp / NAME / "cli/mdstack").unlink()
                (self.tmp / NAME / "cli").rmdir()
                (self.tmp / NAME).rmdir()

    def test_without_data_filter_the_pinned_tag_still_builds(self):
        self.tag(self.good)
        with NoDataFilter() as nd:
            self.fetch(self.good)
        self.assertEqual(nd.calls, [{}, {}])
        self.assertEqual((self.tmp / NAME / "VERSION").read_text(), TAG + "\n")

    def test_git_archive_members_outside_scripts_or_not_plain_are_refused(self):
        for case, member in (("outside", tarfile.TarInfo("cli/mdstack")),
                             ("escape", tarfile.TarInfo("scripts/../../x")),
                             ("symlink", tarfile.TarInfo("scripts/link"))):
            member.type = tarfile.SYMTYPE if case == "symlink" else member.type
            with self.subTest(case), tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / "scripts.tar"
                with tarfile.open(archive, "w") as tar:
                    tar.addfile(member)
                with tarfile.open(archive) as tar, \
                        self.assertRaisesRegex(ValueError, "unsafe git source archive member"):
                    ci.extract(tar, Path(tmp) / "tools", "scripts", "git source archive")
                self.assertFalse((Path(tmp) / "tools").exists())

    def test_moved_or_missing_tag_is_refused_before_anything_runs(self):
        moved = self.commit("v" + TAG[1:])
        self.tag(moved)
        with self.assertRaisesRegex(ValueError, "resolves to %s, not the pinned git_commit %s" % (moved, self.good)):
            self.fetch(self.good)
        self.git("push", "-q", str(self.remote), ":refs/tags/" + TAG)
        with self.assertRaisesRegex(ValueError, "git source fetch failed for " + TAG):
            self.fetch(self.good)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.tmp / NAME).exists())
        self.assertFalse(list(self.tmp.glob(".crew-fetch-*")))

    def test_built_bundle_with_bad_version_is_refused(self):
        bad = self.commit("v5.0.0")
        self.tag(bad)
        with self.assertRaisesRegex(ValueError, "VERSION or bootstrap entry point does not match"):
            self.fetch(bad)
        self.assertTrue(self.log.exists())
        self.assertFalse((self.tmp / NAME).exists())


class TransportTest(unittest.TestCase):
    def test_github_has_no_field(self):
        self.assertIsNone(ci.transport(None))
        self.assertIsNone(ci.transport({"source": "github"}))

    def test_url_mirror_and_git_fields(self):
        self.assertEqual(ci.transport({"source": "mirror", "location": "/srv/rel", "sha256sums_digest": "a" * 64}, "b" * 64),
                         {"kind": "mirror", "location": "/srv/rel", "sha256sums_sha256": "b" * 64, "pinned": True})
        self.assertEqual(ci.transport({"source": "url", "location": "https://rel.example"}, "b" * 64),
                         {"kind": "url", "location": "https://rel.example", "sha256sums_sha256": "b" * 64,
                          "pinned": False})
        self.assertEqual(ci.transport({"source": "git", "location": "/srv/git", "git_commit": "c" * 40}, commit="c" * 40),
                         {"kind": "git", "location": "/srv/git", "commit": "c" * 40})

    def test_record_kind_defaults_to_github(self):
        self.assertEqual(ci.transport_kind({"tag": TAG, "bundle_sha256": "a" * 64}), "github")
        self.assertEqual(ci.transport_kind({"transport": {"kind": "mirror", "location": "/srv/rel"}}), "mirror")


if __name__ == "__main__":
    unittest.main()
