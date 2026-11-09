"""Hardened remote call tests: entrypoint refusals, idempotent replay, client outcomes and the runner.

Usage: python3 dev/tests/environments/test-crew-remote.py

No network or real host: a fake `ssh` on PATH either replies from the environment or runs the real entrypoint
locally (a simulated host), and a fake `tmux` holds the runner's session.
"""
import base64
import hashlib
import importlib.util
import io
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import uuid
import warnings
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import FAKE_COMPOSER, FAKE_TMUX

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
SCRIPT = os.path.join(os.path.dirname(SCRIPTS), "environments", "terminal", "remote", "crew-remote.py")
spec = importlib.util.spec_from_file_location("crew_remote", SCRIPT)
remote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
REAL_SSH = shutil.which("ssh")

# Fake ssh: `-G` prints a resolved config with env settings the client must drop. Otherwise it logs argv and the
# request, then replies from FAKE_SSH_MODE: `host` runs the real entrypoint (the simulated host's forced command),
# `sleep` hangs, otherwise prints FAKE_SSH_REPLY and exits FAKE_SSH_EXIT. With `-t` (attach) stdin stays the caller's
# terminal: the request is the SSH command's payload and the host runs with the caller's stdin.
FAKE_SSH = """#!/usr/bin/env python3
import base64, json, os, subprocess, sys, time
if "-G" in sys.argv:
    print("user crew\\nhostname " + sys.argv[-1] + ".overlay\\nport 2222\\nidentityfile ~/.ssh/crew_key")
    print("sendenv LANG\\nsetenv CREW_SECRET=1\\nforwardagent yes\\nproxyjump jump")
    sys.exit(int(os.environ.get("FAKE_SSH_G_EXIT", "0")))
tty = "-t" in sys.argv
data = None if tty else sys.stdin.read()
request = json.loads(base64.urlsafe_b64decode(sys.argv[-1].split(" ", 1)[1])) if tty else json.loads(data)
with open(os.environ["FAKE_SSH_LOG"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "request": request}) + "\\n")
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
        self.assertEqual(reply, dict(result="ok", version=remote.version(), runner="down",
                                     os=remote.UNAMES.get(platform.system(), platform.system().lower())))
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
        self.assertEqual(remote.call("host-b", "version"), dict(result="ok", version=remote.version(), runner="down",
                                                                os=remote.UNAMES.get(platform.system(), platform.system().lower())))
        subprocess.run([sys.executable, SCRIPT, "--root", self.root, "runner", "--once"], check=True)
        self.assertEqual(remote.call("host-b", "version")["runner"], "up")
        self.assertIn("pull needs windows", remote.call("host-b", "pull")["reason"])  # every verb is built (#346)
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


class Check(Mirror):
    """The `check` verb (#743): the rows, projects and load mdstack host check reads."""
    def check(self, **fields):
        request = dict(project="acme__widgets", default_branch="main", forge=True, identities={"builder": "acme-b"},
                       capabilities={"engines": ["codex"]})
        return remote.call("host-b", "check", **dict(request, **fields))

    def rows(self, reply):
        return {c["check"]: (c["status"], c["detail"]) for c in reply["checks"]}

    def test_refused_without_project_or_branch(self):
        for fields in (dict(project="../x"), dict(default_branch=None)):
            self.assertEqual(self.check(**fields)["result"], "refused")

    def test_forge_host_rows(self):
        for name, text in (("codex", '#!/bin/sh\n[ "$1" = login ] && exit 1\nexit 0\n'),
                           ("gh", '#!/bin/sh\n[ "$1" = auth ] && { echo "Logged in to github.com account acme-b"; '
                                  'exit 0; }\ndest=$4; shift 5; exec git clone "$@" %s "$dest"\n' % self.origin)):
            with open(os.path.join(self.bin, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(self.bin, name), 0o755)
        reply = self.check()
        self.assertEqual((reply["result"], reply["projects"], reply["load"]), ("ok", [], 0))
        rows = self.rows(reply)
        self.assertEqual(rows["tools"], ("ok", "git, tmux, gh, codex"))
        self.assertEqual(rows["project mirror"], ("fail", "acme__widgets has no main"))
        self.assertEqual(rows["logins"], ("human", "not logged in: codex"))
        self.assertEqual(rows["runner"], ("fail", "down"))
        self.assertEqual(rows["capacity"][0], "ok")
        self.assertEqual(remote.call("host-b", "prepare", project="acme__widgets", root=self.root)["result"], "ok")
        remote.runner(self.root, once=True)
        rows = self.rows(self.check(capabilities={}))
        self.assertEqual({k: v[0] for k, v in rows.items()},
                         dict.fromkeys(("tools", "project mirror", "logins", "runner", "capacity"), "ok"))
        self.assertEqual(self.check()["projects"], ["acme__widgets"])

    def test_forge_less_login_toolchain_and_disk_fail(self):
        with open(os.path.join(self.bin, "gh"), "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        with mock.patch.object(remote, "DISK_FLOOR", 1 << 62):
            rows = self.rows(remote.check_verb(dict(project="acme__widgets", default_branch="main", forge=False,
                                                    toolchain_bin=os.path.join(self.tmp, "nope")), self.root))
        self.assertEqual(rows["tools"], ("ok", "git, tmux"))
        self.assertEqual(rows["logins"], ("fail", "gh logged in"))
        self.assertEqual(rows["capacity"][0], "fail")
        self.assertEqual(rows["project mirror"][0], "fail")


class HostOs(Mirror):
    """#1358: the entrypoint picks its host OS adapter from the declared os against its uname (check 5)."""
    def handle(self, uname, verb, **fields):
        with mock.patch.object(remote.platform, "system", return_value=uname):
            return remote.handle(self.request(verb, **fields), self.root)

    def rows(self, reply):
        return {c["check"]: (c["status"], c["detail"]) for c in reply["checks"]}

    def test_mismatch_fails_check_and_prepare_before_any_change(self):
        check = dict(project="acme__widgets", default_branch="main", forge=False, capabilities={"os": "macos"})
        self.assertEqual(self.rows(self.handle("Linux", "check", **check))["capabilities"],
                         ("fail", "declared os macos, host is linux"))
        for verb in ("prepare", "seed"):
            reply = self.handle("Linux", verb, project="acme__widgets", os="macos", request_id="r-" + verb)
            self.assertEqual(reply, dict(result="failed", step="capabilities", error="declared os macos, host is linux"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "mirrors")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "wt")))
        self.assertEqual(self.handle("Linux", "prepare", project="acme__widgets", os="linux",
                                     request_id="r-ok")["result"], "ok")
        self.assertEqual(self.handle("Darwin", "version")["os"], "macos")

    def test_undeclared_os_adds_no_row(self):
        check = dict(project="acme__widgets", default_branch="main", forge=False)
        rows = self.rows(self.handle("Linux", "check", capabilities={}, ssh_port=22, **check))
        self.assertNotIn("capabilities", rows)
        self.assertNotIn("ssh listener", rows)
        self.assertEqual(rows["tools"], ("ok", "git, tmux"))

    def test_linux_adapter_backs_check(self):
        """#1359: systemd mode on a host without the lab image's supervised file."""
        for name, text in (("systemctl", "#!/bin/sh\necho inactive\nexit 3\n"),
                           ("loginctl", "#!/bin/sh\necho no\n"),
                           ("ss", "#!/bin/sh\necho 'LISTEN 0 128 0.0.0.0:22 0.0.0.0:*'\n")):
            with open(os.path.join(self.bin, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(self.bin, name), 0o755)
        remote.runner(self.root, once=True)
        rows = self.rows(self.handle("Linux", "check", project="acme__widgets", default_branch="main", forge=False,
                                     capabilities={"os": "linux"}, ssh_port=22))
        self.assertEqual(rows["capabilities"], ("ok", "os linux"))
        self.assertEqual(rows["tools"], ("ok", "git, tmux, systemctl, loginctl"))
        self.assertEqual(rows["runner"], ("ok", "up; linux inactive"))
        self.assertEqual(rows["linger"], ("warn", "Linger is off: the runner stops at logout"))
        self.assertEqual(rows["ssh listener"], ("warn", "port 22 listens on *"))

    def test_macos_adapter_backs_check(self):
        for name, text in (("launchctl", '#!/bin/sh\n[ "$1" = print ] && echo "	state = running"\nexit 0\n'),
                           ("netstat", "#!/bin/sh\necho 'tcp4  0  0  *.22   *.*   LISTEN'\n")):
            with open(os.path.join(self.bin, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(self.bin, name), 0o755)
        remote.runner(self.root, once=True)
        rows = self.rows(self.handle("Darwin", "check", project="acme__widgets", default_branch="main", forge=False,
                                     capabilities={"os": "macos"}, ssh_port=22))
        self.assertEqual(rows["capabilities"], ("ok", "os macos"))
        self.assertEqual(rows["tools"], ("ok", "git, tmux, launchctl"))
        self.assertEqual(rows["runner"], ("ok", "up; macos running"))
        self.assertEqual(rows["ssh listener"], ("warn", "port 22 listens on *"))


class MacosAdapter(unittest.TestCase):
    """#1358: the macOS adapter against a fake `run`; real launchd proof waits for a macOS VM or host (#1353 J)."""
    def setUp(self):
        spec = importlib.util.spec_from_file_location("macos", os.path.join(os.path.dirname(SCRIPT), "hostos", "macos.py"))
        self.macos = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.macos)
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        self.argvs, self.replies = [], {}

    def run_fake(self, argv):
        self.argvs.append(argv)
        return self.replies.get(argv[1] if argv[0] == "launchctl" else argv[0], (0, ""))

    def test_install_is_an_idempotent_keepalive_agent(self):
        self.replies["print"] = (113, "Could not find service")
        path = self.macos.install(self.run_fake, self.home, 501, "/usr/bin/python3", "/b/crew-remote.py", "/r")
        self.assertEqual(path, os.path.join(self.home, "Library/LaunchAgents/dev.mdstack.runner.plist"))
        with open(path, "rb") as f:
            agent = plistlib.load(f)
        self.assertEqual((agent["KeepAlive"], agent["RunAtLoad"], agent["ProgramArguments"]),
                         (True, True, ["/usr/bin/python3", "/b/crew-remote.py", "--root", "/r", "runner"]))
        self.assertEqual(self.argvs[-1], ["launchctl", "bootstrap", "gui/501", path])
        self.argvs, self.replies = [], {}
        self.macos.install(self.run_fake, self.home, 501, "/usr/bin/python3", "/b/crew-remote.py", "/r")
        self.assertEqual([a[1] for a in self.argvs], ["print", "bootout", "bootstrap"])
        self.replies["bootstrap"] = (5, "Bootstrap failed: 5: Input/output error")
        with self.assertRaisesRegex(RuntimeError, "Input/output error"):
            self.macos.install(self.run_fake, self.home, 501, "/usr/bin/python3", "/b/crew-remote.py", "/r")

    def test_start_stop_status_uninstall_act_on_the_agent_only(self):
        self.assertTrue(self.macos.start(self.run_fake, 501))
        self.assertTrue(self.macos.stop(self.run_fake, 501))
        self.assertEqual(self.argvs, [["launchctl", "kickstart", "-k", "gui/501/dev.mdstack.runner"],
                                      ["launchctl", "bootout", "gui/501/dev.mdstack.runner"]])
        for reply, state in (((0, "gui/501/dev.mdstack.runner = {\n\tstate = running\n"), "running"),
                             ((0, "\tstate = not running\n"), "loaded"), ((113, ""), "absent")):
            self.replies["print"] = reply
            self.assertEqual(self.macos.status(self.run_fake, 501), state)
        self.replies["print"] = (113, "")
        self.macos.install(self.run_fake, self.home, 501, "python3", "crew-remote.py", "/r")
        self.macos.uninstall(self.run_fake, self.home, 501)
        self.assertFalse(os.path.exists(self.macos.plist_path(self.home)))

    def test_start_time_reads_darwin_lstart(self):
        self.replies["env"] = (0, "Sun Nov  8 14:44:16 2026\n")
        expected = int(time.mktime((2026, 11, 8, 14, 44, 16, 0, 0, -1)))
        self.assertEqual(self.macos.start_time(self.run_fake, 42), expected)
        self.assertEqual(self.argvs[-1], ["env", "LC_ALL=C", "ps", "-o", "lstart=", "-p", "42"])
        for reply in ((1, ""), (0, "garbage\n")):
            self.replies["env"] = reply
            self.assertEqual(self.macos.start_time(self.run_fake, 42), "missing")

    def test_listener_row_warns_on_wildcard_or_public_only(self):
        netstat = ("Active Internet connections (including servers)\n"
                   "tcp4       0      0  100.64.1.2.22          *.*                    LISTEN     \n"
                   "tcp4       0      0  10.1.10.5.22           10.1.10.9.50000        ESTABLISHED\n"
                   "tcp46      0      0  *.2222                 *.*                    LISTEN     \n"
                   "tcp4       0      0  17.1.2.3.2222       *.*                    LISTEN     \n")
        self.replies["netstat"] = (0, netstat)
        self.assertEqual(self.macos.listener_row(self.run_fake, 22),
                         dict(status="ok", check="ssh listener", detail="port 22 on 100.64.1.2"))
        row = self.macos.listener_row(self.run_fake, 2222)
        self.assertEqual((row["status"], row["detail"]), ("warn", "port 2222 listens on *, 17.1.2.3"))
        self.assertEqual(self.argvs[-1], ["netstat", "-an", "-p", "tcp"])


class LinuxAdapter(unittest.TestCase):
    """#1359: the Linux adapter against a fake `run`; a real systemd user unit with lingering needs a systemd-capable
    Linux guest, which a no-systemd lab container does not prove."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.marker = os.path.join(self.tmp, "supervised")
        self.linux = self.load()
        self.home = os.path.join(self.tmp, "home")
        self.argvs, self.replies = [], {}

    def load(self):
        spec = importlib.util.spec_from_file_location("linux", os.path.join(os.path.dirname(SCRIPT), "hostos", "linux.py"))
        module = importlib.util.module_from_spec(spec)
        real = open
        with mock.patch("builtins.open", lambda p, *a, **k: real(self.marker if p == "/etc/mdstack/supervised" else p,
                                                                 *a, **k)):
            spec.loader.exec_module(module)
        module.SUPERVISED = self.marker
        return module

    def run_fake(self, argv):
        self.argvs.append(argv)
        return self.replies.get(argv[2] if argv[0] == "systemctl" else argv[1] if argv[0] == "loginctl" else argv[0],
                                (0, ""))

    def test_install_is_an_idempotent_restart_always_unit_with_linger(self):
        path = self.linux.install(self.run_fake, self.home, 1000, "/usr/bin/python3", "/b/crew-remote.py", "/r x")
        self.assertEqual(path, os.path.join(self.home, ".config/systemd/user/mdstack-runner.service"))
        with open(path) as f:
            unit = f.read()
        self.assertIn('ExecStart="/usr/bin/python3" "/b/crew-remote.py" "--root" "/r x" "runner"\n', unit)
        self.assertIn("Restart=always\n", unit)
        self.assertIn("WantedBy=default.target\n", unit)
        self.assertEqual(self.argvs, [["systemctl", "--user", "daemon-reload"],
                                      ["systemctl", "--user", "enable", "--now", "mdstack-runner.service"],
                                      ["loginctl", "enable-linger", "1000"]])
        self.assertEqual(self.linux.install(self.run_fake, self.home, 1000, "python3", "crew-remote.py", "/r"), path)
        self.replies["enable"] = (1, "Failed to connect to bus: No medium found")
        with self.assertRaisesRegex(RuntimeError, "No medium found"):
            self.linux.install(self.run_fake, self.home, 1000, "python3", "crew-remote.py", "/r")

    def test_start_stop_status_linger_uninstall_act_on_the_user_unit_only(self):
        self.assertTrue(self.linux.start(self.run_fake, 1000))
        self.assertTrue(self.linux.stop(self.run_fake, 1000))
        self.assertEqual(self.argvs, [["systemctl", "--user", "start", "mdstack-runner.service"],
                                      ["systemctl", "--user", "stop", "mdstack-runner.service"]])
        for reply, state in (((0, "active\n"), "active"), ((3, "inactive\n"), "inactive"),
                             ((1, "Failed to connect to bus: No medium found\n"), "no user manager")):
            self.replies["is-active"] = reply
            self.assertEqual(self.linux.status(self.run_fake, 1000), state)
        self.replies["show-user"] = (0, "yes\n")
        self.assertEqual(self.linux.service_rows(self.run_fake, 1000), [dict(status="ok", check="linger",
                                                                             detail="Linger=yes")])
        self.assertEqual(self.argvs[-1], ["loginctl", "show-user", "1000", "--property=Linger", "--value"])
        self.replies["show-user"] = (1, "User 1000 is not logged in or lingering")
        self.assertEqual(self.linux.service_rows(self.run_fake, 1000)[0]["status"], "warn")
        path = self.linux.install(self.run_fake, self.home, 1000, "python3", "crew-remote.py", "/r")
        self.linux.uninstall(self.run_fake, self.home, 1000)
        self.assertEqual(self.argvs[-1], ["systemctl", "--user", "disable", "--now", "mdstack-runner.service"])
        self.assertFalse(os.path.exists(path))

    def test_supervised_is_selected_by_the_image_file_never_by_a_missing_systemd(self):
        self.assertEqual(self.linux.TOOLS, ["systemctl", "loginctl"])
        with open(self.marker, "w") as f:
            f.write("crew-lab-host.py\n")
        supervised = self.load()
        self.assertEqual(supervised.TOOLS, [])
        self.assertEqual(supervised.install(self.run_fake, self.home, 1000, "python3", "crew-remote.py", "/r"),
                         "n/a: supervised")
        self.assertEqual((supervised.start(self.run_fake, 1000), supervised.stop(self.run_fake, 1000)), (False, False))
        self.assertEqual(supervised.status(self.run_fake, 1000), "supervised")
        self.assertEqual(supervised.service_rows(self.run_fake, 1000), [])
        supervised.uninstall(self.run_fake, self.home, 1000)
        self.assertEqual(self.argvs, [])
        self.assertFalse(os.path.exists(self.home))

    def test_start_time_reads_procfs_then_ps(self):
        proc = os.path.join(self.tmp, "proc")
        os.makedirs(os.path.join(proc, "42"))
        with open(os.path.join(proc, "42", "stat"), "w") as f:
            f.write("42 (crew (remote)) S 1 42 42 0 -1 4194560 1 0 0 0 0 0 0 0 20 0 1 0 %d 1000 100\n"
                    % (250 * os.sysconf("SC_CLK_TCK")))
        with open(os.path.join(proc, "stat"), "w") as f:
            f.write("cpu  1 2 3\nbtime 1793000000\nprocesses 9\n")
        self.assertEqual(self.linux.start_time(self.run_fake, 42, proc), 1793000250)
        self.assertEqual(self.argvs, [])
        self.replies["env"] = (0, "Sun Nov  8 14:44:16 2026\n")
        self.assertEqual(self.linux.start_time(self.run_fake, 7, proc),
                         int(time.mktime((2026, 11, 8, 14, 44, 16, 0, 0, -1))))
        self.assertEqual(self.argvs[-1], ["env", "LC_ALL=C", "ps", "-o", "lstart=", "-p", "7"])
        self.replies["env"] = (1, "")
        self.assertEqual(self.linux.start_time(self.run_fake, 7, proc), "missing")

    def test_listener_row_warns_on_wildcard_or_public_only(self):
        self.replies["ss"] = (0, "LISTEN 0 128 100.64.1.2:22 0.0.0.0:*\n"
                                 "LISTEN 0 128 [fd7a:115c::1]:22 [::]:*\n"
                                 "LISTEN 0 128 [::]:2222 [::]:*\n"
                                 "LISTEN 0 128 127.0.0.1%lo:2222 0.0.0.0:*\n"
                                 "LISTEN 0 128 17.1.2.3:2222 0.0.0.0:*\n")
        self.assertEqual(self.linux.listener_row(self.run_fake, 22),
                         dict(status="ok", check="ssh listener", detail="port 22 on 100.64.1.2, fd7a:115c::1"))
        row = self.linux.listener_row(self.run_fake, 2222)
        self.assertEqual((row["status"], row["detail"]), ("warn", "port 2222 listens on *, 17.1.2.3"))
        self.assertEqual(self.argvs[-1], ["ss", "-Hltn"])


class Toolkit(Mirror):
    """prepare with a toolkit pin installs the primary's release from a mirror source with the shared verifier."""
    TAG = "v5.1.0"

    def setUp(self):
        super().setUp()
        self.releases = os.path.join(self.tmp, "releases")
        self.sha, sums = self.publish()
        self.pin = dict(tag=self.TAG, bundle_sha256=self.sha, transport=dict(
            kind="mirror", location=self.releases, sha256sums_sha256=sums, pinned=False))
        self.toolkit = os.path.join(self.root, "toolkit", "mdstack-5.1.0")

    def publish(self, crew="#!/bin/sh\n", extra=(), tag=None):
        """Write releases/<tag>/{mdstack-<v>.tar.gz,SHA256SUMS}; return both digests."""
        tag = tag or self.TAG
        name = remote.crew_install().bundle_name(tag)
        where = os.path.join(self.releases, tag)
        os.makedirs(where, exist_ok=True)
        archive = os.path.join(where, name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            for path, data in (("VERSION", tag + "\n"), ("cli/mdstack", crew)) + tuple(extra):
                info = tarfile.TarInfo(name + "/" + path)
                info.size = len(data.encode())
                tar.addfile(info, io.BytesIO(data.encode()))
        sha = remote.crew_install().digest(archive)
        with open(os.path.join(where, "SHA256SUMS"), "w") as f:
            f.write("%s  %s.tar.gz\n" % (sha, name))
        return sha, remote.crew_install().digest(os.path.join(where, "SHA256SUMS"))

    def prepare(self, pin):
        return remote.call("host-b", "prepare", project="acme__widgets", toolkit=pin)

    def test_install_then_reuse_and_record(self):
        for state in ("installed", "reused"):
            reply = self.prepare(self.pin)
            self.assertEqual((reply["result"], reply.get("toolkit")), ("ok", dict(tag=self.TAG, state=state)), reply)
        record = self.load(self.toolkit + ".json")
        self.assertEqual((record["tag"], record["bundle_sha256"], record["transport"]),
                         (self.TAG, self.sha, self.pin["transport"]))
        self.assertEqual(sorted(record["files"]), ["VERSION", "cli/mdstack"])
        self.assertEqual(self.load(os.path.join(self.root, "state/acme__widgets/toolkit.json")), dict(tag=self.TAG))
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "toolkit"))), ["mdstack-5.1.0", "mdstack-5.1.0.json"])

    def test_entrypoint_run_from_the_toolkit_keeps_it_verified(self):
        extra = []
        for rel in ("environments/terminal/remote/crew-remote.py", "scripts/crew-install.py"):
            with open(os.path.join(os.path.dirname(SCRIPTS), rel)) as f:
                extra.append((rel, f.read()))
        sha, sums = self.publish(extra=extra)
        pin = dict(self.pin, bundle_sha256=sha, transport=dict(self.pin["transport"], sha256sums_sha256=sums))
        self.assertEqual(self.prepare(pin)["toolkit"]["state"], "installed")
        with mock.patch.dict(os.environ, FAKE_SSH_ENTRY=os.path.join(self.toolkit, "environments/terminal/remote/crew-remote.py")), \
                mock.patch.object(remote, "version", return_value=self.TAG):
            self.assertEqual(self.status(pin), dict(status="ok", detail="mdstack v5.1.0 verified"))
            reply = self.prepare(pin)
            self.assertEqual(reply.get("toolkit"), dict(tag=self.TAG, state="reused"), reply)
            self.assertEqual(self.status(pin)["status"], "ok")
        self.assertFalse([d for d, _, _ in os.walk(self.toolkit) if d.endswith("__pycache__")])

    def test_tampered_or_partial_version_is_installed_again(self):
        self.prepare(self.pin)
        with open(os.path.join(self.toolkit, "cli/mdstack"), "w") as f:
            f.write("tampered\n")
        self.assertEqual(self.prepare(self.pin)["toolkit"]["state"], "installed")
        with open(os.path.join(self.toolkit, "cli/mdstack")) as f:
            self.assertEqual(f.read(), "#!/bin/sh\n")
        os.remove(self.toolkit + ".json")
        self.assertEqual(self.prepare(self.pin)["toolkit"]["state"], "installed")
        self.assertFalse([n for n in os.listdir(os.path.join(self.root, "toolkit")) if n.startswith(".staging-")])

    def test_refused_release_never_becomes_ready(self):
        self.prepare(self.pin)
        bad_sums = dict(self.pin, transport=dict(self.pin["transport"], sha256sums_sha256="0" * 64))
        cases = ((dict(self.pin, bundle_sha256="0" * 64), "differs from the primary's pin"),
                 (bad_sums, "does not match the pinned sha256sums_digest"),
                 (dict(self.pin, tag="5.1.0"), "toolkit pin needs a release tag"),
                 (dict(self.pin, transport=dict(kind="ftp", location="x")), "kind url, mirror or git"))
        for pin, message in cases:
            with self.subTest(message=message):
                reply = self.prepare(pin)
                self.assertEqual((reply["result"], reply.get("step")), ("failed", "toolkit"), reply)
                self.assertIn(message, reply["error"])
                self.assertEqual(self.status(), dict(status="ok", detail="mdstack v5.1.0 verified"))
        self.assertFalse([n for n in os.listdir(os.path.join(self.root, "toolkit")) if n.startswith(".staging-")])
        with open(os.path.join(self.toolkit, "cli/mdstack"), "w") as f:
            f.write("tampered\n")
        self.assertEqual(self.prepare(bad_sums)["result"], "failed")
        self.assertIn("files differ from its record", self.status()["detail"])

    def status(self, pin=None, project="acme__widgets"):
        return remote.call("host-b", "version", project=project, toolkit=pin or self.pin)["toolkit"]

    def test_version_reports_the_pinned_toolkit(self):
        self.assertEqual(self.status()["status"], "fail")
        self.assertIn("pins no toolkit on this host", self.status()["detail"])
        self.prepare(self.pin)
        self.assertEqual(self.status(), dict(status="ok", detail="mdstack v5.1.0 verified"))
        cases = ((dict(self.pin, tag="v5.2.0"), "pins v5.1.0 on this host, the primary v5.2.0"),
                 (dict(self.pin, bundle_sha256="0" * 64), "record differs from the primary's pin"),
                 (dict(self.pin, transport=dict(self.pin["transport"], location="/elsewhere")), "record differs"))
        for pin, message in cases:
            with self.subTest(message=message):
                self.assertEqual(self.status(pin)["status"], "fail")
                self.assertIn(message, self.status(pin)["detail"])
        with open(os.path.join(self.toolkit, "extra"), "w") as f:
            f.write("x")
        self.assertIn("files differ from its record", self.status()["detail"])
        os.remove(os.path.join(self.toolkit, "extra"))
        with open(os.path.join(self.toolkit, "VERSION"), "w") as f:
            f.write("v5.1.0 \n")
        self.assertIn("files differ from its record", self.status()["detail"])
        self.assertNotIn("toolkit", remote.call("host-b", "version"))

    def test_prune_removes_only_unpinned_versions(self):
        self.prepare(self.pin)
        toolkit = os.path.join(self.root, "toolkit")
        for name in ("mdstack-5.0.0", ".staging-old"):
            os.makedirs(os.path.join(toolkit, name, "scripts"))
        with open(os.path.join(toolkit, "mdstack-5.0.0.json"), "w") as f:
            f.write("{}")
        os.makedirs(os.path.join(self.root, "state/acme__gadgets"))
        with open(os.path.join(self.root, "state/acme__gadgets/toolkit.json"), "w") as f:
            json.dump(dict(tag="v5.0.0"), f)
        reply = remote.call("host-b", "prepare", project="acme__widgets", toolkit=self.pin, prune=True)
        self.assertEqual(reply["pruned"], [".staging-old"])
        os.remove(os.path.join(self.root, "state/acme__gadgets/toolkit.json"))
        reply = remote.call("host-b", "prepare", project="acme__widgets", toolkit=self.pin, prune=True)
        self.assertEqual(reply["pruned"], ["mdstack-5.0.0", "mdstack-5.0.0.json"])
        self.assertEqual(sorted(os.listdir(toolkit)), ["mdstack-5.1.0", "mdstack-5.1.0.json"])
        self.assertEqual(self.status()["status"], "ok")

    def test_new_pin_installs_its_toolkit_and_prunes_the_old_one(self):  # #1312
        self.prepare(self.pin)
        sha, sums = self.publish(tag="v7.0.0")
        pin = dict(self.pin, tag="v7.0.0", bundle_sha256=sha, transport=dict(self.pin["transport"], sha256sums_sha256=sums))
        reply = remote.call("host-b", "prepare", project="acme__widgets", toolkit=pin, prune=True)
        self.assertEqual((reply["result"], reply["toolkit"]), ("ok", dict(tag="v7.0.0", state="installed")), reply)
        self.assertEqual(reply["pruned"], ["mdstack-5.1.0", "mdstack-5.1.0.json"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "toolkit"))), ["mdstack-7.0.0", "mdstack-7.0.0.json"])
        self.assertEqual(self.status(pin), dict(status="ok", detail="mdstack v7.0.0 verified"))


