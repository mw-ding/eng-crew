#!/usr/bin/env python3
"""Offline self-test for scripts/metrics-decide.py (fixture CSVs, no network)."""
import contextlib
import importlib.util
import io
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures", "metrics")
spec = importlib.util.spec_from_file_location(
    "metrics_decide", os.path.join(HERE, "metrics-decide.py"))
md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md)

AS_OF = "2026-10-29"
CONTROL, PRODUCT = "mw-ding/eng-crew", "mw-ding/agentconnect"


def run(name, *extra):
    """Run the CLI on a fixture; return (exit code, stdout)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = md.main(["--csv", os.path.join(FIX, name + ".csv"),
                        "--as-of", AS_OF, *extra])
    return code, out.getvalue()


class DecideTest(unittest.TestCase):
    def test_ok(self):
        code, text = run("ok")
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: OK", text)
        self.assertNotIn("TRIP", text.replace("VERDICT: OK", ""))
        self.assertIn(CONTROL, text)
        self.assertIn(PRODUCT, text)

    def test_latency_trip(self):
        code, text = run("latency-trip")
        self.assertEqual(code, 1)
        self.assertIn("VERDICT: TRIP", text)
        self.assertIn("| rollup | 8 | 200 | 8 | 98 | +105% | TRIP |", text)
        self.assertIn("## Pull requests to link", text)

    def test_latency_threshold_is_tunable(self):
        code, text = run("latency-trip", "--latency-pct", "150")
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: OK", text)

    def test_rework_trip(self):
        code, text = run("rework-trip")
        self.assertEqual(code, 1)
        self.assertIn("VERDICT: TRIP", text)
        self.assertIn("| OK | 38% | TRIP |", text)  # latency fine, rework 38%
        self.assertIn(CONTROL + "#10 (100 min, changes=3)", text)

    def test_reopen_rate_is_separate_from_rework(self):
        code, text = run("rework-trip")
        rollup = [l for l in text.splitlines() if l.startswith("| rollup")][0]
        self.assertIn("| OK | 38% | TRIP | 3 | 0 | 0% |", rollup)
        for repo in (CONTROL, PRODUCT):
            line = [l for l in text.splitlines() if l.startswith("| " + repo)][0]
            self.assertIn("| 0 | 0% |", line)
        self.assertIn("reopen rate is reported only", text)

    def test_reopen_rate_counts_reopened_prs(self):
        rows = md.load_rows(os.path.join(FIX, "reopen-only.csv"))
        cur, base = md.split_windows(rows, AS_OF, 14, 14)
        s = md.stats(cur, 3)
        self.assertEqual((s["n"], s["reopened"], s["rework"]), (6, 1, 1))
        self.assertAlmostEqual(s["reopen_rate"], 1 / 6)
        code, text = run("reopen-only")
        self.assertEqual(code, 0)  # 17% rework is under the 20% gate
        rollup = [l for l in text.splitlines() if l.startswith("| rollup")][0]
        self.assertIn("| 17% | OK | 1 | 1 | 17% |", rollup)

    def test_repo_trip_does_not_trip_rollup(self):
        code, text = run("repo-only-trip")
        self.assertEqual(code, 3)
        self.assertIn("VERDICT: FOLLOW-UP", text)
        rollup = [l for l in text.splitlines() if l.startswith("| rollup")][0]
        self.assertNotIn("TRIP", rollup)
        product = [l for l in text.splitlines() if l.startswith("| " + PRODUCT)][0]
        self.assertIn("TRIP", product)
        self.assertIn(PRODUCT + "#114", text)

    def test_empty_baseline_is_insufficient_not_trip(self):
        code, text = run("no-baseline")
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: OK", text)
        rollup = [l for l in text.splitlines() if l.startswith("| rollup")][0]
        self.assertIn("INSUFFICIENT", rollup)

    def test_too_few_prs_is_insufficient(self):
        code, text = run("insufficient")
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: INSUFFICIENT", text)

    def test_missing_csv_is_usage_error(self):
        code, _ = run("does-not-exist")
        self.assertEqual(code, 2)

    def test_reopened_counts_as_rework(self):
        row = {"reopened": True, "changes": 0}
        self.assertTrue(md.is_rework(row, 3))
        self.assertFalse(md.is_rework({"reopened": False, "changes": 2}, 3))
        self.assertTrue(md.is_rework({"reopened": False, "changes": 3}, 3))

    def test_non_positive_tuning_is_usage_error(self):
        for flag in ("--min-prs", "--window-days", "--baseline-days",
                     "--latency-pct", "--rework-pct", "--rework-changes"):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                md.main(["--csv", os.path.join(FIX, "ok.csv"), flag, "0"])
            self.assertEqual(cm.exception.code, 2, flag)
            self.assertIn("greater than 0", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())

    def test_non_finite_tuning_is_usage_error(self):
        for flag in ("--latency-pct", "--rework-pct"):
            for bad in ("nan", "inf"):
                err = io.StringIO()
                with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                    md.main(["--csv", os.path.join(FIX, "latency-trip.csv"),
                             "--as-of", AS_OF, flag, bad])
                self.assertEqual(cm.exception.code, 2, (flag, bad))
                self.assertIn("finite", err.getvalue())

    def test_windows_split_by_merge_date(self):
        rows = md.load_rows(os.path.join(FIX, "ok.csv"))
        cur, base = md.split_windows(rows, AS_OF, 14, 14)
        self.assertEqual((len(cur), len(base)), (8, 8))
        # A 7-day window starts Oct 23, so the Oct 20 rows move to the baseline.
        cur7, base7 = md.split_windows(rows, AS_OF, 7, 14)
        self.assertEqual((len(cur7), len(base7)), (0, 8))


if __name__ == "__main__":
    unittest.main()
