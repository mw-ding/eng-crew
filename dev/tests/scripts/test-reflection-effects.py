#!/usr/bin/env python3
"""Offline self-test for scripts/reflection-effects.py (no network), through its real CLI.

Covers the proposal -> issue -> PR chain from decision comments (a later decision wins, an unmerged issue stays
pending), activation pending, an open first 14-day window with its next evaluation date, no baseline, keep / revise /
revert recommendations on a cohort-limited CSV, fewer than 3 PRs as insufficient, a counter whose coverage is unknown,
the markdown sidecar's non-causal header, and malformed input. Run in CI.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts", "reflection-effects.py")
GH = "https://github.com/o/m"
DECISION = """[Ash/reflection-decision] week-2026-10-05

- rp-keep: accept → #11 (new)
- rp-revise: accept → #12 (new)
- rp-revert: accept → #13 (new)
- rp-few: correct scope; accept → #14 (new)
- rp-act: accept → #15 (new)
- rp-open: accept → #16 (new)
- rp-early: accept → #17 (new)
- rp-nobase: accept → #18 (new)
- rp-stall: accept → #19 (new)
- rp-gone: reject one-off
Source: owner answer.
"""


def issue(n, metric, state="CLOSED"):
    return {"number": n, "url": "%s/issues/%d" % (GH, n), "state": state, "title": "t", "comments": [],
            "body": "**Failure class:** stall\n- **Effect metric**: `%s`, lower is better\n" % metric}


def pr(n, closes):
    return {"number": n, "url": "%s/pull/%d" % (GH, n), "state": "MERGED", "title": "fix", "comments": [],
            "body": "Closes #%d" % closes, "closedAt": "2026-10-10T00:00:00Z"}


LOG = {"number": 1, "url": GH + "/issues/1", "state": "OPEN", "title": "Reflection log", "body": "",
       "comments": [{"body": "[Ash/reflection-decision] week-x\n\n- rp-keep: accept → #99 (new)\n",
                     "createdAt": "2026-10-06T00:00:00Z"},  # superseded by the later decision
                    {"body": DECISION, "createdAt": "2026-10-07T00:00:00Z"}]}
FORGE = [LOG, issue(11, "verdict_rounds_per_pr"), issue(12, "verdict_rounds_per_pr"),
         issue(13, "verdict_rounds_per_pr"), issue(14, "ci_fix_rounds_per_pr"), issue(15, "verdict_rounds_per_pr"),
         issue(16, "verdict_rounds_per_pr", "OPEN"), issue(17, "verdict_rounds_per_pr"),
         issue(18, "verdict_rounds_per_pr"), issue(19, "stall_minutes")] + [
    pr(100 + n, n) for n in (11, 12, 13, 14, 15, 17, 18, 19)]


def baseline(proposal, name, value, n, repo="o/m"):
    refs = ["%s#%d" % (repo, k) for k in range(n)]
    return {"type": "baseline", "proposal": proposal, name: {"value": value, "n": n, "refs": refs,
                                                             "coverage": "csv merged_at in window"}}


def activation(proposal, at, value="v1 installed"):
    return {"type": "activation", "proposal": proposal, "activation": value, "recorded_at": at}


ACT = "2026-10-12T00:00:00Z"  # after window: 2026-10-12 to 2026-10-26 (now 2026-11-01: one whole window)
LEDGER = [baseline("rp-keep", "verdict_rounds_per_pr", 3.0, 3), activation("rp-keep", ACT),
          baseline("rp-revise", "verdict_rounds_per_pr", 1.0, 3), activation("rp-revise", ACT),
          baseline("rp-revert", "verdict_rounds_per_pr", 1.0, 3, repo="o/other"), activation("rp-revert", ACT),
          baseline("rp-few", "ci_fix_rounds_per_pr", 1.0, 2), activation("rp-few", ACT),
          baseline("rp-act", "verdict_rounds_per_pr", 1.0, 3), activation("rp-act", ACT, "pending"),
          baseline("rp-early", "verdict_rounds_per_pr", 1.0, 3), activation("rp-early", "2026-10-25T00:00:00Z"),
          activation("rp-nobase", ACT),
          baseline("rp-stall", "stall_minutes", 40.0, 2), activation("rp-stall", ACT)]
CSV = """repo,pr,merged_at,verdicts,ci_fix_rounds
o/m,1,2026-10-13T00:00:00Z,1,0
o/m,2,2026-10-14T00:00:00Z,1,0
o/m,3,2026-10-15T00:00:00Z,2,1
o/other,4,2026-10-13T00:00:00Z,2,0
o/other,5,2026-10-14T00:00:00Z,2,0
o/other,6,2026-10-15T00:00:00Z,2,0
o/m,7,2026-10-30T00:00:00Z,9,9
"""


class ReflectionEffects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.paths = {}
        for name, data in (("forge", json.dumps(FORGE)), ("csv", CSV),
                           ("ledger", "".join(json.dumps(r) + "\n" for r in LEDGER))):
            self.paths[name] = os.path.join(self.tmp, name)
            with open(self.paths[name], "w") as f:
                f.write(data)

    def run_cli(self, *extra, code=0):
        r = subprocess.run([sys.executable, SCRIPT, "--forge", self.paths["forge"], "--ledger", self.paths["ledger"],
                            "--csv", self.paths["csv"], "--now", "2026-11-01", *extra], capture_output=True, text=True)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def rows(self):
        return {r["proposal"]: r for r in json.loads(self.run_cli("--json").stdout)}

    def test_chain_from_decisions_later_wins_rejects_skipped(self):
        rows = self.rows()
        self.assertEqual(sorted(rows), ["rp-act", "rp-early", "rp-few", "rp-keep", "rp-nobase", "rp-open",
                                        "rp-revert", "rp-revise", "rp-stall"])
        self.assertEqual((rows["rp-keep"]["issue"], rows["rp-keep"]["pr"]), ("o/m#11", "o/m#111"))
        self.assertEqual((rows["rp-open"]["pr"], rows["rp-open"]["status"], rows["rp-open"]["missing"]),
                         (None, "pending", ["not merged"]))

    def test_pending_until_activation_and_a_whole_window(self):
        rows = self.rows()
        self.assertEqual((rows["rp-act"]["status"], rows["rp-act"]["missing"], rows["rp-act"]["activation"]),
                         ("pending", ["activation pending"], "pending"))
        early = rows["rp-early"]
        self.assertEqual((early["status"], early["next_evaluation"], early["after"]), ("pending", "2026-11-08", None))
        self.assertEqual((rows["rp-nobase"]["status"], rows["rp-nobase"]["missing"]),
                         ("insufficient", ["no baseline"]))

    def test_recommendations_on_the_cohort(self):
        rows = self.rows()
        keep, revise, revert = rows["rp-keep"], rows["rp-revise"], rows["rp-revert"]
        self.assertEqual((keep["after"]["value"], keep["after"]["n"], keep["repos"], keep["class"]),
                         (1.3, 3, ["o/m"], "stall"))  # o/m only: the 2026-10-30 row is outside the window
        self.assertEqual((keep["status"], keep["recommendation"], keep["next_evaluation"]),
                         ("evaluated", "keep", "2026-11-09"))
        self.assertEqual((revise["recommendation"], revise["before"]["value"]), ("revise", 1.0))  # +30%, not more
        self.assertEqual((revert["repos"], revert["after"]["value"], revert["recommendation"]),
                         (["o/other"], 2.0, "revert"))

    def test_insufficient_samples_and_unknown_counter_coverage(self):
        rows = self.rows()
        self.assertEqual((rows["rp-few"]["status"], rows["rp-few"]["missing"], rows["rp-few"]["recommendation"]),
                         ("insufficient", ["before n=2 < 3"], "none"))
        stall = rows["rp-stall"]
        self.assertEqual((stall["status"], stall["missing"]), ("insufficient", ["after coverage unknown"]))

    def test_markdown_sidecar(self):
        out = self.run_cli().stdout
        self.assertTrue(out.startswith("Recommendations only: a before/after comparison, not a cause"))
        self.assertIn("| rp-keep | o/m#11 → o/m#111 | v1 installed | verdict_rounds_per_pr | 3.0 (n=3) | 1.3 (n=3) "
                      "| o/m; stall | none | evaluated | 2026-11-09 | keep |", out)
        self.assertIn("| rp-open | o/m#16 → none | pending |", out)

    def test_malformed_forge_exits_2(self):
        with open(self.paths["forge"], "w") as f:
            f.write("{}")
        self.assertIn("unreadable input", self.run_cli(code=2).stderr)


if __name__ == "__main__":
    unittest.main()
