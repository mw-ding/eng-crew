#!/usr/bin/env python3
"""Offline self-test for scripts/triage-clusters.py (no network).

Checks key-based grouping (failure class, Source, Depends on, path prefix; one cluster per issue), a slug that stays
stable across sweeps while members join, a member the model adds with its reason (and one without a reason refused),
and the noise cap counting a cluster proposal once whatever its size (#1298). Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
spec = importlib.util.spec_from_file_location("triage_clusters", os.path.join(SCRIPTS, "triage-clusters.py"))
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)


def issue(n, body="", labels=(), milestone=None, state="OPEN", comments=(), url="issues"):
    return {"number": n, "url": "https://github.com/acme/widgets/%s/%d" % (url, n), "state": state,
            "title": "issue %d" % n, "body": body, "labels": [{"name": x} for x in labels],
            "milestone": {"number": 7, "title": milestone} if milestone else None, "comments": list(comments)}


def backlog():
    return [
        issue(1, "**Failure class:** scheduler-stall in the watcher\n**Source:** acme/widgets#90", labels=["P1"]),
        issue(2, "Failure class: scheduler-stall\nSee core/sched/run.py"),
        issue(3, "Source: https://github.com/acme/widgets/issues/91"),
        issue(4, "**Source:** acme/widgets#91"),
        issue(5, "Depends on #6 and #9"),
        issue(6, "the target"),
        issue(7, "touches core/sched/loop.py"),
        issue(8, "body", comments=[{"body": "[Riley/card-extracted] #8\n**Failure class:** unknown\n"
                                            "**Source:** https://github.com/acme/widgets/issues/8"}]),
        issue(10, "Failure class: scheduler-stall", state="CLOSED"),
        issue(11, "Failure class: scheduler-stall", url="pull"),
        issue(12, "Failure class: scheduler-stall", labels=["triage:log"]),
    ]


def by_slug(result):
    return {c["slug"]: c for c in result["clusters"]}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = tc.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Grouping(unittest.TestCase):
    def test_keys_place_each_open_issue_once(self):
        got = by_slug(tc.build(backlog(), {}, {}, 10))
        self.assertEqual(sorted(got), ["class-scheduler-stall", "depends-acme-widgets-6", "source-acme-widgets-91"])
        stall = got["class-scheduler-stall"]
        self.assertEqual([m["ref"] for m in stall["members"]], ["acme/widgets#1", "acme/widgets#2"])
        self.assertEqual(stall["members"][0]["keys"], ["class:scheduler-stall"])  # cites the keys that placed it
        self.assertEqual([m["ref"] for m in got["depends-acme-widgets-6"]["members"]],
                         ["acme/widgets#5", "acme/widgets#6"])  # the open target joins its dependants
        # #2 and #7 share component:core/sched, but #2 is already placed by its class: no second cluster
        self.assertNotIn("component-core-sched", got)
        self.assertEqual(stall["band"], "P1")
        self.assertEqual(stall["milestone"], "backlog")
        self.assertEqual(stall["summary"], "2 open issues sharing class:scheduler-stall")

    def test_component_cluster_and_card_extracted_unknown_skipped(self):
        items = [issue(1, "edit core/sched/run.py"), issue(2, "and core/sched/loop.py"), issue(8, comments=[
            {"body": "[Riley/card-extracted] #8\n**Failure class:** unknown\n"
                     "**Source:** https://github.com/acme/widgets/issues/8"}])]
        got = by_slug(tc.build(items, {}, {}, 10))
        self.assertEqual(list(got), ["component-core-sched"])
        self.assertEqual(tc.keys(items[2]), set())  # unknown class and a self-Source give no key
        self.assertEqual(tc.keys(issue(9, comments=[{"body": "[Riley/card-extracted] #9\n**Failure class:** "
                                                             "Liveness gap"}])), {"class:liveness"})


class Stability(unittest.TestCase):
    def test_slug_stable_and_new_members_listed(self):
        first = tc.build(backlog(), {}, {}, 10)
        items = backlog() + [issue(13, "Failure class: scheduler-stall")]
        second = by_slug(tc.build(items, first, {}, 10))
        self.assertIn("class-scheduler-stall", second)
        self.assertEqual(second["class-scheduler-stall"]["new"], ["acme/widgets#13"])
        self.assertEqual(second["source-acme-widgets-91"]["new"], [])
        self.assertEqual(tc.build(items, first, {}, 10), tc.build(items, first, {}, 10))  # reproducible

    def test_prior_slug_kept_when_a_rival_grows(self):
        first = tc.build([issue(1, "a/x/1.py"), issue(2, "a/x/2.py b/y/2.py"), issue(3, "b/y/3.py")], {}, {}, 10)
        self.assertEqual(sorted(by_slug(first)), ["component-a-x"])
        grown = [issue(1, "a/x/1.py"), issue(2, "a/x/2.py b/y/2.py")] + [issue(n, "b/y/%d.py" % n) for n in (3, 4, 5)]
        self.assertEqual(sorted(by_slug(tc.build(grown, {}, {}, 10))), ["component-b-y"])  # without a prior
        got = by_slug(tc.build(grown, first, {}, 10))
        self.assertEqual(sorted(got), ["component-a-x", "component-b-y"])  # the recorded slug keeps #2
        self.assertEqual([m["ref"] for m in got["component-a-x"]["members"]], ["acme/widgets#1", "acme/widgets#2"])


class Model(unittest.TestCase):
    def test_model_member_with_reason_carries_over(self):
        model = {"members": [{"cluster": "class-scheduler-stall", "ref": "acme/widgets#7",
                              "reason": "same watcher stall,\n reworded"}],
                 "clusters": {"class-scheduler-stall": {"band": "P1", "milestone": "M37", "summary": "Watcher stalls"}}}
        first = tc.build(backlog(), {}, model, 10)
        stall = by_slug(first)["class-scheduler-stall"]
        self.assertIn({"ref": "acme/widgets#7", "by": "model", "reason": "same watcher stall, reworded"},
                      stall["members"])
        self.assertEqual((stall["size"], stall["summary"], stall["milestone"]), (3, "Watcher stalls", "M37"))
        again = by_slug(tc.build(backlog(), first, {}, 10))["class-scheduler-stall"]  # no model input this sweep
        self.assertIn("acme/widgets#7", [m["ref"] for m in again["members"]])
        self.assertEqual((again["new"], again["summary"]), ([], "Watcher stalls"))

    def test_model_member_without_reason_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            items, model = os.path.join(tmp, "items.json"), os.path.join(tmp, "model.json")
            with open(items, "w") as f:
                json.dump(backlog(), f)
            with open(model, "w") as f:
                json.dump({"members": [{"cluster": "class-scheduler-stall", "ref": "acme/widgets#7"}]}, f)
            code, out, err = run("--items", items, "--sweep", "20261108T1800Z", "--model", model)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("needs a one-line reason", err)

    def test_model_member_already_placed_is_skipped(self):
        model = {"members": [{"cluster": "class-scheduler-stall", "ref": "acme/widgets#3", "reason": "x"}]}
        got = tc.build(backlog(), {}, model, 10)
        self.assertEqual(by_slug(got)["class-scheduler-stall"]["size"], 2)
        self.assertEqual(got["notes"], ["model member acme/widgets#3 skipped: already in a cluster"])


class Cap(unittest.TestCase):
    def items(self):
        return [issue(n, "Failure class: %s" % cls, labels=[band])
                for n, cls, band in [(1, "big", "P2"), (2, "big", "P2"), (3, "big", "P2"), (4, "big", "P2"),
                                     (5, "pair", "P1"), (6, "pair", "P1"), (7, "quiet", "P3"), (8, "quiet", "P3")]]

    def test_cluster_proposal_counts_once(self):
        model = {"clusters": {"class-big": {"tracking": True}, "class-pair": {"milestone": "M37"},
                              "class-quiet": {"tracking": True}}}
        got = tc.build(self.items(), {}, model, 2)
        self.assertEqual(got["proposed"], ["class-pair", "class-big"])  # band first; four members cost one
        self.assertEqual(got["skipped_cap"], ["class-quiet"])
        self.assertEqual(by_slug(got)["class-quiet"]["proposals"], [])
        again = tc.build(self.items(), got, {}, 1)  # open proposals cost nothing; the capped one fits now
        self.assertEqual((again["proposed"], again["skipped_cap"]), (["class-quiet"], []))

    def test_no_proposal_when_members_already_in_milestone(self):
        items = [issue(1, "Failure class: big", milestone="M37"), issue(2, "Failure class: big", milestone="M37")]
        got = tc.build(items, {}, {}, 10)
        self.assertEqual((got["proposed"], by_slug(got)["class-big"]["milestone"]), ([], "M37"))


class Cli(unittest.TestCase):
    def test_render_and_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            items, out_path = os.path.join(tmp, "items.json"), os.path.join(tmp, "clusters.json")
            with open(items, "w") as f:
                json.dump(backlog(), f)
            code, out, err = run("--items", items, "--sweep", "20261108T1800Z", "--out", out_path)
            with open(out_path) as f:
                saved = json.load(f)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines()[0], "clusters: 3 (proposed 0, skipped: cap 0)")
        self.assertIn("- cluster:class-scheduler-stall size=2 band=P1 milestone=backlog new=2 "
                      "(acme/widgets#1, acme/widgets#2) proposal=- (none) key=class:scheduler-stall", out)
        self.assertIn("  - acme/widgets#1: class:scheduler-stall", out)
        self.assertEqual(saved["sweep"], "20261108T1800Z")

    def test_unreadable_input(self):
        code, out, err = run("--items", "/nonexistent.json", "--sweep", "x")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("unreadable input", err)


if __name__ == "__main__":
    unittest.main()
