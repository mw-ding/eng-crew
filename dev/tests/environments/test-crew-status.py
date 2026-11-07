"""Tests for mdstack status (and the C5 probe), moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers `mdstack status` and the probe with a fake `ps`: each probe class (a same-name window probes `missing`), the
status table, a trust dialog and the Codex hooks dialog probe `ambiguous`; captured screens in `fixtures/dialog/`:
Codex approval and folder trust, Claude Code permission and trust prompts and fatal API errors probe `ambiguous`,
working screens that quote the same text stay `alive`. Run in CI.
"""
import json
import os
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import LivenessBase, screen, STUCK, WORKING


class Status(LivenessBase):
    def test_cursor_bundled_node_start_probe_and_unrelated_node(self):
        binary = os.path.join(self.tmp, "bin", "cursor-agent")
        with open(binary, "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(binary, 0o755)
        directory = os.path.dirname(os.path.realpath(binary))
        argv = directory + "/node " + directory + "/index.js --force"
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["cursor/composer-1"]\n')
        self.env["FAKE_TMUX_PANE"] = "node"
        with open(self.ps, "w") as f:
            json.dump({"argv": {"/dev/ttyp11": [["S+", argv]]}}, f)
        result = self.spawn("builder", "--issue", "8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.probe("ben-8"), "alive")
        for stat, command in (("S", argv), ("S+", "node unrelated.js"),
                              ("S+", directory + "/node /other/index.js")):
            with open(self.ps, "w") as f:
                json.dump({"argv": {"/dev/ttyp11": [[stat, command]]}}, f)
            self.assertEqual(self.probe("ben-8"), "ambiguous")

    def test_cursor_create_probe_delete(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["cursor/composer-1"]\n')
        created = self.spawn("builder", "--issue", "8")
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        rec = self.record("ben-8")
        ready = self.probe("ben-8")
        self.assertEqual(ready, "alive")
        self.set_pane(11, command="node")
        self.assertEqual(self.probe("ben-8"), "ambiguous")
        self.set_pane(11, command="cursor-agent")
        deleted = self.crew("kill", "ben-8", "--project", self.project)
        self.assertEqual(deleted.returncode, 0, deleted.stdout + deleted.stderr)
        for path in (rec["worktree"], rec["claim"], os.path.join(self.state, "runs", "ben-8.json")):
            self.assertFalse(os.path.exists(path), path)
        print("mdstack spawn builder --issue 8: exit=0 engine=cursor harness=cursor-agent")
        print("probe ben-8: cursor-agent=alive node=ambiguous")
        print("mdstack kill ben-8: exit=0 worktree=false claim=false run=false")

    def test_cursor_probe_requires_pi_foreground_and_preserves_identity_checks(self):
        path = os.path.join(self.state, "runs", "ben-7.json")
        rec = self.record("ben-7")
        rec.update(engine="cursor", harness="cursor-agent")
        with open(path, "w") as f:
            json.dump(rec, f)
        for command, want in (("cursor-agent", "alive"), ("node", "ambiguous"), ("zsh", "ambiguous")):
            self.set_pane(10, command=command)
            self.assertEqual(self.probe(), want)
        with open(self.ps, "w") as f:
            json.dump({"fg": {"/dev/ttyp10": [["S+", "cursor-agent"]]}}, f)
        self.assertEqual(self.probe(), "alive")
        self.set_pane(10, command="cursor-agent", dead="1")
        self.assertEqual(self.probe(), "dead")
        self.set_pane(10, command="cursor-agent", pid="123")
        self.assertEqual(self.probe(), "missing")

    def test_pi_create_probe_delete(self):
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["pi/anthropic/claude-sonnet-4-5"]\n')
        created = self.spawn("builder", "--issue", "8")
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        rec = self.record("ben-8")
        ready = self.probe("ben-8")
        self.assertEqual(ready, "alive")
        self.set_pane(11, command="node")
        self.assertEqual(self.probe("ben-8"), "ambiguous")
        self.set_pane(11, command="pi")
        deleted = self.crew("kill", "ben-8", "--project", self.project)
        self.assertEqual(deleted.returncode, 0, deleted.stdout + deleted.stderr)
        for path in (rec["worktree"], rec["claim"], os.path.join(self.state, "runs", "ben-8.json")):
            self.assertFalse(os.path.exists(path), path)
        print("mdstack spawn builder --issue 8: exit=0 engine=pi harness=pi")
        print("probe ben-8: pi=alive node=ambiguous")
        print("mdstack kill ben-8: exit=0 worktree=false claim=false run=false")

    def test_pi_probe_requires_pi_foreground_and_preserves_identity_checks(self):
        path = os.path.join(self.state, "runs", "ben-7.json")
        rec = self.record("ben-7")
        rec.update(engine="pi", harness="pi")
        with open(path, "w") as f:
            json.dump(rec, f)
        for command, want in (("pi", "alive"), ("node", "ambiguous"), ("zsh", "ambiguous")):
            self.set_pane(10, command=command)
            self.assertEqual(self.probe(), want)
        with open(self.ps, "w") as f:
            json.dump({"fg": {"/dev/ttyp10": [["S+", "pi"]]}}, f)
        self.assertEqual(self.probe(), "alive")
        self.set_pane(10, command="pi", dead="1")
        self.assertEqual(self.probe(), "dead")
        self.set_pane(10, command="pi", pid="123")
        self.assertEqual(self.probe(), "missing")

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
        dialog = "Do you trust the files in this folder?\n> 1. Yes, proceed\n  2. No, exit\nEnter to confirm · Esc to cancel"
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
        self.set_pane(10, screen="Hooks need review\n> 1. Review hooks\n  2. Continue without hooks\n"
                               "enter confirm · esc skip")
        self.assertEqual(self.probe(), "ambiguous")

    def test_quoted_trust_and_hooks_prompts_stay_alive(self):
        prompts = ["Do you trust the files in this folder?\nNo, exit\nEnter to confirm · Esc to cancel",
                   "Hooks need review\nenter confirm · esc skip"]
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.set_pane(10, screen=prompt)
                self.assertEqual(self.probe(), "ambiguous")
                self.set_pane(10, screen=prompt + "\n❯\n? for shortcuts")
                self.assertEqual(self.probe(), "alive")
        self.set_pane(10, screen="Tool output mentions trust and No, exit\nEnter to confirm · Esc to cancel")
        self.assertEqual(self.probe(), "alive")

    def test_stuck_screens_are_ambiguous_working_screens_alive(self):  # #289
        for name, want in [(n, "ambiguous") for n in STUCK] + [(n, "alive") for n in WORKING]:
            with self.subTest(name):
                self.set_pane(10, screen=screen(name))
                self.assertEqual(self.probe(), want)

    def test_status_shows_a_stuck_coordinator_and_role_ambiguous(self):  # #289
        with open(self.panes, "w") as f:
            json.dump({"crew-acme-widgets:0": {"command": "claude", "screen": screen("claude-proceed")},
                       "crew-acme-widgets:10": {"screen": screen("codex-approval")}}, f)
        rows = self.crew("status", "--project", self.project).stdout.splitlines()
        self.assertEqual((rows[1].split()[5], rows[2].split()[6]), ("ambiguous", "ambiguous"))


if __name__ == "__main__":
    unittest.main()
