"""Tests for crew guard, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: decisions, an open owner ask (`asks/<n>.json`, also unreadable) blocking until it closes, a live
watcher, at most one block per stop cycle (Claude Code stop_hook_active, Codex notify payload), malformed input, no-op outside the coordinator window. Run in CI.
"""
import json
import os
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base


class Guard(Base):
    def guard(self, stdin='{"stop_hook_active": false}', role="coordinator"):
        r = self.crew("guard", "--state", self.state, stdin=stdin, CREW_ROLE=role)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def test_guard_allows_stop_with_no_work(self):
        self.assertIsNone(self.guard())

    def test_guard_blocks_work_in_flight_without_watcher(self):
        self.put("runs/ben-7.json", "{}")
        self.assertEqual(self.guard()["decision"], "block")
        os.remove(os.path.join(self.state, "runs", "ben-7.json"))
        self.put("wake/queue.jsonl", '{"reason": "status:"}\n')
        self.assertEqual(self.guard()["decision"], "block")

    def test_guard_blocks_open_owner_ask_without_watcher(self):
        self.put("asks/42.json", '{"deadline": "2026-11-02T09:00:00-08:00"}')
        self.assertEqual(self.guard()["decision"], "block")
        self.put("asks/42.json", "not json")  # unreadable: still open, as the watcher wakes on it at once
        self.assertEqual(self.guard()["decision"], "block")
        self.put("wake/watcher.pid", "%d\n" % os.getpid())
        self.assertIsNone(self.guard())
        os.remove(os.path.join(self.state, "wake", "watcher.pid"))
        os.remove(os.path.join(self.state, "asks", "42.json"))  # the coordinator closed the ask
        self.assertIsNone(self.guard())

    def test_guard_noop_outside_coordinator_window(self):
        self.put("runs/ben-7.json", "{}")
        for role in ["builder", "reviewer", "synthesizer", ""]:
            self.assertIsNone(self.guard(role=role), role)

    def test_guard_allows_stop_with_live_watcher(self):
        self.put("runs/ben-7.json", "{}")
        self.put("wake/watcher.pid", "%d\n" % os.getpid())
        self.assertIsNone(self.guard())
        self.put("wake/watcher.pid", "999999999\n")
        self.assertEqual(self.guard()["decision"], "block")

    def test_guard_blocks_at_most_once_per_stop_cycle(self):
        self.put("runs/ben-7.json", "{}")
        self.assertEqual(self.guard('{"stop_hook_active": false}')["decision"], "block")
        allowed = self.guard('{"stop_hook_active": true}')
        self.assertNotIn("decision", allowed)
        self.assertIn("no watcher is armed", allowed["systemMessage"])

    def test_guard_codex_notify_blocks_once_per_wake(self):
        """A Codex agent-turn-complete payload: the turn its own wake line started allows the stop (#170)."""
        self.put("runs/ben-7.json", "{}")
        turn = {"type": "agent-turn-complete", "thread-id": "t", "turn-id": "u", "last-assistant-message": "ok"}
        self.assertEqual(self.guard(json.dumps(dict(turn, **{"input-messages": ["Read your brief"]})))["decision"],
                         "block")
        allowed = self.guard(json.dumps(dict(turn, **{"input-messages": ["wake: turn-end guard"]})))
        self.assertNotIn("decision", allowed)
        self.assertIn("no watcher is armed", allowed["systemMessage"])
        for messages in [["wake: turn-end guard", "status?"], [], "wake: turn-end guard", 7, None]:
            self.assertEqual(self.guard(json.dumps(dict(turn, **{"input-messages": messages})))["decision"],
                             "block", messages)

    def test_guard_malformed_stdin_counts_as_not_active(self):
        self.put("runs/ben-7.json", "{}")
        for stdin in ["", "not json", "[1, 2]", "null"]:
            self.assertEqual(self.guard(stdin)["decision"], "block", stdin)
        os.remove(os.path.join(self.state, "runs", "ben-7.json"))
        for stdin in ["", "not json", '{"stop_hook_active": true}']:
            self.assertIsNone(self.guard(stdin), stdin)


if __name__ == "__main__":
    unittest.main()
