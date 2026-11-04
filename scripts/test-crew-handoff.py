"""`crew handoff` tests: owner commands (draining, aborted, takeover only on a legal transition; drain deadline;
the Stop guard while draining), manifest sets and references, retry (same id, one post), partial (one set held, the rest
adopted, claimed sets skipped) and duplicate (a second ack is ignored), against a fake `gh api`. Resume (#212): the
full reconcile table, ack once per id (rules, takeover manifest), stopped only after the wake sources stop, lifting
only `holds_added`, the `lost` ownership wake that stops poll and keeps the watcher from re-arming, and `stopped` tearing
the session down from a detached process that keeps unlanded worktrees and posts last.
"""
import json
import os
from pathlib import Path
import re
import unittest
import signal
import subprocess
import sys
import time
from crew_testlib import Base, CREW, KillLandedBase, SECRET

SHA = "1" * 40
OLD, NEW = "a" * 40, "b" * 40

# Fake gh api: GET reads $GH_DATA; POST appends the stdin body as an acme-bot comment, failing while $GH_FAIL
# counts down; GH_FAIL_MODE=lost posts the comment, then fails, as a timed-out request that did land. DELETE drops a
# label; a GET of another item path reads data[path] (default empty).
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys
path = os.environ["GH_DATA"]
data = json.load(open(path))
args = sys.argv[1:]
url = next(a for a in args if a.startswith("repos/"))
rel = url.split("/", 3)[3].split("?")[0]
if "DELETE" in args:
    n, label = int(rel.split("/")[1]), rel.split("/")[3]
    for i in data["issues"]:
        if i["number"] == n:
            i["labels"] = [lb for lb in i["labels"] if lb["name"] != label]
    data.setdefault("deleted", []).append(rel)
    json.dump(data, open(path, "w"))
    sys.exit(0)
if "-F" in args:
    fail = int(data.get("fail", 0))
    data["fail"] = max(fail - 1, 0)
    if not fail or os.environ.get("GH_FAIL_MODE") == "lost":
        data["comments"].append({"id": len(data["comments"]) + 1, "user": {"login": "acme-bot"},
                                 "body": sys.stdin.read(), "created_at": "2026-11-01T12:00:00Z"})
    json.dump(data, open(path, "w"))
    if fail:
        sys.exit(1)
    print(json.dumps(data["comments"][-1]))  # GitHub returns the created comment object
    sys.exit(0)
if rel == "issues/99/comments":
    print(json.dumps([data["comments"]]))
elif "/" in rel and not rel.startswith("commits/"):
    print(json.dumps([data.get(rel, [])]))
else:
    print(json.dumps([data[rel.split("/")[0]]]))
