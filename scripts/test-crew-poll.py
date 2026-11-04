"""Tests for crew poll, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: the decision function on recorded `gh` JSON in `fixtures/poll/` (new-head ->
reviewer, ci-passed -> synthesizer, ci-failed -> builder, changes -> builder, approved -> synthesizer, merged ->
coordinator, no change -> nothing; `new-head` carries round `k`, reset by a cutover; an
evidence-only fix at the verdict head emits `fix-at-head` once; an intake `pass=ack` marker wakes nobody
and counts no round, #303) and `poll --once` against a fake `gh` (baseline, one wake record per change,
read-only calls); express routing (no reviewer event, `ci-passed` only with a selfgate pass at head,
`selfgate-passed` to the synthesizer, `new-head` on lane fallback, an unreadable resolution runs the crew lane, #672);
`gh` retries (a transient 5xx retried with bounded backoff, a persistent one a `Transient` error and
`--once` exit 75, a non-transient error never retried, other callers kept to one attempt, #702); the triage scan on
`fixtures/poll/triage-*.json` (each skip rule, owner replies, exact-key duplicate hints, card fields from the intake
template, P0 signals from defaults or a rules file, unreadable items and repos recorded, one wake per new P0, issue
reads only, off unless `triage.enabled`, #747). Run in CI.
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest import mock
from crew_testlib import Base, CREW, HERE


POLL = os.path.join(HERE, "fixtures", "poll")
HEAD = "1" * 40
# Fake gh: serves $FAKE_GH_DIR/{prs,issues,pr-<n>}.json for pr list / issue list / pr view; logs every call.
FAKE_GH = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    args, d = sys.argv[1:], os.environ["FAKE_GH_DIR"]
    with open(os.path.join(d, "gh.log"), "a") as f:
        f.write(json.dumps(args) + "\\n")
    name = ("job" if "/actions/jobs/" in args[1] else "commit" if "/commits/" in args[1] else "files" if "/files" in args[1]
            else "compare") if args[0] == "api" else (
        {("pr", "list"): "prs", ("issue", "list"): "issues"}.get(tuple(args[:2])) or args[0] + "-" + args[2])
    sys.stdout.write(open(os.path.join(d, name + ".json")).read())
    """)


def fixture(name):
    with open(os.path.join(POLL, name)) as f:
        return json.load(f)


def load_crew():
    from importlib.machinery import SourceFileLoader
    import importlib.util
    loader = SourceFileLoader("crew_cli", CREW)
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
    loader.exec_module(mod)
    return mod


