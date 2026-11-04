#!/usr/bin/env python3
"""Offline self-test for scripts/triage-metrics.py (no network).

Builds a calibration sweep over twelve fixture issues and checks the deterministic 10-sample spot check, the
8-of-10 bar (met, not met, pending; an answer to a revised proposal never counts for the original), each report metric, and the eval set freeze and re-score. Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("triage_metrics", os.path.join(HERE, "triage-metrics.py"))
tm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tm)

SWEEP = "20261104T0600Z"


def rec(issue, decision="classify", priority="P2", sweep=SWEEP, at="2026-11-04T06:10:00Z"):
    return {"createdAt": at, "author": {"login": "riley"},
            "body": "[Riley/triage] #%d\n<!-- crew:v1 role=researcher pass=triage issue=%d decision=%s priority=%s "
                    "mode=shadow sweep=%s -->" % (issue, issue, decision, priority, sweep)}


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
            "accuracy: 2/3 (67%) closed items match the newest record (band and close)",
            "override rate: 1/2 (50%) owner answers rejected",
            "reopen rate: 1/2 (50%) closed-as-proposed items reopened",
            "time to triage: median 2.0 h over 5 items",
            "proposals per day: mean 4.5 over 2 days",
            "tokens per sweep: median 16000.0 over 2 sweeps (1 unknown)"])

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
