#!/usr/bin/env python3
"""Offline item rigor tests. Usage: python3 scripts/test-item-flavor.py (run in CI)."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("item_flavor", Path(__file__).with_name("item-flavor.py"))
item = importlib.util.module_from_spec(spec)
spec.loader.exec_module(item)


def record(flavor="standard", default="thorough", reason=""):
    return (reason + "\n<!-- crew:v1 role=coordinator pass=flavor issue=196 flavor=" + flavor
            + " default=" + default + " -->")


class ItemFlavor(unittest.TestCase):
    def resolve(self, bodies, profile=None, default=None):
        return item.resolve_item(profile or {"flavor": {"name": "thorough"}}, 196, bodies, default)

    def test_unset_project_default_is_standard(self):
        self.assertEqual(item.resolve_item({}, 196, [], None),
                         dict(flavor="thorough", default="standard", status="flavor-missing"))
        self.assertEqual(item.resolve_item({}, 196, [record(default="standard")], None)["status"], "recorded")

    def test_default_and_missing_record(self):
        self.assertEqual(self.resolve([record("thorough")])["flavor"], "thorough")
        self.assertEqual(self.resolve([], {"flavor": {"name": "fast"}}),
                         dict(flavor="thorough", default="fast", status="flavor-missing"))

    def test_lowering_with_reason(self):
        self.assertEqual(self.resolve([record(reason="Reason: docs only")]),
                         dict(flavor="standard", default="thorough", status="recorded"))

    def test_lowering_without_reason_refused(self):
        for reason in ("", "Reason:   ", "prose Reason: docs only"):
            with self.subTest(reason=reason):
                self.assertEqual(self.resolve([record(reason=reason)]),
                                 dict(flavor="thorough", default="thorough", status="flavor-refused"))

    def test_newest_record_and_immediate_tightening(self):
        self.assertEqual(self.resolve([record(reason="Reason: docs"), record("thorough")])["flavor"], "thorough")
        self.assertEqual(self.resolve([record("thorough"), record()])["status"], "flavor-refused")
        self.assertEqual(self.resolve([record().replace("issue=196", "issue=197")])["status"], "flavor-missing")

    def test_class_default_and_recorded_default_cannot_hide_lowering(self):
        profile = {"flavor": {"name": "fast"}}
        self.assertEqual(self.resolve([record(default="fast")], profile, "thorough")["status"], "flavor-refused")
        self.assertEqual(self.resolve([record("thorough", "fast")], profile)["status"], "recorded")

    def test_custom_any_knob_and_caps_lowering(self):
        for knobs in ({"base": "thorough", "merge": "auto"}, {"base": "thorough", "caps": [2, 3]}):
            profile = {"flavor": {"custom": {"local": knobs}}}
            self.assertEqual(self.resolve([record("local")], profile)["status"], "flavor-refused")
            self.assertEqual(self.resolve([record("local", reason="Reason: owner choice")], profile)["flavor"], "local")

    def test_cli_gap_and_refusal(self):
        profile = Path(__file__).parent / "fixtures/render/crew.toml"
        for bodies, code, status in (([], 0, "flavor-missing"), ([record("fast", "standard")], 1, "flavor-refused"),
                                     ([record("fast", "standard", "Reason: docs")], 0, "recorded"),
                                     ([record()], 0, "recorded")):
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO(json.dumps(bodies))), contextlib.redirect_stdout(output):
                self.assertEqual(item.main(["--project", str(profile), "--issue", "196"]), code)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], status)
            self.assertTrue(result["project_gap"])


if __name__ == "__main__":
    unittest.main()