# Stub forge-free scripts at the job's head: check-repo prints the env names it sees, run-tests prints its args and
# a long filler (to cap) and fails on a name with "fail", evidence-cli echoes its args.
STUBS = {
    "scripts/check-repo.py": "import os\nprint(' '.join(sorted(os.environ)))\n",
    "scripts/run-tests.py": "import sys\nprint(sys.argv[1:])\nprint('x' * 9000)\n"
                            "sys.exit(any('fail' in a for a in sys.argv))\n",
    "scripts/evidence-cli.py": "import sys\nprint(sys.argv[1:])\n",
    "dev/tests/x/test-ok.py": "", "dev/tests/x/test-fail.py": "", "scripts/helper.py": "",
}


class Job(Base):
    """A host root whose acme__widgets mirror holds the stub scripts' commit, as a seed would leave it."""
    def setUp(self):
        super().setUp()
        warnings.filterwarnings("ignore", "subprocess .* is still running", ResourceWarning)  # the detached job
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
                 (tests("../test-ok.py"), "dev/tests/*/test-*.py"), (tests("test-missing.py"), "dev/tests/*/test-*.py"),
                 (tests("helper.py"), "dev/tests/*/test-*.py"), (tests(), "dev/tests/*/test-*.py"),
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


class RunBase(Mirror):
    """A prepared host with its runner up and one live pane process for a spawned run."""
    def setUp(self):
        super().setUp()
        self.assertEqual(remote.call("host-b", "prepare", project="acme__widgets", root=self.root)["result"], "ok")
        remote.runner(self.root, once=True)
        self.pane()
        self.sha = self.head(self.origin)
        self.wt = os.path.join(self.root, "wt", "7-%s-builder-build" % self.sha[:7])
        self.state = os.path.join(self.root, "state", "acme__widgets")

    def pane(self):
        """A live pane process whose group stop() can end: orphaned, so init reaps it."""
        out = subprocess.run(["sh", "-c", "sleep 60 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True,
                             start_new_session=True).stdout.strip()
        self.pid = int(out)
        os.environ["FAKE_TMUX_PANE"] = "%%1 %d 0 0 /dev/ttys001 claude" % self.pid
        self.addCleanup(lambda pid=self.pid: subprocess.run(["kill", "-9", str(pid)], capture_output=True))

    def spawn(self, request_id=None, **fields):
        request = dict(project="acme__widgets", window="ben-7", primary="host-a", role="builder",
                       engine="claude-code", model="opus", effort="high", permission_mode="bypass",
                       identity="acme-bot", brief="# Brief\n", worktree_path="wt/" + os.path.basename(self.wt),
                       sha=self.sha, ref="refs/heads/main", verdicts={"pr9-%s-r1-review.md" % self.sha[:7]: "review\n"})
        return remote.call("host-b", "spawn", request_id=request_id, **dict(request, **fields))

    def kill(self, **fields):
        return remote.call("host-b", "kill", **dict(dict(project="acme__widgets", window="ben-7", primary="host-a",
                                                         refs=["refs/heads/main"]), **fields))

    def probe(self, **fields):
        return remote.call("host-b", "probe", **dict(dict(project="acme__widgets", window="ben-7", primary="host-a"),
                                                     **fields))

    def windows(self):
        return self.load(os.environ["FAKE_TMUX_STATE"])["crew-host"]


class RunLifecycle(RunBase):
    """#345: spawn, probe and kill a role run in the runner's session; the worktree guards hold on the host."""
    def test_spawn_starts_in_the_runner_session_once(self):
        reply = self.spawn("spawn-1")
        self.assertEqual((reply["result"], reply["worktree"], reply["pane_pid"]), ("ok", self.wt, str(self.pid)))
        self.assertEqual(self.windows(), {"0": "runner", "1": "acme__widgets/ben-7"})
        self.assertEqual(self.spawn("spawn-1"), reply)  # a retried request id never opens a second window
        self.assertEqual(self.windows(), {"0": "runner", "1": "acme__widgets/ben-7"})
        self.assertEqual(self.spawn()["reason"], "run ben-7 exists")
        self.assertEqual(subprocess.run(["git", "-C", self.wt, "rev-parse", "HEAD"], capture_output=True, text=True)
                         .stdout.strip(), self.sha)
        with open(os.path.join(self.state, "runs", "ben-7.brief.md")) as f:
            self.assertEqual(f.read(), "# Brief\n")
        with open(os.path.join(self.state, "verdicts", "pr9-%s-r1-review.md" % self.sha[:7])) as f:
            self.assertEqual(f.read(), "review\n")
        with open(os.environ["FAKE_TMUX_LOG"]) as f:
            (launch,) = [json.loads(line) for line in f if '"new-window"' in line]
        env = dict(a.split("=", 1) for a in launch if a.startswith("CREW_"))
        self.assertEqual((env["CREW_ID"], env["CREW_STATE"], env["CREW_IDENTITY"]), ("ben-7", self.state, "acme-bot"))
        self.assertTrue(launch[-1].startswith('export GH_TOKEN="$(gh auth token --user "$CREW_IDENTITY")"; exec claude '))
        rec = self.load(os.path.join(self.state, "runs", "ben-7.json"))
        self.assertEqual((rec["primary"], rec["worktree"], rec["pane_id"]), ("host-a", self.wt, "%1"))

    def test_spawn_refusals_start_nothing(self):
        for fields, reason in ((dict(sha="0" * 40), "stale spawn: refs/heads/main is not " + "0" * 40),
                               (dict(engine="nope"), "engine or permission_mode not launchable on this host"),
                               (dict(permission_mode="ask"), "engine or permission_mode not launchable on this host"),
                               (dict(worktree_path="mirrors/x"), "spawn needs worktree_path=wt/<name>, sha, ref and verdicts"),
                               (dict(ref="--upload-pack=x"), "spawn needs worktree_path=wt/<name>, sha, ref and verdicts"),
                               (dict(verdicts={"../x.md": ""}), "spawn needs worktree_path=wt/<name>, sha, ref and verdicts"),
                               (dict(model="a b"), "spawn needs role, model, effort, identity and brief"),
                               (dict(relaunch=True), "no run ben-7 to relaunch")):
            self.assertEqual(self.spawn(**fields), dict(result="refused", reason=reason))
        self.assertEqual(self.spawn(worktree_path="../x")["reason"], "path outside root")
        os.remove(os.path.join(self.root, "runner.json"))
        self.assertEqual(self.spawn()["reason"], "runner down")
        self.assertEqual(self.windows(), {"0": "runner"})
        self.assertFalse(os.path.exists(self.wt))

    def test_probe_classes(self):
        self.assertEqual(self.probe()["liveness"], "missing")
        self.spawn()
        self.assertEqual(self.probe()["liveness"], "alive")
        self.assertEqual(self.probe(primary="host-c")["reason"], "probe run ben-7 belongs to primary host-a")
        tmux = self.load(os.environ["FAKE_TMUX_STATE"])
        tmux["_panes"]["crew-host:1"] = "%%1 %d 1 0 /dev/ttys001 claude" % self.pid
        with open(os.environ["FAKE_TMUX_STATE"], "w") as f:
            json.dump(tmux, f)
        self.assertEqual(self.probe()["liveness"], "dead")
        tmux["_panes"]["crew-host:1"] = "%%2 %d 0 0 /dev/ttys001 claude" % self.pid
        with open(os.environ["FAKE_TMUX_STATE"], "w") as f:
            json.dump(tmux, f)
        self.assertEqual(self.probe()["liveness"], "missing")  # same name, another run

    def test_kill_keeps_unlanded_work_then_discards_on_request(self):
        self.spawn()
        with open(os.path.join(self.wt, "a.txt"), "w") as f:
            f.write("x\n")
        self.assertEqual(self.kill(primary="host-c")["reason"], "kill run ben-7 belongs to primary host-a")
        reply = self.kill()
        self.assertEqual(reply, dict(result="ok", unlanded=["uncommitted: ?? a.txt"], removed=False))
        self.assertEqual(self.windows(), {"0": "runner"})  # the window stops either way
        self.assertTrue(os.path.isdir(self.wt))
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "ben-7.json")))
        self.pane()
        reply = self.spawn(relaunch=True, brief="# Brief 2\n")  # restart in place: same worktree, fresh brief
        self.assertEqual((reply["result"], reply["worktree"]), ("ok", self.wt))
        self.assertEqual(self.windows(), {"0": "runner", "1": "acme__widgets/ben-7"})
        self.assertTrue(os.path.exists(os.path.join(self.wt, "a.txt")))
        self.assertEqual(self.kill(keep=True), dict(result="ok", unlanded=[], removed=False))
        self.assertTrue(os.path.isdir(self.wt))
        self.assertEqual(self.kill(discard=True), dict(result="ok", unlanded=[], removed=True))
        self.assertFalse(os.path.exists(self.wt))
        self.assertEqual(os.listdir(os.path.join(self.state, "runs")), [])
        self.assertEqual(self.kill(), dict(result="ok", unlanded=[], removed=False))  # already gone

    def test_kill_removes_landed_work_and_lists_unpushed_commits(self):
        self.spawn()
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", self.wt, "commit",
                        "-q", "--allow-empty", "-m", "local"], check=True)
        reply = self.kill()
        self.assertEqual(len(reply["unlanded"]), 1)
        self.assertTrue(reply["unlanded"][0].startswith("commit: ") and reply["unlanded"][0].endswith(" local"))
        subprocess.run(["git", "-C", self.wt, "push", "-q", "origin", "HEAD:refs/heads/main"], check=True,
                       capture_output=True)
        self.assertEqual(self.kill(), dict(result="ok", unlanded=[], removed=True))
        self.assertFalse(os.path.exists(self.wt))
        self.assertEqual(self.kill(refs=["main"])["reason"], "kill needs refs, the default branch first")

    def test_kill_never_touches_another_projects_run(self):  # review r1 P1: one runner session, many projects
        self.spawn()
        self.assertEqual(self.kill(project="other__project", primary="host-c"),
                         dict(result="ok", unlanded=[], removed=False))
        self.assertEqual(self.windows(), {"0": "runner", "1": "acme__widgets/ben-7"})
        self.assertEqual(self.probe()["liveness"], "alive")
        self.assertEqual(self.probe(project="other__project")["liveness"], "missing")


