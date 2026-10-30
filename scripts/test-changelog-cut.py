#!/usr/bin/env python3
"""Offline tests for scripts/changelog-cut.py on temp files."""
import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "changelog-cut.py")
spec = importlib.util.spec_from_file_location("changelog_cut", SCRIPT)
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

HEADER = "# Changelog\n\nIntro.\n\n"
UNRELEASED = ("## [Unreleased]\n\n### Added\n\n- New thing. (PR #2)\n"
              "  Box skill copy: none.\n\n### Fixed\n\n- A fix. (PR #3)\n\n")
OLD = "## [0.1.0] - 2026-10-01\n\n### Added\n\n- First. (PR #1)\n\n"
BOOTSTRAP = "## Bootstrap (2026-10-19)\n\n### Added\n\n- Spec.\n"
EMPTY = "## [Unreleased]\n\n### Added\n\n### Fixed\n\n"


class ChangelogCutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "CHANGELOG.md")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text):
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    def read(self):
        with open(self.path, encoding="utf-8", newline="") as f:
            return f.read()

    def run_cut(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cc.main([*args, "--file", self.path, "--date", "2026-10-30"])
        return code, out.getvalue(), err.getvalue()

    def assert_refused(self, text, version, message):
        self.write(text)
        code, _, err = self.run_cut(version)
        self.assertEqual(code, 1)
        self.assertIn(message, err)
        self.assertEqual(self.read(), text)

    def test_normal_cut(self):
        self.write(HEADER + UNRELEASED + OLD + BOOTSTRAP)
        code, out, _ = self.run_cut("0.2.0")
        self.assertEqual(code, 0, out)
        body = UNRELEASED[len("## [Unreleased]\n"):]
        expected = (HEADER + "## [Unreleased]\n\n## [0.2.0] - 2026-10-30\n"
                    + body + OLD + BOOTSTRAP)
        self.assertEqual(self.read(), expected)

    def test_first_cut_at_end_of_file_and_crlf(self):
        text = (HEADER + UNRELEASED).replace("\n", "\r\n")
        self.write(text)
        self.assertEqual(self.run_cut("1.0.0-rc.1+b5")[0], 0)
        self.assertIn("## [Unreleased]\r\n\r\n## [1.0.0-rc.1+b5] - 2026-10-30\r\n",
                      self.read())

    def test_dry_run_prints_and_does_not_write(self):
        text = HEADER + UNRELEASED + OLD
        self.write(text)
        code, out, _ = self.run_cut("0.2.0", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("## [0.2.0] - 2026-10-30\n", out)
        self.assertEqual(self.read(), text)

    def test_empty_unreleased_refused(self):
        self.assert_refused(HEADER + EMPTY + OLD, "0.2.0", "has no entries")
        self.assert_refused(HEADER + "## [Unreleased]\n" + OLD, "0.2.0",
                            "has no entries")

    def test_missing_unreleased_refused(self):
        self.assert_refused(HEADER + OLD, "0.2.0", "no ## [Unreleased]")

    def test_duplicate_version_refused(self):
        self.assert_refused(HEADER + UNRELEASED + OLD, "0.1.0", "already exists")

    def test_bad_version_refused(self):
        for bad in ["v1.0.0", "1.0", "1.0.0.0", "01.0.0", "1.0.0-", "1.0.0-01",
                    "1.0.0+", "x.y.z", ""]:
            with self.subTest(bad=bad):
                self.assert_refused(HEADER + UNRELEASED, bad, "not a SemVer")

    def test_version_not_greater_refused(self):
        for low in ["0.0.9", "0.1.0-rc.1", "0.1.0+build.2"]:
            with self.subTest(low=low):
                self.assert_refused(HEADER + UNRELEASED + OLD, low,
                                    "not greater than 0.1.0")

    def test_precedence(self):
        order = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta",
                 "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1",
                 "1.1.0", "2.0.0"]
        self.assertEqual(sorted(reversed(order), key=cc.precedence), order)

    def test_bad_date_is_usage_error(self):
        self.write(HEADER + UNRELEASED)
        r = subprocess.run([sys.executable, SCRIPT, "0.2.0", "--file", self.path,
                            "--date", "2026-13-01"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_default_date_is_today_utc(self):
        self.write(HEADER + UNRELEASED)
        r = subprocess.run([sys.executable, SCRIPT, "0.2.0", "--file", self.path],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        self.assertIn("## [0.2.0] - %s\n" % today, self.read())


if __name__ == "__main__":
    unittest.main()
