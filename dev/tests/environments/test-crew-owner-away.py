#!/usr/bin/env python3
"""Contract tests for owner away records, return briefs and rendered instructions.

Checks the protocol's examples and safety boundaries and renders both runtime
bindings to catch missing command/return instructions. Run in CI's test glob.
"""
import contextlib
import datetime
import importlib.util
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("crew_render", ROOT / "scripts/crew-render.py")
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)


class OwnerAway(unittest.TestCase):
    def setUp(self):
        self.protocol = (ROOT / "docs/protocol.md").read_text()
        self.away = self.protocol.split("### Owner away mode\n", 1)[1].split(
            "**Standing doc-only merge-ok", 1)[0]

    def test_record_examples_and_restart_contract(self):
        entered = json.loads(re.search(r"```json\n(.*?)\n```", self.away, re.S)[1])
        returned = json.loads(re.search(r'`({"state":"returned".*?})`', self.away)[1])
        self.assertEqual(entered["state"], "away")
        self.assertIsNone(entered["until"])
        self.assertEqual(entered["words"], "keep #123 on hold")
        self.assertIsNone(entered["cap"])
        self.assertIs(entered["quiet"], False)
        self.assertEqual(returned["state"], "returned")
        self.assertEqual(entered["entry"], returned["entry"])
        self.assertLess(datetime.datetime.fromisoformat(entered["started"]),
                        datetime.datetime.fromisoformat(returned["returned"]))
        for rule in ("signed append-only issue comments are authoritative",
                     "Only profile owner logins count", "ignore edits and already-recorded source ids",
                     "including whitespace, using JSON escaping only", "away-control.json",
                     "cmd=away cmd-id=<source-id>", "cmd=away-return cmd-id=<return-source-id>",
                     "round=n/a verdict=n/a", "signed delivery receipt", "brief_url"):
            self.assertIn(rule, " ".join(self.away.split()))

    def test_sla_authority_and_return_boundaries(self):
        text = " ".join(self.away.split())
        for rule in ("never authority", "allowed defaults apply on schedule",
                     "`until` does not pause or replace that clock",
                     "never parse them into standing grants, merge-ok, flavor acceptance or a gate waiver",
                     "Every §7 gate still applies", "unless it is another away command",
                     "it does not prove the owner returned", "Resume normal notifications"):
            self.assertIn(rule, text)
        self.assertIn("`away` is project-scoped and also works on a held PR; it releases no hold",
                      self.protocol)

    def test_cap_and_quiet_flags(self):
        text = " ".join(self.away.split())
        for rule in ("/crew away [--cap <n>] [--quiet] [until <time>] [words]",
                     "`--cap` takes an integer of 1 or more",
                     "starts no new run while the live run count is at or above `cap`",
                     "never stops a live run, skips a gate or changes a round cap",
                     "keeps the normal SLA clock and defaults",
                     "the owner's own messages do not end it",
                     "or when the owner sends `/crew away --end`",
                     "ends a non-quiet away mode"):
            self.assertIn(rule, text)
        self.assertNotIn("Cap and quiet flags are not supported", text)
        self.assertIn("/crew away [--cap <n>] [--quiet] [until <time>] [words]` | Coordinator",
                      self.protocol)

    def test_return_brief_is_standalone(self):
        text = (ROOT / "templates/owner-return-brief.md").read_text()
        for heading in ("## Return brief", "### Landed", "### Defaults applied", "### Waiting", "### Next"):
            self.assertIn(heading, text)
        for rule in ("full URLs", "use `None` when empty", "recommended action first",
                     "deadline with timezone", "<harness> · <model>"):
            self.assertIn(rule, text)

    def test_both_runtime_bindings_deliver_away_and_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            for runtime, name in (("tmux", "coordinator.md"),
                                  ("grok-bot", "coordinator-steering-dispatcher.md")):
                project = Path(tmp) / "crew.toml"
                project.write_text('[runtime]\nname = "%s"\n' % runtime)
                out = Path(tmp) / runtime
                output = io.StringIO()
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    code = cr.main(["--project", str(project), "--out", str(out)])
                self.assertEqual(code, 0, output.getvalue())
                text = " ".join((out / "runtime" / name).read_text().split())
                for rule in ("Owner away mode", "away-control.json",
                             "first owner message back", "owner-return-brief.md"):
                    self.assertIn(rule, text, runtime)
                if runtime == "grok-bot":
                    for rule in ("scheduled SLA defaults", "no new authority"):
                        self.assertIn(rule, text)
                    skill = (out / "runtime/skills/eng-pr-pipeline/SKILL.md").read_text()
                    self.assertIn("### Owner away mode", skill)


if __name__ == "__main__":
    unittest.main()
