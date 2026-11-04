"""`crew feedback` tests (#299, docs/triage.md T7): a simulated spawn failure files one redacted runtime-blocker card,
a second identical failure comments on it, and an unreadable card list files nothing.

A fake `gh` keeps issues in a JSON file; no network.
"""
import json
import os
import unittest
from crew_testlib import Base, SECRET

FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
db, args = os.environ["FAKE_GH_DB"], sys.argv[1:]
issues = json.load(open(db)) if os.path.exists(db) else []
if os.environ.get("FAKE_GH_FAIL"):
    sys.exit("gh: HTTP 502")
if args[:2] == ["issue", "list"]:
    print(json.dumps([{"number": i["number"], "body": i["body"]} for i in issues]))
elif args[:2] == ["issue", "create"]:
    n = 100 + len(issues)
    issues.append({"number": n, "repo": args[args.index("-R") + 1], "title": args[args.index("--title") + 1],
                   "body": sys.stdin.read(), "comments": []})
    print("https://example.test/%s/issues/%d" % (issues[-1]["repo"], n))
elif args[:2] == ["issue", "comment"]:
    next(i for i in issues if i["number"] == int(args[2]))["comments"].append(sys.stdin.read())
json.dump(issues, open(db, "w"))
"""


class Feedback(Base):
    def setUp(self):
        super().setUp()
        with open(os.path.join(self.tmp, "bin", "gh"), "w") as f:
            f.write(FAKE_GH)
        self.db = os.path.join(self.tmp, "issues.json")
        self.env.update(FAKE_GH_DB=self.db, GH_TOKEN=SECRET)
        wt = os.path.join(self.tmp, "state", "wt", "7-abc1234-builder-build")
        self.put("runs/ben-7.json", json.dumps({
            "role": "builder", "item": "issue #7", "engine": "codex", "model": "gpt-x", "effort": "high",
            "harness": "codex", "worktree": wt, "args": {"issue": 7, "pass": "build"}}))
        self.summary = "spawn failed: %s/.codex not writable for dev@example.com, token %s" % (wt, SECRET)

    def feedback(self, *extra, **env):
        return self.crew("feedback", "--project", self.project, "--class", "spawn-failure", "--window", "ben-7",
                         "--summary", self.summary, "--sign", "— Ash (Coordinator)", *extra, **env)

    def issues(self):
        with open(self.db) as f:
            return json.load(f)

    def test_files_one_redacted_card_then_comments(self):
        first = self.feedback()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(first.stdout.strip(), "filed: https://example.test/acme/eng-crew/issues/100")
        [card] = self.issues()
        self.assertEqual((card["repo"], card["title"]), ("acme/eng-crew", "intake: spawn-failure on acme/widgets#7"))
        for line in ["**Source:** acme/widgets#7", "**Trigger:** runtime-blocker", "**Failure class:** spawn-failure",
                     "**Decision:** pending", "- Window: ben-7 (builder, issue #7)",
                     "- Engine: codex gpt-x high (harness codex)",
                     "- Summary: spawn failed: <worktree>/.codex not writable for <email>, token <redacted>",
                     "— Ash (Coordinator)"]:
            self.assertIn(line + "\n", card["body"])
        for leak in [SECRET, "dev@example.com", self.tmp]:
            self.assertNotIn(leak, card["body"])
        second = self.feedback()
        self.assertEqual(second.stdout.strip(), "commented: acme/eng-crew#100")
        [card] = self.issues()
        self.assertEqual(len(card["comments"]), 1)
        self.assertIn("Seen again on acme/widgets#7 (trigger `runtime-blocker`).", card["comments"][0])
        self.assertNotIn(SECRET, card["comments"][0])

    def test_other_class_files_a_new_card_and_dry_run_posts_nothing(self):
        self.assertEqual(self.feedback().returncode, 0)
        dry = self.crew("feedback", "--project", self.project, "--class", "watcher-timeout", "--summary", "poll hung",
                        "--repo", "acme/crew-intake", "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stdout)
        self.assertIn("dry-run: gh issue create -R acme/crew-intake --title intake: watcher-timeout on acme/widgets",
                      dry.stdout)
        self.assertIn("**Source:** acme/widgets (run blocker, no item)", dry.stdout)
        self.assertEqual(len(self.issues()), 1)

    def test_unreadable_card_list_or_bad_slug_files_nothing(self):
        failed = self.feedback(FAKE_GH_FAIL="1")
        self.assertEqual(failed.returncode, 1)
        self.assertIn("cannot list open cards in acme/eng-crew", failed.stdout)
        self.assertFalse(os.path.exists(self.db))
        bad = self.crew("feedback", "--project", self.project, "--class", "Spawn Failure", "--summary", "x")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("--class must be a lowercase slug", bad.stdout)


if __name__ == "__main__":
    unittest.main()
