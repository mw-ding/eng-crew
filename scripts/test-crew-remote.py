"""Hardened remote call tests: entrypoint refusals, idempotent replay, client outcomes and the runner.

Usage: python3 scripts/test-crew-remote.py

No network or real host: a fake `ssh` on PATH either replies from the environment or runs the real entrypoint
locally (a simulated host), and a fake `tmux` holds the runner's session.
"""
import base64
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest import mock
from crew_testlib import FAKE_TMUX

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "crew-remote.py")
spec = importlib.util.spec_from_file_location("crew_remote", SCRIPT)
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
REAL_SSH = shutil.which("ssh")

# Fake ssh: `-G` prints a resolved config with env settings the client must drop. Otherwise it logs argv and the
# request, then replies from FAKE_SSH_MODE: `host` runs the real entrypoint (the simulated host's forced command),
# `sleep` hangs, otherwise prints FAKE_SSH_REPLY and exits FAKE_SSH_EXIT.
FAKE_SSH = """#!/usr/bin/env python3
import json, os, subprocess, sys, time
if "-G" in sys.argv:
    print("user crew\\nhostname " + sys.argv[-1] + ".overlay\\nport 2222\\nidentityfile ~/.ssh/crew_key")
    print("sendenv LANG\\nsetenv CREW_SECRET=1\\nforwardagent yes\\nproxyjump jump")
    sys.exit(int(os.environ.get("FAKE_SSH_G_EXIT", "0")))
data = sys.stdin.read()
with open(os.environ["FAKE_SSH_LOG"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "request": json.loads(data)}) + "\\n")
mode = os.environ.get("FAKE_SSH_MODE", "")
if mode == "host":
    env = {k: v for k, v in os.environ.items() if k == "PATH" or k.startswith("FAKE_TMUX_")}
    env["SSH_ORIGINAL_COMMAND"] = sys.argv[-1]
    sys.exit(subprocess.run([sys.executable, os.environ["FAKE_SSH_ENTRY"], "--root", os.environ["FAKE_SSH_ROOT"]],
                            input=data, text=True, env=env).returncode)
if mode == "sleep":
    time.sleep(30)
sys.stderr.write(os.environ.get("FAKE_SSH_STDERR", ""))
print(os.environ.get("FAKE_SSH_REPLY", ""))
sys.exit(int(os.environ.get("FAKE_SSH_EXIT", "0")))
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "root")
        os.makedirs(self.root)
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        for name, text in (("ssh", FAKE_SSH), ("tmux", FAKE_TMUX)):
            with open(os.path.join(self.bin, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(self.bin, name), 0o755)
        self.log = os.path.join(self.tmp, "ssh.log")
        env = {"PATH": self.bin + os.pathsep + os.environ["PATH"], "FAKE_SSH_LOG": self.log,
               "FAKE_SSH_ENTRY": SCRIPT, "FAKE_SSH_ROOT": self.root,
               "FAKE_TMUX_LOG": os.path.join(self.tmp, "tmux.log"),
               "FAKE_TMUX_STATE": os.path.join(self.tmp, "tmux.json")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, verb, **fields):
        return dict(fields, verb=verb, version=remote.version())

    def load(self, path):
        with open(path) as f:
            return json.load(f)

    def calls(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]


class Entrypoint(Base):
    def test_version_and_runner_state(self):
        reply = remote.handle(dict(verb="version"), self.root)
        self.assertEqual(reply, dict(result="ok", version=remote.version(), runner="down"))
        self.assertEqual(remote.runner(self.root, once=True), 0)
        self.assertEqual(remote.handle(dict(verb="version"), self.root)["runner"], "up")
        beat = self.load(os.path.join(self.root, "runner.json"))
        beat["beat"] = time.time() - 4 * beat["interval"]
        with open(os.path.join(self.root, "runner.json"), "w") as f:
            json.dump(beat, f)
        self.assertEqual(remote.handle(dict(verb="version"), self.root)["runner"], "down")

    def test_refusals(self):
        outside = os.path.join(self.tmp, "outside")
        os.symlink(self.tmp, os.path.join(self.root, "link"))
        cases = [
            (None, "unknown verb"), ("rm -rf ~", "unknown verb"), (dict(verb="shell"), "unknown verb"),
            (dict(verb="probe", version="v0.0.1"), "version skew"), (dict(verb="probe"), "version skew"),
            (self.request("probe", root=outside), "root differs"),
            (self.request("logs", path="../outside"), "path outside root"),
            (self.request("logs", path="/etc/passwd"), "path outside root"),
            (self.request("logs", log_path="link/outside"), "path outside root"),
            (self.request("logs", path=["a"]), "path outside root"),
            (self.request("spawn"), "needs a request id"), (self.request("spawn", request_id="../x"), "needs a request id"),
            (self.request("probe", path="wt/run", root=self.root), "verb probe not built"),
        ]
        for request, reason in cases:
            with self.subTest(request=request):
                reply = remote.handle(request, self.root)
                self.assertEqual(reply["result"], "refused")
                self.assertIn(reason, reply["reason"])
        reply = remote.handle(dict(verb="version"), self.root, command="crew-host; rm -rf ~")
        self.assertEqual(reply, dict(result="refused", reason="SSH command must be crew-host"))

    def test_mutating_retry_replays_first_reply(self):
        seen = []

        def spawn(request, root):
            seen.append(request["request_id"])
            return dict(result="ok", window=len(seen))
        with mock.patch.dict(remote.HANDLERS, spawn=spawn):
            first = remote.handle(self.request("spawn", request_id="r1"), self.root)
            again = remote.handle(self.request("spawn", request_id="r1"), self.root)
            other = remote.handle(self.request("spawn", request_id="r2"), self.root)
        self.assertEqual((first, again, other["window"], seen), (dict(result="ok", window=1), first, 2, ["r1", "r2"]))

    def test_handler_error_is_a_structured_failure(self):
        with mock.patch.dict(remote.HANDLERS, probe=lambda request, root: 1 / 0):
            reply = remote.handle(self.request("probe"), self.root)
        self.assertEqual(reply, dict(result="failed", error="ZeroDivisionError: division by zero"))

    def test_cli_reads_stdin_and_never_runs_a_shell_string(self):
        marker = os.path.join(self.tmp, "pwned")
        for data in ('{"verb": "version"}', "touch %s" % marker, '{"verb": "$(touch %s)"}' % marker):
            r = subprocess.run([sys.executable, SCRIPT, "--root", self.root], input=data, capture_output=True,
                               text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(json.loads(r.stdout)["result"], ("ok", "refused"))
        self.assertFalse(os.path.exists(marker))


class Client(Base):
    def test_hardened_argv_and_request(self):
        os.environ["FAKE_SSH_REPLY"] = json.dumps(dict(result="ok"))
        self.assertEqual(remote.call("host-b", "spawn", project="acme__widgets"), dict(result="ok"))
        remote.call("host-b", "spawn", request_id="retry-1")
        remote.call("host-b", "probe")
        first, retry, probe = self.calls()
        self.assertEqual(first["argv"][:2] + first["argv"][-2:], ["-F", "none", "host-b", "crew-host"])
        for option in ("-T", "-a", "-x", "BatchMode=yes", "StrictHostKeyChecking=yes", "ClearAllForwardings=yes",
                       "ConnectTimeout=10", "ServerAliveInterval=5", "ServerAliveCountMax=2", "user=crew",
                       "hostname=host-b.overlay", "port=2222", "identityfile=~/.ssh/crew_key"):
            self.assertIn(option, first["argv"])
        for dropped in ("sendenv", "setenv", "forwardagent", "proxyjump"):
            self.assertFalse(any(a.lower().startswith(dropped) for a in first["argv"]), dropped)
        self.assertEqual((first["request"]["verb"], first["request"]["version"]), ("spawn", remote.version()))
        self.assertRegex(first["request"]["request_id"], "^[0-9a-f]{32}$")
        self.assertEqual(retry["request"]["request_id"], "retry-1")
        self.assertNotIn("request_id", probe["request"])

    def test_outcomes(self):
        cases = [
            (dict(FAKE_SSH_REPLY=json.dumps(dict(result="refused", reason="unknown verb"))), "refused"),
            (dict(FAKE_SSH_REPLY="not json"), "failed"),
            (dict(FAKE_SSH_REPLY=json.dumps(dict(result="maybe"))), "failed"),
            (dict(FAKE_SSH_REPLY=json.dumps(dict(result="ok")), FAKE_SSH_EXIT="1"), "failed"),
            (dict(FAKE_SSH_EXIT="255", FAKE_SSH_STDERR="Host key verification failed."), "unreachable"),
            (dict(FAKE_SSH_G_EXIT="255"), "failed"),
        ]
        for env, result in cases:
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                self.assertEqual(remote.call("host-b", "spawn", request_id="r1")["result"], result)
        with mock.patch.dict(os.environ, FAKE_SSH_MODE="sleep"):
            reply = remote.call("host-b", "spawn", request_id="r1", timeout=1)
        self.assertEqual((reply["result"], reply["request_id"]), ("unreachable", "r1"))
        with mock.patch.dict(os.environ, PATH=self.tmp):
            self.assertEqual(remote.call("host-b", "version")["result"], "unreachable")

    def test_simulated_host_end_to_end(self):
        os.environ["FAKE_SSH_MODE"] = "host"
        self.assertEqual(remote.call("host-b", "version"), dict(result="ok", version=remote.version(), runner="down"))
        subprocess.run([sys.executable, SCRIPT, "--root", self.root, "runner", "--once"], check=True)
        self.assertEqual(remote.call("host-b", "version")["runner"], "up")
        self.assertIn("not built", remote.call("host-b", "spawn")["reason"])
        self.assertIn("path outside root", remote.call("host-b", "logs", path="../x")["reason"])


class Mirror(Base):
    """A local origin and a simulated host; a fake `gh` clones the origin, as the host's own login would."""
    def setUp(self):
        super().setUp()
        self.origin = os.path.join(self.tmp, "origin.git")
        self.work = os.path.join(self.tmp, "work")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.origin], check=True)
        subprocess.run(["git", "clone", "-q", self.origin, self.work], check=True, capture_output=True)
        self.commit()
        with open(os.path.join(self.bin, "gh"), "w") as f:
            f.write('#!/bin/sh\n[ "$3" = acme/widgets ] || { echo "repository not found: $3" >&2; exit 1; }\n'
                    'dest=$4; shift 5; exec git clone "$@" %s "$dest"\n' % self.origin)
        os.chmod(os.path.join(self.bin, "gh"), 0o755)
        os.environ["FAKE_SSH_MODE"] = "host"

    def commit(self):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", self.work, "commit",
                        "-q", "--allow-empty", "-m", "c"], check=True)
        subprocess.run(["git", "-C", self.work, "push", "-q", "origin", "HEAD:main"], check=True, capture_output=True)

    def head(self, repo):
        return subprocess.run(["git", "-C", repo, "rev-parse", "refs/heads/main"], capture_output=True, text=True,
                              check=True).stdout.strip()


