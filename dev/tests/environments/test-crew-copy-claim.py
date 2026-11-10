"""Tests for host-wide working-copy claims (environments/terminal/copy-claim.py, `mdstack copy-claim`, #391).

Covers: a second crew is refused while the first holds the copy, and only the holder releases; path aliases (a
symlink, `..`, a trailing slash) are one claim; an old claim from a still-live holder is never reclaimed by age;
re-acquiring one's own claim is a no-op; concurrent acquires have exactly one winner; and the CLI, run from two
profiles with separate state roots, refuses the second crew with exit 1 and names the holder. Stdlib only.
"""
import importlib.util
import json
import os
import sys
import threading
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, PROFILE, ROOT_DIR

spec = importlib.util.spec_from_file_location("copy_claim", os.path.join(ROOT_DIR, "environments", "terminal",
                                                                         "copy-claim.py"))
claims = importlib.util.module_from_spec(spec)
spec.loader.exec_module(claims)


class Helper(Base):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, MDSTACK_COPY_CLAIMS=self.env["MDSTACK_COPY_CLAIMS"])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.copy = os.path.join(self.tmp, "copy")
        os.makedirs(self.copy)

    def test_second_crew_refused_and_only_holder_releases(self):
        claims.acquire(self.copy, "/state/a", "ben-7", "issue #7")
        with self.assertRaises(RuntimeError) as e:
            claims.acquire(self.copy, "/state/b", "ben-9", "issue #9")
        self.assertIn("claimed by crew /state/a run ben-7 (issue #7)", str(e.exception))
        for crew, run in (("/state/b", "ben-7"), ("/state/a", "ben-8")):
            with self.assertRaises(RuntimeError):
                claims.release(self.copy, crew, run)
        self.assertEqual(claims.holder(self.copy)["crew"], "/state/a")
        claims.release(self.copy, "/state/a", "ben-7")
        self.assertIsNone(claims.holder(self.copy))
        self.assertEqual(claims.acquire(self.copy, "/state/b", "ben-9", "issue #9")["crew"], "/state/b")

    def test_aliases_are_one_claim(self):
        link = os.path.join(self.tmp, "link")
        os.symlink(self.copy, link)
        claims.acquire(self.copy, "/state/a", "ben-7", "issue #7")
        for alias in (link, link + "/", os.path.join(self.tmp, "bin", "..", "copy")):
            with self.subTest(alias=alias), self.assertRaises(RuntimeError):
                claims.acquire(alias, "/state/b", "ben-9", "issue #9")
        self.assertEqual(claims.holder(link)["path"], os.path.realpath(self.copy))

    def test_old_claim_of_live_holder_is_never_reclaimed_by_age(self):
        claims.acquire(self.copy, "/state/a", "ben-7", "issue #7")
        path = claims.claim_path(self.copy)
        with open(path) as f:
            rec = json.load(f)
        rec["since"] = "2000-01-01T00:00:00Z"
        with open(path, "w") as f:
            json.dump(rec, f)
        with self.assertRaises(RuntimeError) as e:
            claims.acquire(self.copy, "/state/b", "ben-9", "issue #9")
        self.assertIn("since 2000-01-01T00:00:00Z", str(e.exception))
        self.assertEqual(claims.holder(self.copy), rec)

    def test_own_reacquire_is_a_noop(self):
        first = claims.acquire(self.copy, "/state/a", "ben-7", "issue #7")
        self.assertEqual(claims.acquire(self.copy, "/state/a", "ben-7", "issue #7"), first)
        self.assertEqual(os.listdir(claims.store()), [os.path.basename(claims.claim_path(self.copy))])

    def test_concurrent_acquires_have_one_winner(self):
        won, barrier = [], threading.Barrier(8)

        def race(i):
            barrier.wait()
            try:
                claims.acquire(self.copy, "/state/%d" % i, "run-%d" % i, "")
                won.append(i)
            except RuntimeError:
                pass
        threads = [threading.Thread(target=race, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(won), 1)
        self.assertEqual(claims.holder(self.copy)["run"], "run-%d" % won[0])


class Cli(Base):
    """Two profiles with separate state roots stand in for two crews on one host."""
    def setUp(self):
        super().setUp()
        self.other = os.path.join(self.tmp, "other", "crew.toml")
        os.makedirs(os.path.dirname(self.other))
        with open(self.other, "w") as f:
            f.write(PROFILE.format(runtime="tmux", engine="claude-code", state=os.path.join(self.tmp, "other-state")))
        self.copy = os.path.join(self.tmp, "copy")
        os.makedirs(self.copy)

    def claim(self, project, *args):
        return self.crew("copy-claim", *args, "--path", self.copy, "--project", project)

    def test_second_crew_refused_until_holder_releases(self):
        r = self.claim(self.project, "acquire", "--run", "pack-7", "--item", "issue #7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.claim(self.other, "acquire", "--run", "pack-9", "--item", "issue #9")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("refusing: working copy %s claimed by crew %s run pack-7 (issue #7)" % (
            os.path.realpath(self.copy), self.state), r.stdout)
        self.assertEqual(self.claim(self.other, "release", "--run", "pack-7").returncode, 1)
        self.assertEqual(json.loads(self.claim(self.other, "show").stdout)["crew"], self.state)
        self.assertEqual(self.claim(self.project, "acquire").returncode, 2)
        self.assertEqual(self.claim(self.project, "release", "--run", "pack-7").returncode, 0)
        self.assertEqual(self.claim(self.other, "show").stdout.strip(), "null")
        self.assertEqual(self.claim(self.other, "acquire", "--run", "pack-9").returncode, 0)


if __name__ == "__main__":
    unittest.main()
