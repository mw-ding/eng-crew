#!/usr/bin/env python3
"""Offline self-test for scripts/reflection-effects.py (no network), through its real CLI.

Covers the proposal -> issue -> PR chain from decision comments (a later decision wins, an unmerged issue stays
pending), activation pending, an open first window with its next evaluation date, no baseline, keep / revise /
revert on a repo/class cohort that drops other repos and classes, equal-length before/after windows for an incident
counter over several windows, sample coverage shown per side, a cohort that cannot be established (no card class, a
CSV without `class`, lines without `repo`/`class`) as insufficient, fewer than 3 PRs, unknown counter coverage, the
markdown sidecar's non-causal header, and malformed input. Run in CI.
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
NAMES = {11: "keep", 12: "revise", 13: "revert", 14: "few", 15: "act", 16: "open", 17: "early", 18: "nobase",
         19: "ft", 20: "stall", 21: "noclass"}
DECISION = "[Ash/reflection-decision] week-2026-10-05\n\n" + "".join(
    "- rp-%s: %saccept → #%d (new)\n" % (name, "correct scope; " if name == "few" else "", n)
    for n, name in NAMES.items()) + "- rp-gone: reject one-off\nSource: owner answer.\n"
METRICS = {11: "verdict_rounds_per_pr", 12: "verdict_rounds_per_pr", 13: "verdict_rounds_per_pr",
           14: "ci_fix_rounds_per_pr", 19: "false_throttles", 20: "stall_minutes"}


def issue(n):
    cls = "" if n == 21 else "**Failure class:** %s\n" % NAMES[n]
    body = cls + "- **Effect metric**: `%s`, lower is better\n" % METRICS.get(n, "verdict_rounds_per_pr")
    return {"number": n, "url": "%s/issues/%d" % (GH, n), "state": "OPEN" if n == 16 else "CLOSED", "title": "t",
            "comments": [], "body": body}


def pr(n, closes):
    return {"number": n, "url": "%s/pull/%d" % (GH, n), "state": "MERGED", "title": "fix", "comments": [],
            "body": "Closes #%d" % closes, "closedAt": "2026-10-10T00:00:00Z"}


LOG = {"number": 1, "url": GH + "/issues/1", "state": "OPEN", "title": "Reflection log", "body": "",
       "comments": [{"body": "[Ash/reflection-decision] week-x\n\n- rp-keep: accept → #99 (new)\n",
                     "createdAt": "2026-10-06T00:00:00Z"},  # superseded by the later decision
                    {"body": DECISION, "createdAt": "2026-10-07T00:00:00Z"}]}
FORGE = [LOG] + [issue(n) for n in NAMES] + [pr(100 + n, n) for n in NAMES if n != 16]
BASE = {"since": "2026-09-28T00:00:00Z", "until": "2026-10-12T00:00:00Z"}  # 14 days before activation
ACT = "2026-10-12T00:00:00Z"  # first after window: 2026-10-12 to 2026-10-26; the second to 2026-11-09


def baseline(proposal, name, repo="o/m"):
    return {"type": "baseline", "proposal": proposal, "window": BASE, name: {"refs": ["%s#1" % repo]}}


def activation(proposal, at=ACT, value="v1 installed"):
    return {"type": "activation", "proposal": proposal, "activation": value, "recorded_at": at}


LEDGER = [baseline("rp-keep", "verdict_rounds_per_pr"), activation("rp-keep"),
          baseline("rp-revise", "verdict_rounds_per_pr"), activation("rp-revise"),
          baseline("rp-revert", "verdict_rounds_per_pr", repo="o/other"), activation("rp-revert"),
          baseline("rp-few", "ci_fix_rounds_per_pr"), activation("rp-few"),
          baseline("rp-act", "verdict_rounds_per_pr"), activation("rp-act", value="pending"),
          baseline("rp-early", "verdict_rounds_per_pr"), activation("rp-early", "2026-10-25T00:00:00Z"),
          activation("rp-nobase"),
          baseline("rp-ft", "false_throttles"), activation("rp-ft"),
          baseline("rp-stall", "stall_minutes"), activation("rp-stall"),
          baseline("rp-noclass", "verdict_rounds_per_pr"), activation("rp-noclass")]
BEFORE, AFTER = "2026-10-0%dT00:00:00Z", "2026-10-1%dT00:00:00Z"
CSV = ["repo,pr,merged_at,verdicts,ci_fix_rounds,class"] + [
    "%s,%d,%s,%d,%d,%s" % (repo, k, when % (k % 3 + (1 if when == BEFORE else 3)), v, v, cls) for k, (repo, when, v, cls) in enumerate([
        ("o/m", BEFORE, 3, "keep"), ("o/m", BEFORE, 3, "keep"), ("o/m", BEFORE, 3, "keep"),
        ("o/m", AFTER, 1, "keep"), ("o/m", AFTER, 1, "keep"), ("o/m", AFTER, 2, "keep"),
        ("o/m", AFTER, 9, "unrelated"), ("o/m", AFTER, 9, "unrelated"), ("o/x", AFTER, 9, "keep"),
        ("o/m", BEFORE, 1, "revise"), ("o/m", BEFORE, 1, "revise"), ("o/m", BEFORE, 1, "revise"),
        ("o/m", AFTER, 1, "revise"), ("o/m", AFTER, 1, "revise"), ("o/m", AFTER, 2, "revise"),
        ("o/other", BEFORE, 1, "revert"), ("o/other", BEFORE, 1, "revert"), ("o/other", BEFORE, 1, "revert"),
        ("o/other", AFTER, 2, "revert"), ("o/other", AFTER, 2, "revert"), ("o/other", AFTER, 2, "revert"),
        ("o/m", BEFORE, 1, "few"), ("o/m", BEFORE, 1, "few"),
        ("o/m", AFTER, 0, "few"), ("o/m", AFTER, 0, "few"), ("o/m", AFTER, 0, "few")], start=1)]
INCIDENTS = [{"id": "i-%d" % k, "kind": "false-throttle", "confirmed": "https://x/%d" % k, "ts": ts,
              "repo": "o/m", "class": "ft"} for k, ts in enumerate(
    ["2026-10-01T00:00:00Z", "2026-10-15T00:00:00Z", "2026-10-30T00:00:00Z"])] + [
    {"id": "i-other", "kind": "false-throttle", "confirmed": "https://x/o", "ts": "2026-10-16T00:00:00Z",
     "repo": "o/m", "class": "unrelated"}]
OBS = [dict(source="watch", repo="o/m", key="run:a", **o) for o in (
    {"kind": "stall", "since": "2026-09-30T12:00:00Z", "ts": "2026-09-30T12:10:00Z", "class": "stall"},
    {"kind": "resume", "since": "2026-09-30T12:00:00Z", "ts": "2026-09-30T12:40:00Z", "class": "stall"},
    {"kind": "stall", "since": "2026-10-14T00:00:00Z", "ts": "2026-10-14T00:10:00Z", "class": "stall"},
    {"kind": "resume", "since": "2026-10-14T00:00:00Z", "ts": "2026-10-14T00:20:00Z", "class": "stall"},
    {"kind": "stall", "since": "2026-10-15T00:00:00Z", "ts": "2026-10-15T09:00:00Z", "class": "unrelated"})]


def jsonl(rows):
    return "".join(json.dumps(r) + "\n" for r in rows)


class ReflectionEffects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.paths = {}
        for name, data in (("forge", json.dumps(FORGE)), ("csv", "\n".join(CSV) + "\n"), ("ledger", jsonl(LEDGER)),
                           ("incidents", jsonl(INCIDENTS)), ("observations", jsonl(OBS))):
            self.paths[name] = os.path.join(self.tmp, name)
            self.write(name, data)

    def write(self, name, data):
        with open(self.paths[name], "w") as f:
            f.write(data)

    def run_cli(self, *extra, now="2026-11-01", inputs=("csv", "incidents", "observations"), code=0):
        args = [a for name in inputs for a in ("--" + name, self.paths[name])]
        r = subprocess.run([sys.executable, SCRIPT, "--forge", self.paths["forge"], "--ledger", self.paths["ledger"],
                            "--now", now, *args, *extra], capture_output=True, text=True)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r

    def rows(self, **kw):
        return {r["proposal"]: r for r in json.loads(self.run_cli("--json", **kw).stdout)}

    def test_chain_from_decisions_later_wins_rejects_skipped(self):
        rows = self.rows()
        self.assertEqual(sorted(rows), sorted("rp-" + name for name in NAMES.values()))
        self.assertEqual((rows["rp-keep"]["issue"], rows["rp-keep"]["pr"]), ("o/m#11", "o/m#111"))
        self.assertEqual((rows["rp-open"]["pr"], rows["rp-open"]["status"], rows["rp-open"]["missing"]),
                         (None, "pending", ["not merged"]))

    def test_pending_until_activation_and_a_whole_window(self):
        rows = self.rows()
        self.assertEqual((rows["rp-act"]["status"], rows["rp-act"]["missing"], rows["rp-act"]["activation"]),
                         ("pending", ["activation pending"], "pending"))
        early = rows["rp-early"]
        self.assertEqual((early["status"], early["next_evaluation"], early["missing"]),
                         ("pending", "2026-11-08", ["first 14-day window open"]))
        self.assertEqual((rows["rp-nobase"]["status"], rows["rp-nobase"]["missing"]),
                         ("insufficient", ["no baseline"]))

    def test_recommendations_on_the_repo_and_class_cohort(self):
        rows = self.rows()
        keep, revise, revert = rows["rp-keep"], rows["rp-revise"], rows["rp-revert"]
        # unrelated-class and o/x rows excluded from both sides
        self.assertEqual((keep["before"]["value"], keep["after"]["value"], keep["after"]["n"]), (3.0, 1.3, 3))
        self.assertEqual((keep["repos"], keep["class"], keep["status"], keep["recommendation"]),
                         (["o/m"], "keep", "evaluated", "keep"))
        self.assertEqual((revise["before"]["value"], revise["after"]["value"], revise["recommendation"]),
                         (1.0, 1.3, "revise"))  # +30%, not more
        self.assertEqual((revert["repos"], revert["after"]["value"], revert["recommendation"]),
                         (["o/other"], 2.0, "revert"))

    def test_counter_windows_stay_equal_length(self):  # r1 finding 1
        for now in ("2026-11-01", "2026-11-10"):  # after window 2026-10-12..26, then 2026-10-26..11-09
            with self.subTest(now=now):
                ft = self.rows(now=now)["rp-ft"]
                self.assertEqual((ft["before"]["value"], ft["after"]["value"], ft["after"]["refs"]),
                                 (1, 1, ["i-1" if now == "2026-11-01" else "i-2"]))  # i-other: another class
                self.assertEqual((ft["status"], ft["recommendation"]), ("evaluated", "keep"))
                self.assertEqual(ft["after"]["coverage"], "confirmed incidents in window")

    def test_coverage_shown_for_each_side(self):  # r1 finding 3
        stall = self.rows()["rp-stall"]
        self.assertEqual((stall["before"]["value"], stall["after"]["value"], stall["recommendation"]),
                         (30.0, 20.0, "keep"))  # the unrelated-class stall is outside the cohort
        out = self.run_cli().stdout
        self.assertIn("| 30.0 (n=1; coverage partial 2026-09-30T12:10:00Z to 2026-10-12T00:00:00Z) "
                      "| 20.0 (n=1; coverage partial 2026-10-12T00:00:00Z to 2026-10-14T00:20:00Z) |", out)
        self.assertIn("| 1 (n=1; coverage confirmed incidents in window) | 1 (n=1; coverage confirmed incidents in "
                      "window) |", out)

    def test_cohort_not_established_is_insufficient(self):  # r1 finding 2
        rows = self.rows()
        self.assertEqual((rows["rp-noclass"]["status"], rows["rp-noclass"]["missing"]),
                         ("insufficient", ["no proposal class"]))
        self.write("csv", "\n".join(line.rsplit(",", 1)[0] for line in CSV) + "\n")
        self.write("incidents", jsonl([{k: v for k, v in i.items() if k != "class"} for i in INCIDENTS]))
        rows = self.rows()
        self.assertEqual((rows["rp-keep"]["status"], rows["rp-keep"]["missing"], rows["rp-keep"]["after"]),
                         ("insufficient", ["cohort: CSV records no class"], None))
        self.assertEqual(rows["rp-ft"]["missing"], ["cohort: incidents lines record no repo or class"])
        self.assertEqual(rows["rp-stall"]["status"], "evaluated")

    def test_insufficient_samples_and_unknown_counter_coverage(self):
        rows = self.rows(inputs=("csv",))
        self.assertEqual((rows["rp-few"]["status"], rows["rp-few"]["missing"], rows["rp-few"]["recommendation"]),
                         ("insufficient", ["before n=2 < 3"], "none"))
        self.assertEqual((rows["rp-ft"]["status"], rows["rp-ft"]["missing"]),
                         ("insufficient", ["before coverage unknown", "after coverage unknown"]))

    def test_markdown_sidecar(self):
        out = self.run_cli().stdout
        self.assertTrue(out.startswith("Recommendations only: a before/after comparison, not a cause"))
        self.assertIn("| rp-keep | o/m#11 → o/m#111 | v1 installed | verdict_rounds_per_pr | 3.0 (n=3; coverage csv "
                      "merged_at in window) | 1.3 (n=3; coverage csv merged_at in window) | o/m; keep | none "
                      "| evaluated | 2026-11-09 | keep |", out)
        self.assertIn("| rp-open | o/m#16 → none | pending |", out)

    def test_malformed_forge_exits_2(self):
        self.write("forge", "{}")
        self.assertIn("unreadable input", self.run_cli(code=2).stderr)


if __name__ == "__main__":
    unittest.main()
