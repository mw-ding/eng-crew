"""Tests for crew acked (and send --wait-ack), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import os
import subprocess
import sys
import textwrap
import unittest
from crew_testlib import SendBase


class Acked(SendBase):
    def test_ack_only_from_status_file(self):
        r = self.crew("send", "ben-7", "fix", "#1", "--wait-ack", "0.3", "--project", self.project)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        msg_id = self.inbox()[0]["id"]
        self.assertIn("no ack: " + msg_id, r.stdout)
        acked = ["acked", "ben-7", msg_id, "--project", self.project]
        self.assertEqual(self.crew(*acked).returncode, 3)
        self.put("status/ben-7.status", "ack: other-id #1\ndone: #1 inbox: %s\n" % msg_id)
        self.assertEqual(self.crew(*acked).returncode, 3)
        self.put("status/ben-7.status", "done: #1\nack: %s #1\n" % msg_id)
        r = self.crew(*acked)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("acked " + msg_id, r.stdout)

    def test_wait_ack_sees_late_ack(self):
        status = os.path.join(self.state, "status", "ben-7.status")
        os.makedirs(os.path.dirname(status), exist_ok=True)
        # A stand-in role: acks whatever id lands in the inbox, a moment after the send.
        role = subprocess.Popen([sys.executable, "-c", textwrap.dedent("""\
            import json, os, sys, time
            inbox, status = sys.argv[1:]
            while not os.path.exists(inbox):
                time.sleep(0.05)
            time.sleep(0.3)
            open(status, "a").write("ack: %s\\n" % json.loads(open(inbox).readline())["id"])
            """), os.path.join(self.state, "inbox", "ben-7.jsonl"), status])
        self.addCleanup(role.wait)
        r = self.crew("send", "ben-7", "review", "#9", "--wait-ack", "10", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("acked " + self.inbox()[0]["id"], r.stdout)


if __name__ == "__main__":
    unittest.main()
