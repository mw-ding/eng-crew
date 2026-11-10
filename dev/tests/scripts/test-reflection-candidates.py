#!/usr/bin/env python3
"""Offline self-test for scripts/reflection-candidates.py (no network).

Builds each evidence index with the real reflection-scan.py, then checks threshold selection (3 distinct incidents of
one class, a findings row at count 3); fixed rows and patterns giving no new work without a fresh occurrence after
the fix, and a regression when one came; a closed card of one counted incident not blocking the pattern card;
existing open work getting only missing evidence, and nothing once an interrupted run's card cites it all; the real
#1398 card, which already names its three sites; and missing inputs listed, malformed input exit 2 (#1522). Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
FIX = os.path.join(TESTS, "scripts", "fixtures", "reflection")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = load("reflection_scan", "reflection-scan.py")
rc = load("reflection_candidates", "reflection-candidates.py")
WINDOW = ["--since", "2026-11-01T00:00:00Z", "--until", "2026-11-08T00:00:00Z"]
U = "https://github.com/o/r/"


def item(n, created, body="", state="OPEN", closed=None, kind="issues", comments=()):
    return {"number": n, "url": "%s%s/%d" % (U, kind, n), "state": state, "title": "item %d" % n, "labels": [],
            "createdAt": created, "closedAt": closed, "body": body,
            "comments": [{"body": c, "createdAt": closed or created, "url": "%sissues/%d#c" % (U, n)}
                         for c in comments]}


def card(n, source, created, cls="flaky-ci", **kw):
    return item(n, created, "**Source:** o/r#%d\n**Failure class:** %s\n" % (source, cls), **kw)


def pr(n, closed):
    return item(n, "2026-10-01T00:00:00Z", state="MERGED", closed=closed, kind="pull")


def fixed_cards():
    """Three flaky-ci incidents on PRs #1-#3, each card closed by its own fix in the window."""
    return [pr(n, "2026-10-02T00:00:00Z") for n in (1, 2, 3)] + [
        card(10, 1, "2026-11-02T00:00:00Z", state="CLOSED", closed="2026-11-02T06:00:00Z"),
        card(11, 2, "2026-11-04T00:00:00Z", state="CLOSED", closed="2026-11-04T06:00:00Z"),
        card(12, 3, "2026-11-05T00:00:00Z", state="CLOSED", closed="2026-11-05T06:00:00Z")]


def candidates(items, buffer=None, window=WINDOW, forge=True):
    """Run the scan on `items`, then the helper on its index; returns (exit code, result or stderr)."""
    with tempfile.TemporaryDirectory() as d:
        snap, index = os.path.join(d, "forge.json"), os.path.join(d, "index.json")
        with open(snap, "w") as f:
            json.dump(items, f)
        with contextlib.redirect_stdout(io.StringIO()):
            assert rs.main(window + ["--forge", snap, "--out", index]) == 0
        argv = ["--index", index] + (["--forge", snap] if forge else [])
        if buffer is not None:
            argv += ["--buffer", os.path.join(d, "buffer.md")]
            with open(argv[-1], "w") as f:
                f.write(buffer)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rc.main(argv)
    return code, json.loads(out.getvalue()) if code == 0 else err.getvalue()


def only(items, **kw):
    code, got = candidates(items, **kw)
    assert code == 0, got
    assert len(got["candidates"]) == 1, got["candidates"]
    return got["candidates"][0]


def row(count, status="buffered", date="2026-11-05", refs="o/r#1, o/r#2, o/r#3"):
    return ("# Findings buffer\n\n## Entries\n\n### CI flakes on retry\n\n- **Date:** %s\n- **PR / repo:** %s\n"
            "- **Smell:** a retry passes.\n- **Count:** %d\n- **Proposed fix layer:** CI check\n- **Status:** %s\n"
            % (date, refs, count, status))


class ClassThreshold(unittest.TestCase):
    def test_three_individually_fixed_incidents_file_a_pattern_card(self):
        got = only(fixed_cards())
        self.assertEqual((got["basis"], got["class"], got["count"], got["action"]), ("class", "flaky-ci", 3, "file"))
        self.assertEqual(got["incidents"], ["ri-o-r-1", "ri-o-r-2", "ri-o-r-3"])
        self.assertEqual(got["proposal_prefix"], "rp-flaky-ci-")

    def test_two_incidents_are_below_the_threshold(self):
        code, got = candidates(fixed_cards()[:-1])
        self.assertEqual((code, got["candidates"]), (0, []))

    def test_fixed_pattern_needs_a_fresh_occurrence(self):
        fix = item(5, "2026-10-20T00:00:00Z", "**Proposed fix:** rp-flaky-ci-scripts-ci-py: retry once.",
                   state="CLOSED", closed="2026-11-07T00:00:00Z")
        got = only(fixed_cards() + [fix])
        self.assertEqual((got["action"], got["match"]), ("skip", U + "issues/5"))
        fix["closedAt"] = "2026-11-03T00:00:00Z"
        got = only(fixed_cards() + [fix])
        self.assertEqual((got["action"], got["regression_of"]), ("file", U + "issues/5"))
        self.assertEqual(got["fresh"], ["ri-o-r-2", "ri-o-r-3"])

    def test_open_card_gets_only_missing_evidence_then_nothing(self):
        mine = item(20, "2026-11-06T00:00:00Z", "**Proposed fix:** rp-flaky-ci-scripts-ci-py: ri-o-r-1, o/r#2")
        got = only(fixed_cards() + [mine])
        self.assertEqual((got["action"], got["match"], got["new"]), ("append", U + "issues/20", ["ri-o-r-3"]))
        mine["comments"] = [{"body": "[Riley/reflection-evidence] week-2026-W45: o/r#3", "url": U + "issues/20#c"}]
        got = only(fixed_cards() + [mine])
        self.assertEqual((got["action"], got["new"]), ("none", []))

    def test_real_1398_card_already_names_its_three_sites(self):
        code, got = candidates(rs.load(os.path.join(FIX, "forge-20261109T1300Z.json")),
                               window=["--since", "2026-11-08T21:00:00Z", "--until", "2026-11-09T13:00:00Z"])
        self.assertEqual(code, 0)
        self.assertEqual([(c["class"], c["count"], c["action"], c["match"]) for c in got["candidates"]],
                         [("conflicting-pr-gets-no-ci", 3, "none",
                           "https://github.com/mw-ding/mdstack/issues/1398")])


