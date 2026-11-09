"""Lab run evidence tests: the record's hosts, hashes and transport, simulated and stub labels, skipped scenarios
with no evidence, the injected events and timeline, the A30 journey, teardown and the Markdown copy.

Usage: python3 dev/tests/environments/test-crew-lab-evidence.py

No Docker: the manifest is a fixture shaped like crew-lab-docker.py setup writes it.
"""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
LAB = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "environments", "terminal", "remote", "lab")
loader = importlib.machinery.SourceFileLoader("crew_lab_evidence", os.path.join(LAB, "crew-lab-evidence.py"))
spec = importlib.util.spec_from_loader("crew_lab_evidence", loader)
ev = importlib.util.module_from_spec(spec)
loader.exec_module(ev)
BUNDLE, SOURCE = "b" * 64, "s" * 40


def manifest():
    act = dict(bundle_sha256=BUNDLE, source_sha=SOURCE)
    return dict(lab=dict(run="r1", context="desktop-linux", endpoint="unix:///d", image="sha256:" + "i" * 64,
                         tag="v7.1.0-lab.1", source_sha=SOURCE, stage={"mdstack-7.1.0-lab.1.tar.gz": BUNDLE},
                         hosts={"lab-a": dict(container="c1", network="n1", port=55022, host_key="ssh-ed25519 K",
                                              activated=act)}))


def rec():
    timeline = [dict(t="T0", scenario="disconnect", event="disconnect", phase="start"),
                dict(ev.event("disconnect", "inject"), scenario="disconnect"),
                dict(ev.event("disconnect", "lift"), scenario="disconnect"),
                dict(t="T1", scenario="disconnect", event="disconnect", phase="pass")]
    report = dict(disconnect=dict(passed=True, failures=[], seconds=40, job="j"),
                  red=dict(passed=False, failures=["a red remote test was not a red remote run"], seconds=3))
    return ev.record(manifest(), "lab-a", BUNDLE, "2026-11-09T05:00:00.000Z", timeline, report,
                     ["exact-head", "red", "disconnect", "pause"])


class RecordTest(unittest.TestCase):
    def test_hosts_hashes_and_transport_are_recorded(self):
        r = rec()
        self.assertEqual((r["lab"], r["run"], r["image"], r["source_sha"], r["client_bundle_sha256"]),
                         ("C", "r1", "sha256:" + "i" * 64, SOURCE, BUNDLE))
        self.assertEqual(r["stage"], {"mdstack-7.1.0-lab.1.tar.gz": BUNDLE})
        self.assertEqual(r["hosts"]["lab-a"], dict(container="c1", network="n1", port=55022,
                                                   host_key="ssh-ed25519 K", bundle_sha256=BUNDLE, source_sha=SOURCE))
        self.assertEqual((r["transport"]["kind"], r["transport"]["path"]), ("ssh", "127.0.0.1:55022"))

    def test_simulated_controls_and_stubs_are_labelled(self):
        r = rec()
        self.assertEqual((r["simulated"], r["real_device"], r["transport"]["simulated"]), (True, False, True))
        self.assertEqual([(e["event"], e["phase"], e["simulated"]) for e in r["events"]],
                         [("disconnect", "inject", True), ("disconnect", "lift", True)])
        self.assertEqual(r["events"][0]["control"], "docker network disconnect, then connect")
        self.assertEqual(len(r["timeline"]), 4)
        self.assertTrue(any("sample repo" in s for s in r["stubs"]))

    def test_a_skipped_scenario_supplies_no_evidence(self):
        s = rec()["scenarios"]
        self.assertEqual(s["exact-head"], dict(status="skipped", evidence=False))
        self.assertEqual(s["pause"], dict(status="skipped", evidence=False))
        self.assertEqual((s["disconnect"]["status"], s["disconnect"]["evidence"]), ("pass", True))
        self.assertEqual((s["red"]["status"], s["red"]["failures"]), ("fail", ["a red remote test was not a red "
                                                                              "remote run"]))

    def test_write_keeps_one_json_and_markdown_record_per_run(self):
        d = tempfile.mkdtemp()
        path = ev.write(d, rec())
        self.assertEqual(path, os.path.join(d, "runs", "2026-11-09T050000.000Z.json"))
        self.assertEqual(json.loads(Path(path).read_text())["scenarios"]["pause"]["evidence"], False)
        md = Path(path[:-5] + ".md").read_text()
        self.assertIn("## Lab C run r1: simulated, not a real device", md)
        self.assertIn("| pause | skipped | no: did not run |", md)
        self.assertIn("| disconnect | pass | yes |", md)
        self.assertIn("disconnect inject (simulated: docker network disconnect, then connect)", md)
        self.assertIn("- Host `lab-a`: container `c1`, network `n1`, port 55022, bundle `%s`" % BUNDLE, md)


