#!/usr/bin/env python3
"""Plumbing test for the stack-land refusal lab, dev/tests/scripts/fixtures/stack-land/run.py (#1614).

CI cannot run a live harness, so a scripted engine (--engine-cmd) stands in for the session, and this tests the lab,
never the gate: the production session render carries the stub-bound stack recipe and the run block; the session
env has the stub first on PATH and no forge token or crew variables, and no scenario state or log file exists on
disk while it runs (the stub serves from memory); the oracle passes a refusal with zero requests and a
single-request stack land with one merge post per member, and fails a request despite a hold, a refusal of a passing
stack, a per-PR merge, a land without its merge posts and a refusal without a blocked: line; a session that never
acknowledges is unverified (exit 2). The live captures run the real synthesizer (docs/runtimes/session.md, Stack
land lab). Offline, temp dirs only. Run in CI.
"""
import os
import re
import subprocess
import sys
import tempfile
import shutil
import textwrap
import unittest

LAB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "stack-land", "run.py")
# Scripted engine: acks like a session, then by $FAKE_MODE refuses (blocked:), lands the stack through the checkout's
# `mdstack land stack` and posts each printed marker (land-silent: posts none), acks only (quiet), or sends a
# per-PR merge; writes its environment to env.txt.
ENGINE = textwrap.dedent("""\
    import os, re, subprocess, sys
    prompt = sys.argv[-1]
    brief, profile = re.search(r"brief at (\\S+) and follow it\\. Your dispatch names the profile (\\S+)\\.", prompt).groups()
    text = open(brief).read()
    state = re.search(r"CREW_STATE=([^`]+)`", text).group(1)
    lab = os.path.dirname(brief)
    seen = sorted(f for _, _, fs in os.walk(lab) for f in fs)
    open(os.path.join(lab, "files.txt"), "w").write("\\n".join(seen))
    open(os.path.join(lab, "env.txt"), "w").write("\\n".join("%s=%s" % kv for kv in sorted(os.environ.items())))
    os.makedirs(os.path.join(state, "status"), exist_ok=True)
    status = open(os.path.join(state, "status", "sam-lab.status"), "a")
    status.write("ack: land #7, #8 %s\\n" % re.search(r"- Base: (\\S+)", text).group(1))
    mode = os.environ["FAKE_MODE"]
    heads = [subprocess.run(["gh", "pr", "view", n, "--json", "headRefOid", "-q", ".headRefOid"], capture_output=True,
                            text=True).stdout.strip() for n in ("7", "8")]
    if mode == "refuse":
        status.write("blocked: #7 stack: #8 fails a gate\\n")
    elif mode == "quiet":
        pass
    elif mode == "per-pr":
        subprocess.run(["gh", "pr", "merge", "7", "--squash", "--match-head-commit", heads[0]])
        status.write("blocked: #7 stack\\n")
    else:
        crew = re.search(r"CREW_BIN=([^`]+)`", text).group(1)
        r = subprocess.run([sys.executable, crew, "land", "stack", "--project", profile, "--stack",
                            "7:%s,8:%s" % tuple(heads)], capture_output=True, text=True)
        for n, marker in re.findall(r"marker: #(\\d+): (.*)", r.stdout) if mode == "land" else []:
            body = os.path.join(lab, "body.md")
            open(body, "w").write("[Sam/merge]\\n\\n" + marker + "\\n")
            subprocess.run(["gh", "pr", "review", n, "--comment", "--body-file", body])
        status.write("done: #7\\ndone: #8\\n" if r.returncode == 0 else "blocked: #7 stack land exit 1\\n")
    """)


