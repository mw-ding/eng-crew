"""Tests for mdstack gc (#316): the dry-run-first, merged-only sweep of run copies lifecycle reaping missed.

Covers: a merged, landed run is listed in dry run and removed with --apply (records too; a reviewer's linked
worktree through git), a rerun is a no-op; --max bounds removals; a live window, unlanded work and a closed-unmerged
PR and a nested evidence worktree are kept with reasons; an orphan copy with no run record is removed on squash-merged head proof and kept without a
merged PR or while a working-copy claim holds it; a failed removal exits 1 and keeps the records; a backstop wake through mdstack route recovers a
missed close-out. Fixtures in crew_testlib.py (stdlib only). Run in CI.
"""
import json
import os
import shutil
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import KillLandedBase

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
prs = json.load(open(os.environ["FAKE_PRS"])) if os.path.exists(os.environ["FAKE_PRS"]) else {}
if args[:2] == ["pr", "view"] and args[args.index("--json") + 1] == "state":
    print(json.dumps({"state": prs[args[2]]["state"]}))
elif args[:2] == ["pr", "list"]:
    print(json.dumps([dict(p, number=int(n)) for n, p in prs.items() if p["state"] == "MERGED"]))
elif args[:2] in (["issue", "view"], ["pr", "view"]):
    print(json.dumps({"labels": [], "closingIssuesReferences": []}))
else:
    sys.exit(1)
