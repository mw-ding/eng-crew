#!/usr/bin/env python3
"""Offline self-test for scripts/metrics-refresh.py (no network).

Covers the metrics parsing logic. Run in CI.
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "metrics_refresh", os.path.join(HERE, "metrics-refresh.py"))
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)

SHA1, SHA2 = "a" * 40, "b" * 40


def marker(role, step, rnd, sha, verdict="n/a"):
    return "<!-- crew:v1 role=%s pass=%s pr=1 sha=%s round=%s verdict=%s -->" % (
        role, step, sha, rnd, verdict)


class MetricsTest(unittest.TestCase):
    def test_marker_must_be_whole_line(self):
        body = "see `<!-- crew:v1 role=builder pass=fix -->` inline\n" + marker(
            "builder", "fix", 1, SHA1)
        self.assertEqual(len(mr.parse_markers(body)), 1)

    def test_review_metrics(self):
        reviews = [
            {"body": "x\n" + marker("builder", "ci-fix", 1, SHA1)},
            {"body": marker("builder", "ci-fix", 1, SHA1)},  # duplicate
            {"body": marker("builder", "ci-fix", 2, SHA2)},
            {"body": marker("builder", "fix", 1, SHA1)},
            {"body": marker("reviewer-validator", "verdict", 1, SHA1, "changes")},
            {"body": marker("reviewer-validator", "verdict", 2, SHA2, "pass")},
            {"body": marker("reviewer-validator", "review", 2, SHA2, "pass")},
            {"body": None},
        ]
        self.assertEqual(mr.review_metrics(reviews), {
            "ci_fix_rounds": 2, "builder_fix_rounds": 1,
            "verdicts": 2, "changes_verdicts": 1})

    def test_crew_pr_definition(self):
        self.assertTrue(mr.is_crew_pr(
            "<!-- crew:v1 role=builder issue=1 tier=default -->", []))
        self.assertTrue(mr.is_crew_pr("", ["crew:approved"]))
        self.assertFalse(mr.is_crew_pr("plain", ["bug"]))

    def test_row(self):
        pr = {"number": 7, "created_at": "2026-10-26T00:00:00Z",
              "merged_at": "2026-10-26T01:30:00Z"}
        row = mr.build_row("o/r", pr, [], [{"event": "reopened"}])
        self.assertEqual(row["open_to_merge_min"], 90)
        self.assertEqual(row["state"], "merged")
        self.assertEqual(row["reopened"], "reopened")
        closed = mr.build_row("o/r", dict(pr, merged_at=None), [], [])
        self.assertEqual((closed["state"], closed["open_to_merge_min"],
                          closed["reopened"]), ("closed", "", ""))

    def test_sort_is_numeric(self):
        rows = [{"repo": "b", "pr": 2}, {"repo": "a", "pr": 10}, {"repo": "a", "pr": 9}]
        self.assertEqual([(r["repo"], r["pr"]) for r in mr.sort_rows(rows)],
                         [("a", 9), ("a", 10), ("b", 2)])


if __name__ == "__main__":
    unittest.main()
