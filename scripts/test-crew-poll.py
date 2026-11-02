"""Tests for crew poll, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only).

Covers: the decision function on recorded `gh` JSON in `fixtures/poll/` (new-head ->
reviewer, ci-passed -> synthesizer, ci-failed -> builder, changes -> builder, approved -> synthesizer, merged ->
coordinator, no change -> nothing; `new-head` carries round `k`, reset by a cutover; an
evidence-only fix at the verdict head emits `fix-at-head` once; an intake `pass=ack` marker wakes nobody
and counts no round, #303) and `poll --once` against a fake `gh` (baseline, one wake record per change,
read-only calls). Run in CI.
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import textwrap
import unittest
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
    name = ("commit" if "/commits/" in args[1] else "compare") if args[0] == "api" else (
        {("pr", "list"): "prs", ("issue", "list"): "issues"}.get(tuple(args[:2])) or "pr-" + args[2])
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
                                                "fixed": False}})

    def test_every_event_has_exactly_one_consumer(self):
        self.assertEqual(sorted(self.crew.CONSUMER), sorted(["new-head", "ci-passed", "ci-failed", "review-changes-requested",
                                                             "review-approved", "pr-merged", "pr-closed",
                                                             "issue-assigned", "fix-at-head", "merge-up"]))
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

    def test_ci_finishes_without_a_second_review(self):
        self.serve("prs-none.json")
        self.serve("prs-pending.json")
        self.serve("prs-ci-failed.json")
        self.serve("prs-ci-passed.json")
        self.assertEqual([(r["event"], r["consumer"]) for r in self.queue()],
                         [("new-head", "reviewer"), ("ci-failed", "builder"), ("ci-passed", "synthesizer")])

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
        self.assertIn("merge-up -> reviewer", r.stdout)
        event = self.queue()[0]
        self.assertEqual((event["event"], event["consumer"], event["refs"], event["previous_head"], event["round"]),
                         ("merge-up", "reviewer", ["#171", "3" * 40], HEAD, 2))
        self.assertEqual(self.crew("poll", "--once", "--project", self.project).returncode, 0)
        self.assertEqual(len([e for e in self.queue() if e["consumer"] == "reviewer"]), 1)
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


if __name__ == "__main__":
    unittest.main()
