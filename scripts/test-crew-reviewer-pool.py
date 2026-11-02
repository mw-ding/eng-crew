"""Reviewer lead fixtures: handoff replay, fresh passes, admission, cleanup and identity recovery.
Fake tmux/GitHub; --transcript prints the handoff-to-completion lifecycle. Run in CI.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import sys
import unittest
from unittest import mock
from crew_testlib import CREW, HERE, FAKE_TMUX_PANES, FAKE_PS

loader = importlib.machinery.SourceFileLoader("route_tests", os.path.join(HERE, "test-crew-route.py"))
route_tests = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(route_tests)


class ReviewerPool(route_tests.Route):
    def setUp(self):
        super().setUp()
        bindir = os.path.join(self.tmp, "bin")
        os.rename(os.path.join(bindir, "tmux"), os.path.join(bindir, "tmux-base"))
        for name, text in (("tmux", FAKE_TMUX_PANES), ("ps", FAKE_PS)):
            with open(os.path.join(bindir, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(bindir, name), 0o755)
        self.env.update(FAKE_PANES=os.path.join(self.tmp, "panes.json"), FAKE_PS=os.path.join(self.tmp, "ps.json"))
        self.put("render/runtime/reviewer-lead.md", "Manage the reviewer pool; never review.\n")
        loader = importlib.machinery.SourceFileLoader("reviewer_cli", CREW)
        self.mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        loader.exec_module(self.mod)
        self.lead = self.mod.commands()["lead"]
        self.args = argparse.Namespace(project=self.project, org_profile=None, timeout=1, suites=0)

    def pool(self, load=0, suites=0):
        self.args.suites = suites
        with mock.patch.dict(os.environ, dict(self.env, CREW_POOL="reviewer")), \
                mock.patch("os.getloadavg", return_value=(load, 0, 0)), mock.patch("os.cpu_count", return_value=4):
            self.assertEqual(self.mod.commands()["reviewer-pool"].run(self.args), 0)

    def messages(self):
        return self.lead.pending(self.state, "vera-lead")

    def handoff(self, kind, refs):
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.lead.handoff(self.args, "reviewer", kind, refs), 0)

    def test_handoff_dispatch_complete_reclaim(self):
        self.queue(self.event(), self.event())
        self.route()
        self.assertEqual(self.names(), ["ash", "vera-lead"])
        self.assertEqual(len(self.messages()), 1)
        self.pool()
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual(self.messages(), [])
        self.put("verdicts/pr12-%s-r1-review.md" % self.sha[:7], "review output")
        self.put("status/vera-12-r1-review.status", "done: #12 %s review pass\n" % self.sha)
        self.queue(self.status("vera-12-r1-review", "review pass"))
        self.route()
        self.pool()
        self.assertNotIn("vera-12-r1-review", self.names())
        self.assertIn("vera-12-r1-validate", self.names())
        self.queue(self.status("vera-12-r1-validate", "validate pass"))
        self.route()
        self.pool()
        self.assertEqual(self.names(), ["ash", "vera-lead"])
        self.assertEqual(self.messages(), [])
        if "--transcript" in sys.argv:
            print("$ crew route --project <fixture>/crew.toml --timeout 1; exit 0")
            print("$ crew reviewer-pool --suites 0 --project <fixture>/crew.toml; exit 0")
            print("handoff received: one lead, one durable request, zero workers")
            print("dispatch: one fresh review; duplicate event suppressed")
            print("completion: review reclaimed, retained output, fresh validation")
            print("validation completed: both workers reclaimed; lead stays; pending=0")

    def test_admission_defers_load_suites_unknown_then_resumes(self):
        result = self.spawn("reviewer", "--pr", "12", "--round", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.handoff("review", ["#12", self.sha, "1"])
        for load, suites in ((4, 0), (0, 1), (0, None)):
            self.pool(load, suites)
            self.assertNotIn("vera-12-r1-review", self.names())
            self.assertEqual(len(self.messages()), 1)
        self.pool()
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual(self.messages(), [])

    def test_empty_reviewer_pool_retains_one_slot_under_known_pressure(self):
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool(suites=None)
        self.assertNotIn("vera-12-r1-review", self.names())
        self.pool(load=4, suites=1)
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual(self.messages(), [])
        if "--admission-transcript" in sys.argv:
            print("empty reviewer pool: unknown suites -> defer; load=4, CPUs=4, suites=1 -> one review")

    def test_profile_suite_cap_allows_reviewer_expansion(self):
        with open(self.project, "a") as out:
            out.write("\n[runtime.options]\nmax_suites = 2\n")
        result = self.spawn("reviewer", "--pr", "12", "--round", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool(suites=1)
        self.assertIn("vera-12-r1-review", self.names())
        self.assertEqual(self.messages(), [])

    def test_builder_completion_wakes_deferred_review_after_last_suite(self):
        result = self.spawn("reviewer", "--pr", "12", "--round", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool(suites=1)
        self.assertEqual(len(self.messages()), 1)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        before = len(self.calls())
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha))
        self.route()
        self.assertTrue(any(c[0] == "send-keys" and c[c.index("-t") + 1] == "=crew-acme-widgets:3"
                            and c[-1].startswith("inbox:") for c in self.calls()[before:]))
        self.pool()
        self.assertEqual(sorted(n for n in self.names() if n.endswith("review")),
                         ["vera-12-r1-review", "vera-12-r3-review"])
        self.assertEqual(self.messages(), [])
        if "--admission-transcript" in sys.argv:
            print("suite running: expansion deferred; pending=1; existing review=1")
            print("builder done: reviewer lead nudged without coordinator handoff")
            print("suite finished: pending=0; fresh review=1; duplicate completion suppressed")

    def delta_merge_up(self, note):
        previous = self.approved_push()
        self.live["reviews"][-1]["body"] = (
            "[Ben/fix] round 2 @ " + self.sha[:7] + "\n\n" + note + "\n" +
            self.live["reviews"][-1]["body"] + "\n— 🛠️ Ben (Builder) · codex · gpt-6.1-sol")
        self.save()
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha),
                   dict(self.event("merge-up"), previous_head=previous, round=2))
        self.route()
        self.pool()
        self.assertEqual([n for n in self.names() if n.endswith("review")], ["vera-12-r2-review"])
        self.assertEqual(self.record("vera-12-r2-review")["head"], self.sha)
        self.assertEqual(self.messages(), [])
        if "--merge-up-transcript" in sys.argv:
            print(note + " -> one review at updated head, round 2; no coordinator handoff")
        self.queue(self.status("vera-12-r2-review", "review pass"))
        self.route()
        self.pool()
        self.assertIn("vera-12-r2-validate", self.names())
        if "--merge-up-transcript" in sys.argv:
            print("delta review passed -> fresh independent validation at updated head")

    def test_resolved_conflict_merge_up_starts_delta_review(self):
        self.delta_merge_up("Resolved conflict in docs.")

    def test_semantic_conflict_fix_starts_delta_review(self):
        self.delta_merge_up("Fixed train's semantic conflict.")

    def test_differing_patch_merge_up_starts_delta_review(self):
        self.delta_merge_up("Differing patch after merge-up.")

    def test_identical_merge_up_keeps_synthesizer_portability(self):
        previous = self.approved_push()
        self.queue(dict(reason="status", window="ben-7", line="done: #7 #12 " + self.sha),
                   dict(self.event("merge-up"), previous_head=previous, round=2, consumer="synthesizer"))
        self.route()
        self.pool()
        self.assertEqual(self.names(), ["ash", "vera-lead"])
        self.assertEqual(self.messages(), [])
        self.assertEqual([w["event"] for w in self.pending()], ["merge-up"])
        if "--merge-up-transcript" in sys.argv:
            print("identical merge-up -> synthesizer portability; zero review workers")

    def test_delta_note_must_be_signed_and_pin_current_head(self):
        route = self.mod.commands()["route"]
        note = ("[Ben/fix] round 1 @ " + self.sha[:7] + "\nResolved conflict.\n"
                "<!-- crew:v1 role=builder pass=fix pr=12 sha=%s round=1 verdict=n/a -->\n"
                "— 🛠️ Ben (Builder) · codex · gpt-6.1-sol")
        self.live["reviews"] = [dict(body=note % self.sha)]
        self.assertTrue(route.merge_up_delta(self.live, self.sha))
        for body in (note % ("f" * 40), (note % self.sha).split("—")[0],
                     (note % self.sha).replace("Resolved conflict.", "Identical merge-up; no conflicts."),
                     (note % self.sha).replace("Resolved conflict.", "No differing patch.")):
            self.live["reviews"] = [dict(body=body)]
            self.assertFalse(route.merge_up_delta(self.live, self.sha))

    def test_full_cap_then_completed_slot_admits_validation(self):
        self.env["CREW_POOL"] = "reviewer"
        with open(self.project) as f:
            text = f.read()
        with open(self.project, "w") as f:
            f.write(text.replace('name = "tmux"\n', 'name = "tmux"\noptions = { reviewers = 1 }\n'))
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        self.handoff("review", ["#12", self.sha, "2"])
        self.pool()
        self.assertNotIn("vera-12-r2-review", self.names())
        self.assertEqual(len(self.messages()), 1)
        self.put("status/vera-12-r1-review.status", "done: #12 %s review pass\n" % self.sha)
        with mock.patch.dict(os.environ, self.env):
            self.lead.event(self.args, "reviewer", self.status("vera-12-r1-review", "review pass"))
        self.pool()
        self.assertNotIn("vera-12-r1-review", self.names())
        self.assertIn("vera-12-r1-validate", self.names())

    def test_replay_review_after_cleanup_starts_missing_validation(self):
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        self.assertEqual(self.crew("kill", "vera-12-r1-review", "--project", self.project, CREW_POOL="reviewer").returncode, 0)
        wake = dict(self.status("vera-12-r1-review", "review pass"), round=1)
        with mock.patch.dict(os.environ, self.env):
            self.lead.event(self.args, "reviewer", wake)
        self.pool()
        self.assertIn("vera-12-r1-validate", self.names())
        self.pool()
        self.assertEqual(len([n for n in self.names() if "validate" in n]), 1)

    def test_recheck_escalation_starts_review_then_validation(self):
        self.handoff("recheck", ["#12", self.sha, "2"])
        self.pool()
        self.queue(self.status("vera-12-r2-recheck", "recheck escalate"))
        self.route()
        self.pool(load=4)
        self.assertIn("vera-12-r2-review", self.names())
        self.assertEqual(self.messages(), [])
        self.pool()
        self.assertNotIn("vera-12-r2-recheck", self.names())
        self.assertIn("vera-12-r2-review", self.names())
        self.queue(self.status("vera-12-r2-review", "review pass"))
        self.route()
        self.pool()
        self.assertIn("vera-12-r2-validate", self.names())

    def test_recheck_completion_never_starts_validation(self):
        self.handoff("recheck", ["#12", self.sha, "1"])
        self.pool()
        self.queue(self.status("vera-12-r1-recheck", "recheck pass"))
        self.route()
        self.pool()
        self.assertEqual(self.names(), ["ash", "vera-lead"])

    def test_held_request_stays_stale_head_retires(self):
        self.live["labels"] = [{"name": "crew:escalated"}]
        self.save()
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        self.assertEqual(len(self.messages()), 1)
        self.live["headRefOid"] = "f" * 40
        self.save()
        self.pool()
        self.assertEqual(self.messages(), [])
        self.assertEqual(self.names(), ["ash", "vera-lead"])

    def test_same_head_rereview_ignores_old_section(self):
        self.put("verdicts/pr12-%s-r1-review.md" % self.sha[:7],
                 "<!-- crew:v1 role=reviewer-validator pass=review pr=12 sha=%s round=1 verdict=pass -->" % self.sha)
        self.live["reviews"] = [dict(body="<!-- crew:v1 role=coordinator pass=steer cmd=rereview cmd-id=42 sha=%s -->" % self.sha)]
        self.save()
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        self.assertIn("vera-12-r1-review", self.names())

    def test_lead_restart_preserves_queue_and_live_worker(self):
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        self.handoff("validate", ["#12", self.sha, "1"])
        with mock.patch.dict(os.environ, self.env):
            rec = dict(self.lead.records(self.state))["vera-lead"]
            windows = dict((n, i) for i, n in self.mod.tmux.list_windows("crew-acme-widgets"))
            self.assertEqual(self.mod.probe("crew-acme-widgets", "vera-lead", rec, windows), "alive")
        if "--transcript" in sys.argv:
            print("before recovery: readiness=alive; live review=1; pending validation=1")
        worker = self.record("vera-12-r1-review")
        self.pool(suites=1)
        with mock.patch.dict(os.environ, self.env):
            self.mod.tmux.kill_window("crew-acme-widgets", 3)
            self.assertEqual(self.lead.ensure(self.args, "reviewer"), 0)
            rec = dict(self.lead.records(self.state))["vera-lead"]
            windows = dict((n, i) for i, n in self.mod.tmux.list_windows("crew-acme-widgets"))
            self.assertEqual(self.mod.probe("crew-acme-widgets", "vera-lead", rec, windows), "alive")
        if "--transcript" in sys.argv:
            print("after recovery: readiness=alive; restarts=1; live review=1; pending validation=1")
        self.assertEqual(self.record("vera-12-r1-review"), worker)
        self.assertEqual(len(self.messages()), 1)
        self.put("verdicts/pr12-%s-r1-review.md" % self.sha[:7],
                 "<!-- crew:v1 role=reviewer-validator pass=review pr=12 sha=%s round=1 verdict=pass -->" % self.sha)
        self.pool()
        self.assertIn("vera-12-r1-validate", self.names())
        with mock.patch.dict(os.environ, self.env):
            self.mod.tmux.kill_window("crew-acme-widgets", 3)
            self.assertEqual(self.lead.ensure(self.args, "reviewer"), 1)
        if "--transcript" in sys.argv:
            print("$ crew lead ensure reviewer --project <fixture>/crew.toml; first recovery exit 0, second exit 1")
            print("lead restart: identity replaced; live review untouched; pending validation preserved and dispatched")
            print("second lead failure: blocked; no replacement; workers retained")

    def test_worker_probe_restarts_once_and_never_ambiguous(self):
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        wake = dict(reason="stale", window="vera-12-r1-review")
        args = argparse.Namespace(**vars(self.args), reviewer_lead=True) if not hasattr(self.args, "reviewer_lead") else self.args
        pool = self.mod.commands()["reviewer-pool"]
        with mock.patch.dict(os.environ, dict(self.env, CREW_POOL="reviewer")), \
                mock.patch.object(pool, "probe", return_value="ambiguous"):
            with self.assertRaisesRegex(RuntimeError, "escalation"):
                pool.dispatch(args, self.mod.profile(args)[0], self.state, wake)
        with mock.patch.dict(os.environ, dict(self.env, CREW_POOL="reviewer")):
            self.mod.tmux.kill_window("crew-acme-widgets", 20)
            self.assertTrue(pool.dispatch(args, self.mod.profile(args)[0], self.state, wake))
        self.assertEqual(self.record("vera-12-r1-review")["restarts"], 1)

    def test_infra_ci_allows_validation_real_failure_keeps_it_pending(self):
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        check = dict(status="COMPLETED", conclusion="FAILURE")
        self.live["statusCheckRollup"] = [check]
        self.save()
        self.queue(self.status("vera-12-r1-review", "review pass"))
        self.route()
        self.pool()
        self.assertNotIn("vera-12-r1-validate", self.names())
        self.assertEqual(len(self.messages()), 1)
        check["_ci_infra"] = True
        self.save()
        self.pool()
        self.assertIn("vera-12-r1-validate", self.names())
        self.assertEqual(self.messages(), [])

    def test_ambiguous_lead_never_starts_replacement(self):
        self.handoff("review", ["#12", self.sha, "1"])
        with open(self.env["FAKE_PANES"], "w") as f:
            json.dump({"crew-acme-widgets:3": {"command": "sleep"}}, f)
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.lead.ensure(self.args, "reviewer"), 1)
        self.assertEqual(len(self.messages()), 1)
        self.assertEqual(self.names(), ["ash", "vera-lead"])

    def test_closed_pr_reclaims_active_worker_through_lead(self):
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        self.live["state"] = "CLOSED"
        self.save()
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(self.lead.event(self.args, "reviewer", self.event("pr-closed")), 0)
        self.pool()
        self.assertEqual(self.names(), ["ash", "vera-lead"])
        self.assertEqual(self.messages(), [])

    def test_rereview_waits_for_old_pass_then_starts_fresh(self):
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        self.live["reviews"] = [dict(body="<!-- crew:v1 role=coordinator pass=steer cmd=rereview cmd-id=42 sha=%s -->" % self.sha)]
        self.save()
        self.handoff("review", ["#12", self.sha, "1", "42"])
        self.pool()
        self.assertEqual(len(self.messages()), 1)
        self.assertEqual(len([n for n in self.names() if n.endswith("review")]), 1)
        self.queue(self.status("vera-12-r1-review", "review pass"))
        self.route()
        self.pool()
        self.assertEqual(self.record("vera-12-r1-review")["rereview_id"], "42")
        self.assertNotIn("vera-12-r1-validate", self.names())

    def test_reclaim_does_not_bypass_load_admission_by_dequeuing(self):
        result = self.spawn("reviewer", "--pr", "12", "--round", "3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.handoff("review", ["#12", self.sha, "1"])
        self.pool()
        request = dict(role="reviewer", issue=None, pr=12, head=self.sha, **{
            "pass": "review", "round": 2, "tier": "default"})
        self.put("spawn-queue.jsonl", json.dumps(request) + "\n")
        self.queue(self.status("vera-12-r1-review", "review pass"))
        self.route()
        self.pool(load=4)
        self.assertNotIn("vera-12-r1-validate", self.names())
        self.assertIn("vera-12-r3-review", self.names())
        with open(os.path.join(self.state, "spawn-queue.jsonl")) as f:
            self.assertEqual(json.loads(f.read()), request)
        self.assertEqual(len(self.messages()), 1)

    def test_ci_jobs_without_steps_are_infra_never_green(self):
        poll = self.mod.commands()["poll"]
        self.live["statusCheckRollup"] = [dict(status="COMPLETED", conclusion="FAILURE", detailsUrl="https://github.com/acme/widgets/actions/runs/123/job/456")]
        with mock.patch.object(poll, "gh_json", return_value={"jobs": [{"steps": []}]}):
            poll.observe_ci(self.live, "acme/widgets")
        self.assertEqual(poll.pr_snapshot(self.live)["ci"], "infra")
        self.live["labels"] = [{"name": "crew:in-review"}]
        events, _ = poll.decide({"prs": {"12": {"head": self.sha, "ci": "pending"}}}, [self.live], [])
        self.assertEqual([(e["event"], e["consumer"]) for e in events], [("ci-infra", "coordinator")])
        self.live["statusCheckRollup"][0].pop("_ci_infra")
        with mock.patch.object(poll, "gh_json", return_value={"jobs": [{"steps": [{"name": "test"}]}]}):
            poll.observe_ci(self.live, "acme/widgets")
        self.assertEqual(poll.pr_snapshot(self.live)["ci"], "failed")


if __name__ == "__main__":
    names = [n for n in ReviewerPool.__dict__ if n.startswith("test_")]
    if "--transcript" in sys.argv:
        names = ["test_handoff_dispatch_complete_reclaim", "test_lead_restart_preserves_queue_and_live_worker"]
    if "--admission-transcript" in sys.argv:
        names = ["test_empty_reviewer_pool_retains_one_slot_under_known_pressure",
                 "test_profile_suite_cap_allows_reviewer_expansion",
                 "test_builder_completion_wakes_deferred_review_after_last_suite"]
    if "--merge-up-transcript" in sys.argv:
        names = ["test_resolved_conflict_merge_up_starts_delta_review",
                 "test_semantic_conflict_fix_starts_delta_review",
                 "test_differing_patch_merge_up_starts_delta_review",
                 "test_identical_merge_up_keeps_synthesizer_portability"]
    result = unittest.TextTestRunner().run(unittest.TestSuite(ReviewerPool(n) for n in names))
    sys.exit(not result.wasSuccessful())
