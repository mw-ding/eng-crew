#!/usr/bin/env python3
"""Tests for scripts/run-tests.py (offline, temp dir only).

Covers pass and fail exit codes, failing-file output capture, per-file
duration and slowest lines, serial files and a missing file. Run in CI.
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
RUNNER = os.path.join(HERE, "run-tests.py")


class RunTestsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, body):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w") as fh:
            fh.write(body)
        return path

    def run_runner(self, *args):
        proc = subprocess.run([sys.executable, RUNNER, *args], capture_output=True, text=True)
        return proc.returncode, proc.stdout

    def test_all_pass_exits_zero_and_hides_output(self):
        a = self.write("test-a.py", "print('quiet a')\n")
        b = self.write("test-b.py", "print('quiet b')\n")
        code, out = self.run_runner("-j", "2", a, b)
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"ok +\d+\.\ds  .*test-a\.py")
        self.assertRegex(out, r"ok +\d+\.\ds  .*test-b\.py")
        self.assertIn("slowest:", out)
        self.assertIn("2 files, 0 failed", out)
        self.assertNotIn("quiet a", out)

    def test_failure_exits_nonzero_and_shows_its_output(self):
        ok = self.write("test-ok.py", "print('fine')\n")
        bad = self.write("test-bad.py",
                         "import sys\nprint('to stdout')\nprint('to stderr', file=sys.stderr)\nsys.exit(3)\n")
        code, out = self.run_runner(ok, bad)
        self.assertEqual(code, 1, out)
        self.assertRegex(out, r"FAIL +\d+\.\ds  .*test-bad\.py")
        self.assertRegex(out, r"===== FAIL .*test-bad\.py \(exit 3\) =====")
        self.assertIn("to stdout", out)
        self.assertIn("to stderr", out)
        self.assertNotIn("fine", out)
        self.assertIn("2 files, 1 failed", out)

    def test_runs_in_parallel_and_lists_slowest_first(self):
        slow = self.write("test-slow.py", "import time\ntime.sleep(3.0)\n")
        fast = self.write("test-fast.py", "import time\ntime.sleep(2.0)\n")
        code, out = self.run_runner("-j", "2", "--slowest", "1", slow, fast)
        self.assertEqual(code, 0, out)
        slowest = out.split("slowest:\n", 1)[1].split("\n\n", 1)[0]
        self.assertIn("test-slow.py", slowest)
        self.assertNotIn("test-fast.py", slowest)
        wall = float(out.rsplit("failed, ", 1)[1].split("s wall", 1)[0])
        self.assertLess(wall, 4.5, out)

    def test_serial_file_runs_after_parallel_batch(self):
        spec = importlib.util.spec_from_file_location("run_tests", RUNNER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        a = self.write("test-a.py", "")
        s = self.write("test-serial.py", "")
        mod.SERIAL = {"test-serial.py"}
        order = []
        real = mod.run_one
        mod.run_one = lambda path: (order.append(os.path.basename(path)), real(path))[1]
        with contextlib.redirect_stdout(io.StringIO()):
            code = mod.main([s, a])
        self.assertEqual(code, 0)
        self.assertEqual(order, ["test-a.py", "test-serial.py"])

    def test_missing_file_is_an_error(self):
        code, _ = self.run_runner(os.path.join(self.tmp.name, "test-nope.py"))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
