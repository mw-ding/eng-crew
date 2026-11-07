"""Tests for crew watch (and its scan), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: scan with a fake clock (fresh, silent, dead -> restart, twice -> escalate, status line once; a builder
after `done:` flagged when dead, a reviewer's `done:` terminal), exit with a reason line and queue record, PID
file, `--source` events, typed wake line only into an idle coordinator and never into one showing a captured
stuck screen (a `dialog` wake queued instead, #315), backstop backoff while idle, a never-exiting source cut
off at `--source-timeout` as an incident, waking as `source-failing` at `--source-failures`, a source slower than a
short `--interval` not cut off, transient (exit 75) source failures recorded without a wake until N in a row and a
success resetting the count, a re-exec in place when the crew code changes on disk (#702), a wake on queue growth with no re-queue, a self-queueing source queued once, SIGTERM removing the PID
file and saving state, a signal during a scan waiting for the running child, a second signal exiting at once,
SIGHUP like SIGTERM, a dialog waking at once (each captured stuck screen in `fixtures/dialog/`; a working
screen never), a stale key that ignores the liveness class, an owner ask waking at its deadline once per
deadline (an unreadable one at once), the scan sleep cut short to land on a deadline, an ask wake while the
backstop is backed off; unfinished spawns skip liveness wakes for 60 s, then wake as missing, while started missing
runs wake immediately; a run record reaped between listing and stat skipped, a second watcher refusing to start
without touching the armed one's PID file, and a watcher removing the PID file only when it holds its own PID
(#591); finishing work deferred past `stuck_after` waking once as `schedule-stuck` with the snapshot, and the exit
line followed by the schedule summary (#628); the triage sweep timer (#748): due, overdue on wake, an empty queue
skipped, disabled, queued and failed spawns, never a wake, and closed milestones swept at once and kept until a started sweep takes them (#374), and the timer
running after the scan's `--source` commands, so a resumed crew's overdue slot reads the queue that scan's poll wrote
(#1098). Run in CI.
"""
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock
from crew_testlib import CREW, HEAD, LivenessBase, NOW, screen, STUCK, WORKING


