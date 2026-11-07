"""Tests for crew schedule snapshot (docs/scheduling.md#inputs): every input read from a fixture state dir into one
JSON object, `unknown` per failed read, memory pressure on macOS and Linux; the summary line, defer `since` times and
stuck finishing work (docs/scheduling.md#observability). Fake tmux and gh; run in CI.
"""
import datetime
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import CREW, Base, LivenessBase

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
if os.environ.get("FAKE_GH_FAIL"):
    sys.exit(1)
args = sys.argv[1:]
if args[0] == "api":
    print(json.dumps([{"number": 34, "title": "M18.2"}, {"number": 30, "title": "M21"}]))
elif args[:2] == ["issue", "list"] and "--label" in args:
    if os.environ.get("FAKE_GH_HOLDS_FAIL"):
        sys.exit(1)
    print(json.dumps([{"number": int(n)} for n in os.environ.get("FAKE_GH_HELD", "").split()]))
elif args[:2] == ["pr", "list"]:
    print(os.environ.get("FAKE_GH_PRS", "[]"))
elif args[:2] == ["issue", "list"]:
    print(json.dumps([
        {"number": 620, "milestone": {"title": "M18.2"}, "body": "## Depends on\\n\\n#598. Start after.\\n\\n## AC\\n#1"},
        {"number": 622, "milestone": None, "body": "Depends on #620, #621\\n"},
        {"number": 7, "milestone": None, "body": None},
        {"number": 15, "milestone": None, "body": "", "title": "main-red: default-branch CI red after land of #14"},
        {"number": 16, "milestone": None, "body": "", "title": "Fix the main-red notify text"}]))