class Prepare(Mirror):
    def test_fresh_then_refresh(self):
        reply = remote.call("host-b", "prepare", project="acme__widgets", root=self.root)
        mirror = os.path.join(self.root, "mirrors", "acme__widgets.git")
        self.assertEqual(reply, dict(result="ok", step="clone", mirror="mirrors/acme__widgets.git"))
        self.assertEqual(self.head(mirror), self.head(self.origin))
        for path in ("wt", "state/acme__widgets/status", "state/acme__widgets/inbox", "state/acme__widgets/verdicts"):
            self.assertTrue(os.path.isdir(os.path.join(self.root, path)), path)
        self.commit()
        reply = remote.call("host-b", "prepare", project="acme__widgets")
        self.assertEqual((reply["result"], reply["step"]), ("ok", "fetch"))
        self.assertEqual(self.head(mirror), self.head(self.origin))
        self.assertNotEqual(*[c["request"]["request_id"] for c in self.calls()])

    def test_failure_names_the_step(self):
        reply = remote.call("host-b", "prepare", project="acme__gadgets")
        self.assertEqual((reply["result"], reply["step"]), ("failed", "clone"))
        self.assertIn("repository not found: acme/gadgets", reply["error"])
        self.assertFalse(os.path.exists(os.path.join(self.root, "wt")))
        remote.call("host-b", "prepare", project="acme__widgets")
        shutil.rmtree(self.origin)
        reply = remote.call("host-b", "prepare", project="acme__widgets")
        self.assertEqual((reply["result"], reply["step"]), ("failed", "fetch"))
        for project in ("../x", "acme/widgets", "acme_x__w", None):
            reply = remote.call("host-b", "prepare", project=project)
            self.assertEqual(reply, dict(result="refused", reason="project must be owner__repo"))


