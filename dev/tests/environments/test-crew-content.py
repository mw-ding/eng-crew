"""Fixture tests for portable verdict content checks and train records (#502).

Real git rebases prove that hunk shifts carry, changed whitespace/modes/binary
content do not, and a differing applied train patch is sent to its builder.
Run in CI through the dev/tests/*/test-*.py glob.
"""
import importlib.util
import json
import os
import unittest

spec = importlib.util.spec_from_file_location("train_tests", os.path.join(os.path.dirname(__file__), "test-crew-train.py"))
train = importlib.util.module_from_spec(spec)
spec.loader.exec_module(train)


class Content(train.TrainBase):
    def test_solo_train_conflict_routes_owner_pickup_without_builder(self):
        self.pr(1, {"a.txt": "first\n"})
        head = self.pr(2, {"a.txt": "second\n"})
        self.assertEqual(self.train("build", "1", "2").returncode, 0)
        _, reviews = self.view(2)
        self.serve(2, head, reviews, labels=["crew:solo"], mergeable="CONFLICTING")
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash"}}, f)
        result = self.train("land", "1", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("merge-up pr=2 status=solo", result.stdout)
        self.assertEqual(self.record()["dropped"][0]["merge_up"], "solo")
        with open(os.path.join(self.state, "inbox", "ash.jsonl")) as f:
            message = json.loads(f.read())
        self.assertEqual((message["kind"], message["refs"][:2]), ("solo", ["#2", head]))
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-2.jsonl")))

    def compare(self, base, verified, updated_base, updated):
        return self.crew("content", base, verified, updated_base, updated, "--repo", self.project_dir,
                         "--project", self.project)

    def rebased(self):
        self.commit({"a.txt": "first\n" + "middle\n" * 12 + "last\n"}, "long base")
        base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-b", "feature")
        self.commit({"a.txt": "first\n" + "middle\n" * 12 + "LAST\n"}, "feature")
        verified = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "main")
        self.commit({"a.txt": "prefix\nfirst\n" + "middle\n" * 12 + "last\n"}, "base shifted")
        updated_base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "feature")
        self.git("rebase", "main")
        return base, verified, updated_base, self.git("rev-parse", "HEAD")

    def test_identical_patch_rebase_carries_full_verified_sha(self):
        refs = self.rebased()
        self.assertNotEqual(refs[1], refs[3])
        r = self.compare(*refs)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "content=identical carried-from=" + refs[1])

    def test_differing_rebase_routes_builder_including_whitespace(self):
        base, verified, updated_base, _ = self.rebased()
        self.commit({"a.txt": "prefix\nfirst\n" + "middle\n" * 12 + "LAST \n"}, "resolution differs")
        r = self.compare(base, verified, updated_base, self.git("rev-parse", "HEAD"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout.strip(), "content=different route=builder")

    def test_modes_and_binary_changes_are_not_carried(self):
        base = self.git("rev-parse", "HEAD")
        self.commit({"f.txt": "x\n", "binary.dat": "a\x00b"}, "verified")
        verified = self.git("rev-parse", "HEAD")
        os.chmod(os.path.join(self.project_dir, "f.txt"), 0o755)
        self.git("add", "f.txt")
        self.git("commit", "-q", "-m", "mode differs")
        self.assertEqual(self.compare(base, verified, base, self.git("rev-parse", "HEAD")).returncode, 1)
        self.git("reset", "--hard", verified)
        self.commit({"binary.dat": "a\x00c"}, "binary differs")
        self.assertEqual(self.compare(base, verified, base, self.git("rev-parse", "HEAD")).returncode, 1)

    def test_unavailable_commit_blocks_carry(self):
        head = self.git("rev-parse", "HEAD")
        r = self.compare(head, head, head, "0" * 40)
        self.assertEqual(r.returncode, 1)
        self.assertIn("content=unverified route=builder", r.stdout)

    def test_updated_head_without_verified_base_blocks_carry(self):
        _, head = self.portable_train()
        _, reviews = self.view(1)
        base = self.record()["members"][0]["verified_base"]
        reviews[0]["body"] = reviews[0]["body"].replace(" base=" + base, "")
        self.serve(1, head, reviews)
        r = self.train("build", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("reason=no-verified-base", r.stdout)
        self.assertEqual(self.record(2)["members"], [])
        self.assertEqual(self.gh_calls("pr", "merge"), [])

    def test_unchanged_head_without_base_keeps_existing_train_path(self):
        head = self.pr(1, {"feature.txt": "x\n"})
        _, reviews = self.view(1)
        reviews[0]["body"] = reviews[0]["body"].replace(" base=" + self.git("rev-parse", "origin/main"), "")
        self.serve(1, head, reviews)
        r = self.train("build", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.train("land", "1", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        args = self.gh_calls("pr", "review")[0]["args"]
        body = args[args.index("--body") + 1]
        self.assertIn("sha=" + head, body)
        self.assertNotIn("content=identical", body)
        self.assertNotIn("carried-from=", body)

    def test_green_train_records_patch_identity_in_merge_marker(self):
        head = self.built(1)[0]
        r = self.train("land", "1", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = self.gh_calls("pr", "review")[0]["args"]
        body = body[body.index("--body") + 1]
        self.assertIn("content=identical carried-from=" + head, body)
        self.assertIn("sha=" + head, body)
        self.assertIn(self.record()["sha"], body)

    def portable_train(self):
        base, verified, updated_base, updated = self.rebased()
        self.git("push", "-q", "origin", "main", verified + ":refs/pull/1/head")
        self.git("push", "-q", "origin", updated + ":refs/heads/updated-fixture")
        self.git("update-ref", "refs/pull/1/head", updated, verified, cwd=self.origin)
        marker = "<!-- crew:v1 role=reviewer-validator pass=verdict pr=1 sha=%s base=%s round=1 verdict=pass -->" % (
            verified, base)
        self.serve(1, updated, [{"body": "[Vera/verdict] round 1\n" + marker}])
        r = self.train("build", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return verified, updated

    def test_updated_head_lands_with_old_identical_passing_verdict(self):
        verified, updated = self.portable_train()
        self.assertEqual(self.record()["members"][0]["verified_head"], verified)
        r = self.train("land", "1", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        args = self.gh_calls("pr", "merge")[0]["args"]
        self.assertEqual(args[args.index("--match-head-commit") + 1], updated)
        args = self.gh_calls("pr", "review")[0]["args"]
        body = args[args.index("--body") + 1]
        self.assertIn("sha=" + updated, body)
        self.assertIn("content=identical carried-from=" + verified, body)

    def test_precheck_accepts_proven_old_formal_verdict(self):
        verified, updated = self.portable_train()
        path, view = train.Precheck.complete_view(self, 1)
        base = self.record()["members"][0]["verified_base"]
        view["reviews"][0]["body"] = view["reviews"][0]["body"].replace(
            "sha=" + updated, "sha=" + verified + " base=" + base)
        with open(path, "w") as f:
            json.dump(view, f)
        r = self.train("check", "1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("name=verdict status=pass", r.stdout)
        self.assertIn(verified, r.stdout)

    def test_later_changes_verdict_stops_carried_approval(self):
        _, updated = self.portable_train()
        _, reviews = self.view(1)
        reviews.append({"body": "<!-- crew:v1 role=reviewer-validator pass=verdict pr=1 sha=%s round=2 verdict=changes -->" % updated})
        self.serve(1, updated, reviews)
        r = self.train("land", "1", "1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("no approval verdict at head", r.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])

    def test_differing_train_patch_is_dropped_and_routes_builder(self):
        self.pr(1, {"a.txt": "feature\n", "b.txt": "already landed\n"})
        self.commit({"b.txt": "already landed\n"}, "part of patch is now in main")
        self.git("push", "-q", "origin", "main")
        self.pr(2, {"safe.txt": "safe\n"})
        self.assertEqual(self.train("build", "1", "2").returncode, 0)
        self.assertEqual([m["pr"] for m in self.record()["members"]], [2])
        self.assertEqual(self.record()["dropped"][0]["reason"], "content-different")
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "10": "ben-1"}}, f)
        self.put("runs/ben-1.json", json.dumps(dict(index=10, role="builder", item="issue #1",
                 **{"pass": "build"}, repo=self.project_dir, worktree=self.project_dir, claim="unused", engine="codex",
                 model="test", effort="medium", harness="codex", pr=1)))
        r = self.train("land", "1", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("merge-up pr=1 status=builder", r.stdout)
        with open(os.path.join(self.state, "inbox", "ben-1.jsonl")) as f:
            self.assertEqual(json.loads(f.read())["kind"], "fix")
        self.assertEqual(self.gh_calls("api"), [])

    def test_land_rechecks_identity_and_routes_differing_patch(self):
        self.built(1)
        rec = self.record()
        rec["members"][0]["updated_base"] = rec["members"][0]["step"]
        self.put("trains/train-1.json", json.dumps(rec))
        with open(self.state_file, "w") as f:
            json.dump({"crew-acme-widgets": {"0": "ash", "10": "ben-1"}}, f)
        self.put("runs/ben-1.json", json.dumps(dict(index=10, role="builder", item="issue #1",
                 **{"pass": "build"}, repo=self.project_dir, worktree=self.project_dir, claim="unused", engine="codex",
                 model="test", effort="medium", harness="codex", pr=1)))
        r = self.train("land", "1", "1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("stopped pr=1 reason=content-different", r.stdout)
        self.assertIn("merge-up pr=1 status=builder", r.stdout)
        self.assertEqual(self.gh_calls("pr", "merge"), [])


if __name__ == "__main__":
    unittest.main()
