#!/usr/bin/env python3
"""Fixture test for scripts/worktree-purge.py (offline, temp repos only).

Covers every keep reason (main, current directory, protected, run record,
claim, tmux pane, uncommitted changes, open PR, PR head mismatch, no PR,
remote branch moved), the remove class (head in origin/main, merged PR with
remote branch gone or matching, `.crew/` scratch ignored), and `--apply`
removing only `remove` rows without touching branches. The GitHub lookup and
tmux pane list are injected, so no network or tmux. Run in CI.
"""
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("worktree_purge", os.path.join(HERE, "worktree-purge.py"))
wp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wp)


def sh(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], check=True, capture_output=True, text=True).stdout.strip()


class WorktreePurgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = os.path.realpath(self.tmp.name)
        self.origin = os.path.join(self.d, "origin.git")
        self.repo = os.path.join(self.d, "repo")
        self.state = os.path.join(self.d, "state")
        os.makedirs(os.path.join(self.state, "runs"))
        os.makedirs(os.path.join(self.state, "claims"))
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.origin], check=True)
        subprocess.run(["git", "clone", "-q", self.origin, self.repo], check=True, capture_output=True)
        for k, v in (("user.name", "t"), ("user.email", "t@t"), ("commit.gpgsign", "false")):
            sh(self.repo, "config", k, v)
        self.commit(self.repo, "base")
        sh(self.repo, "push", "-q", "origin", "HEAD:main")
        self.prs = {}
        self.panes = []

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, cwd, msg):
        with open(os.path.join(cwd, msg + ".txt"), "w") as fh:
            fh.write(msg)
        sh(cwd, "add", ".")
        sh(cwd, "commit", "-q", "-m", msg)
        return sh(cwd, "rev-parse", "HEAD")

    def wt(self, name, branch=True, work=True):
        path = os.path.join(self.d, "wt", name)
        sh(self.repo, "worktree", "add", "-q", *(["-b", "b/" + name] if branch else ["--detach"]), path, "origin/main")
        head = self.commit(path, name) if work else sh(path, "rev-parse", "HEAD")
        return path, head

    def pr(self, name, head, state, push=False):
        self.prs[name] = [{"number": len(self.prs) + 1, "state": state, "headRefOid": head, "headRefName": "b/" + name}]
        if push:
            sh(self.repo, "push", "-q", "origin", "%s:refs/heads/b/%s" % (head, name))

    def lookup(self, repo, branch, sha):
        return [p for v in self.prs.values() for p in v if p["headRefName"] == branch or p["headRefOid"] == sha]

    def run_purge(self, apply=False, cwd=None, protect=()):
        out = io.StringIO()
        wp.run(self.repo, self.state, list(protect), "main", apply, cwd or self.d,
               lookup=self.lookup, panes=lambda: self.panes, out=out)
        rows = {}
        for line in out.getvalue().splitlines():
            parts = line.split("\t")
            if len(parts) == 6:
                rows[os.path.basename(parts[0])] = (parts[4], parts[5])
        return rows, out.getvalue()

    def test_classifies_every_reason(self):
        merged_path, merged = self.wt("merged-in-main")
        sh(merged_path, "push", "-q", "origin", "HEAD:main")
        sh(self.repo, "fetch", "-q")
        _, gone = self.wt("squash-gone")
        self.pr("squash-gone", gone, "MERGED")
        _, match = self.wt("squash-match")
        self.pr("squash-match", match, "MERGED", push=True)
        scratch, sh_head = self.wt("scratch-only")
        self.pr("scratch-only", sh_head, "CLOSED")
        os.makedirs(os.path.join(scratch, ".crew", "runs"))
        open(os.path.join(scratch, ".crew", "runs", "x.md"), "w").close()
        _, open_head = self.wt("open-pr")
        self.pr("open-pr", open_head, "OPEN")
        mism, old = self.wt("mismatch")
        self.pr("mismatch", old, "MERGED")
        self.commit(mism, "later")
        self.wt("no-pr")
        moved_path, moved = self.wt("moved")
        self.pr("moved", moved, "MERGED", push=True)
        newer = self.commit(moved_path, "newer")
        sh(self.repo, "push", "-q", "origin", "%s:refs/heads/b/moved" % newer)
        sh(moved_path, "reset", "-q", "--hard", moved)
        dirty, _ = self.wt("dirty", work=False)
        with open(os.path.join(dirty, "base.txt"), "a") as fh:
            fh.write("edit")
        run_path, _ = self.wt("run-ref", work=False)
        with open(os.path.join(self.state, "runs", "ben-1.json"), "w") as fh:
            json.dump({"worktree": run_path, "args": {"pr": None}}, fh)
        self.wt("42-claimed", work=False)
        with open(os.path.join(self.state, "claims", "builder-issue42"), "w") as fh:
            fh.write("heartbeat: x\n")
        pane_path, _ = self.wt("pane", work=False)
        self.panes = [os.path.join(pane_path, "sub")]
        here, _ = self.wt("here", work=False)
        prot, _ = self.wt("prot", work=False)

        rows, out = self.run_purge(cwd=here, protect=[prot])
        want = {
            "repo": ("keep", "main worktree"),
            "here": ("keep", "current directory"),
            "prot": ("keep", "protected checkout"),
            "run-ref": ("keep", "referenced by run record ben-1.json"),
            "42-claimed": ("keep", "referenced by claim builder-issue42"),
            "pane": ("keep", "referenced by tmux pane"),
            "dirty": ("keep", "uncommitted changes (1 paths)"),
            "open-pr": ("keep", "PR open"),
            "mismatch": ("keep", "head differs from every merged or closed PR head"),
            "no-pr": ("keep", "no PR and head not in origin/main"),
            "moved": ("keep", "PR #6 merged, remote branch moved"),
            "merged-in-main": ("remove", "head in origin/main"),
            "squash-gone": ("remove", "PR #1 merged, remote branch gone"),
            "squash-match": ("remove", "PR #2 merged, remote branch matches"),
            "scratch-only": ("remove", "PR #3 closed, remote branch gone"),
        }
        self.assertEqual(rows, want)
        self.assertIn("dry run: 4 remove, 11 keep", out)
        self.assertIn("1 keep: referenced by run record\n", out)
        self.assertTrue(os.path.isdir(os.path.join(self.d, "wt", "squash-gone")))

    def test_apply_removes_only_remove_rows_and_keeps_branches(self):
        _, gone = self.wt("gone")
        self.pr("gone", gone, "MERGED")
        scratch, head = self.wt("scratch")
        self.pr("scratch", head, "MERGED")
        os.makedirs(os.path.join(scratch, ".crew"))
        open(os.path.join(scratch, ".crew", "note"), "w").close()
        keep, _ = self.wt("keep")

        rows, out = self.run_purge(apply=True)
        self.assertFalse(os.path.exists(os.path.join(self.d, "wt", "gone")))
        self.assertFalse(os.path.exists(scratch))
        self.assertTrue(os.path.isdir(keep))
        self.assertIn("removed %s" % os.path.join(self.d, "wt", "gone"), out)
        self.assertIn("removed 2, kept 2", out)
        branches = sh(self.repo, "branch", "--format=%(refname:short)").split()
        self.assertEqual(sorted(branches), ["b/gone", "b/keep", "b/scratch", "main"])
        listed = sh(self.repo, "worktree", "list", "--porcelain")
        self.assertNotIn("/wt/gone", listed)

    def test_failed_lookup_keeps(self):
        self.wt("x")

        def boom(*a):
            raise RuntimeError("offline")
        out = io.StringIO()
        wp.run(self.repo, self.state, [], "main", False, self.d, lookup=boom, panes=lambda: [], out=out)
        self.assertIn("keep\tPR lookup failed: offline", out.getvalue())


if __name__ == "__main__":
    unittest.main()
