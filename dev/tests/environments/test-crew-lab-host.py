"""Lab test host tests: verified bundle activation, the run's forced key, the per-container host key, the PID-1
supervisor and the image spec.

Usage: python3 dev/tests/environments/test-crew-lab-host.py

No Docker: activation runs on a staged fake bundle, the supervisor on short-lived fake services, and the runner
service is built for the current (non-root) user. The Dockerfile is checked as text.
"""
import hashlib
import importlib.util
import io
import json
import os
import pwd
import re
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
LAB = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "environments", "terminal", "remote", "lab")
spec = importlib.util.spec_from_file_location("crew_lab_host", os.path.join(LAB, "crew-lab-host.py"))
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
KEY = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyMaterial0123456789abcdefABCDEF lab-run-1"
SOURCE = "0123456789abcdef0123456789abcdef01234567"


def stage_bundle(stage, tag, tamper=False):
    name = "mdstack-" + tag[1:]
    archive = Path(stage) / (name + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        for path, data in (("VERSION", tag + "\n"), ("cli/mdstack", "#!/bin/sh\n")):
            info = tarfile.TarInfo(name + "/" + path)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data.encode()))
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (Path(stage) / "SHA256SUMS").write_text(("0" * 64 if tamper else sha) + "  " + archive.name + "\n")
    return sha


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.bundle, self.record = self.dir / "opt" / "mdstack", self.dir / "lab.json"
        self.bundle.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()


class ActivateTest(Base):
    def test_verified_release_moves_into_place_and_is_recorded(self):
        sha = stage_bundle(self.dir, "v7.1.0")
        self.assertEqual(lab.activate(self.dir, "v7.1.0", str(self.bundle), self.record), sha)
        self.assertEqual((self.bundle / "VERSION").read_text().strip(), "v7.1.0")
        record = json.loads(self.record.read_text())
        self.assertEqual((record["tag"], record["bundle_sha256"], record["source_sha"]), ("v7.1.0", sha, None))

    def test_checksum_mismatch_activates_nothing(self):
        stage_bundle(self.dir, "v7.1.0", tamper=True)
        with self.assertRaisesRegex(ValueError, "SHA256SUMS mismatch"):
            lab.activate(self.dir, "v7.1.0", str(self.bundle), self.record)
        self.assertFalse(self.bundle.exists() or self.record.exists())

    def test_dev_tag_needs_the_exact_source_sha(self):
        stage_bundle(self.dir, "v0.0.0-dev.1")
        for bad in (None, "0123abc"):
            with self.assertRaisesRegex(ValueError, "needs --source-sha"):
                lab.activate(self.dir, "v0.0.0-dev.1", str(self.bundle), self.record, bad)
        lab.activate(self.dir, "v0.0.0-dev.1", str(self.bundle), self.record, SOURCE)
        self.assertEqual(json.loads(self.record.read_text())["source_sha"], SOURCE)

    def test_an_active_bundle_is_never_replaced(self):
        self.bundle.mkdir()
        stage_bundle(self.dir, "v7.1.0")
        with self.assertRaisesRegex(ValueError, "already active"):
            lab.activate(self.dir, "v7.1.0", str(self.bundle), self.record)


class AuthorizeTest(Base):
    def test_one_forced_restrict_line_replaced_each_run(self):
        home = self.dir / "home"
        lab.authorize(str(home), "ssh-ed25519 AAAAold old-run\n", "/opt/mdstack")
        line = lab.authorize(str(home), KEY + "\n", "/opt/mdstack")
        keys = home / ".ssh" / "authorized_keys"
        self.assertEqual(keys.read_text(), line)
        self.assertEqual(line, 'command="python3 /opt/mdstack/environments/terminal/remote/crew-remote.py --root %s",'
                               'restrict %s\n' % (home / ".mdstack", KEY))
        self.assertEqual((keys.stat().st_mode & 0o777, (home / ".ssh").stat().st_mode & 0o777), (0o600, 0o700))

    def test_refuses_options_extra_lines_or_non_keys(self):
        for bad in ('command="sh" ' + KEY, KEY + "\n" + KEY, "no-key-here", KEY + " two words"):
            with self.assertRaisesRegex(ValueError, "one public key line"):
                lab.authorize(str(self.dir / "home"), bad, "/opt/mdstack")
        self.assertFalse((self.dir / "home").exists())


class RunnerServiceTest(Base):
    def test_runner_runs_as_the_user_in_a_scrubbed_env(self):
        me = pwd.getpwuid(os.getuid())
        user = pwd.struct_passwd((me.pw_name, "x", me.pw_uid, me.pw_gid, "", str(self.dir), "/bin/sh"))
        with mock.patch.dict(os.environ, GH_TOKEN="secret", SSH_AUTH_SOCK="/agent", CREW_ID="ben-1"), \
                mock.patch.object(lab.subprocess, "Popen") as popen:
            argv, env, start = lab.runner_service(user, "/opt/mdstack")
            start()
        self.assertEqual(argv, ["python3", "/opt/mdstack/environments/terminal/remote/crew-remote.py", "--root",
                                str(self.dir / ".mdstack"), "runner"])
        kwargs = popen.call_args.kwargs
        self.assertEqual(popen.call_args.args, (argv,))
        self.assertEqual((kwargs["user"], kwargs["group"], kwargs["cwd"]), (me.pw_uid, me.pw_gid, str(self.dir)))
        self.assertEqual(kwargs["env"], env)
        self.assertEqual(env, dict(PATH="/usr/local/bin:/usr/bin:/bin", HOME=str(self.dir), USER=me.pw_name,
                                   LOGNAME=me.pw_name, LANG="C.UTF-8"))

    def test_never_root(self):
        root = pwd.struct_passwd(("root", "x", 0, 0, "", "/root", "/bin/sh"))
        with self.assertRaisesRegex(ValueError, "never runs as root"):
            lab.runner_service(root, "/opt/mdstack")


