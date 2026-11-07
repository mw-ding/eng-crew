#!/usr/bin/env python3
"""Offline self-test for scripts/metrics-baseline.py (no network). Run in CI."""
import importlib.util
import os
import unittest
from unittest.mock import patch

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
spec = importlib.util.spec_from_file_location("metrics_baseline", os.path.join(SCRIPTS, "metrics-baseline.py"))
mb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mb)

SHA1, SHA2 = "a" * 40, "b" * 40


def review(at, role, step, rnd="n/a", sha=SHA1, verdict="n/a"):
    return {"submitted_at": at, "body": "x\n<!-- crew:v1 role=%s pass=%s pr=1 sha=%s round=%s verdict=%s -->" % (
        role, step, sha, rnd, verdict)}


PR = {"number": 7, "created_at": "2026-11-04T10:00:00Z", "merged_at": "2026-11-04T12:00:00Z",
      "body": "## Context\n\nCloses #5\n"}
ISSUE = {"number": 5, "created_at": "2026-11-04T09:00:00Z", "milestone": {"number": 38, "title": "M25"}}
REVIEWS = [
    review("2026-11-04T10:02:00Z", "reviewer-validator", "ack"),
    review("2026-11-04T10:10:00Z", "reviewer-validator", "verdict", 1, SHA1, "changes"),
    review("2026-11-04T10:20:00Z", "builder", "fix", 1, SHA2),
    review("2026-11-04T10:30:00Z", "reviewer-validator", "ack"),  # merge-up ack after a verdict
    review("2026-11-04T11:00:00Z", "reviewer-validator", "verdict", 2, SHA2, "pass"),
    {"submitted_at": "2026-11-04T10:05:00Z",
     "body": "mentions `<!-- crew:v1 role=reviewer-validator pass=verdict -->` inline"},
]
COMMITS = [{"sha": SHA1, "commit": {"message": "a\n\nEngine: claude-code opus medium"}},
           {"sha": SHA2, "commit": {"message": "b\n\nEngine: codex gpt high"}}]


class BaselineTest(unittest.TestCase):
    def test_closing_issue(self):
        self.assertEqual(mb.closing_issue(PR["body"]), 5)
        self.assertEqual(mb.closing_issue("fixes #12 later\nResolves #9"), 12)
        self.assertIsNone(mb.closing_issue("see #5"))

    def test_pr_row(self):
        row = mb.pr_row(PR, ISSUE, REVIEWS, COMMITS)
        self.assertEqual(row["issue_to_pr_min"], 60)
        self.assertEqual(row["ack_latency_min"], 2)
        self.assertEqual(row["pr_to_first_verdict_min"], 10)
        self.assertEqual(row["verdict_to_land_min"], 60)
        self.assertEqual((row["rounds"], row["defects"], row["state"]), (2, 1, "merged"))
        self.assertEqual(row["engine_runs"], 2)

    def test_unmerged_no_issue_no_markers(self):
        pr = dict(PR, merged_at=None, body="")
        row = mb.pr_row(pr, None, [], [])
        self.assertEqual(row["state"], "closed")
        for key in ("issue", "issue_to_pr_min", "pr_to_first_verdict_min", "verdict_to_land_min",
                    "ack_latency_min", "engine_runs"):
            self.assertEqual(row[key], "", key)
        self.assertEqual((row["rounds"], row["defects"]), (0, 0))

    def test_ack_after_first_verdict_ignored(self):
        row = mb.pr_row(PR, ISSUE, REVIEWS[1:], COMMITS)
        self.assertEqual(row["ack_latency_min"], "")

    def test_summarize_medians_skip_blanks(self):
        rows = [mb.pr_row(PR, ISSUE, REVIEWS, COMMITS),
                mb.pr_row(dict(PR, merged_at=None), None, [], [])]
        stats = {key: (shown, n) for key, _, _, shown, n in mb.summarize(rows)}
        self.assertEqual(stats["verdict_to_land_min"], ("60", 1))
        self.assertEqual(stats["rounds"], ("1", 2))
        self.assertEqual(stats["defects"], ("0.5", 2))
        self.assertEqual(mb.summarize([])[0][3:], ("n/a", 0))

    def test_render(self):
        text = mb.render([mb.pr_row(PR, ISSUE, REVIEWS, COMMITS)], "o/r", "2026-11-03", "2026-11-07",
                         "#38 M25", "2026-11-07 08:00 UTC")
        self.assertIn("closing issue in milestone #38 M25", text)
        self.assertIn("| Handoff ack latency (min) | 2 | 1 |", text)
        self.assertIn("PRs: 1 (1 merged). Defects caught in total: 1.", text)
        self.assertIn("| 7 | 5 | merged | 60 | 10 | 60 | 2 | 2 | 1 | 2 |", text)

    def test_collect_filters_crew_and_milestone(self):
        hits = [
            {"number": 7, "body": "Closes #5\n<!-- crew:v1 role=builder issue=5 -->", "labels": []},
            {"number": 8, "body": "Closes #6", "labels": [{"name": "crew:in-review"}]},
            {"number": 9, "body": "Closes #5", "labels": []},  # not a crew PR
        ]
        other = dict(ISSUE, number=6, milestone={"number": 44, "title": "M25.1"})
        responses = {"repos/o/r/issues/5": ISSUE, "repos/o/r/issues/6": other,
                     "repos/o/r/pulls/7": PR, "repos/o/r/pulls/7/reviews": REVIEWS,
                     "repos/o/r/pulls/7/commits": COMMITS}
        calls = []

        def fake(path, *params):
            calls.append((path,) + params)
            return hits if path == "search/issues" else responses[path]
        with patch.object(mb.mr, "gh_json", side_effect=fake):
            rows, title = mb.collect("o/r", "2026-11-03", "2026-11-07", 38)
        self.assertEqual([r["pr"] for r in rows], [7])
        self.assertEqual(title, "M25")
        self.assertIn("q=repo:o/r is:pr is:closed closed:2026-11-03..2026-11-07", calls[0])
        self.assertNotIn(("repos/o/r/pulls/8",), calls)


if __name__ == "__main__":
    unittest.main()