"""


class Fixture(Base):
    """A state dir with demand in both pools, a reservation, errors, lands, a train and two runs."""
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


class Snapshot(Fixture):
    def test_every_input_from_fixture_state(self):
        snap = self.snapshot()
        builder = snap["demand"]["builder"]
        self.assertEqual([(d["kind"], d.get("queued", False)) for d in builder], [("merge-up", False), ("build", True)])
        reviewer = snap["demand"]["reviewer"]
        self.assertEqual([d["kind"] for d in reviewer], ["review", "work"])
        self.assertEqual(reviewer[1]["event"]["event"], "pr-merged")
        self.assertEqual({w["name"]: w["state"] for w in snap["workers"]}, {"ben-7": "idle", "vera-8": "exited"})
        self.assertEqual([w["name"] for w in snap["workers"] if w["finished"]], [])
        self.assertEqual(snap["reservations"][0]["ref"], "#9")
        self.assertEqual(snap["trains"], ["train-3.json"])
        self.assertEqual(sorted(land["refs"][0] for land in snap["lands"]), ["#12", "#13"])
        self.assertEqual(snap["errors"], 1)
        self.assertEqual(snap["caps"], {"builder": 5, "reviewer": 2})
        self.assertEqual(snap["memory_high"], "critical")
        self.assertIsInstance(snap["load"], float)
        self.assertIn(snap["memory"] if snap["memory"] == "unknown" else snap["memory"]["os"],
                      ("darwin", "linux", "unknown"))
        tracker = snap["tracker"]
        self.assertEqual([m["title"] for m in tracker["milestones"]], ["M18.2", "M21"])
        self.assertEqual(tracker["max_active"], 1)
        self.assertEqual({i["number"]: (i["milestone"], i["depends"]) for i in tracker["issues"]},
                         {620: ("M18.2", [598]), 622: (None, [620, 621]), 7: (None, []), 15: (None, []), 16: (None, [])})
        self.assertEqual(tracker["red_fixes"], [15])

    def test_holds_read_labels_and_prs_closing_held_issues(self):  # #712
        prs = json.dumps([{"number": 40, "labels": [{"name": "crew:hold"}], "closingIssuesReferences": []},
                          {"number": 41, "labels": [], "closingIssuesReferences": [{"number": 639}]},
                          {"number": 42, "labels": [], "closingIssuesReferences": [{"number": 7}]}])
        self.assertEqual(self.snapshot()["holds"], [])
        self.assertEqual(self.snapshot(FAKE_GH_HELD="639", FAKE_GH_PRS=prs)["holds"], [40, 41, 639])
        self.assertEqual(self.snapshot(FAKE_GH_HOLDS_FAIL="1")["holds"], "unknown")
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\nhold_label_blocks = false\n')
        self.assertEqual(self.snapshot(FAKE_GH_HELD="639", FAKE_GH_PRS=prs)["holds"], [40, 41, 639])  # #1124

    def test_reviewer_done_line_marks_its_worker_finished(self):  # #719; a builder's done: is not terminal
        self.put("status/vera-8.status", "done: #8 %s validate pass\n" % ("a" * 40))
        self.assertEqual([w["name"] for w in self.snapshot()["workers"] if w["finished"]], ["vera-8"])

    def test_reviewer_work_events_rank_as_the_pass_they_start(self):
        sha = "a" * 40
        events = [{"event": "new-head", "refs": ["#31", sha]}, {"reason": "status", "line": "done: #7 #32 " + sha},
                  {"reason": "status", "line": "done: #33 %s review pass" % sha},
                  {"reason": "status", "line": "done: #34 %s recheck escalate" % sha},
                  {"reason": "status", "line": "done: #35 %s review changes" % sha}]
        for i, e in enumerate(events):
            self.put("leads/reviewer-events/w%d.json" % i, json.dumps(e))
        self.put("inbox/vera-lead.jsonl", "".join(json.dumps(dict(id="w%d" % i, kind="work", refs=[
            os.path.join(self.state, "leads", "reviewer-events", "w%d.json" % i)])) + "\n" for i in range(len(events))))
        self.assertEqual([(d["kind"], d["refs"][0][-8:]) for d in self.snapshot()["demand"]["reviewer"]],
                         [("review", "#31"), ("review", "#32"), ("validate", "#33"), ("review", "#34"),
                          ("work", "/w4.json")])

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

    def test_open_main_red_issue_and_its_pr_rank_class_1_by_default(self):  # #1072
        self.snap["tracker"]["red_fixes"] = [15, 30]
        demand = dict(builder=[item("build", 15), item("fix", 31), item("build", 10)], reviewer=[item("review", 43)])
        self.assertEqual(self.ranked(**demand), [(1, "#15"), (1, "#31"), (5, "#43"), (7, "#10")])
        self.snap["tracker"]["red_fixes"] = []
        self.assertEqual(self.ranked(**demand), [(5, "#43"), (6, "#31"), (7, "#10"), (8, "#15")])

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

    def test_work_wake_beside_eligible_demand_is_skipped(self):
        wake = dict(id="w1", kind="work", refs=["/state/leads/reviewer-events/e1.json"],
                    event={"event": "pr-merged", "refs": ["#5"]})
        self.assertEqual(self.ranked(builder=[item("build", 10)], reviewer=[wake, item("review", 33)]),
                         [(5, "#33"), (7, "#10")])

    def test_spawned_fix_record_maps_pr_to_issue(self):
        self.snap["workers"] = [{"name": "ben-30", "role": "builder", "item": "issue #10, PR #31", "pr": 31}]
        got = self.schedule.rank(dict(self.snap, demand={"builder": [item("fix", 31)], "reviewer": [item("validate", 31)]}))
        self.assertEqual([(r["class"], r["ref"], r["issue"], r["milestone_order"]) for r in got],
                         [(4, "#31", 10, 0), (6, "#31", 10, 0)])

    def test_held_issue_or_pr_is_left_out_and_listed_as_held(self):  # #712
        self.snap["holds"] = [20, 31]
        demand = dict(builder=[item("build", 20, ts="2026-11-02T08:00:00Z"), item("build", 10), item("fix", 31)],
                      reviewer=[item("validate", 31), item("review", 33)])
        self.assertEqual(self.ranked(**demand), [(5, "#33"), (7, "#10")])
        self.assertEqual([(r["kind"], r["ref"]) for r in self.schedule.held(self.snap)],
                         [("build", "#20"), ("fix", "#31"), ("validate", "#31")])
        self.snap["holds"] = [30]  # the PR's issue, mapped through its worker record
        self.assertEqual(self.ranked(**demand), [(5, "#33"), (7, "#10"), (8, "#20")])
        self.snap["holds"] = "unknown"
        self.assertEqual(len(self.ranked(**demand)), 5)

    def test_unknown_inputs_and_unranked_kinds(self):
        self.snap["tracker"] = "unknown"
        self.snap["workers"] = "unknown"
        self.snap["demand"] = {"builder": [item("build", 20), item("work", 5)], "reviewer": "unknown"}
        self.assertEqual([(r["class"], r["ref"]) for r in self.schedule.rank(self.snap)], [(7, "#20")])


T0 = datetime.datetime(2026, 11, 3, 8, 0, tzinfo=datetime.timezone.utc)


class Target(unittest.TestCase):
    def setUp(self):
        self.schedule = Memory.load()
        self.opts = dict(self.schedule.TARGET_OPTIONS)
        self.snap = dict(workers=[{"state": "busy"}] * 3 + [{"state": "idle"}], caps={"builder": 4, "reviewer": 2},
                         load=5.0, memory={"os": "darwin", "level": "normal"}, memory_high="warn", errors=0, tracker="unknown",
                         demand={"builder": [item("build", 10)], "reviewer": []})
        self.doc = dict(target=3, changed=self.schedule.stamp(T0), starts=[])

    def step(self, minutes, doc=None, **snap):
        return self.schedule.target(dict(self.snap, **snap), self.opts, self.doc if doc is None else doc,
                                    T0 + datetime.timedelta(minutes=minutes))

    def test_first_run_starts_at_busy_count_within_caps(self):
        first = lambda **snap: self.schedule.target(dict(self.snap, **snap), self.opts, None, T0)["target"]
        self.assertEqual(first(), 3)
        self.assertEqual(first(workers=[]), 1)
        self.assertEqual(first(caps={"builder": 1, "reviewer": 1}), 2)

    def test_hold_between_watermarks(self):
        self.assertEqual(self.step(3), self.doc)
        self.assertEqual(self.step(3, load=2.0, errors=1)["target"], 3)
        self.assertEqual(self.step(3, load=2.0, memory={"os": "linux", "some_avg10": 5.0})["target"], 3)

    def test_grow_when_every_signal_low_and_demand_waits(self):
        grown = self.step(3, load=3.9)
        self.assertEqual((grown["target"], grown["changed"]), (4, "2026-11-03T08:03:00Z"))
        self.assertEqual(self.step(3, load=3.9, demand={"builder": [], "reviewer": []})["target"], 3)
        self.assertEqual(self.step(3, dict(self.doc, target=6), load=1.0)["target"], 6)

    def test_shrink_from_busy_on_any_high_signal(self):
        for snap in (dict(load=6.0), dict(memory={"os": "darwin", "level": "warn"}), dict(errors=3),
                     dict(memory={"os": "linux", "some_avg10": 10.0})):
            self.assertEqual(self.step(3, dict(self.doc, target=6), **snap)["target"], 2, snap)
        self.assertEqual(self.step(3, dict(self.doc, target=1), load=9.0)["target"], 1)

    def test_memory_threshold_by_speed_and_override(self):  # #1282
        values = {"runtime.options.builders": 4, "runtime.options.reviewers": 2}
        high = lambda caps, **opts: self.schedule.memory_high(dict(values, **opts), caps)
        full, light = {"builder": 4, "reviewer": 2}, {"builder": 3, "reviewer": 2}
        self.assertEqual((high(full), high(light), high({"builder": "unknown", "reviewer": 2})),
                         ("critical", "warn", "unknown"))
        self.assertEqual(high({"builder": 10, "reviewer": 2}, **{"runtime.options.builders": 12}), "critical")  # band
        self.assertEqual(high(full, **{"runtime.options.memory_high": "warn"}), "warn")
        self.assertEqual(high(light, **{"runtime.options.memory_high": "critical"}), "critical")

    def test_full_speed_throttles_on_memory_only_at_critical(self):  # #1282
        warn, critical = {"os": "darwin", "level": "warn"}, {"os": "darwin", "level": "critical"}
        big = dict(self.doc, target=6)
        self.assertEqual(self.step(3, load=3.9, memory=warn, memory_high="critical")["target"], 4)
        self.assertEqual(self.step(3, big, memory=critical, memory_high="critical")["target"], 2)
        self.assertEqual(self.step(3, big, memory=warn, memory_high="warn")["target"], 2)
        linux = lambda avg: {"os": "linux", "some_avg10": avg}
        self.assertEqual(self.step(3, big, memory=linux(10.0), memory_high="critical")["target"], 6)
        self.assertEqual(self.step(3, big, memory=linux(40.0), memory_high="critical")["target"], 2)
        self.assertEqual(self.step(3, memory=warn, memory_high="unknown")["target"], 3)

    def test_at_most_one_change_per_interval(self):
        doc = self.step(3, load=1.0)
        for minutes in (3.5, 4, 4.9):
            self.assertEqual(self.step(minutes, doc, load=9.0)["target"], 4)
        self.assertEqual(self.step(5, doc, load=9.0)["target"], 2)

    def test_no_flapping_when_load_hovers(self):
        doc = self.doc
        for i, load in enumerate([4.0, 5.9, 4.5, 5.99, 4.0, 5.0] * 3):
            doc = self.step(3 * (i + 1), doc, load=load)
        self.assertEqual(doc, self.doc)

    def test_unknown_inputs_hold_and_lower_caps_clamp_at_once(self):
        for snap in (dict(load="unknown"), dict(memory="unknown"), dict(errors="unknown"), dict(workers="unknown"),
                     dict(load=9.0, caps={"builder": "unknown", "reviewer": 2})):
            self.assertEqual(self.step(3, **snap)["target"], 3, snap)
        self.assertEqual(self.step(1, caps={"builder": 1, "reviewer": 1})["target"], 2)
        self.assertEqual(self.step(1, caps={"builder": 0, "reviewer": 0})["target"], 1)
        zero = dict(caps={"builder": 0, "reviewer": 0}, load=1.0)
        self.assertEqual(self.step(3, dict(self.doc, target=1), **zero)["target"], 1)
        self.assertEqual(self.step(3, **zero)["target"], 1)

    def test_ramp_limit_counts_starts_in_the_interval(self):
        doc = self.step(3, dict(self.doc, starts=["2026-11-03T08:00:30Z", "2026-11-03T08:02:00Z"]))
        self.assertEqual((doc["starts"], self.schedule.ramp_left(doc, self.opts)), (["2026-11-03T08:02:00Z"], 1))
        self.assertEqual(self.schedule.ramp_left(dict(doc, starts=doc["starts"] * 3), self.opts), 0)

    def test_update_target_writes_target_json(self):
        with tempfile.TemporaryDirectory() as state:
            values = {"runtime.options.schedule_interval": 60}
            first = self.schedule.update_target(state, self.snap, values, T0)
            path = os.path.join(state, "schedule", "target.json")

            def saved():
                with open(path) as f:
                    return json.load(f)
            self.assertEqual(saved(), first)
            later = self.schedule.update_target(state, dict(self.snap, load=1.0), values, T0 + datetime.timedelta(minutes=1))
            self.assertEqual((first["target"], later["target"], saved()), (3, 4, later))


def walked(actions):
    return [(a["action"], a["ref"], a["reasons"]) for a in actions]


class Decide(unittest.TestCase):
    """The walk of docs/scheduling.md#model: caller-only reservations, cross-pool holds, floors, lead down."""
    def setUp(self):
        self.schedule = Memory.load()
        self.opts = dict(self.schedule.TARGET_OPTIONS)
        self.snap = dict(workers=[], caps={"builder": 1, "reviewer": 1})
        self.ranked = [dict(pool="reviewer", ref="#5", kind="review", **{"class": 5}),
                       dict(pool="builder", ref="#7", kind="build", **{"class": 7})]
        self.alive = {"builder": "alive", "reviewer": "alive"}

    def walk(self, pool, reserved=(), target=2, starts=(), leads=None, ceiling=None, ranked=None, **snap):
        return walked(self.schedule.walk(pool, self.ranked if ranked is None else ranked, dict(self.snap, **snap),
                                         [dict(ref=r, pool=p, time="t") for p, r in reserved],
                                         dict(target=target, starts=list(starts)), self.opts,
                                         self.alive if leads is None else leads, ceiling))

    def test_builder_calls_first(self):
        self.assertEqual(self.walk("builder"), [("hold", "#5", []), ("admit", "#7", [])])
        self.assertEqual(self.walk("reviewer", reserved=[("builder", "#7")]), [("admit", "#5", [])])

    def test_reviewer_calls_first(self):
        self.assertEqual(self.walk("reviewer"), [("admit", "#5", []), ("hold", "#7", [])])
        self.assertEqual(self.walk("builder", reserved=[("reviewer", "#5")]), [("admit", "#7", [])])

    def test_repeated_calls_by_one_lead_never_reserve_the_other_pool(self):
        first = self.walk("builder")
        again = self.walk("builder", reserved=[("builder", "#7")])
        self.assertEqual((first, again), ([("hold", "#5", []), ("admit", "#7", [])],
                                          [("hold", "#5", []), ("admit", "#7", ["reserved"])]))

    def test_red_fix_takes_the_budget_before_a_review(self):  # #1072: decide's default rank sees main-red issues
        snap = dict(demand={"builder": [item("build", 15)], "reviewer": [item("review", 43)]}, workers=[],
                    tracker=dict(milestones=[], max_active=1, issues=[], red_fixes=[15]))
        ranked = self.schedule.rank(snap)
        self.assertEqual([(r["class"], r["ref"]) for r in ranked], [(1, "#15"), (5, "#43")])
        self.assertEqual(self.walk("builder", target=1, ranked=ranked), [("admit", "#15", []), ("hold", "#43", ["floor"])])

    def test_floors_with_target_one(self):
        self.assertEqual(self.walk("builder", target=1), [("hold", "#5", []), ("admit", "#7", ["floor"])])
        self.assertEqual(self.walk("reviewer", reserved=[("builder", "#7")], target=1), [("admit", "#5", ["floor"])])

    def test_floor_waives_target_ramp_and_ceiling_for_the_top_item_only(self):
        builds = [dict(pool="builder", ref="#%d" % n, kind="build", **{"class": 7}) for n in (7, 8)]
        caps = {"builder": 3, "reviewer": 1}
        reviewing = [{"role": "reviewer", "state": "busy"}]
        for kw, why in ((dict(target=1), "target"), (dict(target=5, starts=["a", "b"]), "ramp"),
                        (dict(target=5, ceiling="max_suites"), "max_suites")):
            self.assertEqual(self.walk("builder", ranked=builds, caps=caps, workers=reviewing, **kw),
                             [("admit", "#7", ["floor"]), ("defer", "#8", [why])], kw)
        busy = [{"role": "builder", "state": "busy"}, {"role": "builder", "state": "idle"}]
        self.assertEqual(self.walk("builder", ranked=builds, caps=caps, target=1, workers=busy),
                         [("defer", "#7", ["target"]), ("defer", "#8", ["target"])])
        self.assertEqual(self.walk("builder", ranked=builds, caps={"builder": 0, "reviewer": 1}),
                         [("defer", "#7", ["cap"]), ("defer", "#8", ["cap"])])

    def test_reviewer_floor_under_builder_load(self):
        busy = [{"role": "builder", "state": "busy"}] * 3
        self.assertEqual(self.walk("reviewer", target=3, caps={"builder": 3, "reviewer": 1}, workers=busy),
                         [("admit", "#5", ["floor"])])

    def test_other_lead_down_drops_its_hold(self):
        builds = self.ranked[:1] + [dict(pool="builder", ref="#%d" % n, kind="build", **{"class": 7}) for n in (7, 8)]
        caps = {"builder": 2, "reviewer": 1}
        self.assertEqual(self.walk("builder", ranked=builds, caps=caps),
                         [("hold", "#5", []), ("admit", "#7", []), ("defer", "#8", ["target"])])
        for down in ("dead", "missing", "ambiguous", "unknown"):
            self.assertEqual(self.walk("builder", ranked=builds, caps=caps, leads=dict(self.alive, reviewer=down)),
                             [("drop", "#5", ["lead-down"]), ("admit", "#7", []), ("admit", "#8", [])], down)

    def test_demand_a_busy_worker_runs_takes_no_budget(self):  # #988: a running merge-up starved the builder ramp
        ranked = [dict(pool="builder", ref="#972", kind="merge-up", **{"class": 3}),
                  dict(pool="builder", ref="#928", kind="build", **{"class": 7})]
        worker = dict(role="builder", item="issue #936, PR #972", pr=None, state="busy")
        run = lambda w: self.walk("builder", ranked=ranked, caps={"builder": 6, "reviewer": 1}, target=6, starts=["a"],
                                  workers=[w])
        self.assertEqual(self.opts["schedule_ramp"], 2)
        self.assertEqual(run(worker), [("admit", "#928", [])])
        self.assertEqual(run(dict(worker, item="issue #936", pr=972)), [("admit", "#928", [])])
        for other in (dict(worker, state="idle"), dict(worker, role="reviewer")):
            self.assertEqual(run(other)[:1], [("admit", "#972", [])], other)
        review = [dict(pool="reviewer", ref="#972", kind="validate", **{"class": 4})]
        self.assertEqual(self.walk("reviewer", ranked=review, caps={"builder": 1, "reviewer": 2}, target=6,
                                   workers=[dict(worker, role="reviewer", item="PR #972 r3 review", pr=972)]),
                         [("admit", "#972", [])])

    def test_reservation_expiry_and_run_record(self):
        live = lambda workers, minutes=1: [r["ref"] for r in self.schedule.live_reservations(
            [dict(ref="#9", pool="builder", time="2026-11-03T08:00:00Z")], workers, T0 + datetime.timedelta(minutes=minutes))]
        old = dict(role="builder", item="issue #9", pr=None, state="idle", start="2026-11-03T07:00:00Z")
        self.assertEqual(live([]), ["#9"])
        self.assertEqual(live([], minutes=10), [])
        self.assertEqual(live([old]), ["#9"])
        self.assertEqual(live([dict(old, role="reviewer", state="busy")]), ["#9"])
        self.assertEqual(live([dict(old, state="busy")]), [])
        self.assertEqual(live([dict(old, start="2026-11-03T08:00:30Z")]), [])
        self.assertEqual(live([dict(old, item="issue #3, PR #9", state="busy")]), [])

    def test_ceilings(self):
        snap = dict(suites=4, load=0.5, cpus=8)
        hit = lambda values, **kw: self.schedule.ceiling_hit(dict(snap, **kw), values)
        self.assertIsNone(hit({}))
        self.assertEqual(hit({"runtime.options.max_suites": 4}), "max_suites")
        self.assertIsNone(hit({"runtime.options.max_suites": 5}))
        self.assertEqual(hit({"runtime.options.max_load": 4}), "max_load")
        self.assertEqual(hit({"runtime.options.max_load": 9}, load="unknown"), "max_load")
        self.assertIsNone(hit({"runtime.options.max_load": 9}))


