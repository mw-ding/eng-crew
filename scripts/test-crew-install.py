#!/usr/bin/env python3
"""Offline tests for scripts/crew-install.py (stdlib only): the shared release verifier on a staged fake bundle
(a good bundle moves into place; a SHA256SUMS pin mismatch, missing, duplicate and mismatched entries, unsafe
members and a bad VERSION are refused before the destination exists, with nothing extracted before the
checksum checks) and the install.json transport record (none for github; url, mirror and git fields; an old
record reads as github). Run in CI.
"""
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("crew_install", os.path.join(HERE, "crew-install.py"))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)

TAG, NAME = "v5.1.0", "eng-crew-5.1.0"


def stage_bundle(stage, version=TAG, extra=None, sums=None):
    """Write NAME.tar.gz (VERSION, scripts/crew, optional extra member) and SHA256SUMS into stage."""
    archive = Path(stage) / (NAME + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for path, data in (("VERSION", version + "\n"), ("scripts/crew", "#!/bin/sh\n")):
            info = tarfile.TarInfo(NAME + "/" + path)
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
        self.assertTrue((self.dest / "scripts/crew").is_file())

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
        escape = tarfile.TarInfo(NAME + "/../../escape")
        link = tarfile.TarInfo(NAME + "/link")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        for member in (escape, link, tarfile.TarInfo("other/file")):
            with self.subTest(member.name):
                stage_bundle(self.stage, extra=member)
                self.refused("unsafe release archive member", extracted=False)
        stage_bundle(self.stage, version="v5.0.0")
        self.refused("VERSION or bootstrap entry point does not match")


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
