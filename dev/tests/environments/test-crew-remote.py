"""Hardened remote call tests: entrypoint refusals, idempotent replay, client outcomes and the runner.

Usage: python3 dev/tests/environments/test-crew-remote.py

No network or real host: a fake `ssh` on PATH either replies from the environment or runs the real entrypoint
locally (a simulated host), and a fake `tmux` holds the runner's session.
"""
import base64
import importlib.util
import io
import json
import os
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
from crew_testlib import FAKE_TMUX

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
SCRIPT = os.path.join(SCRIPTS, "crew-remote.py")
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


class Toolkit(Mirror):
    """prepare with a toolkit pin installs the primary's release from a mirror source with the shared verifier."""
    TAG = "v5.1.0"

    def setUp(self):
        super().setUp()
        self.releases = os.path.join(self.tmp, "releases")
        self.sha, sums = self.publish()
        self.pin = dict(tag=self.TAG, bundle_sha256=self.sha, transport=dict(
            kind="mirror", location=self.releases, sha256sums_sha256=sums, pinned=False))
        self.toolkit = os.path.join(self.root, "toolkit", "eng-crew-5.1.0")

    def publish(self, crew="#!/bin/sh\n", extra=(), tag=None):
        """Write releases/<tag>/{<name>.tar.gz,SHA256SUMS} (v5.1.0: eng-crew-5.1.0); return both digests."""
        tag = tag or self.TAG
        name = remote.crew_install().bundle_name(tag)
        where = os.path.join(self.releases, tag)
        os.makedirs(where, exist_ok=True)
        archive = os.path.join(where, name + ".tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            for path, data in (("VERSION", tag + "\n"), ("scripts/crew", crew)) + tuple(extra):
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
        self.assertEqual(sorted(record["files"]), ["VERSION", "scripts/crew"])
        self.assertEqual(self.load(os.path.join(self.root, "state/acme__widgets/toolkit.json")), dict(tag=self.TAG))
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "toolkit"))), ["eng-crew-5.1.0", "eng-crew-5.1.0.json"])

    def test_entrypoint_run_from_the_toolkit_keeps_it_verified(self):
        extra = []
        for rel in ("scripts/crew-remote.py", "environments/terminal/remote/crew-remote.py", "scripts/crew-install.py"):
            with open(os.path.join(os.path.dirname(SCRIPTS), rel)) as f:  # the forced command runs the #1222 shim
                extra.append((rel, f.read()))
        sha, sums = self.publish(extra=extra)
        pin = dict(self.pin, bundle_sha256=sha, transport=dict(self.pin["transport"], sha256sums_sha256=sums))
        self.assertEqual(self.prepare(pin)["toolkit"]["state"], "installed")
        with mock.patch.dict(os.environ, FAKE_SSH_ENTRY=os.path.join(self.toolkit, "scripts/crew-remote.py")), \
                mock.patch.object(remote, "version", return_value=self.TAG):
            self.assertEqual(self.status(pin), dict(status="ok", detail="mdstack v5.1.0 verified"))
            reply = self.prepare(pin)
            self.assertEqual(reply.get("toolkit"), dict(tag=self.TAG, state="reused"), reply)
            self.assertEqual(self.status(pin)["status"], "ok")
        self.assertFalse([d for d, _, _ in os.walk(self.toolkit) if d.endswith("__pycache__")])

    def test_tampered_or_partial_version_is_installed_again(self):
        self.prepare(self.pin)
        with open(os.path.join(self.toolkit, "scripts/crew"), "w") as f:
            f.write("tampered\n")
        self.assertEqual(self.prepare(self.pin)["toolkit"]["state"], "installed")
        with open(os.path.join(self.toolkit, "scripts/crew")) as f:
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
        with open(os.path.join(self.toolkit, "scripts/crew"), "w") as f:
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
        for name in ("eng-crew-5.0.0", ".staging-old"):
            os.makedirs(os.path.join(toolkit, name, "scripts"))
        with open(os.path.join(toolkit, "eng-crew-5.0.0.json"), "w") as f:
            f.write("{}")
        os.makedirs(os.path.join(self.root, "state/acme__gadgets"))
        with open(os.path.join(self.root, "state/acme__gadgets/toolkit.json"), "w") as f:
            json.dump(dict(tag="v5.0.0"), f)
        reply = remote.call("host-b", "prepare", project="acme__widgets", toolkit=self.pin, prune=True)
        self.assertEqual(reply["pruned"], [".staging-old"])
        os.remove(os.path.join(self.root, "state/acme__gadgets/toolkit.json"))
        reply = remote.call("host-b", "prepare", project="acme__widgets", toolkit=self.pin, prune=True)
        self.assertEqual(reply["pruned"], ["eng-crew-5.0.0", "eng-crew-5.0.0.json"])
        self.assertEqual(sorted(os.listdir(toolkit)), ["eng-crew-5.1.0", "eng-crew-5.1.0.json"])
        self.assertEqual(self.status()["status"], "ok")

    def test_7x_pin_installs_mdstack_toolkit_and_prunes_the_6x_one(self):  # #1312
        self.prepare(self.pin)
        sha, sums = self.publish(tag="v7.0.0")
        pin = dict(self.pin, tag="v7.0.0", bundle_sha256=sha, transport=dict(self.pin["transport"], sha256sums_sha256=sums))
        reply = remote.call("host-b", "prepare", project="acme__widgets", toolkit=pin, prune=True)
        self.assertEqual((reply["result"], reply["toolkit"]), ("ok", dict(tag="v7.0.0", state="installed")), reply)
        self.assertEqual(reply["pruned"], ["eng-crew-5.1.0", "eng-crew-5.1.0.json"])
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
