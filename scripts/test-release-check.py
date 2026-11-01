#!/usr/bin/env python3
"""Offline tests for scripts/release-check.py on temp files.

Covers: pass and notes, pre-release order, every failure (a leftover fragment
included). Run in CI.
"""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "release-check.py")
spec = importlib.util.spec_from_file_location("release_check", SCRIPT)
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

HEADER = "# Changelog\n\nIntro.\n\n"
EMPTY = "## [Unreleased]\n\n### Added\n\n"
CUT = "## [1.1.0] - 2026-10-30\n\n### Added\n\n- New thing. (PR #2)\n  Box skill copy: none.\n\n"
OLD = "## [1.0.0] - 2026-10-01\n\n### Added\n\n- First. (PR #1)\n\n"
BOOTSTRAP = "## Bootstrap (2026-10-19)\n\n- Spec.\n"
NOTES = "### Added\n\n- New thing. (PR #2)\n  Box skill copy: none.\n"


class ReleaseCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "CHANGELOG.md")
        self.notes = os.path.join(self.tmp.name, "notes.md")

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, text, version, *tags):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = rc.main([version, "--file", self.path, "--notes", self.notes, "--tags", *tags])
        return code, err.getvalue()

    def assert_failed(self, text, version, message, *tags):
        code, err = self.run_check(text, version, *tags)
        self.assertEqual(code, 1)
        self.assertIn(message, err)
        self.assertFalse(os.path.exists(self.notes))

    def test_ok_writes_notes(self):
        code, err = self.run_check(HEADER + EMPTY + CUT + OLD + BOOTSTRAP, "1.1.0", "v1.0.0")
        self.assertEqual(code, 0, err)
        with open(self.notes, encoding="utf-8") as f:
            self.assertEqual(f.read(), NOTES)

    def test_notes_stop_at_non_version_heading(self):
        code, err = self.run_check(HEADER + EMPTY + CUT + BOOTSTRAP, "1.1.0")
        self.assertEqual(code, 0, err)
        with open(self.notes, encoding="utf-8") as f:
            self.assertEqual(f.read(), NOTES)

    def test_pre_release_greater_than_latest_tag(self):
        text = HEADER + EMPTY + CUT.replace("1.1.0", "2.0.0-rc.1") + OLD
        self.assertEqual(self.run_check(text, "2.0.0-rc.1", "v1.0.0", "v2.0.0-rc.0")[0], 0)

    def test_unreleased_not_empty(self):
        text = HEADER + "## [Unreleased]\n\n### Added\n\n- Pending. (PR #3)\n\n" + CUT
        self.assert_failed(text, "1.1.0", "still has entries")

    def test_no_version_section(self):
        self.assert_failed(HEADER + EMPTY + BOOTSTRAP, "1.1.0", "followed by a version section")

    def test_wrong_top_version(self):
        self.assert_failed(HEADER + EMPTY + CUT + OLD, "1.0.0", "top version section is [1.1.0]")

    def test_tag_exists(self):
        self.assert_failed(HEADER + EMPTY + CUT, "1.1.0", "tag v1.1.0 already exists", "v1.1.0")

    def test_not_greater_than_latest_tag(self):
        self.assert_failed(HEADER + EMPTY + CUT, "1.1.0", "not greater than tag v1.2.0",
                           "v1.0.0", "v1.2.0", "not-semver")

    def test_not_semver(self):
        self.assert_failed(HEADER + EMPTY + CUT, "v1.1.0", "not a SemVer version")

    def test_leftover_fragment_refused(self):
        frags = os.path.join(self.tmp.name, "changes", "unreleased")
        os.makedirs(frags)
        self.assertEqual(self.run_check(HEADER + EMPTY + CUT, "1.1.0")[0], 0)
        os.remove(self.notes)
        with open(os.path.join(frags, "7-late.md"), "w", encoding="utf-8") as f:
            f.write("---\n")
        self.assert_failed(HEADER + EMPTY + CUT, "1.1.0", "fragments left (7-late.md)")

    def test_fragments_flag(self):
        other = os.path.join(self.tmp.name, "other")
        os.makedirs(other)
        with open(os.path.join(other, "7-late.md"), "w", encoding="utf-8") as f:
            f.write("---\n")
        self.assertEqual(self.run_check(HEADER + EMPTY + CUT, "1.1.0")[0], 0)
        os.remove(self.notes)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = rc.main(["1.1.0", "--file", self.path, "--fragments", other])
        self.assertEqual(code, 1)
        self.assertIn("fragments left (7-late.md)", err.getvalue())

    def test_missing_file(self):
        code = rc.main(["1.1.0", "--file", os.path.join(self.tmp.name, "nope.md")])
        self.assertEqual(code, 1)

    def test_cli_prints_notes_to_stdout(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(HEADER + EMPTY + CUT)
        out = subprocess.run([sys.executable, SCRIPT, "1.1.0", "--file", self.path],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout, NOTES)


if __name__ == "__main__":
    unittest.main()
