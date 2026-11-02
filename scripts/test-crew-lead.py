"""Pool-lead fixtures: admission caps/load/suites, identity-based restart, durable handoff
replay and cleanup boundaries. Fake tmux and GitHub; no model or network calls. Run in CI.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock
from crew_testlib import LivenessBase

TRANSCRIPT = "--transcript" in sys.argv


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

    def snapshot(self):
        with mock.patch.dict(os.environ, self.env):
            windows = dict((n, i) for i, n in self.mod.tmux.list_windows("crew-acme-widgets"))
            ready = self.mod.probe("crew-acme-widgets", "ben-lead", self.lead_record(), windows)
        return dict(lead_restarts=self.lead_record()["restarts"], pending=len(self.lead.pending(self.state, "ben-lead")),
                    worker_present=os.path.isdir(self.record("ben-7")["worktree"]), readiness=ready)

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
        if TRANSCRIPT:
            print("before restart: " + json.dumps(self.snapshot()))
        with mock.patch.dict(os.environ, self.env):
            self.mod.tmux.kill_window("crew-acme-widgets", 2)
        self.assertEqual(self.ensure(), 0)
        self.assertEqual(self.lead_record()["restarts"], 1)
        self.assertEqual(self.lead.pending(self.state, "ben-lead")[0]["id"], "work-1")
        self.assertTrue(os.path.isdir(self.record("ben-7")["worktree"]))
        if TRANSCRIPT:
            print("after restart: " + json.dumps(self.snapshot()))
        with mock.patch.dict(os.environ, self.env):
            self.mod.tmux.kill_window("crew-acme-widgets", 2)
        self.assertEqual(self.ensure(), 1)
        self.assertEqual(len(self.lead_windows()), 2)
        if TRANSCRIPT:
            print("second recovery: blocked; no duplicate lead; worker and handoff preserved")

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

    def test_other_pool_cannot_dequeue_builder_and_lead_can(self):
        self.put("spawn-queue.jsonl", json.dumps(dict(role="builder", issue=8, pr=None, **{
            "pass": "build", "round": 1, "tier": "default", "head": None})) + "\n")
        self.assertEqual(self.crew("dequeue", "--project", self.project).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-8.json")))
        result = self.crew("dequeue", "--project", self.project, CREW_POOL="builder")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-8.json")))

    def test_capacity_counts_waiting_workers_and_excludes_lead(self):
        self.assertEqual(self.ensure(), 0)
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % ("a" * 40))
        args = argparse.Namespace(**vars(self.args), action="capacity", role="builder", suites=0, queued=8)
        out = io.StringIO()
        with mock.patch.dict(os.environ, self.env), mock.patch("os.getloadavg", return_value=(0, 0, 0)), \
                mock.patch("os.cpu_count", return_value=4), contextlib.redirect_stdout(out):
            self.assertEqual(self.lead.run(args), 0)
        result = json.loads(out.getvalue())
        self.assertEqual((result["active"], result["cap"], result["admit"]), (1, 5, 4))
        if TRANSCRIPT:
            print("fixture load=0, CPUs=4, suites=0; waiting worker counts, lead excluded: " + out.getvalue().strip())

    def test_watcher_routes_missing_lead_restart(self):
        self.assertEqual(self.ensure(), 0)
        with mock.patch.dict(os.environ, self.env):
            self.mod.tmux.kill_window("crew-acme-widgets", 2)
        wakes = self.scan(2_000_000_000)
        wake = next(w for w in wakes if w.get("window") == "ben-lead")
        self.put("wake/queue.jsonl", json.dumps(wake) + "\n")
        r = self.crew("route", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.lead_record()["restarts"], 1)

    def test_killing_lead_keeps_its_inbox(self):
        self.assertEqual(self.ensure(), 0)
        self.put("inbox/ben-lead.jsonl", json.dumps(dict(id="work-1", kind="build", refs=["#8"])) + "\n")
        r = self.crew("kill", "ben-lead", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.lead.pending(self.state, "ben-lead")), 1)
        self.assertEqual(self.ensure(), 0)
        self.assertEqual(self.lead_record()["restarts"], 1)

    def test_worker_kill_is_handed_to_lead_and_explicit_lead_cleanup_works(self):
        result = self.crew("kill", "ben-7", "--project", self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        self.assertEqual(len(self.lead.pending(self.state, "ben-lead")), 1)
        result = self.crew("kill", "ben-7", "--project", self.project, CREW_POOL="builder")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "BuilderLead.test_capacity_counts_waiting_workers_and_excludes_lead",
                       "BuilderLead.test_restart_preserves_live_workers_and_pending_queue"] if TRANSCRIPT else None)
