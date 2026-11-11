"""Tests for zero-token routing with fake tmux and gh: review/validate lifecycle, caps and head deduplication,
merged close-out and protected branches, dependency merges that wake the coordinator (#814), milestone-closing and release-cut merges that wake it too (#1559), express changes skipped by the reviewer pool (#672), a queued researcher done: sparing a same-name respawn (#1092), ownership and judgement handoff, and watcher continuation.
Run in CI. --transcript and --inbox-transcript print reproducible CLI lifecycles with volatile fixture paths and
SHAs scrubbed.
"""
import json
import os
import shlex
import subprocess
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import FAKE_PS, FAKE_TMUX_PANES, SpawnBase


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
                    "elif args[:2] == ['pr', 'edit'] and 'crew:approved' in args:\n"  # a tag edit lands, except _sticky ones
                    "    names = [l['name'] for l in pr['labels']]\n"
                    "    for flag, name in zip(args, args[1:]):\n"
                    "        if flag == '--add-label' and name not in names: names.append(name)\n"
                    "        if flag == '--remove-label' and name not in pr.get('_sticky', []): names.remove(name)\n"
                    "    pr['labels'] = [{'name': n} for n in names]; json.dump(pr, open(%r, 'w'))\n"
                    "elif args[:2] == ['repo', 'view']: print(json.dumps({'defaultBranchRef': {'name': 'main'}}))\n"
                    "elif args[:2] == ['issue', 'view']: print(json.dumps(pr.get('_issue', {'labels': [{'name': 'crew:ready'}], 'state': 'CLOSED', 'stateReason': 'COMPLETED'})))\n"
                    "elif args[:1] == ['api'] and '/files' in args[1]: print(json.dumps(pr.get('_files', [])))\n"
                    "elif args[:1] == ['api'] and '/milestones/' in args[1]: print(json.dumps(pr.get('_milestone', {})))\n"
                    "elif args[:1] == ['api'] and '/actions/jobs/' in args[1]: print(json.dumps(pr.get('_job', {})))\n"
                    "elif args[:1] == ['api'] and '--paginate' in args: sys.exit(1)\n"
                    "elif args[:1] == ['api'] and '/commits/' in args[1]: print(json.dumps({'parents': pr['_parents']}))\n"
                    "elif args[:1] == ['api'] and '/compare/' in args[1]: print(json.dumps({'status': pr['_comparison']}))\n"
                    "elif args[:1] == ['api'] and '-X' not in args: print('{}')\n"
                    "elif args[:2] == ['issue', 'list']: print(json.dumps(pr.get('_open', [])))\n"
                    "elif args[1:2] == ['list']: print('[]')\n" % (self.gh_log, self.data, self.data))
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
        self.transcript.append(("mdstack route --project <fixture>/crew.toml --timeout 1", r))
        return r

    def names(self):
        with open(self.state_file) as f:
            return sorted(json.load(f)["crew-acme-widgets"].values())

    @staticmethod
    def signed(body, login="acme-reviewer", name="Vera"):
        return dict(author={"login": login}, body=body + "\n— 🔍 %s (Reviewer) · codex · gpt-6.1-sol" % name)

    def gh_calls(self):
        with open(self.gh_log) as f:
            return [json.loads(line) for line in f]

    def test_missing_builder_and_queued_work_go_to_its_lead(self):
        bindir = os.path.join(self.tmp, "bin")
        os.rename(os.path.join(bindir, "tmux"), os.path.join(bindir, "tmux-base"))
        for name, text in (("tmux", FAKE_TMUX_PANES), ("ps", FAKE_PS)):
            with open(os.path.join(bindir, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(bindir, name), 0o755)
        self.env.update(FAKE_PANES=os.path.join(self.tmp, "panes.json"), FAKE_PS=os.path.join(self.tmp, "ps.json"))
        self.put("render/runtime/builder-lead.md", "Manage the builder pool.\n")
        message = dict(self.event("builder-message"), window="ben-7", id="fix-1", kind="fix")
        self.queue(message, dict(event="builder-queued", refs=["#7"]))
        self.route()
        self.assertIn("ben-lead", self.names())
        self.assertNotIn("ben-7", self.names())
        with open(os.path.join(self.state, "inbox", "ben-lead.jsonl")) as f:
            events = []
            for m in map(json.loads, f):
                with open(m["refs"][0]) as event_file:
                    events.append(json.load(event_file))
        self.assertEqual([e["event"] for e in events], ["builder-message", "builder-queued"])
        self.assertEqual(self.pending(), [])

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

    def test_solo_skips_builder_routing_but_keeps_independent_review(self):
        self.live["labels"] = [{"name": "crew:solo"}]
        self.save()
        message = dict(self.event("builder-message"), window="ben-7", kind="fix")
        self.queue(message, self.event())
        self.route()
        self.assertNotIn("ben-7", self.names())
        self.assertNotIn("ben-lead", self.names())
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual(self.pending(), [dict(message, consumer="coordinator")])


    def test_express_change_never_starts_a_reviewer_pass(self):  # #672
        record = ("[Ash/flavor] #7: express\nReason: small\n<!-- crew:v1 role=coordinator pass=flavor issue=7 "
                  "flavor=express default=standard -->")
        self.live.update(labels=[{"name": "crew:express"}], _files=[{"filename": "docs/a.md"}],
                         _issue={"labels": [], "comments": [{"author": {"login": "acme-bot"}, "body": record}]})
        self.save()
        self.queue(self.event(), dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha))
        self.assertIn("crew: route: #12 resolves express; the reviewer pool skips it", self.route().stdout)
        self.assertEqual((self.names(), self.pending()), (["ash"], []))
        self.live["_issue"] = {"labels": []}  # unreadable resolution: the crew lane reviews it
        self.save()
        self.queue(self.event())
        self.assertIn("crew lane: express resolution unreadable", self.route().stdout)
        self.assertIn("vera-12-r1-review", self.names())

    def test_recheck_escalation_starts_review_then_validation_at_same_round(self):
        r = self.spawn("reviewer", "--pr", "12", "--pass", "recheck", "--round", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.transcript.append(("mdstack spawn reviewer --pr 12 --pass recheck --round 2 --project <fixture>/crew.toml", r))
        name = "vera-12-r2-recheck"
        self.assertIn(name, self.names())
        self.queue(self.status(name, "recheck escalate"), self.status(name, "recheck escalate"))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r2-review"])
        self.assertEqual(self.record("vera-12-r2-review")["head"], self.sha)
        self.transcript.append(("state", "recheck escalation: recheck removed; one review created at the same head, round 2"))
        self.queue(self.status("vera-12-r2-review", "review pass"))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r2-validate"])
        self.assertEqual(self.pending(), [])
        self.transcript.append(("state", "review passed: review removed; validation created at the same head, round 2"))
        self.queue(self.status("vera-12-r2-validate", "validate pass"))
        self.route()
        self.assertEqual(self.names(), ["ash"])
        self.transcript.append(("state", "validation completed: reviewer runs removed; queued wakes: []"))

    def test_ci_infra_reclassified_and_validation_continues(self):
        self.live["statusCheckRollup"] = [dict(status="COMPLETED", conclusion="FAILURE",
                                              detailsUrl="https://github.com/acme/widgets/actions/runs/1/job/2")]
        self.live["_job"] = dict(status="completed", conclusion="failure", steps=[])
        self.save()
        self.queue(self.event(), self.event("ci-failed"))
        self.route()
        self.assertEqual(self.pending()[0]["event"], "ci-infra")
        self.assertEqual(self.pending()[0]["consumer"], "coordinator")
        self.transcript.append(("state", "zero-step failed job: ci-infra -> coordinator; no builder fix; CI remains non-green"))
        infra = self.pending()[0]
        self.queue(infra, self.status("vera-12-r1-review", "review pass"))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r1-validate"])
        self.assertEqual(self.pending(), [infra])
        self.transcript.append(("state", "review passed despite startup outage: validation created; review removed"))
        self.queue(infra, self.status("vera-12-r1-validate", "validate pass"))
        self.route()
        self.assertEqual(self.names(), ["ash"])
        self.assertEqual(self.pending(), [infra])
        self.transcript.append(("state", "validation completed: reviewer runs removed; only coordinator ci-infra notice remains"))

    def test_started_or_unknown_failed_job_blocks_validation(self):
        self.live["statusCheckRollup"] = [dict(status="COMPLETED", conclusion="FAILURE",
                                              detailsUrl="https://github.com/acme/widgets/actions/runs/1/job/2")]
        self.queue(self.event())
        self.route()
        for job in ({}, dict(status="completed", conclusion="failure", steps=[{"name": "test"}])):
            self.live["_job"] = job
            self.save()
            self.queue(self.status("vera-12-r1-review", "review pass"))
            self.route()
            self.assertEqual(len(self.pending()), 1)
            self.assertIn("vera-12-r1-review", self.names())

    def test_builder_lifetime_reuses_fix_and_ci_messages_then_reaps(self):
        result = self.spawn("builder", "--issue", "7")
        self.assertEqual(result.returncode, 0)
        self.transcript.append(("mdstack spawn builder --issue 7 --project <fixture>/crew.toml", result))
        worktree = self.record("ben-7")["worktree"]
        done = "done: #7 #12 " + self.sha
        self.put("status/ben-7.status", done + "\n")
        self.queue(dict(reason="status", window="ben-7", line=done))
        self.route()
        self.assertIn("ben-7", self.names())
        for kind in ("fix", "ci-red"):
            result = self.crew("send", "ben-7", kind, "#12", self.sha, "--project", self.project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.transcript.append(("mdstack send ben-7 %s '#12' <head-sha> --project <fixture>/crew.toml" % kind, result))
            self.assertEqual(self.record("ben-7")["worktree"], worktree)
        with open(os.path.join(self.state, "inbox", "ben-7.jsonl")) as f:
            self.assertEqual([json.loads(line)["kind"] for line in f], ["fix", "ci-red"])
        self.live["state"] = "MERGED"
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertNotIn("ben-7", self.names())
        self.assertFalse(os.path.exists(worktree))
        for path in ("runs/ben-7.json", "claims/builder-issue7", "inbox/ben-7.jsonl"):
            self.assertFalse(os.path.exists(os.path.join(self.state, path)))
        self.transcript.append(("state", "done: builder retained; fix and ci-red reused its worktree; merge reaped it"))
        self.transcript.append(("state", "builder window, worktree, run record, claim and inbox: absent"))

    def test_later_message_respawns_reclaimed_builder_through_route(self):
        self.spawn("builder", "--issue", "7")
        self.crew("kill", "ben-7", "--project", self.project)
        result = self.crew("send", "ben-7", "fix", "#12", self.sha, "--project", self.project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("ben-7", self.names())
        self.route()
        self.assertIn("ben-7", self.names())
        self.assertEqual(self.record("ben-7")["args"]["pr"], 12)
        with open(os.path.join(self.state, "inbox", "ben-7.jsonl")) as f:
            self.assertEqual(json.load(f)["refs"], ["#12", self.sha])
        self.assertEqual(self.pending(), [])
        self.transcript.append(("state", "missing builder: send queued refs; route respawned builder fix and delivered refs"))

    def test_replacement_message_waits_in_spawn_queue_until_capacity(self):
        with open(self.project, "a") as f:
            f.write("\n[runtime.options]\nbuilders = 1\n")
        self.spawn("builder", "--issue", "8")
        self.crew("send", "ben-7", "fix", "#12", self.sha, "--project", self.project)
        self.route()
        self.assertNotIn("ben-7", self.names())
        self.assertEqual(self.pending(), [])
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            queued = json.load(f)
        self.assertEqual(queued["messages"][0]["refs"], ["#12", self.sha])
        self.put("status/ben-8.status", "done: #8 #13 " + self.sha + "\n")
        self.route()
        self.assertIn("ben-7", self.names())
        with open(os.path.join(self.state, "inbox", "ben-7.jsonl")) as f:
            self.assertEqual(json.load(f)["refs"], ["#12", self.sha])
        self.assertEqual(self.pending(), [])

    def test_closed_pr_reaps_builder_without_merged_closeout(self):
        self.spawn("builder", "--issue", "7")
        worktree = self.record("ben-7")["worktree"]
        self.live["state"] = "CLOSED"
        self.save()
        self.queue(self.event("pr-closed"))
        self.route()
        self.assertNotIn("ben-7", self.names())
        self.assertFalse(os.path.exists(worktree))
        self.assertFalse(any(c[:2] == ["pr", "edit"] for c in self.gh_calls()))
        self.assertEqual(self.pending(), [])

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
        self.live["reviews"] = [self.signed(
            "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=1 verdict=changes -->\n"
            "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=2 verdict=pass -->"
            % ("0" * 40, previous))]
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

    def synthesizer_lead(self):
        bindir = os.path.join(self.tmp, "bin")
        os.rename(os.path.join(bindir, "tmux"), os.path.join(bindir, "tmux-base"))
        for name, text in (("tmux", FAKE_TMUX_PANES), ("ps", FAKE_PS)):
            with open(os.path.join(bindir, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(bindir, name), 0o755)
        self.env.update(FAKE_PANES=os.path.join(self.tmp, "panes.json"), FAKE_PS=os.path.join(self.tmp, "ps.json"))
        self.put("render/runtime/synthesizer-lead.md", "Land approved PRs.\n")

    def land_queue(self):
        path = os.path.join(self.state, "inbox", "sam-lead.jsonl")
        if not os.path.exists(path):
            return []
        events = []
        with open(path) as f:
            for m in map(json.loads, f):
                with open(m["refs"][0]) as event_file:
                    events.append(json.load(event_file)["event"])
        return events

    def test_land_events_go_to_the_synthesizer_lead_not_the_coordinator(self):  # #1569
        self.synthesizer_lead()
        previous = self.approved_push()
        self.queue(self.event("review-approved"), self.event("ci-passed"),
                   dict(self.event("merge-up"), previous_head=previous, round=2))
        self.route()
        self.assertEqual(self.pending(), [])
        self.assertIn("sam-lead", self.names())
        self.assertEqual(self.land_queue(), ["review-approved", "ci-passed", "merge-up"])
        self.live["reviews"] = [dict(body="<!-- crew:v1 role=builder pass=selfgate pr=12 sha=%s verdict=pass -->"
                                          % self.sha)]
        self.save()
        self.queue(self.event("selfgate-passed"), self.event("ci-passed"))
        self.route()
        self.assertEqual(self.pending(), [])
        self.assertEqual(self.land_queue(), ["review-approved", "ci-passed", "merge-up", "selfgate-passed"])
        self.live["reviews"] = [dict(body="[Ash/steer] merge-ok\n<!-- crew:v1 role=coordinator pass=steer pr=12 sha=%s "
                                          "round=n/a verdict=n/a cmd=merge-ok cmd-id=chat -->" % self.sha)]
        self.save()
        self.queue(dict(self.event("ci-passed"), id="merge-ok"))  # the §7 approval override counts too
        self.route()
        self.assertEqual(self.pending(), [])
        self.assertEqual(self.land_queue()[-1], "ci-passed")
        self.assertEqual(len(self.land_queue()), 5)

    def test_unapproved_superseded_and_held_land_events(self):  # #1569
        self.synthesizer_lead()
        superseded = dict(event="review-approved", refs=["#12", "f" * 40])
        self.queue(self.event("ci-passed"), superseded)
        self.route()
        self.assertEqual((self.pending(), self.land_queue()), ([], []))
        self.put("ci/12-%s.json" % self.sha, "{}")  # held CI failure: the coordinator drops it on green
        self.live["labels"] = []
        self.save()
        self.queue(self.event("ci-passed"))
        self.route()
        self.assertEqual(self.pending(), [self.event("ci-passed")])
        self.live["labels"] = [{"name": "crew:hold"}]
        self.save()
        self.put("wake/queue.jsonl", "")
        self.queue(self.event("review-approved"))
        self.route()
        self.assertEqual(self.pending(), [self.event("review-approved")])
        self.assertEqual(self.land_queue(), [])

    def passed_after_changes(self, *extra, login="acme-reviewer", name="Vera", sha=None):
        verdict = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=%d verdict=%s -->"
        self.live.update(labels=[{"name": "crew:changes"}, {"name": "crew:in-review"}], reviews=[
            self.signed(verdict % ("0" * 40, 1, "changes")),
            dict(body="<!-- crew:v1 role=builder pass=fix pr=12 sha=%s round=1 verdict=n/a -->" % self.sha),
            self.signed(verdict % (sha or self.sha, 2, "pass"), login=login, name=name), *extra])
        self.save()

    def tags(self):
        with open(self.data) as f:
            return sorted(label["name"] for label in json.load(f)["labels"])

    def test_passing_verdict_reconciles_superseded_tags_before_land(self):  # #1464
        self.synthesizer_lead()
        self.passed_after_changes()
        self.queue(self.event("review-approved"))
        self.route()
        self.assertEqual((self.pending(), self.land_queue()), ([], ["review-approved"]))
        self.assertEqual(self.tags(), ["crew:approved"])
        self.assertIn(["pr", "edit", "12", "-R", "acme/widgets", "--add-label", "crew:approved",
                       "--remove-label", "crew:changes", "--remove-label", "crew:in-review"], self.gh_calls())
        self.queue(self.event("review-approved"), self.event("ci-passed"))  # a replay edits nothing
        self.route()
        self.assertEqual(self.pending(), [])
        self.assertEqual(sum(c[:2] == ["pr", "edit"] for c in self.gh_calls()), 1)
        self.assertEqual(self.land_queue(), ["review-approved", "ci-passed"])  # the lead dedupes the replay

    def test_non_live_or_superseded_pass_keeps_the_changes_tag(self):  # #1464
        self.synthesizer_lead()
        verdict = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=2 verdict=changes -->"
        steer = "<!-- crew:v1 role=coordinator pass=steer pr=12 sha=%s round=2 verdict=n/a cmd=rereview cmd-id=r1 -->"
        for case, kw, extra in (
                ("foreign runtime", dict(name="Rex"), ()), ("other login", dict(login="someone"), ()),
                ("stale head", dict(sha="f" * 40), ()),
                ("later changes verdict", {}, (self.signed(verdict % self.sha),)),
                ("formal changes request", {}, (dict(self.signed("Needs work."), state="CHANGES_REQUESTED"),)),
                ("open rereview", {}, (dict(body=steer % self.sha),))):
            with self.subTest(case=case):
                self.passed_after_changes(*extra, **kw)
                self.queue(self.event("review-approved"))
                self.route()
                self.assertEqual(self.tags(), ["crew:changes", "crew:in-review"])
        self.assertFalse(any(c[:2] == ["pr", "edit"] for c in self.gh_calls()))
        self.passed_after_changes()
        self.live["labels"].append({"name": "crew:hold"})
        self.save()
        self.put("wake/queue.jsonl", "")
        self.queue(self.event("review-approved"))
        self.route()  # a hold keeps the event for the coordinator and its tags
        self.assertEqual(self.pending(), [self.event("review-approved")])
        self.assertEqual(self.tags(), ["crew:changes", "crew:hold", "crew:in-review"])

    def test_failed_tag_readback_never_forwards_land_work(self):  # #1464
        self.synthesizer_lead()
        self.passed_after_changes()
        self.live["_sticky"] = ["crew:changes"]
        self.save()
        self.queue(self.event("review-approved"))
        self.route()
        self.assertEqual(self.land_queue(), [])
        [left] = self.pending()
        self.assertIn("tag readback after approval: crew:approved,crew:changes", left["route_error"])

    def test_synthesizer_lead_status_wakes_coordinator_only_for_exceptions(self):  # #1569
        self.synthesizer_lead()
        self.queue(self.event("review-approved"))
        self.route()
        url = "https://github.com/acme/widgets/pull/12#pullrequestreview-1"
        gate = "blocked: #12 %s gate-status %s " % (self.sha, url)
        quiet = [dict(reason="status", window="sam-lead", line=line) for line in (
            "ack: m1", "done: #12 " + self.sha, "done: m1", gate + "wait=ci", gate + "wait=review,selfgate",
            "train-report n=3 members=12,13 landed=12,13 dropped=none stop=none path=train")]
        loud = [dict(reason="status", window="sam-lead", line=line) for line in (
            gate + "wait=ci,merge-ok", "blocked: #12 sensitive", "blocked: main red after #12 " + url,
            "train-report n=4 members=12,13 landed=none dropped=none stop=ci=fail path=train")]
        self.queue(*quiet, *loud)
        self.route()
        self.assertEqual(self.pending(), loud)
        self.assertIn("sam-lead", self.names())

    def test_non_merge_fix_push_gets_normal_review(self):
        self.approved_push(merge=False)
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha),
                   dict(self.event(), round=2))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r2-review"])
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.pending(), [])

    def test_merge_up_approved_only_by_another_runtime_gets_review(self):  # #1290
        self.approved_push()
        self.live["reviews"][0] = self.signed(self.live["reviews"][0]["body"].split("\n—")[0], name="Grok Bot")
        self.save()
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha))
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-12-r1-review"])

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
        self.live["reviews"] += [self.signed(verdict), dict(body="<!-- crew:v1 role=coordinator pass=steer "
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

    def test_finished_researcher_is_reaped_and_its_done_goes_to_the_coordinator(self):  # #584
        self.assertEqual(self.spawn("researcher", "--issue", "7").returncode, 0)
        done = dict(reason="status", window="riley-7", line="done: #7 research https://example.invalid/c/1")
        self.queue(done)
        self.route()
        self.assertEqual(self.names(), ["ash"])
        self.assertEqual(self.pending(), [done])
        self.assertFalse(os.path.exists(os.path.join(self.state, "runs", "riley-7.json")))

    def test_queued_researcher_done_spares_a_respawn_under_the_same_name(self):  # #1092
        self.assertEqual(self.spawn("researcher", "--issue", "7").returncode, 0)
        run = os.path.join(self.state, "runs", "riley-7.json")
        with open(run) as f:
            first = json.load(f)
        # the fake tmux gives no pane identity, so a respawn in the same second would match on start alone (#1453)
        first["start"] = "2000-01-01T00:00:00Z"
        with open(run, "w") as f:
            json.dump(first, f)
        done = dict(reason="status", window="riley-7", line="done: #7 research https://example.invalid/c/1",
                    run=[first.get(k) for k in ("start", "pane_id", "pane_pid", "pane_start", "worktree")])
        self.queue(done)
        self.route()
        self.assertNotIn("riley-7", self.names())
        self.assertEqual(self.spawn("researcher", "--issue", "7").returncode, 0)
        with open(os.path.join(self.state, "runs", "riley-7.json")) as f:
            second = json.load(f)
        self.assertNotEqual(done["run"], [second.get(k) for k in ("start", "pane_id", "pane_pid", "pane_start", "worktree")])
        self.route()
        self.assertIn("riley-7", self.names())
        self.assertTrue(os.path.exists(os.path.join(self.state, "runs", "riley-7.json")))
        self.assertEqual(self.pending(), [done])

    def test_reflection_done_relays_its_report_and_reaps_only_its_window(self):  # #1520
        self.assertEqual(self.spawn("researcher", "--reflection", "close-3").returncode, 0)
        old = dict(reason="status", window="riley-reflection", line="done: reflection close-2 https://example.invalid/5#c1")
        self.queue(old)
        self.route()
        self.assertIn("riley-reflection", self.names())  # an earlier window's completion never reaps this run
        self.assertEqual(self.pending(), [dict(old, report="https://example.invalid/5#c1")])
        done = dict(reason="status", window="riley-reflection", line="done: reflection close-3 https://example.invalid/5#c2")
        self.queue(done)
        self.route()
        self.assertNotIn("riley-reflection", self.names())
        self.assertEqual(self.pending()[-1], dict(done, report="https://example.invalid/5#c2"))

    def test_new_head_deduplicates_live_queued_and_posted_pass(self):
        self.queue(self.event(), self.event())
        self.route()
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.crew("kill", "vera-12-r1-review", "--project", self.project).returncode, 0)
        self.live["reviews"] = [self.signed("<!-- crew:v1 role=reviewer-validator pass=review pr=12 sha=%s "
                                            "round=1 verdict=pass -->" % self.sha)]
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

    def test_another_runtimes_posted_pass_never_suppresses_review(self):  # #1290
        marker = "<!-- crew:v1 role=reviewer-validator pass=review pr=12 sha=%s round=1 verdict=pass -->" % self.sha
        self.live["reviews"] = [dict(body=marker), self.signed(marker, login="other-bot"),
                                self.signed(marker, name="Grok Bot")]
        self.save()
        self.queue(self.event())
        self.route()
        self.assertIn("vera-12-r1-review", self.names())

    def test_another_runtimes_verdict_at_head_never_gates_new_head_review(self):  # #1290
        verdict = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=1 verdict=pass -->" % self.sha
        self.live["reviews"] = [dict(body=verdict), self.signed(verdict, login="other-bot"),
                                self.signed(verdict, name="Grok Bot")]
        self.save()
        self.queue(self.event())
        self.route()
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual(self.crew("kill", "vera-12-r1-review", "--project", self.project).returncode, 0)
        self.live["reviews"].append(self.signed(verdict))
        self.save()
        self.queue(self.event())
        self.route()
        self.assertEqual(len(self.windows()), 1)
        self.assertEqual(self.pending(), [])

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

    def test_superseded_ci_failed_dropped(self):  # #578
        self.live["headRefOid"] = "f" * 40
        self.save()
        self.queue(self.event("ci-failed"))
        self.route()
        self.assertEqual(self.pending(), [])

    def test_waiting_gate_status_recorded_routing_blocks_wake(self):  # #578
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        url = "https://github.com/acme/widgets/pull/12#pullrequestreview-1"
        line = "blocked: #12 %s gate-status %s " % (self.sha, url)
        waiting = [dict(reason="status", window="sam", line=line + tail)
                   for tail in ("wait=ci", "wait=review", "wait=ci,validation,train", "wait=ci,selfgate")]
        routing = [dict(reason="status", window="sam", line=line.rstrip()),
                   dict(reason="status", window="sam", line=line + "wait=ci,merge-ok"),
                   dict(reason="status", window="sam", line=line + "wait=conflicts"),
                   dict(reason="status", window="sam", line="blocked: #12 mirror")]
        self.queue(*waiting, *routing)
        self.route()
        self.assertEqual(self.pending(), routing)
        self.assertIn("sam", self.names())

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

    def test_hold_blocks_review_even_when_hold_label_blocks_is_false(self):
        with open(self.project, "a") as f:
            f.write('\n[runtime.options]\nhold_label_blocks = false\n')
        self.live["labels"] = [{"name": "crew:hold"}]
        self.save()
        self.queue(self.event())
        self.route()
        self.assertEqual(self.pending(), [self.event()])
        self.assertEqual(self.windows(), [])

    def test_repeated_head_with_newest_verdict_opens_no_round(self):
        verdict = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=12 sha=%s round=1 verdict=changes -->" % self.sha
        self.live["reviews"] = [self.signed(verdict)]
        self.save()
        self.queue(dict(self.event(), round=2), dict(self.event("fix-at-head"), round=2))
        self.route()
        self.assertEqual(self.pending(), [])
        self.assertEqual(self.windows(), [])
        fix = "<!-- crew:v1 role=builder pass=fix pr=12 sha=%s round=1 verdict=n/a -->" % self.sha
        self.live["reviews"].append(dict(body=fix))
        self.save()
        self.queue(dict(self.event("fix-at-head"), round=2))
        self.route()
        self.assertIn("vera-12-r2-review", self.names())

    def test_spawn_refuses_head_that_changed_after_live_read(self):
        self.live["headRefOid"] = "f" * 40
        self.save()
        self.queue(dict(self.event(), refs=["#12", "f" * 40]))
        self.route()
        self.assertIn("spawn failed", self.pending()[0]["route_error"])
        self.assertEqual(self.windows(), [])

    def test_slack_land_reaches_coordinator_after_mechanical_cleanup(self):
        with open(self.project, "a") as f:
            f.write('\n[backends.owner-channel]\nname = "slack"\n[runtime.options]\n'
                    'slack_webhook_env = "CREW_TEST_WEBHOOK"\n')
        self.live.update(state="MERGED")
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertEqual(self.pending(), [self.event("pr-merged")])
        self.assertIn(["api", "-X", "DELETE", "repos/acme/widgets/git/refs/heads/builder/7-feature"], self.gh_calls())

    def test_lead_land_closeout_needs_no_coordinator_turn(self):  # #1569
        self.synthesizer_lead()
        self.put("render/runtime/builder-lead.md", "Manage the builder pool.\n")
        with open(self.project, "a") as f:
            f.write('\n[backends.owner-channel]\nname = "slack"\n[runtime.options]\n'
                    'slack_webhook_env = "CREW_TEST_WEBHOOK"\n')
        self.live.update(state="MERGED", title="Feature", milestone={"title": "M40"},
                         _open=[dict(number=9, body="## Depends on\n\n#7. Start after.\n")])
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertEqual(self.pending(), [])
        self.assertIn(["api", "-X", "DELETE", "repos/acme/widgets/git/refs/heads/builder/7-feature"], self.gh_calls())
        with open(os.path.join(self.state, "wake", "land-12.json")) as f:
            self.assertEqual(json.load(f), dict(id="land-12", kind="land", url="https://github.com/acme/widgets/pull/12",
                                                title="Feature", train="direct", milestone="M40"))
        with open(os.path.join(self.state, "inbox", "ben-lead.jsonl")) as f:
            self.assertEqual([(m["kind"], m["refs"]) for m in map(json.loads, f)], [("build", ["#9"])])
        self.live["_issue"] = {"labels": [], "state": "CLOSED", "stateReason": "COMPLETED"}  # #9 not released yet
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertEqual(self.pending(), [dict(self.event("pr-merged"), consumer="coordinator", dependents=["#9"])])

    def test_dependency_merge_reaches_coordinator_after_cleanup(self):
        self.live.update(state="MERGED", _open=[dict(number=9, body="## Depends on\n\n#7. Start after.\n\n## AC\n#1"),
                                                dict(number=10, body="Depends on #3\n"),
                                                dict(number=11, body="See #7.\n")])
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertEqual(self.pending(), [self.event("pr-merged", consumer="coordinator", dependents=["#9"])])
        self.assertIn(["api", "-X", "DELETE", "repos/acme/widgets/git/refs/heads/builder/7-feature"], self.gh_calls())
        self.live["_open"] = [dict(number=10, body="Depends on #3\n")]
        self.save()
        os.remove(os.path.join(self.state, "wake", "queue.jsonl"))
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertEqual(self.pending(), [])

    def test_milestone_closing_or_release_cut_merge_reaches_coordinator(self):  # #1559
        cut = [dict(filename="CHANGELOG.md", patch="@@ -8,2 +8,4 @@\n ## [Unreleased]\n+\n+## [7.5.0] - 2026-11-10\n")]
        entry = [dict(filename="CHANGELOG.md", patch="@@ -8,2 +8,3 @@\n ## [Unreleased]\n+- A fix. (issue #7)\n")]
        issue = dict(labels=[], state="CLOSED", stateReason="COMPLETED", milestone=dict(number=40, title="M40"))
        for name, extra, woken in (
                ("last open item", dict(_issue=issue, _milestone=dict(state="open", open_issues=0)), True),
                ("release cut", dict(_files=cut), True),
                ("items left", dict(_issue=issue, _milestone=dict(state="open", open_issues=2)), False),
                ("milestone already closed", dict(_issue=issue, _milestone=dict(state="closed", open_issues=0)), False),
                ("no milestone, changelog entry only", dict(_files=entry), False)):
            with self.subTest(name):
                self.live.pop("_issue", None)
                self.live.update(dict(state="MERGED", _milestone={}, _files=[]), **extra)
                self.save()
                self.queue(self.event("pr-merged"))
                self.route()
                self.assertEqual(self.pending(), [self.event("pr-merged", consumer="coordinator",
                                                             note="milestone-complete")] if woken else [])
                self.assertIn(["api", "-X", "DELETE", "repos/acme/widgets/git/refs/heads/builder/7-feature"],
                              self.gh_calls())
                if os.path.exists(os.path.join(self.state, "wake", "queue.jsonl")):
                    os.remove(os.path.join(self.state, "wake", "queue.jsonl"))

    def test_watcher_wakes_coordinator_on_dependency_merge(self):
        self.live.update(state="MERGED", _open=[dict(number=9, body="## Depends on\n\n#7\n")])
        self.save()
        merged = self.event("pr-merged", id="poll-1", source="poll", reason="poll", consumer="builder")  # mdstack poll's shape
        self.queue(merged)
        r = self.crew("watch", "--project", self.project, "--no-nudge", "--interval", ".01", "--backstop", "30")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "poll: pr-merged")
        self.assertEqual(self.pending(), [dict(merged, consumer="coordinator", dependents=["#9"])])

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

    def test_merged_closeout_closes_linked_issue_left_open(self):  # #846
        for issue, closed in (({"state": "OPEN", "stateReason": ""}, True),
                              ({"state": "OPEN", "stateReason": "REOPENED"}, False),  # kept open on purpose (#917)
                              ({"state": "CLOSED", "stateReason": "COMPLETED"}, False)):
            with self.subTest(issue=issue):
                open(self.gh_log, "w").close()
                self.live.update(state="MERGED", _issue=dict(issue, labels=[]))
                self.save()
                self.queue(self.event("pr-merged"))
                self.route()
                calls = [c for c in self.gh_calls() if c[:2] == ["issue", "close"]]
                self.assertEqual(calls, [["issue", "close", "7", "-R", "acme/widgets", "--comment",
                                          "[Ash/close-out] #12 merged and closes this issue, but GitHub left it open; "
                                          "closed by close-out."]] if closed else [])
                self.assertEqual(self.pending(), [])

    def test_merged_closeout_keeps_synthesizer_through_main_ci(self):  # #1339
        for completion in ("done: #12 " + "a" * 40, "blocked: main red after #12 https://ci/run/1"):
            with self.subTest(completion=completion.split()[0]):
                self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
                self.put("inbox/sam.jsonl", "")
                self.put("status/sam.status", "")
                self.live["state"] = "MERGED"
                self.save()
                self.queue(self.event("pr-merged"))
                self.route()
                self.assertIn("sam", self.names())
                self.put("status/sam.status", completion + "\n")
                self.queue(self.event("pr-merged"))
                self.route()
                self.assertNotIn("sam", self.names())
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

    def test_resend_land_ignores_completions_before_ack(self):
        for previous in ("blocked: #13 ci-red", "done: #13"):
            with self.subTest(previous=previous):
                self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
                old = dict(id="old", kind="land", refs=["#13", "e" * 40])
                retry = dict(id="retry", kind="land", refs=["#13", "f" * 40])
                self.put("inbox/sam.jsonl", "".join(json.dumps(m) + "\n" for m in (old, retry)))
                self.put("status/sam.status", "ack: old\n" + previous + "\n")
                self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
                self.route()
                self.assertIn("sam", self.names())
                self.assertEqual(self.record("sam")["pending_lands"], [retry])
                self.transcript.append(("state", previous + ": unacked retry retained; pending_lands=1"))
                r = self.crew("kill", "sam", "--project", self.project)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.transcript.append(("mdstack kill sam --project <fixture>/crew.toml", r))
                r = self.spawn("synthesizer", "--pr", "12")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.record("sam")["pending_lands"], [retry])
                with open(os.path.join(self.state, "inbox/sam.jsonl")) as f:
                    self.assertEqual([json.loads(line) for line in f], [retry])
                self.transcript.append(("mdstack spawn synthesizer --pr 12 --project <fixture>/crew.toml", r))
                self.transcript.append(("state", "respawn: only retry restored; old completed land absent"))
                self.put("status/sam.status", "ack: retry\ndone: #13 " + "f" * 40 + "\n")
                self.queue(dict(reason="status", window="sam", line="done: #13 " + "f" * 40))
                self.route()
                self.assertNotIn("sam", self.names())
                self.assertFalse(os.path.exists(os.path.join(self.state, "inbox/sam.jsonl")))
                self.transcript.append(("state", "retry completed: run and inbox removed"))

    def test_stale_land_done_is_never_replayed(self):
        """#1187: a land the synthesizer stops on without posting closes with `done: <refs> stale`."""
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        legacy = dict(id="legacy", kind="land", refs=["#11"])
        old = dict(id="old", kind="land", refs=["#13", "e" * 40])
        retry = dict(id="retry", kind="land", refs=["#13", "f" * 40, "e" * 40])
        self.put("inbox/sam.jsonl", "".join(json.dumps(m) + "\n" for m in (legacy, old, retry)))
        self.put("status/sam.status", "ack: legacy\ndone: #11 stale\nack: old\nack: retry\n"
                 "done: #13 %s stale\n" % ("e" * 40))
        self.queue(dict(reason="status", window="sam", line="done: #13 %s stale" % ("e" * 40)))
        self.route()
        self.assertIn("sam", self.names())
        self.assertEqual(self.record("sam")["pending_lands"], [retry])
        self.assertEqual(self.pending(), [])
        r = self.crew("kill", "sam", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.spawn("synthesizer", "--pr", "12")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.record("sam")["pending_lands"], [retry])
        with open(os.path.join(self.state, "inbox/sam.jsonl")) as f:
            self.assertEqual([json.loads(line) for line in f], [retry])
        self.put("status/sam.status", "ack: retry\ndone: #13 %s stale\n" % ("f" * 40))
        self.queue(dict(reason="status", window="sam", line="done: #13 %s stale" % ("f" * 40)))
        self.route()
        self.assertNotIn("sam", self.names())
        self.assertEqual(self.pending(), [])

    def test_merged_closeout_keeps_acknowledged_lands(self):
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        message = dict(id="pending", kind="land", refs=["#13", "f" * 40])
        self.put("inbox/sam.jsonl", json.dumps(message) + "\n")
        self.put("status/sam.status", "ack: pending\ndone: #12 " + self.sha + "\n")
        self.live["state"] = "MERGED"
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertIn("sam", self.names())
        self.assertEqual(self.record("sam")["pending_lands"], [message])

    def test_terminal_synthesizer_dequeues_replacement(self):
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        self.put("spawn-queue.jsonl", json.dumps(dict(role="synthesizer", pr=12, issue=None, head=self.sha,
                                                     **{"pass": "land", "round": 1, "tier": "default"})) + "\n")
        self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
        self.route()
        self.assertIn("sam", self.names())
        self.assertEqual(len(self.windows()), 2)
        self.assertEqual(self.pending(), [])
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            self.assertEqual(f.read(), "")

    def test_synthesizer_kept_with_open_train(self):
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        self.put("trains/train-1.json", json.dumps(dict(n=1, members=[dict(pr=12)], landed=[])))
        self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
        self.route()
        self.assertIn("sam", self.names())
        self.live["state"] = "MERGED"
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertIn("sam", self.names())
        self.put("trains/train-1.json", json.dumps(dict(n=1, members=[dict(pr=12)], landed=[], closed=True)))
        self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
        self.route()
        self.assertNotIn("sam", self.names())

    def test_synthesizer_kept_with_land_lock(self):
        self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
        lock = self.crew("land-lock", "acquire", "--project", self.project, CREW_ID="")
        self.assertEqual(lock.returncode, 0, lock.stdout + lock.stderr)
        self.addCleanup(self.crew, "land-lock", "release", "--project", self.project)
        self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
        self.route()
        self.assertIn("sam", self.names())
        self.live["state"] = "MERGED"
        self.save()
        self.queue(self.event("pr-merged"))
        self.route()
        self.assertIn("sam", self.names())
        self.assertEqual(self.crew("land-lock", "release", "--project", self.project).returncode, 0)
        self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
        self.route()
        self.assertNotIn("sam", self.names())

    def test_pending_lands_recover_on_kill_and_missing_window(self):
        for crash in (False, True):
            with self.subTest(crash=crash):
                self.assertEqual(self.spawn("synthesizer", "--pr", "12").returncode, 0)
                messages = [dict(id="completed", kind="land", refs=["#12", self.sha]),
                            dict(id="pending", kind="land", refs=["#13", "f" * 40])]
                self.put("inbox/sam.jsonl", "".join(json.dumps(m) + "\n" for m in messages))
                self.put("status/sam.status", "ack: completed\ndone: #12 " + self.sha + "\nack: pending\n" +
                         "done: #13 " + "e" * 40 + "\n")
                self.put("trains/train-1.json", json.dumps(dict(n=1, members=[dict(pr=13)], landed=[])))
                if crash:
                    subprocess.run(["tmux", "kill-window", "-t", "crew-acme-widgets:1"], env=self.env, check=True)
                else:
                    r = self.crew("kill", "sam", "--project", self.project)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                r = self.spawn("synthesizer", "--pr", "12")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(self.record("sam")["pending_lands"], messages[1:])
                with open(os.path.join(self.state, "inbox/sam.jsonl")) as f:
                    self.assertEqual([json.loads(line) for line in f], messages[1:])
                with open(os.path.join(self.state, "runs/sam.brief.md")) as f:
                    brief = f.read()
                self.assertIn("trains/train-1.json", brief)
                self.assertIn("inbox: pending", brief)
                launch = self.windows()[-1][-1]
                self.assertIn("trains/train-1.json", launch)
                self.assertIn("Pending inbox IDs: pending", launch)
                self.assertNotIn("inbox: completed", brief)
                self.transcript.append(("mdstack spawn synthesizer --pr 12 --project <fixture>/crew.toml", r))
                self.transcript.append(("state", "crash=%s: restored only unfinished land #13; run pending_lands=1; "
                                        "first message names train-1.json and inbox ID pending" % crash))
                self.put("status/sam.status", "ack: pending\nblocked: #13 waiting\n")
                self.put("trains/train-1.json", json.dumps(dict(n=1, members=[dict(pr=13)], landed=[], closed=True)))
                self.queue(dict(reason="status", window="sam", line="done: #12 " + self.sha))
                self.route()
                self.assertNotIn("sam", self.names())

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
                      "--source", shlex.join([sys.executable, source]), "--source-interval", "0", "--backstop", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual([w["event"] for w in self.pending()], ["owner asks for status"])
        self.assertFalse(any(c[0] == "send-keys" for c in self.calls()))


if __name__ == "__main__":
    modes = {"--transcript": "test_lifecycle", "--inbox-transcript": "test_synthesizer_done_preserves_pending_inbox",
             "--recheck-transcript": "test_recheck_escalation_starts_review_then_validation_at_same_round",
             "--builder-transcript": "test_builder_lifetime_reuses_fix_and_ci_messages_then_reaps",
             "--replacement-transcript": "test_later_message_respawns_reclaimed_builder_through_route",
             "--infra-transcript": "test_ci_infra_reclassified_and_validation_continues",
             "--recovery-transcript": "test_pending_lands_recover_on_kill_and_missing_window",
             "--resend-transcript": "test_resend_land_ignores_completions_before_ack"}
    if any(flag in sys.argv for flag in modes):
        method = next(method for flag, method in modes.items() if flag in sys.argv)
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
