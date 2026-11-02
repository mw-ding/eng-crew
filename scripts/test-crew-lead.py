"""Pool-lead fixtures: admission caps/load/suites, identity-based restart, durable handoff
replay and cleanup boundaries. Fake tmux and GitHub; no model or network calls. Run in CI.
"""
import argparse
import json
import os
import unittest
from unittest import mock
from crew_testlib import LivenessBase


class BuilderLead(LivenessBase):
    def setUp(self):
        super().setUp()
        self.lead = self.mod.commands()["lead"]
        self.args = argparse.Namespace(project=self.project, org_profile=None, timeout=1)
        self.put("render/runtime/builder-lead.md", "Manage the builder pool; never build.\n")

    def ensure(self):
        with mock.patch.dict(os.environ, self.env):
            return self.lead.ensure(self.args, "builder")

    def lead_record(self):
        return dict(self.lead.records(self.state))["ben-lead"]

    def lead_windows(self):
        return [c for c in self.calls() if c[0] == "new-window" and c[c.index("-n") + 1] == "ben-lead"]

    def test_scaling_caps_load_and_suite_observations(self):
        admit = self.lead.admission
        self.assertEqual(admit(5, 2, 8, 0.5, 4, 0), 3)
        self.assertEqual(admit(5, 5, 8, 0.5, 4, 0), 0)
        self.assertEqual(admit(5, 4, 8, 0.5, 4, 0), 1)
        self.assertEqual(admit(5, 2, 8, 4, 4, 0), 0)
        self.assertEqual(admit(5, 2, 8, 0.5, 4, 1), 0)
        self.assertEqual(admit(5, 2, 8, None, 4, 0), 0)
        self.assertEqual(admit(5, 2, 8, 0.5, 4, None), 0)

    def test_recovery_decisions_do_not_restart_ambiguous_or_active(self):
        for state in ("dead", "missing"):
            self.assertEqual(self.lead.recovery(state, 0), "restart")
            self.assertEqual(self.lead.recovery(state, 1), "blocked")
        self.assertEqual(self.lead.recovery("ambiguous", 0), "blocked")
        self.assertEqual(self.lead.recovery("alive", 0), "none")

    def test_live_lead_is_unique_and_outside_worker_cap(self):
        worker = self.record("ben-7")
        self.assertEqual(self.ensure(), 0)
        self.assertEqual(self.ensure(), 0)
        self.assertEqual(len(self.lead_windows()), 1)
        self.assertEqual(self.lead_record()["index"], 2)
        self.assertEqual(self.record("ben-7"), worker)
        call = self.lead_windows()[0]
        env = [call[i + 1] for i, arg in enumerate(call) if arg == "-e"]
        self.assertIn("CREW_POOL=builder", env)
        self.assertNotIn("GH_TOKEN", " ".join(env))

    def test_restart_preserves_live_workers_and_pending_queue(self):
        self.assertEqual(self.ensure(), 0)
        inbox = "inbox/ben-lead.jsonl"
        self.put(inbox, json.dumps(dict(id="work-1", kind="build", refs=["#8"])) + "\n")
        with mock.patch.dict(os.environ, self.env):
            self.mod.tmux.kill_window("crew-acme-widgets", 2)
        self.assertEqual(self.ensure(), 0)
        self.assertEqual(self.lead_record()["restarts"], 1)
        self.assertEqual(self.lead.pending(self.state, "ben-lead")[0]["id"], "work-1")
        self.assertTrue(os.path.isdir(self.record("ben-7")["worktree"]))
        with mock.patch.dict(os.environ, self.env):
            self.mod.tmux.kill_window("crew-acme-widgets", 2)
        self.assertEqual(self.ensure(), 1)
        self.assertEqual(len(self.lead_windows()), 2)

    def test_ambiguous_lead_stays_and_escalates(self):
        self.assertEqual(self.ensure(), 0)
        self.set_pane(2, command="sleep")
        self.assertEqual(self.ensure(), 1)
        self.assertEqual(len(self.lead_windows()), 1)

    def test_handoff_replay_reuses_durable_event_and_message(self):
        wake = dict(event="issue-assigned", refs=["#8"])
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.lead.event(self.args, "builder", wake), 0)
            self.assertEqual(self.lead.event(self.args, "builder", wake), 0)
        pending = self.lead.pending(self.state, "ben-lead")
        self.assertEqual(len(pending), 1)
        self.assertTrue(os.path.isfile(pending[0]["refs"][0]))
        self.put("status/ben-lead.status", "ack: %s\ndone: %s\n" % (pending[0]["id"], pending[0]["id"]))
        self.assertEqual(self.lead.pending(self.state, "ben-lead"), [])







if __name__ == "__main__":
    unittest.main()