class Summary(unittest.TestCase):
    def setUp(self):
        self.schedule = Memory.load()
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        os.makedirs(os.path.join(self.state, "schedule"))

    def write(self, name, *lines):
        with open(os.path.join(self.state, "schedule", name), "w") as f:
            f.writelines(json.dumps(line) + "\n" for line in lines)

    def test_unknown_inputs_orphans_and_newest_decision(self):
        snap = dict(ts="2026-11-03T10:00:00Z", workers="unknown", reservations=[], memory={"os": "linux", "some_avg10": 2.5},
                    load="unknown", errors=0, orphans=[{"window": "ben-7", "pid": 42}],
                    demand={"builder": "unknown", "reviewer": [{"kind": "validate", "refs": ["#8"]}, {"kind": "work"}]})
        self.write("decisions-20261102.jsonl", dict(action="snapshot", snapshot={}, target=9, caps={}))
        self.write("decisions-20261103.jsonl", dict(action="snapshot", snapshot=snap, target=3,
                                                    caps={"builder": 2, "reviewer": "unknown"}), dict(action="admit"))
        with open(os.path.join(self.state, "schedule", "deferred.json"), "w") as f:
            json.dump({"builder": {"#5": {"kind": "build", "class": 7, "reasons": ["overlap #4 a.py"], "since": "x"},
                                   "#6": ["target"]},
                       "reviewer": {"#8": {"kind": "review", "class": 5, "reasons": ["cap"], "since": "x"}}}, f)
        self.assertEqual(self.schedule.summary(self.state),
                         "schedule: builders unknown/2 reviewers unknown/unknown target 3 (load unknown mem psi 2.5 "
                         "errors 0) queued validate 1 builder unknown; deferred 2 (overlap 1, cap 1); held 0; orphans 1 ben-7 pid 42; "
                         "terminal unknown")

    def test_finished_reviewer_holding_a_slot_is_terminal(self):  # #719
        workers = [dict(name="vera-711-r3-validate", role="reviewer", state="busy", finished=True),
                   dict(name="ben-7", role="builder", state="busy", finished=False)]
        snap = dict(ts="2026-11-03T10:00:00Z", workers=workers, reservations=[], memory={"os": "darwin", "level": "normal"},
                    load=0.5, errors=0, orphans=[], demand={"builder": [], "reviewer": []})
        self.write("decisions-20261103.jsonl", dict(action="snapshot", snapshot=snap, target=3,
                                                    caps={"builder": 3, "reviewer": 3}))
        self.assertEqual(self.schedule.summary(self.state),
                         "schedule: builders 1/3 reviewers 1/3 target 3 (load 0.5/cpu mem normal errors 0) queued none; "
                         "deferred 0; held 0; orphans 0; terminal 1 vera-711-r3-validate")

    def test_memory_threshold_in_the_summary(self):  # #1282
        snap = dict(ts="2026-11-03T10:00:00Z", workers=[], reservations=[], load=0.5, errors=0, orphans=[],
                    demand={"builder": [], "reviewer": []})
        for memory, high, shown in (({"os": "darwin", "level": "warn"}, "critical", "warn (high at critical)"),
                                    ({"os": "linux", "some_avg10": 2.5}, "critical", "psi 2.5 (high at psi 40.0)"),
                                    ("unknown", "warn", "unknown (high at warn)")):
            self.write("decisions-20261103.jsonl", dict(action="snapshot", target=3, caps={"builder": 3, "reviewer": 3},
                                                        snapshot=dict(snap, memory=memory, memory_high=high)))
            self.assertIn("(load 0.5/cpu mem %s errors 0)" % shown, self.schedule.summary(self.state))

    def test_stuck_is_finishing_work_past_the_threshold(self):
        since = lambda s: "2026-11-03T10:%02d:00Z" % s
        with open(os.path.join(self.state, "schedule", "deferred.json"), "w") as f:
            json.dump({"builder": {"#1": {"kind": "fix", "class": 6, "reasons": ["target"], "since": since(0)},
                                   "#2": {"kind": "build", "class": 7, "reasons": ["target"], "since": since(0)}},
                       "reviewer": {"#3": {"kind": "review", "class": 5, "reasons": ["cap"], "since": since(20)}}}, f)
        now = datetime.datetime(2026, 11, 3, 10, 30, tzinfo=datetime.timezone.utc).timestamp()
        self.assertEqual([d["ref"] for d in self.schedule.stuck(self.state, now, 1800)], ["#1"])
        self.assertEqual([d["ref"] for d in self.schedule.stuck(self.state, now, 600)], ["#1", "#3"])