"""


class Gc(KillLandedBase):
    def setUp(self):
        super().setUp()
        self.env["FAKE_PRS"] = os.path.join(self.tmp, "prs.json")
        with open(os.path.join(self.tmp, "bin", "gh"), "w") as f:
            f.write(FAKE_GH)

    def prs(self, **states):
        with open(self.env["FAKE_PRS"], "w") as f:
            json.dump({n.lstrip("n"): {"state": s, "headRefOid": h} for n, (s, h) in states.items()}, f)

    def gc(self, *args):
        return self.crew("gc", "--project", self.project, *args)

    def drop_window(self, name):  # the window is gone: a refused or missed close-out left the run behind
        with open(self.state_file) as f:
            data = json.load(f)
        data["crew-acme-widgets"] = {k: v for k, v in data["crew-acme-widgets"].items() if v != name}
        with open(self.state_file, "w") as f:
            json.dump(data, f)

    def merged_builder(self, state="MERGED"):
        wt = os.path.realpath(self.builder())  # gc prints real paths (macOS /var is /private/var)
        self.git("checkout", "-q", "-b", "builder/7-x", cwd=wt)
        head = self.commit(wt)
        self.git("push", "-q", "origin", "HEAD:refs/pull/12/head", cwd=wt)
        self.put("status/ben-7.status", "done: #7 #12 %s\n" % head)
        self.prs(n12=(state, head))
        return wt, head

    def rows(self, r):
        return [line.split("\t") for line in r.stdout.splitlines() if "\t" in line]

    def test_merged_landed_run_dry_run_then_removed_and_rerun_noop(self):
        wt, _ = self.merged_builder()
        self.drop_window("ben-7")
        r = self.gc()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rows(r), [[wt, "ben-7", "remove", "PR #12 merged, landed"]])
        self.assertIn("gc: dry run: 1 to remove, 0 kept", r.stdout)
        self.assertTrue(os.path.isdir(wt))
        r = self.gc("--apply", "--max", "0")
        self.assertEqual(self.rows(r), [[wt, "ben-7", "keep", "over --max 0"]])
        self.assertTrue(os.path.isdir(wt))
        r = self.gc("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rows(r), [[wt, "ben-7", "removed", "PR #12 merged, landed"]])
        self.assertFalse(os.path.exists(wt))
        for rel in ["runs/ben-7.json", "status/ben-7.status", "claims/builder-issue7"]:
            self.assertFalse(os.path.exists(os.path.join(self.state, rel)), rel)
        r = self.gc("--apply")
        self.assertEqual((r.returncode, self.rows(r)), (0, []))
        self.assertIn("gc: removed 0, failed 0, kept 0", r.stdout)

    def test_merged_reviewer_linked_worktree_removed_by_git(self):
        sha = self.pr(9, "codex gpt-6.1-sol medium")
        self.assertEqual(self.spawn("reviewer", "--pr", "9").returncode, 0)
        wt = os.path.realpath(self.record("vera-9-r1-review")["worktree"])
        self.assertTrue(os.path.isfile(os.path.join(wt, ".git")))  # a linked worktree of the checkout
        self.drop_window("vera-9-r1-review")
        self.prs(n9=("MERGED", sha))
        r = self.gc("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rows(r), [[wt, "vera-9-r1-review", "removed", "PR #9 merged, landed"]])
        self.assertFalse(os.path.exists(wt))
        self.assertNotIn(wt, self.git("worktree", "list"))

    def test_live_window_unlanded_and_closed_unmerged_kept(self):
        wt, _ = self.merged_builder()
        self.assertEqual(self.rows(self.gc("--apply")), [[wt, "ben-7", "keep", "window live"]])
        self.drop_window("ben-7")
        with open(os.path.join(wt, "notes.txt"), "w") as f:
            f.write("x\n")
        r = self.gc("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rows(r), [[wt, "ben-7", "keep", "unlanded: uncommitted: ?? notes.txt"]])
        os.remove(os.path.join(wt, "notes.txt"))
        self.prs(n12=("CLOSED", "x"))
        self.assertEqual(self.rows(self.gc("--apply")), [[wt, "ben-7", "keep", "PR #12 closed, not merged"]])
        self.assertTrue(os.path.isdir(wt))
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))

    def test_nested_evidence_worktree_kept(self):  # .crew/ is excluded, so C6 status alone would not see it
        wt, _ = self.merged_builder()
        self.drop_window("ben-7")
        self.git("worktree", "add", "-q", "--detach", os.path.join(wt, ".crew", "evidence"), cwd=wt)
        self.assertEqual(self.rows(self.gc("--apply")), [[wt, "ben-7", "keep", "has nested worktrees"]])
        self.assertTrue(os.path.isdir(os.path.join(wt, ".crew", "evidence")))

    def orphan(self):
        """ben-7's copy with its run record lost after a squash merge of PR 12 deleted the branch."""
        wt, head = self.merged_builder()
        self.drop_window("ben-7")
        self.git("fetch", "-q", "origin", "refs/pull/12/head")
        self.git("merge", "--squash", "FETCH_HEAD")
        self.git("commit", "-q", "-m", "squash PR 12")
        self.git("push", "-q", "origin", "main")
        os.remove(os.path.join(self.state, "runs", "ben-7.json"))
        os.utime(wt, (0, 0))  # older than the orphan age guard
        return wt, head

    def test_orphan_squash_merged_removed_on_head_proof(self):
        wt, head = self.orphan()
        r = self.gc("--apply")
        self.assertEqual(self.rows(r), [[wt, "-", "keep", "working-copy claim held by run ben-7"]])
        shutil.rmtree(self.env["MDSTACK_COPY_CLAIMS"])  # its holder is gone; the owner dropped the stale claim
        self.prs(n12=("MERGED", "0" * 40))
        self.assertEqual(self.rows(self.gc("--apply")), [[wt, "-", "keep", "no merged PR"]])
        self.prs(n12=("MERGED", head))
        r = self.gc("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.rows(r), [[wt, "-", "removed", "PR #12 merged, landed"]])
        self.assertFalse(os.path.exists(wt))

    def test_failed_removal_exits_nonzero_and_keeps_records(self):
        wt, _ = self.merged_builder()
        self.drop_window("ben-7")
        root = os.path.dirname(wt)
        os.chmod(root, 0o555)
        self.addCleanup(os.chmod, root, 0o755)
        r = self.gc("--apply")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        (row,) = self.rows(r)
        self.assertEqual(row[:3], [wt, "ben-7", "failed"])
        self.assertIn("gc: removed 0, failed 1, kept 0", r.stdout)
        self.assertTrue(os.path.isdir(wt))
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))

    def test_backstop_wake_recovers_a_missed_close_out(self):
        wt, _ = self.merged_builder()
        self.drop_window("ben-7")
        self.put("wake/queue.jsonl", json.dumps({"reason": "backstop", "event": "due (idle in flight)"}) + "\n")
        r = self.crew("route", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("\tben-7\tremoved\tPR #12 merged, landed", r.stdout)
        self.assertFalse(os.path.exists(wt))


if __name__ == "__main__":
    unittest.main()