"""


def marker(state, from_="tmux@local", to="tmux@box", id_="20261101-abcdef"):
    return {"user": {"login": "acme-bot"}, "body": "<!-- crew:v1 role=coordinator pass=handoff handoff=%s "
            "state=%s from=%s to=%s cmd-id=chat sha=%s round=n/a verdict=n/a -->" % (id_, state, from_, to, SHA)}


def issue(n, labels=(), body="", pr=False, milestone=None):
    return {"number": n, "labels": [{"name": lb} for lb in labels], "body": body, "assignees": [],
            "milestone": milestone, **({"pull_request": {}} if pr else {})}


class Fixture(Base):
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


class Handoff(Fixture):
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
        self.assertIn("|---|---|---|---|\n| s1 | #10 #11 #12 | in-review none in-review | - - aaaaaaa |\n"
                      "| s2 | #20 #21 | changes changes | - aaaaaaa |\n\n", r.stdout)
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
        r = self.handoff("manifest", "--post", "--signature", "— Ash")  # a normal successful POST
        self.assertEqual((r.returncode, r.stderr), (0, ""))
        self.assertIn("already offered", r.stdout)
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
                                                 "rerun #21 builder fix kept 21-fix", "missed #40 adopt"], r.stderr)
        for n in (10, 11, 12):
            self.put("claims/builder-issue%d" % n, "")
        self.assertEqual(self.handoff("reconcile").stdout.splitlines()[0], "s1 skip #10 #11 #12")
        self.assertEqual(len(self.comments()), 3)  # reconcile writes nothing

class Resume(Fixture):
    SIGN = "— 🔥 Ash (Coordinator) · Claude Code · claude-opus-5-5"

    def incoming(self):
        """The outgoing side offers; the profile then turns into the incoming tmux@box."""
        self.assertEqual(self.handoff("manifest", "--post", "--signature", "— Ash").returncode, 0)
        Path(self.project).write_text(Path(self.project).read_text().replace('"local"', '"box"'))

    def states(self, state):
        return [c["body"] for c in self.comments() if "state=%s " % state in c["body"]]

    def test_reconcile_table_gone_tags_stale_and_rules(self):
        self.incoming()
        data = json.loads(self.data.read_text())
        offer = data["comments"][-1]
        offer["body"] = offer["body"].replace('"value": "standard"', '"value": "thorough"', 1)
        issues = [i for i in data["issues"] if i["number"] != 11]  # #11 closed
        issues[0]["labels"] = [{"name": "crew:approved"}]  # #10's tag moved after the offer
        self.write(data["comments"], issues=issues, **{
            "pulls/21/reviews": [{"submitted_at": "2026-11-01T12:30:00Z", "body": "<!-- crew:v1 role=reviewer "
                                  "pass=verdict pr=21 -->"}],
            "issues/12/comments": [{"created_at": "2026-11-01T11:00:00Z", "body": "<!-- crew:v1 pass=fix -->"}]})
        r = self.handoff("reconcile")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertEqual(lines[:3], ["s1 hold #10 #12 tags: #10", "s2 adopt #20 #21", "gone #11 close-out"])
        self.assertIn("stale #21 pass=verdict rerun at head", lines)  # posted in transit; #12's predates the offer
        self.assertFalse(any(line.startswith("stale #12") for line in lines))
        self.assertTrue(any(line.startswith("rule flavor.") and "thorough" in line for line in lines), lines)

    def test_ack_once_after_rules_and_never_twice(self):
        self.incoming()
        data = json.loads(self.data.read_text())
        data["comments"][-1]["body"] = data["comments"][-1]["body"].replace('"value": "standard"', '"value": "x"', 1)
        self.write(data["comments"], fail=1)
        r = self.handoff("ack", "--signature", self.SIGN)
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing ack: rule differences", r.stdout)
        self.assertEqual(self.states("acked"), [])
        r = self.handoff("ack", "--rules-confirmed", "--signature", self.SIGN)  # first POST fails, the retry posts
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        [post] = self.states("acked")
        self.assertIn("[Ash/handoff] acked tmux@local → tmux@box (20261101-abcdef)", post)
        self.assertIn("Reconciled against live state: s1 adopt #10 #11 #12; s2 adopt #20 #21; rerun #21", post)
        self.assertTrue(post.rstrip().endswith(self.SIGN))
        r = self.handoff("ack", "--rules-confirmed", "--signature", self.SIGN)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "crew: handoff: tmux@box owns; already acked"))
        self.assertEqual(len(self.states("acked")), 1)
        self.assertEqual(self.crew("ownership", "--project", self.project).returncode, 0)

    def test_takeover_ack_carries_the_manifest(self):
        Path(self.project).write_text(Path(self.project).read_text().replace('"local"', '"box"'))
        self.write([marker("claimed", "none", "tmux@local"), marker("takeover")])
        r = self.handoff("ack", "--signature", self.SIGN)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        [post] = self.states("acked")
        self.assertIn("missed #10 adopt", post)
        self.assertEqual(json.loads(re.search(r"```json\n(.*?)\n```", post, re.S).group(1))["mode"], "takeover")

    def test_prompt_stop_lost_wake_and_watcher_not_rearmed(self):
        acked = [marker("claimed", "none", "tmux@local"), marker("draining"), marker("offered"), marker("acked")]
        self.write(acked[:3])
        self.assertEqual(self.crew("poll", "--once", "--project", self.project).returncode, 0)
        self.write(acked)
        r = self.crew("poll", "--once", "--project", self.project)
        self.assertIn("ownership: lost", r.stdout)
        queue = [json.loads(line) for line in Path(self.state, "wake", "queue.jsonl").read_text().splitlines()]
        self.assertEqual([w["refs"] for w in queue], [["read-only"], ["lost"]])
        r = self.crew("watch", "--project", self.project)
        self.assertEqual(r.returncode, 1)
        self.assertIn("watcher not armed", r.stdout)
        r = self.crew("guard", "--state", self.state, stdin='{"stop_hook_active": false}',
                      CREW_ROLE="coordinator", CREW_PROJECT=self.project)
        self.assertEqual(r.stdout.strip(), "")  # the outgoing turn may end

    def test_lift_only_holds_added_after_stopped(self):
        self.incoming()
        data = json.loads(self.data.read_text())
        offer = data["comments"][-1]
        offer["body"] = offer["body"].replace('"holds_added": []', '"holds_added": ["#10", "#20", "#30"]')
        for i in data["issues"]:
            if i["number"] in (10, 20, 30, 11):
                i["labels"].append({"name": "crew:hold"})
        self.write(data["comments"] + [marker("acked")], issues=data["issues"])
        r = self.handoff("lift")
        self.assertEqual(r.returncode, 1)
        self.assertIn("refusing lift", r.stdout)
        self.write(self.comments() + [marker("stopped")])
        r = self.handoff("lift", "--keep", "20")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(self.data.read_text())["deleted"],
                         ["issues/10/labels/crew:hold", "issues/30/labels/crew:hold"])  # #11 was never added
        self.assertEqual(self.handoff("lift").stdout.strip(), "crew: handoff: lifted crew:hold on #20")
        Path(self.project).write_text(Path(self.project).read_text().replace('"box"', '"local"'))
        self.assertEqual(self.handoff("lift").returncode, 1)  # the outgoing side lifts nothing


class PromptStop(KillLandedBase):
    """`crew handoff stopped` from the coordinator window, with a builder's unlanded work (#718 round 1)."""

    def setUp(self):
        super().setUp()
        self.wt = self.builder()
        Path(self.wt, "wip.txt").write_text("unlanded work\n")
        p = Path(self.project)
        p.write_text(p.read_text().replace('[repo]\n', '[repo]\ncontrol_item = 99\n').replace(
            '[runtime]\n', '[runtime]\ninstance = "local"\n'))
        Path(self.tmp, "bin", "gh").write_text(FAKE_GH)
        self.data = Path(self.tmp, "handoff-gh.json")
        self.data.write_text(json.dumps({"commits": {"sha": SHA}, "comments": [
            marker("claimed", "none", "tmux@local"), marker("draining"), marker("offered"), marker("acked")]}))
        self.env["GH_DATA"] = str(self.data)

    def stopped_posts(self):
        return [c["body"] for c in json.loads(self.data.read_text())["comments"] if "state=stopped " in c["body"]]

    def test_stopped_detaches_keeps_work_and_posts_after_the_session_is_down(self):
        self.assertIn("crew-acme-widgets", json.loads(Path(self.state_file).read_text()))
        # Window 0 stand-in: a shell in its own process group runs the command, then is killed with its group,
        # as crew down's kill-session does to the coordinator; the detached teardown must survive it.
        pane = subprocess.Popen(["sh", "-c", '"$0" "$1" handoff stopped --signature "— Ash" --project "$2"; sleep 30',
                                 sys.executable, CREW, self.project], env=self.env, stdout=subprocess.PIPE, text=True,
                                start_new_session=True)
        self.assertIn("stopping wake sources outside the session", pane.stdout.readline())
        os.killpg(pane.pid, signal.SIGKILL)
        pane.wait()
        # The actor posts, then prints its result line last; its stdout is the log file, block-buffered until it
        # exits (#755). Wait on that line, not on the post; the deadline only guards against a hang.
        log_file, log = Path(self.state, "handoff-stop.log"), ""
        deadline = time.monotonic() + 120
        while not re.search(r"crew: handoff: (posted|refusing) stopped", log) and time.monotonic() < deadline:
            time.sleep(0.2)
            log = log_file.read_text()
        self.assertIn("posted stopped 20261101-abcdef", log)
        [post] = self.stopped_posts()
        self.assertNotIn("crew-acme-widgets", json.loads(Path(self.state_file).read_text()))  # session down first
        self.assertTrue(Path(self.wt, "wip.txt").exists())
        self.assertIn("Worktrees kept on this host: %s." % os.path.basename(self.wt), post)
        self.assertIn("state=stopped from=tmux@local to=tmux@box", post)
        again = self.crew("handoff", "stopped", "--signature", "— Ash", "--project", self.project)
        self.assertEqual(again.stdout.strip(), "crew: handoff: 20261101-abcdef already stopped")
        self.assertEqual(len(self.stopped_posts()), 1)