class PullSend(RunLifecycle):
    """#346: pull returns status lines by offset with a prefix digest; send appends the inbox line and nudges once."""
    def status(self, text, mode="a"):
        with open(os.path.join(self.state, "status", "ben-7.status"), mode) as f:
            f.write(text)

    def pull(self, data=b"", **fields):
        at = dict(offset=len(data), digest=hashlib.sha256(data).hexdigest())
        return remote.call("host-b", "pull", **dict(dict(project="acme__widgets", windows={"ben-7": at},
                                                         primary="host-a"), **fields))

    def chunk(self, reply):
        got = reply["windows"]["ben-7"]
        return got["offset"], base64.b64decode(got["data"])

    def test_pull_by_offset_resumes_and_resets_on_a_rewritten_file(self):
        self.spawn()
        self.status("ack: a\nstep: half")  # a line still being written waits for the next pull
        reply = self.pull()
        self.assertEqual((self.chunk(reply), reply["windows"]["ben-7"]["liveness"]), ((0, b"ack: a\n"), "alive"))
        self.assertEqual(self.chunk(self.pull(b"ack: a\n")), (7, b""))  # a repeated pull adds nothing
        self.status(" done\nstep: 2\n")
        self.assertEqual(self.chunk(self.pull(b"ack: a\n")), (7, b"step: half done\nstep: 2\n"))
        self.assertEqual(self.chunk(self.pull(b"ack: X\n")), (0, b"ack: a\nstep: half done\nstep: 2\n"))  # torn mirror
        self.status("new run\n", "w")  # a shorter, rewritten file: from 0
        self.assertEqual(self.chunk(self.pull(b"ack: a\nstep: half done\n")), (0, b"new run\n"))
        self.assertEqual(self.pull(primary="host-c")["reason"], "pull run ben-7 belongs to primary host-a")
        self.assertEqual(self.pull(windows={"ben-7": {"offset": -1, "digest": ""}})["reason"],
                         "pull needs an offset and digest for ben-7")
        gone = self.pull(windows={"ben-8": {"offset": 0, "digest": hashlib.sha256(b"").hexdigest()}})
        self.assertEqual(gone["windows"]["ben-8"], dict(offset=0, data="", size=0, liveness="missing"))

    def send(self, request_id=None, **fields):
        msg = dict(id="20261108T120000Z-abc123", kind="fix", refs=["#9", "a" * 40], **{"from": "ash"},
                   ts="2026-11-08T12:00:00Z")
        return remote.call("host-b", "send", request_id=request_id, **dict(dict(
            project="acme__widgets", window="ben-7", primary="host-a", message=msg), **fields))

    def test_send_appends_the_inbox_line_and_types_the_nudge_once(self):
        self.assertEqual(self.send()["reason"], "no window ben-7 on this host")
        self.spawn()
        self.assertEqual(self.send("send-1"), dict(result="ok", nudge=None))
        self.assertEqual(self.send("send-1"), dict(result="ok", nudge=None))  # a retried request id acts once
        with open(os.path.join(self.state, "inbox", "ben-7.jsonl")) as f:
            (line,) = [json.loads(x) for x in f]
        self.assertEqual((line["id"], line["refs"]), ("20261108T120000Z-abc123", ["#9", "a" * 40]))
        with open(os.environ["FAKE_TMUX_LOG"]) as f:
            typed = [json.loads(x) for x in f if '"send-keys"' in x]
        self.assertEqual(typed[0], ["send-keys", "-t", "=crew-host:1", "-l", "inbox: 20261108T120000Z-abc123"])
        self.assertEqual(typed[1:], [["send-keys", "-t", "=crew-host:1", "Enter"]])
        for message in (dict(id="x"), dict(id="20261108T120000Z-abc123", kind="fix", refs=["--- a/x"], ts="t",
                                           **{"from": "ash"})):
            self.assertEqual(self.send(message=message)["reason"],
                             "send needs a refs-only message {id, kind, refs, from, ts}")
        self.assertEqual(self.send(primary="host-c")["reason"], "send run ben-7 belongs to primary host-a")

    def composer(self, enters):
        """The host's tmux behind send.py's composer model (env renamed: the fake ssh passes FAKE_TMUX_* only)."""
        os.rename(os.path.join(self.bin, "tmux"), os.path.join(self.bin, "tmux-base"))
        with open(os.path.join(self.bin, "tmux"), "w") as f:
            f.write(FAKE_COMPOSER.replace('"FAKE_COMPOSER"', '"FAKE_TMUX_COMPOSER"'))
        os.chmod(os.path.join(self.bin, "tmux"), 0o755)
        path = os.path.join(self.tmp, "composer.json")
        os.environ["FAKE_TMUX_COMPOSER"] = path
        with open(path, "w") as f:
            json.dump({"history": [], "draft": [], "enters": enters}, f)
        return lambda: self.load(path)

    def enters(self):
        with open(os.environ["FAKE_TMUX_LOG"]) as f:
            return sum(1 for x in f if json.loads(x)[-1:] == ["Enter"])

    def test_send_retries_an_enter_swallowed_as_a_newline(self):  # review r1: the draft spans the indented row
        self.spawn()
        model = self.composer(["newline", "submit"])
        self.assertEqual(self.send("send-2"), dict(result="ok", nudge=None))
        self.assertEqual((model()["draft"], model()["history"], self.enters()),
                         ([], ["› inbox: 20261108T120000Z-abc123", "  "], 2))

    def test_send_reports_a_nudge_that_never_submits(self):
        self.spawn()
        model = self.composer(["newline"])
        self.assertEqual(self.send("send-3"), dict(result="ok", nudge="`inbox: 20261108T120000Z-abc123` is still in "
                                                                        "its composer after 3 Enter retries"))
        self.assertEqual((model()["history"], self.enters()), ([], 4))


