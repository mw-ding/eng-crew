#!/usr/bin/env python3
"""Offline self-test for scripts/triage-metrics.py (no network).

Builds a calibration sweep over twelve fixture issues and checks the deterministic 10-sample spot check, the
8-of-10 bar (met, not met, pending; an answer to a revised proposal never counts for the original), each report metric,
owner feedback on applied records and the rolling apply-mode bar (#835), cluster counts (#1298), and the eval set
freeze and re-score. Run in CI.
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
spec = importlib.util.spec_from_file_location("triage_metrics", os.path.join(SCRIPTS, "triage-metrics.py"))
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

SWEEP = "20261104T0600Z"


def rec(issue, decision="classify", priority="P2", sweep=SWEEP, at="2026-11-04T06:10:00Z", mode="shadow"):
    return {"createdAt": at, "author": {"login": "riley"},
            "body": "[Riley/triage] #%d\n<!-- crew:v1 role=researcher pass=triage issue=%d decision=%s priority=%s "
                    "mode=%s sweep=%s -->" % (issue, issue, decision, priority, mode, sweep)}


def issue(n, comments=(), state="OPEN", reason=None, labels=(), created="2026-11-04T04:10:00Z"):
    return {"number": n, "url": "https://github.com/acme/widgets/issues/%d" % n, "state": state,
            "stateReason": reason, "labels": [{"name": x} for x in labels], "createdAt": created,
            "comments": list(comments)}


def backlog(accepted, rejected):
    """Twelve issues, each with a calibration record; the first `accepted` / next `rejected` answered."""
    items = [issue(n, [rec(n)]) for n in range(1, 13)]
    sampled = tm.sample(items, SWEEP, 10)
    for k, r in enumerate(sampled):
        item = next(i for i in items if tm.ref(i) == r)
        if k < accepted + rejected:
            item["comments"].append(rec(item["number"], "owner-accepted" if k < accepted else "owner-rejected",
                                        sweep="20261104T1200Z", at="2026-11-04T12:10:00Z"))
    return items


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = tm.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class Calibration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, data):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    def test_sample_is_ten_and_deterministic(self):
        items = backlog(0, 0)
        first = tm.sample(items, SWEEP, 10)
        self.assertEqual(len(first), 10)
        self.assertEqual(first, tm.sample(list(reversed(items)), SWEEP, 10))
        self.assertTrue(all(r.startswith("acme/widgets#") for r in first))
        items.append(issue(99, [rec(99, sweep="20261105T0000Z")]))  # a later sweep's record never joins the sample
        self.assertEqual(first, tm.sample(items, SWEEP, 10))
        code, out, _ = run("sample", "--items", self.write("i.json", items), "--sweep", SWEEP)
        self.assertEqual((code, out.split()), (0, first))

    def test_bar(self):
        for acc, rej, code, state in ((8, 2, 0, "met"), (7, 3, 1, "not met"), (6, 1, 1, "pending")):
            c, out, _ = run("bar", "--items", self.write("i.json", backlog(acc, rej)), "--sweep", SWEEP)
            self.assertEqual(c, code)
            self.assertIn("bar: %d/10 accepted as is, %d rejected, %d pending (need 8): %s"
                          % (acc, rej, 10 - acc - rej, state), out)

    def test_answer_to_a_revised_proposal_never_counts(self):  # #774 round 1
        items = backlog(7, 3)
        item = next(i for i in items if tm.answer(i, SWEEP) == "owner-rejected")
        item["comments"] += [rec(item["number"], priority="P1", sweep="20261105T0600Z", at="2026-11-05T06:10:00Z"),
                             rec(item["number"], "owner-accepted", priority="P1", sweep="20261105T1200Z",
                                 at="2026-11-05T12:10:00Z")]
        self.assertEqual(tm.answer(item, SWEEP), "owner-rejected")
        self.assertEqual(tm.answer(item, "20261105T0600Z"), "owner-accepted")
        code, out, _ = run("bar", "--items", self.write("i.json", items), "--sweep", SWEEP)
        self.assertEqual(code, 1)
        self.assertIn("bar: 7/10 accepted as is, 3 rejected, 0 pending (need 8): not met", out)
        self.assertNotIn(tm.ref(item), tm.proposals(items, SWEEP))
        self.assertEqual(len(tm.proposals(items, SWEEP)), 7)

    def test_report(self):
        items = [
            issue(1, [rec(1, priority="P1")], "CLOSED", "COMPLETED", ["P1"]),  # match
            issue(2, [rec(2, "duplicate")], "CLOSED", "DUPLICATE"),  # match: close proposed, closed as duplicate
            issue(3, [rec(3, priority="P2")], "CLOSED", "COMPLETED", ["P3"]),  # band mismatch
            issue(4, [rec(4, "propose-close"), rec(4, "owner-accepted", at="2026-11-04T08:00:00Z")],
                  "OPEN", "REOPENED"),  # reopened after the proposed close
            issue(5, [rec(5), rec(5, "owner-rejected", at="2026-11-04T08:00:00Z")]),
            issue(6, [], created="2026-11-03T00:00:00Z"),  # untriaged: no time to triage
            issue(7, [{"createdAt": "2026-11-04T06:30:00Z", "body": "<!-- crew:v1 role=researcher pass=triage-log "
                       "sweep=a applied=0 proposed=4 skipped=1 tokens=12000 -->"},
                      {"createdAt": "2026-11-04T12:30:00Z", "body": "<!-- crew:v1 role=researcher pass=triage-log "
                       "sweep=b applied=0 proposed=2 skipped=0 tokens=unknown -->"},
                      {"createdAt": "2026-11-05T06:30:00Z", "body": "<!-- crew:v1 role=researcher pass=triage-log "
                       "sweep=c applied=0 proposed=3 skipped=0 tokens=20000 -->"}], labels=["triage:log"]),
        ]
        code, out, _ = run("report", "--items", self.write("i.json", items))
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), [
            "accuracy: 2/3 (67%) records match (closed items by band and close, answered applied records by the owner)",
            "override rate: 1/2 (50%) owner answers rejected or adjusted",
            "reopen rate: 1/2 (50%) closed-as-proposed items reopened",
            "time to triage: median 2.0 h over 5 items",
            "proposals per day: mean 4.5 over 2 days",
            "tokens per sweep: median 16000.0 over 2 sweeps (1 unknown)",
            "applied feedback: 0 accepted, 0 rejected, 0 adjusted",
            "clusters: 0 recorded, newest sizes total 0; 0 open issues labelled across 0 cluster labels"])

    def test_feedback_on_applied_records(self):  # #835
        def applied(n, answer, at, sweep="20261106T0600Z"):
            return issue(n, [rec(n, "place", mode="apply", sweep="20261106T0000Z", at="2026-11-06T00:10:00Z"),
                             rec(n, answer, mode="apply", sweep=sweep, at=at)])
        items = [applied(1, "owner-accepted", "2026-11-06T01:00:00Z"),
                 applied(2, "owner-rejected", "2026-11-06T02:00:00Z"),
                 applied(3, "owner-adjusted", "2026-11-06T03:00:00Z", sweep="20261106T1200Z"),
                 issue(4, [rec(4, "place", mode="apply")]),  # unanswered: not judged
                 issue(5, [rec(5), rec(5, "owner-rejected", at="2026-11-04T08:00:00Z")])]  # shadow: not applied
        code, out, _ = run("report", "--items", self.write("i.json", items), "--sweep", "20261106T1200Z")
        lines = out.splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(lines[0], "accuracy: 1/3 (33%) records match (closed items by band and close, "
                                   "answered applied records by the owner)")
        self.assertEqual(lines[1], "override rate: 3/4 (75%) owner answers rejected or adjusted")
        self.assertEqual(lines[6:], ["applied feedback: 1 accepted, 1 rejected, 1 adjusted",
                                     "clusters: 0 recorded, newest sizes total 0; 0 open issues labelled across 0 "
                                     "cluster labels",
                                     "applied feedback recorded by sweep 20261106T1200Z: 0 accepted, 0 rejected, "
                                     "1 adjusted",
                                     "clusters recorded by sweep 20261106T1200Z: 0, 0 new members, 0 proposed"])

    def test_cluster_counts(self):  # #1298
        def cluster(slug, size, new, proposed, sweep):
            return {"createdAt": "2026-11-08T18:10:00Z", "body": "[Riley/cluster] cluster:%s\n<!-- crew:v1 "
                    "role=researcher pass=triage-cluster cluster=%s size=%d new=%d band=P2 proposed=%d sweep=%s -->"
                    % (slug, slug, size, new, proposed, sweep)}
        log = issue(9, [cluster("class-stall", 2, 2, 0, "s1"), cluster("depends-6", 3, 3, 1, "s1"),
                        cluster("class-stall", 4, 2, 1, "s2")], labels=["triage:log"])
        items = [log, issue(1, labels=["cluster:class-stall"]), issue(2, labels=["cluster:class-stall"]),
                 issue(3, labels=["cluster:depends-6"]), issue(4, state="CLOSED", labels=["cluster:depends-6"])]
        self.assertEqual(tm.clusters(items), "clusters: 2 recorded, newest sizes total 7; 3 open issues labelled "
                                             "across 2 cluster labels")
        self.assertEqual(tm.clusters(items, "s2"), "clusters recorded by sweep s2: 1, 2 new members, 1 proposed")

    def test_cluster_newest_record_by_time_not_issue_order(self):  # review r1 finding 2
        def log(n, day, size):
            return issue(n, [{"createdAt": day + "T18:00:00Z", "body": "<!-- crew:v1 role=researcher "
                              "pass=triage-cluster cluster=class-stall size=%d new=0 band=P2 proposed=0 sweep=x -->"
                              % size}], labels=["triage:log"])
        logs = [log(11, "2026-11-09", 4), log(10, "2026-11-08", 2)]
        for order in (logs, logs[::-1]):
            self.assertTrue(tm.clusters(order).startswith("clusters: 1 recorded, newest sizes total 4;"))

    def test_accuracy_keeps_answered_applied_records_once(self):  # #835 review R1
        item = issue(1, [rec(1, "place", mode="apply", sweep="20261105T0000Z", at="2026-11-05T00:10:00Z"),
                         rec(1, "owner-rejected", mode="apply", sweep="20261105T0100Z", at="2026-11-05T01:10:00Z")])
        self.assertTrue(tm.report([item])[0].startswith("accuracy: 0/1 (0%)"))
        item["comments"].append(rec(1, "classify", priority="P1", mode="apply", sweep="20261105T0200Z",
                                    at="2026-11-05T02:10:00Z"))  # a later unanswered record keeps the answered one
        self.assertTrue(tm.report([item])[0].startswith("accuracy: 0/1 (0%)"))
        item["comments"].append(rec(1, "owner-accepted", mode="apply", sweep="20261105T0300Z",
                                    at="2026-11-05T03:10:00Z"))
        self.assertTrue(tm.report([item])[0].startswith("accuracy: 1/2 (50%)"))
        item.update(state="CLOSED", stateReason="COMPLETED", labels=[{"name": "P3"}])  # newest answered: no double count
        self.assertTrue(tm.report([item])[0].startswith("accuracy: 1/2 (50%)"))
        item["comments"].append(rec(1, "classify", priority="P3", mode="apply", sweep="20261105T0400Z",
                                    at="2026-11-05T04:10:00Z"))  # unanswered newest record: judged at close
        self.assertTrue(tm.report([item])[0].startswith("accuracy: 2/3 (67%)"))

    def test_rolling_bar_proposes_shadow_below_eight_of_ten(self):  # #835
        def answered(k, answer):
            return issue(k, [rec(k, "place", mode="apply", at="2026-11-06T00:10:00Z"),
                             rec(k, answer, mode="apply", at="2026-11-06T%02d:00:00Z" % k)])
        items = [answered(k, "owner-accepted") for k in range(1, 8)]
        code, out, _ = run("rolling", "--items", self.write("i.json", items))
        self.assertEqual((code, out.strip()), (1, "rolling: 7/10 accepted as is over the newest owner answers on "
                                                  "applied records, 0 rejected or adjusted, 3 pending (need 8): pending"))
        items += [answered(8, "owner-rejected"), answered(9, "owner-adjusted"), answered(10, "owner-rejected")]
        items.append(issue(11, [rec(11), rec(11, "owner-rejected", at="2026-11-06T23:00:00Z")]))  # shadow: ignored
        code, out, _ = run("rolling", "--items", self.write("i.json", items))
        self.assertEqual(code, 1)
        self.assertIn("3 rejected or adjusted, 0 pending (need 8): not met; propose a return to shadow mode", out)
        items[7]["comments"].append(rec(8, "owner-accepted", mode="apply", at="2026-11-06T12:00:00Z"))  # re-answered
        items.append(answered(12, "owner-accepted"))  # the oldest answer rolls out of the window
        code, out, _ = run("rolling", "--items", self.write("i.json", items))
        self.assertEqual((code, out.strip()), (0, "rolling: 8/10 accepted as is over the newest owner answers on "
                                                  "applied records, 2 rejected or adjusted, 0 pending (need 8): met"))

    def test_eval_freeze_and_score(self):
        items = backlog(8, 2)
        out_path = os.path.join(self.tmp.name, "eval.json")
        code, out, _ = run("eval-freeze", "--items", self.write("i.json", items), "--sweep", SWEEP, "--out", out_path)
        self.assertEqual((code, out.strip()), (0, "eval set: 8 owner-confirmed records -> %s" % out_path))
        with open(out_path) as f:
            frozen = json.load(f)["records"]
        answers = {r: dict(v) for r, v in frozen.items()}
        answers[sorted(answers)[0]]["priority"] = "P1"
        code, out, _ = run("eval-score", "--set", out_path, "--answers", self.write("a.json", answers))
        self.assertEqual((code, out.strip()), (0, "eval: 7/8 (88%) records match the eval set"))

    def test_usage_and_unreadable(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            tm.main(["bar", "--items", "x.json"])
        self.assertEqual(cm.exception.code, 2)
        code, _, err = run("report", "--items", os.path.join(self.tmp.name, "missing.json"))
        self.assertEqual(code, 2)
        self.assertIn("unreadable input", err)


if __name__ == "__main__":
    unittest.main()
