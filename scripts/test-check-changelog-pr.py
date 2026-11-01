#!/usr/bin/env python3
"""CHANGELOG PR guard fixtures using temporary git repos, without network."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("check-changelog-pr.py")


class ChangelogPRTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("README.md", "Before\n")
        self.write("CHANGELOG.md", "Unreleased\n")
        self.write("changes/unreleased/1-old.md", "Old fragment\n")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              capture_output=True, text=True, env=self.env).stdout

    def write(self, path, text="After\n"):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")

    def run_guard(self, *args, base=None):
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root),
                               "--event", "pull_request", "--base", base or self.base,
                               *args], capture_output=True, text=True, env=self.env)

    def test_fragment_present(self):
        self.write("README.md")
        self.write("changes/unreleased/2-new.md")
        self.commit()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("new fragment added", result.stdout)

    def test_fragment_missing(self):
        self.write("README.md")
        self.commit()
        result = self.run_guard()
        self.assertEqual(result.returncode, 1)
        self.assertIn("add changes/unreleased/<issue>-<slug>.md", result.stderr)

    def test_exempt_only(self):
        self.write("changes/unreleased/1-old.md")
        self.write("evidence/1/check.txt")
        self.commit()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("exempt-only", result.stdout)

    def test_cut_pr(self):
        self.write("CHANGELOG.md", "Released\n")
        (self.root / "changes/unreleased/1-old.md").unlink()
        self.commit()
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("exempt-only", result.stdout)

    def test_existing_fragment_edit_does_not_satisfy(self):
        self.write("README.md")
        self.write("changes/unreleased/1-old.md")
        self.commit()
        self.assertEqual(self.run_guard().returncode, 1)

    def test_cut_with_content_changes_requires_fragment(self):
        self.write("CHANGELOG.md", "Released\n")
        self.write("README.md")
        self.commit()
        self.assertEqual(self.run_guard().returncode, 1)

    def test_empty_train_diff(self):
        self.assertEqual(self.run_guard().returncode, 0)

    def test_push_main_skips_diff(self):
        result = self.run_guard("--event", "push", base="missing-ref")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("push event", result.stdout)

    def test_unreadable_base_fails(self):
        result = self.run_guard(base="missing-ref")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot read PR diff", result.stderr)

    def test_base_only_fragment_does_not_satisfy(self):
        self.git("checkout", "-qb", "base")
        self.write("changes/unreleased/2-base.md")
        self.commit()
        newer_base = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-qb", "pr", self.base)
        self.write("README.md")
        self.commit()
        self.assertEqual(self.run_guard(base=newer_base).returncode, 1)


if __name__ == "__main__":
    unittest.main()
