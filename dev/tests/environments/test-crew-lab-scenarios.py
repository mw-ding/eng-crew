"""Lab runner scenario tests: the verified client toolkit, the ssh shim, the org profiles and sample branch, the lab
env, refusals, injection confirmation, runner recovery health, label-checked recreate and the scenario report.

Usage: python3 dev/tests/environments/test-crew-lab-scenarios.py

No Docker or SSH: the staged bundle is a minimal release archive, the real ssh is a fake that echoes its argv, and
docker calls go to a stub. The scenarios themselves need the owner's Docker daemon (crew-lab-scenarios.py).
"""
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
LAB = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "environments", "terminal", "remote", "lab")
loader = importlib.machinery.SourceFileLoader("crew_lab_scenarios", os.path.join(LAB, "crew-lab-scenarios.py"))
spec = importlib.util.spec_from_loader("crew_lab_scenarios", loader)
sc = importlib.util.module_from_spec(spec)
loader.exec_module(sc)
TAG = "v7.1.0-lab.1"


def bundle(stage, tag=TAG):
    """A minimal release archive and SHA256SUMS: VERSION, the entry point and the remote module."""
    os.makedirs(stage)
    name = "mdstack-" + tag[1:]
    with tarfile.open(os.path.join(stage, name + ".tar.gz"), "w:gz") as tar:
        for path, text in (("VERSION", tag + "\n"), ("cli/mdstack", ""),
                           ("environments/terminal/remote/crew-remote.py", "")):
            data = text.encode()
            info = tarfile.TarInfo("%s/%s" % (name, path))
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    sha = hashlib.sha256(Path(stage, name + ".tar.gz").read_bytes()).hexdigest()
    Path(stage, "SHA256SUMS").write_text("%s  %s.tar.gz\n" % (sha, name))
    return sha


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(subprocess.run, ["rm", "-rf", self.tmp])
        self.sb = os.path.join(self.tmp, "sb")
        self.repo, self.state = os.path.join(self.sb, "repo"), os.path.join(self.sb, "state")
        os.makedirs(self.repo)
        os.makedirs(self.state)
        Path(self.repo, "crew.toml").write_text('[repo]\nowner = "campaign"\nname = "sandbox-r1"\n')
        git = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t"]
        for argv in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "seed"]):
            subprocess.run(git + argv, check=True, capture_output=True)
        self.stage = os.path.join(self.tmp, "stage")
        sha = bundle(self.stage)
        self.manifest = os.path.join(self.state, "manifest.json")
        self.m = dict(run_id="r1", repo="campaign/sandbox-r1", profile=dict(path=os.path.join(self.repo, "crew.toml")),
                      roots=dict(state_dir=self.state), lab=dict(tag=TAG, run="r1", owner="o1", source_sha=None,
                      endpoint="unix:///d",
                      stage={"mdstack-7.1.0-lab.1.tar.gz": sha}, networks=["n1"],
                      hosts={"lab-a": dict(container="c1", network="n1", port=55022, host_key="k")}))
        self.write()
        patch = mock.patch.object(sc.labd.guard, "refusals", return_value=[])
        patch.start()
        self.addCleanup(patch.stop)
        env = mock.patch.dict(os.environ, dict(GH_TOKEN="ghp_decoy", SSH_AUTH_SOCK="/tmp/agent", CREW_STATE="/live"))
        env.start()
        self.addCleanup(env.stop)

    def write(self):
        Path(self.manifest).write_text(json.dumps(self.m))

    def lab(self):
        return sc.Lab(self.manifest, self.stage, "lab-a")


