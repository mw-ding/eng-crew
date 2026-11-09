"""Tests for mdstack attach, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: read-only by default, by role, the builders view leaves the layout unchanged, unknown
window and missing session refused, and a run on a role host through `ssh -t` and `capture` (#348).
Run in CI.
"""
import json
import os
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import ObserveBase


class Attach(ObserveBase):
    def attach(self, *args):
        return self.crew("attach", *args, "--project", self.project)

    def attaches(self):
        return [c for c in self.calls() if c[0] == "attach-session"]

    def test_attach_window_read_only_by_default(self):
        r = self.attach("ben-7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.attaches(), [["attach-session", "-r", "-t", "=crew-acme-widgets:10"]])
        self.assertEqual(self.attach("ben-8", "--rw").returncode, 0)
        self.assertEqual(self.attaches()[1], ["attach-session", "-t", "=crew-acme-widgets:11"])

    def test_attach_by_role(self):
        for role, index in [("reviewer", 20), ("coordinator", 0), ("synthesizer", 1)]:
            self.assertEqual(self.attach(role).returncode, 0, role)
            self.assertEqual(self.attaches()[-1], ["attach-session", "-r", "-t", "=crew-acme-widgets:%d" % index])
        r = self.attach("builder")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ben-7, ben-8", r.stdout)
        self.assertEqual(len(self.attaches()), 3)

    def test_attach_team_window_0_by_name_alias_or_role(self):  # #1329
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('owners = ["acme-owner"]\n', 'owners = ["acme-owner"]\nteam = "mdp-m4"\n'))
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": dict(self.session, **{"0": "ash-mdp-m4"})}, f)
        for target in ("ash-mdp-m4", "ash", "coordinator"):
            self.assertEqual(self.attach(target).returncode, 0, target)
            self.assertEqual(self.attaches()[-1], ["attach-session", "-r", "-t", "=crew-acme-widgets:0"])

    def test_attach_refuses_unknown_window_and_missing_session(self):
        r = self.attach("ben-99")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no window ben-99", r.stdout)
        os.remove(self.state_file)
        r = self.attach("ben-7")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not running", r.stdout)
        self.assertEqual(self.attaches(), [])

    def test_attach_builders_temporary_tiled_view_keeps_layout(self):
        r = self.attach("builders")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        calls = self.calls()
        new = [c for c in calls if c[0] == "new-session"]
        self.assertEqual(len(new), 1)
        view = new[0][new[0].index("-s") + 1]
        self.assertTrue(view.startswith("crew-acme-widgets-builders-"), view)
        splits = [c for c in calls if c[0] == "split-window"]
        self.assertEqual(len(splits), 1)
        self.assertIn("capture-pane -p -t '=crew-acme-widgets:10' ", new[0][-1])
        self.assertIn("capture-pane -p -t '=crew-acme-widgets:11' ", splits[0][-1])
        self.assertIn(["select-layout", "-t", "=%s:" % view, "tiled"], calls)
        self.assertEqual(self.attaches(), [["attach-session", "-r", "-t", "=" + view]])
        self.assertEqual(calls[-1], ["kill-session", "-t", "=" + view])
        crew_targets = [c for c in calls if "-t" in c and c[c.index("-t") + 1].startswith("=crew-acme-widgets")
                        and not c[c.index("-t") + 1].startswith("=" + view)]
        self.assertEqual({c[0] for c in crew_targets}, {"has-session", "list-windows"})
        with open(self.state_file) as f:
            self.assertEqual(json.load(f), {"crew-acme-widgets": self.session})

    def test_attach_builders_without_builders(self):
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash"}}, f)
        r = self.attach("builders")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no builder windows", r.stdout)
        self.assertEqual([c for c in self.calls() if c[0] in ("new-session", "attach-session")], [])


class AttachRemote(ObserveBase):  # #348: a run on a role host, through its host's attach and capture verbs
    def attach(self, *args, **env):
        return self.crew("attach", *args, "--project", self.project, **env)

    def attaches(self):
        return [c for c in self.calls() if c[0] == "attach-session"]

    def test_attach_remote_window_over_ssh_tty(self):
        self.remote_run("ben-12")
        os.remove(self.state_file)  # no local session needed for a remote run
        r = self.attach("ben-12")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.attach("ben-12", "--rw").returncode, 0)
        calls = self.ssh_calls()
        self.assertEqual([(c["request"]["verb"], c["request"]["window"], c["request"]["rw"]) for c in calls],
                         [("attach", "ben-12", False), ("attach", "ben-12", True)])
        self.assertEqual(calls[0]["request"]["project"], "acme__widgets")
        self.assertIn("-t", calls[0]["argv"])
        self.assertNotIn("-T", calls[0]["argv"])
        self.assertTrue(calls[0]["argv"][-1].startswith("crew-host "))
        r = self.attach("ben-12", FAKE_SSH_EXIT="255")
        self.assertEqual(r.returncode, 255)
        self.assertIn("crew: host-b unreachable", r.stdout)

    def test_attach_role_counts_remote_runs(self):
        self.remote_run("ben-12")
        r = self.attach("builder")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ben-7, ben-8, ben-12", r.stdout)
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash"}}, f)
        self.assertEqual(self.attach("builder").returncode, 0)
        self.assertEqual([c["request"]["window"] for c in self.ssh_calls()], ["ben-12"])
        self.assertEqual(self.attaches(), [])

    def test_attach_builders_adds_a_capture_pane_per_remote_builder(self):
        self.remote_run("ben-12")
        self.remote_run("vera-13", role="reviewer")
        r = self.attach("builders")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        splits = [c for c in self.calls() if c[0] == "split-window"]
        self.assertEqual(len(splits), 2)
        self.assertIn("attach ben-12 --capture --project %s" % self.project, splits[1][-1])
        self.assertIn("'ben-12 on host-b'", splits[1][-1])
        self.assertIn("sleep 15", splits[1][-1])
        self.assertNotIn("vera-13", json.dumps(self.calls()))
        self.assertEqual(self.ssh_calls(), [])  # the view's pane polls; opening it calls no host

    def test_capture_prints_the_remote_pane_once(self):
        self.remote_run("ben-12", capture=dict(result="ok", text="$ make test\nok"))
        r = self.attach("ben-12", "--capture")
        self.assertEqual((r.returncode, r.stdout), (0, "$ make test\nok\n"))
        self.assertEqual(self.ssh_calls()[0]["request"]["verb"], "capture")
        self.remote_run("ben-12", capture=dict(result="refused", reason="no run ben-12 on this host"))
        r = self.attach("ben-12", "--capture")
        self.assertEqual((r.returncode, r.stdout), (1, "crew: host-b refused: no run ben-12 on this host\n"))
        r = self.attach("ben-7", "--capture")
        self.assertEqual((r.returncode, r.stdout), (1, "crew: no remote run ben-7\n"))


if __name__ == "__main__":
    unittest.main()
