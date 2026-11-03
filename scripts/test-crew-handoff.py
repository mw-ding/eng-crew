#!/usr/bin/env python3
"""Tests for crew handoff: owner chat commands post draining, aborted or takeover only on a legal transition.

Fake gh serves the control item comments and default-branch head and records each post (stdlib only). Run in CI.
"""
import json
import os
from pathlib import Path
import re
import unittest
from crew_testlib import Base

SIGN = "— 🔥 Ash (Coordinator) · Claude Code · claude-opus-5-5"


def marker(state, from_="none", to="tmux@local", id_="20261101-abcdef"):
    return {"user": {"login": "acme-bot"}, "body": "<!-- crew:v1 role=coordinator pass=handoff handoff=%s state=%s "
            "from=%s to=%s cmd-id=chat sha=%s round=n/a verdict=n/a -->" % (id_, state, from_, to, "1" * 40)}


class Handoff(Base):
    def setUp(self):
        super().setUp()
        p = Path(self.project)
        p.write_text(p.read_text().replace('[repo]\n', '[repo]\ncontrol_item = 99\n').replace(
            '[runtime]\n', '[runtime]\ninstance = "local"\n'))
        self.comments, self.posts = Path(self.tmp) / "comments.json", Path(self.tmp) / "posts.txt"
        gh = Path(self.tmp) / "bin" / "gh"
        gh.write_text('#!/usr/bin/env python3\nimport os, sys\na = sys.argv[1:]\n'
                      'if a[:2] == ["issue", "comment"]:\n'
                      '    open(os.environ["POSTS"], "a").write(" ".join(a) + "\\n" + sys.stdin.read())\n'
                      'elif "commits/HEAD" in a[1]:\n    print("2" * 40)\n'
                      'else:\n    print(open(os.environ["COMMENTS"]).read())\n')
        gh.chmod(0o755)
        self.env.update(COMMENTS=str(self.comments), POSTS=str(self.posts))

    def handoff(self, *args, record=()):
        self.comments.write_text(json.dumps([list(record)]))
        return self.crew("handoff", *args, "--sign", SIGN, "--project", self.project)

    def test_owner_hands_off_with_drain_deadline(self):
        r = self.handoff("to", "grok-bot@box", "--deadline", "45", record=[marker("claimed")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        post = self.posts.read_text()
        self.assertIn("issue comment 99 -R acme/widgets --body-file -", post)
        self.assertRegex(post, r"\[Ash/handoff\] draining tmux@local → grok-bot@box \(\d{8}-[0-9a-f]{6}\)\n"
                               r"Owner command \(chat\): handoff to grok-bot@box, mode drain, deadline 45 min")
        self.assertIn("state=draining from=tmux@local to=grok-bot@box cmd-id=chat sha=" + "2" * 40, post)
        self.assertTrue(post.rstrip().endswith(SIGN))
        self.assertFalse(re.search(r"^/crew", post, re.M))
        ask = json.loads(Path(self.state, "asks", "handoff.json").read_text())
        self.assertIn(ask["handoff"], post)
        self.assertIn(ask["deadline"][:16], post)

    def test_stop_mode_has_no_deadline_and_dry_run_posts_nothing(self):
        r = self.handoff("to", "grok-bot@box", "--mode", "stop", "--dry-run", record=[marker("claimed")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("mode stop.", r.stdout)
        self.assertFalse(self.posts.exists() or Path(self.state, "asks").exists())

    def test_refuses_illegal_transitions_without_posting(self):
        drain = marker("draining", "tmux@local", "grok-bot@box")
        for args, record in [(("to", "grok-bot@box"), [marker("claimed", to="grok-bot@box")]),  # not the owner
                             (("to", "grok-bot@box"), [marker("claimed"), drain]),  # one open handoff
                             (("to", "tmux@local"), [marker("claimed")]),
                             (("to", "Bad"), [marker("claimed")]),
                             (("abort",), [marker("claimed")]),
                             (("takeover", "grok-bot@box"), [marker("claimed")])]:
            r = self.handoff(*args, record=record)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("refusing", r.stdout)
        self.env["COMMENTS"] = "/missing"
        self.assertEqual(self.crew("handoff", "abort", "--sign", SIGN, "--project", self.project).returncode, 1)
        self.assertFalse(self.posts.exists())

    def test_abort_closes_the_open_handoff_and_drops_the_deadline(self):
        self.put("asks/handoff.json", '{"deadline": "2026-11-03T08:00:00+00:00"}')
        r = self.handoff("abort", record=[marker("claimed"), marker("draining", "tmux@local", "grok-bot@box")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("handoff=20261101-abcdef state=aborted from=tmux@local to=grok-bot@box", self.posts.read_text())
        self.assertFalse(Path(self.state, "asks", "handoff.json").exists())

    def test_takeover_new_or_reusing_the_open_id(self):
        r = self.handoff("takeover", "grok-bot@box", record=[marker("claimed", to="grok-bot@box")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("state=takeover from=grok-bot@box to=tmux@local", self.posts.read_text())
        self.posts.unlink()
        offered = [marker("claimed", to="grok-bot@box"), marker("draining", "grok-bot@box", "tmux@local"),
                   marker("offered", "grok-bot@box", "tmux@local")]
        self.assertEqual(self.handoff("takeover", "grok-bot@box", record=offered).returncode, 0)
        self.assertIn("handoff=20261101-abcdef state=takeover", self.posts.read_text())
        self.posts.unlink()
        r = self.handoff("abort", record=offered + [marker("takeover", "grok-bot@box", "tmux@local")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("state=aborted from=grok-bot@box to=tmux@local", self.posts.read_text())

    def test_guard_keeps_draining_coordinator_until_runs_end(self):
        self.put("runs/ben-7.json", "{}")
        for record, blocked in [([marker("claimed"), marker("draining", "tmux@local", "grok-bot@box")], True),
                                ([marker("claimed", to="grok-bot@box")], False)]:
            self.comments.write_text(json.dumps([record]))
            r = self.crew("guard", "--state", self.state, stdin='{"stop_hook_active": false}',
                          CREW_ROLE="coordinator", CREW_PROJECT=self.project)
            self.assertEqual(bool(r.stdout.strip()) and json.loads(r.stdout).get("decision") == "block", blocked)


if __name__ == "__main__":
    unittest.main()
