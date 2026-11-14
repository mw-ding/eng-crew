#!/usr/bin/env python3
"""Offline item rigor tests. Usage: python3 dev/tests/scripts/test-item-flavor.py (run in CI)."""
import importlib.util
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("item_flavor", Path(__file__).resolve().parents[3] / "scripts" / "item-flavor.py")
item = importlib.util.module_from_spec(spec)
spec.loader.exec_module(item)


def record(flavor="standard", default="thorough", reason=""):
    return (reason + "\n<!-- crew:v1 role=coordinator pass=flavor issue=196 flavor=" + flavor
            + " default=" + default + " -->")


class ItemFlavor(unittest.TestCase):
    def resolve(self, bodies, profile=None, default=None, labels=None):
        return item.resolve_item(profile or {"flavor": {"name": "thorough"}}, 196, bodies, default, labels)

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

    def test_express_item_flavor(self):
        self.assertEqual(self.resolve([record("express", "standard", "Reason: owner express grant")], labels=[]),
                         dict(flavor="express", default="thorough", status="recorded"))
        self.assertEqual(self.resolve([record("express", "standard")])["status"], "flavor-refused")
        self.assertEqual(self.resolve([record("express", "express")])["status"], "flavor-refused")
        with self.assertRaises(ValueError):
            self.resolve([], default="express")

    def test_express_eligibility(self):
        reason = "Reason: owner express grant"
        override = reason + "\nOwner override: \"express is fine for #196\""
        for labels, body, status, blockers in (
                (None, reason, "express-ineligible", ["labels unknown"]),
                (["enhancement"], reason, "recorded", None),
                (["crew:sensitive"], reason, "express-ineligible", ["crew:sensitive"]),
                (["crew:spec", "crew:sensitive"], reason, "express-ineligible", ["crew:sensitive", "crew:spec"]),
                (["crew:sensitive", "crew:spec"], override, "recorded", None),
                (["crew:sensitive"], reason + "\nOwner override:   ", "express-ineligible", ["crew:sensitive"]),
                (["crew:sensitive"], reason + "\nprose Owner override: yes", "express-ineligible", ["crew:sensitive"]),
                (["crew:solo"], override, "express-ineligible", ["crew:solo"])):
            with self.subTest(labels=labels, body=body):
                result = self.resolve([record("express", "thorough", body)], labels=labels)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["flavor"], "express" if status == "recorded" else "thorough")
                self.assertEqual(result.get("blockers"), blockers)
        self.assertEqual(self.resolve([record(reason="Reason: docs")], labels=["crew:sensitive"])["status"], "recorded")

    def test_cli_express_labels(self):
        profile = Path(__file__).resolve().parents[1] / "fixtures/render/crew.toml"
        bodies = [record("express", "standard", "Reason: owner express grant")]
        for extra, code, status in (([], 1, "express-ineligible"), (["--labels", ""], 0, "recorded"),
                                    (["--labels", "enhancement, crew:spec"], 1, "express-ineligible")):
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO(json.dumps(bodies))), contextlib.redirect_stdout(output):
                self.assertEqual(item.main(["--project", str(profile), "--issue", "196"] + extra), code)
            self.assertEqual(json.loads(output.getvalue())["status"], status)

    def test_cli_gap_and_refusal(self):
        profile = Path(__file__).resolve().parents[1] / "fixtures/render/crew.toml"
        for bodies, code, status in (([], 0, "flavor-missing"), ([record("fast", "standard")], 1, "flavor-refused"),
                                     ([record("fast", "standard", "Reason: docs")], 0, "recorded"),
                                     ([record()], 0, "recorded")):
            output = io.StringIO()
            with patch("sys.stdin", io.StringIO(json.dumps(bodies))), contextlib.redirect_stdout(output):
                self.assertEqual(item.main(["--project", str(profile), "--issue", "196"]), code)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], status)
            self.assertTrue(result["project_gap"])


class ItemTier(unittest.TestCase):
    """#1830: the optional tier= on a flavor record, scanned apart from flavor."""

    def tiered(self, tier, flavor="standard", issue=196):
        return "<!-- crew:v1 role=coordinator pass=flavor issue=%d flavor=%s default=standard tier=%s -->" % (
            issue, flavor, tier)

    def test_newest_tiered_record_wins_and_flavor_only_record_keeps_it(self):
        self.assertIsNone(item.resolve_tier(196, [record()]))
        self.assertEqual(item.resolve_tier(196, [self.tiered("trivial"), self.tiered("deep")]), "deep")
        self.assertEqual(item.resolve_tier(196, [self.tiered("deep"), record("thorough")]), "deep")
        self.assertEqual(item.resolve_item({"flavor": {"name": "standard"}}, 196, [self.tiered("deep", "thorough")])["flavor"],
                         "thorough")  # flavor resolution ignores the tier field

    def test_other_issue_role_or_pass_is_ignored(self):
        for body in (self.tiered("deep", issue=197), self.tiered("deep").replace("role=coordinator", "role=builder"),
                     self.tiered("deep").replace("pass=flavor", "pass=triage")):
            self.assertIsNone(item.resolve_tier(196, [body]))

    def test_malformed_newest_tier_raises(self):
        for tier in ("high", "Deep", "deep,default"):
            with self.assertRaises(ValueError):
                item.resolve_tier(196, [self.tiered("deep"), self.tiered(tier)])
        self.assertEqual(item.resolve_tier(196, [self.tiered("high"), self.tiered("default")]), "default")


if __name__ == "__main__":
    unittest.main()
