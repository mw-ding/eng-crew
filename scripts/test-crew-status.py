"""Tests for crew status (and the C5 probe), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import json
import os
import unittest
from crew_testlib import LivenessBase


class Status(LivenessBase):
    def test_probe_classes(self):
        self.assertEqual(self.probe(), "alive")
        self.set_pane(10, command="node")
        self.assertEqual(self.probe(), "ambiguous")
        with open(self.ps, "w") as f:
            json.dump({"fg": {"/dev/ttyp10": [["S+", "/usr/local/bin/codex"]]}}, f)
        self.assertEqual(self.probe(), "alive")
        os.remove(self.ps)
        self.set_pane(10, dead="1")
        self.assertEqual(self.probe(), "dead")
        self.set_pane(10)
        with open(self.ps, "w") as f:  # pid reused by another process
            json.dump({"start": {"9000010": "Fri Oct 30 11:00:00 2026"}}, f)
        self.assertEqual(self.probe(), "missing")
        os.remove(self.ps)
        self.set_pane(10, id="%99", pid="9000099")  # a new window with the same name and harness
        self.assertEqual(self.probe(), "missing")
        self.set_pane(10)
        with open(self.state_file) as f:
            state = json.load(f)
        state["crew-acme-widgets"].pop("10")
        with open(self.state_file, "w") as f:
            json.dump(state, f)
        self.assertEqual(self.probe(), "missing")

    def test_status_table(self):
        self.put("status/ben-7.status", "ack: m1\nblocked: needs a decision on #7\n")
        r = self.crew("status", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        head, ash, row = r.stdout.splitlines()
        self.assertEqual(head.split(), ["WINDOW", "ROLE", "ITEM", "HEAD", "BEAT", "LIVENESS", "LAST"])
        self.assertEqual(ash.split(), ["ash", "coordinator", "-", "-", "-", "ambiguous", "-"])  # no harness seen
        base = self.git("rev-parse", "--short=7", "origin/main")
        self.assertEqual(row.split()[:8], ["ben-7", "builder", "issue", "#7", base, "0m", "alive", "blocked:"])

    def test_status_trust_dialog_is_ambiguous(self):
        dialog = "Do you trust the files in this folder?\n> 1. Yes, proceed\n  2. No, exit"
        with open(self.panes, "w") as f:
            json.dump({"crew-acme-widgets:0": {"command": "claude"}, "crew-acme-widgets:10": {}}, f)
        rows = self.crew("status", "--project", self.project).stdout.splitlines()
        self.assertEqual((rows[1].split()[5], rows[2].split()[6]), ("alive", "alive"))
        with open(self.panes, "w") as f:
            json.dump({"crew-acme-widgets:0": {"command": "claude", "screen": dialog},
                       "crew-acme-widgets:10": {"screen": dialog}}, f)
        rows = self.crew("status", "--project", self.project).stdout.splitlines()
        self.assertEqual((rows[1].split()[5], rows[2].split()[6]), ("ambiguous", "ambiguous"))

    def test_codex_hooks_review_dialog_is_ambiguous(self):  # #139 F7
        self.set_pane(10, screen="Hooks need review\n> 1. Review hooks\n  2. Continue without hooks")
        self.assertEqual(self.probe(), "ambiguous")


if __name__ == "__main__":
    unittest.main()
