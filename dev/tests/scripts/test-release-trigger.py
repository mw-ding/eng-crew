#!/usr/bin/env python3
"""Offline release-trigger fixtures: cut detection, no-op, CI gate and owner approval.

Run in CI; uses fake gh responses and local tag fixtures, never real tags,
releases or GitHub writes.
"""
import contextlib
import copy
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("release_trigger", Path(__file__).with_name("release-trigger.py"))
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

CUT = "# Changelog\n\n## [Unreleased]\n\n## [1.2.3] - 2026-11-01\n\n### Fixed\n\n- A fix.\n"
HEAD, MERGE = "a" * 40, "b" * 40
PR = {"number": 7, "head": {"sha": HEAD}, "merge_commit_sha": MERGE,
      "merged_at": "2026-11-01T12:00:00Z", "base": {"ref": "main", "repo": {"full_name": "owner/repo"}}}
MARKER = "<!-- crew:v1 role=synthesizer pass=steer cmd=merge-ok pr=7 sha=%s round=n/a verdict=n/a -->" % HEAD
POST = {"user": {"login": "owner"}, "body": MARKER}


class ReleaseTriggerTest(unittest.TestCase):
    def test_detect_new_cut(self):
        self.assertEqual(rt.detect(CUT, ["v1.2.2"]), "1.2.3")

    def test_detect_refuses_non_cut(self):
        cases = [CUT.replace("\n## [1.2.3]", "\n- Pending.\n\n## [1.2.3]"),
                 CUT.replace("1.2.3", "next"), CUT.replace("1.2.3", "1.2.3-rc.1"),
                 "# Changelog\n\n## [Unreleased]\n", CUT.replace("Unreleased", "Pending")]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(rt.rc.Failed):
                rt.detect(text, [])
        with self.assertRaisesRegex(rt.rc.Failed, "already exists"):
            rt.detect(CUT, ["v1.2.3"])

    def test_push_skips_green_but_real_cut_pr_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            changelog = Path(tmp, "CHANGELOG.md")
            changelog.write_text(CUT)
            env = {"GITHUB_OUTPUT": str(Path(tmp, "output")), "GITHUB_STEP_SUMMARY": str(Path(tmp, "summary"))}
            previous = os.getcwd()
            try:
                os.chdir(tmp)
                with patch.dict(os.environ, env), patch.object(rt.subprocess, "check_output", return_value="v1.2.3\n"):
                    self.assertEqual(rt.main(["detect", "--skip-invalid"]), 0)
                    self.assertEqual(Path(env["GITHUB_OUTPUT"]).read_text(), "ready=false\n")
                    self.assertEqual(Path(env["GITHUB_STEP_SUMMARY"]).read_text().count("\n"), 1)
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(rt.main(["detect"]), 1)
            finally:
                os.chdir(previous)

    def test_approval_requires_owner_pr_and_full_head(self):
        self.assertTrue(rt.approved(PR, [POST], "owner"))
        bad = [dict(POST, user={"login": "bot"}), dict(POST, body=None)]
        bad += [dict(POST, body=MARKER.replace(old, new)) for old, new in
                [(HEAD, MERGE), (HEAD, HEAD[:7]), ("pr=7", "pr=8"),
                 ("pass=steer", "pass=verdict"), ("cmd=merge-ok", "cmd=hold")]]
        for post in bad:
            with self.subTest(post=post):
                self.assertFalse(rt.approved(PR, [post], "owner"))

    def test_merged_pr_is_exact_commit_and_main(self):
        self.assertEqual(rt.merged_pr([PR], MERGE, "owner/repo"), PR)
        cases = [[], [PR, PR], [dict(PR, merged_at=None)], [dict(PR, merge_commit_sha=HEAD)]]
        other_base = copy.deepcopy(PR)
        other_base["base"]["ref"] = "feature"
        cases.append([other_base])
        for prs in cases:
            with self.subTest(prs=prs), self.assertRaises(rt.rc.Failed):
                rt.merged_pr(prs, MERGE, "owner/repo")

    def test_authorize_reads_all_pages_and_both_post_types(self):
        env = {"RELEASE_OWNER": "owner", "GITHUB_ACTOR": "owner", "GITHUB_TRIGGERING_ACTOR": "owner",
               "GITHUB_REPOSITORY": "owner/repo", "GITHUB_SHA": MERGE}
        for reviews, comments in [([[POST]], [[]]), ([[]], [[], [POST]])]:
            with self.subTest(reviews=reviews, comments=comments), patch.dict(os.environ, env):
                with patch.object(rt, "gh", side_effect=[[[PR]], [[{"filename": "CHANGELOG.md"}]], reviews, comments,
                                  {"closingIssuesReferences": [{"number": 4, "url": "https://github.com/owner/repo/issues/4"}]}]) as gh:
                    self.assertEqual(rt.authorize(), ["4"])
                    self.assertIn("--paginate", gh.call_args_list[2].args)
                    self.assertIn("--slurp", gh.call_args_list[3].args)
        with patch.dict(os.environ, env), patch.object(rt, "gh", side_effect=[[[PR]], [[{"filename": "CHANGELOG.md"}]], [[]], [[]]]):
            with self.assertRaisesRegex(rt.rc.Failed, "missing owner merge-ok"):
                rt.authorize()
        with patch.dict(os.environ, env), patch.object(rt, "gh", side_effect=[[[PR]], [[{"filename": "README.md"}]]]):
            with self.assertRaisesRegex(rt.rc.Failed, "not a CHANGELOG cut"):
                rt.authorize()
        for key in ("RELEASE_OWNER", "GITHUB_ACTOR", "GITHUB_TRIGGERING_ACTOR"):
            with self.subTest(key=key), patch.dict(os.environ, dict(env, **{key: ""})), patch.object(rt, "gh") as gh:
                with self.assertRaisesRegex(rt.rc.Failed, "actor"):
                    rt.authorize()
                gh.assert_not_called()

    def test_ci_state_needs_latest_green_run_at_sha(self):
        def run(status="completed", conclusion="success", sha=MERGE, created="2026-11-01T12:00:00Z"):
            return {"id": 1, "head_sha": sha, "status": status, "conclusion": conclusion, "created_at": created}
        self.assertEqual(rt.ci_state([run()], MERGE), "success")
        self.assertEqual(rt.ci_state([], MERGE), "pending")
        self.assertEqual(rt.ci_state([run(sha=HEAD)], MERGE), "pending")
        self.assertEqual(rt.ci_state([run(status="in_progress", conclusion=None)], MERGE), "pending")
        self.assertEqual(rt.ci_state([run(conclusion="failure"), run(created="2026-11-01T13:00:00Z")], MERGE), "success")
        for conclusion in ("failure", "cancelled", "timed_out", "skipped"):
            with self.subTest(conclusion=conclusion), self.assertRaisesRegex(rt.rc.Failed, conclusion):
                rt.ci_state([run(), run(conclusion=conclusion, created="2026-11-01T13:00:00Z")], MERGE)

    def test_ci_gate_waits_then_proceeds_or_refuses_past_bound(self):
        env = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_SHA": MERGE}
        green = {"head_sha": MERGE, "status": "completed", "conclusion": "success"}
        pending = dict(green, status="queued", conclusion=None)
        now = [0]
        def sleep(seconds):
            now[0] += seconds
        with patch.dict(os.environ, env), patch.object(rt, "gh", side_effect=[
                {"workflow_runs": []}, {"workflow_runs": [pending]}, {"workflow_runs": [green]}]) as gh:
            rt.ci_gate(100, 30, sleep, lambda: now[0])
            self.assertIn("head_sha=%s&event=push&branch=main" % MERGE, gh.call_args.args[1])
            self.assertEqual(now[0], 60)
        for runs in ([], [pending], [dict(green, head_sha=HEAD)]):
            now[0] = 0
            with self.subTest(runs=runs), patch.dict(os.environ, env), \
                    patch.object(rt, "gh", return_value={"workflow_runs": runs}):
                with self.assertRaisesRegex(rt.rc.Failed, "within 90s"):
                    rt.ci_gate(90, 30, sleep, lambda: now[0])
        with patch.dict(os.environ, env), patch.object(rt, "gh", return_value={"workflow_runs": [dict(green, conclusion="cancelled")]}):
            with self.assertRaisesRegex(rt.rc.Failed, "cancelled"):
                rt.ci_gate(90, 30, sleep, lambda: now[0])

    def test_actor_refusal_names_the_fix(self):
        env = {"RELEASE_OWNER": "owner", "GITHUB_ACTOR": "owner", "GITHUB_TRIGGERING_ACTOR": "owner"}
        with patch.dict(os.environ, env):
            self.assertEqual(rt.main(["actor"]), 0)
        for key in ("GITHUB_ACTOR", "GITHUB_TRIGGERING_ACTOR"):
            with self.subTest(key=key), patch.dict(os.environ, dict(env, **{key: "bot"})):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    self.assertEqual(rt.main(["actor"]), 1)
                self.assertIn("actor bot (%s) is not RELEASE_OWNER" % key, err.getvalue())
                self.assertIn("dispatch release.yml as the owner account, or have the synthesizer merge", err.getvalue())
        with patch.dict(os.environ, dict(env, RELEASE_OWNER="")), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(rt.main(["actor"]), 1)
            self.assertIn("RELEASE_OWNER is unset", err.getvalue())

    def test_workflows_sequence_release_after_ci(self):
        root = Path(__file__).resolve().parent.parent
        release = (root / '.github/workflows/release.yml').read_text()
        ci = (root / '.github/workflows/ci.yml').read_text()
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", ci)
        self.assertNotIn("cancel-in-progress: true", ci)
        self.assertIn("needs: [prepare, validate, ci-gate]", release)
        self.assertIn("release-trigger.py ci-gate", release)
        self.assertIn("release-trigger.py actor", release)
        self.assertNotIn("scripts/test-*.py", release)
        self.assertNotIn("check-repo.py", release)

    def test_workflow_routes_dispatch_push_and_real_or_simulated_pr(self):
        root = Path(__file__).resolve().parent.parent
        workflow = (root / '.github/workflows/release.yml').read_text()
        block = workflow.split('      - name: Detect the cut\n', 1)[1].split('\n      - name:', 1)[0]
        script = '\n'.join(line[10:] for line in block.split('        run: |\n', 1)[1].splitlines())
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            (stage / 'scripts').symlink_to(root / 'scripts', target_is_directory=True)
            (stage / 'CHANGELOG.md').write_text(CUT)
            git = stage / 'git'
            git.write_text('#!/bin/sh\ncase "$1" in tag) echo "$FIXTURE_TAGS";; diff) echo "$FIXTURE_DIFF";; esac\n')
            git.chmod(0o755)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ['PATH'], BASE_SHA=HEAD,
                       GITHUB_OUTPUT=str(stage / 'output'), GITHUB_STEP_SUMMARY=str(stage / 'summary'))
            cases = [('workflow_dispatch', '', '', '2.0.0-rc.1', 0, 'version=2.0.0-rc.1'),
                     ('push', '', '', '', 0, 'version=1.2.3'),
                     ('push', '', 'v1.2.3', '', 0, 'ready=false'),
                     ('pull_request', 'CHANGELOG.md', '', '', 0, 'version=1.2.3'),
                     ('pull_request', 'CHANGELOG.md', 'v1.2.3', '', 1, ''),
                     ('pull_request', '', '', '', 0, 'simulated=true')]
            for event, diff, tags, version, code, expected in cases:
                with self.subTest(event=event, diff=diff, tags=tags):
                    (stage / 'output').write_text('')
                    run = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], cwd=tmp,
                                         env=dict(env, EVENT=event, INPUT_VERSION=version,
                                                  FIXTURE_DIFF=diff, FIXTURE_TAGS=tags), capture_output=True, text=True)
                    self.assertEqual(run.returncode, code, run.stderr)
                    self.assertIn(expected, (stage / 'output').read_text())
                    if event == 'pull_request' and diff:
                        self.assertNotIn('simulated=true', (stage / 'output').read_text())


if __name__ == "__main__":
    unittest.main()