class Seed(Mirror):
    """A forge-less host's mirror seeded from the primary's bundle; it never runs gh."""
    def bundle(self, *refs):
        path = os.path.join(self.tmp, "seed.bundle")
        subprocess.run(["git", "-C", self.work, "fetch", "-q", "origin"], check=True)
        subprocess.run(["git", "-C", self.work, "bundle", "create", "-q", path, *refs], check=True, capture_output=True)
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def test_seed_fresh_then_refresh(self):
        os.remove(os.path.join(self.bin, "gh"))
        mirror = os.path.join(self.root, "mirrors", "acme__widgets.git")
        for _ in range(2):
            reply = remote.call("host-b", "seed", project="acme__widgets", branch="main",
                                bundle=self.bundle("refs/remotes/origin/main"))
            tip = self.head(self.origin)
            self.assertEqual(reply, dict(result="ok", step="seed", tip=tip, mirror="mirrors/acme__widgets.git"))
            self.assertEqual(self.head(mirror), tip)
            r = subprocess.run(["git", "-C", mirror, "rev-parse", "refs/crew/heads/" + tip], capture_output=True)
            self.assertEqual(r.returncode, 0)
            self.commit()
        self.assertTrue(os.path.isdir(os.path.join(self.root, "state/acme__widgets/inbox")))
        self.assertFalse([n for n in os.listdir(os.path.join(self.root, "requests")) if n.endswith(".bundle")])

    def test_seed_failures(self):
        two = self.bundle("refs/remotes/origin/main", "HEAD")
        cases = [(dict(bundle="!!"), None), (dict(bundle=base64.b64encode(b"junk").decode()), "verify"),
                 (dict(bundle=two), "verify"),
                 (dict(bundle=self.bundle("refs/remotes/origin/main"), branch="../x"), "branch")]
        for fields, step in cases:
            with self.subTest(step=step):
                reply = remote.call("host-b", "seed", project="acme__widgets", **fields)
                self.assertEqual((reply["result"], reply.get("step")), ("failed", step), reply)
        self.assertFalse(os.path.exists(os.path.join(self.root, "wt")))


