#!/usr/bin/env python3
"""Fixture test for scripts/campaign-sandbox.py (offline, temp dirs only).

Covers level-a setup (bare origin, seeded clone, isolated profile, control item and fixtures, guarded manifest), the
refusals before any write (non-empty root, root overlapping production), teardown recording retained work (including
an unpushed branch that is not checked out) and the sentinel, `--remove` only without retained work, the
session-targeted tmux kill, and the print-only level-b forge plan.
Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("campaign_sandbox", os.path.join(HERE, "campaign-sandbox.py"))
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

PROD = """[repo]
owner = "mw-ding"
name = "eng-crew"
default_branch = "main"

[runtime]
name = "tmux"

[paths]
state_dir = "{d}/prod/state"
worktree_root = "{d}/prod/wt"
live_dir = "{d}/prod/live"
"""


class CampaignSandboxTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = os.path.realpath(self.tmp.name)
        self.prod = os.path.join(self.d, "prod.toml")
        self.write(self.prod, PROD.format(d=self.d))
        self.src = os.path.join(self.d, "src")
        subprocess.run(["git", "init", "-q", self.src], check=True)
        cs.git("commit", "-q", "--allow-empty", "-m", "c", cwd=self.src)
        self.sentinel = os.path.join(self.d, "outside.txt")
        self.write(self.sentinel, "untouched\n")
        self.root = os.path.join(self.d, "sandbox")
        self.manifest = os.path.join(self.root, "state", "manifest.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def read(self, path):
        with open(path) as fh:
            return fh.read()

    def run_cmd(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = cs.main(list(argv))
        return code, out.getvalue()

    def setup_sandbox(self, root=None):
        return self.run_cmd("setup", "--root", root or self.root, "--run-id", "r785", "--production", self.prod,
                            "--source", self.src, "--release", "v4.0.0", "--sentinel", self.sentinel,
                            "--scenario", "A01")

    def test_setup_builds_isolated_level_a_sandbox(self):
        code, out = self.setup_sandbox()
        self.assertEqual(code, 0, out)
        self.assertIn("ok: run r785 targets campaign/sandbox-r785 (session crew-campaign-r785)", out)
        m = json.loads(self.read(self.manifest))
        self.assertEqual(m["roots"], {"state_dir": self.root + "/state", "worktree_root": self.root + "/wt",
                                      "live_dir": self.root + "/live"})
        self.assertEqual(m["scenarios"], ["A01"])
        log = cs.git("--git-dir", os.path.join(self.root, "origin.git"), "log", "--format=%s", "main")
        self.assertEqual(log, "campaign sandbox seed\n")
        rec = json.loads(self.read(os.path.join(self.root, "state", "sandbox.json")))
        self.assertIn("crew:ready", rec["labels"])
        self.assertIn("integration:finding", rec["labels"])
        self.assertEqual(rec["control_item"]["labels"], ["integration:run"])
        self.assertEqual(subprocess.run(["sh", os.path.join(self.root, "repo", "ci.sh")]).returncode, 0)
        self.assertEqual(subprocess.run(["sh", os.path.join(self.root, "repo", "ci.sh")],
                                        env=dict(os.environ, CI_RESULT="1")).returncode, 1)

    def test_setup_refuses_before_any_write(self):
        os.makedirs(self.root)
        self.write(os.path.join(self.root, "keep.txt"), "x")
        code, out = self.setup_sandbox()
        self.assertEqual((code, out.strip()), (2, "refused: root: %s exists and is not empty" % self.root))
        self.assertEqual(os.listdir(self.root), ["keep.txt"])
        inside = os.path.join(self.d, "prod", "state", "sb")
        code, out = self.setup_sandbox(inside)
        self.assertEqual((code, out.strip()), (2, "refused: root: %s overlaps a production root" % inside))
        self.assertFalse(os.path.exists(inside))

    def test_teardown_keeps_retained_work_and_checks_sentinel(self):
        self.setup_sandbox()
        repo = os.path.join(self.root, "repo")
        wt = os.path.join(self.root, "wt", "builder-1")
        cs.git("worktree", "add", "-q", "-b", "builder/1-x", wt, cwd=repo)
        cs.git("commit", "-q", "--allow-empty", "-m", "unlanded", cwd=wt)
        self.write(os.path.join(repo, "dirty.txt"), "x")
        code, out = self.run_cmd("teardown", self.manifest, "--remove")
        self.assertEqual(code, 0, out)
        self.assertIn("sentinel unchanged", out)
        self.assertIn("kept: %s" % self.root, out)
        rec = json.loads(self.read(os.path.join(self.root, "state", "cleanup.json")))
        self.assertEqual([r["path"] for r in rec["retained"]], [repo, wt])
        self.assertEqual(rec["retained"][0]["dirty"], ["?? dirty.txt"])
        self.assertTrue(rec["retained"][1]["unpushed"][0].endswith(" unlanded"))
        self.assertTrue(rec["sentinel_unchanged"])
        self.assertEqual(self.read(self.sentinel), "untouched\n")

    def test_teardown_keeps_unpushed_branch_not_checked_out(self):
        self.setup_sandbox()
        repo = os.path.join(self.root, "repo")
        cs.git("checkout", "-q", "-b", "builder/1-unlanded", cwd=repo)
        cs.git("commit", "-q", "--allow-empty", "-m", "unlanded work", cwd=repo)
        cs.git("checkout", "-q", "main", cwd=repo)
        code, out = self.run_cmd("teardown", self.manifest, "--remove")
        self.assertEqual(code, 0, out)
        self.assertIn("kept: %s" % self.root, out)
        rec = json.loads(self.read(os.path.join(self.root, "state", "cleanup.json")))
        self.assertEqual([r["path"] for r in rec["retained"]], [repo])
        self.assertEqual(rec["retained"][0]["dirty"], [])
        self.assertTrue(rec["retained"][0]["unpushed"][0].endswith(" unlanded work"))

    def test_teardown_remove_clean_sandbox_and_changed_sentinel(self):
        self.setup_sandbox()
        self.write(self.sentinel, "changed\n")
        code, out = self.run_cmd("teardown", self.manifest, "--remove")
        self.assertEqual(code, 1, out)
        self.assertIn("sentinel CHANGED", out)
        self.assertTrue(os.path.isdir(self.root))
        self.write(self.sentinel, "untouched\n")
        code, out = self.run_cmd("teardown", self.manifest, "--remove")
        self.assertEqual(code, 0, out)
        self.assertIn("removed: %s" % self.root, out)
        self.assertFalse(os.path.exists(self.root))

    def test_teardown_refused_when_manifest_drifted(self):
        self.setup_sandbox()
        with open(os.path.join(self.root, "crew.toml"), "a") as fh:
            fh.write("# edit\n")
        code, out = self.run_cmd("teardown", self.manifest, "--remove")
        self.assertEqual(code, 2)
        self.assertIn("refused: profile:", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "state", "cleanup.json")))

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_teardown_kills_only_the_sandbox_session(self):
        self.setup_sandbox()
        other = "crew-campaign-r785-other"
        for name in ("crew-campaign-r785", other):
            subprocess.run(["tmux", "new-session", "-d", "-s", name], check=True)
        try:
            code, out = self.run_cmd("teardown", self.manifest)
            self.assertEqual(code, 0, out)
            rec = json.loads(self.read(os.path.join(self.root, "state", "cleanup.json")))
            self.assertTrue(rec["session_killed"])
            self.assertNotEqual(subprocess.run(["tmux", "has-session", "-t", "=crew-campaign-r785"],
                                             capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(["tmux", "has-session", "-t", "=" + other]).returncode, 0)
        finally:
            subprocess.run(["tmux", "kill-session", "-t", "=" + other], capture_output=True)

    def test_plan_forge_prints_only_and_refuses_production(self):
        code, out = self.run_cmd("plan-forge", "--repo", "acme/m25-sandbox", "--production", self.prod)
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertEqual(lines[0], "plan: gh repo create acme/m25-sandbox --private")
        self.assertIn("plan: gh label create integration:run -R acme/m25-sandbox", lines)
        self.assertEqual(sum(line.startswith("plan: gh label create crew:") for line in lines), 10)
        self.assertTrue(lines[-1].startswith("level b: blocked, owner account access"))
        code, out = self.run_cmd("plan-forge", "--repo", "mw-ding/eng-crew", "--production", self.prod)
        self.assertEqual((code, out.strip()), (2, "refused: repo: mw-ding/eng-crew is the production repo"))


if __name__ == "__main__":
    unittest.main()
