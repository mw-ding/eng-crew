"""Tests for crew schedule snapshot (docs/scheduling.md#inputs): every input read from a fixture state dir into one
JSON object, `unknown` per failed read, memory pressure on macOS and Linux. Fake tmux and gh; run in CI.
"""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import unittest
from unittest import mock
from crew_testlib import CREW, Base

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
if os.environ.get("FAKE_GH_FAIL"):
    sys.exit(1)
args = sys.argv[1:]
if args[0] == "api":
    print(json.dumps([{"number": 34, "title": "M18.2"}, {"number": 30, "title": "M21"}]))
elif args[:2] == ["issue", "list"]:
    print(json.dumps([
        {"number": 620, "milestone": {"title": "M18.2"}, "body": "## Depends on\\n\\n#598. Start after.\\n\\n## AC\\n#1"},
        {"number": 622, "milestone": None, "body": "Depends on #620, #621\\n"},
        {"number": 7, "milestone": None, "body": None}]))
"""


class Snapshot(Base):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.tmp, "bin", "gh"), "w") as f:
            f.write(FAKE_GH)
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash"}}, f)
        now = datetime.datetime.now(datetime.timezone.utc)
        stamp = lambda minutes: (now - datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.event = os.path.join(self.state, "leads", "builder-events", "e1.json")
        self.put("leads/builder-events/e1.json", json.dumps({"event": "pr-merged", "refs": ["#5"]}))
        self.put("inbox/ben-lead.jsonl", "".join(json.dumps(m) + "\n" for m in [
            {"id": "b1", "kind": "build", "refs": ["#620"], "ts": stamp(5)},
            {"id": "b2", "kind": "merge-up", "refs": ["#601"], "ts": stamp(4)}]))
        self.put("status/ben-lead.status", "ack: b1\ndone: b1\n")
        self.put("inbox/vera-lead.jsonl", "".join(json.dumps(m) + "\n" for m in [
            {"id": "r1", "kind": "review", "refs": ["#601", "a" * 40, "1"]},
            {"id": "r2", "kind": "work", "refs": [self.event]}]))
        self.put("spawn-queue.jsonl", "".join(json.dumps(e) + "\n" for e in [
            {"role": "builder", "issue": 9, "pr": None, "pass": "build", "queued": stamp(3)},
            {"role": "reviewer", "issue": None, "pr": 8, "pass": "review", "queued": stamp(3)}]))
        self.put("schedule/reservations.json", json.dumps([{"ref": "#9", "pool": "builder", "time": stamp(1)}]))
        self.put("schedule/errors.jsonl", json.dumps({"ts": stamp(2)}) + "\n" + json.dumps({"ts": stamp(30)}) + "\n")
        self.put("inbox/sam.jsonl", "".join(json.dumps(m) + "\n" for m in [
            {"id": "l1", "kind": "land", "refs": ["#11", "c" * 40]},
            {"id": "l2", "kind": "land", "refs": ["#12", "d" * 40]}]))
        self.put("inbox/synthesizer-pending.jsonl", json.dumps({"id": "l3", "kind": "land", "refs": ["#13"]}) + "\n")
        self.put("status/sam.status", "ack: l1\ndone: #11 " + "c" * 40 + "\nack: l2\n")
        self.put("trains/train-3.json", json.dumps({"members": [1, 2], "landed": [1]}))
        run = dict(index=10, item="issue #7", repo="acme/widgets", worktree="/wt", claim="/c", engine="codex",
                   model="m", effort="e", harness="codex")
        self.put("runs/ben-7.json", json.dumps(dict(run, role="builder", **{"pass": "build"})))
        self.put("status/ben-7.status", "done: #7 #12 " + "b" * 40 + "\n")
        self.put("runs/vera-8.json", json.dumps(dict(run, index=20, role="reviewer", **{"pass": "review"})))

    def snapshot(self, **env):
        r = self.crew("schedule", "snapshot", "--project", self.project, **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_every_input_from_fixture_state(self):
        snap = self.snapshot()
        builder = snap["demand"]["builder"]
        self.assertEqual([(d["kind"], d.get("queued", False)) for d in builder], [("merge-up", False), ("build", True)])
        reviewer = snap["demand"]["reviewer"]
        self.assertEqual([d["kind"] for d in reviewer], ["review", "work"])
        self.assertEqual(reviewer[1]["event"]["event"], "pr-merged")
        self.assertEqual({w["name"]: w["state"] for w in snap["workers"]}, {"ben-7": "idle", "vera-8": "exited"})
        self.assertEqual(snap["reservations"][0]["ref"], "#9")
        self.assertEqual(snap["trains"], ["train-3.json"])
        self.assertEqual(sorted(land["refs"][0] for land in snap["lands"]), ["#12", "#13"])
        self.assertEqual(snap["errors"], 1)
        self.assertEqual(snap["caps"], {"builder": 5, "reviewer": 2})
        self.assertIsInstance(snap["load"], float)
        self.assertIn(snap["memory"] if snap["memory"] == "unknown" else snap["memory"]["os"],
                      ("darwin", "linux", "unknown"))
        tracker = snap["tracker"]
        self.assertEqual([m["title"] for m in tracker["milestones"]], ["M18.2", "M21"])
        self.assertEqual(tracker["max_active"], 1)
        self.assertEqual({i["number"]: (i["milestone"], i["depends"]) for i in tracker["issues"]},
                         {620: ("M18.2", [598]), 622: (None, [620, 621]), 7: (None, [])})

    def test_failed_reads_are_unknown_per_input(self):
        os.remove(self.event)
        snap = self.snapshot(FAKE_GH_FAIL="1")
        self.assertEqual(snap["demand"]["reviewer"], "unknown")
        self.assertEqual(len(snap["demand"]["builder"]), 2)
        self.assertEqual(snap["tracker"], "unknown")
        self.put("away-control.json", json.dumps({"issue": 110}))
        self.put("schedule/errors.jsonl", "{not json\n")
        self.put("inbox/sam.jsonl", "{not json\n")
        snap = self.snapshot(FAKE_GH_FAIL="1")
        self.assertEqual(snap["caps"], {"builder": "unknown", "reviewer": "unknown"})
        self.assertEqual(snap["errors"], "unknown")
        self.assertEqual(snap["lands"], "unknown")
        self.assertEqual(snap["reservations"][0]["ref"], "#9")


class Memory(unittest.TestCase):
    def setUp(self):
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(mod)
        self.schedule = mod.commands()["schedule"]

    def test_macos_pressure_levels(self):
        for raw, level in (("1\n", "normal"), ("2\n", "warn"), ("4\n", "critical")):
            done = subprocess.CompletedProcess([], 0, stdout=raw)
            with mock.patch.object(self.schedule.platform, "system", return_value="Darwin"), \
                    mock.patch.object(self.schedule.subprocess, "run", return_value=done):
                self.assertEqual(self.schedule.memory(), {"os": "darwin", "level": level})

    def test_linux_psi_some_avg10(self):
        psi = "some avg10=12.50 avg60=3.00 avg300=1.00 total=1\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        with mock.patch.object(self.schedule.platform, "system", return_value="Linux"), \
                mock.patch("builtins.open", mock.mock_open(read_data=psi)):
            self.assertEqual(self.schedule.memory(), {"os": "linux", "some_avg10": 12.5})

    def test_unreadable_pressure_is_unknown(self):
        with mock.patch.object(self.schedule.platform, "system", return_value="Linux"), \
                mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(self.schedule.read(self.schedule.memory), "unknown")


if __name__ == "__main__":
    unittest.main()
