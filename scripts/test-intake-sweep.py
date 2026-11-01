#!/usr/bin/env python3
"""Offline self-test for scripts/intake-sweep.py (no network).

Offline unittest for the intake helper on a built-in fixture. Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "intake_sweep", os.path.join(HERE, "intake-sweep.py"))
ins = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ins)

NOW = "2026-10-29T12:00:00Z"
FIELDS = ["**Source:**", "**Trigger:**", "**Failure class:**", "**Proposed fix:**",
          "**Scope:**", "**Lesson:**", "**Findings entry:**", "**Decision:**",
          "**Decided by:**"]


def pr(number, updated, labels=(), draft=False):
    return {"number": number, "title": "PR %d" % number,
            "url": "https://example.test/o/r/pull/%d" % number,
            "labels": [{"name": n} for n in labels],
            "updatedAt": updated, "isDraft": draft}


FIXTURE = [
    pr(1, "2026-10-28T00:00:00Z", ["crew:blocked"]),  # blocked, fresh
    pr(2, "2026-10-10T00:00:00Z", ["crew:in-review"]),  # stale
    pr(3, "2026-10-28T00:00:00Z", ["crew:in-review"]),  # fresh, not blocked
    pr(4, "2026-09-01T00:00:00Z", [], draft=True),  # stale draft
    pr(5, "2026-10-22T12:00:00Z"),  # exactly 7 days: not stale
]


def run(args, stdin=""):
    out = io.StringIO()
    old = ins.sys.stdin
    ins.sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out):
            code = ins.main(args)
    finally:
        ins.sys.stdin = old
    return code, out.getvalue()


class IntakeSweepTest(unittest.TestCase):
    def cards(self, **kw):
        return ins.build_cards(FIXTURE, ins.parse_time(NOW), **kw)

    def test_blocked_and_stale_produce_cards(self):
        text = "\n".join(self.cards())
        self.assertIn("#1 ", text)
        self.assertIn("#2 ", text)
        self.assertIn("blocked-pr", text)
        self.assertIn("stale-pr", text)

    def test_fresh_unlabelled_and_draft_do_not(self):
        text = "\n".join(self.cards())
        for n in (3, 4, 5):
            self.assertNotIn("o/r/pull/%d)" % n, text)
        self.assertEqual(len(self.cards()), 2)

    def test_default_scope_is_repo(self):
        for c in self.cards():
            self.assertIn("**Scope:** repo: ", c)
            self.assertIn("(triage: confirm or promote)", c)

    def test_card_has_every_template_field(self):
        template = open(os.path.join(HERE, "..", "templates",
                                     "intake-candidate.md")).read()
        for c in self.cards():
            for field in FIELDS:
                self.assertIn(field, c)
                self.assertIn(field, template)

    def test_stale_days_and_label_options(self):
        self.assertEqual(len(self.cards(stale_days=30)), 1)
        self.assertEqual(len(self.cards(label="other:label")), 1)

    def test_empty_input_prints_nothing(self):
        self.assertEqual(run(["--now", NOW], "[]"), (0, ""))
        self.assertEqual(run(["--now", NOW], ""), (0, ""))

    def test_file_and_stdin(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "prs.json")
            with open(path, "w") as fh:
                json.dump(FIXTURE, fh)
            code, out = run(["--now", NOW, path])
            self.assertEqual(code, 0)
            self.assertIn("blocked-pr", out)
        code, out = run(["--now", NOW], json.dumps(FIXTURE))
        self.assertEqual(code, 0)
        self.assertIn("stale-pr", out)

    def test_bad_json_is_a_usage_error(self):
        self.assertEqual(run(["--now", NOW], "{not json")[0], 2)


if __name__ == "__main__":
    unittest.main()