class Orphans(LivenessBase):
    def snapshot(self):
        r = self.crew("schedule", "snapshot", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_live_tool_session_without_a_run_record_is_an_orphan(self):  # #706 r1
        self.set_pane(10, command="node")
        with open(self.ps, "w") as f:
            json.dump({"children": [[42, 9000010, "S", "codex.real"], [43, 42, "Ss", "python3"]]}, f)
        os.remove(os.path.join(self.state, "runs", "ben-7.json"))
        self.assertEqual(self.snapshot()["orphans"], [{"window": "ben-7", "pid": "9000010"}])
        with open(self.ps, "w") as f:
            json.dump({"children": [[42, 9000010, "S", "codex.real"]]}, f)  # the harness alone is no tool session
        self.assertEqual(self.snapshot()["orphans"], [])


class DecideCommand(Fixture):
    def call(self, *argv):
        r = self.crew("schedule", *argv, "--project", self.project)
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        return json.loads(r.stdout)

    def saved(self, name):
        with open(os.path.join(self.state, "schedule", name)) as f:
            return json.load(f) if name.endswith(".json") else [json.loads(line) for line in f]

    def test_decide_reserves_logs_and_release_frees(self):
        brief = lambda out: [(a["ref"], a["reasons"]) for a in out["admit"] + out["deferred"]]
        self.assertEqual(brief(self.call("decide", "--pool", "builder")), [("#9", ["reserved"]), ("#601", ["target"])])
        self.assertEqual(self.call("release", "--pool", "builder", "#9")["released"], ["#9"])
        self.assertEqual(self.saved("reservations.json"), [])
        out = self.call("decide", "--pool", "builder")
        self.assertEqual((out["target"], brief(out)), (1, [("#601", []), ("#9", ["target"])]))
        self.assertEqual([(r["ref"], r["pool"]) for r in self.saved("reservations.json")], [("#601", "builder")])
        self.assertEqual(len(self.saved("target.json")["starts"]), 1)
        self.call("decide", "--pool", "builder")
        day = [n for n in os.listdir(os.path.join(self.state, "schedule")) if n.startswith("decisions-")]
        lines = [(x["action"], x.get("ref"), x.get("reasons")) for x in self.saved(day[0]) if x["action"] != "drop"]
        self.assertEqual(lines, [("snapshot", None, None), ("defer", "#601", ["target"]), ("admit", "#9", ["reserved"]),
                                 ("snapshot", None, None), ("admit", "#601", []), ("defer", "#9", ["target"]),
                                 ("snapshot", None, None), ("admit", "#601", ["reserved"])])
        self.assertIn("demand", self.saved(day[0])[0]["snapshot"])

    def test_unreadable_demand_defers_only_that_pool(self):
        os.remove(self.event)
        self.assertEqual(self.call("decide", "--pool", "reviewer")["deferred"][0]["reasons"], ["demand-unreadable"])
        self.assertEqual(self.call("decide", "--pool", "builder")["admit"][0]["ref"], "#9")

    def test_reservations_count_as_busy_for_the_first_target(self):
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.put("schedule/reservations.json", json.dumps([dict(ref=r, pool="builder", time=now) for r in ("#9", "#77")]))
        self.assertEqual(self.call("decide", "--pool", "builder")["target"], 2)

    def test_summary_line_and_defer_since(self):  # #628
        self.assertEqual(self.crew("schedule", "summary", "--project", self.project).stdout, "schedule: no decision yet\n")
        self.call("decide", "--pool", "builder")
        since = self.saved("deferred.json")["builder"]["#601"]
        self.assertEqual((since["kind"], since["class"], since["reasons"]), ("merge-up", 3, ["target"]))
        self.call("decide", "--pool", "builder")
        self.assertEqual(self.saved("deferred.json")["builder"]["#601"]["since"], since["since"])
        r = self.crew("schedule", "summary", "--project", self.project)
        self.assertRegex(r.stdout, r"^schedule: builders 1/5 reviewers 0/2 target 1 \(load [\d.]+/cpu mem .+ errors 1\) "
                                   r"queued merge-up 1 review 1 build 1; deferred 1 \(target 1\); held 0; orphans 0; "
                                   r"terminal 0\n$")

    def test_target_one_skips_an_older_held_handoff(self):  # #712: the #639 / #710 stall
        stamp = lambda minutes: (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes)
                                 ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.put("inbox/ben-lead.jsonl", "".join(json.dumps(m) + "\n" for m in [
            {"id": "h1", "kind": "build", "refs": ["#639"], "ts": stamp(600)},
            {"id": "c1", "kind": "build", "refs": ["#710"], "ts": stamp(5)}]))
        self.put("status/ben-lead.status", "")
        os.remove(os.path.join(self.state, "spawn-queue.jsonl"))
        self.put("schedule/reservations.json", "[]")
        self.put("schedule/target.json", json.dumps(dict(target=1, changed=stamp(0), starts=[])))
        decide = lambda **env: json.loads(self.crew("schedule", "decide", "--pool", "builder", "--project", self.project,
                                                    **env).stdout)
        out = decide(FAKE_GH_HELD="639")
        self.assertEqual((out["target"], [a["ref"] for a in out["admit"]], out["deferred"]), (1, ["#710"], []))
        self.assertEqual(out["held"], [dict(pool="builder", ref="#639", kind="build")])
        self.assertRegex(self.crew("schedule", "summary", "--project", self.project).stdout,
                         r"queued review 1 build 1; deferred 0; held 1 #639; ")
        self.call("release", "--pool", "builder", "#710")
        out = decide()  # hold lifted: the same pending handoff ranks again, no new handoff
        self.assertEqual(([a["ref"] for a in out["admit"]], out["held"]), (["#639"], []))
        self.call("release", "--pool", "builder", "#639")
        out = decide(FAKE_GH_HELD="639", FAKE_GH_HOLDS_FAIL="1")  # an unreadable hold read grants nothing (r1)
        self.assertEqual((out["admit"], [d["reasons"] for d in out["deferred"]], out["held"]),
                         ([], [["holds-unreadable"]], []))
        self.assertRegex(self.crew("schedule", "summary", "--project", self.project).stdout, r"; held unknown; ")

    def test_decide_and_release_require_a_pool(self):
        r = self.crew("schedule", "decide", "--project", self.project)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (2, "crew: schedule decide requires --pool\n", ""))


if __name__ == "__main__":
    unittest.main()
