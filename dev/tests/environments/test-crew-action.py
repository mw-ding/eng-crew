"""Tests for crew action (#1232), the terminal binding of the actions CLI contract (actions/cli.md); fixtures in
crew_testlib.py (stdlib only).

Covers: every result keeps the contract envelope with its outcome agreeing with the exit code (the conformance kit's
envelope check); --capabilities; usage, unsupported and short-head refusals; and that check-ownership, heartbeat,
notify, ack and report act on the same control item, claim, inbox and status files `crew ownership`, `crew send`,
`crew acked` and route read today. Run in CI.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import HEAD, SendBase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
spec = importlib.util.spec_from_file_location("contract", os.path.join(ROOT, "actions", "contract.py"))
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
SUPPORTED = {"check-ownership", "heartbeat", "notify", "ack", "report"}


class Action(SendBase):
    def setUp(self):
        super().setUp()
        self.env.update(CREW_PROJECT=self.project, CREW_ID="ben-7", CREW_ROLE="builder")

    def action(self, *args, **env):
        """(exit, result) of one --json call, checked against the contract envelope."""
        r = self.crew("action", *args, "--json", **env)
        op = args[1] if args[1:2] and args[1] in contract.ACTIONS.get(args[0], []) else None
        result, problems = contract.envelope(r.stdout, r.returncode, args[0], op)
        self.assertEqual(problems, [], r.stdout + r.stderr)
        return r.returncode, result

    def status(self, window="ben-7"):
        return Path(self.state, "status", window + ".status").read_text().splitlines()

    def test_capabilities_name_every_action(self):
        r = self.crew("action", "--capabilities", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        caps = json.loads(r.stdout)["capabilities"]
        self.assertEqual(caps, {a: "supported" if a in SUPPORTED else "unsupported" for a in contract.ACTIONS})
        self.write_profile(runtime="session")
        caps = json.loads(self.crew("action", "--capabilities", "--json").stdout)["capabilities"]
        self.assertEqual((caps["notify"], caps["heartbeat"], caps["report"]), ("unsupported", "unsupported", "supported"))

    def test_usage_unsupported_and_short_head(self):
        self.assertEqual(self.action("no-such-action")[1]["reason"]["code"], "usage")
        self.assertEqual(self.action("no-such-action")[0], 2)
        code, result = self.action("claim")
        self.assertEqual((code, result["reason"]["code"]), (2, "usage"))
        code, result = self.action("report", "--status", "done", "--bogus", "x")
        self.assertEqual((code, result["reason"]["code"]), (2, "usage"))
        for action, ops in contract.ACTIONS.items():
            if action not in SUPPORTED:
                code, result = self.action(action, *ops[:1], "--item", "1", "--head", HEAD)
                self.assertEqual((code, result["reason"]["code"]), (6, "unsupported"), action)
        for flags in [["land", "acquire", "--bogus", "x"], ["land", "acquire", "--rule", "sideways"],
                      ["read", "extra-positional"], ["claim", "release", "--pass", "build"]]:
            code, result = self.action(*flags)
            self.assertEqual((code, result["reason"]["code"]), (2, "usage"), flags)
        code, result = self.action("land", "acquire", "--rule", "direct", "--rule", "train")
        self.assertEqual((code, result["reason"]["code"]), (6, "unsupported"))
        code, result = self.action("report", "--status", "done", "--ref", "#7", "--head", HEAD[:7])
        self.assertEqual((code, result["reason"]["code"]), (6, "invalid-ref"))
        self.assertFalse(os.path.exists(os.path.join(self.state, "status", "ben-7.status")))

    def test_report_appends_the_status_lines_route_reads(self):
        sha = "a" * 40
        self.assertEqual(self.action("report", "--status", "ack", "--ref", "build", "--ref", "#7", "--ref", sha)[0], 0)
        code, result = self.action("report", "--status", "done", "--ref", "#7", "--ref", "#12", "--ref", sha)
        self.assertEqual(code, 0)
        self.assertEqual(result["result"]["line"], "done: #7 #12 " + sha)
        self.assertEqual(self.action("report", "--status", "blocked", "--ref", "#7", "--reason", "hold")[0], 0)
        self.assertEqual(self.status(), ["ack: build #7 " + sha, "done: #7 #12 " + sha, "blocked: #7 hold"])
        r = self.crew("action", "report", "--status", "done", "--ref", "#7", "--ref", "#12", "--ref", sha)
        status = os.path.join(self.state, "status", "ben-7.status")
        self.assertEqual((r.returncode, r.stdout), (0, "completed: report %s\n" % status))
        self.assertEqual(self.status()[-1], "done: #7 #12 " + sha)
        refused = [(["--status", "done"], 6, "invalid-ref"),
                   (["--status", "done", "--ref", "@@ -1 +1 @@"], 6, "invalid-ref"),
                   (["--status", "blocked", "--ref", "#7"], 2, "usage"),
                   (["--status", "blocked", "--reason", "two\nlines"], 6, "invalid-ref")]
        for flags, want, reason in refused:
            code, result = self.action("report", *flags)
            self.assertEqual((code, result["reason"]["code"]), (want, reason), flags)
        self.assertEqual(len(self.status()), 4)
        code, result = self.action("report", "--status", "done", "--ref", "#7", CREW_ID="")
        self.assertEqual((code, result["reason"]["code"]), (2, "usage"))

    def test_notify_then_ack_is_send_and_acked(self):
        code, result = self.action("notify", "--to", "ben-7", "--kind", "fix", "--ref", "#7", CREW_ID="ash")
        self.assertEqual((code, result["outcome"], result["reason"]["code"]), (3, "pending", "no-receipt"))
        msg_id = result["refs"]["message"]
        self.assertEqual([m["id"] for m in self.inbox()], [msg_id])
        self.assertEqual(self.inbox()[0]["refs"], ["#7"])
        self.assertEqual(self.crew("acked", "ben-7", msg_id, "--project", self.project).returncode, 3)
        code, result = self.action("ack", "--message", "20260101T000000Z-abcdef")
        self.assertEqual((code, result["reason"]["code"]), (6, "invalid-ref"))
        self.assertEqual(self.action("ack", "--message", msg_id)[0], 0)
        self.assertEqual(self.action("ack", "--message", msg_id)[0], 0)
        self.assertEqual(self.status(), ["ack: " + msg_id])
        self.assertEqual(self.crew("acked", "ben-7", msg_id, "--project", self.project).returncode, 0)
        code, result = self.action("notify", "--to", "ben-9", "--kind", "review", "--ref", "#7")
        self.assertEqual((code, result["reason"]["code"]), (6, "no-recipient"))
        code, result = self.action("notify", "--to", "ben-7", "--kind", "fix", "--ref", "diff --git a b")
        self.assertEqual((code, result["reason"]["code"]), (6, "invalid-ref"))

    def test_heartbeat_rewrites_only_the_runs_claim(self):
        claim = Path(self.state, "claims", "builder-issue7")
        self.put("claims/builder-issue7", "")
        self.put("claims/builder-issue8", "")
        self.put("runs/ben-7.json", json.dumps({"role": "builder", "claim": str(claim)}))
        for _ in range(2):
            code, result = self.action("heartbeat")
            self.assertEqual((code, result["refs"]["claim"]), (0, "builder-issue7"))
        self.assertEqual(claim.read_text(), "heartbeat: %s\n" % result["result"]["heartbeat"])
        for flags in [["--claim", "builder-issue8"], ["--claim", "builder-issue9"], ["--claim", "../runs/ben-7.json"]]:
            code, result = self.action("heartbeat", *flags)
            self.assertEqual((code, result["reason"]["code"]), (6, "not-held"), flags)
        self.assertEqual(Path(self.state, "claims", "builder-issue8").read_text(), "")
        self.put("claims/builder-issue8", "heartbeat: 2000-01-01T00:00:00Z\n")
        self.put("runs/ben-8.json", json.dumps({"role": "builder", "claim": str(claim.with_name("builder-issue8"))}))
        os.remove(os.path.join(self.state, "runs", "ben-7.json"))
        for flags in [[], ["--claim", str(claim)], ["--claim", "builder-issue8"]]:
            code, result = self.action("heartbeat", *flags)
            self.assertEqual((code, result["reason"]["code"]), (6, "not-held"), flags)
        self.assertEqual(Path(self.state, "claims", "builder-issue8").read_text(), "heartbeat: 2000-01-01T00:00:00Z\n")
        self.assertEqual(self.action("heartbeat", CREW_ID="ben-8")[0], 0)

    def test_explicit_key_replays_the_first_outcome(self):
        flags = ["report", "--status", "done", "--ref", "#7", "--key", "report-retry"]
        first, again = self.action(*flags), self.action(*flags)
        self.assertEqual((first[0], again[0], again[1]["result"]["replayed"]), (0, 0, True))
        self.assertEqual(self.status(), ["done: #7"])
        code, result = self.action("report", "--status", "done", "--ref", "#8", "--key", "report-retry")
        self.assertEqual((code, result["reason"]["code"]), (6, "key-conflict"))
        self.assertEqual(self.action("report", "--status", "done", "--ref", "#7")[0], 0)
        self.assertEqual(self.status(), ["done: #7", "done: #7"])  # no --key: a new effect, as a re-report is today
        notify = ["notify", "--to", "ben-7", "--kind", "review", "--ref", "#7", "--key", "notify-retry"]
        sent = [self.action(*notify, CREW_ID="ash") for _ in range(2)]
        self.assertEqual([(c, r["outcome"]) for c, r in sent], [(3, "pending")] * 2)
        self.assertEqual(sent[0][1]["refs"]["message"], sent[1][1]["refs"]["message"])
        self.assertEqual(len(self.inbox()), 1)
        self.assertEqual(self.action("ack", "--message", sent[0][1]["refs"]["message"])[0], 0)
        code, result = self.action(*notify, CREW_ID="ash")
        self.assertEqual((code, result["result"]["receipt"]), (0, "ack: " + sent[0][1]["refs"]["message"]))
        self.assertEqual(len(self.inbox()), 1)

    def test_check_ownership_reads_the_control_item(self):
        self.assertEqual(self.action("check-ownership", "--for", "land")[1]["result"]["state"], "active")
        self.assertEqual(self.action("check-ownership", "--for", "land", "--key", "land-guard")[0], 0)
        p = Path(self.project)
        p.write_text(p.read_text().replace('[repo]\n', '[repo]\ncontrol_item = 99\n').replace(
            '[runtime]\n', '[runtime]\ninstance = "local"\n'))
        body = ("<!-- crew:v1 role=coordinator pass=handoff handoff=20261101-abcdef state=claimed from=none "
                "to=grok-bot@box cmd-id=chat sha=%s round=n/a verdict=n/a -->" % HEAD)
        comments = Path(self.tmp, "comments.json")
        comments.write_text(json.dumps([[{"user": {"login": "acme-bot"}, "body": body}]]))
        gh = Path(self.tmp, "bin", "gh")
        gh.write_text('#!/usr/bin/env python3\nimport os\nprint(open(os.environ["COMMENTS"]).read())\n')
        self.env["COMMENTS"] = str(comments)
        code, result = self.action("check-ownership", "--for", "land", "--key", "land-guard")
        self.assertEqual((code, result["reason"]["code"]), (6, "not-owner"))  # a read is never replayed
        self.assertNotIn("replayed", result["result"])
        for verb in ["start", "write"]:
            code, result = self.action("check-ownership", "--for", verb)
            self.assertEqual((code, result["reason"]["code"], result["result"]),
                             (6, "not-owner", {"state": "read-only", "runtime": "tmux@local"}))
            self.assertEqual(self.crew("ownership", "--project", self.project, "--action", verb).returncode, 1)
        code, result = self.action("notify", "--to", "ben-7", "--kind", "fix", "--ref", "#7")
        self.assertEqual((code, result["reason"]["code"]), (6, "not-owner"))
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-7.jsonl")))


if __name__ == "__main__":
    unittest.main()
