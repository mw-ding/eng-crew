#!/usr/bin/env python3
"""CLI tests for scripts/check-pr-linkage.py (offline, temp files only).

Covers a clean body, a matching and a stale allocation, a missing citation,
unintended closing keywords (descriptive, URL, cross-repo, duplicate), a
two-issue PR and the release-only form (#1418, #1416). Run in CI.
"""
import os
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts", "check-pr-linkage.py")
ALLOC = "https://github.com/o/r/issues/879#issuecomment-1"


def body(*lines):
    return "\n".join(["## Context", "", "Allocation: " + ALLOC, "", *lines, "", "## Changes Made", ""])


class CheckPrLinkageTest(unittest.TestCase):
    def run_check(self, text, *argv):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "body.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            out = subprocess.run([sys.executable, SCRIPT, "--body-file", path, *argv],
                                 capture_output=True, text=True)
        return out.returncode, out.stdout, out.stderr

    def test_matching_allocation_passes(self):
        code, out, err = self.run_check(body("Closes #879"), "--closes", "879", "--allocation", ALLOC)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, "check-pr-linkage: OK (closing line for #879; allocation cited)\n")
        self.assertEqual(self.run_check(body("Closes #879", out), "--closes", "879", "--allocation", ALLOC)[1], out)

    def test_stale_allocation_flags_both_lines(self):
        # #950: the body kept the old link after the allocation moved the issue.
        code, out, _ = self.run_check(body("Closes #900"), "--closes", "879", "--allocation", ALLOC)
        self.assertEqual(code, 1)
        self.assertIn("line 5: closing keyword `Closes` before `#900` outside the intended closing line", out)
        self.assertIn("no whole `Closes` line for #879, the issue the allocation gives this PR", out)

    def test_part_of_instead_of_closes_fails(self):
        code, out, _ = self.run_check(body("Part of #879"), "--closes", "879", "--allocation", ALLOC)
        self.assertEqual(code, 1)
        self.assertIn("no whole `Closes` line for #879", out)

    def test_uncited_allocation_fails(self):
        code, out, _ = self.run_check("Closes #879\n", "--closes", "879", "--allocation", ALLOC)
        self.assertEqual(code, 1)
        self.assertIn("the body does not cite the allocation " + ALLOC, out)

    def test_descriptive_closing_phrases_flagged(self):
        # #1094: a table phrase `closed #20` became a closing reference.
        text = body("Closes #879", "| A22 | closed #20 |",
                    "Fixes: https://github.com/o/r/issues/7 and resolves o/other#3.", "Closes #879")
        code, out, _ = self.run_check(text, "--closes", "879", "--allocation", ALLOC)
        self.assertEqual(code, 1)
        self.assertIn("line 6: closing keyword `closed` before `#20`", out)
        self.assertIn("line 7: closing keyword `Fixes` before `https://github.com/o/r/issues/7`", out)
        self.assertIn("line 7: closing keyword `resolves` before `o/other#3`", out)
        self.assertIn("line 8: closing keyword `Closes` before `#879`", out)
        self.assertEqual(out.count("check-pr-linkage: "), 4)
        # Pasting the findings into a PR body adds no closing reference of its own.
        _, again, _ = self.run_check(body("Closes #879", out), "--closes", "879", "--allocation", ALLOC)
        self.assertEqual(again, "check-pr-linkage: OK (closing line for #879; allocation cited)\n")

    def test_plain_mentions_pass(self):
        text = body("Closes #879", "Follows #20, now closed; see the fix in #21 and close-out #22.")
        code, out, _ = self.run_check(text, "--closes", "879", "--allocation", ALLOC)
        self.assertEqual(code, 0, out)

    def test_two_issue_pr(self):
        text = body("Closes #431", "Closes #1291")
        code, out, _ = self.run_check(text, "--closes", "431", "--closes", "1291", "--allocation", ALLOC)
        self.assertEqual(code, 0, out)
        self.assertIn("closing line for #431, #1291", out)

    def test_release_form_passes_and_flags_keywords(self):
        ok = "Refs #1700\n\nRelease issue: #1700\n"
        self.assertEqual(self.run_check(ok, "--release", "1700")[:2],
                         (0, "check-pr-linkage: OK (release issue #1700)\n"))
        code, out, _ = self.run_check("Closes #1700\nRelease issue: #1700\n", "--release", "1700")
        self.assertEqual(code, 1)
        self.assertIn("line 1: closing keyword `Closes` before `#1700`", out)
        self.assertIn("no `Refs #1700`", out)

    def test_usage_errors(self):
        code, _, err = self.run_check("Closes #1\n", "--closes", "1")
        self.assertEqual(code, 2)
        self.assertIn("--closes needs --allocation", err)
        code, _, err = self.run_check("x", "--closes", "1", "--release", "2", "--allocation", ALLOC)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
