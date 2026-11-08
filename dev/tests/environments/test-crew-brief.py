"""Tests for mdstack brief (#647): the "This run" block for any runtime; fixtures in crew_testlib.py (stdlib only).

Covers: every field in order, empty values left out, the missing-field refusal (exit 2, nothing printed),
and that mdstack spawn's tmux block is the same helper's output. Run in CI.
"""
import importlib.util
import os
import subprocess
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import CREW, SCRIPTS

spec = importlib.util.spec_from_file_location("brief", os.path.join(os.path.dirname(SCRIPTS), "environments", "terminal", "crew.d", "brief.py"))
brief = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brief)

ALL = [("window", "Window", "ben-7"), ("item", "Item", "issue #7"), ("pass", "Pass", "review"),
       ("round", "Round", "2"), ("slot", "Slot", "3"), ("host", "Host", "cloud-a"),
       ("worktree", "Worktree", "/wt/7-abc1234-builder-build"), ("base", "Base", "a" * 40),
       ("engine", "Engine", "codex gpt-6.1-sol medium"), ("claim", "Claim", "/state/claims/builder-issue7"),
       ("flavor", "Flavor", "standard"), ("comments", "Comments", "PRR_1, PRR_2")]
REQUIRED = ["--item", "issue #7", "--pass", "build", "--base", "a" * 40]


def crew(*args):
    return subprocess.run([sys.executable, CREW, "brief", *args], capture_output=True, text=True)


class Brief(unittest.TestCase):
    def test_every_field_in_order(self):
        r = crew(*[a for flag, _, value in ALL for a in ("--" + flag, value)])
        self.assertEqual((r.returncode, r.stderr), (0, ""), r.stdout)
        self.assertEqual(r.stdout, "\n## This run\n\n" + "".join("- %s: %s\n" % (label, value)
                                                                  for _, label, value in ALL))

    def test_each_optional_field_alone(self):
        for flag, label, value in ALL:
            if label in brief.REQUIRED:
                continue
            with self.subTest(flag=flag):
                r = crew(*REQUIRED, "--" + flag, value)
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertIn("- %s: %s\n" % (label, value), r.stdout)
                self.assertEqual(len(r.stdout.splitlines()), 7, r.stdout)

    def test_missing_or_empty_required_field_refuses(self):
        for i in range(0, len(REQUIRED), 2):
            label = REQUIRED[i][2:].capitalize()
            for args in (REQUIRED[:i] + REQUIRED[i + 2:], REQUIRED[:i + 1] + [""] + REQUIRED[i + 2:]):
                with self.subTest(args=args):
                    r = crew(*args)
                    self.assertEqual(r.returncode, 2, r.stdout)
                    self.assertEqual(r.stdout, "crew: refusing run block: missing %s (required: Item, Pass, Base)\n"
                                     % label)
                    self.assertNotIn("This run", r.stdout + r.stderr)
        r = crew()
        self.assertEqual(r.returncode, 2)
        self.assertIn("missing Item, Pass, Base", r.stdout)

    def test_empty_optional_value_is_left_out(self):
        self.assertNotIn("Round", crew(*REQUIRED, "--round", "").stdout)

    def test_caller_order_kept_for_tmux_block(self):
        # mdstack spawn's pairs (test-crew-spawn.py asserts the brief it writes byte for byte)
        pairs = [("Window", "ben-7"), ("Item", "issue #7"), ("Pass", "build"), ("Worktree", "/wt"),
                 ("Base", "b" * 40), ("Engine", "claude-code opus medium"), ("Claim", "/c")]
        self.assertEqual(brief.run_block(pairs), "\n## This run\n\n" + "".join("- %s: %s\n" % kv for kv in pairs))
        with self.assertRaises(ValueError):
            brief.run_block(pairs[:4])


if __name__ == "__main__":
    unittest.main()
