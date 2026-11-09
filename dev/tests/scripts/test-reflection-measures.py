#!/usr/bin/env python3
"""Offline self-test for scripts/reflection-measures.py (no network), through its real CLI.

Covers the CSV round means (a missing column stays unknown), first-ready to merged with polling bounds, the union of
overlapping stalls with replayed samples deduped and an open stall bounded by its observation, confirmed
false-throttles counted by incident id while unconfirmed errors stay unclassified, null values and `unknown` coverage
without samples, and the ledger: merge ref with pending or confirmed activation, a baseline refused once activation is
confirmed. Run in CI.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts", "reflection-measures.py")
CSV = """repo,pr,state,opened_at,merged_at,open_to_merge_min,ci_fix_rounds,builder_fix_rounds,verdicts
a/b,1,merged,2026-11-01T00:00:00Z,2026-11-02T00:00:00Z,10,1,0,1
a/b,2,merged,2026-11-01T00:00:00Z,2026-11-03T00:00:00Z,10,0,2,3
a/b,3,merged,2026-10-01T00:00:00Z,2026-10-02T00:00:00Z,10,5,0,9
"""
POLL = [  # pr 7: ready sampled at 10:10 (previous poll 10:00), merged sampled at 11:10 (previous 11:00)
    {"source": "poll", "pr": 7, "ts": "2026-11-02T10:10:00Z", "prev_ts": "2026-11-02T10:00:00Z", "ready": True,
     "state": "OPEN"},
    {"source": "poll", "pr": 7, "ts": "2026-11-02T10:30:00Z", "prev_ts": "2026-11-02T10:20:00Z", "ready": True,
     "state": "OPEN"},
    {"source": "poll", "pr": 7, "ts": "2026-11-02T11:10:00Z", "prev_ts": "2026-11-02T11:00:00Z", "ready": False,
     "state": "MERGED"},
    {"source": "poll", "pr": 8, "ts": "2026-11-02T11:10:00Z", "prev_ts": None, "ready": False, "state": "MERGED"},
]
WATCH = [
    {"source": "watch", "kind": "stall", "key": "run:ben-1", "since": "2026-11-02T12:00:00Z",
     "ts": "2026-11-02T12:15:00Z"},
    {"source": "watch", "kind": "stall", "key": "run:ben-1", "since": "2026-11-02T12:00:00Z",
     "ts": "2026-11-02T12:16:00Z"},  # replayed scan: same stall
    {"source": "watch", "kind": "resume", "key": "run:ben-1", "since": "2026-11-02T12:00:00Z",
     "ts": "2026-11-02T12:30:00Z"},
    {"source": "watch", "kind": "stall", "key": "run:vera-2", "since": "2026-11-02T12:20:00Z",
     "ts": "2026-11-02T12:40:00Z"},  # overlaps ben-1's wait; never resumed
]
INCIDENTS = [
    {"id": "outage-1474", "kind": "false-throttle", "confirmed": "https://x/issues/1474#c", "ts": "2026-11-02T00:00:00Z"},
    {"id": "outage-1474", "kind": "false-throttle", "confirmed": "https://x/issues/1475#c", "ts": "2026-11-02T01:00:00Z"},
    {"id": "quoted-pane", "kind": "false-throttle", "ts": "2026-11-02T02:00:00Z"},  # not confirmed
]
ERRORS = [{"source": "ben-1", "text": "429", "ts": "2026-11-02T03:00:00Z"},
          {"source": "ben-1", "text": "429", "ts": "2026-11-02T03:00:30Z"},  # same error still on screen
          {"source": "vera-2", "text": "overloaded", "ts": "2026-11-02T04:00:00Z"}]


class ReflectionMeasures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.paths = {}
        for name, rows in (("obs", POLL + WATCH), ("incidents", INCIDENTS), ("errors", ERRORS)):
            self.paths[name] = os.path.join(self.tmp, name + ".jsonl")
            with open(self.paths[name], "w") as f:
                f.writelines(json.dumps(r) + "\n" for r in rows)
        self.paths["csv"] = os.path.join(self.tmp, "prs.csv")
        with open(self.paths["csv"], "w") as f:
            f.write(CSV)
        self.ledger = os.path.join(self.tmp, "ledger.jsonl")

    def run_cli(self, *args, code=0):
        r = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def window(self, obs=None):
        return ["--since", "2026-11-01", "--until", "2026-11-05", "--csv", self.paths["csv"],
                "--observations", obs or self.paths["obs"], "--incidents", self.paths["incidents"],
                "--errors", self.paths["errors"]]

    def measure(self, obs=None):
        return json.loads(self.run_cli("measure", *self.window(obs)).stdout)

    def test_csv_round_means_and_missing_column_unknown(self):
        out = self.measure()
        self.assertEqual((out["verdict_rounds_per_pr"]["value"], out["verdict_rounds_per_pr"]["n"]), (2.0, 2))
        self.assertEqual(out["verdict_rounds_per_pr"]["refs"], ["a/b#1", "a/b#2"])
        self.assertEqual(out["ci_fix_rounds_per_pr"]["value"], 0.5)
        with open(self.paths["csv"], "w") as f:
            f.write("repo,pr,merged_at\na/b,1,2026-11-02T00:00:00Z\n")
        out = self.measure()
        self.assertEqual((out["verdict_rounds_per_pr"]["value"], out["verdict_rounds_per_pr"]["n"]), (None, 0))

    def test_ready_to_land_first_observed_ready_with_polling_bounds(self):
        ready = self.measure()["ready_to_land"]
        self.assertEqual((ready["value"], ready["bounds"], ready["n"], ready["refs"]), (60.0, [50.0, 70.0], 1, ["pr#7"]))
        self.assertEqual(ready["coverage"]["from"], "2026-11-02T10:10:00Z")
        self.assertTrue(ready["coverage"]["partial"])

    def test_stall_minutes_union_overlapping_waits_and_dedupe_replays(self):
        stall = self.measure()["stall_minutes"]
        self.assertEqual((stall["value"], stall["n"], stall["open"]), (40.0, 2, 1))  # 12:00-12:40, not 30+20
        self.assertEqual(stall["refs"], ["run:ben-1", "run:vera-2"])
        poll_only = os.path.join(self.tmp, "poll.jsonl")
        with open(poll_only, "w") as f:
            f.writelines(json.dumps(r) + "\n" for r in POLL)
        self.assertEqual(self.measure(poll_only)["stall_minutes"]["value"], 0.0)  # sampled, none stalled

    def test_false_throttles_confirmed_only_and_unconfirmed_unclassified(self):
        ft = self.measure()["false_throttles"]
        self.assertEqual((ft["value"], ft["refs"], ft["unclassified_errors"]), (1, ["outage-1474"], 2))
        with open(self.paths["incidents"], "w") as f:
            f.write(json.dumps(INCIDENTS[2]) + "\n")
        self.assertEqual(self.measure()["false_throttles"]["value"], 0)  # a read file with none confirmed: zero
        os.remove(self.paths["incidents"])
        ft = self.measure()["false_throttles"]
        self.assertEqual((ft["value"], ft["coverage"]), (None, "unknown"))  # no incident file: unknown

    def test_no_observations_stay_unknown(self):
        empty = os.path.join(self.tmp, "none.jsonl")
        out = self.measure(empty)
        for name in ("ready_to_land", "stall_minutes"):
            self.assertEqual((out[name]["value"], out[name]["n"], out[name]["coverage"]), (None, 0, "unknown"))

    def test_ledger_baseline_before_activation_only(self):
        self.run_cli("baseline", "--ledger", self.ledger, "--proposal", "P1", *self.window())
        r = self.run_cli("record", "--ledger", self.ledger, "--proposal", "P1", "--merge-ref", "#1600")
        self.assertIn("activation pending", r.stdout)
        self.run_cli("baseline", "--ledger", self.ledger, "--proposal", "P1", *self.window())  # still before activation
        self.run_cli("record", "--ledger", self.ledger, "--proposal", "P1", "--merge-ref", "#1600",
                     "--activation", "v0.40.0 installed")
        r = self.run_cli("baseline", "--ledger", self.ledger, "--proposal", "P1", *self.window(), code=1)
        self.assertIn("refused: P1 already has a confirmed activation", r.stderr)
        with open(self.ledger) as f:
            rows = [json.loads(line) for line in f]
        self.assertEqual([(r["type"], r.get("activation")) for r in rows],
                         [("baseline", None), ("activation", "pending"), ("baseline", None),
                          ("activation", "v0.40.0 installed")])
        self.assertEqual(rows[0]["window"], {"since": "2026-11-01T00:00:00Z", "until": "2026-11-05T00:00:00Z"})
        self.assertEqual(rows[0]["stall_minutes"]["value"], 40.0)


if __name__ == "__main__":
    unittest.main()