class Observe(RunBase):
    """#348: attach to a run's pane through a TTY only, capture its screen and tail its step summary."""
    def setUp(self):
        super().setUp()
        self.spawn()
        self.scope = dict(project="acme__widgets", window="ben-7", primary="host-a")

    def attaches(self):
        with open(os.environ["FAKE_TMUX_LOG"]) as f:
            return [args for args in map(json.loads, f) if args[0] == "attach-session"]

    def test_only_attach_takes_a_tty(self):
        self.assertEqual(remote.handle(self.request("attach", **self.scope), self.root),
                         dict(result="refused", reason="attach needs a TTY"))
        self.assertEqual(remote.handle(self.request("probe", **self.scope), self.root, tty=True),
                         dict(result="refused", reason="only attach takes a TTY"))
        self.assertEqual(self.attaches(), [])

    def test_attach_runs_tmux_on_the_runs_pane_read_only_unless_rw(self):
        self.assertEqual(remote.handle(self.request("attach", **self.scope), self.root, tty=True),
                         dict(result="ok", exit=0))
        remote.handle(self.request("attach", rw=True, **self.scope), self.root, tty=True)
        self.assertEqual(self.attaches(), [["attach-session", "-r", "-t", "=crew-host:1"],
                                           ["attach-session", "-t", "=crew-host:1"]])
        for fields, reason in ((dict(primary="host-c"), "attach run ben-7 belongs to primary host-a"),
                               (dict(window="ben-8"), "no run ben-8 on this host"),
                               (dict(project="other__project"), "no run ben-7 on this host")):
            self.assertEqual(remote.handle(self.request("attach", **dict(self.scope, **fields)), self.root, tty=True),
                             dict(result="refused", reason=reason))
        self.assertEqual(len(self.attaches()), 2)

    def test_attach_over_ssh_carries_the_request_in_the_command(self):
        code = remote.attach("host-b", **self.scope)  # the test's stdin is no TTY, so the host refuses
        self.assertEqual(code, 1)
        (call,) = [c for c in self.calls() if c["request"]["verb"] == "attach"]
        self.assertIn("-t", call["argv"])
        self.assertNotIn("-T", call["argv"])
        self.assertEqual((call["argv"][-2], call["argv"][-1].split(" ")[0]), ("host-b", "crew-host"))
        self.assertEqual(call["request"], dict(self.scope, verb="attach", version=remote.version()))
        self.assertEqual(self.attaches(), [])
        payload = base64.urlsafe_b64encode(json.dumps(self.request("attach", **self.scope)).encode()).decode()
        env = dict(os.environ, SSH_ORIGINAL_COMMAND="crew-host " + payload)
        primary, secondary = os.openpty()
        self.addCleanup(os.close, primary)
        with os.fdopen(secondary) as tty:  # sshd's pty: the entrypoint attaches and exits with tmux's code
            r = subprocess.run([sys.executable, SCRIPT, "--root", self.root], stdin=tty, capture_output=True,
                               text=True, env=env)
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertEqual(self.attaches(), [["attach-session", "-r", "-t", "=crew-host:1"]])
        r = subprocess.run([sys.executable, SCRIPT, "--root", self.root], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, env=env)
        self.assertEqual((r.returncode, json.loads(r.stdout)), (1, dict(result="refused", reason="attach needs a TTY")))

    def test_capture_returns_the_pane_screen(self):
        os.environ["FAKE_TMUX_SCREEN"] = "line 1\nline 2\n\n\n"
        self.assertEqual(remote.call("host-b", "capture", **self.scope), dict(result="ok", text="line 1\nline 2"))
        self.assertEqual(remote.call("host-b", "capture", **dict(self.scope, window="ben-8")),
                         dict(result="refused", reason="no run ben-8 on this host"))

    def test_logs_tails_the_newest_step_summary_only(self):
        self.assertEqual(remote.call("host-b", "logs", **self.scope), dict(result="ok", path=None, lines=[]))
        for rel, count, mtime in (("issue-7/build", 3, 1000), ("pr-9/fix-1", 30, 2000)):
            path = os.path.join(self.wt, ".crew", "runs", rel, "summary.md")
            os.makedirs(os.path.join(os.path.dirname(path), "steps"))
            with open(path, "w") as f:
                f.write("".join("%s step %d\n" % (rel, i) for i in range(count)))
            os.utime(path, (mtime, mtime))
            with open(os.path.join(os.path.dirname(path), "steps", "build.log"), "w") as f:
                f.write("RAW\n")
        reply = remote.call("host-b", "logs", lines=2, **self.scope)
        self.assertEqual(reply, dict(result="ok", path=os.path.relpath(path, self.root),
                                     lines=["pr-9/fix-1 step 28", "pr-9/fix-1 step 29"]))
        self.assertEqual(len(remote.call("host-b", "logs", **self.scope)["lines"]), 20)
        for lines in (0, 501, True, "5"):
            self.assertEqual(remote.call("host-b", "logs", lines=lines, **self.scope),
                             dict(result="refused", reason="lines must be 1 to 500"))
        self.assertEqual(remote.call("host-b", "logs", **dict(self.scope, primary="host-c"))["reason"],
                         "logs run ben-7 belongs to primary host-a")


class Runner(Base):
    def test_runner_owns_one_session_and_beats(self):
        os.environ["TMUX_TMPDIR"] = os.path.join(self.tmp, "tmux-tmp")
        remote.runner(self.root, once=True)
        socket_dir = os.path.join(self.tmp, "tmux-tmp", "tmux-%d" % os.getuid())  # -S never makes it (#348 lab)
        self.assertEqual(os.stat(socket_dir).st_mode & 0o777, 0o700)
        remote.runner(self.root, once=True)
        with open(os.environ["FAKE_TMUX_LOG"]) as f:
            log = [json.loads(line) for line in f]
        self.assertEqual(sum(args[0] == "new-session" for args in log), 1)
        self.assertEqual(self.load(os.environ["FAKE_TMUX_STATE"])["crew-host"], {"0": "runner"})
        beat = self.load(os.path.join(self.root, "runner.json"))
        self.assertEqual((beat["session"], beat["interval"], beat["pid"]), ("crew-host", 30, os.getpid()))


if __name__ == "__main__":
    unittest.main()
