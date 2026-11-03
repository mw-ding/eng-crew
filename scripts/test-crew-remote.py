"""Hardened remote call tests: entrypoint refusals, idempotent replay, client outcomes and the runner.

Usage: python3 scripts/test-crew-remote.py

No network or real host: a fake `ssh` on PATH either replies from the environment or runs the real entrypoint
locally (a simulated host), and a fake `tmux` holds the runner's session.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from crew_testlib import FAKE_TMUX

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "crew-remote.py")
spec = importlib.util.spec_from_file_location("crew_remote", SCRIPT)
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)

# Fake ssh: logs argv and the request, then replies from FAKE_SSH_MODE: `host` runs the real entrypoint (the
# simulated host's forced command), `sleep` hangs, otherwise prints FAKE_SSH_REPLY and exits FAKE_SSH_EXIT.
FAKE_SSH = """#!/usr/bin/env python3
import json, os, subprocess, sys, time
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
        self.assertEqual(first["argv"][-2:], ["host-b", "crew-host"])
        for option in ("-T", "-a", "-x", "BatchMode=yes", "StrictHostKeyChecking=yes", "ClearAllForwardings=yes",
                       "ConnectTimeout=10", "ServerAliveInterval=5", "ServerAliveCountMax=2"):
            self.assertIn(option, first["argv"])
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
