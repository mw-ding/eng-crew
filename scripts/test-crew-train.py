"""Tests for crew train (#321): a fake `gh` and a logging `git` on PATH, a temp bare origin; fixtures in
crew_testlib.py (stdlib only)."""
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
# Fake gh: pr view serves $FAKE_GH_DIR/pr-<n>.json; pr checks plays checks.json in order (null: no checks reported
# yet, exit 1), keeping the last; pr merge squashes refs/pull/<n>/head onto the origin's main like GitHub does,
# refusing a head that is not --match-head-commit; every call is logged with its time.
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
    elif args[:2] == ["pr", "view"]:
        print(json.dumps(pr(args[2])))
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

    def serve(self, n, head, reviews):
        with open(os.path.join(self.gh_dir, "pr-%d.json" % n), "w") as f:
            json.dump({"number": n, "state": "OPEN", "headRefOid": head, "labels": [], "statusCheckRollup": [],
                       "reviews": reviews}, f)

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

    def record(self):
        with open(os.path.join(self.state, "trains", "train-1.json")) as f:
            return json.load(f)

    def built(self, *prs):
        heads = [self.pr(n, {"f%d.txt" % n: "x\n"}) for n in prs]
        r = self.train("build", *map(str, prs))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return heads


class Build(TrainBase):
    def test_build_merges_in_order_and_drops_conflict(self):
        h1, h2 = self.pr(1, {"b.txt": "one\n"}), self.pr(2, {"a.txt": "two\n"})
        self.pr(3, {"a.txt": "three\n"})  # conflicts with #2 once #2 is in the train
        base = self.remote("refs/heads/main")
        r = self.train("build", "1", "2", "3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record()
        self.assertEqual([(m["pr"], m["head"]) for m in rec["members"]], [(1, h1), (2, h2)])
        self.assertIn("member pr=1 head=%s step=" % h1, r.stdout)
        self.assertIn("dropped pr=3 reason=conflict", r.stdout)
        self.assertEqual(r.stdout.count("ci-link "), 1)  # one run for both jobs
        self.assertIn("ci-link %s\n" % LINK, r.stdout)
        self.assertIn("train n=1 branch=crew/train-1 base=%s sha=%s pr=900 local=pass ci=pass" % (base, rec["sha"]),
                      r.stdout)
        self.assertEqual(self.remote("refs/heads/crew/train-1"), rec["sha"])
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
        land = self.train("land", "1")
        self.assertEqual(land.returncode, 1)
        self.assertIn("train 1 CI is fail, not pass; nothing landed", land.stdout)
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


class Land(TrainBase):
    def test_land_in_order_with_records_then_close_and_delete(self):
        heads = self.built(1, 2, 3)
        rec = self.record()
        r = self.train("land", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        merges = [c["args"] for c in self.gh_calls("pr", "merge")]
        self.assertEqual(merges, [["pr", "merge", str(n), "-R", "acme/widgets", "--squash", "--match-head-commit", h]
                                  for n, h in zip((1, 2, 3), heads)])
        main = self.remote("refs/heads/main")
        self.assertEqual(self.git("rev-parse", main + "^{tree}"), self.git("rev-parse", rec["sha"] + "^{tree}"))
        posts = [c["args"] for c in self.gh_calls("pr", "review")]
        self.assertEqual([p[2] for p in posts], ["1", "2", "3"])
        for (n, head), post in zip(zip((1, 2, 3), heads), posts):
            body = post[post.index("--body") + 1]
            self.assertTrue(body.startswith("[Sam/merge] squashed @ %s" % head[:7]), body)
            for text in ["`crew/train-1` @ " + rec["sha"], LINK, "train PR #900", 'Permission: merge_grant = "test grant"',
                         "<!-- crew:v1 role=synthesizer pass=merge pr=%d sha=%s round=n/a verdict=n/a -->" % (n, head)]:
                self.assertIn(text, body)
        self.assertEqual([c["args"] for c in self.gh_calls("pr", "close")], [["pr", "close", "900", "-R", "acme/widgets"]])
        self.assertEqual(self.remote("refs/heads/crew/train-1"), "")
        self.assertIn("train n=1 landed=3/3 pr-closed=yes branch-deleted=yes", r.stdout)

    def test_land_stops_on_head_change(self):
        heads = self.built(1, 2, 3)
        self.serve(2, "f" * 40, [])  # #2 got a new commit after the train was built
        r = self.train("land", "1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual([c["args"][2] for c in self.gh_calls("pr", "merge")], ["1"])
        self.assertIn("landed pr=1 head=%s" % heads[0], r.stdout)
        self.assertIn("stopped pr=2 reason=head changed: %s, tested %s" % ("f" * 40, heads[1]), r.stdout)
        self.assertIn("train n=1 landed=1/3 pr-closed=yes branch-deleted=yes", r.stdout)
        self.assertEqual(self.record()["stopped"]["pr"], 2)

    def test_land_stops_when_main_moved_or_no_approval(self):
        self.built(1)
        self.commit({"z.txt": "z\n"}, "someone else landed")
        self.git("push", "-q", "origin", "main")
        r = self.train("land", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("stopped pr=1 reason=main moved", r.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])
        self.pr(2, {"b.txt": "two\n"}, approved=False)
        self.assertEqual(self.train("build", "2").returncode, 0)
        r = self.train("land", "2")
        self.assertIn("stopped pr=2 reason=no approval verdict at head", r.stdout)
        self.write_profile()  # merge_grant = "none" and no merge-ok at head
        self.pr(3, {"c.txt": "three\n"})
        self.assertEqual(self.train("build", "3").returncode, 0)
        r = self.train("land", "3")
        self.assertIn("stopped pr=3 reason=no merge permission", r.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])


if __name__ == "__main__":
    unittest.main()
