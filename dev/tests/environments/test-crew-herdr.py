"""Local herdr adapter tests: fake binary, profile dispatch, lifecycle, identity, input and isolation.

Run with python3 dev/tests/environments/test-crew-herdr.py. No real server or harness is started.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import textwrap
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import CREW, SECRET, SpawnBase


FAKE = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    from pathlib import Path
    args = sys.argv[1:]
    path = Path(os.environ["FAKE_HERDR_STATE"])
    state = json.loads(path.read_text()) if path.exists() else {"workspaces": [], "next": 1}
    with open(os.environ["FAKE_HERDR_LOG"], "a") as f:
        f.write(json.dumps(args) + "\\n")
    if not args:
        sys.exit(0)
    if os.environ.get("HERDR_FAIL") == " ".join(args[:2]):
        print("server unavailable", file=sys.stderr)
        sys.exit(1)
    result = {}
    if args[:2] == ["workspace", "list"]:
        result["workspaces"] = state["workspaces"]
    elif args[:2] == ["workspace", "create"]:
        n = state["next"]
        state["next"] += 1
        w = {"workspace_id": "w" + str(n), "label": args[args.index("--label") + 1],
             "pane_id": "w%d:p1" % n, "terminal_id": "terminal-" + str(n),
             "shell_pid": 9000000 + n, "screen": "› ", "command": "claude"}
        state["workspaces"].append(w)
        result["workspace"] = w
    elif args[:2] == ["workspace", "close"]:
        state["workspaces"] = [w for w in state["workspaces"] if w["workspace_id"] != args[2]]
    elif args[:2] == ["pane", "list"]:
        result["panes"] = [w for w in state["workspaces"] if w["workspace_id"] == args[3]]
    elif args[0] == "pane":
        target = args[3] if args[1] == "process-info" else args[2]
        w = next(w for w in state["workspaces"] if w["pane_id"] == target)
        if args[1] == "get":
            result["pane"] = w
        elif args[1] == "process-info":
            result["process_info"] = {"pane_id": target, "foreground_processes": [{"name": w["command"]}]}
            if "shell_pid" in w:
                result["process_info"]["shell_pid"] = w["shell_pid"]
        elif args[1] == "read":
            print(w["screen"])
            sys.exit(0)
        elif args[1] == "run":
            w["command"] = "codex" if "exec codex" in args[3] else "claude"
        elif args[1] == "send-text":
            w["screen"] = "› " + args[3]
        elif args[1] == "send-keys" and not os.environ.get("HERDR_STUCK"):
            w["screen"] = w["screen"].removeprefix("› ") + "\\n› "
    path.write_text(json.dumps(state))
    if args[:2] not in (["pane", "run"], ["pane", "send-text"], ["pane", "send-keys"]):
        print(json.dumps({"result": result}))
    ''')


class Herdr(SpawnBase):
    def setUp(self):
        super().setUp()
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\nsession_backend = "herdr"\n')
        self.herdr_state = Path(self.tmp) / "herdr.json"
        self.herdr_log = Path(self.tmp) / "herdr.log"
        self.env.update(FAKE_HERDR_STATE=str(self.herdr_state), FAKE_HERDR_LOG=str(self.herdr_log))
        for name, text in [("herdr", FAKE), ("ps", "#!/bin/sh\ncase \"$*\" in *lstart*) echo started;; esac\n")]:
            binary = Path(self.tmp) / "bin" / name
            binary.write_text(text)
            binary.chmod(0o755)
        loader = importlib.machinery.SourceFileLoader("herdr_crew", CREW)
        self.mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("herdr_crew", loader))
        loader.exec_module(self.mod)
        self.mod.tmux.name = "herdr"
        self.backend = self.mod.tmux.backends["herdr"]
        self.assertEqual(self.up().returncode, 0)

    def calls_herdr(self):
        return [json.loads(line) for line in self.herdr_log.read_text().splitlines()]

    def edit(self, **fields):
        state = json.loads(self.herdr_state.read_text())
        state["workspaces"][-1].update(fields)
        self.herdr_state.write_text(json.dumps(state))

    def probe(self, rec):
        with patch.dict(os.environ, self.env):
            return self.mod.probe("crew-acme-widgets", "ben-7", rec, {"ben-7": 10})

    def test_profile_dispatch_create_and_kill(self):
        r = self.spawn("builder", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("ben-7")
        self.assertEqual((rec["pane_id"], rec["pane_start"]), ("terminal-2", "started"))
        self.assertEqual(self.probe(rec), "alive")
        creates = [c for c in self.calls_herdr() if c[:2] == ["workspace", "create"]]
        self.assertEqual(len(creates), 2)
        self.assertIn("--no-focus", creates[-1])
        self.assertEqual(creates[-1][creates[-1].index("--cwd") + 1], rec["worktree"])
        self.assertIn("CREW_IDENTITY=acme-bot", creates[-1])
        self.assertNotIn(SECRET, self.herdr_log.read_text())
        r = self.crew("kill", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(Path(rec["worktree"]).exists())
        self.assertEqual(len(json.loads(self.herdr_state.read_text())["workspaces"]), 1)
        print("herdr lifecycle: created background run, identity alive, killed run; coordinator retained")

    def test_identity_changes_dead_and_unavailable(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        rec = self.record("ben-7")
        self.edit(terminal_id="replacement")
        self.assertEqual(self.probe(rec), "missing")
        self.edit(terminal_id=rec["pane_id"], shell_pid=None)
        self.assertEqual(self.probe(rec), "dead")
        self.env["HERDR_FAIL"] = "pane process-info"
        self.assertEqual(self.probe(rec), "ambiguous")
        self.env.pop("HERDR_FAIL")
        state = json.loads(self.herdr_state.read_text())
        state["workspaces"][-1].pop("shell_pid")
        self.herdr_state.write_text(json.dumps(state))
        self.assertEqual(self.probe(rec), "ambiguous")

    def test_os_start_time_is_required(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        rec = self.record("ben-7")
        rec["pane_start"] = "old"
        self.assertEqual(self.probe(rec), "missing")

    def test_doorbell_submitted_once_or_reported_ambiguous(self):
        with patch.dict(os.environ, self.env), patch.object(self.backend.time, "sleep"):
            nudge = self.mod.commands()["send"].nudge
            self.assertIsNone(nudge("crew-acme-widgets", 0, "wake: watcher"))
            with patch.dict(os.environ, HERDR_STUCK="1"):
                self.assertIn("ambiguous", nudge("crew-acme-widgets", 0, "wake: watcher"))
            self.assertIn("nothing typed", nudge("crew-acme-widgets", 0, "wake: watcher"))
        typed = [c for c in self.calls_herdr() if c[:2] == ["pane", "send-text"]]
        self.assertEqual(len(typed), 2)

    def test_dialog_and_payload_send_no_keys(self):
        self.edit(screen="Would you like to run this command?\nPress enter to confirm or esc to cancel")
        with patch.dict(os.environ, self.env):
            self.assertIn("dialog", self.mod.commands()["send"].nudge("crew-acme-widgets", 0, "wake: watcher"))
            self.assertIn("nothing typed", self.backend.doorbell("crew-acme-widgets", 0, "payload"))
        self.assertFalse(any(c[:2] in (["pane", "send-text"], ["pane", "send-keys"]) for c in self.calls_herdr()))

    def test_send_cli_returns_four_on_unsubmitted_line(self):
        r = self.crew("send", "ash", "build", "#7", "--project", self.project, HERDR_STUCK="1")
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("submission ambiguous", r.stdout)
        self.assertEqual(len([c for c in self.calls_herdr() if c[:2] == ["pane", "send-text"]]), 1)
        self.assertTrue(Path(self.state, "inbox", "ash.jsonl").exists())
        print("herdr doorbell: exit 4 on ambiguous submit; typed once, inbox retained")

    def test_kill_retains_workspace_on_failed_probe_or_survivor(self):
        with patch.dict(os.environ, self.env), patch("crew_shared.stop_pane", return_value=44):
            with self.assertRaisesRegex(RuntimeError, "survived"):
                self.backend.kill_window("crew-acme-widgets", 0)
        with patch.dict(os.environ, dict(self.env, HERDR_FAIL="pane process-info")):
            with self.assertRaisesRegex(RuntimeError, "probe unavailable"):
                self.backend.kill_window("crew-acme-widgets", 0)
        self.assertEqual(len(json.loads(self.herdr_state.read_text())["workspaces"]), 1)

    def test_attach_readonly_never_types_and_rw_is_explicit(self):
        with patch.dict(os.environ, self.env), patch.object(self.backend.time, "sleep", side_effect=KeyboardInterrupt), \
                patch("builtins.print"):
            self.assertEqual(self.backend.attach("=crew-acme-widgets:0"), 0)
        self.assertFalse(any(c[:2] == ["workspace", "focus"] for c in self.calls_herdr()))
        with patch.dict(os.environ, self.env):
            self.assertEqual(self.backend.attach("=crew-acme-widgets:0", read_only=False), 0)
        self.assertIn(["workspace", "focus", "w1"], self.calls_herdr())

    def test_private_environment_and_occupied_index_refused(self):
        with patch.dict(os.environ, self.env):
            with self.assertRaisesRegex(RuntimeError, "private coordinator environment"):
                self.backend.new_session("private", "ash", self.tmp, {}, "claude", private_env={"PRIVATE": "value"})
            with self.assertRaisesRegex(RuntimeError, "occupied"):
                self.backend.new_window("crew-acme-widgets", 0, "other", self.tmp, {}, "claude")
        self.assertEqual(len(json.loads(self.herdr_state.read_text())["workspaces"]), 1)

    def test_profile_rejects_unknown_session_backend(self):
        Path(self.project).write_text(Path(self.project).read_text().replace('session_backend = "herdr"',
                                                                         'session_backend = "unknown"'))
        r = self.up()
        self.assertEqual(r.returncode, 1)
        self.assertIn("runtime.options.session_backend: unknown value", r.stdout)

    def test_launch_failure_cleans_workspace(self):
        with patch.dict(os.environ, dict(self.env, HERDR_FAIL="pane run")):
            with self.assertRaisesRegex(RuntimeError, "server unavailable"):
                self.backend.new_window("crew-acme-widgets", 10, "failed", self.tmp, {}, "codex")
        self.assertEqual(len(json.loads(self.herdr_state.read_text())["workspaces"]), 1)

    def test_upgrade_refused_before_stopping_runs(self):
        before = self.herdr_log.read_text()
        r = self.crew("upgrade", "--project", self.project)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("in-place upgrade unsupported", r.stdout)
        self.assertEqual(self.herdr_log.read_text(), before)


if __name__ == "__main__":
    unittest.main()