class SuperviseTest(Base):
    def service(self, name, script):
        log = self.dir / (name + ".log")

        def start():
            with open(log, "a") as f:
                f.write("start\n")
            return lab.subprocess.Popen([sys.executable, "-c", script], stdin=lab.subprocess.DEVNULL)
        return log, start

    def test_restarts_an_exited_service_and_stops_the_rest(self):
        flaky, start_flaky = self.service("flaky", "pass")
        steady, start_steady = self.service("steady", "import time; time.sleep(60)")
        deadline, out = time.time() + 1.5, io.StringIO()
        lab.supervise({"flaky": start_flaky, "steady": start_steady}, lambda: time.time() > deadline, 0.1, out)
        self.assertGreaterEqual(flaky.read_text().count("start"), 3)
        self.assertEqual(steady.read_text().count("start"), 1)
        self.assertIn("lab: flaky exited 0; restarting", out.getvalue())
        self.assertNotIn("steady exited", out.getvalue())

    def test_reaps_children_it_did_not_start(self):
        stray = os.posix_spawn(sys.executable, [sys.executable, "-c", "pass"], os.environ)
        time.sleep(0.3)
        deadline = time.time() + 0.3
        lab.supervise({}, lambda: time.time() > deadline, 0.05, io.StringIO())
        with self.assertRaises(ChildProcessError):
            os.waitpid(stray, os.WNOHANG)


class HostKeyTest(Base):
    def test_own_key_ignores_a_preloaded_one_and_survives_restarts(self):
        etc = self.dir / "etc" / "ssh"
        etc.mkdir(parents=True)
        lab.subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(etc / "ssh_host_ed25519_key")],
                           check=True)
        preloaded = (etc / "ssh_host_ed25519_key").read_bytes()
        path = lab.host_key(str(etc / "crew-lab" / "ssh_host_ed25519_key"))
        own = Path(path).read_bytes()
        self.assertNotEqual(own, preloaded)
        self.assertEqual(((etc / "crew-lab").stat().st_mode & 0o777, Path(path).stat().st_mode & 0o777),
                         (0o700, 0o600))
        lab.host_key(path)
        self.assertEqual(Path(path).read_bytes(), own)
        other = lab.host_key(str(self.dir / "other" / "ssh_host_ed25519_key"))
        self.assertNotEqual(Path(other).read_bytes(), own)

    def test_sshd_uses_only_that_key_and_the_image_deletes_inherited_ones(self):
        conf = Path(LAB, "sshd_config").read_text()
        self.assertEqual(re.findall(r"(?m)^HostKey (\S+)$", conf), [lab.HOST_KEY])
        self.assertNotIn("ssh-keygen -A", " ".join(lab.SSHD))
        self.assertIn("rm -rf /etc/ssh/ssh_host_* /etc/ssh/crew-lab", Path(LAB, "Dockerfile").read_text())


class ReadyTest(Base):
    def beat(self, age):
        (self.dir / ".mdstack").mkdir(exist_ok=True)
        (self.dir / ".mdstack" / "runner.json").write_text(json.dumps(dict(beat=time.time() - age, interval=30)))

    def test_ready_only_on_a_fresh_heartbeat(self):
        self.assertFalse(lab.ready(str(self.dir)))
        self.beat(10)
        self.assertTrue(lab.ready(str(self.dir)))
        self.beat(91)
        self.assertFalse(lab.ready(str(self.dir)))


class ImageSpecTest(unittest.TestCase):
    def setUp(self):
        self.text = Path(LAB, "Dockerfile").read_text()

    def test_base_is_pinned_by_digest_and_nothing_is_fetched(self):
        self.assertIn("@sha256:[0-9a-f]{64}", self.text)
        self.assertRegex(self.text, r"(?m)^FROM \$\{LAB_BASE\}$")
        self.assertIsNone(re.search(r"\b(curl|wget|apt-get|apt|apk|dnf|yum|pip3?|npm)\b", self.text))

    def test_supervisor_is_pid_1_and_health_is_the_heartbeat(self):
        self.assertRegex(self.text, r'ENTRYPOINT \[.*crew-lab-host.py", "supervise", "--user", "crew"\]')
        self.assertRegex(self.text, r'HEALTHCHECK .*crew-lab-host.py", "ready", "--user", "crew"\]')

    def test_nothing_from_a_home_or_login_is_copied_in(self):
        copies = re.findall(r"(?m)^COPY (\S+)", self.text)
        self.assertEqual(copies, ["scripts/crew-install.py", "environments/terminal/remote/lab/crew-lab-host.py",
                                  "environments/terminal/remote/lab/sshd_config"])

    def test_sshd_is_key_only_for_the_runner_user_without_forwarding(self):
        conf = dict(line.split(None, 1) for line in Path(LAB, "sshd_config").read_text().splitlines()
                    if line and not line.startswith("#"))
        for k, v in dict(AllowUsers="crew", PermitRootLogin="no", AuthenticationMethods="publickey",
                         PasswordAuthentication="no", PermitUserEnvironment="no", AllowAgentForwarding="no",
                         AllowTcpForwarding="no", X11Forwarding="no").items():
            self.assertEqual(conf.get(k), v, k)


if __name__ == "__main__":
    unittest.main()