class Watch(LivenessBase):
    def test_active_child_or_recent_output_refreshes_heartbeat(self):
        for activity, children in [(NOW - 30, []), (0, [[42, 9000010, "S", "codex.real"],
                                                       [43, 42, "Ss", "python3"]])]:
            with self.subTest(activity=activity, children=children):
                self.put("status/ben-7.status", "heartbeat: old\n")
                os.utime(os.path.join(self.state, "status", "ben-7.status"), (NOW - 1000, NOW - 1000))
                self.set_pane(10, activity=str(activity), command="node" if children else "codex")
                with open(self.ps, "w") as f:
                    json.dump({"children": children}, f)
                wakes = self.scan(NOW)
                self.assertFalse(any(w["reason"] == "stale" for w in wakes))
                self.assertEqual(self.mod.heartbeat(self.state, "ben-7"),
                                 ("heartbeat: 2033-05-18T03:33:20Z", NOW))
                self.assertEqual([w["reason"] for w in self.scan(NOW + 1, self.seen)], ["status"])
                with open(self.ps, "w") as f:
                    json.dump({}, f)
                self.set_pane(10, activity=str(activity))
                self.assertEqual([w["reason"] for w in self.scan(NOW + 901, self.seen)], ["stale"])

    def test_persistent_helpers_only_are_stale_but_detached_work_refreshes(self):
        for harness in ("codex", "claude"):
            with self.subTest(harness=harness):
                rec = self.record("ben-7")
                rec["harness"] = harness
                self.put("runs/ben-7.json", json.dumps(rec))
                self.set_pane(10, command=harness)
                self.put("status/ben-7.status", "heartbeat: old\n")
                os.utime(os.path.join(self.state, "status", "ben-7.status"), (NOW - 1000, NOW - 1000))
                helpers = [[42, 9000010, "S+", harness + ".real"], [43, 42, "S+", "mcp-server"],
                           [44, 43, "S+", "python3"], [45, 42, "S+", "keep-awake"]]
                with open(self.ps, "w") as f:
                    json.dump({"children": helpers}, f)
                self.assertEqual([w["reason"] for w in self.scan(NOW)], ["status", "stale"])
                with open(self.ps, "w") as f:
                    json.dump({"children": helpers + [[46, 43, "Ss", "python3"]]}, f)
                self.assertEqual(self.scan(NOW, self.seen), [])
                self.assertEqual(self.mod.heartbeat(self.state, "ben-7")[1], NOW)
                with open(self.ps, "w") as f:
                    json.dump({"children": helpers}, f)
                self.assertEqual([w["reason"] for w in self.scan(NOW + 901, self.seen)], ["status", "stale"])

    def test_idle_synthesizer_is_not_stale_until_it_has_work(self):  # #578
        rec = self.record("ben-7")
        rec["role"] = "synthesizer"
        self.put("runs/ben-7.json", json.dumps(rec))
        self.beat(NOW - 1000)
        self.assertEqual(self.scan(NOW), [])
        self.put("inbox/ben-7.jsonl", json.dumps(dict(id="m1", kind="land", refs=["#12"])) + "\n")
        self.beat(NOW - 1000)
        self.assertEqual([w["reason"] for w in self.scan(NOW)], ["stale"])
        os.remove(os.path.join(self.state, "inbox", "ben-7.jsonl"))
        self.put("trains/train-1.json", json.dumps(dict(n=1, members=[dict(pr=12)], landed=[])))
        self.beat(NOW - 1000)
        self.assertEqual([w["reason"] for w in self.scan(NOW)], ["stale"])
        self.set_pane(10, dead="1")
        os.remove(os.path.join(self.state, "trains", "train-1.json"))
        self.beat(NOW - 1000)
        self.assertEqual([w["liveness"] for w in self.scan(NOW)], ["dead"])

    def test_zombie_unrelated_child_and_reused_pane_do_not_mask_stale(self):
        with open(self.ps, "w") as f:
            json.dump({"children": [[42, 9000010, "S", "codex.real"], [43, 42, "Z", "python3"],
                                    [44, 999, "S", "python3"]]}, f)
        self.beat(NOW - 1000)
        self.assertEqual([w["reason"] for w in self.scan(NOW)], ["stale"])
        self.set_pane(10, id="%99", activity=str(NOW))
        self.assertEqual([w["liveness"] for w in self.scan(NOW)], ["missing"])

    def test_stray_json_is_not_a_run(self):
        self.beat(NOW)
        for name, text in [("checks", "[]"), ("scratch", '{"note": "scratch"}'), ("broken", "{")]:
            self.put("runs/%s.json" % name, text)
        self.assertEqual([name for name, _ in self.mod.runs(self.state)], ["ben-7"])
        self.assertEqual(self.scan(NOW), [])

    def test_record_reaped_between_listing_and_stat_is_skipped(self):  # #591
        for starting in (False, True):
            with self.subTest(starting=starting):
                rec = self.record("ben-7") if not starting else dict(self.record("ben-7"), start=None)
                os.remove(os.path.join(self.state, "runs", "ben-7.json"))
                with mock.patch.dict(self.mod.scan.__globals__, runs=lambda state: iter([("ben-7", rec)])):
                    self.assertEqual(self.scan(NOW), [])
                self.assertEqual(self.mod.heartbeat(self.state, "ben-7"), ("", None))
                self.put("runs/ben-7.json", json.dumps(rec))

    def test_same_size_status_delivered_after_window_reuse_and_rearm(self):
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % HEAD)
        os.utime(os.path.join(self.state, "status", "ben-7.status"), (NOW, NOW))
        self.assertEqual([w["reason"] for w in self.scan(NOW)], ["status"])
        seen = json.loads(json.dumps(self.seen))
        rec = self.record("ben-7")
        rec["start"] = "2033-05-18T00:00:00Z"
        self.put("runs/ben-7.json", json.dumps(rec))
        self.put("status/ben-7.status", "done: #7 #13 %s\n" % HEAD)
        os.utime(os.path.join(self.state, "status", "ben-7.status"), (NOW, NOW))
        self.assertEqual([w["line"] for w in self.scan(NOW, seen)], ["done: #7 #13 " + HEAD])
        self.assertEqual(self.scan(NOW, self.seen), [])
        self.assertEqual(self.record("ben-7")["pr"], 13)

    def missing_window(self, starting=False):
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash"}}, f)
        if starting:
            rec = self.record("ben-7")
            del rec["start"]
            self.put("runs/ben-7.json", json.dumps(rec))
        self.beat(NOW)

    def test_scan_fresh_starting_run_without_window_does_not_wake(self):
        self.missing_window(starting=True)
        self.assertEqual(self.probe(), "missing")
        self.assertEqual(self.scan(NOW), [])
        self.assertEqual(self.scan(NOW + 59, self.seen), [])

    def test_scan_expired_starting_run_without_window_wakes_once(self):
        self.missing_window(starting=True)
        self.assertEqual(self.scan(NOW), [])
        wakes = self.scan(NOW + 60, self.seen)
        self.assertEqual([(w["reason"], w["liveness"], w["action"]) for w in wakes],
                         [("stale", "missing", "restart")])
        self.assertEqual(self.scan(NOW + 61, self.seen), [])

    def test_scan_started_run_without_window_wakes_immediately(self):
        self.missing_window()
        self.assertEqual([(w["reason"], w["liveness"], w["action"]) for w in self.scan(NOW)],
                         [("stale", "missing", "restart")])

    def test_scan_fresh_silent_dead_and_twice(self):
        self.beat(NOW - 60)
        self.assertEqual(self.scan(NOW), [])  # fresh
        silent = self.scan(NOW + 900)
        self.assertEqual([(w["liveness"], w["action"]) for w in silent], [("alive", "escalate")])  # never restart
        self.assertEqual(self.scan(NOW + 1000, self.seen), [])  # once per silence
        self.set_pane(10, dead="1")
        self.assertEqual([(w["liveness"], w["action"]) for w in self.scan(NOW)], [("dead", "restart")])
        self.set_pane(10, id="%99", pid="9000099")
        self.assertEqual([(w["liveness"], w["action"]) for w in self.scan(NOW + 900)], [("missing", "restart")])
        rec = self.record("ben-7")
        rec["restarts"] = 1  # silent twice: the restarted run went silent and died again
        with open(os.path.join(self.state, "runs", "ben-7.json"), "w") as f:
            json.dump(rec, f)
        self.assertEqual([w["action"] for w in self.scan(NOW + 900)], ["escalate"])
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % HEAD)
        self.assertEqual([(w["reason"], w.get("line"), w.get("liveness")) for w in self.scan(NOW + 900)],
                         [("status", "done: #7 #12 " + HEAD, None), ("stale", None, "missing")])  # #139 F4

    def test_scan_builder_after_done_idle_ok_dead_flagged_reviewer_terminal(self):  # #139 F4
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % HEAD)
        self.beat(NOW - 3600)
        os.utime(os.path.join(self.state, "status", "ben-7.status"), (NOW - 3600, NOW - 3600))
        self.assertEqual([w["reason"] for w in self.scan(NOW, {"offsets": {"ben-7": 54}, "keys": {}})],
                         ["idle-builder"])  # alive and expired; a dead builder still follows recovery below
        self.set_pane(10, dead="1")
        self.assertEqual([(w["liveness"], w["action"]) for w in self.scan(NOW, {"offsets": {"ben-7": 54}, "keys": {}})],
                         [("dead", "restart")])
        rec = self.record("ben-7")
        rec["role"] = "reviewer"
        with open(os.path.join(self.state, "runs", "ben-7.json"), "w") as f:
            json.dump(rec, f)
        self.assertEqual(self.scan(NOW, {"offsets": {"ben-7": 54}, "keys": {}}), [])  # a reviewer done: is terminal

    def test_scan_dialog_wakes_at_once_not_after_stale(self):  # #234 N3
        self.beat(NOW - 30)
        self.set_pane(10, screen="Hooks need review\n> 1. Review hooks\n  2. Continue without hooks\n"
                               "enter confirm · esc skip")
        wakes = self.scan(NOW)  # 30 s after the last progress, far inside --stale 900
        self.assertEqual([(w["reason"], w["liveness"], w["action"]) for w in wakes], [("dialog", "ambiguous", "escalate")])
        self.assertEqual(self.mod.reason(wakes[0]), "dialog: ben-7 ambiguous, silent 30s, escalate")
        self.assertEqual(self.scan(NOW + 900, self.seen), [])  # once per dialog, and no stale wake behind it

    def test_scan_stuck_screen_wakes_at_once_working_screen_does_not(self):  # #289
        self.beat(NOW - 30)
        for name, want in [(n, [("dialog", "ambiguous")]) for n in STUCK] + [(n, []) for n in WORKING]:
            with self.subTest(name):
                self.set_pane(10, screen=screen(name))
                self.assertEqual([(w["reason"], w["liveness"]) for w in self.scan(NOW)], want)

    def test_scan_records_adapter_transient_text_once(self):  # #621
        claude = "  ⎿  API Error (529 {\"type\":\"error\"}) · Retrying in 2 seconds… (attempt 1/10)"
        codex = "■ exceeded retry limit, last status: 429 Too Many Requests"
        errors = os.path.join(self.state, "schedule", "errors.jsonl")
        for harness, text, want in [("claude", claude, [claude.strip()]), ("codex", codex, [codex]),
                                    ("codex", '■ {"type":"error","status":503,…}', ['■ {"type":"error","status":503,…}']),
                                    ("pi", claude, [])] + [(h, screen(n), []) for n in WORKING for h in ("claude", "codex")]:
            with self.subTest(harness=harness, text=text[:30]):
                if os.path.exists(errors):
                    os.remove(errors)
                rec = self.record("ben-7")
                rec["harness"] = harness
                self.put("runs/ben-7.json", json.dumps(rec))
                self.beat(NOW - 30)
                self.set_pane(10, command=harness, screen=text)
                self.scan(NOW)
                self.scan(NOW + 60, self.seen)  # still on screen at the next scan: one error, not two
                lines = []
                if os.path.exists(errors):
                    with open(errors) as f:
                        lines = [json.loads(line) for line in f]
                self.assertEqual([(e["source"], e["text"]) for e in lines], [("ben-7", t) for t in want])

    def test_scan_stale_key_ignores_liveness_class(self):  # #234 N4
        self.beat(NOW - 60)
        self.set_pane(10, command="node")
        self.assertEqual([(w["reason"], w["liveness"]) for w in self.scan(NOW + 900)], [("stale", "ambiguous")])
        self.set_pane(10)
        self.assertEqual(self.probe(), "alive")
        self.assertEqual(self.scan(NOW + 1000, self.seen), [])  # same silence, no second wake

    def ask(self, n, deadline):
        self.put("asks/%s.json" % n, json.dumps({"deadline": deadline}))

    def asks(self, now, seen=None):
        return [w["event"] for w in self.scan(now, seen) if w["reason"] == "ask"]

    def tick(self, now, values=None, rc=0, stdout="crew: started riley-sweep\n"):
        """One triage timer tick with a fake spawn: (outcome, spawn argv or None, queue.jsonl unchanged)."""
        values = {"triage.enabled": True, "triage.interval_hours": 6} if values is None else values
        queue = os.path.join(self.state, "wake", "queue.jsonl")
        before = os.path.exists(queue) and os.path.getsize(queue)
        done = subprocess.CompletedProcess([], rc, stdout, "")
        with mock.patch.object(self.mod.subprocess, "run", return_value=done) as run:
            outcome = self.mod.triage_tick(values, self.state, now, self.project)
        after = os.path.exists(queue) and os.path.getsize(queue)
        return outcome, run.call_args[0][0] if run.called else None, before == after

    def test_triage_timer_due_and_overdue_on_wake(self):  # #748
        outcome, argv, quiet = self.tick(NOW)  # never swept: due on the first scan
        self.assertEqual((outcome, quiet), ("started", True))
        self.assertEqual((os.path.realpath(argv[1]), argv[2:]),
                         (os.path.realpath(CREW), ["spawn", "researcher", "--sweep", "--project", self.project]))
        self.assertEqual(self.tick(NOW + 6 * 3600 - 1)[:2], (None, None))  # inside the interval
        self.assertEqual(self.tick(NOW + 6 * 3600)[0], "started")  # due
        self.assertEqual(self.tick(NOW + 30 * 86400)[0], "started")  # woke a month overdue: at once, one sweep
        self.assertEqual(self.tick(NOW + 30 * 86400 + 5)[:2], (None, None))
        with open(os.path.join(self.state, "triage", "sweep.json")) as f:
            self.assertEqual(json.load(f), {"at": NOW + 30 * 86400, "outcome": "started"})

    def test_triage_timer_skips_an_empty_queue_and_sweeps_an_unreadable_one(self):  # #748
        self.put("triage/queue.json", json.dumps({"items": []}))
        self.assertEqual(self.tick(NOW)[:2], ("skipped: empty queue", None))
        self.assertEqual(self.tick(NOW + 3600)[:2], (None, None))  # a skipped slot still counts
        self.put("triage/queue.json", json.dumps({"items": [{"issue": 9, "kind": "owner-reply"}]}))
        self.assertEqual(self.tick(NOW + 6 * 3600)[0], "started")
        self.put("triage/queue.json", "{not json")
        self.assertEqual(self.tick(NOW + 12 * 3600)[0], "started")

    def test_triage_timer_disabled_never_spawns(self):  # #748
        for values in ({}, {"triage.enabled": False, "triage.interval_hours": 6}):
            self.assertEqual(self.tick(NOW, values)[:2], (None, None))
        self.assertFalse(os.path.exists(os.path.join(self.state, "triage", "sweep.json")))

    def test_triage_timer_keeps_closed_milestones_until_a_started_sweep_takes_them(self):  # #374
        poll = self.mod.commands()["poll"]
        values = {"triage.enabled": True, "triage.interval_hours": 6, "repo.owner": "acme", "repo.name": "widgets"}
        closed = [{"number": 1, "title": "M1"}]

        def scan():  # crew poll's milestone part
            pending = poll.triage_milestones(values, self.state, read=lambda *a, **k: closed)
            self.put("triage/queue.json", json.dumps({"items": [], "milestones": pending}))
            return [m["number"] for m in pending]
        queued = "queued: researcher research sweep (researcher cap reached)\n"
        self.assertEqual(scan(), [])  # baseline
        self.assertEqual(self.tick(NOW, values)[0], "skipped: empty queue")
        closed.append({"number": 2, "title": "M2"})
        self.assertEqual(scan(), [2])
        self.assertEqual(self.tick(NOW + 60, values, stdout=queued)[0], "queued")  # at once, inside the interval
        self.assertEqual(scan(), [2])  # capped: still pending
        closed.append({"number": 3, "title": "M3"})
        self.assertEqual(scan(), [2, 3])  # M3 closes before the queued sweep starts
        self.assertEqual(self.tick(NOW + 120, values)[:2], (None, None))  # the queued sweep will take both
        self.assertEqual(self.tick(NOW + 60 + 6 * 3600, values, stdout=queued)[0], "queued")  # interval before dequeue
        self.assertEqual(scan(), [2, 3])
        self.assertEqual(poll.triage_untaken(self.state), [{"repo": "acme/widgets", "number": n, "title": "M%d" % n}
                                                           for n in (2, 3)])  # what the dequeued spawn names and takes
        poll.triage_take(self.state, poll.triage_untaken(self.state))
        self.assertEqual(scan(), [])
        self.assertEqual(self.tick(NOW + 61 + 12 * 3600, values)[0], "skipped: empty queue")
        closed.append({"number": 4, "title": "M4"})
        self.assertEqual(scan(), [4])
        self.assertEqual(self.tick(NOW + 62 + 12 * 3600, values, rc=1, stdout="crew: riley-sweep already running\n")[0],
                         "failed: crew: riley-sweep already running")
        self.assertEqual(self.tick(NOW + 62 + 12 * 3600 + 599, values)[:2], (None, None))
        self.assertEqual(self.tick(NOW + 62 + 12 * 3600 + 600, values)[0], "started")  # retried after SWEEP_RETRY

    def test_triage_timer_queued_and_failed_spawns(self):  # #748
        self.assertEqual(self.tick(NOW, stdout="queued: researcher research sweep (...)\n")[0], "queued")
        self.assertEqual(self.tick(NOW + 6 * 3600, rc=1, stdout="crew: session x not reachable\n")[0],
                         "failed: crew: session x not reachable")
        self.assertEqual(self.tick(NOW + 6 * 3600 + 599)[:2], (None, None))
        self.assertEqual(self.tick(NOW + 6 * 3600 + 600)[0], "started")  # retried after SWEEP_RETRY

    DOCS = {"docs.enabled": True, "docs.interval_days": 7, "docs.repos": ["acme/widgets"], "repo.owner": "acme",
            "repo.name": "widgets", "repo.default_branch": "main"}

    def docs_tick(self, now, values=None, findings=0, head="a" * 40, scan_rc=0, spawn_rc=0,
                  stdout="crew: started riley-docs\n"):
        """One docs-pass timer tick with a fake git, docs scan and spawn: (outcome, the argv run, queue.jsonl unchanged).
        The fake scan writes acme/widgets' scan.json with `findings` broken links at `head`, scanned today."""
        values = self.DOCS if values is None else values
        queue = os.path.join(self.state, "wake", "queue.jsonl")
        before = os.path.exists(queue) and os.path.getsize(queue)
        out = os.path.join(os.path.dirname(self.state), "acme__widgets", "docs", "scan.json")

        def run(argv, **_):
            if argv[1:2] == [os.path.join(self.mod.HERE, "docs-scan.py")] and not scan_rc:
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "w") as f:
                    json.dump({"repo": "acme/widgets", "head": head, "scanned": str(now), "inventory": [],
                               "stale": [{"path": "docs/d.md", "age_days": int(now)}],
                               "broken_links": [{"path": "README.md", "line": n} for n in range(findings)]}, f)
            rc = scan_rc if "docs-scan.py" in argv[1] else spawn_rc if "spawn" in argv else 0
            return subprocess.CompletedProcess(argv, rc, stdout if "spawn" in argv else "",
                                               "docs-scan: no --checkout for acme/pack\n" if rc else "")
        with mock.patch.object(self.mod.subprocess, "run", side_effect=run) as fake:
            outcome = self.mod.docs_tick(values, self.state, now, self.project)
        after = os.path.exists(queue) and os.path.getsize(queue)
        return outcome, [c[0][0] for c in fake.call_args_list], before == after

    def test_docs_timer_due_at_once_and_catches_up_overdue_on_wake(self):  # #1026
        outcome, argv, quiet = self.docs_tick(NOW)  # never run: due on the first scan
        self.assertEqual((outcome, quiet), ("started", True))
        self.assertEqual([a[3:5] for a in argv[:2]], [["rev-parse", "--show-toplevel"], ["fetch", "-q"]])
        self.assertEqual(argv[2][2:5], ["--project", self.project, "--checkout"])
        self.assertTrue(argv[2][5].startswith("acme/widgets="))
        self.assertEqual((os.path.realpath(argv[3][1]), argv[3][2:]),
                         (os.path.realpath(CREW), ["spawn", "researcher", "--docs-pass", "--project", self.project]))
        week = 7 * 86400
        self.assertEqual(self.docs_tick(NOW + week - 1, findings=1), (None, [], True))  # inside the interval
        self.assertEqual(self.docs_tick(NOW + week, findings=1)[0], "started")  # due
        self.assertEqual(self.docs_tick(NOW + 60 * 86400, findings=2)[0], "started")  # woke two months overdue: one pass
        self.assertEqual(self.docs_tick(NOW + 60 * 86400 + 5, findings=3)[:2], (None, []))
        with open(os.path.join(self.state, "docs", "pass.json")) as f:
            rec = json.load(f)
        self.assertEqual((rec["at"], rec["outcome"]), (NOW + 60 * 86400, "started"))

    def test_docs_timer_skips_a_scan_unchanged_since_the_last_report(self):  # #1026
        week = 7 * 86400
        self.assertEqual(self.docs_tick(NOW, findings=1)[0], "started")
        outcome, argv, _ = self.docs_tick(NOW + week, findings=1, head="b" * 40)  # new head and date, same findings
        self.assertEqual((outcome, len(argv)), ("skipped: scan unchanged", 3))  # scanned, no session
        self.assertEqual(self.docs_tick(NOW + week + 60, findings=2)[:2], (None, []))  # a skipped slot still counts
        self.assertEqual(self.docs_tick(NOW + 2 * week, findings=1)[0], "skipped: scan unchanged")  # vs the last report
        self.assertEqual(self.docs_tick(NOW + 3 * week, findings=2)[0], "started")  # changed: a pass
        self.assertEqual(self.docs_tick(NOW + 4 * week, findings=2, stdout="queued: researcher research docs pass\n")[0],
                         "skipped: scan unchanged")
        self.assertEqual(self.docs_tick(NOW + 5 * week, findings=0, stdout="queued: researcher research docs pass\n")[0],
                         "queued")  # a queued pass is the report too
        self.assertEqual(self.docs_tick(NOW + 6 * week, findings=0)[0], "skipped: scan unchanged")

    def test_docs_timer_retries_a_failed_scan_or_spawn(self):  # #1026
        self.assertEqual(self.docs_tick(NOW, scan_rc=2)[:2][0], "failed: scan: docs-scan: no --checkout for acme/pack")
        self.assertEqual(self.docs_tick(NOW + 599)[:2], (None, []))
        self.assertEqual(self.docs_tick(NOW + 600, spawn_rc=1, stdout="crew: riley-docs already running\n")[0],
                         "failed: crew: riley-docs already running")
        self.assertEqual(self.docs_tick(NOW + 1200)[0], "started")  # the failed spawn reported nothing: not skipped

    def test_docs_timer_disabled_never_scans(self):  # #1026
        for values in ({}, dict(self.DOCS, **{"docs.enabled": False})):
            self.assertEqual(self.docs_tick(NOW, values), (None, [], True))
        self.assertFalse(os.path.exists(os.path.join(self.state, "docs", "pass.json")))

    def test_scan_ask_wakes_at_its_deadline_once(self):  # #287
        self.ask("12", "2033-05-17T20:33:20-07:00")  # == NOW
        self.assertEqual(self.asks(NOW - 1), [])
        wakes = [w for w in self.scan(NOW, self.seen) if w["reason"] == "ask"]
        self.assertEqual([self.mod.reason(w) for w in wakes], ["ask: 12 deadline 2033-05-17T20:33:20-07:00"])
        self.assertEqual(self.asks(NOW + 3600, self.seen), [])  # once per deadline
        self.ask("12", "2033-05-17T20:43:20-07:00")  # moved to NOW + 600: fires again at the new deadline
        self.assertEqual(self.asks(NOW + 599, self.seen), [])
        self.assertEqual(self.asks(NOW + 600, self.seen), ["12 deadline 2033-05-17T20:43:20-07:00"])
        self.put("asks/13.json", "{")  # a bad record wakes at once, once
        self.assertEqual(self.asks(NOW + 600, self.seen), ["13 deadline unreadable"])
        self.assertEqual(self.asks(NOW + 601, self.seen), [])

    def test_pause_lands_the_next_scan_on_an_ask_deadline(self):  # #287
        self.assertEqual(self.mod.pause(self.state, NOW - 2, 5), 5)  # no open ask
        self.ask("12", "2033-05-17T20:33:20-07:00")  # == NOW
        self.assertEqual(self.mod.pause(self.state, NOW - 2, 5), 2)
        self.assertEqual(self.mod.pause(self.state, NOW - 60, 5), 5)
        self.assertEqual(self.mod.pause(self.state, NOW, 5), 5)  # due: this scan wakes, no shorter sleep

    def test_watch_ask_deadline_wakes_while_backstop_backed_off(self):  # #287
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)  # nothing in flight
        self.put("wake/watch-state.json", json.dumps({"idle": 4}))  # backstop at its cap, 16 x 3600 s
        self.ask("12", "2020-01-01T09:00:00-08:00")  # past due
        out, err = self.watch("--backstop", "3600").communicate(timeout=10)
        self.assertEqual(out, "ask: 12 deadline 2020-01-01T09:00:00-08:00\n", err)
        self.assertEqual(self.queue_lines()[0]["reason"], "ask")
        with open(os.path.join(self.state, "wake", "watch-state.json")) as f:
            self.assertEqual(json.load(f)["idle"], 4)  # an ask wake, not a backstop

    def decision(self):
        snap = dict(ts="2033-05-18T03:33:20Z", workers=[], reservations=[], memory={"os": "darwin", "level": "normal"},
                    load=0.5, errors=0, orphans=[], demand={"builder": [{"kind": "merge-up", "refs": ["#601"]}], "reviewer": []})
        self.put("schedule/decisions-20330518.jsonl", json.dumps(
            dict(action="snapshot", snapshot=snap, target=2, caps={"builder": 5, "reviewer": 2})) + "\n")
        return snap

    def test_scan_schedule_stuck_wakes_once_per_deferral(self):  # #628
        snap = self.decision()
        deferred = lambda since: self.put("schedule/deferred.json", json.dumps({"builder": {
            "#601": {"kind": "merge-up", "class": 3, "reasons": ["target"], "since": since},
            "#9": {"kind": "build", "class": 7, "reasons": ["target"], "since": "2020-01-01T00:00:00Z"}}}))
        stuck = lambda now, seen=None: [w for w in self.scan(now, seen) if w["reason"] == "schedule-stuck"]
        deferred("2033-05-18T03:03:20Z")  # NOW - 1800
        self.assertEqual(stuck(NOW - 1), [])
        wakes = stuck(NOW, self.seen)
        self.assertEqual([self.mod.reason(w) for w in wakes],
                         ["schedule-stuck: builder #601 merge-up class 3 deferred since 2033-05-18T03:03:20Z: target"])
        self.assertEqual(wakes[0]["snapshot"], snap)
        self.assertEqual(stuck(NOW + 60, self.seen), [])  # deduplicated
        deferred("2033-05-18T02:00:00Z")  # a new deferral of the same ref
        self.assertEqual(len(stuck(NOW + 60, self.seen)), 1)
        self.put("schedule/deferred.json", "{")
        self.assertEqual(stuck(NOW + 60), [])  # unreadable: no wake, no crash

    def test_watch_exit_line_carries_the_schedule_summary(self):  # #628
        self.decision()
        p = self.watch()
        self.put("status/ben-7.status", "done: PR #12\n")
        out, err = p.communicate(timeout=10)
        self.assertEqual(out.splitlines(), ["status: ben-7 done: PR #12", "schedule: builders 0/5 reviewers 0/2 "
                         "target 2 (load 0.5/cpu mem normal errors 0) queued merge-up 1; deferred 0; held 0; orphans 0; terminal 0"], err)

    def watch(self, *args):
        return subprocess.Popen([sys.executable, CREW, "watch", "--project", self.project, "--interval", "0.05", *args],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)

    def test_watch_blocks_then_exits_with_reason_and_queue(self):
        p = self.watch()
        pidfile = os.path.join(self.state, "wake", "watcher.pid")
        for _ in range(100):
            if os.path.exists(pidfile):
                break
            time.sleep(0.05)
        with open(pidfile) as f:
            self.assertEqual(int(f.read()), p.pid)
        self.assertIsNone(p.poll())  # blocks: fresh run, nothing new
        self.put("status/ben-7.status", "done: PR #12\n")
        out, err = p.communicate(timeout=10)
        self.assertEqual((p.returncode, out), (0, "status: ben-7 done: PR #12\n"), err)
        with open(os.path.join(self.state, "wake", "queue.jsonl")) as f:
            self.assertEqual(json.loads(f.readline())["line"], "done: PR #12")
        self.assertFalse(os.path.exists(pidfile))
        self.assertNotIn("send-keys", [c[0] for c in self.calls()])

    def test_muse_versioned_coordinator_wakes_but_dialog_does_not(self):
        source = ["--source", "printf 'pr-merged #9\\n'"]
        nudge = ["send-keys", "-t", "=crew-acme-widgets:0", "-l", "wake: watcher"]
        self.set_pane(0, command="muse-bin-0.1.0-R708.1", screen=
                      "Do you trust this workspace?\nUse Up/Down or 1/2, then Enter. Esc quits.")
        self.watch(*source).communicate(timeout=10)
        self.assertNotIn(nudge, self.calls())
        self.assertEqual(self.queue_lines()[-1]["reason"], "dialog")
        self.set_pane(0, command="muse-bin-0.1.0-R708.1")
        self.watch(*source).communicate(timeout=10)
        self.assertIn(nudge, self.calls())

    def test_watch_source_event_and_nudge_idle_coordinator(self):
        source = ["--source", "printf 'pr-merged #9\\n'"]
        nudge = ["send-keys", "-t", "=crew-acme-widgets:0", "-l", "wake: watcher"]
        self.set_pane(0, command="claude", activity=str(int(time.time())))  # busy: output just now
        out, _ = self.watch(*source).communicate(timeout=10)
        self.assertEqual(out, "poll: pr-merged #9\n")
        self.set_pane(0, command="claude")  # idle: no output since 1970
        self.watch(*source, "--no-nudge").communicate(timeout=10)
        self.assertNotIn(nudge, self.calls())
        self.watch(*source).communicate(timeout=10)
        self.assertIn(nudge, self.calls())

    def test_watch_never_types_into_a_coordinator_prompt(self):  # #315
        source = ["--source", "printf 'pr-merged #9\\n'"]
        for name in STUCK:  # idle coordinator showing a prompt: queue a dialog wake instead of the wake line
            with self.subTest(name):
                self.set_pane(0, command="claude", screen=screen(name))
                out, err = self.watch(*source).communicate(timeout=10)
                self.assertEqual(out, "poll: pr-merged #9 (+1 more in wake/queue.jsonl)\n", err)  # own record once
                w = self.queue_lines()[-1]
                self.assertEqual({k: w[k] for k in ("reason", "window", "liveness", "action")},
                                 {"reason": "dialog", "window": "ash", "liveness": "ambiguous", "action": "escalate"})
        self.assertNotIn("send-keys", [c[0] for c in self.calls()])
        for name in WORKING:
            with self.subTest(name):
                self.set_pane(0, command="claude", screen=screen(name))
                out, _ = self.watch(*source).communicate(timeout=10)
                self.assertEqual(out, "poll: pr-merged #9\n")
        self.assertEqual(self.calls().count(["send-keys", "-t", "=crew-acme-widgets:0", "-l", "wake: watcher"]),
                         len(WORKING))  # a normal screen still gets the wake line

    def test_watch_backstop_backs_off_while_idle(self):
        self.assertEqual(self.crew("kill", "ben-7", "--project", self.project).returncode, 0)
        idle = []
        for _ in range(2):
            out, _ = self.watch("--backstop", "0.1").communicate(timeout=10)
            self.assertEqual(out, "backstop: due (nothing in flight)\n")
            with open(os.path.join(self.state, "wake", "watch-state.json")) as f:
                idle.append(json.load(f)["idle"])
        self.assertEqual(idle, [1, 2])

    def armed(self, p):
        for _ in range(100):
            if os.path.exists(os.path.join(self.state, "wake", "watch-state.json")):
                break
            time.sleep(0.05)
        self.assertIsNone(p.poll())  # blocking, state saved after a scan

    def queue_lines(self):
        with open(os.path.join(self.state, "wake", "queue.jsonl")) as f:
            return [json.loads(line) for line in f]

    def test_watch_source_timeout_never_wedges(self):
        start = time.monotonic()
        out, _ = self.watch("--source", "sleep 30", "--source-timeout", "1", "--source-failures", "1").communicate(
            timeout=20)
        self.assertLess(time.monotonic() - start, 15)  # cut off at --source-timeout, long before the 30 s
        self.assertEqual(out, "source-failing: sleep 30: 1 failures in a row, last: timed out after 1s\n")
        self.assertEqual(self.queue_lines()[0]["reason"], "source-failing")

    def incidents(self):
        with open(os.path.join(self.state, "wake", "incidents.jsonl")) as f:
            return [json.loads(line) for line in f]

    def test_watch_transient_source_failures_wake_once_after_n_in_a_row(self):  # #702
        counter = os.path.join(self.tmp, "calls")
        code = ("import sys; n = len(open(%r).read()) if __import__('os').path.exists(%r) else 0\n"
                "open(%r, 'a').write('x')\n"
                "if n != 2: print('crew: gh pr list failed: HTTP 504: 504 Gateway Timeout'); sys.exit(75)\n"
                ) % (counter, counter, counter)  # calls 1-2 fail, 3 succeeds quietly, 4-6 fail
        out, err = self.watch("--source", shlex.join([sys.executable, "-c", code])).communicate(timeout=30)
        self.assertEqual(out, "source-failing: %s: 3 failures in a row, last: crew: gh pr list failed: HTTP 504: "
                         "504 Gateway Timeout\n" % shlex.join([sys.executable, "-c", code]), err)
        with open(counter) as f:
            self.assertEqual(len(f.read()), 6)  # no wake at failures 1, 2, 4 or 5
        self.assertEqual([i["consecutive"] for i in self.incidents()], [1, 2, 1, 2, 3])
        self.assertEqual([q["reason"] for q in self.queue_lines()], ["source-failing"])

    def crew_home(self, *args):
        """A watcher run from a copied crew home of its own, so the test can update its code on disk."""
        root = os.path.join(self.tmp, "home")
        shutil.copytree(os.path.dirname(os.path.dirname(CREW)), root,
                        ignore=shutil.ignore_patterns(".git", ".crew", "test-*", "fixtures"))
        scripts = os.path.join(root, "scripts")
        p = subprocess.Popen([sys.executable, os.path.join(scripts, "crew"), "watch", "--project", self.project,
                              *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        self.armed(p)
        return scripts, p

    def test_watch_reexecs_before_routing_with_a_new_profile_key(self):  # #702 R1: code and profile updated together
        scripts, p = self.crew_home("--interval", "2", "--no-nudge")
        time.sleep(0.3)  # asleep between scans
        config = os.path.join(os.path.dirname(scripts), "core", "crew-config.py")
        with open(config) as f:
            text = f.read()
        with open(config, "w") as f:
            f.write(text.replace('"poll_interval": (int, 60)', '"poll_interval": (int, 60), "reload_probe": (int, 1)'))
        with open(self.project, "a") as f:
            f.write("\n[runtime.options]\nreload_probe = 1\n")
        self.put("status/ben-7.status", "done: PR #12\n")
        out, err = p.communicate(timeout=20)
        self.assertEqual((p.returncode, out), (0, "status: ben-7 done: PR #12\n"), err)
        self.assertEqual(err, "crew: watch: crew code changed on disk; re-exec\n")

    def test_watch_reexecs_when_crew_code_changes(self):  # #702
        scripts, p = self.crew_home("--interval", "0.05")
        with open(os.path.join(os.path.dirname(scripts), "environments", "terminal", "crew.d", "watch.py"), "a") as f:
            f.write("\nsys.stderr.write('reloaded\\n')\n")  # runs at import, so only in a new process image
        time.sleep(1)  # a few scans: the re-exec'd watcher is armed again under the same PID
        self.assertIsNone(p.poll())
        with open(os.path.join(self.state, "wake", "watcher.pid")) as f:
            self.assertEqual(int(f.read()), p.pid)
        self.put("status/ben-7.status", "done: PR #12\n")
        out, err = p.communicate(timeout=10)
        self.assertEqual((p.returncode, out), (0, "status: ben-7 done: PR #12\n"), err)
        self.assertEqual(err, "crew: watch: crew code changed on disk; re-exec\nreloaded\n")
        self.assertFalse(os.path.exists(os.path.join(self.state, "wake", "watcher.pid")))

    def test_watch_source_timeout_floor_outlasts_a_short_interval(self):  # #272
        slow = shlex.join([sys.executable, "-c", "import time; time.sleep(0.5); print('pr-merged #9')"])
        out, _ = self.watch("--source", slow).communicate(timeout=20)  # 10 x --interval 0.05
        self.assertEqual(out, "poll: pr-merged #9\n")

    def test_watch_wakes_on_queue_growth_without_requeueing(self):
        p = self.watch()
        self.armed(p)
        rec = {"id": "poll-1", "source": "poll", "reason": "poll", "event": "ci-passed", "refs": ["#12"]}
        self.put("wake/queue.jsonl", json.dumps(rec) + "\n")  # a crew poll loop in its own window
        out, err = p.communicate(timeout=10)
        self.assertEqual(out, "poll: ci-passed\n", err)
        self.assertEqual(self.queue_lines(), [rec])
        out, _ = self.watch("--backstop", "0.1").communicate(timeout=10)  # offset saved: no second wake
        self.assertEqual(out, "backstop: due (work in flight)\n")

    def test_watch_does_not_double_queue_a_poll_source(self):
        script = os.path.join(self.tmp, "poll-once.py")  # appends its own record and prints a line, like crew poll
        with open(script, "w") as f:
            f.write("import json, sys\nwith open(sys.argv[1], 'a') as f:\n"
                    "    f.write(json.dumps({'reason': 'poll', 'event': 'ci-failed'}) + '\\n')\n"
                    "print('crew: poll: ci-failed -> builder #12')\n")
        os.makedirs(os.path.join(self.state, "wake"), exist_ok=True)
        queue = os.path.join(self.state, "wake", "queue.jsonl")
        source = ["--source", shlex.join([sys.executable, script, queue]), "--interval", "5"]  # timeout > startup
        out, _ = self.watch(*source).communicate(timeout=20)
        self.assertEqual(out, "poll: ci-failed\n")
        self.assertEqual(self.queue_lines(), [{"reason": "poll", "event": "ci-failed"}])

    def test_watch_triage_timer_reads_the_queue_this_scans_poll_wrote(self):  # #1098: resume, overdue slot
        with open(self.project, "a") as f:
            f.write("\n[triage]\nenabled = true\n")
        self.put("triage/queue.json", json.dumps({"items": []}))  # the pre-pause poll's queue
        self.put("triage/sweep.json", json.dumps({"at": time.time() - 20 * 3600, "outcome": "skipped: empty queue"}))
        script = os.path.join(self.tmp, "poll-once.py")  # queues the issue opened during the pause, like crew poll
        with open(script, "w") as f:
            f.write("import json, sys\nwith open(sys.argv[1], 'w') as f:\n"
                    "    json.dump({'items': [{'repo': 'acme/widgets', 'issue': 9, 'reason': 'new'}]}, f)\n"
                    "print('crew: poll: triage queued #9')\n")
        queue = os.path.join(self.state, "triage", "queue.json")
        out, err = self.watch("--source", shlex.join([sys.executable, script, queue])).communicate(timeout=60)
        self.assertEqual(out, "poll: crew: poll: triage queued #9\n", err)
        with open(os.path.join(self.state, "triage", "sweep.json")) as f:
            self.assertNotEqual(json.load(f)["outcome"], "skipped: empty queue")  # the overdue slot sweeps #9

    def test_second_watcher_leaves_the_armed_ones_pid_file(self):  # #591
        p = self.watch()
        self.armed(p)
        pidfile = os.path.join(self.state, "wake", "watcher.pid")
        with open(self.ps, "w") as f:
            json.dump({"command": {str(p.pid): "python3 scripts/crew watch --project crew.toml"}}, f)
        second = self.watch()
        out, _ = second.communicate(timeout=10)
        self.assertEqual((second.returncode, out), (1, "crew: a watcher is already armed (pid %d)\n" % p.pid))
        with open(pidfile) as f:
            self.assertEqual(int(f.read()), p.pid)
        self.assertIsNone(p.poll())
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=10)
        self.assertFalse(os.path.exists(pidfile))

    def test_watcher_removes_only_its_own_pid_file(self):  # #591: a stale or reused PID does not block arming
        pidfile = os.path.join(self.state, "wake", "watcher.pid")
        self.put("wake/watcher.pid", "%d\n" % os.getpid())  # live, but not crew watch
        p = self.watch()
        self.armed(p)
        self.put("wake/watcher.pid", "%d\n" % os.getpid())  # another watcher took over the file
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=10)
        with open(pidfile) as f:
            self.assertEqual(int(f.read()), os.getpid())

    def test_watch_sigterm_removes_pid_file_and_saves_state(self):
        p = self.watch()
        self.armed(p)
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM)
        self.assertFalse(os.path.exists(os.path.join(self.state, "wake", "watcher.pid")))
        with open(os.path.join(self.state, "wake", "watch-state.json")) as f:
            self.assertIn("queue", json.load(f))

    def test_watch_signal_waits_for_a_running_child(self):  # #272: a signal never leaves a child running
        done = os.path.join(self.tmp, "child-done")
        code = "import os, signal, time; os.kill(os.getppid(), signal.SIGTERM); time.sleep(0.3); open(%r, 'w')" % done
        p = self.watch("--source", shlex.join([sys.executable, "-c", code]))
        p.communicate(timeout=20)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM)
        self.assertTrue(os.path.exists(done))  # the child finished before the watcher exited
        self.assertFalse(os.path.exists(os.path.join(self.state, "wake", "watcher.pid")))

    def test_watch_second_signal_exits_at_once(self):  # #272: a held signal never makes a hung child unkillable
        started = os.path.join(self.tmp, "child-started")
        code = "import time; open(%r, 'w'); time.sleep(60)" % started
        p = self.watch("--source", shlex.join([sys.executable, "-c", code]), "--source-timeout", "60")
        for _ in range(200):
            if os.path.exists(started):
                break
            time.sleep(0.05)
        start = time.monotonic()
        while p.poll() is None and time.monotonic() - start < 20:  # signals sent apart, so two are delivered
            p.send_signal(signal.SIGTERM)
            time.sleep(0.1)
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM)
        self.assertLess(time.monotonic() - start, 20)

    def test_watch_sighup_like_sigterm(self):  # #234 N8
        p = self.watch()
        self.armed(p)
        p.send_signal(signal.SIGHUP)
        p.communicate(timeout=10)
        self.assertEqual(p.returncode, 128 + signal.SIGHUP)
        self.assertFalse(os.path.exists(os.path.join(self.state, "wake", "watcher.pid")))


if __name__ == "__main__":
    unittest.main()
