"""Unit tests for conservative finite grant recognition and safe clause boundaries (#1774)."""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crew_testlib import CREW


class Scope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_loader("scope_cli", SourceFileLoader("scope_cli", CREW))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        cls.scope = cli.load("unit_grant_scope", "environments/terminal/crew.d/_grant_scope.py")

    def test_safe_boundaries_keep_nested_semicolons_and_unbalanced_text(self):
        self.assertEqual(self.scope.clauses("one (two; three); four"), ["one (two; three)", " four"])
        self.assertEqual(self.scope.clauses("one (two; three; four"), ["one (two; three; four"])

    def test_finite_multiple_sources_and_foreign_locator(self):
        value = "every M35 and M36 PRs (owner 2026-11-08, #9 comment 101, #9 comment 103)"
        self.assertEqual(self.scope.recognize(value, "acme/widgets"),
                         (["M35", "M36"], [], [("acme/widgets", "9", "101"), ("acme/widgets", "9", "103")]))
        self.assertIsNone(self.scope.recognize("M35 PRs per https://github.com/other/repo/issues/9#issuecomment-101", "acme/widgets"))


if __name__ == "__main__":
    unittest.main()