class PollDecide(unittest.TestCase):
    """The pure decision function on recorded gh JSON fixtures: each change is one event for one consumer."""

    @classmethod
    def setUpClass(cls):
        cls.crew = load_crew()

    def decide(self, before, after, issues_before="issues-none.json", issues_after="issues-none.json"):
        _, state = self.crew.decide({}, fixture(before), fixture(issues_before))
        return self.crew.decide(state, fixture(after), fixture(issues_after))

    def only(self, before, after, **kw):
        events, _ = self.decide(before, after, **kw)
        return [(e["event"], e["consumer"], e["refs"]) for e in events]

    def test_landing_markers_preserve_stops_until_matching_resume(self):
        def post(cmd, extra="", role="coordinator"):
            return {"body": "<!-- crew:v1 role=%s pass=steer cmd=%s %s -->" % (role, cmd, extra)}
        urgent = post("urgent", "cmd-id=u pr=171 sha=" + HEAD)
        reviews = [urgent, post("stop-landing", "cmd-id=a sha=" + HEAD),
                   post("stop-landing", "cmd-id=b"), post("resume-landing", "stop-id=unknown"),
                   post("resume-landing", "stop-id=a"), post("resume-landing", "stop-id=b", role="builder")]
        result = self.crew.landing_steers(reviews)
        self.assertEqual(result["stops"], ["b"])
        self.assertEqual(result["urgent"][0]["sha"], HEAD)
        self.assertEqual(self.crew.landing_steers(reviews + [post("resume-landing", "stop-id=b")])["stops"], [])
        self.assertEqual(self.crew.pr_snapshot({"headRefOid": HEAD, "reviews": [urgent],
                                              "statusCheckRollup": []})["verdict"], None)

    def test_ci_passed_to_synthesizer_only(self):
        self.assertEqual(self.only("prs-pending.json", "prs-ci-passed.json"),
                         [("ci-passed", "synthesizer", ["#171", HEAD])])

    def test_ci_failed_to_builder(self):
        self.assertEqual(self.only("prs-pending.json", "prs-ci-failed.json"),
                         [("ci-failed", "builder", ["#171", HEAD])])

    def test_zero_step_failure_emits_infra_once_and_never_green(self):
        prs = fixture("prs-ci-failed.json")
        for check in prs[0]["statusCheckRollup"]:
            if check.get("conclusion") == "FAILURE":
                check["steps"] = []
        _, before = self.crew.decide({}, fixture("prs-pending.json"), [])
        events, state = self.crew.decide(before, prs, [])
        self.assertEqual([(e["event"], e["consumer"]) for e in events], [("ci-infra", "coordinator")])
        self.assertEqual(state["prs"]["171"]["ci"], "infra")
        self.assertEqual(self.crew.decide(state, prs, [])[0], [])
        prs[0]["statusCheckRollup"].append({"status": "COMPLETED", "conclusion": "FAILURE", "steps": [{}]})
        self.assertEqual(self.crew.pr_snapshot(prs[0])["ci"], "failed")

    def test_changes_verdict_to_builder(self):
        self.assertEqual(self.only("prs-ci-passed.json", "prs-changes.json"),
                         [("review-changes-requested", "builder", ["#171", HEAD])])

    def test_pass_verdict_to_synthesizer(self):
        self.assertEqual(self.only("prs-ci-passed.json", "prs-approved.json"),
                         [("review-approved", "synthesizer", ["#171", HEAD])])

    def test_merged_to_coordinator_and_dropped(self):
        _, state = self.crew.decide({}, fixture("prs-approved.json"), [])
        events, state = self.crew.decide(state, fixture("prs-none.json") + [fixture("pr-171-merged.json")], [])
        self.assertEqual([(e["event"], e["consumer"]) for e in events], [("pr-merged", "coordinator")])
        self.assertNotIn("171", state["prs"])
        closed = dict(fixture("pr-171-merged.json"), state="CLOSED")
        self.assertEqual([e["event"] for e in self.crew.decide({"prs": {"171": {}}}, [closed], [])[0]], ["pr-closed"])

    def test_no_change_nothing(self):
        for name in ["prs-pending.json", "prs-ci-passed.json", "prs-ci-failed.json", "prs-changes.json",
                     "prs-approved.json"]:
            self.assertEqual(self.only(name, name, issues_before="issues-ready.json",
                                       issues_after="issues-ready.json"), [], name)

    def test_assigned_ready_issue_to_builder(self):
        self.assertEqual(self.only("prs-pending.json", "prs-pending.json", issues_after="issues-ready.json"),
                         [("issue-assigned", "builder", ["#134"])])

    def test_hidden_marker_at_head_only_and_non_crew_pr_ignored(self):
        _, state = self.crew.decide({}, fixture("prs-ci-passed.json"), [])
        self.assertEqual(state["prs"], {"171": {"head": HEAD, "ci": "passed", "verdict": None, "round": 1,
                                                "fixed": False, "selfgate": None}})

    def test_every_event_has_exactly_one_consumer(self):
        self.assertEqual(sorted(self.crew.CONSUMER), sorted(["new-head", "ci-passed", "ci-failed", "ci-infra", "review-changes-requested",
                                                             "review-approved", "pr-merged", "pr-closed",
                                                             "issue-assigned", "fix-at-head", "merge-up",
                                                             "selfgate-passed"]))
        self.assertTrue(all(isinstance(v, str) for v in self.crew.CONSUMER.values()))


    def marked(self, name, *markers, at=None):
        """A fixture with one more review (or one inserted at index at) holding the given crew:v1 lines."""
        prs = fixture(name)
        review = {"body": "".join("<!-- crew:v1 %s -->\n" % m for m in markers)}
        prs[0]["reviews"].insert(len(prs[0]["reviews"]) if at is None else at, review)
        return prs

    def test_opened_and_pushed_heads_start_review_without_ci(self):
        for ci in ("prs-pending.json", "prs-ci-failed.json", "prs-ci-passed.json"):
            prs = fixture(ci)
            events, state = self.crew.decide({}, prs, [])
            self.assertEqual(events[0], {"event": "new-head", "consumer": "reviewer",
                                         "refs": ["#171", HEAD], "round": 1})
            self.assertEqual(self.crew.decide(state, prs, [])[0], [])
            prs[0]["headRefOid"] = "2" * 40
            events, _ = self.crew.decide(state, prs, [])
            self.assertEqual(events[0]["event"], "new-head")
            self.assertEqual(events[0]["refs"], ["#171", "2" * 40])
            self.assertEqual(sum(e["consumer"] == "reviewer" for e in events), 1)

    def express(self, prev, prs):
        events, state = self.crew.decide(prev, prs, [], express={"171"})
        return [(e["event"], e["consumer"]) for e in events], state

    def test_express_skips_reviewers_and_routes_selfgate_and_ci_to_synthesizer(self):  # #672
        selfgate = "role=builder pass=selfgate pr=171 sha=%s verdict=pass" % HEAD
        self.assertEqual(self.express({}, fixture("prs-pending.json"))[0], [])
        _, state = self.express({}, fixture("prs-ci-passed.json"))  # CI green alone wakes nobody
        self.assertEqual(state["prs"]["171"]["express"], True)
        events, state = self.express(state, self.marked("prs-ci-passed.json", selfgate))
        self.assertEqual(events, [("selfgate-passed", "synthesizer")])
        self.assertEqual(self.express(state, self.marked("prs-ci-passed.json", selfgate))[0], [])
        _, state = self.express({}, self.marked("prs-pending.json", selfgate))
        self.assertEqual(self.express(state, self.marked("prs-ci-passed.json", selfgate))[0], [("ci-passed", "synthesizer")])
        self.assertEqual(self.express({}, fixture("prs-ci-failed.json"))[0], [("ci-failed", "builder")])
        stale = "role=builder pass=selfgate pr=171 sha=%s verdict=pass" % ("0" * 40)
        self.assertEqual(self.express({}, self.marked("prs-ci-passed.json", stale))[0], [])
        changes = selfgate.replace("verdict=pass", "verdict=changes")
        self.assertEqual(self.express({}, self.marked("prs-ci-passed.json", changes))[0], [])

    def test_express_evidence_only_fix_wakes_no_reviewer(self):  # #672 r1: a changes verdict from before the lane
        changes = "role=reviewer-validator pass=verdict pr=171 sha=%s round=1 verdict=changes" % HEAD
        _, state = self.express({}, self.marked("prs-ci-passed.json", changes))
        fix = "role=builder pass=fix pr=171 sha=%s" % HEAD
        self.assertEqual(self.express(state, self.marked("prs-ci-passed.json", changes, fix))[0], [])

    def test_express_merge_up_carries_the_selfgate_to_ci_passed(self):  # #672 r2
        selfgate = "role=builder pass=selfgate pr=171 sha=%s verdict=pass" % HEAD
        _, state = self.express({}, self.marked("prs-ci-passed.json", selfgate))
        merged = self.marked("prs-pending.json", selfgate)
        merged[0]["headRefOid"] = "3" * 40
        events, state = self.crew.decide(state, merged, [], {"171": {"head": HEAD, "round": 1}}, express={"171"})
        self.assertEqual([(e["event"], e["consumer"], e.get("previous_head")) for e in events],
                         [("merge-up", "synthesizer", HEAD)])
        green = self.marked("prs-ci-passed.json", selfgate)
        green[0]["headRefOid"] = "3" * 40
        self.assertEqual(self.express(state, green)[0], [("ci-passed", "synthesizer")])
        _, state = self.express(state, green)
        self.assertEqual(self.express(state, green)[0], [])  # an idle poll at the carried head wakes nobody

    def test_express_fallback_emits_new_head_once(self):  # #672: the coordinator then hands normal review
        _, state = self.express({}, fixture("prs-pending.json"))
        events, state = self.crew.decide(state, fixture("prs-pending.json"), [])
        self.assertEqual(events, [{"event": "new-head", "consumer": "reviewer", "refs": ["#171", HEAD], "round": 1}])
        self.assertEqual(self.crew.decide(state, fixture("prs-pending.json"), [])[0], [])

    def test_new_head_carries_round_k(self):  # #139 F21
        old = "role=reviewer-validator pass=verdict pr=171 sha=%s round=1 verdict=changes" % ("2" * 40)
        prs = self.marked("prs-pending.json", old)
        events, _ = self.crew.decide({}, prs, [])
        self.assertEqual((events[0]["event"], events[0]["round"]), ("new-head", 2))
        cut = self.marked("prs-pending.json", old, "role=coordinator pass=cutover pr=171 sha=%s round=n/a "
                          "verdict=n/a" % HEAD)
        self.assertEqual(self.crew.decide({}, cut, [])[0][0]["round"], 1)  # §5: counted after a cutover

    def test_evidence_only_fix_at_same_head_wakes_reviewer_once(self):  # #139 B2
        fix = "role=builder pass=fix pr=171 sha=%s round=1 verdict=n/a engine=codex model=m effort=e" % HEAD
        _, state = self.crew.decide({}, fixture("prs-changes.json"), [])
        events, state = self.crew.decide(state, self.marked("prs-changes.json", fix), [])
        self.assertEqual([(e["event"], e["consumer"], e["refs"], e["round"]) for e in events],
                         [("fix-at-head", "reviewer", ["#171", HEAD], 2)])
        self.assertEqual(self.crew.decide(state, self.marked("prs-changes.json", fix), [])[0], [])
        _, state = self.crew.decide({}, fixture("prs-changes.json"), [])
        early = self.marked("prs-changes.json", fix, at=2)  # a fix note older than the verdict at head
        self.assertEqual(self.crew.decide(state, early, [])[0], [])

    def test_intake_ack_wakes_nobody_and_counts_no_round(self):  # #303: pass=ack is narrative only
        ack = "role=reviewer-validator pass=ack pr=171 sha=%s round=n/a verdict=n/a" % HEAD
        _, state = self.crew.decide({}, fixture("prs-ci-passed.json"), [])
        for acks in ([ack], [ack, ack]):  # one ack, and a repeated one: neither is an event
            self.assertEqual(self.crew.decide(state, self.marked("prs-ci-passed.json", *acks), [])[0], [])
        old = "role=reviewer-validator pass=verdict pr=171 sha=%s round=1 verdict=changes" % ("2" * 40)
        events, _ = self.crew.decide({}, self.marked("prs-pending.json", old, ack), [])
        self.assertEqual([(e["event"], e["round"]) for e in events], [("new-head", 2)])
        self.assertEqual(self.crew.decide({}, self.marked("prs-ci-passed.json", ack), [])[1]["prs"]["171"]["verdict"],
                         None)


