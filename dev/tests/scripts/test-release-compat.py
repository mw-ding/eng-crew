#!/usr/bin/env python3
"""Offline tests for scripts/release-compat.py on temp git repos.

A fake validator stands in for core/crew-config.py so each break kind is one
setting: an operation newly required, an operation removed, an optional
addition. Covers minor and patch refusal, major acceptance, baseline choice,
a missing baseline and a corpus the baseline rejects. One end-to-end case
runs the real validator on both sides. Run in CI; never reads real tags.
"""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
ROOT = os.path.dirname(os.path.dirname(TESTS))
spec = importlib.util.spec_from_file_location("release_compat", os.path.join(ROOT, "scripts", "release-compat.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

MANIFEST = '[pack]\nname = "github"\ncommands = "x"\n\n[capabilities.change]\nopen = "supported"\nclose = "supported"\n'
# Fake crew-config.py: REQUIRED operations must be declared, every declared one must be KNOWN.
VALIDATOR = '''import sys, tomllib
REQUIRED, KNOWN = %r, %r
m = tomllib.load(open(sys.argv[2], "rb"))
bad = ["capabilities.change.%%s: required" %% k for k in REQUIRED if k not in m["capabilities"]["change"]]
bad += ["capabilities.change.%%s: unknown key" %% k for k in m["capabilities"]["change"] if k not in KNOWN]
if m["pack"]["name"] != "github" and "mdstack_version" not in m["pack"]:
    bad.append("pack.mdstack_version: required for an external backend")
for b in bad:
    print(sys.argv[2] + ":" + b)
sys.exit(1 if bad else 0)
'''
BASE = (["open"], ["open", "close"])


def git(repo, *args):
    subprocess.run(["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def write(repo, rel, text):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class ReleaseCompatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        git(self.repo, "init", "-q")

    def tearDown(self):
        self.tmp.cleanup()

    def release(self, tag, validator=BASE, manifest=MANIFEST):
        write(self.repo, rc.VALIDATOR, VALIDATOR % validator)
        write(self.repo, "connectors/github/manifest.toml", manifest)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", tag)
        git(self.repo, "tag", tag)

    def candidate(self, validator):
        write(self.repo, rc.VALIDATOR, VALIDATOR % validator)

    def run_compat(self, version, *extra):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = rc.main([version, "--repo", self.repo, *extra])
        return code, err.getvalue()

    def test_compatible_candidate_passes(self):
        self.release("v1.0.0")
        code, err = self.run_compat("1.1.0", "--tags", "v1.0.0")
        self.assertEqual(code, 0, err)
        self.assertIn("2 manifest(s) against baseline v1.0.0", err)

    def test_optional_addition_passes(self):
        self.release("v1.0.0")
        self.candidate((["open"], ["open", "close", "rebase"]))
        self.assertEqual(self.run_compat("1.1.0", "--baseline", "v1.0.0")[0], 0)

    def test_newly_required_operation_refuses_minor_and_patch(self):
        self.release("v1.0.0")
        self.candidate((["open", "rebase"], ["open", "close", "rebase"]))
        for version in ("1.1.0", "1.0.1", "1.1.0-rc.1"):
            with self.subTest(version=version):
                code, err = self.run_compat(version, "--baseline", "v1.0.0")
                self.assertEqual(code, 1)
                self.assertIn("refused: connectors/github/manifest.toml passes baseline v1.0.0 (", err)
                self.assertIn("capabilities.change.rebase: required", err)
                self.assertIn("refused: external pack (from connectors/github/manifest.toml)", err)
                self.assertIn("%s is not a major bump; cut 2.0.0" % version, err)

    def test_removed_operation_refuses_minor(self):
        self.release("v1.0.0")
        self.candidate((["open"], ["open"]))
        code, err = self.run_compat("1.1.0", "--baseline", "v1.0.0")
        self.assertEqual(code, 1)
        self.assertIn("capabilities.change.close: unknown key", err)

    def test_major_accepts_the_break(self):
        self.release("v1.0.0")
        self.candidate((["open", "rebase"], ["open", "close", "rebase"]))
        code, err = self.run_compat("2.0.0", "--baseline", "v1.0.0")
        self.assertEqual(code, 0, err)
        self.assertIn("breaking (allowed by major 2.0.0): connectors/github/manifest.toml: "
                      "capabilities.change.rebase: required", err)

    def test_baseline_is_greatest_stable_tag_below_version(self):
        tags = ["v1.0.0", "v1.2.0", "v1.3.0-rc.1", "v2.0.0", "not-semver", "v1.10.0+b"]
        self.assertEqual(rc.pick_baseline("1.3.0", tags), "v1.2.0")
        self.assertEqual(rc.pick_baseline("2.1.0", tags), "v2.0.0")
        with self.assertRaises(rc.Failed):
            rc.pick_baseline("1.0.0", tags)

    def test_missing_baseline_fails_with_repair_step(self):
        self.release("v1.0.0")
        code, err = self.run_compat("1.1.0", "--baseline", "v1.0.9")
        self.assertEqual(code, 1)
        self.assertIn("cannot read baseline v1.0.9", err)
        self.assertIn("git fetch --tags", err)
        code, err = self.run_compat("1.1.0", "--tags")
        self.assertEqual(code, 1)
        self.assertIn("no published stable tag below 1.1.0", err)

    def test_corpus_rejected_by_its_own_release_fails(self):
        self.release("v1.0.0", validator=(["open", "rebase"], ["open", "close", "rebase"]))
        code, err = self.run_compat("1.1.0", "--baseline", "v1.0.0")
        self.assertEqual(code, 1)
        self.assertIn("baseline v1.0.0 rejects its own connectors/github/manifest.toml", err)
        self.assertIn("repair CORPUS", err)

    def test_corpus_missing_at_baseline_fails(self):
        self.release("v1.0.0")
        git(self.repo, "rm", "-q", "connectors/github/manifest.toml")
        git(self.repo, "commit", "-q", "-m", "drop")
        git(self.repo, "tag", "v1.1.0")
        code, err = self.run_compat("1.2.0", "--baseline", "v1.1.0")
        self.assertEqual(code, 1)
        self.assertIn("baseline v1.1.0 has no connectors/github/manifest.toml", err)

    def test_not_semver(self):
        self.release("v1.0.0")
        self.assertIn("not a SemVer version", self.run_compat("v1.1.0", "--baseline", "v1.0.0")[1])

    def test_real_validator_end_to_end(self):
        files = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, check=True).stdout
        for rel in filter(None, files.decode().split("\0")):
            src = os.path.join(ROOT, rel)
            if os.path.isfile(src) and not os.path.islink(src):
                with open(src, "rb") as f:
                    data = f.read()
                os.makedirs(os.path.dirname(os.path.join(self.repo, rel)), exist_ok=True)
                with open(os.path.join(self.repo, rel), "wb") as f:
                    f.write(data)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "snapshot")
        git(self.repo, "tag", "v1.0.0")
        out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "release-compat.py"), "1.1.0",
                              "--repo", self.repo, "--tags", "v1.0.0"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("2 manifest(s) against baseline v1.0.0", out.stderr)


if __name__ == "__main__":
    unittest.main()
