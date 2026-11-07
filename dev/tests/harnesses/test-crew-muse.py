"""Muse adapter tests using fake binaries and the tmux lifecycle fixtures."""
import json
import os
from pathlib import Path
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, LivenessBase, SECRET, SpawnBase


def muse_fakes(test):
    binary = Path(test.tmp, "bin", "muse")
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    gh = binary.with_name("gh")
    text = gh.read_text().replace("args = sys.argv[1:]\n", "args = sys.argv[1:]\n"
        "if args[0] == 'api':\n"
        " print(os.environ.get('FAKE_MUSE_VISIBILITY', '{\"private\": false}'))\n"
        " sys.exit(int(os.environ.get('FAKE_MUSE_API_EXIT', '0')))\n")
    gh.write_text(text)


class Workers(SpawnBase):
    def setUp(self):
        super().setUp()
        muse_fakes(self)
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["muse/default", "codex/gpt-6.1-sol"]\n')

    def test_all_roles_launch_with_model_effort_and_pointer(self):
        self.pr(9, "codex gpt-6.1-sol medium")
        self.env["FAKE_TMUX_PANE"] = "muse-bin-0.1.0-R708.1"
        for role, ref, name in (("builder", "--issue", "ben-7"),
                                ("reviewer", "--pr", "vera-9-r1-review"),
                                ("synthesizer", "--pr", "sam")):
            result = self.spawn(role, ref, "7" if role == "builder" else "9")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            launch = self.windows()[-1][-1]
            self.assertTrue(launch.endswith('exec muse --yolo --model default --reasoning-effort medium '
                                           '"Read your brief at $CREW_BRIEF and follow it."'), launch)
            self.assertNotIn(SECRET, launch)
            self.assertEqual(self.record(name)["harness"], "muse")

    def test_private_or_unreadable_visibility_refuses_and_cleans_up(self):
        for visibility, code in (('{"private": true}', "0"), ('{}', "0"), ('invalid', "0"),
                                 ('{"private": false}', "1")):
            with self.subTest(visibility=visibility, code=code):
                self.env.update(FAKE_MUSE_VISIBILITY=visibility, FAKE_MUSE_API_EXIT=code)
                result = self.spawn("builder", "--issue", "7")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("verified public repository", result.stdout)
                self.assertEqual(self.windows(), [])
                self.assertFalse(Path(self.state, "claims", "builder-issue7").exists())
                self.assertFalse(Path(self.state, "runs", "ben-7.json").exists())

    def test_unsupported_modes_refuse_and_clean_up(self):
        for mode in ("safe", "auto"):
            self.write_profile()
            with open(self.project, "a") as f:
                f.write('\n[engines.default]\norder = ["muse/default"]\n'
                        '\n[runtime.options]\npermission_mode = "%s"\n' % mode)
            result = self.spawn("builder", "--issue", "7")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Muse supports only permission_mode=bypass", result.stdout)
            self.assertFalse(Path(self.state, "claims", "builder-issue7").exists())
            self.assertFalse(Path(self.state, "runs", "ben-7.json").exists())
            self.assertEqual(self.windows(), [])

    def test_muse_builder_excluded_from_review(self):
        self.pr(9, "muse default medium")
        result = self.spawn("reviewer", "--pr", "9")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.record("vera-9-r1-review")["engine"], "codex")


class Coordinator(Base):
    def setUp(self):
        super().setUp()
        muse_fakes(self)
        self.write_profile(engine="muse")

    def test_launch_keeps_configured_model_and_effort(self):
        result = self.up()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.new_session()[-1].endswith(
            'exec muse --yolo "Read your brief at $CREW_BRIEF and follow it."'))
        self.assertFalse(Path(self.project_dir, ".claude").exists())

    def test_private_and_unsupported_modes_refuse_before_session(self):
        self.env["FAKE_MUSE_VISIBILITY"] = '{"private": true}'
        self.assertEqual(self.up().returncode, 1)
        self.env["FAKE_MUSE_VISIBILITY"] = '{"private": false}'
        for mode in ("safe", "auto"):
            self.write_profile(engine="muse")
            with open(self.project, "a") as f:
                f.write('\n[runtime.options]\npermission_mode = "%s"\n' % mode)
            result = self.up()
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("Muse supports only permission_mode=bypass", result.stdout)
        self.assertFalse(any(c[0] == "new-session" for c in self.calls()))


class Probe(LivenessBase):
    def test_create_probe_complete_delete(self):
        muse_fakes(self)
        with open(self.project, "a") as f:
            f.write('\n[engines.default]\norder = ["muse/default"]\n')
        self.env["FAKE_TMUX_PANE"] = "muse-bin-0.1.0-R708.1"
        result = self.spawn("builder", "--issue", "8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rec = self.record("ben-8")
        self.assertEqual(self.probe("ben-8"), "alive")
        for command in ("node", "not-muse-bin-1", "muse-bin-"):
            self.set_pane(11, command=command)
            self.assertEqual(self.probe("ben-8"), "ambiguous")
        self.set_pane(11, command="muse")
        for screen in ('Do you trust this workspace?\n> 1 Trust and continue\n'
                       'Use Up/Down or 1/2, then Enter. Esc quits.',
                       'Sign in at this page:\nhttps://example.invalid/device\nWaiting for approval…\nEsc cancel'):
            self.set_pane(11, command="muse", screen=screen)
            self.assertEqual(self.probe("ben-8"), "ambiguous")
        self.set_pane(11, command="muse-bin-0.1.0-R708.1")
        self.put("status/ben-8.status", "done: #8 #9 " + rec["head"] + "\n")
        self.assertEqual(self.probe("ben-8"), "alive")
        result = self.crew("kill", "ben-8", "--project", self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in (rec["worktree"], rec["claim"], Path(self.state, "runs", "ben-8.json")):
            self.assertFalse(os.path.exists(path), path)
        print("Muse fake lifecycle: create=0 versioned-probe=alive unrelated=ambiguous")
        print("trust/login=ambiguous complete=done kill=0 worktree/claim/run=removed")

    def test_versioned_foreground_preserves_identity_and_dead_checks(self):
        rec = self.record("ben-7")
        rec.update(engine="muse", harness="muse")
        self.put("runs/ben-7.json", json.dumps(rec))
        self.set_pane(10, command="zsh")
        with open(self.ps, "w") as f:
            json.dump({"fg": {"/dev/ttyp10": [["S+", "muse-bin-0.1.0"]]}}, f)
        self.assertEqual(self.probe(), "alive")
        self.set_pane(10, command="muse", dead="1")
        self.assertEqual(self.probe(), "dead")
        self.set_pane(10, command="muse", pid="123")
        self.assertEqual(self.probe(), "missing")


if __name__ == "__main__":
    unittest.main()
