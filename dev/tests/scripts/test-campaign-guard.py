#!/usr/bin/env python3
"""Fixture test for scripts/campaign-guard.py (offline, temp dirs only).

Covers the manifest pins, every production-target refusal (repo, session, nested roots, placeholder, out path),
pin drift (profile edit, source moved) and the outside-sandbox sentinel check. Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("campaign_guard", os.path.join(HERE, "campaign-guard.py"))
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

PROFILE = """[repo]
owner = "%s"
name = "%s"
default_branch = "main"

[runtime]
name = "tmux"

[paths]
state_dir = "%s/state"
worktree_root = "%s/wt"
live_dir = "%s/live"
"""


class CampaignGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = os.path.realpath(self.tmp.name)
        self.prod = self.profile("prod.toml", "mw-ding", "eng-crew", self.d + "/prod")
        self.sand = self.profile("sand.toml", "acme", "sandbox", self.d + "/sand")
        self.src = os.path.join(self.d, "src")
        subprocess.run(["git", "init", "-q", self.src], check=True)
        self.commit()
        self.sentinel = os.path.join(self.d, "outside.txt")
        self.write(self.sentinel, "untouched\n")
        os.makedirs(self.d + "/sand/state")
        self.out = os.path.join(self.d, "sand/state/m.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def read(self, path):
        with open(path) as fh:
            return fh.read()

    def profile(self, name, owner, repo, root, extra=""):
        path = os.path.join(self.d, name)
        self.write(path, PROFILE % (owner, repo, root, root, root) + extra)
        return path

    def commit(self):
        subprocess.run(["git", "-C", self.src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "c"], check=True)

    def run_cmd(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = cg.main(list(argv))
        return code, out.getvalue()

    def manifest(self, sandbox=None, out=None):
        return self.run_cmd("manifest", "--sandbox", sandbox or self.sand, "--production", self.prod,
                            "--source", self.src, "--release", "v4.0.0", "--run-id", "r1", "--scenario", "A01",
                            "--sentinel", self.sentinel, "--out", out or self.out)

    def test_manifest_pins_and_check_passes(self):
        code, out = self.manifest()
        self.assertEqual(code, 0, out)
        m = json.loads(self.read(self.out))
        self.assertEqual(m["repo"], "acme/sandbox")
        self.assertEqual(m["session"], "crew-acme-sandbox")
        self.assertEqual(m["release"], "v4.0.0")
        self.assertEqual(m["scenarios"], ["A01"])
        self.assertEqual(len(m["source"]["sha"]), 40)
        self.assertEqual(m["roots"]["state_dir"], self.d + "/sand/state")
        self.assertEqual(self.run_cmd("check", self.out), (0, "ok: run r1 targets acme/sandbox (session "
                                                              "crew-acme-sandbox)\n"))

    def assert_refused(self, sandbox, reason):
        code, out = self.manifest(sandbox)
        self.assertEqual(code, 2)
        self.assertIn("refused: " + reason, out)
        self.assertFalse(os.path.exists(self.out), "a refused manifest is never written")

    def test_production_repo_refused(self):
        self.assert_refused(self.profile("s.toml", "mw-ding", "eng-crew", self.d + "/sand"), "repo:")

    def test_production_session_refused(self):
        extra = '\n[runtime.options]\nsession = "crew-mw-ding-eng-crew"\n'
        self.assert_refused(self.profile("s.toml", "acme", "sandbox", self.d + "/sand", extra), "session:")

    def test_nested_state_refused(self):
        self.assert_refused(self.profile("s.toml", "acme", "sandbox", self.d + "/prod/state/x"), "paths.state_dir:")

    def test_placeholder_refused(self):
        path = self.profile("s.toml", "acme", "sandbox", self.d + "/sand")
        self.write(path, self.read(path).replace(self.d + "/sand/live", "<live-dir>"))
        self.assert_refused(path, "paths.live_dir: still the placeholder")

    def test_out_outside_sandbox_refused(self):
        prod = self.d + "/prod/state/record.json"
        os.makedirs(os.path.dirname(prod))
        self.write(prod, "production record\n")
        link = self.d + "/sand/state/link.json"
        os.symlink(prod, link)
        for out in (prod, link, self.d + "/m.json"):
            code, text = self.manifest(out=out)
            self.assertEqual(code, 2)
            self.assertIn("refused: out:", text)
        self.assertEqual(self.read(prod), "production record\n")
        self.assertFalse(os.path.exists(self.d + "/m.json"))

    def test_drift_refused_at_check(self):
        self.assertEqual(self.manifest()[0], 0)
        self.commit()
        code, out = self.run_cmd("check", self.out)
        self.assertEqual(code, 2)
        self.assertIn("refused: source:", out)
        self.write(self.sand, self.read(self.sand).replace("acme", "mw-ding").replace("sandbox", "eng-crew"))
        code, out = self.run_cmd("check", self.out)
        self.assertIn("refused: repo:", out)
        self.assertIn("refused: profile:", out)
        self.assertIn("refused: target:", out)

    def test_sentinel(self):
        self.assertEqual(self.manifest()[0], 0)
        self.assertEqual(self.run_cmd("sentinel", self.out), (0, "sentinel unchanged: %s\n" % self.sentinel))
        self.write(self.sentinel, "touched\n")
        self.assertEqual(self.run_cmd("sentinel", self.out)[0], 1)
        os.remove(self.sentinel)
        self.assertEqual(self.run_cmd("sentinel", self.out)[0], 1)


if __name__ == "__main__":
    unittest.main()