class FindingsThreshold(unittest.TestCase):
    def test_row_at_count_three_files_and_below_does_not(self):
        got = only([], buffer=row(3))
        self.assertEqual((got["basis"], got["class"], got["action"]), ("findings", "ci-flakes-on-retry", "file"))
        code, got = candidates([], buffer=row(2))
        self.assertEqual(got["candidates"], [])

    def test_fixed_row_needs_a_fresh_post_fix_occurrence(self):
        fix = pr(30, "2026-11-06T00:00:00Z")
        got = only([fix], buffer=row(4, "fixed by #30"))
        self.assertEqual((got["action"], got["reason"]), ("skip", "closed o/r#30, no occurrence after"))
        got = only([fix], buffer=row(4, "fixed by #30", date="2026-11-07"))
        self.assertEqual((got["action"], got["regression_of"], got["fresh"]),
                         ("file", U + "pull/30", ["row-date-2026-11-07"]))
        fix["closedAt"] = "2026-11-03T00:00:00Z"
        code, got = candidates([fix] + fixed_cards(), buffer=row(4, "applied by #30", date="2026-11-02"))
        got = [c for c in got["candidates"] if c["basis"] == "findings"][0]
        self.assertEqual((got["action"], got["fresh"]), ("file", ["ri-o-r-2", "ri-o-r-3"]))

    def test_fixed_row_regression_reconciles_a_filed_card(self):
        fix = pr(30, "2026-11-06T00:00:00Z")
        later = row(4, "fixed by #30", date="2026-11-07")
        mine = item(40, "2026-11-07T12:00:00Z", "**Failure class:** ci-flakes-on-retry\n"
                    "**Proposed fix:** rp-ci-flakes-on-retry-scripts-ci-py\nEvidence: o/r#1, o/r#2")
        got = only([fix, mine], buffer=later)
        self.assertEqual((got["action"], got["match"], got["new"], got["regression_of"]),
                         ("append", U + "issues/40", ["o/r#3"], U + "pull/30"))
        mine["body"] += ", o/r#3"
        got = only([fix, mine], buffer=later)
        self.assertEqual((got["action"], got["new"]), ("none", []))
        mine.update(state="CLOSED", closedAt="2026-11-07T18:00:00Z")
        got = only([fix, mine], buffer=later)
        self.assertEqual((got["action"], got["match"]), ("skip", U + "issues/40"))
        self.assertNotIn("regression_of", got)
        got = only([fix, mine], buffer=row(4, "fixed by #30", date="2026-11-08"))
        self.assertEqual((got["action"], got["regression_of"], got["fresh"]),
                         ("file", U + "issues/40", ["row-date-2026-11-08"]))
        self.assertEqual(only([fix, mine], buffer=row(4, "fixed by #30"))["action"], "skip")

    def test_fixed_row_with_an_unknown_fix_is_skipped(self):
        got = only([pr(1, "2026-10-02T00:00:00Z")], buffer=row(5, "fixed by #99"))
        self.assertEqual((got["action"], got["reason"]), ("skip", "fixed by o/r#99, fix date unknown"))

    def test_batched_row_appends_new_sightings_to_its_issue(self):
        batch = item(40, "2026-10-30T00:00:00Z", "Batch: o/r#1, o/r#2")
        got = only([batch], buffer=row(3, "batched -> #40"))
        self.assertEqual((got["action"], got["match"], got["new"]), ("append", U + "issues/40", ["o/r#3"]))


class Inputs(unittest.TestCase):
    def test_missing_inputs_are_listed(self):
        code, got = candidates(fixed_cards(), forge=False)
        self.assertEqual((code, got["missing"]), (0, ["forge: not provided", "findings: no --buffer"]))

    def test_malformed_index_exits_2(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = rc.main(["--index", f.name])
        finally:
            os.remove(f.name)
        self.assertEqual(code, 2)
        self.assertIn("reflection-candidates: unreadable input", err.getvalue())


if __name__ == "__main__":
    unittest.main()
