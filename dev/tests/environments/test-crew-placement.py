"""Offline fixture tests for the placement decision function (crew.d/_placement.py, #207; stdlib only).

Covers each step of docs/runtimes/multi-device.md#placement: no inventory and primary-only roles stay local,
affinity order, least-loaded by ratio with ties by candidate order, capability rules by role, pass and changed-path
glob, roles exclusion, engine order before load, skipped engines, queue with one reason per host, refusal with no
engine, and the override's refusals. Run in CI.
"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
spec = importlib.util.spec_from_file_location("crew_placement", os.path.join(
    ROOT, "environments", "terminal", "crew.d", "_placement.py"))
placement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(placement)

PROFILE = {
    "hosts.host-a.primary": True, "hosts.host-a.capabilities.os": "macos", "hosts.host-a.capabilities.arch": "arm64",
    "hosts.host-a.capabilities.engines": ["claude-code", "codex"], "hosts.host-a.max_runs": 2,
    "hosts.host-b.capabilities.os": "linux", "hosts.host-b.capabilities.arch": "x86_64",
    "hosts.host-b.capabilities.engines": ["codex", "claude-code"], "hosts.host-b.max_runs": 4,
    "hosts.host-c.capabilities.os": "macos", "hosts.host-c.capabilities.arch": "arm64",
    "hosts.host-c.capabilities.devices": ["ios-simulator"], "hosts.host-c.capabilities.engines": ["claude-code"],
    "hosts.host-c.max_runs": 1, "hosts.host-c.roles": ["reviewer"],
    "placement.hosts": ["host-b", "host-a"],
    "placement.rules": [{"role": "reviewer", "pass": "validate", "paths": ["ios/**"],
                         "needs": {"devices": ["ios-simulator"]}}],
}
ORDER = [["claude-code", "opus"], ["codex", "gpt"]]
UP = {"reachable": True, "ready": True, "load": 0}


def request(role="builder", pass_="build", paths=(), order=ORDER, host=None):
    return {"role": role, "pass": pass_, "paths": list(paths), "order": order, "host": host}


class Place(unittest.TestCase):
    def place(self, req, facts=None, values=PROFILE):
        facts = facts or {}
        return placement.place(req, values, lambda h: dict(UP, **facts.get(h, {})))

    def test_no_inventory_is_local_first_engine(self):
        got = placement.place(request(), {}, lambda h: self.fail("no facts without hosts"))
        self.assertEqual(got, dict(result="place", host=None, engine="claude-code", model="opus", placement="local",
                                   rejections=[]))

    def test_primary_only_roles_stay_on_the_primary(self):
        for role in ("synthesizer", "coordinator", "researcher"):
            got = self.place(request(role, "land"))
            self.assertEqual((got["host"], got["placement"]), ("host-a", "local"))
            self.assertEqual(self.place(request(role, "land", host="host-b"))["result"], "refuse")

    def test_affinity_least_loaded_ratio_ties_by_candidate_order(self):
        self.assertEqual(self.place(request())["host"], "host-b")  # 0/4 ties 0/2: affinity order
        got = self.place(request(), {"host-b": {"load": 2}, "host-a": {"load": 0}})
        self.assertEqual((got["host"], got["placement"]), ("host-a", "affinity"))
        self.assertEqual(self.place(request(), {"host-b": {"load": 2}, "host-a": {"load": 1}})["host"], "host-b")

    def test_capability_rule_matches_role_pass_and_path(self):
        got = self.place(request("reviewer", "validate", ["ios/App/main.swift"]))
        self.assertEqual((got["host"], got["placement"]), ("host-c", "capability"))
        for req in (request("reviewer", "review", ["ios/a.swift"]), request("reviewer", "validate", ["web/a.ts"]),
                    request("builder", "build", ["ios/a.swift"])):
            self.assertEqual(self.place(req)["placement"], "affinity", req)

    def test_roles_exclusion_drops_a_host(self):
        values = dict(PROFILE, **{"placement.hosts": ["host-c", "host-a"]})
        self.assertEqual(self.place(request(), values=values)["host"], "host-a")

    def test_engine_order_comes_before_load(self):
        values = dict(PROFILE, **{"hosts.host-b.capabilities.engines": ["codex"]})
        got = self.place(request(), {"host-a": {"load": 1}}, values)
        self.assertEqual((got["host"], got["engine"]), ("host-a", "claude-code"))
        self.assertEqual(got["rejections"], ["host-b: lists no claude-code"])

    def test_skipped_engine_is_never_picked(self):
        got = self.place(request("reviewer", "review", order=[["codex", "gpt"]]))
        self.assertEqual((got["host"], got["engine"], got["model"]), ("host-b", "codex", "gpt"))

    def test_queue_names_one_reason_per_host(self):
        got = self.place(request(), {"host-b": {"load": 4}, "host-a": {"reachable": False}})
        self.assertEqual(got, dict(result="queue", reason="host-b: at cap 4/4; host-a: unreachable"))
        got = self.place(request(), {"host-b": {"ready": False}, "host-a": {"load": 2}})
        self.assertEqual(got["reason"], "host-b: not ready; host-a: at cap 2/2")

    def test_no_engine_refuses(self):
        got = self.place(request(order=[["cursor", "composer"]]))
        self.assertEqual(got["result"], "refuse")
        self.assertIn("host-b, host-a", got["reason"])

    def test_override_places_and_refuses(self):
        got = self.place(request(host="host-a"))
        self.assertEqual((got["result"], got["host"], got["placement"]), ("place", "host-a", "override"))
        cases = [(request(host="host-z"), "host-z: not in the inventory"),
                 (request(host="host-c"), "host-c: excludes role builder"),
                 (request("reviewer", "validate", ["ios/a.swift"], host="host-a"), "host-a: lacks device ios-simulator"),
                 (request(host="host-a"), "host-a: at cap 2/2")]
        for req, reason in cases:
            facts = {"host-a": {"load": 2}} if reason.endswith("cap 2/2") else {}
            self.assertEqual(self.place(req, facts), dict(result="refuse", reason=reason))
        self.assertEqual(self.place(request(host="host-a"), {"host-a": {"reachable": False}})["result"], "refuse")
        got = self.place(request(host="host-a"), values={})
        self.assertEqual(got, dict(result="refuse", reason="no [hosts] inventory"))


if __name__ == "__main__":
    unittest.main()