class Commands(Fixture):
    SIGN = "— 🔥 Ash (Coordinator) · Claude Code · claude-opus-5-5"

    def command(self, *args, record=()):
        self.write(list(record))
        return self.handoff(*args, "--signature", self.SIGN)

    def posts(self):
        return [c["body"] for c in self.comments() if "pass=handoff" in c["body"] and "Owner command" in c["body"]]

    def test_owner_hands_off_with_drain_deadline(self):
        r = self.command("to", "grok-bot@box", "--deadline", "45", record=[marker("claimed", "none", "tmux@local")])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        [post] = self.posts()
        self.assertRegex(post, r"\[Ash/handoff\] draining tmux@local → grok-bot@box \(\d{8}-[0-9a-f]{6}\)\n"
                               r"Owner command \(chat\): handoff to grok-bot@box, mode drain, deadline 45 min")
        self.assertIn("state=draining from=tmux@local to=grok-bot@box cmd-id=chat sha=" + SHA, post)
        self.assertTrue(post.rstrip().endswith(self.SIGN))
        self.assertFalse(re.search(r"^/crew", post, re.M))
        ask = json.loads(Path(self.state, "asks", "handoff.json").read_text())
        self.assertIn(ask["handoff"], post)
        self.assertIn(ask["deadline"][:16], post)
        r = self.handoff("manifest")  # the posted draining opens the handoff the manifest reads
        self.assertIn("state=offered from=tmux@local to=grok-bot@box", r.stdout)

    def test_stop_mode_has_no_deadline_and_dry_run_posts_nothing(self):
        r = self.command("to", "grok-bot@box", "--mode", "stop", "--dry-run",
                         record=[marker("claimed", "none", "tmux@local")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("mode stop.", r.stdout)
        self.assertEqual(self.posts(), [])
        self.assertFalse(Path(self.state, "asks").exists())

    def test_refuses_illegal_transitions_without_posting(self):
        claim, drain = marker("claimed", "none", "tmux@local"), marker("draining", to="grok-bot@box")
        for args, record in [(("to", "grok-bot@box"), [marker("claimed", "none", "grok-bot@box")]),  # not the owner
                             (("to", "grok-bot@box"), [claim, drain]),  # one open handoff
                             (("to", "tmux@local"), [claim]),
                             (("to", "Bad"), [claim]),
                             (("abort",), [claim]),
                             (("takeover", "grok-bot@box"), [claim])]:
            r = self.command(*args, record=record)
            self.assertEqual(r.returncode, 1, args)
            self.assertIn("refusing", r.stdout)
        self.assertEqual(self.handoff("abort").returncode, 1)  # no --signature
        self.env["GH_DATA"] = "/missing"
        self.assertEqual(self.handoff("abort", "--signature", self.SIGN).returncode, 1)
        self.env["GH_DATA"] = str(self.data)
        self.assertEqual(self.posts(), [])

    def test_abort_closes_the_open_handoff_and_drops_the_deadline(self):
        self.put("asks/handoff.json", '{"deadline": "2026-11-03T08:00:00+00:00"}')
        r = self.command("abort", record=[marker("claimed", "none", "tmux@local"), marker("draining", to="grok-bot@box")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("handoff=20261101-abcdef state=aborted from=tmux@local to=grok-bot@box", self.posts()[0])
        self.assertFalse(Path(self.state, "asks", "handoff.json").exists())

    def test_takeover_new_or_reusing_the_open_id(self):
        r = self.command("takeover", "grok-bot@box", record=[marker("claimed", "none", "grok-bot@box")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("state=takeover from=grok-bot@box to=tmux@local", self.posts()[0])
        offered = [marker("claimed", "none", "grok-bot@box"), marker("draining", "grok-bot@box", "tmux@local"),
                   marker("offered", "grok-bot@box", "tmux@local")]
        self.assertEqual(self.command("takeover", "grok-bot@box", record=offered).returncode, 0)
        self.assertIn("handoff=20261101-abcdef state=takeover", self.posts()[0])
        r = self.command("abort", record=offered + [marker("takeover", "grok-bot@box", "tmux@local")])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("state=aborted from=grok-bot@box to=tmux@local", self.posts()[0])

    def test_guard_keeps_draining_coordinator_until_runs_end(self):
        for record, blocked in [([marker("claimed", "none", "tmux@local"), marker("draining")], True),
                                ([marker("claimed", "none", "grok-bot@box")], False)]:
            self.write(record)
            r = self.crew("guard", "--state", self.state, stdin='{"stop_hook_active": false}',
                          CREW_ROLE="coordinator", CREW_PROJECT=self.project)
            self.assertEqual(bool(r.stdout.strip()) and json.loads(r.stdout).get("decision") == "block", blocked)


if __name__ == "__main__":
    unittest.main()