class GhRetry(unittest.TestCase):
    """gh_json retries transient GitHub failures with bounded backoff before reporting (#702)."""

    @classmethod
    def setUpClass(cls):
        cls.poll = load_crew().commands()["poll"]

    def gh(self, *stderrs, retry=True):
        """Run gh_json against gh failing with each stderr in turn, then succeeding; return (result or error, sleeps,
        gh calls)."""
        results = [subprocess.CompletedProcess([], 1, "", e) for e in stderrs] + \
            [subprocess.CompletedProcess([], 0, "[1]", "")]
        with mock.patch("subprocess.run", side_effect=results) as run, mock.patch("time.sleep") as sleep:
            try:
                out = self.poll.gh_json("pr", "list", **({"retry": self.poll.RETRY_DELAYS} if retry else {}))
            except RuntimeError as e:
                out = e
        return out, [c.args[0] for c in sleep.call_args_list], run.call_count

    def test_transient_failure_retried_then_succeeds(self):
        bad = "HTTP 504: 504 Gateway Timeout (https://api.github.com/graphql)"
        self.assertEqual(self.gh(bad, "read: connection reset by peer"), ([1], [1, 2], 3))

    def test_persistent_transient_failure_is_bounded_and_marked(self):
        out, sleeps, calls = self.gh(*["HTTP 502: Bad Gateway"] * 4)
        self.assertIsInstance(out, self.poll.Transient)
        self.assertEqual((str(out), sleeps, calls), ("crew: gh pr list failed: HTTP 502: Bad Gateway", [1, 2, 4], 4))

    def test_non_transient_failure_is_not_retried(self):
        out, sleeps, calls = self.gh("HTTP 404: Not Found")
        self.assertIs(type(out), RuntimeError)
        self.assertEqual((sleeps, calls), ([], 1))

    def test_other_callers_keep_one_attempt(self):  # train_view records each failed read itself (#621)
        out, sleeps, calls = self.gh("HTTP 504: 504 Gateway Timeout", retry=False)
        self.assertIsInstance(out, self.poll.Transient)
        self.assertEqual((sleeps, calls), ([], 1))

    def test_once_exits_tempfail_on_transient_and_one_otherwise(self):
        args = mock.Mock(once=True)
        for error, code in [(self.poll.Transient("crew: gh pr list failed: HTTP 504"), 75),
                            (RuntimeError("crew: gh pr list failed: HTTP 404"), 1)]:
            with self.subTest(code=code), mock.patch.object(self.poll, "profile", return_value=({}, None, None)), \
                    mock.patch.object(self.poll, "poll_once", side_effect=error), mock.patch("builtins.print"):
                self.assertEqual(self.poll.run(args), code)