class PrepareTest(Base):
    def test_prepare_verifies_the_bundle_then_writes_shim_profiles_sample_and_lab_env(self):
        fake = os.path.join(self.tmp, "real-ssh")
        Path(fake).write_text('#!/bin/sh\necho "$@"\n')
        os.chmod(fake, 0o755)
        lab = self.lab()
        with mock.patch.object(sc, "SSH", fake):
            head = lab.prepare()
        d = os.path.join(self.state, "lab")
        self.assertEqual(Path(d, "toolkit", "VERSION").read_text().strip(), TAG)
        shim = os.path.join(d, "bin", "ssh")
        resolve = subprocess.run([shim, "-G", "lab-a"], capture_output=True, text=True).stdout.split()
        self.assertEqual(resolve, ["-F", os.path.join(d, "home", ".ssh", "config"), "-G", "lab-a"])
        hardened = ["-F", "none", "-T", "-o", "BatchMode=yes", "lab-a", "crew-host"]
        self.assertEqual(subprocess.run([shim, *hardened], capture_output=True, text=True).stdout.split(), hardened)
        runner, role = Path(d, "org.toml").read_text(), Path(d, "org-role.toml").read_text()
        self.assertIn('[hosts.lab-a]\nmax_runs = 2\nroot = "~/.mdstack"\nforge = false', runner)
        self.assertNotIn("forge", role)
        self.assertIn('[[placement.rules]]\nrole = "builder"\nneeds = { os = "linux" }', role)
        self.assertEqual(lab.git("rev-parse", "--abbrev-ref", "HEAD"), "lab")
        self.assertEqual(lab.git("rev-parse", "HEAD"), head)
        self.assertEqual(sorted(lab.git("ls-files").split()), [
            "crew.toml", "dev/tests/lab/test-lab.py", "scripts/check-repo.py", "scripts/run-tests.py"])
        self.assertEqual(os.environ["HOME"], os.path.join(d, "home"))
        self.assertTrue(os.environ["PATH"].startswith(os.path.join(d, "bin") + os.pathsep))
        self.assertFalse({"GH_TOKEN", "SSH_AUTH_SOCK", "CREW_STATE"} & set(os.environ))

    def test_a_bundle_the_hosts_did_not_activate_refuses(self):
        self.m["lab"]["stage"] = {"mdstack-7.1.0-lab.1.tar.gz": "0" * 64}
        self.write()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(sc.main([self.manifest, "--stage", self.stage]), 2)
        self.assertRegex(out.getvalue(),
                         r"refused: prepare: bundle [0-9a-f]{64} is not the one the lab hosts activated")
        self.assertFalse(os.path.exists(os.path.join(self.state, "lab", "scenarios.json")))

    def test_no_loopback_host_refuses_before_prepare(self):
        del self.m["lab"]["hosts"]["lab-a"]["port"]
        self.write()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(sc.main([self.manifest, "--stage", self.stage]), 2)
        self.assertIn("refused: lab: no loopback host lab-a recorded", out.getvalue())
        self.assertFalse(os.path.exists(os.path.join(self.state, "lab", "toolkit")))


class FakeLab:
    def __init__(self, replies):
        self.replies, self.events = list(replies), []

    def call(self, verb, **fields):
        self.events.append(verb)
        return self.replies.pop(0)

    def up(self):
        return self.call("version")["result"] == "ok"


class InjectionTest(unittest.TestCase):
    def test_an_injection_that_leaves_ssh_up_fails(self):
        lab, s = FakeLab([dict(result="ok"), dict(result="ok")]), sc.Seen()
        sc.injected(lab, s, "pause", lambda: lab.events.append("inject"), lambda: lab.events.append("lift"))
        self.assertEqual(s.failures, ["pause did not break the SSH path: {'result': 'ok'}"])
        self.assertEqual(lab.events, ["inject", "version", "lift", "version"])

    def test_a_breaking_injection_passes_and_is_lifted_even_when_the_step_fails(self):
        lab, s = FakeLab([dict(result="unreachable"), dict(result="ok")]), sc.Seen()
        self.assertEqual(sc.injected(lab, s, "disconnect", lambda: None, lambda: lab.events.append("lift"),
                                     lambda: "during"), "during")
        self.assertEqual(s.failures, [])
        lab = FakeLab([dict(result="unreachable")])
        with self.assertRaises(RuntimeError):
            sc.injected(lab, s, "disconnect", lambda: None, lambda: lab.events.append("lift"),
                        lambda: (_ for _ in ()).throw(RuntimeError("step")))
        self.assertEqual(lab.events, ["version", "lift"])

    def test_run_line_and_exits_read_only_this_host_and_head(self):
        out = ["mdstack: config x", "runner:lab-a/abc1234-0123456789ab head=" + "a" * 40, "check-repo exit 0",
               "tests exit 1", "exit 1"]
        self.assertEqual(sc.run_line(out, "lab-a", "a" * 40), "abc1234-0123456789ab")
        self.assertIsNone(sc.run_line(out, "lab-b", "a" * 40))
        self.assertIsNone(sc.run_line(out, "lab-a", "b" * 40))
        self.assertEqual(sc.exits(out), [0, 1])


