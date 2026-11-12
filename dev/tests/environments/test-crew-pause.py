"""Tests for mdstack pause and the project pause barrier (#1714); fixtures in crew_testlib.py (stdlib only).

Covers: the barrier is written before anything stops and refuses while a land holds the lock (exit 75, nothing
stopped); every window but window 0 stops with each run's worktree, record, claim, inbox and status kept, lead
records dropped and the session kept; pausing again is safe; a role host that does not answer is an incomplete pause
with the barrier kept; plain down refuses while paused and keeps remote work; dispatch, message, land, restart, train, cleanup, route and up's role windows refuse while
paused, and an unreadable barrier refuses as paused; the watcher queues events without routing or nudging. Run in CI.
"""
import fcntl
import json
import os
import subprocess
import sys
import time
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import CREW, KillLandedBase, ObserveBase


class Pause(KillLandedBase):
    def pause(self, *args):
        return self.crew("pause", "--project", self.project, *args)

    def barrier(self):
        with open(os.path.join(self.state, "pause.json")) as f:
            return json.load(f)

    def test_pause_stops_workers_keeps_window_0_and_all_work(self):
        wt = self.builder()
        with open(os.path.join(wt, "wip.txt"), "w") as f:
            f.write("x\n")
        self.put("inbox/ben-7.jsonl", '{"id": "m1"}\n')
        self.put("status/ben-7.status", "ack: m1\n")
        r = self.pause("--reason", "owner asked")
        self.assertEqual((r.returncode, r.stdout), (0, "crew: paused; window 0 and the watcher kept; stopped ben-7; "
                                                       "work kept (mdstack resume)\n"), r.stderr)
        kills = [c for c in self.calls() if c[0].startswith("kill-")]
        self.assertEqual(kills, [["kill-window", "-t", "=crew-acme-widgets:10"]])  # never window 0 or the session
        self.assertEqual({k: v for k, v in self.barrier().items() if k != "at"},
                         {"reason": "owner asked", "stopped": ["ben-7"], "state": "paused"})
        self.assertTrue(os.path.isfile(os.path.join(wt, "wip.txt")))
        for rel in ("runs/ben-7.json", "runs/ben-7.brief.md", "claims/builder-issue7", "inbox/ben-7.jsonl",
                    "status/ben-7.status"):
            self.assertTrue(os.path.exists(os.path.join(self.state, rel)), rel)
        again = self.pause()
        self.assertEqual(again.returncode, 0, again.stdout)
        self.assertEqual(self.barrier()["stopped"], ["ben-7"])  # the first pause's stopped runs are kept

    def test_pause_waits_for_a_land_holding_the_lock(self):
        self.builder()
        os.makedirs(os.path.join(self.state, "locks"), exist_ok=True)
        with open(os.path.join(self.state, "locks", "merge.lock"), "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            r = self.pause()
        self.assertEqual(r.returncode, 75, r.stdout + r.stderr)
        self.assertIn("crew: pausing: a land holds", r.stdout)
        self.assertEqual(self.barrier()["state"], "pausing")  # written first: no new land starts meanwhile
        self.assertEqual([c for c in self.calls() if c[0].startswith("kill-")], [])

    def test_paused_project_refuses_work_paths(self):
        self.builder()
        self.assertEqual(self.pause().returncode, 0)
        for argv in (["spawn", "builder", "--issue", "8"], ["dequeue"], ["send", "ben-7", "fix", "#7"],
                     ["kill", "ben-7"], ["restart", "ben-7"], ["land-lock", "acquire"], ["gc", "--apply"],
                     ["train", "build", "12"], ["route"]):
            r = self.crew(*argv, "--project", self.project)
            self.assertIn("crew: project paused (since ", r.stdout, argv)
            if argv != ["route"]:
                self.assertEqual(r.returncode, 1, argv)
        self.assertEqual(self.crew("land-lock", "release", "--project", self.project).returncode, 0)
        up = self.crew("up", "--project", self.project)
        self.assertEqual(up.returncode, 0, up.stdout)
        self.assertIn("crew: project paused; started no role windows (mdstack resume)", up.stdout)
        self.assertEqual(len(self.windows()), 1)  # only the builder spawned before the pause

    def test_unreadable_barrier_counts_as_paused_and_pause_rewrites_it(self):
        self.put("pause.json", "{not json")
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("crew: project paused (pause state unreadable: ", r.stdout)
        self.assertEqual(self.pause().returncode, 0)
        self.assertEqual(self.barrier()["state"], "paused")

    def test_watcher_keeps_events_and_routes_nothing_while_paused(self):
        self.assertEqual(self.pause().returncode, 0)
        source = os.path.join(self.tmp, "source.sh")
        with open(source, "w") as f:
            f.write("#!/bin/sh\necho 'new-head #12'\n")
        os.chmod(source, 0o755)
        p = subprocess.Popen([sys.executable, CREW, "watch", "--project", self.project, "--interval", "0.2",
                              "--source", source, "--source-interval", "0"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env)
        queue, deadline = os.path.join(self.state, "wake", "queue.jsonl"), time.monotonic() + 30
        while not os.path.exists(queue) and time.monotonic() < deadline:
            time.sleep(0.1)
        with self.assertRaises(subprocess.TimeoutExpired):  # a paused one-shot watcher never exits on a wake
            p.communicate(timeout=1)
        p.terminate()
        out, _ = p.communicate(timeout=10)
        with open(queue) as f:
            queued = [json.loads(line) for line in f]
        self.assertEqual({(w["reason"], w["event"]) for w in queued}, {("poll", "new-head #12")})
        self.assertNotIn("route", out)
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])  # no nudge
        self.assertFalse(os.path.exists(os.path.join(self.state, "routines")))  # no routine ran


class PauseRemote(ObserveBase):
    def test_role_host_refusal_is_an_incomplete_pause(self):
        self.put("leads/synthesizer.json", json.dumps({"name": "sam", "role": "synthesizer-lead", "index": 1}))
        self.remote_run("ben-12", kill=dict(result="unreachable", error="no route"))
        r = self.crew("pause", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("crew: pause incomplete: pane processes survived, or their host did not answer, in ben-12", r.stdout)
        with open(os.path.join(self.state, "pause.json")) as f:
            rec = json.load(f)
        self.assertEqual(rec["state"], "pausing")
        self.assertFalse(os.path.exists(os.path.join(self.state, "leads", "synthesizer.json")))  # stopped: fresh on resume
        self.assertNotIn(["kill-window", "-t", "=crew-acme-widgets:0"], self.calls())
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-12.json")))

    def test_plain_down_refuses_while_paused_and_keeps_remote_work(self):
        self.remote_run("ben-12", kill=dict(result="ok", unlanded=[], removed=False))
        self.assertEqual(self.crew("pause", "--project", self.project).returncode, 0)
        r = self.crew("down", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("crew: project paused (since ", r.stdout)
        self.assertEqual([c["request"]["discard"] for c in self.ssh_calls() if c["request"]["verb"] == "kill"], [False])
        self.assertTrue(all(c["request"]["keep"] for c in self.ssh_calls() if c["request"]["verb"] == "kill"))
        for rel in ("runs/ben-12.json", "pause.json"):
            self.assertTrue(os.path.exists(os.path.join(self.state, rel)), rel)
        self.assertNotIn("kill-session", [c[0] for c in self.calls()])


if __name__ == "__main__":
    unittest.main()
