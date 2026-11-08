"""Lab Docker setup and teardown tests: manifest pins, refusal before mutation, loopback-only ports, isolated env,
the per-run SSH config, the N3 probe and manifest-scoped teardown.

Usage: python3 dev/tests/environments/test-crew-lab-docker.py

No Docker: every docker, ssh-keygen and tmux call goes to an in-memory fake daemon that records argv and env. The
campaign guard check, its sentinel and the tmux decoy are stubbed; their own tests cover them.
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
LAB = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "environments", "terminal", "remote", "lab")
spec = importlib.util.spec_from_file_location("crew_lab_docker", os.path.join(LAB, "crew-lab-docker.py"))
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
ENDPOINT = "unix:///owner/.docker/run/docker.sock"
INHERITED = {"CREW_STATE": "/live/state", "CREW_PROJECT": "/live/crew.toml", "GH_TOKEN": "ghp_decoy",
             "GITHUB_TOKEN": "ghp_decoy2", "SSH_AUTH_SOCK": "/tmp/agent.sock", "TMUX": "/tmp/tmux-1/default,1,0",
             "TMUX_PANE": "%1"}


class FakeDocker:
    """Enough of the Docker CLI for the lab: resources keyed by ID, each call recorded with its env."""

    def __init__(self):
        self.calls, self.objs, self.n = [], {}, 0
        self.ports, self.mounts, self.endpoint, self.activated = ["127.0.0.1:55022"], [], ENDPOINT, {}
        self.probe = lambda cid, t: "denied: [Errno 101] Network is unreachable"

    def add(self, kind, name, labels=None, **extra):
        self.n += 1
        rid = "%s%04d" % (kind[0], self.n) + "0" * 8
        self.objs[rid] = dict(kind=kind, name=name, labels=labels or {}, nets=[], **extra)
        return rid

    def find(self, ref):
        return next((k for k, o in self.objs.items() if ref in (k, o["name"])), None)

    def __call__(self, argv, env):
        self.calls.append((list(argv), dict(env)))
        out, rc = self.answer(list(argv)), 0
        if out is None:
            out, rc = "", 1
        return subprocess.CompletedProcess(argv, rc, out + "\n", "no such object" if rc else "")

    def labels(self, argv):
        return dict(argv[i + 1].split("=", 1) for i, x in enumerate(argv) if x == "--label")

    def listing(self, kind, argv):
        objs = [o for o in self.objs.values() if o["kind"] == kind]
        if "--filter" in argv:
            k, v = argv[argv.index("--filter") + 1][len("label="):].split("=", 1)
            objs = [o for o in objs if o["labels"].get(k) == v]
        return "\n".join(o["name"] for o in objs)

    def answer(self, a):
        if a[0] == "ssh-keygen":
            key = a[a.index("-f") + 1]
            Path(key).write_text("private\n")
            Path(key + ".pub").write_text("ssh-ed25519 AAAArun crew-lab\n")
            return ""
        if a[0] == "tmux":
            return ""
        a = a[1:]
        if a[:2] == ["context", "show"]:
            return "desktop-linux"
        if a[:2] == ["context", "inspect"]:
            return self.endpoint
        if a[:2] == ["ps", "-a"]:
            return self.listing("container", a)
        if a[:2] == ["network", "ls"]:
            return self.listing("network", a)
        if a[:2] == ["image", "inspect"]:
            return "sha256:" + "ab" * 32 if a[-1] == "lab:dev" else None
        if a[:2] == ["network", "create"]:
            return self.add("network", a[-1], self.labels(a), internal="--internal" in a)
        if a[:2] == ["network", "connect"]:
            self.objs[a[3]]["nets"].append(a[2])
            return ""
        if a[:2] == ["network", "rm"]:
            return "" if self.objs.pop(a[2], None) else None
        if a[0] == "create":
            rid = self.add("container", a[a.index("--name") + 1], self.labels(a), argv=a)
            self.objs[rid]["nets"].append(a[a.index("--network") + 1])
            return rid
        if a[0] == "inspect" and a[1] == "--type":
            o = self.objs.get(a[3])
            if not o or o["kind"] != a[2]:
                return None
            return json.dumps([{"Id": a[3], "Config": {"Labels": o["labels"]}} if a[2] == "container"
                               else {"Id": a[3], "Labels": o["labels"]}])
        if a[0] == "inspect" and "Mounts" in a[2]:
            return json.dumps(self.mounts)
        if a[0] == "inspect":
            return " ".join("10.%d.0.2" % (int(n[1:5]) % 250) for n in self.objs[a[-1]]["nets"])
        if a[0] == "cp" and os.path.isdir(a[1]):
            self.bundle = next(hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(a[1]).glob("*.tar.gz"))
            return ""
        if a[0] in ("cp", "start"):
            return ""
        if a[0] == "exec" and a[2:4] == ["cat", "/opt/mdstack-lab.json"]:
            return json.dumps(dict({"tag": "v7.1.0", "bundle_sha256": self.bundle, "sha256sums_sha256": "c" * 64,
                                    "source_sha": None}, **self.activated))
        if a[0] == "exec" and a[2:4] == ["cat", lab.HOST_KEY]:
            return "ssh-ed25519 AAAAhost%s crew-lab" % a[1][:5]
        if a[0] == "exec" and a[3] == "-c":
            return json.dumps({t: self.probe(a[1], t) for t in a[5:]})
        if a[0] == "exec":
            return ""
        if a[0] == "port":
            return "\n".join(self.ports)
        if a[0] == "logs":
            return "lab: started sshd"
        if a[:3] == ["rm", "-f", "-v"]:
            return "" if self.objs.pop(a[3], None) else None
        raise AssertionError("unexpected docker call %s" % a)

    def docker_argv(self):
        return [argv[1:] for argv, _ in self.calls if argv[0] == "docker"]

    def mutations(self):
        return [a for a in self.docker_argv() if a[0] in ("create", "cp", "start", "rm") or
                a[:2] in (["network", "create"], ["network", "rm"], ["network", "connect"])]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state = root / "state"
        self.state.mkdir()
        self.stage = root / "stage"
        self.stage.mkdir()
        (self.stage / "mdstack-7.1.0.tar.gz").write_bytes(b"bundle")
        (self.stage / "SHA256SUMS").write_text("x  mdstack-7.1.0.tar.gz\n")
        self.manifest = self.state / "manifest.json"
        self.manifest.write_text(json.dumps({"run_id": "run1", "roots": {"state_dir": str(self.state)}}))
        self.fake = FakeDocker()
        self.refusals = []
        self.sentinel, self.decoy = 0, True
        for target, attr, value in ((lab, "call", self.fake), (lab.guard, "refusals", lambda m: self.refusals),
                                    (lab.guard, "main", lambda argv: self.sentinel),
                                    (lab.runner, "decoy_start", lambda: "/tmp/decoy/s"),
                                    (lab.runner, "decoy_alive", lambda sock: self.decoy),
                                    (lab.time, "sleep", lambda s: None)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, INHERITED)
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def setup_lab(self, *extra):
        return lab.main(["setup", str(self.manifest), "--image", "lab:dev", "--stage", str(self.stage),
                         "--tag", "v7.1.0", *extra])

    def m(self):
        return json.loads(self.manifest.read_text())


class SetupTest(Base):
    def test_manifest_pins_context_image_ids_ports_and_hashes(self):
        self.assertEqual(self.setup_lab(), 0)
        lab_ = self.m()["lab"]
        self.assertEqual((lab_["context"], lab_["endpoint"], lab_["image"]), ("desktop-linux", ENDPOINT,
                                                                             "sha256:" + "ab" * 32))
        self.assertEqual(sorted(lab_["stage"]), ["SHA256SUMS", "mdstack-7.1.0.tar.gz"])
        self.assertEqual(sorted(lab_["hosts"]), ["lab-a", "lab-b"])
        self.assertEqual(len(lab_["networks"]), 2)
        for h in lab_["hosts"].values():
            self.assertEqual(self.fake.objs[h["container"]]["labels"],
                             {"mdstack.lab.run": "run1", "mdstack.lab.owner": lab_["owner"]})
            self.assertEqual((h["port"], h["volumes"]), (55022, []))
            self.assertEqual(h["activated"]["bundle_sha256"], lab_["stage"]["mdstack-7.1.0.tar.gz"])

    def test_ssh_is_published_on_loopback_only_and_nothing_is_mounted(self):
        self.setup_lab()
        creates = [a for a in self.fake.docker_argv() if a[0] == "create"]
        self.assertEqual(len(creates), 2)
        for a in creates:
            self.assertEqual(a[a.index("-p") + 1], "127.0.0.1::22")
            self.assertFalse({"-v", "--volume", "--mount", "--privileged"} & set(a))
        self.assertFalse(any(o.get("internal") for o in self.fake.objs.values()))

    def test_per_run_ssh_config_maps_lowercase_aliases_to_loopback_ports(self):
        self.setup_lab()
        home = self.state / "lab" / "home" / ".ssh"
        conf = (home / "config").read_text()
        self.assertIn("Host lab-a\n  HostName 127.0.0.1\n  Port 55022\n  User crew\n  HostKeyAlias lab-a\n", conf)
        self.assertIn("IdentityAgent none", conf)
        self.assertIn("UserKnownHostsFile %s" % (home / "known_hosts"), conf)
        self.assertRegex((home / "known_hosts").read_text(), r"(?m)^lab-b ssh-ed25519 AAAAhostc\d+$")

    def test_children_get_an_isolated_home_and_no_inherited_crew_token_agent_or_tmux(self):
        self.setup_lab()
        lab_home = str(self.state / "lab" / "home")
        for argv, env in self.fake.calls:
            self.assertFalse(set(INHERITED) & set(env), argv)
            if argv[1:3] not in (["context", "show"], ["context", "inspect"]):
                self.assertEqual(env["HOME"], lab_home, argv)
                self.assertEqual(env["GH_CONFIG_DIR"], str(self.state / "lab" / "gh-config"))
            if argv[0] == "docker" and argv[1] != "context":
                self.assertEqual(env.get("DOCKER_HOST"), ENDPOINT, argv)

    def test_name_collision_refuses_before_any_mutation(self):
        self.fake.add("network", "crew-lab-run1-lab-a")
        self.assertEqual(self.setup_lab(), 2)
        self.assertEqual(self.fake.mutations(), [])
        self.assertNotIn("lab", self.m())

    def test_run_label_collision_refuses_before_any_mutation(self):
        self.fake.add("container", "leftover", {"mdstack.lab.run": "run1"})
        self.assertEqual(self.setup_lab(), 2)
        self.assertEqual(self.fake.mutations(), [])

    def test_existing_lab_guard_refusal_or_uppercase_alias_refuse_before_docker(self):
        for change in (lambda: self.manifest.write_text(json.dumps(dict(self.m(), lab={"run": "run1"}))),
                       lambda: self.refusals.append("source: moved"), None):
            with self.subTest(change=change):
                self.manifest.write_text(json.dumps({"run_id": "run1", "roots": {"state_dir": str(self.state)}}))
                self.refusals.clear()
                self.fake.calls.clear()
                if change:
                    change()
                    self.assertEqual(self.setup_lab(), 2)
                else:
                    self.assertEqual(self.setup_lab("--host", "Lab-A"), 2)
                self.assertEqual(self.fake.calls, [])

    def test_missing_image_refuses_before_any_mutation(self):
        self.assertEqual(lab.main(["setup", str(self.manifest), "--image", "nope", "--stage", str(self.stage),
                                   "--tag", "v7.1.0"]), 2)
        self.assertEqual(self.fake.mutations(), [])

    def test_port_beyond_loopback_bind_mount_or_other_bundle_stops_with_ids_recorded(self):
        for field, value in (("ports", ["0.0.0.0:55022"]), ("mounts", [{"Type": "bind", "Source": "/Users"}]),
                             ("activated", {"bundle_sha256": "f" * 64}), ("activated", {"source_sha": "0" * 40})):
            with self.subTest(field=field, value=value):
                self.manifest.write_text(json.dumps({"run_id": "run1", "roots": {"state_dir": str(self.state)}}))
                self.fake = FakeDocker()
                setattr(self.fake, field, value)
                with mock.patch.object(lab, "call", self.fake):
                    self.assertEqual(self.setup_lab(), 2)
                host = self.m()["lab"]["hosts"]["lab-a"]
                self.assertIn(host["container"], self.fake.objs)
                self.assertNotIn("lab-b", self.m()["lab"]["hosts"])


class N3Test(Base):
    def test_n3_setup_uses_internal_networks_no_ports_and_a_driver_on_all(self):
        self.assertEqual(self.setup_lab("--n3"), 0)
        lab_ = self.m()["lab"]
        self.assertTrue(all(self.fake.objs[n]["internal"] for n in lab_["networks"]))
        hosts = [a for a in self.fake.docker_argv() if a[0] == "create" and "--entrypoint" not in a]
        self.assertFalse(any("-p" in a for a in hosts))
        self.assertTrue(all(a[a.index("--add-host") + 1] == "host.docker.internal:host-gateway" for a in hosts))
        self.assertEqual(sorted(self.fake.objs[lab_["driver"]]["nets"]), sorted(lab_["networks"]))
        self.assertTrue(all("port" not in h for h in lab_["hosts"].values()))

    def test_proved_only_when_every_lateral_probe_is_denied_and_the_driver_reaches_hosts(self):
        self.setup_lab("--n3")
        driver = self.m()["lab"]["driver"]
        self.fake.probe = lambda cid, t: "open" if cid == driver else "denied: [Errno 101] unreachable"
        self.assertEqual(lab.main(["n3", str(self.manifest)]), 0)
        self.assertEqual(json.loads((self.state / "lab" / "n3.json").read_text()), {"proved": True, "reasons": []})

    def test_a_refused_lateral_connect_or_a_dead_driver_is_unproved(self):
        self.setup_lab("--n3")
        driver = self.m()["lab"]["driver"]
        for probe, needle in ((lambda cid, t: "open" if cid == driver or t.endswith(":443") else "denied: x",
                               "-> 1.1.1.1:443: open"),
                              (lambda cid, t: "refused" if cid != driver and t.startswith("host.") else
                               "open" if cid == driver else "denied: x", "host.docker.internal:22: refused"),
                              (lambda cid, t: "denied: x", "no positive control"),
                              (lambda cid, t: "open" if cid == driver else "unresolved: [Errno -2] Name or service"
                               if t.startswith("host.") else "denied: x", "host.docker.internal:22: unresolved")):
            with self.subTest(needle=needle):
                self.fake.probe = probe
                self.assertEqual(lab.main(["n3", str(self.manifest)]), 1)
                reasons = json.loads((self.state / "lab" / "n3.json").read_text())["reasons"]
                self.assertTrue(any(needle in r for r in reasons), reasons)

    def test_loopback_setup_reports_n3_unproved(self):
        self.setup_lab()
        self.assertEqual(lab.main(["n3", str(self.manifest)]), 1)
        self.assertIn("loopback", json.loads((self.state / "lab" / "n3.json").read_text())["reasons"][0])


class TeardownTest(Base):
    def setUp(self):
        super().setUp()
        self.other = self.fake.add("container", "agentconnect-web-1")
        self.other_net = self.fake.add("network", "agentconnect_default")
        self.assertEqual(self.setup_lab("--n3"), 0)

    def test_captures_evidence_then_removes_only_manifest_owned_ids(self):
        self.assertEqual(lab.main(["teardown", str(self.manifest)]), 0)
        self.assertEqual(set(self.fake.objs), {self.other, self.other_net})
        ev = self.state / "lab" / "evidence"
        self.assertEqual(sorted(p.name for p in ev.iterdir()),
                         ["driver.inspect.json", "driver.log", "lab-a.inspect.json", "lab-a.log",
                          "lab-b.inspect.json", "lab-b.log", "net-0.inspect.json", "net-1.inspect.json"])
        record = json.loads((self.state / "lab" / "cleanup.json").read_text())
        self.assertEqual((len(record["removed"]), record["sentinel_unchanged"], record["tmux_decoy_alive"]),
                         (5, True, True))
        lab_ = self.m()["lab"]
        ids = set(lab_["networks"]) | {lab_["driver"]} | {h["container"] for h in lab_["hosts"].values()}
        for argv, _ in self.fake.calls:
            self.assertNotIn("prune", argv)
            self.assertNotIn("kill-server", argv)
            if argv[1:2] == ["rm"] or argv[1:3] == ["network", "rm"]:
                self.assertIn(argv[-1], ids)
                self.assertFalse(any("*" in x for x in argv))
        self.assertIn(["tmux", "-S", "/tmp/decoy/s", "kill-session", "-t", "=decoy"],
                      [argv for argv, _ in self.fake.calls])

    def test_owner_or_run_label_mismatch_refuses_before_any_removal(self):
        lab_ = self.m()["lab"]
        for rid, key in ((lab_["hosts"]["lab-b"]["container"], "mdstack.lab.owner"), (lab_["networks"][1],
                                                                                         "mdstack.lab.run")):
            with self.subTest(key=key):
                before, labels = set(self.fake.objs), self.fake.objs[rid]["labels"]
                saved, labels[key] = labels[key], "someone-else"
                self.fake.calls.clear()
                self.assertEqual(lab.main(["teardown", str(self.manifest)]), 2)
                self.assertEqual((self.fake.mutations(), set(self.fake.objs)), ([], before))
                self.assertFalse((self.state / "lab" / "cleanup.json").exists())
                labels[key] = saved

    def test_already_gone_ids_are_noted_not_failed(self):
        self.fake.objs.pop(self.m()["lab"]["driver"])
        self.assertEqual(lab.main(["teardown", str(self.manifest)]), 0)
        self.assertEqual(len(json.loads((self.state / "lab" / "cleanup.json").read_text())["gone"]), 1)

    def test_moved_context_refuses_before_any_removal(self):
        self.fake.endpoint = "unix:///var/run/docker.sock"
        self.fake.calls.clear()
        self.assertEqual(lab.main(["teardown", str(self.manifest)]), 2)
        self.assertEqual(self.fake.mutations(), [])

    def test_changed_sentinel_or_lost_tmux_decoy_fails(self):
        for attr in ("sentinel", "decoy"):
            with self.subTest(attr=attr):
                self.sentinel, self.decoy = (1, True) if attr == "sentinel" else (0, False)
                self.assertEqual(lab.main(["teardown", str(self.manifest)]), 1)


class ProbeTest(unittest.TestCase):
    def probe(self, error):
        out = []
        with mock.patch("socket.create_connection", side_effect=error), \
                mock.patch("sys.argv", ["probe", "host.docker.internal:22"]), mock.patch("builtins.print", out.append):
            exec(lab.PROBE, {})
        return json.loads(out[0])["host.docker.internal:22"]

    def test_only_a_network_error_counts_as_denied(self):
        import socket
        self.assertTrue(self.probe(socket.gaierror(-2, "Name or service not known")).startswith("unresolved:"))
        self.assertEqual(self.probe(ConnectionRefusedError()), "refused")
        self.assertTrue(self.probe(OSError(101, "Network is unreachable")).startswith("denied:"))


if __name__ == "__main__":
    unittest.main()
