#!/usr/bin/env python3
"""Fixture test for scripts/step-summary.py (offline, temp dir only)."""
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "step_summary", os.path.join(HERE, "step-summary.py"))
ss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss)


def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = ss.main(list(argv))
    assert code == 0
    return out.getvalue().strip()


class StepSummaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.base = ("--root", self.root, "--ref", "issue-85", "--run-id", "r1")

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        path = os.path.join(self.root, ".crew", "runs", "issue-85", "r1", "summary.md")
        with open(path) as fh:
            return fh.read()

    def test_two_steps_one_header(self):
        run(*self.base, "--step", "build", "--status", "ok", "--duration", "42",
            "--outcome", "built 3 targets")
        run(*self.base, "--step", "test", "--status", "fail", "--duration", "184",
            "--outcome", "1 failed\nFAILED test_x\nAssertionError", "--log",
            "steps/test.log")
        text = self.read()
        self.assertTrue(text.startswith("# Step summary\n"))
        self.assertEqual(text.count("# Step summary"), 1)
        self.assertIn("- Ref: `issue-85`", text)
        self.assertIn("- **build** · ok · 42s\n  > built 3 targets\n", text)
        self.assertIn("- **test** · fail · 3m04s\n  > 1 failed\n", text)
        self.assertIn("  log: `steps/test.log`\n", text)
        self.assertLess(text.index("**build**"), text.index("**test**"))

    def test_truncation(self):
        run(*self.base, "--step", "s", "--status", "warn", "--outcome",
            "a\nb\nc\nd\n" + "x" * 500)
        text = self.read()
        self.assertIn("> c", text)
        self.assertNotIn("> d", text)
        run(*self.base, "--step", "long", "--status", "ok", "--outcome", "y" * 500)
        long_line = [l for l in self.read().splitlines() if "yyy" in l][0]
        self.assertEqual(len(long_line), len("  > ") + ss.MAX_LINE_CHARS)
        self.assertTrue(long_line.endswith("..."))

    def test_redaction(self):
        # Built at runtime so this file carries no literal token shapes.
        gh = "gh" + "p_" + "A" * 36
        sk = "sk" + "-" + "b" * 30
        outcome = "\n".join([
            "push with " + gh,
            "key " + sk,
            "Authorization: " + "Bear" + "er abc123def",
            "clone https://user:" + "hunter2" + "@host/x.git",
            "PASSWORD=hunter2",
        ])
        run(*self.base, "--step", "push", "--status", "fail", "--outcome", outcome)
        text = self.read()
        for secret in (gh, sk, "abc123def", "hunter2"):
            self.assertNotIn(secret, text)
        self.assertIn(ss.REDACTED, text)

    def test_log_tail_only(self):
        log = os.path.join(self.root, "raw.log")
        with open(log, "w") as fh:
            fh.write("".join("line %d\n" % i for i in range(100)))
        run(*self.base, "--step", "t", "--status", "ok", "--outcome-from-log", log)
        text = self.read()
        self.assertIn("> line 99", text)
        self.assertIn("> line 97", text)
        self.assertNotIn("line 96", text)

    def test_bad_ref_rejected(self):
        with self.assertRaises(SystemExit):
            ss.main(["--root", self.root, "--ref", "../x", "--run-id", "r1",
                     "--step", "s", "--status", "ok"])

    def test_duration_format(self):
        self.assertEqual(ss.fmt_duration("5"), "5s")
        self.assertEqual(ss.fmt_duration("125"), "2m05s")
        self.assertEqual(ss.fmt_duration("3m04s"), "3m04s")


if __name__ == "__main__":
    unittest.main()