# Stub forge-free scripts at the job's head: check-repo prints the env names it sees, run-tests prints its args and
# a long filler (to cap) and fails on a name with "fail", evidence-cli echoes its args.
STUBS = {
    "scripts/check-repo.py": "import os\nprint(' '.join(sorted(os.environ)))\n",
    "scripts/run-tests.py": "import sys\nprint(sys.argv[1:])\nprint('x' * 9000)\n"
                            "sys.exit(any('fail' in a for a in sys.argv))\n",
    "scripts/evidence-cli.py": "import sys\nprint(sys.argv[1:])\n",
    "scripts/test-ok.py": "", "scripts/test-fail.py": "", "scripts/helper.py": "",
}


class Job(Base):
    """A host root whose acme__widgets mirror holds the stub scripts' commit, as a seed would leave it."""
    def setUp(self):
        super().setUp()
        work = os.path.join(self.tmp, "work")
        for path, text in STUBS.items():
            os.makedirs(os.path.dirname(os.path.join(work, path)), exist_ok=True)
            with open(os.path.join(work, path), "w") as f:
                f.write(text)
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", work]
        subprocess.run(["git", "init", "-q", work], check=True)
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "c"], check=True)
        self.head = subprocess.run([*git, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.mirror = os.path.join(self.root, "mirrors", "acme__widgets.git")
        subprocess.run(["git", "clone", "-q", "--mirror", work, self.mirror], check=True)

    def job(self, job_id="j1", request_id=None, **fields):
        fields = dict(dict(project="acme__widgets", head=self.head, commands=[dict(command="check-repo")]), **fields)
        return remote.handle(self.request("job", job_id=job_id, request_id=request_id or uuid.uuid4().hex, **fields),
                             self.root)

    def wait(self, job_id="j1", call=None):
        for _ in range(200):
            reply = (call or (lambda: remote.handle(self.request("result", job_id=job_id), self.root)))()
            if reply.get("status") == "done":
                return reply
            time.sleep(0.05)
        self.fail("job %s never finished" % job_id)

    def test_refused_unknown_command(self):
        tests = lambda *files: [dict(command="tests", files=list(files))]  # noqa: E731
        evidence = dict(command="evidence", argv=["true"])
        cases = [([dict(command="shell", argv=["rm"])], "not in the closed set"), ([], "non-empty list"),
                 ("check-repo", "non-empty list"), (["check-repo"], "not in the closed set"),
                 (tests("../test-ok.py"), "scripts/test-*.py"), (tests("test-missing.py"), "scripts/test-*.py"),
                 (tests("helper.py"), "scripts/test-*.py"), (tests(), "scripts/test-*.py"),
                 ([dict(command="evidence", argv="rm -rf ~")], "argv list"),
                 ([dict(evidence, setup=["x"])], "argv list"), ([evidence, evidence], "one evidence")]
        for commands, reason in cases:
            with self.subTest(commands=commands):
                reply = self.job(commands=commands)
                self.assertEqual(reply["result"], "refused")
                self.assertIn(reason, reply["reason"])
        self.assertIn("job_id", self.job(job_id="../x", request_id="r")["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.root, "jobs")))

    def test_refused_head_not_in_mirror(self):
        for head in ("0" * 40, "HEAD", "main", self.head[:12], "--upload-pack=x", None):
            with self.subTest(head=head):
                self.assertEqual(self.job(head=head), dict(result="refused", reason="head not in the host mirror"))
        for project in ("acme__gadgets", "../acme__widgets", None):
            self.assertEqual(self.job(project=project)["reason"], "project mirror not prepared")
        self.assertFalse(os.path.exists(os.path.join(self.root, "jobs")))
        self.assertEqual(remote.handle(self.request("result", job_id="j1"), self.root),
                         dict(result="refused", reason="unknown job"))

    def test_scrubbed_env(self):
        with mock.patch.dict(os.environ, GH_TOKEN="ghp_x", GITHUB_TOKEN="x", SSH_AUTH_SOCK="/tmp/agent",
                             CREW_PROJECT="/p/crew.toml", CREW_PROFILE="away", HOME=self.tmp):
            self.assertEqual(self.job()["status"], "running")
        names = self.wait()["commands"][0]["tail"].split()
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "SSH_AUTH_SOCK", "CREW_PROJECT", "CREW_PROFILE", "FAKE_SSH_LOG"):
            self.assertNotIn(name, names)
        self.assertEqual({"PATH", "HOME"} - set(names), set())

    def test_result_shape(self):
        commands = [dict(command="check-repo"), dict(command="tests", files=["test-ok.py", "test-fail.py"]),
                    dict(command="evidence", argv=["crew", "x y"], label="R1", setup="git init -q\n")]
        self.assertEqual(self.job(commands=commands), dict(result="ok", job_id="j1", head=self.head, status="running"))
        done = self.wait()
        self.assertEqual(sorted(done), ["commands", "head", "job_id", "result", "status"])
        self.assertEqual((done["head"], [c["command"] for c in done["commands"]]),
                         (self.head, ["check-repo", "tests", "evidence"]))
        for c in done["commands"]:
            self.assertEqual(sorted(c), ["command", "duration", "exit", "log", "tail"])
            self.assertTrue(os.path.isfile(os.path.join(self.root, c["log"])), c["log"])
            self.assertLessEqual(len(c["tail"]), remote.TAIL)
        self.assertEqual([c["exit"] for c in done["commands"]], [0, 1, 0])
        self.assertTrue(done["commands"][1]["tail"].endswith("x" * 100 + "\n"))
        setup = os.path.join(self.root, "jobs", "j1", "setup.sh")
        self.assertIn(str(["--label", "R1", "--setup", setup, "--", "crew", "x y"]), done["commands"][2]["tail"])
        wt = os.path.join(self.root, "jobs", "j1", "wt")
        head = subprocess.run(["git", "-C", wt, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, self.head)
        self.assertEqual(self.load(os.path.join(self.root, "jobs", "j1", "result.json"))["commands"][1]["exit"], 1)

    def test_idempotent_retry(self):
        self.assertEqual(self.job(request_id="r1")["status"], "running")
        first = self.wait()
        again = self.job(request_id="other", commands=[dict(command="tests", files=["test-ok.py"])])
        self.assertEqual(again, dict(result="ok", job_id="j1", head=self.head, status="done", retried=True))
        self.assertEqual(self.wait(), first)
        self.assertEqual(len([n for n in os.listdir(os.path.join(self.root, "jobs", "j1")) if n.endswith(".log")]), 1)
        self.assertEqual(self.job(request_id="r1"), dict(result="ok", job_id="j1", head=self.head, status="running"))

    def test_retention_removes_old_jobs(self):
        self.job()
        self.wait()
        old = time.time() - remote.JOB_RETENTION - 60
        os.utime(os.path.join(self.root, "jobs", "j1"), (old, old))
        self.job(job_id="j2")
        self.assertEqual(os.listdir(os.path.join(self.root, "jobs")), ["j2"])
        r = subprocess.run(["git", "-C", self.mirror, "worktree", "list"], capture_output=True, text=True)
        self.assertNotIn(os.path.join("jobs", "j1"), r.stdout)
        self.wait("j2")

    def test_simulated_host_end_to_end(self):
        os.environ["FAKE_SSH_MODE"] = "host"
        reply = remote.call("host-b", "job", job_id="e2e", project="acme__widgets", head=self.head,
                            commands=[dict(command="tests", files=["test-ok.py"])])
        self.assertEqual((reply["result"], reply["status"]), ("ok", "running"))
        done = self.wait("e2e", lambda: remote.call("host-b", "result", job_id="e2e"))
        self.assertEqual([(c["command"], c["exit"]) for c in done["commands"]], [("tests", 0)])
        self.assertNotIn("request_id", self.calls()[-1]["request"])


class RealSshConfig(Base):
    @unittest.skipUnless(REAL_SSH, "no OpenSSH client")
    def test_configured_env_never_reaches_the_call(self):
        """Real `ssh -G` resolution, no connection: SendEnv and SetEnv from the config are gone, auth is kept."""
        config = os.path.join(self.tmp, "ssh_config")
        with open(config, "w") as f:
            f.write("Host crew-review-host\n    HostName 127.0.0.1\n    User crew\n    Port 2222\n"
                    "    IdentityFile %s/crew_key\n    UserKnownHostsFile %s/known_hosts\n"
                    "    SendEnv CREW_REVIEW_SENTINEL\n    SetEnv CREW_REVIEW_CONFIG=nonsecret\n"
                    "    ForwardAgent yes\n    ProxyJump jump.invalid\n" % (self.tmp, self.tmp))
        os.environ["PATH"] = os.path.dirname(REAL_SSH)

        def resolved(argv):
            r = subprocess.run([argv[0], "-G", *argv[1:]], capture_output=True, text=True, check=True)
            return r.stdout.splitlines()
        self.assertIn("sendenv CREW_REVIEW_SENTINEL", resolved(["ssh", "-F", config, "crew-review-host"]))
        lines = resolved(remote.ssh_argv("crew-review-host", config))
        self.assertFalse([line for line in lines if line.startswith(("sendenv ", "setenv ", "proxyjump "))], lines)
        for line in ("hostname 127.0.0.1", "user crew", "port 2222", "identityfile %s/crew_key" % self.tmp,
                     "userknownhostsfile %s/known_hosts" % self.tmp, "stricthostkeychecking true", "batchmode yes",
                     "forwardagent no", "forwardx11 no", "clearallforwardings yes"):
            self.assertIn(line, lines)


class Runner(Base):
    def test_runner_owns_one_session_and_beats(self):
        remote.runner(self.root, once=True)
        remote.runner(self.root, once=True)
        with open(os.environ["FAKE_TMUX_LOG"]) as f:
            log = [json.loads(line) for line in f]
        self.assertEqual(sum(args[0] == "new-session" for args in log), 1)
        self.assertEqual(self.load(os.environ["FAKE_TMUX_STATE"])["crew-host"], {"0": "runner"})
        beat = self.load(os.path.join(self.root, "runner.json"))
        self.assertEqual((beat["session"], beat["interval"], beat["pid"]), ("crew-host", 30, os.getpid()))


if __name__ == "__main__":
    unittest.main()
