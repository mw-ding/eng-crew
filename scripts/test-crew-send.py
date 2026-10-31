"""Tests for crew send, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import os
import unittest
from crew_testlib import SendBase


class Send(SendBase):
    def test_append_format_and_nudge(self):
        sha = "a" * 40
        r = self.send("ben-7", "fix", "#171", sha, "https://github.com/acme/widgets/pull/171", "docs/x.md")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r2 = self.send("ben-7", "ci-red", "#171")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        first, second = self.inbox()
        self.assertEqual(sorted(first), ["from", "id", "kind", "refs", "ts"])
        self.assertEqual(first["kind"], "fix")
        self.assertEqual(first["refs"], ["#171", sha, "https://github.com/acme/widgets/pull/171", "docs/x.md"])
        self.assertEqual(first["from"], "coordinator")
        self.assertRegex(first["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertNotEqual(first["id"], second["id"])
        self.assertIn("sent %s to ben-7" % first["id"], r.stdout)
        keys = [c for c in self.calls() if c[0] == "send-keys"]
        self.assertEqual(keys[:2], [["send-keys", "-t", "=crew-acme-widgets:10", "-l", "inbox: " + first["id"]],
                                    ["send-keys", "-t", "=crew-acme-widgets:10", "Enter"]])
        self.assertEqual(len(keys), 4)

    def test_oversized_or_payload_rejected(self):
        diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
        for refs in [["p" * 201], ["d/" + "y" * 198] * 5, [diff], ["---a/x"], ["@@"],
                     ["Traceback"], ["two words"], ["#171", "line\nbreak"]]:
            r = self.crew("send", "--project", self.project, "ben-7", "fix", "--", *refs)  # --: refs may start with -
            self.assertEqual(r.returncode, 2, (refs, r.stdout, r.stderr))
            self.assertIn("refusing send", r.stdout)
        self.assertIn("over 1024", self.send("ben-7", "fix", *["d/" + "y" * 198] * 5).stdout)  # each ref legal
        self.assertEqual(self.send("ben-7", "Fix it", "#1").returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-7.jsonl")))
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])

    def test_unknown_window_refused(self):
        r = self.send("ben-8", "fix", "#1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no window ben-8", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-8.jsonl")))
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])


if __name__ == "__main__":
    unittest.main()