def journey_report():
    wake = lambda r, a="escalate", e="": dict(reason=r, action=a, event=e)
    return {"exact-head": dict(passed=True, failures=[], seconds=9, remote=[0, 0], local=[0, 0]),
            "partition": dict(passed=True, failures=[], seconds=80, spawn=[0, "crew: started ben-1 (on lab-a)"],
                              placed=dict(host="lab-a", placement="capability", remote=True),
                              send=[0, "crew: sent M to ben-1 on lab-a\ncrew: acked M by ben-1"],
                              outage_wakes=[wake("unreachable")], reconcile=[wake("reconcile", "wake", "ben-1 alive")],
                              steps=[1, 2, 3], kill=[0, "tombstone written\ncrew: killed ben-1"],
                              tombstone_reconcile=[wake("x", "wake", "lab-a: tombstoned ben-1 stopped")])}


class JourneyTest(unittest.TestCase):
    def test_partition_and_exact_head_give_the_a30_journey_with_its_physical_limits(self):
        r = ev.record(manifest(), "lab-a", BUNDLE, "2026-11-09T05:00:00.000Z", [], journey_report(),
                      ["exact-head", "partition"])
        j = r["journey"]
        self.assertEqual((j["passed"], j["placed"]["host"], j["outage_wakes"], j["reconcile"], j["steps"],
                          j["steps_once_in_order"], j["tombstone"]),
                         (True, "lab-a", [["unreachable", "escalate"]], ["ben-1 alive"], 3, True,
                          ["lab-a: tombstoned ben-1 stopped"]))
        self.assertIn("acked M by ben-1", j["send"])
        self.assertEqual(j["local"], dict(remote=[0, 0], local=[0, 0], match=True))
        self.assertTrue(any("overlay" in x for x in j["limits"]) and any("stubs" in x for x in j["limits"]))
        md = ev.markdown(r)
        self.assertIn("### A30 remote-builder journey: pass, simulated host", md)
        self.assertIn("- Send: crew: sent M to ben-1 on lab-a; crew: acked M by ben-1", md)
        self.assertIn("- Local comparison: remote exits [0, 0], local [0, 0], match: True", md)
        self.assertIn("Physical limits:", md)

    def test_no_journey_unless_both_scenarios_ran_and_a_failed_one_fails_it(self):
        report = journey_report()
        self.assertIsNone(rec()["journey"])
        self.assertIsNone(ev.journey({"partition": report["partition"]}))
        report["exact-head"].update(passed=False, local=[0, 1])
        self.assertEqual((ev.journey(report)["passed"], ev.journey(report)["local"]["match"]), (False, False))

    def test_close_adds_teardown_once_to_each_run_record(self):
        d = tempfile.mkdtemp()
        path = ev.write(d, rec())
        ev.close(d, dict(removed=["c1", "n1"], gone=[], sentinel_unchanged=True, tmux_decoy_alive=True))
        ev.close(d, dict(removed=[], gone=["c1"], sentinel_unchanged=False, tmux_decoy_alive=False))
        self.assertEqual(json.loads(Path(path).read_text())["teardown"]["removed"], ["c1", "n1"])
        self.assertIn("Teardown: removed 2, gone 0, sentinel unchanged: True, tmux decoy alive: True",
                      Path(path[:-5] + ".md").read_text())
        ev.close(tempfile.mkdtemp(), {})  # no runs/ yet: nothing to close


if __name__ == "__main__":
    unittest.main()
