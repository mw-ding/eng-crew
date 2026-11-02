"""Tests for zero-token routing with fake tmux and gh: review/validate lifecycle, caps and head deduplication,
merged close-out and protected branches, ownership and judgement handoff, and watcher continuation.
Run in CI. --transcript and --inbox-transcript print reproducible CLI lifecycles with volatile fixture paths and
SHAs scrubbed.
"""
import json
import os
import shlex
import sys
import unittest
from crew_testlib import SpawnBase


class Route(SpawnBase):
    def setUp(self):
        super().setUp()
        self.sha = self.pr(12, "codex gpt-6.1-sol medium")
        self.data = os.path.join(self.tmp, "github.json")
        self.gh_log = os.path.join(self.tmp, "gh-route.log")
        self.live = dict(number=12, state="OPEN", headRefOid=self.sha, isDraft=False, labels=[], reviews=[],
                         statusCheckRollup=[], headRefName="builder/7-feature", baseRefName="main",
                         headRepositoryOwner={"login": "acme"}, headRepository={"name": "widgets"},
                         isCrossRepository=False, closingIssuesReferences=[{"number": 7}])
        self.save()
        with open(os.path.join(self.tmp, "bin", "gh"), "w") as f:
            f.write("#!/usr/bin/env python3\nimport json, sys\n"
                    "args = sys.argv[1:]\nopen(%r, 'a').write(json.dumps(args) + '\\n')\n"
                    "pr = json.load(open(%r))\n"
                    "if args[:2] == ['pr', 'view']: print(json.dumps(pr))\n"
                    "elif args[:2] == ['repo', 'view']: print(json.dumps({'defaultBranchRef': {'name': 'main'}}))\n"
                    "elif args[:2] == ['issue', 'view']: print(json.dumps({'labels': [{'name': 'crew:ready'}]}))\n"
                    "elif args[:1] == ['api'] and '--paginate' in args: sys.exit(1)\n"
                    "elif args[:1] == ['api'] and '/commits/' in args[1]: print(json.dumps({'parents': pr['_parents']}))\n"
                    "elif args[:1] == ['api'] and '/compare/' in args[1]: print(json.dumps({'status': pr['_comparison']}))\n"
                    "elif args[:1] == ['api'] and '-X' not in args: print('{}')\n" % (self.gh_log, self.data))
        self.transcript = []

    def save(self):
        with open(self.data, "w") as f:
            json.dump(self.live, f)

    def queue(self, *records):
        self.put("wake/queue.jsonl", "".join(json.dumps(w) + "\n" for w in records))

    def pending(self):
        path = os.path.join(self.state, "wake", "queue.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def event(self, event="new-head", **kw):
        return dict(event=event, refs=["#12", self.sha], round=1, **kw)

    def status(self, name, result):
        return dict(reason="status", window=name, line="done: #12 %s %s" % (self.sha, result))

    def route(self):
        r = self.crew("route", "--project", self.project, "--timeout", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.transcript.append(("crew route --project <fixture>/crew.toml --timeout 1", r))
        return r

    def names(self):
        with open(self.state_file) as f:
            return sorted(json.load(f)["crew-acme-widgets"].values())

    def gh_calls(self):
        with open(self.gh_log) as f:
            return [json.loads(line) for line in f]

    def test_lifecycle(self):
        self.queue(self.event())
        self.route()
        self.assertIn("vera-12-r1-review", self.names())
        self.transcript.append(("state", "created review window; queued wakes: []"))
        name = "vera-12-r1-review"
        self.put("status/" + name + ".status", "done: #12 %s review pass\n" % self.sha)
        section = "verdicts/pr12-%s-r1-review.md" % self.sha[:7]
        self.put(section, "Review passed\n")
        self.queue(self.status(name, "review pass"))
        self.route()
        self.assertNotIn(name, self.names())
        self.assertIn("vera-12-r1-validate", self.names())
        self.assertTrue(os.path.exists(os.path.join(self.state, section)))
        self.transcript.append(("state", "review completed; review window removed; validation window created"))
        self.queue(self.status("vera-12-r1-validate", "validate pass"))
        self.route()
        self.assertEqual(self.names(), ["ash"])
        self.assertEqual(self.pending(), [])
        self.transcript.append(("state", "validation completed; validation window removed; role runs: []; queued wakes: []"))

    def test_new_head_replaces_previous_head_review(self):
        self.queue(self.event())
        self.route()
        old = self.record("vera-12-r1-review")["worktree"]
        self.git("reset", "-q", "--hard", self.sha)
        self.sha = self.pr(12, "codex gpt-6.1-sol high")
        self.live["headRefOid"] = self.sha
        self.save()
        self.queue(self.event())
        self.route()
        self.assertEqual(self.pending(), [])
        self.assertFalse(os.path.exists(old))
        self.assertEqual(self.record("vera-12-r1-review")["head"], self.sha)

    def test_builder_done_and_fix_at_head_deduplicate_review(self):
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha), self.event())
        self.route()
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.pending(), [])
        self.queue(dict(self.event("fix-at-head"), round=2))
        self.route()
        self.assertIn("vera-12-r2-review", self.names())

    def approved_push(self, merge=True):
        previous = self.sha
        self.live["reviews"] = [dict(body=(
            "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=1 verdict=changes -->\n"
            "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=2 verdict=pass -->"
            % ("0" * 40, previous)))]
        self.git("commit", "-q", "--allow-empty", "-m", "default branch update")
        default = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "--detach", previous)
        if merge:
            self.git("merge", "-q", "--no-ff", "main", "-m", "merge-up\n\nEngine: none (pure merge-up, plain git)")
        else:
            self.git("commit", "-q", "--allow-empty", "-m", "fix\n\nEngine: codex gpt-6.1-sol medium")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("push", "-q", "origin", "HEAD:refs/pull/12/head")
        self.live.update(headRefOid=self.sha, _parents=[{"sha": previous}, {"sha": default}] if merge else
                         [{"sha": previous}], _comparison="identical")
        self.live["reviews"].append(dict(body="<!-- crew:v1 role=builder pass=fix pr=12 sha=%s round=2 "
                                              "verdict=n/a engine=codex model=gpt-6.1-sol effort=medium -->" % self.sha))
        self.save()
        return previous

    def test_merge_up_stays_queued_for_synthesizer_without_reviewer(self):
        previous = self.approved_push()
        built = dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha)
        event = dict(self.event("merge-up"), previous_head=previous, round=2, consumer="synthesizer")
        self.queue(built)
        self.route()
        self.assertEqual(self.windows(), [])
        self.queue(event, built, event)
        for _ in range(2):
            r = self.crew("route", "--project", self.project, "--timeout", "1")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(self.names(), ["ash"])
            self.assertEqual(self.windows(), [])
            self.assertEqual(self.pending(), [event, event])

    def test_non_merge_fix_push_gets_normal_review(self):
        self.approved_push(merge=False)
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha),
                   dict(self.event(), round=2))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r2-review"])
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.pending(), [])

    def test_merge_up_with_open_rereview_gets_normal_review(self):
        previous = self.approved_push()
        self.live["reviews"].append(dict(body="<!-- crew:v1 role=coordinator pass=steer cmd=rereview pr=12 "
                                              "sha=%s -->" % self.sha))
        self.save()
        self.queue(dict(self.event("merge-up"), previous_head=previous, round=2),
                   dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r2-review"])
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.pending(), [])

    def test_merge_up_rereview_overrides_prior_verdict_and_section(self):
        previous = self.approved_push()
        verdict = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=2 verdict=pass -->" % self.sha
        self.put("verdicts/pr12-%s-r2-review.md" % self.sha[:7], verdict)
        self.live["reviews"] += [dict(body=verdict), dict(body="<!-- crew:v1 role=coordinator pass=steer "
                                                            "cmd=rereview pr=12 sha=%s -->" % self.sha)]
        self.save()
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha),
                   dict(self.event("merge-up"), previous_head=previous, round=2))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r2-review"])
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.pending(), [])

    def test_changes_reap_terminal_reviewer_but_keep_findings(self):
        self.queue(self.event())
        self.route()
        name = "vera-12-r1-review"
        section = "verdicts/pr12-%s-r1-review.md" % self.sha[:7]
        self.put(section, "Review changes: fix the issue\n")
        self.queue(self.status(name, "review changes"))
        self.route()
        self.assertEqual(self.names(), ["ash"])
        self.assertEqual(self.pending(), [self.status(name, "review changes")])
        with open(os.path.join(self.state, section)) as f:
            self.assertEqual(f.read(), "Review changes: fix the issue\n")

    def test_new_head_deduplicates_live_queued_and_posted_pass(self):
        self.queue(self.event(), self.event())
        self.route()
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.crew("kill", "vera-12-r1-review", "--project", self.project).returncode, 0)
        self.live["reviews"] = [{"body": "<!-- crew:v1 role=reviewer-validator pass=review pr=12 sha=%s "
                                          "round=1 verdict=pass -->" % self.sha}]
        self.save()
        self.queue(self.event())
        self.route()
        self.assertEqual(len(self.windows()), 1)
        self.live["reviews"] = []
        self.save()
        self.put("spawn-queue.jsonl", json.dumps(dict(role="reviewer", pr=12, issue=None, head=self.sha,
                                                     **{"pass": "review", "round": 1, "tier": "default"})) + "\n")
        self.queue(self.event())
        self.route()
        self.assertEqual(len(self.windows()), 1)
        self.queue(dict(self.event(), round=2))
        self.route()
        self.assertIn("vera-12-r2-review", self.names())

    def test_capped_validation_dequeues_after_review_kill(self):
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\nreviewers = 1\n')
        self.queue(self.event())
        self.route()
        self.put("status/vera-12-r1-review.status", "done: #12 %s review pass\n" % self.sha)
        self.queue(self.status("vera-12-r1-review", "review pass"))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r1-validate"])
        self.assertIn("queued: reviewer validate", self.transcript[-1][1].stdout)
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            self.assertEqual(f.read(), "")

    def test_new_head_starts_with_red_ci_but_validation_waits(self):
        self.live["statusCheckRollup"] = [{"status": "COMPLETED", "conclusion": "FAILURE"}]
        self.save()
        self.queue(self.event())
        self.route()
        self.queue(self.status("vera-12-r1-review", "review pass"))
        self.route()
        self.assertEqual(len(self.pending()), 1)
        self.assertIn("vera-12-r1-review", self.names())

    def test_judgement_and_progress(self):
        records = [dict(reason=reason, window="ben-7", line=line) for reason, line in
                   [("status", "blocked: #7"), ("status", "failed: #7"), ("dialog", ""), ("stale", ""),
                    ("ask", "")]]
        records += [self.event("ci-failed"), self.event("review-changes-requested")]
        self.queue(*records, dict(reason="status", line="ack: msg"), dict(reason="status", line="heartbeat: now"))
        self.route()
        self.assertEqual(self.pending(), records)

    def test_stale_hold_escalated_and_draft_go_to_coordinator(self):
        for change in (dict(headRefOid="f" * 40), dict(labels=[{"name": "crew:hold"}]),
                       dict(labels=[{"name": "crew:escalated"}]), dict(isDraft=True), dict(state="CLOSED")):
            with self.subTest(change=change):
                before = dict(self.live)
                self.live.update(change)
                self.save()
                self.queue(self.event())
                self.route()
                self.assertEqual(self.pending(), [self.event()])
                self.live = before
        self.assertEqual(self.windows(), [])

    def test_nonblocking_hold_allows_review(self):
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\nhold_label_blocks = false\n')
        self.live["labels"] = [{"name": "crew:hold"}]
        self.save()
        self.queue(self.event())
        self.route()
        self.assertEqual(self.pending(), [])

    def test_spawn_refuses_head_that_changed_after_live_read(self):
        self.live["headRefOid"] = "f" * 40
        self.save()
        self.queue(dict(self.event(), refs=["#12", "f" * 40]))
        self.route()
        self.assertIn("spawn failed", self.pending()[0]["route_error"])
        self.assertEqual(self.windows(), [])

    def test_merged_closeout_and_synthesizer_terminal(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        self.put("inbox/sam.jsonl", "")
        self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
        self.route()
        self.assertNotIn("sam", self.names())
        self.live.update(state="MERGED", labels=[{"name": n} for n in
                         ["crew:approved", "crew:hold", "crew:in-review", "crew:changes"]])
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        calls = self.gh_calls()
        self.assertEqual(sum(c[:2] == ["pr", "edit"] for c in calls), 4)
        self.assertIn(["issue", "edit", "7", "-R", "acme/widgets", "--remove-label", "crew:ready"], calls)
        self.assertIn(["api", "-X", "DELETE", "repos/acme/widgets/git/refs/heads/builder/7-feature"], calls)
        self.assertEqual(self.names(), ["ash"])
        self.assertEqual(self.pending(), [])

    def test_synthesizer_done_preserves_pending_inbox(self):
        for kind, acknowledged in (("land", False), ("land", True), ("fix", False)):
            with self.subTest(kind=kind, acknowledged=acknowledged):
                self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
                message = dict(id="pending", kind=kind, refs=["#13", "f" * 40])
                self.put("inbox/sam.jsonl", json.dumps(message) + "\n")
                self.put("status/sam.status", "ack: pending\n" if acknowledged else "")
                self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
                self.route()
                self.assertIn("sam", self.names())
                with open(os.path.join(self.state, "inbox/sam.jsonl")) as f:
                    self.assertEqual(json.loads(f.read()), message)
                self.assertEqual(self.pending(), [])
                self.transcript.append(("state", "%s (ack=%s): sam retained; pending inbox message preserved" %
                                        (kind, acknowledged)))
                self.put("status/sam.status", "ack: pending\ndone: #13 %s\n" % ("f" * 40))
                self.queue(dict(reason="status", window="sam", line="done: #13 " + "f" * 40))
                self.route()
                self.assertNotIn("sam", self.names())
                self.assertFalse(os.path.exists(os.path.join(self.state, "inbox/sam.jsonl")))
                self.transcript.append(("state", "request completed: sam reaped; inbox removed; queued wakes: []"))

    def test_synthesizer_done_reaps_completed_land_history(self):
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        messages = [dict(id="first", kind="land", refs=["#12", self.sha]),
                    dict(id="second", kind="land", refs=["#13", "f" * 40])]
        self.put("inbox/sam.jsonl", "".join(json.dumps(m) + "\n" for m in messages))
        self.put("status/sam.status", "ack: first\ndone: #12 %s\nack: second\n" % self.sha)
        self.queue(dict(reason="status", window="sam", line="done: #13 " + "f" * 40))
        self.route()
        self.assertNotIn("sam", self.names())
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox/sam.jsonl")))

    def test_merged_protected_branches_are_retained(self):
        for change in (dict(isCrossRepository=True), dict(headRefName="main"),
                       dict(headRefName="release", baseRefName="release")):
            with self.subTest(change=change):
                self.live.update(state="MERGED", **change)
                self.save()
                self.queue(self.event("pr-merged"))
                self.route()
        self.assertFalse(any(c[:3] == ["api", "-X", "DELETE"] for c in self.gh_calls()))

    def test_interrupted_batch_retries_and_section_marker_deduplicates(self):
        marker = "<!-- crew:v1 role=reviewer-validator pass=review pr=12 sha=%s round=1 verdict=pass -->" % self.sha
        self.put("verdicts/pr12-%s-r1-review.md" % self.sha[:7], marker)
        self.put("wake/queue.jsonl.route-interrupted", json.dumps(self.event()) + "\n")
        self.route()
        self.assertEqual(self.windows(), [])
        self.assertEqual(self.pending(), [])
        self.assertFalse(os.path.exists(os.path.join(self.state, "wake/queue.jsonl.route-interrupted")))

    def test_ownership_refusal_leaves_queue_untouched(self):
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('[repo]\n', '[repo]\ncontrol_item = 1\n').replace('[runtime]\n', '[runtime]\ninstance = \"fixture\"\n'))
        self.queue(self.event())
        self.route()
        self.assertEqual(self.pending(), [self.event()])
        self.assertEqual(self.windows(), [])

    def test_failed_action_is_retained(self):
        os.remove(self.data)
        self.queue(self.event())
        self.route()
        self.assertIn("gh pr view", self.pending()[0]["route_error"])

    def test_watcher_routes_and_continues_until_judgement(self):
        self.queue(self.event())
        source = os.path.join(self.tmp, "source.py")
        with open(source, "w") as f:
            f.write("import json, os\np = %r\n"
                    "if os.path.exists(p):\n"
                    "    print('owner asks for status')\n" % os.path.join(self.state, "runs", "vera-12-r1-review.json"))
        r = self.crew("watch", "--project", self.project, "--no-nudge", "--interval", ".01",
                      "--source", shlex.join([sys.executable, source]), "--backstop", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual([w["event"] for w in self.pending()], ["owner asks for status"])
        self.assertFalse(any(c[0] == "send-keys" for c in self.calls()))


if __name__ == "__main__":
    if "--transcript" in sys.argv or "--inbox-transcript" in sys.argv:
        method = "test_synthesizer_done_preserves_pending_inbox" if "--inbox-transcript" in sys.argv else "test_lifecycle"
        test = Route(method)
        test.setUp()
        try:
            getattr(test, method)()
            for cmd, result in test.transcript:
                if cmd == "state":
                    print(result)
                else:
                    print("$ " + cmd + "\nexit: %s\n--- stdout" % result.returncode)
                    print(result.stdout.replace(test.tmp, "<fixture>").replace(test.sha[:7], "<sha7>"), end="")
                    print("--- stderr\n" + result.stderr, end="")
        finally:
            test.doCleanups()
    else:
        unittest.main()
