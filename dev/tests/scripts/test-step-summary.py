#!/usr/bin/env python3
"""Fixture test for scripts/step-summary.py (offline, temp dir only).

Covers format, truncation, redaction. Run in CI.
"""
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
        # Each case stays inside the 3-line outcome limit, so every redactor
        # runs: clean_outcome() drops lines past MAX_LINES before redacting.
        cases = [
            ("push with " + gh + "\nkey " + sk
             + "\nAuthorization: " + "Bear" + "er abc123def", (gh, sk, "abc123def")),
            ("clone https://user" + ":" + "hunter2" + "@host/x.git", ("hunter2",)),
            ("PASSWORD=" + "hunter3", ("hunter3",)),
        ]
        for i, (outcome, secrets) in enumerate(cases):
            run(*self.base, "--step", "push%d" % i, "--status", "fail",
                "--outcome", outcome)
            block = self.read().split("- **push%d**" % i)[1]
            for secret in secrets:
                self.assertNotIn(secret, block)
            self.assertIn(ss.REDACTED, block)
        self.assertIn("//user" + ":%s@host" % ss.REDACTED, self.read())
        self.assertIn("PASSWORD=%s" % ss.REDACTED, self.read())

    def test_log_tail_only(self):
        log = os.path.join(self.root, "raw.log")
        with open(log, "w") as fh:
            fh.write("".join("line %d\n" % i for i in range(100)))
        run(*self.base, "--step", "t", "--status", "ok", "--outcome-from-log", log)
        text = self.read()
        self.assertIn("> line 99", text)
        self.assertIn("> line 97", text)
        self.assertNotIn("line 96", text)

    def test_outcome_from_log_relative_to_run_dir(self):
        steps = os.path.join(self.root, ".crew", "runs", "issue-85", "r1", "steps")
        os.makedirs(steps)
        with open(os.path.join(steps, "unit.log"), "w") as fh:
            fh.write("a\nb\nrun-dir tail\n")
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as elsewhere:
            os.chdir(elsewhere)  # not the run dir, not the root
            try:
                run(*self.base, "--step", "t", "--status", "ok",
                    "--outcome-from-log", "steps/unit.log")
            finally:
                os.chdir(cwd)
        self.assertIn("> run-dir tail", self.read())

    def test_tail_of_large_file_bounded(self):
        log = os.path.join(self.root, "big.log")
        with open(log, "w") as fh:
            fh.write("".join("filler %d\n" % i for i in range(200000)))
            fh.write("\n\nlast-1\n   \nlast-2\nlast-3\n\n")
        self.assertEqual(ss.tail_of(log), "last-1\nlast-2\nlast-3")
        with open(os.path.join(self.root, "short.log"), "w") as fh:
            fh.write("only\n")
        self.assertEqual(ss.tail_of(os.path.join(self.root, "short.log")), "only")
        # Reads stay bounded: far fewer bytes than the file size.
        reads = []
        real_open = open
        def spy(*a, **k):
            fh = real_open(*a, **k)
            orig = fh.read
            fh.read = lambda n=-1: (reads.append(n), orig(n))[1]
            return fh
        ss.open = spy
        try:
            ss.tail_of(log)
        finally:
            del ss.open
        self.assertTrue(reads and all(0 < n <= ss.TAIL_BLOCK for n in reads))
        self.assertLessEqual(sum(reads), ss.TAIL_MAX_BYTES)

    def read_total(self, path):
        reads, real_open = [], open
        def spy(*a, **k):
            fh = real_open(*a, **k)
            orig = fh.read
            fh.read = lambda n=-1: (reads.append(n), orig(n))[1]
            return fh
        ss.open = spy
        try:
            out = ss.tail_of(path)
        finally:
            del ss.open
        self.assertTrue(all(n > 0 for n in reads))
        self.assertLessEqual(sum(reads), ss.TAIL_MAX_BYTES)
        return out

    def test_tail_of_single_long_line_bounded(self):
        log = os.path.join(self.root, "one.log")
        with open(log, "w") as fh:
            fh.write("head\n" + "x" * (8 << 20))
        out = self.read_total(log)
        self.assertTrue(out and set(out) == {"x"})
        self.assertLessEqual(len(out), ss.TAIL_MAX_BYTES)
        run(*self.base, "--step", "t", "--status", "fail", "--outcome-from-log", log)
        self.assertIn("> " + "x" * 10, self.read())

    def test_tail_of_whitespace_tail_bounded(self):
        log = os.path.join(self.root, "ws.log")
        with open(log, "w") as fh:
            fh.write("real\n" + " \n" * (4 << 20))
        self.assertEqual(self.read_total(log), "")
        with open(log, "w") as fh:
            fh.write("real\n" + "\n" * (8 << 20))
        self.assertEqual(self.read_total(log), "")

    def test_tail_of_cut_first_line_dropped(self):
        log = os.path.join(self.root, "cut.log")
        with open(log, "w") as fh:
            fh.write("y" * 100000 + "\na\nb\nc\n")
        self.assertEqual(self.read_total(log), "a\nb\nc")

    def test_dot_identifiers_rejected(self):
        for ref, rid in (("..", "r1"), (".", "r1"), ("issue-85", "."),
                         ("issue-85", ".."), ("...", "r1")):
            with self.assertRaises(SystemExit):
                ss.main(["--root", self.root, "--ref", ref, "--run-id", rid,
                         "--step", "s", "--status", "ok"])
        self.assertFalse(os.path.exists(os.path.join(self.root, ".crew")))

    def test_outcome_from_log_containment(self):
        rdir = os.path.join(self.root, ".crew", "runs", "issue-85", "r1")
        os.makedirs(os.path.join(rdir, "steps"))
        outside = os.path.join(self.root, "x.log")
        with open(outside, "w") as fh:
            fh.write("outside secret tail\n")
        os.symlink(outside, os.path.join(rdir, "steps", "link.log"))
        for rel in ("../x.log", "../../../../x.log", "steps/link.log"):
            with self.assertRaises(SystemExit, msg=rel):
                ss.main([*self.base, "--step", "t", "--status", "ok",
                         "--outcome-from-log", rel])
        run(*self.base, "--step", "abs", "--status", "ok",
            "--outcome-from-log", outside)
        self.assertIn("> outside secret tail", self.read())

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
