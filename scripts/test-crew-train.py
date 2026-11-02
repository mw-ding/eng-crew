"""Tests for crew train (#321): a fake `gh` and a logging `git` on PATH, a temp bare origin; fixtures in
crew_testlib.py (stdlib only).

Covers, with the fake `gh` (its `pr merge` squashes onto the temp bare origin): build merges in order
and drops a conflict even when the repo's `info/attributes` sets `merge=union`, never force-pushes and
takes the next train number, CI read only after the grace period with no checks yet counted as pending,
a red train or failing local check lands nothing, land one member per call in order (out of order
refused) with merge records citing the train then close and delete, land stops on a head change, a moved
default branch, a missing verdict, no merge permission, `crew:escalated`, `crew:changes`, `crew:hold`,
an open rereview, an open hold-until, or a PR GitHub reports `CONFLICTING` or `UNKNOWN`, `close` ends a
train early, `bisect` not yet. Run in CI.
"""
import json
import os
import shutil
import subprocess
import textwrap
import unittest
from crew_testlib import Base

LINK = "https://github.com/acme/widgets/actions/runs/1"  # the CI run; gh pr checks links its jobs
PASS, PENDING, FAIL = ([{"name": name, "bucket": b, "link": LINK + "/job/%d" % i} for i, name in enumerate(["ci", "lint"])]
                       for b in ("pass", "pending", "fail"))
