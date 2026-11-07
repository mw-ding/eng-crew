"""Pool-lead fixtures: presence caps, idle and busy builders, identity-based restart, durable handoff
replay and cleanup boundaries. Fake tmux and GitHub; no model or network calls. Run in CI.
"""
import argparse
import json
import os
import shutil
import sys
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import LivenessBase, SendBase

TRANSCRIPT = "--transcript" in sys.argv or "--presence-transcript" in sys.argv


class BuilderLead(LivenessBase):
    def test_pi_pool_lead_uses_adapter_and_probes_alive(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["pi/anthropic/claude-sonnet-4-5"]\n')
        self.assertEqual(self.ensure(), 0)
        self.assertIn("exec pi --approve --model anthropic/claude-sonnet-4-5 --thinking medium ",
                      self.lead_windows()[0][-1])
        self.assertEqual(self.lead_record()["harness"], "pi")
        self.assertEqual(self.snapshot()["readiness"], "alive")

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

    def test_solo_build_and_fix_handoffs_never_start_lead_or_worker(self):
        self.env["FAKE_SOLO_ISSUE"] = "8"
        self.env["FAKE_SOLO_PR"] = "12"
        with mock.patch.dict(os.environ, self.env):
            for kind, refs in (("build", ["#8"]), ("fix", ["#12", "a" * 40]),
                               ("ci-red", ["#12", "a" * 40]), ("merge-up", ["#12", "a" * 40])):
                self.assertEqual(self.lead.handoff(self.args, "builder", kind, refs), 0)
        self.assertEqual(self.lead_windows(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-lead.jsonl")))
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-8.json")))


    def test_presence_switches_both_pools_without_stopping_workers(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"\n',
                                'name = "tmux"\noptions = { builders = 5, reviewers = 4, present_builders = 1, present_reviewers = 1, max_suites = 1 }\n'))
        self.put("away-control.json", '{"issue": 99}')
        comments = []
        worker = self.record("ben-7")
        original = self.mod.subprocess.run

        def backend(argv, **kwargs):
            if argv[:2] == ["gh", "api"]:
                return mock.Mock(returncode=0, stdout=json.dumps([comments]))
            return original(argv, **kwargs)

        def record(state, entry, source, **flags):
            data = dict(state=state, entry=entry, **flags)
            cmd = "away" if state == "away" else "away-return"
            record_text = "`" + json.dumps(data) + "`\n" if state == "returned" else "```json\n" + json.dumps(data) + "\n```\n"
            comments.append(dict(user=dict(login="acme-bot"), body=(
                record_text +
                "<!-- crew:v1 role=coordinator pass=steer cmd=%s cmd-id=%s sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa round=n/a verdict=n/a -->\n"
                "— Ash (CTO) · codex · gpt-6.1-sol" % (cmd, source))))

        def check(expected):
            for role, cap in zip(("builder", "reviewer"), expected):
                self.assertEqual(self.mod.pool_cap(self.mod.profile(self.args)[0], role, self.state), cap)
                if TRANSCRIPT:
                    print("presence %s: cap=%d" % (role, cap))
            self.assertEqual(self.mod.over_cap(self.mod.profile(self.args)[0], "builder", {"ben-7": 10}, self.state), expected[0] <= 1)
            self.assertEqual(self.record("ben-7"), worker)
            self.assertTrue(os.path.isdir(worker["worktree"]))

        with mock.patch.dict(os.environ, self.env), mock.patch.object(self.mod.subprocess, "run", side_effect=backend), \
                mock.patch("os.getloadavg", return_value=(0, 0, 0)), mock.patch("os.cpu_count", return_value=4):
            check((1, 1))
            record("away", "a", "a", until="2020-01-01T00:00:00Z")
            check((5, 4))  # until alone is not a return
            record("returned", "a", "b")
            check((1, 1))
            record("away", "c", "c", quiet=True)
            check((1, 1))
            record("away", "d", "d", cap=1)
            check((1, 0))  # existing builder consumes the global bound
            record("away", "e", "e")
            comments[-1]["user"]["login"] = "untrusted"
            check((1, 0))
            self.assertFalse(any(c[0] == "kill-window" for c in self.calls()))
            if TRANSCRIPT:
                print("present -> away -> returned -> quiet -> away cap=1; live worker preserved; exit 0")

    def test_away_record_sign_matches_current_or_legacy_coordinator_title(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"\n',
                                'name = "tmux"\noptions = { builders = 5, reviewers = 4, present_builders = 1, present_reviewers = 1 }\n'))
        self.put("away-control.json", '{"issue": 99}')
        for title, cap in (("CTO", 5), ("Coordinator", 5), ("Builder", 1)):
            body = ("```json\n" + json.dumps(dict(state="away", entry="a")) + "\n```\n"
                    "<!-- crew:v1 role=coordinator pass=steer cmd=away cmd-id=a sha=%s round=n/a verdict=n/a -->\n"
                    "— Ash (%s) · codex · gpt-6.1-sol" % ("a" * 40, title))
            out = mock.Mock(returncode=0, stdout=json.dumps([[dict(user=dict(login="acme-bot"), body=body)]]))
            with mock.patch.dict(os.environ, self.env), mock.patch.object(self.mod.subprocess, "run", return_value=out):
                self.assertEqual(self.mod.pool_cap(self.mod.profile(self.args)[0], "builder", self.state), cap, title)

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

    def test_fresh_lead_can_append_its_first_ack(self):  # #1176: a fresh state root has no status/
        shutil.rmtree(os.path.join(self.state, "status"), ignore_errors=True)
        self.assertEqual(self.ensure(), 0)
        call = self.lead_windows()[0]
        status = next(call[i + 1] for i, arg in enumerate(call) if arg == "-e" and call[i + 1].startswith("CREW_STATUS="))
        with open(status.split("=", 1)[1], "a") as f:
            f.write("ack: work-1\n")

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

    def test_resend_after_done_starts_a_new_handoff(self):  # #712: a withdrawn id is never reported acked
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.lead.handoff(self.args, "builder", "build", ["#639"]), 0)
            first = self.lead.pending(self.state, "ben-lead")
            self.put("status/ben-lead.status", "ack: %s\ndone: %s\n" % (first[0]["id"], first[0]["id"]))
            self.assertEqual(self.lead.handoff(self.args, "builder", "build", ["#639"]), 0)
        again = self.lead.pending(self.state, "ben-lead")
        self.assertEqual([(m["kind"], m["refs"]) for m in again], [("build", ["#639"])])
        self.assertNotEqual(again[0]["id"], first[0]["id"])

    def test_other_pool_cannot_dequeue_builder_and_lead_can(self):
        self.put("spawn-queue.jsonl", json.dumps(dict(role="builder", issue=8, pr=None, **{
            "pass": "build", "round": 1, "tier": "default", "head": None})) + "\n")
        self.assertEqual(self.crew("dequeue", "--project", self.project).returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "ben-8.json")))
        result = self.crew("dequeue", "--project", self.project, CREW_POOL="builder")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-8.json")))

    def test_done_builder_with_running_tool_session_still_counts(self):
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % ("a" * 40))
        with open(self.ps, "w") as f:
            json.dump({"children": [[42, 9000010, "S", "codex.real"], [43, 42, "Ss", "python3"]]}, f)
        with mock.patch.dict(os.environ, self.env):
            self.assertIsNone(self.mod.idle_builder(self.state, "ben-7"))
        if TRANSCRIPT:
            print("done builder with running Python child: busy, not reclaimable")

    def test_helpers_are_idle_reclaimable_and_not_suites_but_tool_sessions_are_busy(self):
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % ("a" * 40))
        status = os.path.join(self.state, "status", "ben-7.status")
        os.utime(status, (100, 100))
        values, _, _ = self.mod.profile(self.args)
        dequeue = self.mod.commands()["dequeue"]
        for harness in ("codex", "claude"):
            rec = self.record("ben-7")
            rec["harness"] = harness
            self.put("runs/ben-7.json", json.dumps(rec))
            self.set_pane(10, command=harness)
            helpers = [[42, 9000010, "S+", harness + ".real"], [43, 42, "S", "mcp-server"],
                       [44, 43, "S", "python3"], [45, 42, "S", "sleep"]]
            for busy in (False, True):
                with self.subTest(harness=harness, busy=busy):
                    with open(self.ps, "w") as f:
                        json.dump({"children": helpers + ([[46, 43, "Ss", "python3"]] if busy else [])}, f)
                    with mock.patch.dict(os.environ, self.env), \
                            mock.patch.object(self.mod.commands()["route"], "gh", return_value={"state": "OPEN"}), \
                            mock.patch.object(dequeue, "unlanded", return_value=[]), \
                            mock.patch.object(dequeue, "kill_run", return_value=[]) as kill:
                        self.assertEqual(self.mod.idle_builder(self.state, "ben-7"), None if busy else 100)
                        self.assertEqual(self.lead.suites(values, self.state), int(busy))
                        wakes = self.mod.scan(self.state, "crew-acme-widgets", 1900, 900, {"offsets": {}, "keys": {}})
                        self.assertEqual(any(w["reason"] == "idle-builder" for w in wakes), not busy)
                        dequeue.reclaim(values, "crew-acme-widgets", self.state, {"ben-7": 10})
                        self.assertEqual(kill.call_count, 0 if busy else 1)
                    if TRANSCRIPT:
                        print("%s: helpers only=%s; active=%d suites=%d reclaim=%s expiry=%s" %
                              (harness, not busy, busy, busy, not busy, not busy))

    def test_suite_probe_excludes_closed_and_merged_items(self):
        with open(self.ps, "w") as f:
            json.dump({"children": [[42, 9000010, "Ss", "python3"]]}, f)
        values, _, _ = self.mod.profile(self.args)
        route = self.mod.commands()["route"]
        for state, expected in (("OPEN", 1), ("CLOSED", 0), ("MERGED", 0)):
            with mock.patch.dict(os.environ, self.env), mock.patch.object(route, "gh", return_value={"state": state}):
                self.assertEqual(self.lead.suites(values, self.state), expected)
        if TRANSCRIPT:
            print("suite probe: live item=1; same processes attached to closed/merged item=0")

    def test_watcher_expires_idle_builder_and_preserves_busy_child(self):
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % ("a" * 40))
        status = os.path.join(self.state, "status", "ben-7.status")
        os.utime(status, (100, 100))
        with mock.patch.dict(os.environ, self.env):
            seen = {"offsets": {}, "keys": {}}
            self.assertFalse(any(w["reason"] == "idle-builder" for w in self.mod.scan(self.state, "crew-acme-widgets", 1899, 900, seen)))
            self.assertTrue(any(w["reason"] == "idle-builder" for w in self.mod.scan(self.state, "crew-acme-widgets", 1900, 900, seen)))
            self.assertFalse(any(w["reason"] == "idle-builder" for w in self.mod.scan(self.state, "crew-acme-widgets", 2000, 900, seen)))
            with open(self.ps, "w") as f:
                json.dump({"children": [[42, 9000010, "Ss", "python3"]]}, f)
            self.assertFalse(any(w["reason"] == "idle-builder" for w in self.mod.scan(self.state, "crew-acme-widgets", 3000, 900, seen)))

    def test_last_suite_completion_retries_pending_requests_in_both_pools(self):
        self.assertEqual(self.ensure(), 0)
        self.put("render/runtime/reviewer-lead.md", "Manage the reviewer pool.\n")
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.lead.ensure(self.args, "reviewer"), 0)
        for name in ("ben-lead", "vera-lead"):
            self.put("inbox/" + name + ".jsonl", json.dumps(dict(id="deferred", kind="build", refs=["#8"])) + "\n")
            self.put("status/" + name + ".status", "ack: deferred\n")
        rec = self.record("ben-7")
        rec["role"] = "reviewer"
        rec["args"]["pr"] = 12
        self.put("runs/ben-7.json", json.dumps(rec))
        gh = os.path.join(self.tmp, "bin", "gh")  # the reviewer's PR is still open: no reap (#811)
        with open(gh, "w") as f:
            f.write("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'state': 'OPEN', 'labels': []}))\n")
        os.chmod(gh, 0o755)
        before = len(self.calls())
        self.put("wake/queue.jsonl", json.dumps(dict(reason="status", window="ben-7", line="done: stale")) + "\n")
        result = self.crew("route", "--project", self.project, "--timeout", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        nudges = [c for c in self.calls()[before:] if c[0] == "send-keys" and "inbox: deferred" in c]
        self.assertEqual({c[c.index("-t") + 1] for c in nudges}, {"=crew-acme-widgets:2", "=crew-acme-widgets:3"})
        if TRANSCRIPT:
            print("last suite completed: both pending pools nudged; no coordinator handoff")

    def test_pending_admission_has_recurring_backstop_until_completed(self):
        self.assertEqual(self.ensure(), 0)
        self.put("inbox/ben-lead.jsonl", json.dumps(dict(id="deferred", kind="build", refs=["#8"])) + "\n")
        self.put("status/ben-lead.status", "ack: deferred\n")
        now = 2_000_000_000
        self.assertFalse(any(w["reason"] == "lead-backstop" for w in self.scan(now)))
        self.assertFalse(any(w["reason"] == "lead-backstop" for w in self.scan(now + 59, self.seen)))
        wakes = [w for w in self.scan(now + 60, self.seen) if w["reason"] == "lead-backstop"]
        self.assertEqual([w["window"] for w in wakes], ["ben-lead"])
        before = len(self.calls())
        self.put("wake/queue.jsonl", json.dumps(wakes[0]) + "\n")
        self.assertEqual(self.crew("route", "--project", self.project, "--timeout", "1").returncode, 0)
        self.assertTrue(any(c[0] == "send-keys" and "inbox: deferred" in c for c in self.calls()[before:]))
        self.assertEqual([w["reason"] for w in self.scan(now + 120, self.seen) if w["reason"] == "lead-backstop"],
                         ["lead-backstop"])
        self.put("status/ben-lead.status", "ack: deferred\ndone: deferred\n")
        self.assertFalse(any(w["reason"] == "lead-backstop" for w in self.scan(now + 180, self.seen)))
        if TRANSCRIPT:
            print("deferral backstop: retry at 60 s, again at 120 s; completed request stops retries")

    def test_idle_lead_is_not_stale_until_work_is_pending(self):  # #578
        self.assertEqual(self.ensure(), 0)
        now = 2_000_000_000
        self.assertFalse(any(w.get("window") == "ben-lead" for w in self.scan(now)))
        self.put("inbox/ben-lead.jsonl", json.dumps(dict(id="w1", kind="build", refs=["#8"])) + "\n")
        self.assertEqual([w["liveness"] for w in self.scan(now) if w.get("window") == "ben-lead"], ["alive"])
        self.put("status/ben-lead.status", "ack: w1\ndone: w1\n")
        os.utime(os.path.join(self.state, "status", "ben-lead.status"), (now - 1000, now - 1000))
        self.assertFalse(any(w.get("window") == "ben-lead" and w["reason"] == "stale" for w in self.scan(now)))

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
    unittest.main(argv=[sys.argv[0], "BuilderLead.test_presence_switches_both_pools_without_stopping_workers"] if "--presence-transcript" in sys.argv else [sys.argv[0], "BuilderLead.test_done_builder_with_running_tool_session_still_counts",
                       "BuilderLead.test_helpers_are_idle_reclaimable_and_not_suites_but_tool_sessions_are_busy",
                       "BuilderLead.test_suite_probe_excludes_closed_and_merged_items",
                       "BuilderLead.test_restart_preserves_live_workers_and_pending_queue",
                       "BuilderLead.test_last_suite_completion_retries_pending_requests_in_both_pools",
                       "BuilderLead.test_pending_admission_has_recurring_backstop_until_completed",
                       "BuilderReports.test_admission_deferrals_stay_local",
                       "BuilderLead.test_router_consumes_deferred_lead_status_without_coordinator",
                       "BuilderReports.test_real_blocks_notify_once_across_fresh_processes"] if TRANSCRIPT else None)
