"""Tests for crew watch (and its scan), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import unittest
from crew_testlib import CREW, HEAD, LivenessBase, NOW


class Watch(LivenessBase):
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
        self.assertEqual(self.scan(NOW, {"offsets": {"ben-7": 54}, "keys": {}}), [])  # alive, waiting for its inbox
        self.set_pane(10, dead="1")
        self.assertEqual([(w["liveness"], w["action"]) for w in self.scan(NOW, {"offsets": {"ben-7": 54}, "keys": {}})],
                         [("dead", "restart")])
        rec = self.record("ben-7")
        rec["role"] = "reviewer"
        with open(os.path.join(self.state, "runs", "ben-7.json"), "w") as f:
            json.dump(rec, f)
        self.assertEqual(self.scan(NOW, {"offsets": {"ben-7": 54}, "keys": {}}), [])  # a reviewer done: is terminal

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
        out, _ = self.watch("--source", "sleep 30").communicate(timeout=10)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(out, "source-timeout: sleep 30\n")
        self.assertEqual(self.queue_lines()[0]["reason"], "source-timeout")

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


if __name__ == "__main__":
    unittest.main()
