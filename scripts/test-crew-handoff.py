"""`crew handoff` tests: manifest sets and references, retry (same id, one post), partial (one set held, the rest
adopted, claimed sets skipped) and duplicate (a second ack is ignored), against a fake `gh api`.
"""
import json
import os
from pathlib import Path
import re
import unittest
from crew_testlib import Base, SECRET

SHA = "1" * 40
OLD, NEW = "a" * 40, "b" * 40

# Fake gh api: GET reads $GH_DATA; POST appends the stdin body as an acme-bot comment, failing while $GH_FAIL
# counts down; GH_FAIL_MODE=lost posts the comment, then fails, as a timed-out request that did land.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
path = os.environ["GH_DATA"]
data = json.load(open(path))
args = sys.argv[1:]
url = next(a for a in args if a.startswith("repos/"))
if "-F" in args:
    fail = int(data.get("fail", 0))
    data["fail"] = max(fail - 1, 0)
    if not fail or os.environ.get("GH_FAIL_MODE") == "lost":
        data["comments"].append({"user": {"login": "acme-bot"}, "body": sys.stdin.read()})
    json.dump(data, open(path, "w"))
    sys.exit(1 if fail else 0)
key = "comments" if url.endswith("/comments") else url.split("/")[3].split("?")[0]
print(json.dumps([data[key]]))
"""


def marker(state, from_="tmux@local", to="tmux@box", id_="20261101-abcdef"):
    return {"user": {"login": "acme-bot"}, "body": "<!-- crew:v1 role=coordinator pass=handoff handoff=%s "
            "state=%s from=%s to=%s cmd-id=chat sha=%s round=n/a verdict=n/a -->" % (id_, state, from_, to, SHA)}


def issue(n, labels=(), body="", pr=False, milestone=None):
    return {"number": n, "labels": [{"name": lb} for lb in labels], "body": body, "assignees": [],
            "milestone": milestone, **({"pull_request": {}} if pr else {})}


class Handoff(Base):
    def setUp(self):
        super().setUp()
        p = Path(self.project)
        p.write_text(p.read_text().replace('[repo]\n', '[repo]\ncontrol_item = 99\n').replace(
            '[runtime]\n', '[runtime]\ninstance = "local"\n'))
        gh = Path(self.tmp, "bin", "gh")
        gh.write_text(FAKE_GH)
        gh.chmod(0o755)
        self.data = Path(self.tmp, "gh.json")
        self.env["GH_DATA"] = str(self.data)
        # Set 1: #10 depends on #11, PR #12 closes #10. Set 2: #20 and its PR #21. Backlog: #30.
        self.write([marker("claimed", "none", "tmux@local"), marker("draining")],
                   issues=[issue(10, ["crew:in-review"], "Depends on #11"), issue(11), issue(20, ["crew:changes"]),
                           issue(12, ["crew:in-review"], "Closes #10", pr=True),
                           issue(21, ["crew:changes"], "Closes #20", pr=True), issue(30)],
                   pulls=[{"number": 12, "head": {"sha": OLD}}, {"number": 21, "head": {"sha": OLD}}])
        self.put("runs/ben-21.json", json.dumps({"item": "pr #21", "role": "builder", "pass": "fix",
                                                 "worktree": "/somewhere/21-fix"}))

    def write(self, comments, **extra):
        data = json.loads(self.data.read_text()) if self.data.exists() else {"commits": {"sha": SHA}}
        data.update(comments=comments, **extra)
        self.data.write_text(json.dumps(data))

    def comments(self):
        return json.loads(self.data.read_text())["comments"]

    def handoff(self, *args, **env):
        return self.crew("handoff", *args, "--project", self.project, **env)

    def offered(self):
        return [c for c in self.comments() if "state=offered" in c["body"]]

    def test_manifest_sets_references_and_template(self):
        r = self.handoff("manifest")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        data = json.loads(re.search(r"```json\n(.*?)\n```", r.stdout, re.S).group(1))
        self.assertEqual([[i["item"] for i in s["items"]] for s in data["sets"]],
                         [["#10", "#11", "#12"], ["#20", "#21"]])
        self.assertEqual((data["schema"], data["handoff"], data["to"], data["backlog"]),
                         ("crew-handoff/1", "20261101-abcdef", "tmux@box", ["#30"]))
        pr = data["sets"][1]["items"][1]
        self.assertEqual((pr["stage"], pr["head"], pr["runs"]), ("changes", OLD, [
            {"role": "builder", "pass": "fix", "end": "kept", "worktree": "21-fix"}]))
        self.assertIn("[Ash/handoff] offered tmux@local → tmux@box (20261101-abcdef)", r.stdout)
        self.assertIn("state=offered from=tmux@local to=tmux@box cmd-id=n/a sha=%s" % SHA, r.stdout)
        self.assertNotIn("/somewhere", r.stdout)
        self.assertNotRegex(r.stdout, r"<[A-Za-z-]+>")
        self.assertEqual(self.offered(), [])

    def test_secret_scan_and_owner_checks_refuse(self):
        self.write(self.comments(), issues=[issue(10, ["crew:ready", SECRET])], pulls=[])
        r = self.handoff("manifest")
        self.assertEqual((r.returncode, r.stderr), (1, ""))
        self.assertIn("secret scan refused", r.stdout)
        self.write([marker("claimed", "none", "tmux@local")])
        self.assertEqual(self.handoff("manifest").stdout.strip(), "crew: handoff: no open handoff from tmux@local")
        self.assertEqual(self.handoff("manifest", "--post").returncode, 1)

    def test_retry_same_id_posts_once(self):
        for mode in ["", "lost"]:
            self.write([marker("claimed", "none", "tmux@local"), marker("draining")], fail=1)
            r = self.handoff("manifest", "--post", "--signature", "— Ash", GH_FAIL_MODE=mode)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(len(self.offered()), 1, mode)
            self.assertIn("already offered", r.stdout)
            again = self.handoff("manifest", "--post", "--signature", "— Ash")
            self.assertEqual((again.returncode, len(self.offered())), (0, 1))
            self.assertTrue(self.offered()[0]["body"].endswith("— Ash\n"))

    def test_duplicate_ack_ignored_and_nothing_reposted(self):
        self.assertEqual(self.handoff("manifest", "--post", "--signature", "— Ash").returncode, 0)
        ack = marker("acked")
        self.write(self.comments() + [ack, ack, marker("acked", to="tmux@other")])
        r = self.handoff("manifest", "--post", "--signature", "— Ash")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "crew: handoff: owned by tmux@box; nothing to post"))
        self.assertEqual(len(self.offered()), 1)

    def test_partial_reconcile_holds_moved_set_and_skips_claimed(self):
        self.assertEqual(self.handoff("manifest", "--post", "--signature", "— Ash").returncode, 0)
        self.assertEqual(self.handoff("reconcile").returncode, 1)  # tmux@local is the outgoing side
        Path(self.project).write_text(Path(self.project).read_text().replace('"local"', '"box"'))
        data = json.loads(self.data.read_text())
        self.write(data["comments"], issues=data["issues"] + [issue(40, ["crew:ready"])],
                   pulls=[{"number": 12, "head": {"sha": OLD}}, {"number": 21, "head": {"sha": NEW}}])
        r = self.handoff("reconcile")
        self.assertEqual(r.stdout.splitlines(), ["s1 adopt #10 #11 #12", "s2 hold #20 #21 moved: #21",
                                                 "missed #40 adopt"], r.stderr)
        for n in (10, 11, 12):
            self.put("claims/builder-issue%d" % n, "")
        self.assertEqual(self.handoff("reconcile").stdout.splitlines()[0], "s1 skip #10 #11 #12")
        self.assertEqual(len(self.comments()), 3)  # reconcile writes nothing

if __name__ == "__main__":
    unittest.main()
