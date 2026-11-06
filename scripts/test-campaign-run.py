#!/usr/bin/env python3
"""Fixture test for scripts/campaign-run.py (offline, temp dirs only).

Covers scenario selection, the five distinct statuses, the per-step guard recheck, the command exit captured apart from the capture, explicit
completion waits (matched and deadline), the {source} placeholder and stub env, the guard refusal, a seeded rerun reproducing events and failure, and the
decoy sentinel failing a run whose step reaches an inherited TMUX (#817; throwaway sockets only). Run in CI.
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


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cg, cr = load("campaign_guard", "campaign-guard.py"), load("campaign_run", "campaign-run.py")

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

SCENARIOS = {
    "A01": {"steps": [{"name": "emit", "run": "echo \"$CAMPAIGN_SEED $CREW_STATE\" > {state_dir}/a01.status &"},
                      {"name": "done", "wait": "{state_dir}/a01.status", "match": "^\\d+ $", "deadline": 5}]},
    "A02": {"steps": [{"name": "ok", "run": "echo out; echo err >&2"},
                      {"name": "bad", "run": "echo partial; exit 3"}, {"name": "never", "run": "true"}]},
    "A03": {"requires": ["no-such-tool-784"], "steps": [{"name": "x", "run": "true"}]},
    "A04": {"limitation": "level b needs an owner sandbox repo", "steps": []},
    "A05": {"steps": [{"name": "hang", "wait": "{state_dir}/never", "match": "done", "deadline": 0.2}]},
}


class CampaignRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = os.path.realpath(self.tmp.name)
        prof = {}
        for name, owner, repo in (("prod", "mw-ding", "eng-crew"), ("sand", "acme", "sandbox")):
            prof[name] = os.path.join(self.d, name + ".toml")
            self.write(prof[name], PROFILE % ((owner, repo) + (self.d + "/" + name,) * 3))
        src = os.path.join(self.d, "src")
        subprocess.run(["git", "init", "-q", src], check=True)
        subprocess.run(["git", "-C", src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "c"], check=True)
        self.write(os.path.join(self.d, "outside.txt"), "untouched\n")
        os.makedirs(self.d + "/sand/state")
        self.manifest = self.d + "/sand/state/m.json"
        argv = ["manifest", "--sandbox", prof["sand"], "--production", prof["prod"], "--source", src,
                "--release", "v4.0.0", "--run-id", "r1", "--sentinel", self.d + "/outside.txt", "--out",
                self.manifest]
        for sid in ("A01", "A02", "A03", "A04", "A05", "A06"):
            argv += ["--scenario", sid]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cg.main(argv), 0)
        self.sdir = os.path.join(self.d, "scenarios")
        os.makedirs(self.sdir)
        for sid, sc in SCENARIOS.items():
            self.write(os.path.join(self.sdir, sid + ".json"), json.dumps(dict(sc, id=sid)))
        self.out = self.d + "/sand/state/results.json"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def run_cmd(self, *extra, out=None):
        os.environ["CREW_STATE"] = "/production/state"
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                code = cr.main([self.manifest, "--scenarios", self.sdir, "--out", out or self.out] + list(extra))
        finally:
            del os.environ["CREW_STATE"]
        return code, buf.getvalue()

    def results(self, path=None):
        with open(path or self.out) as fh:
            doc = json.load(fh)
        return doc, {r["id"]: r for r in doc["results"]}

    def test_statuses_distinct_and_exit_captured(self):
        code, out = self.run_cmd("--seed", "7")
        self.assertEqual(code, 1, out)
        doc, res = self.results()
        self.assertEqual({k: r["status"] for k, r in res.items()},
                         {"A01": "PASS", "A02": "FAIL", "A03": "BLOCKED", "A04": "LIMITATION", "A05": "FAIL",
                          "A06": "NOT RUN"})
        ok, bad = res["A02"]["steps"]
        self.assertEqual((ok["capture"], ok["exit"], ok["stdout"], ok["stderr"]), ("ok", 0, "out\n", "err\n"))
        self.assertEqual((bad["capture"], bad["exit"], bad["want"], bad["stdout"]), ("ok", 3, 0, "partial\n"))
        self.assertEqual(len(res["A02"]["steps"]), 2, "a failed step stops the scenario")
        self.assertEqual(res["A05"]["events"], ["wait hang: deadline"])
        self.assertIn("missing tool: no-such-tool-784", res["A03"]["reason"])
        with open(self.d + "/sand/state/a01.status") as fh:
            self.assertEqual(fh.read(), "7 \n", "child got CAMPAIGN_SEED and no inherited CREW_STATE")

    def test_selection_marks_rest_not_run(self):
        code, out = self.run_cmd("--scenario", "A01", "--seed", "1")
        self.assertEqual(code, 1, "NOT RUN is never a pass")
        doc, res = self.results()
        self.assertEqual(doc["selected"], ["A01"])
        self.assertEqual(res["A01"]["status"], "PASS")
        self.assertEqual(res["A02"], {"id": "A02", "status": "NOT RUN", "reason": "not selected", "events": []})
        self.assertEqual(self.run_cmd("--scenario", "A01")[0], 1)
        self.assertEqual(self.run_cmd("--scenario", "A99")[0], 2)

    def test_source_and_stub_env_reach_steps(self):
        st = self.d + "/sand/state"
        spec = {"steps": [{"name": "env", "run": 'git -C {source} rev-parse HEAD > {state_dir}/src.txt; '
                           'echo "$CAMPAIGN_GH_DIR $CAMPAIGN_STUB_LOG $CAMPAIGN_GH_LOG" > {state_dir}/env.txt'}]}
        self.write(os.path.join(self.sdir, "A01.json"), json.dumps(spec))
        self.assertEqual(self.run_cmd("--scenario", "A01")[0], 1, "the other scenarios stay NOT RUN")
        self.assertEqual(self.results()[1]["A01"]["status"], "PASS")
        with open(st + "/src.txt") as fh, open(self.manifest) as mf, open(st + "/env.txt") as env:
            self.assertEqual(fh.read().strip(), json.load(mf)["source"]["sha"])
            self.assertEqual(env.read().split(), [st + "/gh", st + "/stub.log", st + "/gh.log"])

    def test_all_pass_exits_zero(self):
        passing = {"steps": [{"name": "ok", "run": "exit 4", "exit": 4}]}
        for sid in ("A01", "A02", "A03", "A04", "A05", "A06"):
            self.write(os.path.join(self.sdir, sid + ".json"), json.dumps(passing))
        self.assertEqual(self.run_cmd()[0], 0)

    def test_rerun_seed_reproduces_events_and_failure(self):
        self.run_cmd("--seed", "42")
        first = self.d + "/sand/state/first.json"
        os.replace(self.out, first)
        os.remove(self.d + "/sand/state/a01.status")
        self.assertEqual(self.run_cmd("--rerun", first)[0], 1)
        a, b = self.results(first)[0], self.results()[0]
        self.assertEqual((a["seed"], a["order"]), (b["seed"], b["order"]))
        strip = [{k: r.get(k) for k in ("id", "status", "reason", "events")} for r in a["results"]]
        self.assertEqual(strip, [{k: r.get(k) for k in ("id", "status", "reason", "events")} for r in b["results"]])
        self.assertEqual(self.results()[1]["A02"]["reason"], "run bad: exit 3 (want 0)")

    def test_guard_rechecked_before_each_run_step(self):
        drift = {"steps": [{"name": "drift", "run": "printf '\\n' >> \"$CREW_PROJECT\""},
                           {"name": "later", "run": "echo ran > {state_dir}/after-drift"}]}
        self.write(os.path.join(self.sdir, "A01.json"), json.dumps(drift))
        code, out = self.run_cmd("--scenario", "A01", "--scenario", "A02", "--seed", "0")
        self.assertEqual(code, 2, out)
        self.assertFalse(os.path.exists(self.d + "/sand/state/after-drift"), "no mutation after a refusal")
        doc, res = self.results()
        self.assertEqual(res["A01"]["status"], "BLOCKED")
        self.assertIn("refused: profile:", res["A01"]["reason"])
        self.assertEqual(res["A01"]["events"], ["run drift: exit 0 (want 0)"])
        self.assertEqual(doc["order"], ["A01", "A02"])
        self.assertEqual(res["A02"]["status"], "NOT RUN")
        self.assertEqual(res["A02"]["reason"], "run stopped: guard refused")

    def test_guard_refusal_writes_nothing(self):
        for out in (self.d + "/results.json", self.d + "/prod/state/results.json"):
            code, text = self.run_cmd(out=out)
            self.assertEqual(code, 2)
            self.assertIn("refused: out:", text)
            self.assertFalse(os.path.exists(out))
        with open(self.d + "/sand.toml", "a") as fh:
            fh.write("\n")
        code, text = self.run_cmd()
        self.assertEqual(code, 2)
        self.assertIn("refused: profile:", text)
        self.assertFalse(os.path.exists(self.out))

    @unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
    def test_decoy_fails_a_step_that_reaches_inherited_tmux(self):
        kill = {"steps": [{"name": "cleanup", "run": "tmux kill-server; true"}]}
        self.write(os.path.join(self.sdir, "A01.json"), json.dumps(kill))
        self.write(os.path.join(self.sdir, "A02.json"), json.dumps({"steps": [{"name": "ok", "run": "true"}]}))
        os.environ["TMUX_TMPDIR"] = os.path.join(self.d, "no-server")  # a stripped bare call finds no server
        os.makedirs(os.environ["TMUX_TMPDIR"])
        orig = cr.scenario_env
        try:
            self.run_cmd("--scenario", "A01", "--scenario", "A02", "--seed", "0")
            self.assertEqual([self.results()[1][s]["status"] for s in ("A01", "A02")], ["PASS", "PASS"])
            cr.scenario_env = lambda m, seed, base: dict(orig(m, seed, base), TMUX=base["TMUX"])  # the regression
            code, out = self.run_cmd("--scenario", "A01", "--scenario", "A02", "--seed", "0")
        finally:
            cr.scenario_env = orig
            del os.environ["TMUX_TMPDIR"]
        self.assertEqual(code, 1, out)
        res = self.results()[1]
        self.assertEqual((res["A01"]["status"], res["A01"]["reason"]),
                         ("FAIL", "decoy: a tmux server outside the sandbox was killed"))
        self.assertEqual((res["A02"]["status"], res["A02"]["reason"]), ("NOT RUN", "run stopped: decoy killed"))


if __name__ == "__main__":
    unittest.main()