class RunnerTest(unittest.TestCase):
    def lab(self, health, beat_pid):
        lab = mock.Mock(host="lab-a")
        lab.pids.side_effect = [dict(runner=10, sshd=5)] + [dict(runner=11, sshd=5)] * 200
        lab.beat.return_value = dict(pid=beat_pid)
        lab.call.side_effect = [dict(result="ok", runner="up")] * 2 + [dict(result="ok", runner=health)] * 200
        lab.client.return_value = ["runner:lab-a/j head=h", "check-repo exit 0", "tests exit 0", "exit 0"]
        return lab

    def test_a_new_runner_pid_that_never_reports_up_fails_at_the_timeout(self):
        s = sc.Seen()
        with mock.patch.object(sc.time, "sleep"):
            sc.runner(self.lab("down", 11), s)
        self.assertEqual(s.failures, ["the restarted runner never reported up: ['down', 'down', 'down']"])
        self.assertEqual(len(s.obs["health"]), 120)

    def test_a_stale_heartbeat_from_the_killed_runner_fails(self):
        s = sc.Seen()
        with mock.patch.object(sc.time, "sleep"):
            sc.runner(self.lab("up", 10), s)
        self.assertEqual(s.failures, ["the restarted runner never reported up: ['up', 'up', 'up']"])

    def test_a_runner_never_up_before_the_kill_fails_without_killing(self):
        lab, s = self.lab("up", 11), sc.Seen()
        lab.call.side_effect = [dict(result="ok", runner="down")] * 120
        with mock.patch.object(sc.time, "sleep"):
            sc.runner(lab, s)
        self.assertEqual(s.failures, ["the runner was never up before the kill"])
        lab.docker.assert_not_called()

    def test_a_restarted_runner_that_beats_and_reports_up_passes(self):
        s = sc.Seen()
        with mock.patch.object(sc.time, "sleep"):
            sc.runner(self.lab("up", 11), s)
        self.assertEqual(s.failures, [])
        self.assertEqual(s.obs["health"], ["up"])
        self.assertEqual(s.obs["runner_version"], dict(result="ok", runner="up"))


class RecreateTest(Base):
    def test_a_resource_without_the_runs_labels_refuses_with_nothing_removed(self):
        calls = []

        def docker(m, *argv, check=True):
            calls.append(argv)
            labels = {"mdstack.lab.owner": "o1", "mdstack.lab.run": "r1" if argv[1] == "c1" else "other"}
            return json.dumps([{"Config": {"Labels": labels}}] if argv[1] == "c1" else [{"Labels": labels}])
        with mock.patch.object(sc.labd, "docker", docker):
            with self.assertRaisesRegex(RuntimeError, "n1 no longer carries run r1's labels; nothing removed"):
                self.lab().recreate()
        self.assertEqual([a[0] for a in calls], ["inspect", "inspect"])


class ReportTest(Base):
    def test_each_scenario_is_reported_and_any_failure_exits_1(self):
        def good(lab, s):
            s.obs["seen"] = 1

        def bad(lab, s):
            s.check(False, "the client did not fall back locally while pause held")

        def crash(lab, s):
            raise RuntimeError("docker pause: boom")
        os.makedirs(os.path.join(self.state, "lab"))
        out = io.StringIO()
        with mock.patch.object(sc, "SCENARIOS", dict(good=good, bad=bad, crash=crash)), \
                mock.patch.object(sc.Lab, "prepare"), redirect_stdout(out):
            self.assertEqual(sc.main([self.manifest, "--stage", self.stage]), 1)
        self.assertRegex(out.getvalue(), r"PASS good \(\d+s\)\nFAIL bad \(\d+s\)\n  the client did not fall back "
                                         r"locally while pause held\nFAIL crash \(\d+s\)\n  RuntimeError: docker pause")
        report = json.loads(Path(self.state, "lab", "scenarios.json").read_text())
        self.assertEqual({k: v["passed"] for k, v in report.items()}, dict(good=True, bad=False, crash=False))
        self.assertEqual(report["good"]["seen"], 1)


if __name__ == "__main__":
    unittest.main()
