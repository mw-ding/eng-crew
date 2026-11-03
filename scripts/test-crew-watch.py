"""Tests for crew watch (and its scan), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: scan with a fake clock (fresh, silent, dead -> restart, twice -> escalate, status line once; a builder
after `done:` flagged when dead, a reviewer's `done:` terminal), exit with a reason line and queue record, PID
file, `--source` events, typed wake line only into an idle coordinator and never into one showing a captured
stuck screen (a `dialog` wake queued instead, #315), backstop backoff while idle, a never-exiting source cut
off at `--source-timeout` as `source-timeout`, a source slower than a short `--interval` not cut off (the 5 s
floor), a wake on queue growth with no re-queue, a self-queueing source queued once, SIGTERM removing the PID
file and saving state, a signal during a scan waiting for the running child, a second signal exiting at once,
SIGHUP like SIGTERM, a dialog waking at once (each captured stuck screen in `fixtures/dialog/`; a working
screen never), a stale key that ignores the liveness class, an owner ask waking at its deadline once per
deadline (an unreadable one at once), the scan sleep cut short to land on a deadline, an ask wake while the
backstop is backed off; unfinished spawns skip liveness wakes for 60 s, then wake as missing, while started missing
runs wake immediately. Run in CI.
"""
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import unittest
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
        out, _ = self.watch("--source", "sleep 30", "--source-timeout", "1").communicate(timeout=20)
        self.assertLess(time.monotonic() - start, 15)  # cut off at --source-timeout, long before the 30 s
        self.assertEqual(out, "source-timeout: sleep 30\n")
        self.assertEqual(self.queue_lines()[0]["reason"], "source-timeout")

    def test_watch_source_timeout_floor_outlasts_a_short_interval(self):  # #272
        slow = shlex.join([sys.executable, "-c", "import time; time.sleep(0.5); print('pr-merged #9')"])
        out, _ = self.watch("--source", slow).communicate(timeout=20)  # 10 x --interval 0.05, well inside 5 s
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
