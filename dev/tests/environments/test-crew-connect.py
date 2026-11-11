"""`mdstack connect` with fake transports that print their argv; no network, no real host."""
import json
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base

HOSTS = """
[hosts.host-a]
primary = true
max_runs = 2
capabilities = { os = "linux", arch = "x86_64", engines = ["claude-code"] }
[hosts.host-b]
max_runs = 3
capabilities = { os = "linux", arch = "x86_64", engines = ["codex"] }
connect = { alias = "b", transport = "mosh", proxy = "corp-proxy %h %p", options = ["--predict=always"] }
[hosts.host-c]
forge = false
max_runs = 1
capabilities = { os = "macos", arch = "arm64" }
connect = { alias = "c", transport = "et", options = ["-p", "2022"] }
"""


class Connect(Base):
    def setUp(self):
        super().setUp()
        with open(self.project, "a") as f:
            f.write(HOSTS)
        for tool in ("ssh", "mosh", "et"):
            path = os.path.join(self.tmp, "bin", tool)
            with open(path, "w") as f:
                f.write('#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv))\n')
            os.chmod(path, 0o755)

    def connect(self, *args):
        r = self.crew("connect", "--project", self.project, *args)
        return r, (json.loads(r.stdout) if r.returncode == 0 else None)

    def test_ssh_default_plain_shell_and_session(self):
        r, argv = self.connect("host-a")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(argv[1:], ["host-a"])
        self.assertTrue(argv[0].endswith("/ssh"))
        _, argv = self.connect("host-a", "work")
        self.assertEqual(argv[1:], ["-t", "host-a", "tmux", "new-session", "-A", "-s", "work"])

    def test_alias_proxy_options_and_passthrough(self):
        _, argv = self.connect("b", "work", "--", "-L", "8080:localhost:8080")
        self.assertEqual(argv[1:], ["--ssh=ssh -o ProxyCommand='corp-proxy %h %p'", "--experimental-remote-ip=remote",
                                    "--predict=always", "-L",
                                    "8080:localhost:8080", "host-b", "--", "tmux", "new-session", "-A", "-s", "work"])
        _, argv = self.connect("host-b", "-v")
        self.assertEqual(argv[1:], ["--ssh=ssh -o ProxyCommand='corp-proxy %h %p'", "--experimental-remote-ip=remote",
                                    "--predict=always", "-v", "host-b"])

    def test_et_session_and_ssh_proxy(self):
        _, argv = self.connect("c", "work")
        self.assertEqual(argv[1:], ["-p", "2022", "host-c", "-c", "tmux new-session -A -s work"])
        with open(self.project, "a") as f:
            f.write('[hosts.host-a.connect]\nproxy = "corp-proxy %h %p"\n')
        _, argv = self.connect("host-a")
        self.assertEqual(argv[1:], ["-o", "ProxyCommand=corp-proxy %h %p", "host-a"])

    def test_address_is_the_destination_for_every_transport(self):
        with open(self.project) as f:
            text = f.read()
        for host in ("host-a", "host-b", "host-c"):
            text = text.replace("[hosts.%s]\n" % host, '[hosts.%s]\naddress = "%s.region.example.com"\n' % (host, host))
        with open(self.project, "w") as f:
            f.write(text)
        _, argv = self.connect("host-a")
        self.assertEqual(argv[1:], ["host-a.region.example.com"])
        _, argv = self.connect("host-a", "work", "--", "-L", "8080:localhost:8080")
        self.assertEqual(argv[1:], ["-L", "8080:localhost:8080", "-t", "host-a.region.example.com",
                                    "tmux", "new-session", "-A", "-s", "work"])
        _, argv = self.connect("b", "work")
        self.assertEqual(argv[1:], ["--ssh=ssh -o ProxyCommand='corp-proxy %h %p'", "--experimental-remote-ip=remote",
                                    "--predict=always", "host-b.region.example.com",
                                    "--", "tmux", "new-session", "-A", "-s", "work"])
        _, argv = self.connect("host-b")
        self.assertEqual(argv[-1], "host-b.region.example.com")
        _, argv = self.connect("c", "work")
        self.assertEqual(argv[1:], ["-p", "2022", "host-c.region.example.com", "-c", "tmux new-session -A -s work"])
        _, argv = self.connect("c")
        self.assertEqual(argv[1:], ["-p", "2022", "host-c.region.example.com"])
        r, _ = self.connect("host-c.region.example.com")
        self.assertEqual(r.returncode, 1)  # the address is the destination, never a lookup key

    def test_unknown_alias_lists_known(self):
        r, _ = self.connect("nope")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "crew connect: unknown host alias nope; known: b, c, host-a, host-b, host-c")

    def test_bad_session_name(self):
        r, _ = self.connect("b", "a.b")
        self.assertEqual(r.returncode, 1)
        self.assertIn("session name 'a.b'", r.stdout)


if __name__ == "__main__":
    unittest.main()