class Poll(Base):
    """crew poll --once against a fake gh: baseline, one wake record per change, read-only gh calls."""

    def setUp(self):
        super().setUp()
        self.gh_dir = os.path.join(self.tmp, "gh")
        os.makedirs(self.gh_dir)
        fake = os.path.join(self.tmp, "bin", "gh")
        with open(fake, "w") as f:
            f.write(FAKE_GH)
        os.chmod(fake, 0o755)
        self.env["FAKE_GH_DIR"] = self.gh_dir

    def serve(self, prs, issues="issues-none.json", **views):
        for dst, src in [("prs", prs), ("issues", issues)] + [("pr-" + n, s) for n, s in views.items()]:
            shutil.copy(os.path.join(POLL, src), os.path.join(self.gh_dir, dst + ".json"))
        r = self.crew("poll", "--once", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def queue(self):
        path = os.path.join(self.state, "wake", "queue.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f]

    def test_once_baseline_then_one_record_per_change(self):
        self.assertIn("baseline", self.serve("prs-none.json"))
        self.assertEqual(self.queue(), [])
        out = self.serve("prs-pending.json")
        self.assertIn("new-head -> reviewer #171 " + HEAD, out)
        (rec,) = self.queue()
        self.assertEqual(sorted(rec), ["consumer", "event", "id", "reason", "refs", "round", "source", "ts"])
        self.assertEqual((rec["source"], rec["reason"], rec["event"], rec["consumer"], rec["refs"]),
                         ("poll", "poll", "new-head", "reviewer", ["#171", HEAD]))
        self.serve("prs-pending.json")
        self.assertEqual(len(self.queue()), 1)
        self.serve("prs-none.json", **{"171": "pr-171-merged.json"})
        self.assertEqual([(r["event"], r["consumer"]) for r in self.queue()[1:]], [("pr-merged", "coordinator")])
        with open(os.path.join(self.state, "poll-state.json")) as f:
            self.assertEqual(json.load(f)["prs"], {})
        with open(os.path.join(self.gh_dir, "gh.log")) as f:
            calls = [json.loads(line) for line in f]
        self.assertTrue(all(c[:2] in (["pr", "list"], ["issue", "list"], ["pr", "view"]) for c in calls), calls)
        self.assertIn(["pr", "view", "171", "-R", "acme/widgets", "--json",
                       "number,state,headRefOid,labels,statusCheckRollup,reviews"], calls)

    def test_triage_scan_off_unless_enabled(self):  # #747: T2 adds the [triage] profile
        self.serve("prs-none.json")
        self.assertFalse(os.path.exists(os.path.join(self.state, "triage")))

    def test_ci_finishes_without_a_second_review(self):
        self.serve("prs-none.json")
        self.serve("prs-pending.json")
        self.serve("prs-ci-failed.json")
        self.serve("prs-ci-passed.json")
        self.assertEqual([(r["event"], r["consumer"]) for r in self.queue()],
                         [("new-head", "reviewer"), ("ci-failed", "builder"), ("ci-passed", "synthesizer")])

    def express_pr(self, labels=("crew:in-review", "crew:express"), item="express", selfgate=False):
        prs = fixture("prs-ci-passed.json")
        prs[0]["labels"] = [{"name": x} for x in labels]
        if selfgate:
            prs[0]["reviews"].append({"author": {"login": "acme-bot"}, "body": "<!-- crew:v1 role=builder "
                                      "pass=selfgate pr=171 sha=%s verdict=pass -->" % HEAD})
        for name, value in (("prs", prs), ("pr-171", {"closingIssuesReferences": [{"number": 72}]}),
                            ("issue-72", {"labels": [], "comments": [{"author": {"login": "acme-bot"}, "body": (
                                "[Ash/flavor] #72: %s\nReason: small\n<!-- crew:v1 role=coordinator pass=flavor "
                                "issue=72 flavor=%s default=standard -->" % (item, item))}]} if item else {}),
                            ("files", [{"filename": "docs/two.md"}])):
            with open(os.path.join(self.gh_dir, name + ".json"), "w") as f:
                json.dump(value, f)
        r = self.crew("poll", "--once", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_once_resolves_express_and_falls_back(self):  # #672
        self.serve("prs-none.json")
        self.express_pr()
        self.assertEqual(self.queue(), [])  # no new-head, and CI green without a selfgate pass wakes nobody
        self.assertIn("selfgate-passed -> synthesizer #171 " + HEAD, self.express_pr(selfgate=True))
        self.assertIn("new-head -> reviewer #171 " + HEAD, self.express_pr(labels=("crew:in-review",), selfgate=True))
        self.assertEqual([r["event"] for r in self.queue()], ["selfgate-passed", "new-head"])

    def test_once_express_merge_up_reads_the_selfgate(self):  # #672 r2: no reviewer verdict exists
        self.serve("prs-none.json")
        self.express_pr(selfgate=True)
        with open(os.path.join(self.gh_dir, "prs.json")) as f:
            prs = json.load(f)
        prs[0]["headRefOid"] = "3" * 40
        for name, value in (("prs", prs), ("commit", {"parents": [{"sha": HEAD}, {"sha": "4" * 40}]}),
                            ("compare", {"status": "identical"})):
            with open(os.path.join(self.gh_dir, name + ".json"), "w") as f:
                json.dump(value, f)
        r = self.crew("poll", "--once", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("merge-up -> synthesizer #171 " + "3" * 40, r.stdout)
        self.assertEqual([(e["event"], e.get("previous_head")) for e in self.queue()[1:]],
                         [("merge-up", HEAD), ("ci-passed", None)])  # CI already green at the merged head

    def test_once_crew_lane_item_or_unreadable_resolution_gets_review(self):  # #672
        self.serve("prs-none.json")
        self.assertIn("new-head -> reviewer", self.express_pr(item="standard"))
        self.serve("prs-none.json", **{"171": "pr-171-merged.json"})
        out = self.express_pr(item=None)  # the issue read has no comments
        self.assertIn("crew: poll: #171 crew lane: express resolution unreadable", out)
        self.assertIn("new-head -> reviewer", out)

    def test_queued_ci_failed_for_superseded_head_dropped(self):  # #578
        self.serve("prs-pending.json")
        old, other = (dict(event="ci-failed", consumer="builder", refs=refs) for refs in
                      (["#171", "a" * 40], ["#999", "b" * 40]))
        current = dict(event="ci-failed", consumer="builder", refs=["#171", HEAD])
        with open(os.path.join(self.state, "wake", "queue.jsonl"), "w") as f:
            f.writelines(json.dumps(w) + "\n" for w in (old, other, current))
        self.serve("prs-pending.json")
        self.assertEqual(self.queue(), [other, current])

    def test_poll_reads_job_steps_and_routes_startup_failure_to_coordinator(self):
        self.serve("prs-pending.json")
        prs = fixture("prs-ci-failed.json")
        for check in prs[0]["statusCheckRollup"]:
            if check.get("conclusion") == "FAILURE":
                check["detailsUrl"] = "https://github.com/acme/widgets/actions/runs/1/job/2"
        for name, data in [("prs", prs), ("job", dict(status="completed", conclusion="failure", steps=[]))]:
            with open(os.path.join(self.gh_dir, name + ".json"), "w") as f:
                json.dump(data, f)
        for _ in range(2):
            r = self.crew("poll", "--once", "--project", self.project)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([(e["event"], e["consumer"]) for e in self.queue()], [("ci-infra", "coordinator")])

    def merge_push(self, parents, status="identical", verdict="pass", intermediate=False):
        prs = fixture("prs-approved.json")
        prs[0]["reviews"][-1]["body"] = (
            "<!-- crew:v1 role=reviewer-validator pass=verdict pr=171 sha=%s round=1 verdict=changes -->\n"
            "<!-- crew:v1 role=reviewer-validator pass=verdict pr=171 sha=%s round=2 verdict=%s -->"
            % ("0" * 40, HEAD, verdict))
        for name, value in (("prs", prs), ("issues", [])):
            with open(os.path.join(self.gh_dir, name + ".json"), "w") as f:
                json.dump(value, f)
        self.assertEqual(self.crew("poll", "--once", "--project", self.project).returncode, 0)
        if intermediate:  # a later changes verdict must override the cached approval
            prs[0]["reviews"].append({"body": "<!-- crew:v1 role=reviewer-validator pass=verdict pr=171 "
                                     "sha=%s round=2 verdict=changes -->" % HEAD})
        prs[0]["headRefOid"] = "3" * 40
        for name, value in (("prs", prs), ("commit", {"parents": [{"sha": p} for p in parents]}),
                            ("compare", {"status": status})):
            with open(os.path.join(self.gh_dir, name + ".json"), "w") as f:
                json.dump(value, f)
        r = self.crew("poll", "--once", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_approved_merge_emits_recheck_once_with_previous_head_and_round(self):
        r = self.merge_push([HEAD, "4" * 40], status="ahead")
        self.assertIn("merge-up -> synthesizer", r.stdout)
        event = self.queue()[0]
        self.assertEqual((event["event"], event["consumer"], event["refs"], event["previous_head"], event["round"]),
                         ("merge-up", "synthesizer", ["#171", "3" * 40], HEAD, 2))
        self.assertEqual(self.crew("poll", "--once", "--project", self.project).returncode, 0)
        self.assertEqual(len([e for e in self.queue() if e["event"] == "merge-up"]), 1)
        with open(os.path.join(self.gh_dir, "gh.log")) as f:
            api = [json.loads(line) for line in f if json.loads(line)[0] == "api"]
        self.assertEqual(api, [["api", "repos/acme/widgets/commits/" + "3" * 40],
                               ["api", "repos/acme/widgets/compare/" + "4" * 40 + "...main"]])

    def test_non_merge_code_push_uses_normal_review(self):
        self.merge_push([HEAD])
        self.assertEqual(self.queue()[0]["event"], "new-head")

    def test_merge_of_current_default_tip_uses_recheck(self):
        self.merge_push([HEAD, "4" * 40])
        self.assertEqual(self.queue()[0]["event"], "merge-up")

    def test_merge_after_another_builder_commit_uses_normal_review(self):
        self.merge_push(["5" * 40, "4" * 40])
        self.assertEqual(self.queue()[0]["event"], "new-head")

    def test_merge_of_other_branch_uses_normal_review(self):
        self.merge_push([HEAD, "4" * 40], status="diverged")
        self.assertEqual(self.queue()[0]["event"], "new-head")

    def test_changes_verdict_does_not_inherit_approval(self):
        self.merge_push([HEAD, "4" * 40], verdict="changes")
        self.assertEqual(self.queue()[0]["event"], "new-head")

    def test_live_changes_verdict_overrides_cached_pass(self):
        self.merge_push([HEAD, "4" * 40], intermediate=True)
        self.assertEqual(self.queue()[0]["event"], "new-head")


class TriageScan(unittest.TestCase):
    """The zero-model triage scan (triage.md T1, #747) on fixture issues."""

    @classmethod
    def setUpClass(cls):
        cls.crew = load_crew()

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.values = {"repo.owner": "acme", "repo.name": "widgets", "identities.owners": ["owner"]}

    def scan(self, rules=None):
        rules = rules or self.crew.TRIAGE_RULES
        entries = self.crew.triage_scan("acme/widgets", fixture("triage-open.json"), fixture("triage-closed.json"),
                                        rules, {"owner"}, self.crew.triage_card_fields())
        return {e["ref"].split("#")[1]: e for e in entries}

    def poll(self, read=None, project=None):
        calls = []

        def fake(*args, retry=()):
            calls.append(args)
            if read:
                return read(*args)
            return fixture("triage-open.json" if args[5] == "open" else "triage-closed.json")
        self.crew.triage_poll(self.values, self.tmp, project or os.path.join(self.tmp, "crew.toml"), read=fake)
        with open(os.path.join(self.tmp, "triage", "queue.json")) as f:
            queue = json.load(f)
        path = os.path.join(self.tmp, "wake", "queue.jsonl")
        wakes = []
        if os.path.exists(path):
            with open(path) as f:
                wakes = [json.loads(line) for line in f]
        return queue, wakes, calls

    def test_skip_rules_queue_only_unplaced_issues_and_owner_replies(self):
        entries = self.scan()
        self.assertEqual(sorted(entries, key=int), ["10", "11", "12", "16", "20", "21"])
        self.assertEqual({n: entries[n].get("reason") for n in ("10", "16")}, {"10": "new", "16": "owner-reply"})
        # 13 triage:log, 14 milestone, 15 flavor record, 17 non-owner reply, 18 no reply after the record, 19 a PR

    def test_unreadable_item_is_recorded(self):
        self.assertEqual(self.scan()["20"], {"ref": "acme/widgets#20", "unreadable": "KeyError: 'comments'"})

    def test_duplicate_hints_from_exact_keys_across_open_and_closed(self):
        entries = self.scan()
        self.assertEqual(entries["10"]["duplicates"], [{"ref": "acme/widgets#3", "state": "closed",
                                                        "keys": ["class:merge-gate-race", "path:scripts/crew.d/train.py"]}])
        self.assertEqual(entries["21"]["duplicates"], [{"ref": "acme/widgets#4", "state": "closed",
                                                        "keys": ["title:watcher exits early"]}])
        self.assertEqual(entries["11"]["duplicates"], [])

    def test_card_fields_parsed_from_the_intake_template(self):
        fields = self.crew.triage_card_fields()
        self.assertEqual(fields[:3], ["Source", "Trigger", "Failure class"])
        self.assertIn("Escaped from", fields)
        card = self.scan()["10"]["card"]
        self.assertEqual((card["Source"], card["Failure class"], card["Decision"]),
                         ("acme/widgets#171 (https://github.com/acme/widgets/pull/171)", "merge-gate-race", "pending"))
        self.assertEqual(self.scan()["11"]["card"], {})

    def test_intake_issue_template_matches_the_card_and_parses(self):
        root = os.path.dirname(HERE)
        with open(os.path.join(root, ".github", "ISSUE_TEMPLATE", "intake-card.md"), encoding="utf-8") as f:
            body = f.read().split("\n---\n", 1)[1]
        fields = self.crew.triage_card_fields()
        self.assertEqual(re.findall(r"^(?:\*\*)?([A-Z][\w ]*?):", body, re.M), fields)
        card, _ = self.crew.triage_keys({"title": "intake: flake on acme/widgets#1", "body": body}, fields)
        self.assertEqual(sorted(card), sorted(fields))
        with open(os.path.join(root, ".github", "ISSUE_TEMPLATE", "config.yml"), encoding="utf-8") as f:
            self.assertIn("blank_issues_enabled: true", f.read().splitlines())

    def test_p0_signals_from_defaults_and_rules_file(self):
        entries = self.scan()
        self.assertEqual({n: e.get("p0") for n, e in entries.items() if e.get("p0")},
                         {"11": ["keyword:pipeline blocked"], "12": ["label:security"]})
        rules_file = os.path.join(self.tmp, "triage-rules.toml")
        with open(rules_file, "w") as f:
            f.write('[p0]\nkeywords = ["exits early"]\n')
        rules, note = self.crew.triage_rules(rules_file)
        self.assertEqual(note, rules_file)
        self.assertEqual({n for n, e in self.scan(rules).items() if e.get("p0")}, {"21"})
        with open(rules_file, "w") as f:
            f.write("not toml [")
        rules, note = self.crew.triage_rules(rules_file)
        self.assertIs(rules, self.crew.TRIAGE_RULES)
        self.assertTrue(note.startswith("default (unreadable " + rules_file), note)
        self.assertEqual(self.crew.triage_rules(None), (self.crew.TRIAGE_RULES, "default"))

    def test_poll_writes_queue_and_wakes_each_new_p0_once(self):
        queue, wakes, calls = self.poll()
        self.assertEqual((queue["rules"], queue["repos"]), ("default", {"acme/widgets": "ok"}))
        self.assertEqual(len(queue["items"]), 6)
        self.assertEqual([(w["event"], w["consumer"], w["refs"]) for w in wakes],
                         [("triage-p0", "coordinator", ["acme/widgets#11"]),
                          ("triage-p0", "coordinator", ["acme/widgets#12"])])
        self.assertTrue(all(c[:2] == ("issue", "list") for c in calls), calls)  # read-only gh, no model call
        _, wakes, _ = self.poll()
        self.assertEqual(len(wakes), 2)

    def test_triage_repos_and_unreadable_repo_recorded(self):
        def read(*args):
            if args[3] == "acme/down":
                raise RuntimeError("crew: gh issue list failed: HTTP 404")
            return []
        self.values.update({"triage.repos": ["acme/down", "acme/tracker"], "triage.rules": "missing.toml"})
        queue, wakes, _ = self.poll(read)
        self.assertTrue(queue["rules"].startswith("default (unreadable %s" % os.path.join(self.tmp, "missing.toml")))
        self.assertEqual(queue["repos"], {"acme/down": "unreadable: crew: gh issue list failed: HTTP 404",
                                          "acme/tracker": "ok"})
        self.assertEqual((queue["items"], wakes), ([], []))


if __name__ == "__main__":
    unittest.main()