# Fake gh: pr view / issue view serve $FAKE_GH_DIR/pr-<n>.json / issue-<n>.json; pr checks plays checks.json in order
# (null: no checks reported yet, exit 1), keeping the last; pr merge squashes refs/pull/<n>/head onto the origin's main
# like GitHub does, refusing a head that is not --match-head-commit; every call is logged with its time.
FAKE_GH = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, subprocess, sys, tempfile, time
    args, d = sys.argv[1:], os.environ["FAKE_GH_DIR"]
    with open(os.path.join(d, "gh.log"), "a") as f:
        f.write(json.dumps({"t": time.time(), "args": args}) + "\\n")
    pr = lambda n: json.load(open(os.path.join(d, "pr-%s.json" % n)))
    if args[:2] == ["pr", "create"]:
        print("https://github.com/acme/widgets/pull/900")
    elif args[:2] == ["pr", "checks"]:
        seq = json.load(open(os.path.join(d, "checks.json")))
        json.dump(seq[1:] or seq, open(os.path.join(d, "checks.json"), "w"))
        if seq[0] is None:
            sys.exit("no checks reported on the 'crew/train-1' branch")
        print(json.dumps(seq[0]))
        sys.exit(8 if any(c["bucket"] == "pending" for c in seq[0]) else 0)
    elif args[:1] == ["api"]:
        print(open(os.path.join(d, "tree.json")).read())
    elif args[:2] == ["pr", "view"]:
        print(json.dumps(pr(args[2])))
    elif args[:2] == ["issue", "view"]:
        print(open(os.path.join(d, "issue-%s.json" % args[2])).read())
    elif args[:2] == ["pr", "merge"]:
        if pr(args[2])["headRefOid"] != args[args.index("--match-head-commit") + 1]:
            sys.exit("GraphQL: Head branch was modified")
        tmp = tempfile.mkdtemp(dir=d)
        for cmd in (["clone", "-q", os.environ["FAKE_ORIGIN"], "."], ["fetch", "-q", "origin", "pull/%s/head" % args[2]],
                    ["merge", "-q", "--squash", "FETCH_HEAD"], ["commit", "-q", "-m", "squash #" + args[2]],
                    ["push", "-q", "origin", "HEAD:main"]):
            subprocess.run([os.environ["FAKE_REAL_GIT"], *cmd], cwd=tmp, check=True, capture_output=True)
    """)
IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid"}


class TrainBase(Base):
    def setUp(self):
        super().setUp()
        bindir, real = os.path.join(self.tmp, "bin"), shutil.which("git")
        self.gh_dir, self.origin = os.path.join(self.tmp, "gh"), os.path.join(self.tmp, "origin.git")
        os.makedirs(self.gh_dir)
        self.git_log = os.path.join(self.tmp, "git.log")
        for name, text in [("gh", FAKE_GH), ("git", '#!/bin/sh\necho "$*" >> %s\nexec %s "$@"\n' % (self.git_log, real))]:
            with open(os.path.join(bindir, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(bindir, name), 0o755)
        self.env.update(IDENTITY, FAKE_GH_DIR=self.gh_dir, FAKE_ORIGIN=self.origin, FAKE_REAL_GIT=real)
        with open(self.project) as f:
            text = f.read().replace('name = "tmux"\n', 'name = "tmux"\noptions = { merge_grant = "test grant" }\n')
        with open(self.project, "w") as f:
            f.write(text)
        self.git("init", "-q", "--bare", "-b", "main", self.origin, cwd=self.tmp)
        self.git("init", "-q", "-b", "main")
        self.git("remote", "add", "origin", self.origin)
        self.commit({"a.txt": "base\n", "scripts/test-ok.py": "print('ok')\n"}, "base")
        self.git("push", "-q", "origin", "main")
        self.checks(PASS)

    def git(self, *args, cwd=None):
        r = subprocess.run(["git", *args], cwd=cwd or self.project_dir, capture_output=True, text=True,
                           env=dict(os.environ, **IDENTITY))
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def commit(self, files, msg):
        for name, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(self.project_dir, name)), exist_ok=True)
            with open(os.path.join(self.project_dir, name), "w") as f:
                f.write(text)
        self.git("add", *files)
        self.git("commit", "-q", "-m", msg)

    def pr(self, n, files, approved=True):
        """A PR head off origin/main at refs/pull/<n>/head, served by the fake gh, approved at head by default."""
        self.git("checkout", "-q", "-B", "pr%d" % n, "origin/main")
        self.commit(files, "pr %d" % n)
        self.git("push", "-q", "origin", "HEAD:refs/pull/%d/head" % n)
        head = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        marker = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=%d sha=%s round=1 verdict=pass -->" % (n, head)
        self.serve(n, head, [{"body": "[Vera/verdict] round 1\n" + marker}] if approved else [])
        return head

    def serve(self, n, head, reviews, labels=(), comments=(), mergeable="MERGEABLE"):
        with open(os.path.join(self.gh_dir, "pr-%d.json" % n), "w") as f:
            json.dump({"number": n, "state": "OPEN", "headRefOid": head, "labels": [{"name": x} for x in labels],
                       "statusCheckRollup": [], "reviews": list(reviews), "comments": [{"body": b} for b in comments],
                       "mergeable": mergeable}, f)

    def view(self, n):
        with open(os.path.join(self.gh_dir, "pr-%d.json" % n)) as f:
            pr = json.load(f)
        return pr["headRefOid"], pr["reviews"]

    def issue(self, n, state):
        with open(os.path.join(self.gh_dir, "issue-%d.json" % n), "w") as f:
            json.dump({"state": state}, f)

    def checks(self, *seq):
        with open(os.path.join(self.gh_dir, "checks.json"), "w") as f:
            json.dump(list(seq), f)

    def train(self, *args):
        return self.crew("train", *args, "--project", self.project, "--grace", "0", "--interval", "0.01")

    def gh_calls(self, *prefix):
        with open(os.path.join(self.gh_dir, "gh.log")) as f:
            calls = [json.loads(line) for line in f]
        return [c for c in calls if c["args"][:len(prefix)] == list(prefix)]

    def remote(self, ref):
        return self.git("ls-remote", self.origin, ref).split("\t")[0]

    def record(self, n=1):
        with open(os.path.join(self.state, "trains", "train-%d.json" % n)) as f:
            return json.load(f)

    def land_all(self, n, prs):
        return [self.train("land", str(n), str(pr)) for pr in prs]

    def built(self, *prs):
        heads = [self.pr(n, {"f%d.txt" % n: "x\n"}) for n in prs]
        r = self.train("build", *map(str, prs))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return heads


class Build(TrainBase):
    def test_build_merges_in_order_and_drops_conflict(self):
        h1, h2 = self.pr(1, {"b.txt": "one\n"}), self.pr(2, {"a.txt": "two\n"})
        self.pr(3, {"a.txt": "three\n"})  # conflicts with #2 once #2 is in the train
        with open(os.path.join(self.project_dir, ".git", "info", "attributes"), "w") as f:
            f.write("a.txt merge=union\n")  # the shared repo's own attributes would hide that conflict (train 4)
        base = self.remote("refs/heads/main")
        r = self.train("build", "1", "2", "3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record()
        self.assertEqual([(m["pr"], m["head"]) for m in rec["members"]], [(1, h1), (2, h2)])
        self.assertIn("member pr=1 head=%s step=" % h1, r.stdout)
        self.assertIn("deferred pr=3 reason=overlap-with-2", r.stdout)
        self.assertEqual(r.stdout.count("ci-link "), 1)  # one run for both jobs
        self.assertIn("ci-link %s\n" % LINK, r.stdout)
        self.assertIn("train n=1 branch=crew/train-1 base=%s sha=%s pr=900 local=pass ci=pass" % (base, rec["sha"]),
                      r.stdout)
        self.assertEqual(self.remote("refs/heads/crew/train-1"), rec["sha"])
        self.git("fetch", "-q", "origin", "crew/train-1")  # built in a temporary clone, so only the remote has it
        self.assertEqual(self.git("log", "--first-parent", "--format=%s", "%s..%s" % (base, rec["sha"])).splitlines(),
                         ["crew train 1: merge #2 @ %s" % h2[:7], "crew train 1: merge #1 @ %s" % h1[:7]])
        self.assertEqual(self.git("show", rec["sha"] + ":a.txt"), "two")
        create = self.gh_calls("pr", "create")[0]["args"]
        self.assertIn("--draft", create)
        self.assertEqual(create[create.index("--title") + 1], "crew train 1 (CI only, do not merge)")
        with open(self.git_log) as f:
            pushes = [line for line in f if " push " in line]
        self.assertTrue(pushes and not any(" -f" in p or "--force" in p for p in pushes), pushes)
        self.assertEqual(os.listdir(os.path.join(self.tmp, "state", "wt")), [])  # train worktree removed
        os.remove(os.path.join(self.state, "trains", "train-1.json"))  # the remote branch alone still counts
        self.assertEqual(self.train("build", "1").returncode, 0)  # the next train takes the next number
        self.assertEqual(self.remote("refs/heads/crew/train-1"), rec["sha"])
        self.assertNotEqual(self.remote("refs/heads/crew/train-2"), "")

    def test_ci_wait_grace_then_no_checks_yet_is_pending(self):
        self.pr(1, {"b.txt": "one\n"})
        self.checks(None, PENDING, PASS)
        r = self.crew("train", "build", "1", "--project", self.project, "--grace", "0.5", "--interval", "0.01")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ci=pass", r.stdout)
        create, checks = self.gh_calls("pr", "create")[0], self.gh_calls("pr", "checks")
        self.assertEqual(len(checks), 3)
        self.assertGreaterEqual(checks[0]["t"] - create["t"], 0.5)

    def test_red_ci_or_local_failure_lands_nothing(self):
        self.pr(1, {"b.txt": "one\n"})
        self.checks(FAIL)
        r = self.train("build", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("ci-link %s\ntrain n=1" % LINK, r.stdout)  # the failing check, to read after the close
        self.assertIn("ci=fail", r.stdout)
        self.assertEqual([c["args"] for c in self.gh_calls("pr", "close")], [["pr", "close", "900", "-R", "acme/widgets"]])
        self.assertEqual(self.remote("refs/heads/crew/train-1"), "")
        land = self.train("land", "1", "1")
        self.assertEqual(land.returncode, 1)
        self.assertIn("train 1 is CI fail; nothing landed", land.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])
        self.pr(2, {"scripts/test-bad.py": "raise SystemExit('boom')\n"})
        r = self.train("build", "2")
        self.assertEqual(r.returncode, 1)
        self.assertIn("local=fail:scripts/test-bad.py ci=none", r.stdout)
        self.assertIn("boom", r.stdout)
        self.assertEqual(self.remote("refs/heads/crew/train-2"), "")  # nothing pushed, no train PR
        self.assertEqual(len(self.gh_calls("pr", "create")), 1)

    def test_bisect_not_yet(self):
        r = self.train("bisect", "1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not implemented yet", r.stdout)


class Pipeline(TrainBase):
    def test_successor_prepared_while_ci_pending_then_lands_serially(self):
        self.pr(1, {"one.txt": "one"})
        self.pr(2, {"two.txt": "two"})
        self.assertEqual(self.train("build", "1", "--no-wait").returncode, 0)
        self.assertEqual(self.record()["ci"], "pending")
        self.assertEqual(self.gh_calls("pr", "checks"), [])
        result = self.train("build", "1", "2", "--after", "1", "--no-wait")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("deferred pr=1 reason=predecessor-member", result.stdout)
        self.assertEqual(self.record(2)["base"], self.record()["sha"])
        self.assertEqual(self.train("wait", "2").returncode, 0)
        result = self.train("land", "2", "2")
        self.assertIn("predecessor has not finished", result.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])
        self.assertEqual(self.train("wait", "1").returncode, 0)
        self.assertEqual(self.train("land", "1", "1").returncode, 0)
        result = self.train("land", "2", "2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([c["args"][2] for c in self.gh_calls("pr", "merge")], ["1", "2"])

    def test_stopped_predecessor_rebuilds_successor_on_new_main(self):
        self.built(1, 2)
        self.pr(3, {"three.txt": "three"})
        self.assertEqual(self.train("build", "3", "--after", "1", "--no-wait").returncode, 0)
        self.assertEqual(self.train("land", "1", "1").returncode, 0)
        head, reviews = self.view(2)
        self.serve(2, head, reviews, labels=["crew:hold"])
        self.assertEqual(self.train("land", "1", "2").returncode, 1)
        result = self.train("wait", "2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("rebuild train=2 reason=predecessor-stopped", result.stdout)
        self.assertTrue(self.record(2)["closed"])
        self.assertEqual(self.record(3)["base"], self.remote("refs/heads/main"))
        self.assertIsNone(self.record(3)["after"])
        self.assertEqual(self.train("land", "3", "3").returncode, 0)

    def test_shared_file_without_conflict_stays_in_train(self):
        self.commit({"a.txt": "first\n" + "middle\n" * 12 + "last\n"}, "multiline base")
        self.git("push", "-q", "origin", "main")
        self.pr(1, {"a.txt": "FIRST\n" + "middle\n" * 12 + "last\n"})
        self.pr(2, {"a.txt": "first\n" + "middle\n" * 12 + "LAST\n"})
        result = self.train("build", "1", "2")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([m["pr"] for m in self.record()["members"]], [1, 2])


class Precheck(TrainBase):
    def complete_view(self, n):
        path = os.path.join(self.gh_dir, "pr-%d.json" % n)
        with open(path) as f:
            view = json.load(f)
        head = view["headRefOid"]
        body = "\n".join("<!-- crew:v1 role=reviewer-validator pass=%s sha=%s verdict=pass -->" % (p, head)
                         for p in ("review", "validate", "verdict"))
        view.update(body="## Acceptance Evidence\nN/A: no observable behaviour changes\n", files=[],
                    isDraft=False, baseRefName="main", closingIssuesReferences=[{"number": 1}],
                    statusCheckRollup=[{"__typename": "StatusContext", "state": "SUCCESS"}],
                    reviews=[{"body": body, "state": "APPROVED", "author": {"login": "acme-reviewer"}}])
        with open(path, "w") as f:
            json.dump(view, f)
        return path, view

    def test_reports_all_prs_without_git_build_or_github_writes(self):
        self.pr(1, {"one.txt": "one"})
        self.pr(2, {"two.txt": "two"})
        self.complete_view(1)
        path, view = self.complete_view(2)
        view["labels"] = [{"name": "crew:sensitive"}, {"name": "crew:needs-mirror"}]
        view["body"] = "no evidence"
        view["statusCheckRollup"] = []
        with open(path, "w") as f:
            json.dump(view, f)
        result = self.train("check", "1", "2")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for text in ("name=verdict status=pass", "name=evidence status=manual", "name=sensitive status=blocked",
                     "name=mirror status=blocked", "name=ci status=blocked", "name=evidence status=blocked"):
            self.assertIn(text, result.stdout)
        self.assertEqual(self.gh_calls("pr", "create"), [])
        self.assertEqual(self.gh_calls("pr", "merge"), [])
        with open(self.git_log) as f:
            self.assertNotIn("merge", f.read())
        self.assertFalse(os.path.exists(os.path.join(self.state, "trains")))

    def test_failed_validate_marker_cannot_pass_precheck(self):
        self.pr(1, {"one.txt": "one"})
        path, view = self.complete_view(1)
        head = view["headRefOid"]
        view["reviews"][0]["body"] = view["reviews"][0]["body"].replace(
            "pass=validate sha=%s verdict=pass" % head, "pass=validate sha=%s verdict=changes" % head)
        with open(path, "w") as f:
            json.dump(view, f)
        result = self.train("check", "1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("name=verdict status=blocked", result.stdout)


    def test_evidence_artifacts_checked_at_head(self):
        self.pr(1, {"one.txt": "one"})
        path, view = self.complete_view(1)
        view["body"] = "## Acceptance Evidence\nCLI: evidence/1/output.txt\n"
        with open(path, "w") as f:
            json.dump(view, f)
        for present in (True, False):
            with open(os.path.join(self.gh_dir, "tree.json"), "w") as f:
                json.dump({"tree": [{"path": "evidence/1/output.txt"}] if present else []}, f)
            result = self.train("check", "1")
            self.assertEqual(result.returncode, 0 if present else 1, result.stdout + result.stderr)
            self.assertIn("name=evidence status=" + ("manual" if present else "blocked"), result.stdout)
        self.assertIn(view["headRefOid"], self.gh_calls("api")[-1]["args"][1])


    def test_missing_mirror_record_blocks_without_label(self):
        self.pr(1, {"one.txt": "one"})
        path, view = self.complete_view(1)
        view["files"] = [{"path": "templates/runtimes/tmux/synthesizer.md"}]
        with open(path, "w") as f:
            json.dump(view, f)
        result = self.train("check", "1")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('name=mirror status=blocked reason="no coordinator mirror/drift record"', result.stdout)


VERDICT = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=%d sha=%s round=1 verdict=pass -->"
REREVIEW = "<!-- crew:v1 role=coordinator pass=steer pr=%d sha=%s round=n/a verdict=n/a cmd=rereview cmd-id=9 -->"


class Land(TrainBase):
    def test_land_in_order_with_records_then_close_and_delete(self):
        heads = self.built(1, 2, 3)
        rec = self.record()
        # #1: a rereview at head answered by a fresh verdict, and a hold-until on an item that has landed: not blocking
        self.serve(1, heads[0], [{"body": VERDICT % (1, heads[0])}, {"body": REREVIEW % (1, heads[0])},
                                 {"body": VERDICT % (1, heads[0])}], comments=["[Ash/hold] hold-until-#77"])
        self.issue(77, "CLOSED")
        wrong = self.train("land", "1", "2")
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("train 1 lands #1 next, not #2; nothing landed", wrong.stdout)
        runs = self.land_all(1, (1, 2, 3))
        self.assertEqual([r.returncode for r in runs], [0, 0, 0], [r.stdout + r.stderr for r in runs])
        self.assertIn("train n=1 landed=1/3 next=2", runs[0].stdout)
        self.assertIn("train n=1 landed=2/3 next=3", runs[1].stdout)
        self.assertIn("landed pr=3 head=%s" % heads[2], runs[2].stdout)
        self.assertIn("train n=1 landed=3/3 pr-closed=yes branch-deleted=yes", runs[2].stdout)
        merges = [c["args"] for c in self.gh_calls("pr", "merge")]
        self.assertEqual(merges, [["pr", "merge", str(n), "-R", "acme/widgets", "--squash", "--match-head-commit", h]
                                  for n, h in zip((1, 2, 3), heads)])
        self.assertTrue(self.gh_calls("pr", "view")[0]["args"][-1].endswith(",comments,mergeable"))
        main = self.remote("refs/heads/main")
        self.assertEqual(self.git("rev-parse", main + "^{tree}"), self.git("rev-parse", rec["sha"] + "^{tree}"))
        posts = [c["args"] for c in self.gh_calls("pr", "review")]
        self.assertEqual([p[2] for p in posts], ["1", "2", "3"])
        for (n, head), post in zip(zip((1, 2, 3), heads), posts):
            body = post[post.index("--body") + 1]
            self.assertTrue(body.startswith("[Sam/merge] squashed @ %s" % head[:7]), body)
            for text in ["Land rule: train of 3 (ready together).", "`crew/train-1` @ " + rec["sha"], LINK, "train PR #900", 'Permission: merge_grant = "test grant"',
                         "<!-- crew:v1 role=synthesizer pass=merge pr=%d sha=%s round=n/a verdict=n/a -->" % (n, head)]:
                self.assertIn(text, body)
        self.assertEqual([c["args"] for c in self.gh_calls("pr", "close")], [["pr", "close", "900", "-R", "acme/widgets"]])
        self.assertEqual(self.remote("refs/heads/crew/train-1"), "")
        self.assertIn("train 1 is closed; nothing landed", self.train("land", "1", "3").stdout)

    def test_land_stops_on_head_change(self):
        heads = self.built(1, 2, 3)
        self.serve(2, "f" * 40, [])  # #2 got a new commit after the train was built
        runs = self.land_all(1, (1, 2, 3))
        self.assertEqual([r.returncode for r in runs], [0, 1, 1])
        self.assertEqual([c["args"][2] for c in self.gh_calls("pr", "merge")], ["1"])
        self.assertIn("landed pr=1 head=%s" % heads[0], runs[0].stdout)
        self.assertIn("stopped pr=2 reason=head changed: %s, tested %s" % ("f" * 40, heads[1]), runs[1].stdout)
        self.assertIn("train n=1 landed=1/3 pr-closed=yes branch-deleted=yes", runs[1].stdout)
        self.assertIn("train 1 is closed; nothing landed", runs[2].stdout)
        self.assertEqual(self.record()["stopped"]["pr"], 2)

    def test_land_stops_when_main_moved_or_no_approval(self):
        self.built(1)
        self.commit({"z.txt": "z\n"}, "someone else landed")
        self.git("push", "-q", "origin", "main")
        r = self.train("land", "1", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("stopped pr=1 reason=main moved", r.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])
        self.pr(2, {"b.txt": "two\n"}, approved=False)
        self.assertEqual(self.train("build", "2").returncode, 0)
        r = self.train("land", "2", "2")
        self.assertIn("stopped pr=2 reason=no approval verdict at head", r.stdout)
        self.write_profile()  # merge_grant = "none" and no merge-ok at head
        self.pr(3, {"c.txt": "three\n"})
        self.assertEqual(self.train("build", "3").returncode, 0)
        r = self.train("land", "3", "3")
        self.assertIn("stopped pr=3 reason=no merge permission", r.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])

    def test_land_stops_on_a_gate_added_while_ci_ran(self):
        self.issue(77, "OPEN")
        cases = [("escalated", {"labels": ["crew:escalated"]}, "state tag crew:escalated"),
                 ("changes", {"labels": ["crew:changes"]}, "state tag crew:changes"),
                 ("hold label", {"labels": ["crew:hold"]}, "state tag crew:hold"),  # hold_label_blocks defaults true
                 ("sensitive", {"labels": ["crew:sensitive"]}, "crew:sensitive needs owner merge-ok at head"),
                 ("rereview", {"rereview": True}, "open rereview at head"),
                 ("hold-until", {"comments": ["[Ash/hold] hold-until-#77"]}, "open coordinator hold-until-#77"),
                 ("conflicting", {"mergeable": "CONFLICTING"}, "not mergeable: GitHub reports CONFLICTING"),
                 ("unknown", {"mergeable": "UNKNOWN"}, "not mergeable: GitHub reports UNKNOWN")]
        for n, (name, change, reason) in enumerate(cases, 1):
            with self.subTest(gate=name):
                pr = 10 + n
                self.built(pr)
                head, reviews = self.view(pr)
                if change.pop("rereview", False):
                    reviews.append({"body": REREVIEW % (pr, head)})
                self.serve(pr, head, reviews, **change)
                r = self.train("land", str(n), str(pr))
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("stopped pr=%d reason=%s" % (pr, reason), r.stdout)
                self.assertIn("train n=%d landed=0/1 pr-closed=yes branch-deleted=yes" % n, r.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])
        self.assertEqual(len(self.gh_calls("pr", "view", "18")), 10)  # UNKNOWN is read 10 times, then refused

    def test_sensitive_land_requires_merge_ok_at_current_head(self):
        for n, sha in [(1, "0" * 40), (2, None)]:
            self.built(n)
            head, reviews = self.view(n)
            reviews.append({"body": "<!-- crew:v1 role=coordinator pass=steer cmd=merge-ok sha=%s -->" % (sha or head)})
            self.serve(n, head, reviews, labels=["crew:sensitive"])
            result = self.train("land", str(n), str(n))
            self.assertEqual(result.returncode, 1 if sha else 0, result.stdout + result.stderr)
            if sha:
                self.assertIn("crew:sensitive needs owner merge-ok at head", result.stdout)
                self.assertEqual(self.gh_calls("pr", "merge"), [])

    def test_close_ends_a_train_early(self):
        self.built(1, 2)
        r = self.train("close", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("train n=1 landed=0/2 pr-closed=yes branch-deleted=yes", r.stdout)
        self.assertEqual(self.remote("refs/heads/crew/train-1"), "")
        self.assertIn("train 1 is closed; nothing landed", self.train("land", "1", "1").stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])


if __name__ == "__main__":
    unittest.main()
