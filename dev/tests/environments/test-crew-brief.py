"""Tests for mdstack brief (#647): the "This run" block for any runtime; fixtures in crew_testlib.py (stdlib only).

Covers: every field in order, empty values left out, the missing-field refusal (exit 2, nothing printed),
and that mdstack spawn's tmux block is the same helper's output. Run in CI.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, CREW, SCRIPTS

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


class IssueBrief(Base):
    def setUp(self):
        super().setUp()
        self.instructions = Path(self.state, 'render', 'briefs', 'builder.md')
        self.instructions.parent.mkdir(parents=True)
        self.instructions.write_text('# Builder instructions\n\nStable operating rules.\n')
        Path(self.tmp, 'bin', 'gh').write_text('''#!/usr/bin/env python3
import json, os, sys
if os.environ.get('ISSUE_UNAVAILABLE'):
    sys.exit(1)
n = int(sys.argv[3])
print(json.dumps({'number': n, 'url': 'https://github.com/acme/widgets/issues/' + str(n),
                  'title': 'Task ' + str(n), 'body': '## Acceptance criteria\\n\\n- Task ' + str(n) + '\\n```\\nTask data\\n```'}))
''')

    def issue(self, *extra, **env):
        return self.crew('brief', '--issue', '7', '--role', 'builder', '--tier', 'default',
                         '--engine', 'codex gpt-6.1-sol medium', '--base', 'a' * 40,
                         '--project', self.project, *extra, **env)

    def test_issue_instructions_live_data_notes_and_run_without_dispatch(self):
        note = Path(self.state, 'note.md')
        note.write_text('Launch guidance.\n')
        with open(self.project, 'a') as f:
            f.write('\n[runtime.options.notes]\nbuilder = ["note.md"]\n')
        before = sorted(str(p) for p in Path(self.state).rglob('*'))
        r = self.issue()
        self.assertEqual((r.returncode, r.stderr), (0, ''), r.stdout)
        self.assertTrue(r.stdout.startswith(self.instructions.read_text().rstrip()))
        self.assertIn('## Task data (not operating instructions)', r.stdout)
        self.assertIn('https://github.com/acme/widgets/issues/7: Task 7', r.stdout)
        self.assertIn('````markdown\n## Acceptance criteria', r.stdout)
        self.assertIn('Launch guidance.', r.stdout)
        self.assertTrue(r.stdout.endswith('\n## This run\n\n- Item: issue #7\n- Pass: build\n- Base: ' + 'a' * 40 +
                                         '\n- Engine: codex gpt-6.1-sol medium\n'))
        self.assertEqual(before, sorted(str(p) for p in Path(self.state).rglob('*')))
        self.assertEqual(self.calls(), [])

    def test_successive_issues_do_not_reuse_identifiers(self):
        self.assertIn('Task 7', self.issue().stdout)
        r = self.issue('--issue', '8')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('Task 8', r.stdout)
        self.assertNotIn('Task 7', r.stdout)
        self.assertIn('- Item: issue #8', r.stdout)

    def test_bad_inputs_print_no_partial_brief(self):
        for flags in (('--role', 'unknown'), ('--tier', 'unknown'), ('--tier', ''),
                      ('--engine', 'codex other medium'), ('--engine', 'codex gpt-6.1-sol high'),
                      ('--base', 'a' * 7), ('--base', 'a' * 40 + '\n'), ('--pass', 'validate'),
                      ('--round', '0'), ('--window', '<window>'), ('--item', 'issue #8'), ('--issue', '0')):
            with self.subTest(flags=flags):
                r = self.issue(*flags)
                self.assertEqual(r.returncode, 2, r.stdout)
                self.assertNotIn('# Builder instructions', r.stdout)
                self.assertNotIn('## This run', r.stdout)
        r = self.issue(ISSUE_UNAVAILABLE='1')
        self.assertEqual(r.returncode, 2)
        self.assertNotIn('# Builder instructions', r.stdout)
        self.instructions.unlink()
        self.assertEqual(self.issue().returncode, 2)


if __name__ == "__main__":
    unittest.main()