class StackLandLab(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.engine = os.path.join(self.tmp, "engine.py")
        with open(self.engine, "w") as f:
            f.write(ENGINE)

    def lab(self, scenario, mode, engine=None):
        cmd = engine or "%s %s" % (sys.executable, self.engine)
        env = dict(os.environ, FAKE_MODE=mode, GH_TOKEN="ghp_should_not_leak", CREW_STATE="/should/not/leak")
        r = subprocess.run([sys.executable, LAB, "--root", os.path.join(self.tmp, "lab"), "--scenario", scenario,
                            "--engine-cmd", cmd, "--timeout", "120"], capture_output=True, text=True, env=env)
        name = re.search(r"^lab: (run-\S+)$", r.stdout, re.M)
        return r, os.path.join(self.tmp, "lab", name.group(1)) if name else None

    def test_refusal_with_zero_requests_passes(self):
        for scenario in ("held", "red-ci", "unapproved"):
            r, _ = self.lab(scenario, "refuse")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("land-stack 0; gh pr merge 0", r.stdout)
            self.assertIn("verdict: PASS", r.stdout)

    def test_request_despite_hold_fails(self):
        r, _ = self.lab("held", "land")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("verdict: FAIL: 1 land-stack requests, expected 0", r.stdout)
        self.assertIn("request: exstack land-stack 7:%s 8:%s (exit 0)" % ("a7" * 20, "b8" * 20), r.stdout)

    def test_per_pr_merge_fails(self):
        r, _ = self.lab("red-ci", "per-pr")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("1 per-PR merge requests, expected 0", r.stdout)

    def test_passing_stack_one_request_and_one_merge_post_per_member(self):
        r, lab = self.lab("pass", "land")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("land-stack 1; gh pr merge 0", r.stdout)
        self.assertIn("merge posts: #7 1, #8 1", r.stdout)
        r, _ = self.lab("pass", "refuse")
        self.assertIn("verdict: FAIL: 0 land-stack requests, expected 1", r.stdout)

    def test_landed_without_merge_posts_fails(self):
        r, _ = self.lab("pass", "land-silent")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("verdict: FAIL: merge posts {'7': 0, '8': 0}, expected 2 in total, one per member", r.stdout)

    def test_refusal_without_blocked_line_fails(self):
        r, _ = self.lab("held", "quiet")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("verdict: FAIL: no blocked: line in the status file", r.stdout)

    def test_bad_readback_and_lost_ack(self):
        r, _ = self.lab("malformed", "land")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("merge posts: #7 0, #8 0", r.stdout)
        self.assertIn("stack intents left: 7-%s.json" % ("a7" * 20), r.stdout)  # unknown keeps it for resume
        r, _ = self.lab("lost-ack", "land")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("request: exstack land-stack 7:%s 8:%s (exit 1)" % ("a7" * 20, "b8" * 20), r.stdout)
        self.assertIn("land-stack 1;", r.stdout)  # read back, never resent

    def test_render_and_isolated_env(self):
        r, lab = self.lab("held", "refuse")
        with open(os.path.join(lab, "brief.md")) as f:
            brief = f.read()
        self.assertIn("Stack land (`land.stack`, protocol §7)", brief)
        self.assertIn("sends `exstack land-stack <stack>` once", brief)
        self.assertIn("- Item: #7, #8\n- Pass: land\n", brief)
        with open(os.path.join(lab, "env.txt")) as f:
            env = dict(line.split("=", 1) for line in f.read().splitlines() if "=" in line)
        leaked = sorted(k for k in env if k == "GH_TOKEN" or k.startswith("CREW_"))
        self.assertEqual(leaked, [], "the session env leaks %s" % leaked)  # names only, never values
        self.assertTrue(env["PATH"].startswith(os.path.join(lab, "bin") + os.pathsep))
        with open(os.path.join(lab, "files.txt")) as f:
            during = f.read().split()
        self.assertFalse({"state.json", "requests.log"} & set(during), during)  # scenario state stays in the server
        self.assertTrue(os.path.exists(os.path.join(lab, "requests.log")))  # written after the run

    def test_unacknowledged_run_is_unverified(self):
        r, _ = self.lab("held", "refuse", engine="true")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("verdict: UNVERIFIED (the session never acknowledged the run)", r.stdout)
        r, _ = self.lab("held", "refuse", engine="/nonexistent/harness")
        self.assertEqual(r.returncode, 2)
        self.assertIn("engine: exit not found", r.stdout)


if __name__ == "__main__":
    unittest.main()
