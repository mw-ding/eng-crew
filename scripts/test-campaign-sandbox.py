#!/usr/bin/env python3
"""Fixture test for scripts/campaign-sandbox.py (offline, temp dirs only).

Covers level-a setup (bare origin, seeded clone, isolated profile, control item and fixtures, guarded manifest), the
refusals before any write (non-empty root, root overlapping production), teardown recording retained work (including
an unpushed branch that is not checked out) and the sentinel, `--remove` only without retained work, the
session-targeted tmux kill on the sandbox socket, the tmux shim's socket pin and refusals, a scenario's bare
`tmux kill-server` under an inherited decoy TMUX (#817), the fake forge's `--label` answers, per-state `issue list`
answers, kept `--body-file -` bodies, the `gh api` forge stub (kept posts, a lost post, the post probe, a label
delete) and the print-only level-b forge plan. tmux tests use throwaway sockets only. Run in CI.
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
spec = importlib.util.spec_from_file_location("campaign_run", os.path.join(HERE, "campaign-run.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

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
        self.tmp = tempfile.TemporaryDirectory(dir="/tmp" if os.path.isdir("/tmp") else None)  # short socket paths
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

    def test_setup_profile_in_repo_and_engine_stubs(self):
        self.setup_sandbox()
        repo, bindir = os.path.join(self.root, "repo"), os.path.join(self.root, "state", "bin")
        self.assertEqual(json.loads(self.read(self.manifest))["profile"]["path"], os.path.join(repo, "crew.toml"))
        self.assertIn('toolchain_bin = "%s"' % bindir, self.read(os.path.join(repo, "crew.toml")))
        self.assertEqual(cs.git("status", "--porcelain", cwd=repo), "", "the profile is git-excluded")
        log, status = os.path.join(self.d, "stub.log"), os.path.join(self.d, "w.status")
        env = dict(os.environ, CAMPAIGN_STUB_LOG=log, CREW_STATUS=status, CREW_ID="builder-2")
        p = subprocess.run([os.path.join(bindir, "claude"), "--model", "m"], input="inbox: id-1\nhello\n",
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.read(status), "ack: id-1\n")
        self.assertIn("got builder-2: hello", self.read(log))
        self.assertEqual(os.path.basename(os.path.realpath(os.path.join(bindir, "exe", "claude"))), "bash")
        gh = subprocess.run([os.path.join(bindir, "gh"), "auth", "token"], capture_output=True, text=True)
        self.assertEqual(gh.stdout.strip(), "gho_campaignstub")
        answers = os.path.join(self.d, "gh")
        os.mkdir(answers)
        self.write(os.path.join(answers, "issue-list.json"), "[1]")
        self.write(os.path.join(answers, "issue-list-label-crew:hold.json"), "[2]")
        env = dict(os.environ, CAMPAIGN_GH_DIR=answers)
        for argv, want in ((["-R", "o/n", "--label", "crew:hold", "--json", "number"], "[2]"),
                           (["-R", "o/n", "--json", "number"], "[1]"), (["--label", "crew:ready"], "[1]")):
            gh = subprocess.run([os.path.join(bindir, "gh"), "issue", "list", *argv], capture_output=True, text=True,
                                env=env)
            self.assertEqual(gh.stdout, want, argv)

    def test_gh_api_stub_keeps_posts_fails_lost_and_probes(self):
        self.setup_sandbox()
        gh, ghdir = os.path.join(self.root, "state", "bin", "gh"), os.path.join(self.d, "gh")
        env = dict(os.environ, CAMPAIGN_GH_DIR=ghdir)
        url = "repos/campaign/sandbox-r785/issues/1/comments"

        def call(*args, body=None):
            p = subprocess.run([gh, "api", *args], input=body, capture_output=True, text=True, env=env)
            return p.returncode, p.stdout

        os.makedirs(ghdir)
        self.assertEqual(call("--paginate", "--slurp", url), (0, "[]\n"), "no api.json: the plain stub answers")
        self.write(os.path.join(ghdir, "api.json"), json.dumps({
            "commits/main": {"sha": "1" * 40}, "fail": 1, "fail_mode": "lost",
            "issues": [{"number": 5, "labels": [{"name": "crew:hold"}, {"name": "x"}]}]}))
        self.write(os.path.join(ghdir, "post-probe"), "echo probed\n")
        self.assertEqual(json.loads(call("repos/campaign/sandbox-r785/commits/main?per_page=1")[1]), {"sha": "1" * 40})
        self.assertEqual(call(url, "-F", "body=@-", body="first")[0], 1, "a lost post fails")
        code, out = call(url, "-F", "body=@-", body="second")
        self.assertEqual((code, json.loads(out)["id"]), (0, 2))
        pages = json.loads(call("--paginate", "--slurp", url)[1])
        self.assertEqual([(c["body"], c["user"]["login"], c["probe"]) for c in pages[0]],
                         [("first", "sandbox-coordinator", "probed"), ("second", "sandbox-coordinator", "probed")])
        self.assertRegex(pages[0][0]["created_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$")
        self.assertEqual(call("-X", "DELETE", "repos/campaign/sandbox-r785/issues/5/labels/crew:hold")[0], 0)
        self.assertEqual(json.loads(call("repos/campaign/sandbox-r785/issues")[1])[0]["labels"], [{"name": "x"}])
        self.assertEqual(call("--paginate", "--slurp", "repos/campaign/sandbox-r785/pulls/9/reviews"), (0, "[[]]\n"))

    def test_gh_stub_answers_list_state_from_its_own_file(self):
        self.setup_sandbox()
        gh, ghdir = os.path.join(self.root, "state", "bin", "gh"), os.path.join(self.d, "gh")
        env = dict(os.environ, CAMPAIGN_GH_DIR=ghdir)
        os.makedirs(ghdir)
        self.write(os.path.join(ghdir, "issue-list.json"), '["any"]')
        self.write(os.path.join(ghdir, "issue-list-closed.json"), '["closed"]')

        def call(*args):
            return subprocess.run([gh, "issue", "list", "-R", "o/r", *args], capture_output=True, text=True,
                                  env=env).stdout.strip()

        self.assertEqual(call("--state", "closed", "--json", "number"), '["closed"]')
        self.assertEqual(call("--state", "open", "--json", "number"), '["any"]', "no per-state file: the list file")
        self.assertEqual(call("--json", "number"), '["any"]')

    def test_gh_stub_keeps_stdin_bodies(self):
        self.setup_sandbox()
        gh, ghdir = os.path.join(self.root, "state", "bin", "gh"), os.path.join(self.d, "gh")
        os.makedirs(ghdir)
        env = dict(os.environ, CAMPAIGN_GH_DIR=ghdir)

        def call(*args, body=""):
            return subprocess.run([gh, *args], input=body, capture_output=True, text=True, env=env).returncode

        self.assertEqual(call("issue", "create", "-R", "o/r", "--title", "t", "--body-file", "-", body="card\n"), 0)
        self.assertEqual(call("issue", "comment", "5", "-R", "o/r", "--body-file", "f.md", body="not kept\n"), 0)
        self.assertEqual(call("issue", "comment", "5", "-R", "o/r", "--body-file", "-", body="again\n"), 0)
        with open(os.path.join(ghdir, "bodies.log")) as f:
            self.assertEqual(f.read(), "--- gh issue create -R o/r --title t --body-file -\ncard\n"
                                       "--- gh issue comment 5 -R o/r --body-file -\nagain\n")

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
        with open(os.path.join(self.root, "repo", "crew.toml"), "a") as fh:
            fh.write("# edit\n")
        code, out = self.run_cmd("teardown", self.manifest, "--remove")
        self.assertEqual(code, 2)
        self.assertIn("refused: profile:", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "state", "cleanup.json")))

    def tmux(self, sock, *args):
        env = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
        return subprocess.run(["tmux", "-f", os.devnull, "-S", sock, *args], capture_output=True, env=env)

    def decoy(self, session="decoy"):
        sock = os.path.join(self.d, "decoy")
        self.assertEqual(self.tmux(sock, "new-session", "-d", "-s", session, "sleep 300").returncode, 0)
        self.addCleanup(self.tmux, sock, "kill-server")
        return sock

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_teardown_kills_only_the_sandbox_session_on_its_socket(self):
        self.setup_sandbox()
        sock = cs.tmux_socket(os.path.join(self.root, "state"))
        self.addCleanup(self.tmux, sock, "kill-server")
        session = "crew-campaign-r785"
        for name in (session, session + "-other"):
            self.assertEqual(self.tmux(sock, "new-session", "-d", "-s", name, "sleep 300").returncode, 0)
        decoy = self.decoy(session)
        os.environ["TMUX"] = decoy + ",0,0"
        try:
            code, out = self.run_cmd("teardown", self.manifest)
        finally:
            del os.environ["TMUX"]
        self.assertEqual(code, 0, out)
        rec = json.loads(self.read(os.path.join(self.root, "state", "cleanup.json")))
        self.assertTrue(rec["session_killed"])
        self.assertNotEqual(self.tmux(sock, "has-session", "-t", "=" + session).returncode, 0)
        self.assertEqual(self.tmux(sock, "has-session", "-t", "=" + session + "-other").returncode, 0)
        self.assertEqual(self.tmux(decoy, "has-session", "-t", "=" + session).returncode, 0, "inherited TMUX ignored")

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_shim_pins_the_sandbox_socket_and_refuses_others(self):
        self.setup_sandbox()
        state = os.path.join(self.root, "state")
        rec = json.loads(self.read(os.path.join(state, "sandbox.json")))
        sock = cs.tmux_socket(state)
        self.assertEqual(rec["tmux"], {"socket": sock, "shim": os.path.join(state, "bin", "tmux")})
        other = os.path.join(self.d, "other")
        for argv in (["-S", other], ["-S/tmp/x"], ["-uS", other], ["-L", "crew", "-S", other], ["-2uLcrew", "-S", other],
                     ["-uS" + other], ["-uf", os.devnull, "-S", other], ["-f", os.devnull, "-uL", "crew", "-S", other]):
            p = subprocess.run([rec["tmux"]["shim"], *argv, "ls"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 2, argv)
            self.assertIn("tmux shim: refused", p.stderr)
        self.addCleanup(self.tmux, sock, "kill-server")
        decoy = self.decoy()
        p = subprocess.run([rec["tmux"]["shim"], "-uS", decoy, "kill-server"], capture_output=True)
        self.assertEqual(p.returncode, 2, "grouped -uS must not reach an outside server")
        self.assertEqual(self.tmux(decoy, "has-session", "-t", "=decoy").returncode, 0)
        env = dict(os.environ, TMUX=decoy + ",0,0")
        p = subprocess.run([rec["tmux"]["shim"], "-S", sock, "new-session", "-d", "-s", "pinned", "sleep 300"],
                           env=env)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.tmux(sock, "has-session", "-t", "=pinned").returncode, 0)
        for argv in (["-L", "crew"], ["-Lcrew"], ["-2uL", "crew"]):  # a crew's own server (#818) stays in the sandbox
            p = subprocess.run([rec["tmux"]["shim"], *argv, "new-session", "-d", "-s", "own" + argv[0], "sleep 300"],
                               env=env, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(self.tmux(sock, "has-session", "-t", "=own" + argv[0]).returncode, 0, argv)

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_scenario_bare_kill_server_stays_in_the_sandbox(self):
        self.setup_sandbox()
        sdir = os.path.join(self.d, "scenarios")
        os.makedirs(sdir)
        steps = [{"name": "start", "run": "tmux new-session -d -s crew-campaign-r785 'sleep 300'"},
                 {"name": "cleanup", "run": "tmux kill-server"},
                 {"name": "gone", "run": "tmux has-session", "exit": 1}]
        self.write(os.path.join(sdir, "A01.json"), json.dumps({"id": "A01", "steps": steps}))
        out = os.path.join(self.root, "state", "results.json")
        self.addCleanup(self.tmux, cs.tmux_socket(os.path.join(self.root, "state")), "kill-server")
        os.environ["TMUX"] = self.decoy() + ",0,0"  # the crew pane's server; the runner adds its own decoy too
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                code = cr.main([self.manifest, "--scenarios", sdir, "--out", out, "--seed", "1"])
        finally:
            del os.environ["TMUX"]
        self.assertEqual(code, 0, buf.getvalue())
        self.assertEqual(self.tmux(os.path.join(self.d, "decoy"), "has-session", "-t", "=decoy").returncode, 0)

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
