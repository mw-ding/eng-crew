"""Tests for mdstack logs, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: tails only the newest summary, `-f` execs `tail`, no run or summary refused. Run in
CI.
"""
import json
import os
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import ObserveBase


class Logs(ObserveBase):
    def summary(self, wt, rel, lines, mtime):
        path = os.path.join(wt, ".crew", "runs", rel, "summary.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.utime(path, (mtime, mtime))
        return path

    def test_logs_tails_newest_summary_only(self):
        wt = os.path.join(self.tmp, "state", "wt", "7-abcdef0-builder-build")
        self.put("runs/ben-7.json", json.dumps({"worktree": wt}))
        self.summary(wt, "issue-7/r1", ["old step"], 1000)
        newest = self.summary(wt, "pr-12/r2", ["# Run summary", "- build ok", "- unit-tests fail"], 2000)
        steps = os.path.join(os.path.dirname(newest), "steps")
        os.makedirs(steps)
        with open(os.path.join(steps, "unit-tests.log"), "w") as f:
            f.write("RAW LOG LINE\n")
        r = self.crew("logs", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(newest, r.stdout)
        self.assertIn("- unit-tests fail", r.stdout)
        self.assertNotIn("old step", r.stdout)
        self.assertNotIn("RAW LOG LINE", r.stdout)
        r = self.crew("logs", "ben-7", "-n", "1", "--project", self.project)
        self.assertEqual(r.stdout.splitlines()[1:], ["- unit-tests fail"])

    def test_logs_follow_execs_tail(self):
        wt = os.path.join(self.tmp, "wt-7")
        self.put("runs/ben-7.json", json.dumps({"worktree": wt}))
        path = self.summary(wt, "issue-7/r1", ["- build ok"], 1000)
        tail = os.path.join(self.tmp, "bin", "tail")
        with open(tail, "w") as f:
            f.write('#!/bin/sh\necho "tail $*"\n')
        os.chmod(tail, 0o755)
        r = self.crew("logs", "ben-7", "-f", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "tail -n 20 -f " + path)

    def test_logs_refuses_without_run_or_summary(self):
        r = self.crew("logs", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no run ben-7", r.stdout)
        self.put("runs/ben-7.json", json.dumps({"worktree": os.path.join(self.tmp, "wt-7")}))
        r = self.crew("logs", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no step summary yet", r.stdout)


if __name__ == "__main__":
    unittest.main()
