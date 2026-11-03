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
            {"id": "l2", "kind": "land", "refs": ["#12", "d" * 40]},
            {"id": "l4", "kind": "land", "refs": ["#14"]}]))
        self.put("inbox/synthesizer-pending.jsonl", json.dumps({"id": "l3", "kind": "land", "refs": ["#13"]}) + "\n")
        self.put("status/sam.status", "ack: l1\ndone: #11 " + "c" * 40 + "\nack: l2\nack: l4\ndone: #14 " + "e" * 40 + "\n")
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
    @staticmethod
    def load():
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(mod)
        return mod.commands()["schedule"]

    def setUp(self):
        self.schedule = self.load()

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


def item(kind, n, ts="2026-11-02T10:00:00Z", **kw):
    return dict(id="%s%d" % (kind, n), kind=kind, refs=["#%d" % n], ts=ts, **kw)


class Rank(unittest.TestCase):
    def setUp(self):
        self.schedule = Memory.load()
        self.snap = dict(
            demand={"builder": [], "reviewer": []},
            workers=[{"name": "ben-30", "item": "issue #30", "pr": 31}, {"name": "ben-40", "item": "issue #40", "pr": None}],
            tracker=dict(milestones=[{"number": 1, "title": "M18"}, {"number": 2, "title": "M21"}], max_active=2,
                         issues=[dict(number=10, milestone="M18", depends=[]), dict(number=20, milestone="M21", depends=[]),
                                 dict(number=30, milestone="M21", depends=[]), dict(number=11, milestone="M18", depends=[])]))

    def ranked(self, builder=(), reviewer=(), **kw):
        self.snap["demand"] = {"builder": list(builder), "reviewer": list(reviewer)}
        return [(r["class"], r["ref"]) for r in self.schedule.rank(self.snap, **kw)]

    def test_eight_classes_finish_before_start(self):
        got = self.ranked(
            builder=[item("build", 20), item("build", 10), item("fix", 31), item("merge-up", 32), item("build", 9)],
            reviewer=[item("review", 33), item("validate", 34), item("recheck", 35)], red_fixes={9})
        self.assertEqual(got, [(1, "#9"), (2, "#35"), (3, "#32"), (4, "#34"), (5, "#33"), (6, "#31"), (7, "#10"), (8, "#20")])

    def test_ci_red_ranks_with_fix_and_red_fix_beats_everything(self):
        got = self.ranked(builder=[item("ci-red", 31, ts="2026-11-02T09:00:00Z"), item("fix", 32, ts="2026-11-02T08:00:00Z")],
                          reviewer=[item("recheck", 35)], red_fixes={31})
        self.assertEqual(got, [(1, "#31"), (2, "#35"), (6, "#32")])

    def test_unknown_milestone_with_one_active_is_class_7(self):
        self.snap["tracker"]["max_active"] = 1
        self.assertEqual(self.ranked(builder=[item("build", 99), item("build", 20), item("build", 10)]),
                         [(7, "#99"), (7, "#10"), (8, "#20")])

    def test_unknown_milestone_is_latest_active(self):
        self.assertEqual(self.ranked(builder=[item("build", 99), item("build", 10)]), [(7, "#10"), (8, "#99")])

    def test_milestone_tie_break_maps_pr_to_issue(self):
        got = self.ranked(builder=[item("fix", 31, ts="2026-11-02T08:00:00Z"), item("fix", 50, ts="2026-11-02T09:00:00Z"),
                                   item("fix", 12, ts="2026-11-02T10:00:00Z")])
        self.assertEqual(got, [(6, "#31"), (6, "#50"), (6, "#12")])
        self.snap["workers"].append({"name": "ben-10", "item": "issue #10", "pr": 12})
        self.assertEqual(self.ranked(builder=[item("fix", 31), item("fix", 12)]), [(6, "#12"), (6, "#31")])

    def test_critical_path_counts_transitive_waiters(self):
        self.snap["tracker"]["issues"] += [dict(number=60, milestone="M18", depends=[11]),
                                           dict(number=61, milestone="M18", depends=[60]),
                                           dict(number=62, milestone=None, depends=[10, 61])]
        self.assertEqual(self.schedule.critical_path(self.snap["tracker"]["issues"]), {11: 3, 60: 2, 61: 1, 10: 1})
        got = self.ranked(builder=[item("build", 10, ts="2026-11-02T08:00:00Z"), item("build", 11, ts="2026-11-02T09:00:00Z")])
        self.assertEqual(got, [(7, "#11"), (7, "#10")])

    def test_critical_path_survives_a_cycle(self):
        issues = [dict(number=1, milestone=None, depends=[2]), dict(number=2, milestone=None, depends=[1])]
        self.assertEqual(self.schedule.critical_path(issues), {1: 1, 2: 1})

    def test_age_breaks_remaining_ties_oldest_first(self):
        got = self.ranked(reviewer=[item("review", 2, ts="2026-11-02T10:00:00Z"), item("review", 1, ts="2026-11-02T09:00:00Z"),
                                    item("review", 3, ts=None)])
        self.assertEqual(got, [(5, "#1"), (5, "#2"), (5, "#3")])

    def test_queued_spawns_rank_by_issue_and_pr(self):
        got = self.ranked(builder=[dict(kind="build", issue=20, pr=None, ts="2026-11-02T08:00:00Z", queued=True),
                                   dict(kind="fix", issue=30, pr=31, ts="2026-11-02T08:00:00Z", queued=True)])
        self.assertEqual(got, [(6, "#31"), (8, "#20")])

    def test_unknown_inputs_and_unranked_kinds(self):
        self.snap["tracker"] = "unknown"
        self.snap["workers"] = "unknown"
        self.snap["demand"] = {"builder": [item("build", 20), item("work", 5)], "reviewer": "unknown"}
        self.assertEqual([(r["class"], r["ref"]) for r in self.schedule.rank(self.snap)], [(7, "#20")])


if __name__ == "__main__":
    unittest.main()
