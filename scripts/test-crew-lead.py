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
from crew_testlib import LivenessBase, SendBase

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

    def test_router_consumes_deferred_lead_status_without_coordinator(self):
        self.assertEqual(self.ensure(), 0)
        self.put("status/ben-lead.status", "deferred: #8 capacity\n")
        wake = next(w for w in self.scan(2_000_000_000) if w.get("line", "").startswith("deferred:"))
        self.put("wake/queue.jsonl", json.dumps(wake) + "\n")
        result = self.crew("route", "--project", self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mechanical wakes consumed", result.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ash.jsonl")))
        if TRANSCRIPT:
            print("watcher deferral status routed mechanically; coordinator inbox absent")

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


class BuilderReports(SendBase):
    def report(self, reason, ref="#8", detail=""):
        return self.crew("lead", "report", "builder", reason, ref, "--detail", detail,
                         "--project", self.project, CREW_ID="ben-lead")

    def test_admission_deferrals_stay_local(self):
        for reason in ("capacity", "load", "suites", "probe-unavailable"):
            result = self.report(reason, detail="admit=0 active=5 load=10.6")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with open(os.path.join(self.state, "leads", "builder-admission.md")) as f:
                note = f.read()
            self.assertIn("Reason: " + reason, note)
            self.assertIn("Refs: #8", note)
            self.assertIn("admit=0 active=5 load=10.6", note)
            if TRANSCRIPT:
                print(result.stdout.strip())
        with open(os.path.join(self.state, "status", "ben-lead.status")) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(line.startswith("deferred: #8 ") for line in lines))
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ash.jsonl")))
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])
        if TRANSCRIPT:
            print("lead status: 4 deferred entries; coordinator inbox absent; nudges=0")

    def test_real_blocks_notify_once_across_fresh_processes(self):
        for reason in ("spawn-failure", "missing-dependency", "owner-decision", "lead-fault"):
            for attempt in range(2):
                result = self.report(reason, detail="action needed")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if attempt:
                    self.assertIn("identical block already reported", result.stdout)
        messages = self.inbox("ash")
        self.assertEqual(len(messages), 4)
        with open(os.path.join(self.state, "status", "ben-lead.status")) as f:
            self.assertEqual(len(f.readlines()), 4)
        self.assertTrue(all(m["kind"] == "blocked" and m["from"] == "ben-lead" for m in messages))
        for message in messages:
            self.assertEqual(message["refs"][0], "#8")
            with open(message["refs"][1]) as f:
                self.assertIn("action needed", f.read())
        self.assertEqual(len([c for c in self.calls() if c[0] == "send-keys"]), 8)
        changed = self.report("spawn-failure", detail="different failure")
        self.assertEqual(changed.returncode, 0, changed.stdout + changed.stderr)
        self.assertEqual(len(self.inbox("ash")), 5)
        if TRANSCRIPT:
            print("4 real block reasons x 2 fresh processes: coordinator messages=4; duplicates=0")
            print("changed failure detail: coordinator messages=5")

    def test_unknown_reason_is_rejected(self):
        result = self.report("ordinary-wait")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ash.jsonl")))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], "BuilderLead.test_capacity_counts_waiting_workers_and_excludes_lead",
                       "BuilderLead.test_restart_preserves_live_workers_and_pending_queue",
                       "BuilderReports.test_admission_deferrals_stay_local",
                       "BuilderLead.test_router_consumes_deferred_lead_status_without_coordinator",
                       "BuilderReports.test_real_blocks_notify_once_across_fresh_processes"] if TRANSCRIPT else None)
