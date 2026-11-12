"""Tests for mdstack resume (#1714); fixtures in crew_testlib.py (stdlib only).

Covers: no pause is a no-op; an unreadable barrier and refused ownership keep the pause; resume clears only
pause.json, restarts each run the pause stopped once in its own worktree without spending its one restart (so pause
and resume repeat safely), leaves a held item's run, a `done:` run, a live hold, a closed item, a failed live read and a
reviewer whose PR head moved stopped, never touches window 0, and queues one
`resume` wake for the coordinator. Run in CI.
"""
import json
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import LivenessBase


FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
views = json.load(open(os.environ["FAKE_GH_VIEWS"]))
key = " ".join(a[:1] + a[2:3])
if a[1:2] == ["view"] and key in views:
    if views[key] is None:
        print("HTTP 502", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(views[key]))
else:
    print(json.dumps({"labels": [], "closingIssuesReferences": []}))
"""


class Resume(LivenessBase):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.tmp, "bin", "gh"), "w") as f:  # live item reads at resume (#1714)
            f.write(FAKE_GH)
        self.env["FAKE_GH_VIEWS"] = os.path.join(self.tmp, "gh-views.json")
        self.views({"issue 7": {"state": "OPEN", "labels": []}})

    def views(self, views):
        with open(self.env["FAKE_GH_VIEWS"], "w") as f:
            json.dump(views, f)

    def run_crew(self, cmd):
        return self.crew(cmd, "--project", self.project, *(["--timeout", "1"] if cmd == "resume" else []))

    def resume_wakes(self):
        path = os.path.join(self.state, "wake", "queue.jsonl")
        with open(path) if os.path.exists(path) else open(os.devnull) as f:
            return [w for w in map(json.loads, f) if w["reason"] == "resume"]

    def unlanded(self):
        wt = self.record("ben-7")["worktree"]
        self.git("commit", "-q", "--allow-empty", "-m", "local only", cwd=wt)
        return wt

    def test_resume_without_a_pause_is_a_no_op(self):
        r = self.run_crew("resume")
        self.assertEqual((r.returncode, r.stdout), (0, "crew: not paused\n"))
        self.assertEqual(self.resume_wakes(), [])

    def test_unreadable_barrier_is_kept(self):
        self.put("pause.json", "[")
        r = self.run_crew("resume")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing resume: pause state unreadable", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.state, "pause.json")))

    def test_pause_and_resume_repeat_and_restart_each_stopped_run_once(self):
        wt = self.unlanded()
        self.put("asks/99.json", json.dumps({"deadline": "2099-01-01T00:00:00+00:00"}))  # another hold, kept
        for round_ in (1, 2):
            self.assertEqual(self.run_crew("pause").returncode, 0)
            self.set_pane(10, dead="1")
            before = len(self.windows())
            r = self.run_crew("resume")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("crew: resumed; restarted ben-7; stopped none", r.stdout)
            self.assertEqual(len(self.windows()), before + 1)  # one relaunch per resume
            rec = self.record("ben-7")
            self.assertEqual((rec["worktree"], rec.get("restarts", 0)), (wt, 0))  # the one restart is unspent
            self.assertFalse(os.path.exists(os.path.join(self.state, "pause.json")))
            self.assertEqual(len(self.resume_wakes()), round_)
        self.assertTrue(os.path.exists(os.path.join(self.state, "asks", "99.json")))
        self.assertNotIn(["kill-window", "-t", "=crew-acme-widgets:0"], self.calls())
        self.assertEqual([c for c in self.calls() if c[0] == "respawn-window"], [])  # window 0 untouched

    def test_held_run_stays_stopped(self):
        self.unlanded()
        self.assertEqual(self.run_crew("pause").returncode, 0)
        self.set_pane(10, dead="1")
        before = len(self.windows())
        self.put("asks/7.json", json.dumps({"deadline": "2099-01-01T00:00:00+00:00"}))
        r = self.run_crew("resume")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("restarted none; stopped ben-7 (held)", r.stdout)
        self.assertEqual(len(self.windows()), before)
        self.assertEqual(self.resume_wakes()[0]["event"], "restarted none; stopped ben-7 (held)")

    def test_done_run_stays_stopped(self):
        self.put("status/ben-7.status", "done: #7 #12 %s\nheartbeat: 2026-01-01T00:00:00Z\n" % ("a" * 40))
        self.assertEqual(self.run_crew("pause").returncode, 0)
        self.set_pane(10, dead="1")
        before = len(self.windows())
        r = self.run_crew("resume")
        self.assertIn("restarted none; stopped ben-7 (done)", r.stdout)
        self.assertEqual(len(self.windows()), before)

    def test_live_hold_moved_reviewer_head_and_failed_read_keep_runs_stopped(self):
        self.unlanded()
        self.assertEqual(self.run_crew("pause").returncode, 0)
        self.set_pane(10, dead="1")
        before, barrier = len(self.windows()), json.dumps({"at": "x", "reason": "r", "stopped": ["ben-7"], "state": "paused"})
        for views, want in (({"issue 7": {"state": "OPEN", "labels": [{"name": "crew:hold"}]}}, "ben-7 (held)"),
                            ({"issue 7": {"state": "CLOSED", "labels": []}}, "ben-7 (issue #7 closed)"),
                            ({"issue 7": None}, "ben-7 (unreadable: gh issue view: HTTP 502)")):
            self.views(views)  # live only: poll-state.json and asks/ say nothing
            self.put("pause.json", barrier)
            r = self.run_crew("resume")
            self.assertIn("restarted none; stopped %s" % want, r.stdout)
            self.assertEqual(len(self.windows()), before)
        rec = self.record("ben-7")
        rec.update(role="reviewer", head="a" * 40, args=dict(rec["args"], pr=12, issue=None))
        self.put("runs/ben-7.json", json.dumps(rec))
        self.views({"pr 12": {"state": "OPEN", "labels": [], "headRefOid": "b" * 40}})
        self.put("pause.json", barrier)
        self.assertIn("restarted none; stopped ben-7 (head moved)", self.run_crew("resume").stdout)
        self.assertEqual(len(self.windows()), before)

    def test_resume_refuses_without_ownership_and_keeps_the_pause(self):
        self.assertEqual(self.run_crew("pause").returncode, 0)
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:  # an unreadable control item: ownership is read-only
            f.write(text.replace('name = "widgets"', 'name = "widgets"\ncontrol_item = 123', 1).replace(
                'name = "tmux"', 'name = "tmux"\ninstance = "local"', 1))
        r = self.run_crew("resume")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("ownership: read-only; refusing start", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.state, "pause.json")))
        self.assertEqual(self.resume_wakes(), [])

if __name__ == "__main__":
    unittest.main()
