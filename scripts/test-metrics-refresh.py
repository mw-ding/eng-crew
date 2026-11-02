#!/usr/bin/env python3
"""Offline self-test for scripts/metrics-refresh.py (no network).

Covers the metrics parsing logic. Run in CI.
"""
import importlib.util
import os
import csv
import json
import subprocess
import sys
import tempfile
from unittest.mock import patch
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

    def test_precheck_comparison(self):
        precheck = marker("builder", "precheck", "n/a", SHA1)
        changes = marker("reviewer-validator", "verdict", 1, SHA1, "changes")
        passed = marker("reviewer-validator", "verdict", 2, SHA2, "pass")
        pr = {"number": 1, "created_at": "2026-10-26T00:00:00Z",
              "merged_at": "2026-10-26T01:30:00Z", "body": precheck}
        rows = [mr.build_row("o/r", pr, [{"body": changes}, {"body": changes},
                                       {"body": passed}], []),
                mr.build_row("o/r", dict(pr, number=2, body="", merged_at=None),
                             [{"body": precheck}, {"body": passed}], []),
                mr.build_row("o/r", dict(pr, number=3, body="see `" + precheck + "`"),
                             [{"body": changes}], []),
                mr.build_row("o/r", dict(pr, number=4, body="", merged_at=None), [], [])]
        self.assertEqual([r["precheck"] for r in rows],
                         ["recorded", "recorded", "unrecorded", "unrecorded"])
        markdown = mr.render_md(rows, ["o/r", "empty/r"], "2026-10-26", "now")
        self.assertIn("| o/r | recorded | 2 | 3 | 1.50 | 33.33% | 1 | 90.00 |", markdown)
        self.assertIn("| o/r | unrecorded | 2 | 1 | 0.50 | 100.00% | 1 | 90.00 |", markdown)
        self.assertIn("| empty/r | recorded | 0 | 0 | n/a | n/a | 0 | n/a |", markdown)
        self.assertIn("| empty/r | unrecorded | 0 | 0 | n/a | n/a | 0 | n/a |", markdown)
        no_verdicts = mr.render_md(rows[-1:], ["o/r"], "2026-10-26", "now")
        self.assertIn("| o/r | unrecorded | 1 | 0 | 0.00 | n/a | 0 | n/a |", no_verdicts)
        print("precheck comparison: recorded rounds=1.50 changes=33.33% merge=90.00 min; "
              "unrecorded rounds=0.50 changes=100.00%; empty denominators=n/a")

    def test_flavor_uses_latest_verdict_at_head(self):
        def verdict(sha, flavor):
            return {"body": marker("reviewer-validator", "verdict", 1, sha, "pass")
                    .replace(" -->", " flavor=" + flavor + " -->")}
        reviews = [verdict(SHA2, "standard"), verdict(SHA1, "fast"),
                   verdict(SHA2, "custom-docs")]
        self.assertEqual(mr.flavor_at_head(reviews, SHA2), "custom-docs")
        self.assertEqual(mr.flavor_at_head(reviews, "c" * 40), "")
        reviews.append({"body": marker("reviewer-validator", "verdict", 2, SHA2, "pass")})
        self.assertEqual(mr.flavor_at_head(reviews, SHA2), "")
        row = mr.build_row("o/r", {"number": 1, "created_at": "2026-10-26T00:00:00Z"}, [], [])
        self.assertEqual((row["flavor"], row["engine_runs"], row["escaped_defects"]), ("", "", 0))

    def test_escaped_defects_are_distinct_issues_and_exact_references(self):
        issues = [
            {"html_url": "https://github.com/control/crew/issues/1",
             "body": "Escaped from: O/R#7\r\nEscaped from: O/R#7\r\nEscaped from: o/r#8"},
            {"html_url": "https://github.com/o/r/issues/2", "body": "Escaped from: o/r#7"},
            {"html_url": "https://github.com/o/r/issues/3", "body": None},
            {"html_url": "https://github.com/o/r/pull/4", "pull_request": {},
             "body": "Escaped from: o/r#7"},
            {"html_url": "https://github.com/o/r/issues/5",
             "body": "see Escaped from: o/r#7\nEscaped from: o/r#7 extra\nEscaped from: o/r#0"},
        ]
        self.assertEqual(mr.escaped_counts(issues + issues[:1]), {("o/r", 7): 2, ("o/r", 8): 1})

    def test_engine_runs_distinct_per_range_and_section(self):
        commits = [
            {"sha": "0" * 40, "commit": {"message": "build\n\nEngine: codex m medium"}},
            {"sha": SHA1, "commit": {"message": "finish\n\nEngine: codex m medium"}},
            {"sha": SHA2, "commit": {"message": "fix\n\nEngine: codex m medium\nEngine: claude-code s high"}},
            {"sha": "c" * 40, "commit": {"message": "merge\n\nEngine: none (pure merge-up, plain git)"}},
        ]
        body = ("## Review\n" + marker("reviewer-validator", "review", 1, SHA1, "pass")
                + "\n*Reviewed by Vera (claude-code, opus, high)*\n## Validation\n"
                + "Validation engine: claude-code opus high.\n"
                + marker("reviewer-validator", "validate", 1, SHA1, "pass") + "\n"
                + marker("reviewer-validator", "verdict", 1, SHA1, "pass"))
        reviews = [{"body": body}, {"body": body},
                   {"body": marker("builder", "fix", 1, SHA2)},
                   {"body": marker("reviewer-validator", "ack", 1, SHA2)},
                   {"body": "## Review\n" + marker("reviewer-validator", "review", 2, SHA2, "changes")
                    .replace(" -->", " engine=muse model=m -->") + "\n"
                    + marker("reviewer-validator", "verdict", 2, SHA2, "changes")}]
        self.assertEqual(mr.engine_runs(commits, reviews), 6)  # 3 builder + 3 reviewer
        review_only = ("*Reviewed by Vera (muse, m, high)*\n"
                       + marker("reviewer-validator", "review", 1, SHA1) + "\n"
                       + marker("reviewer-validator", "validate", 1, SHA1))
        self.assertEqual(mr.engine_runs([], [{"body": review_only}]), 1)
        self.assertEqual(mr.engine_runs(commits, []), 2)
        self.assertEqual(mr.engine_runs(commits[-1:], []), "")
        self.assertEqual(mr.engine_runs([], [{"body": marker("reviewer-validator", "verdict", 1, SHA1)}]), "")

    def test_api_pagination_and_single_object(self):
        for payload, expected in (('[1,2]\n[3]', [1, 2, 3]),
                                  ('{"items":[1]}\n{"items":[2]}', [1, 2]),
                                  ('{"number":7}', {"number": 7})):
            with patch.object(mr.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 0, payload, "")):
                self.assertEqual(mr.gh_json("fixture"), expected)

    def test_cli_csv_and_markdown_with_fake_github(self):
        reviews = [{"body": "## Review\n*Reviewed by Vera (muse, m, high)*\n"
                    + marker("reviewer-validator", "review", 1, SHA2, "pass")
                    + "\n## Validation\n*Validated by Vera (muse, m, high)*\n"
                    + marker("reviewer-validator", "validate", 1, SHA2, "pass") + "\n"
                    + marker("reviewer-validator", "verdict", 1, SHA2, "pass")
                    .replace(" -->", " flavor=standard -->")}]
        hits = [{"number": 7, "body": "<!-- crew:v1 role=builder issue=7 -->"},
                {"number": 8, "labels": [{"name": "crew:in-review"}]},
                {"number": 9, "body": "not a crew PR"}]
        defect = {"html_url": "https://github.com/control/crew/issues/1",
                  "body": "Escaped from: o/r#7"}
        data = {"prs": {"items": hits}, "defects": {"items": [defect]},
                "repos/o/r/pulls/7/reviews": reviews, "repos/o/r/issues/7/events": [],
                "repos/o/r/pulls/7/commits": [
                    {"sha": SHA2, "commit": {"message": "build\n\nEngine: codex m medium"}}],
                "repos/o/r/pulls/7": {"number": 7, "created_at": "2026-10-26T00:00:00Z",
                    "body": marker("builder", "precheck", "n/a", SHA2),
                    "merged_at": "2026-10-26T01:30:00Z", "head": {"sha": SHA2}},
                "repos/o/r/pulls/8/reviews": [], "repos/o/r/issues/8/events": [],
                "repos/o/r/pulls/8/commits": [],
                "repos/o/r/pulls/8": {"number": 8, "created_at": "2026-10-26T00:00:00Z",
                    "merged_at": None, "head": {"sha": SHA1}}}
        with tempfile.TemporaryDirectory() as tmp:
            fixture = os.path.join(tmp, "github.json")
            with open(fixture, "w") as f:
                json.dump(data, f)
            fake_gh = os.path.join(tmp, "gh")
            with open(fake_gh, "w") as f:
                f.write("#!" + sys.executable + "\n" +
                        "import json, os, sys\n"
                        "with open(os.environ['METRICS_FIXTURE']) as f: data = json.load(f)\n"
                        "path = sys.argv[5]\n"
                        "if path == 'search/issues':\n"
                        "    path = 'defects' if 'Escaped from:' in ' '.join(sys.argv) else 'prs'\n"
                        "print(json.dumps(data[path]))\n")
            os.chmod(fake_gh, 0o755)
            result = subprocess.run([sys.executable, os.path.join(HERE, "metrics-refresh.py"),
                "--repo", "o/r", "--since", "2026-10-26", "--out-dir", tmp],
                env=dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], METRICS_FIXTURE=fixture),
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "o/r: 2 crew PRs\n")
            with open(os.path.join(tmp, "prs.csv")) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(reader.fieldnames, mr.FIELDS)
            self.assertEqual((rows[0]["flavor"], rows[0]["escaped_defects"], rows[0]["engine_runs"]),
                             ("standard", "1", "3"))
            self.assertEqual((rows[0]["state"], rows[0]["open_to_merge_min"]), ("merged", "90"))
            self.assertEqual([r["precheck"] for r in rows], ["recorded", "unrecorded"])
            self.assertEqual((rows[1]["state"], rows[1]["flavor"], rows[1]["engine_runs"]),
                             ("closed", "", ""))
            with open(os.path.join(tmp, "prs.md")) as f:
                markdown = f.read()
            self.assertIn("| " + " | ".join(mr.FIELDS) + " |", markdown)
            self.assertIn("| " + " | ".join(rows[0][k] for k in mr.FIELDS) + " |", markdown)
            self.assertIn("| o/r | recorded | 1 | 1 | 1.00 | 0.00% | 1 | 90.00 |", markdown)
            self.assertIn("| o/r | unrecorded | 1 | 0 | 0.00 | n/a | 0 | n/a |", markdown)
            print("offline CLI: flavor=standard escaped_defects=1 engine_runs=3; legacy blanks preserved")

    def test_sort_is_numeric(self):
        rows = [{"repo": "b", "pr": 2}, {"repo": "a", "pr": 10}, {"repo": "a", "pr": 9}]
        self.assertEqual([(r["repo"], r["pr"]) for r in mr.sort_rows(rows)],
                         [("a", 9), ("a", 10), ("b", 2)])


if __name__ == "__main__":
    unittest.main()
