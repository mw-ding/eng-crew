"""Tests for crew land (#930, #873 B2): an external pack declaring land.mode = "async", whose backend map points
change.land, change.land-status and change.read-head at a fake `exland` CLI on PATH; fixtures in crew_testlib.py
(stdlib only).

Covers: none → request → queued → landing → landed with the landed revision; failed with its reason; timeout;
a stale head refused with no request; a lost acknowledgement resolved by read-back with exactly one request,
and a lost one that reads `none` blocked with no resend; an unknown or malformed status never taken as `none`;
an already in-flight land polled, not requested again; `status` reads once; a sync backend and a short --head
refused; no land lock or train state written in the backend-managed mode. Run in CI.
"""
import json
import os
import re
import sys
import textwrap
import unittest
from crew_testlib import Base, write_pack

HEAD, OTHER, LANDED = "a" * 40, "b" * 40, "c" * 40
# Fake exland: land-status plays $FAKE_LAND_DIR/status.json in order (keeping the last; an int entry exits with
# it); read-head prints head.txt; land exits with land-exit.txt (default 0). Every call is logged.
FAKE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    d, args = os.environ["FAKE_LAND_DIR"], sys.argv[1:]
    open(os.path.join(d, "calls.log"), "a").write(json.dumps(args) + "\\n")
    if args[0] == "land-status":
        path = os.path.join(d, "status.json")
        seq = json.load(open(path))
        json.dump(seq[1:] or seq, open(path, "w"))
        if isinstance(seq[0], int):
            sys.exit(seq[0])
        print(seq[0])
    elif args[0] == "head":
        print(open(os.path.join(d, "head.txt")).read())
    elif args[0] == "land":
        path = os.path.join(d, "land-exit.txt")
        sys.exit(int(open(path).read()) if os.path.exists(path) else 0)
    """)


class Land(Base):
    def setUp(self):
        super().setUp()
        self.fake = os.path.join(self.tmp, "land")
        os.makedirs(self.fake)
        exland = os.path.join(self.tmp, "bin", "exland")
        with open(exland, "w") as f:
            f.write(FAKE)
        os.chmod(exland, 0o755)
        self.env["FAKE_LAND_DIR"] = self.fake
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(repo, "templates", "backends", "github.toml")) as f:
            mapping = f.read()
        mapping = re.sub(r'(?m)^land = .*$', 'land = "exland land <n> --expect-head <head-sha>"\n'
                         'land-status = "exland land-status <n> <head-sha> -R <owner>/<repo>"', mapping)
        mapping = re.sub(r'(?m)^read-head = .*$', 'read-head = "exland head <n>"', mapping)
        self.org = write_pack(os.path.join(self.tmp, "pack"), mapping=mapping)
        self.manifest = os.path.join(self.tmp, "pack", "manifest.toml")
        with open(self.manifest) as f:
            text = f.read().replace('land = "supported"', 'land = "supported"\nland-status = "supported"')
        with open(self.manifest, "w") as f:
            f.write(text + '\n[land]\nmode = "async"\nserializes = true\ntests_against_tip = true\n')
        with open(self.project, "a") as f:
            f.write("[runtime.options]\nland_poll_interval = 1\nland_timeout = 3\n")
        self.head(HEAD)

    def head(self, sha):
        with open(os.path.join(self.fake, "head.txt"), "w") as f:
            f.write(sha)

    def statuses(self, *seq):
        with open(os.path.join(self.fake, "status.json"), "w") as f:
            json.dump(list(seq), f)

    def land(self, action="request", head=HEAD):
        r = self.crew("land", action, "--project", self.project, "--org-profile", self.org, "--pr", "7", "--head", head)
        if "--owner-transcript" in sys.argv:
            print("$ crew land %s --project <fixture>/crew.toml --org-profile <fixture>/pack/profile.toml --pr 7 "
                  "--head %s" % (action, head))
            print("exit: %d\n--- stdout\n%s--- stderr\n%s" % (r.returncode, r.stdout.replace(self.tmp, "<fixture>"),
                                                             r.stderr), end="")
        return r

    def calls(self, verb=None):
        path = os.path.join(self.fake, "calls.log")
        found = []
        if os.path.exists(path):
            with open(path) as f:
                found = [json.loads(line) for line in f]
        return [c for c in found if verb is None or c[0] == verb]

    def test_queued_landing_landed(self):
        self.statuses("none", "queued", "landing", "landed " + LANDED)
        r = self.land()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew: land #7 @ aaaaaaa: queued", r.stdout)
        self.assertIn("crew: land #7 @ aaaaaaa: landing", r.stdout)
        self.assertIn("crew: landed #7 @ aaaaaaa as " + LANDED, r.stdout)
        self.assertEqual(self.calls("land"), [["land", "7", "--expect-head", HEAD]])
        self.assertEqual(self.calls("land-status")[0], ["land-status", "7", HEAD, "-R", "acme/widgets"])
        self.assertFalse(os.path.exists(os.path.join(self.state, "locks")))  # backend-managed: no land lock
        self.assertFalse(os.path.exists(os.path.join(self.state, "trains")))  # and no train

    def test_failed(self):
        self.statuses("none", "queued", "failed checks red on tip")
        r = self.land()
        self.assertEqual(r.returncode, 1)
        self.assertIn("blocked: land #7 @ aaaaaaa: failed: checks red on tip", r.stdout)
        self.assertNotIn("landed", r.stdout)

    def test_timeout(self):
        self.statuses("none", "queued")
        r = self.land()
        self.assertEqual(r.returncode, 1)
        self.assertIn("blocked: land #7 @ aaaaaaa: timeout after 3s, still queued", r.stdout)
        self.assertEqual(len(self.calls("land")), 1)

    def test_stale_head(self):
        self.statuses("none")
        self.head(OTHER)
        r = self.land()
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale head, change head is '%s'; no request sent" % OTHER, r.stdout)
        self.assertEqual(self.calls("land"), [])

    def test_lost_acknowledgement(self):
        with open(os.path.join(self.fake, "land-exit.txt"), "w") as f:
            f.write("1")
        self.statuses("none", "queued", "landed " + LANDED)
        r = self.land()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(self.calls("land")), 1)  # read back, never resent
        self.statuses("none")
        r = self.land()
        self.assertEqual(r.returncode, 1)
        self.assertIn("request failed and land-status is none; rerun the §7 gate check", r.stdout)
        self.assertEqual(len(self.calls("land")), 2)  # one per run

    def test_unknown_status_never_requests(self):
        for bad in (["garbage"], [2], ["landed abc"], ["failed"], ["none\nfailed already requested"], ["none\n"]):
            self.statuses(*bad)
            r = self.land()
            self.assertEqual(r.returncode, 1, bad)
            self.assertIn("blocked: land #7 @ aaaaaaa: unknown", r.stdout)
        self.assertEqual(self.calls("land"), [])

    def test_extra_lines_after_landed_not_success(self):
        self.statuses("landing", "landed %s\nfailed oops" % LANDED)
        r = self.land()
        self.assertEqual(r.returncode, 1)
        self.assertIn("blocked: land #7 @ aaaaaaa: unknown", r.stdout)
        self.assertNotIn("crew: landed", r.stdout)
        self.assertEqual(self.calls("land"), [])

    def test_in_flight_polled_not_requested(self):
        self.statuses("landing", "landed " + LANDED)
        self.assertEqual(self.land().returncode, 0)
        self.statuses("landed " + LANDED)
        self.assertEqual(self.land().returncode, 0)
        self.assertEqual(self.calls("land"), [])

    def test_status_reads_once(self):
        self.statuses("failed head moved", "none")
        r = self.land("status")
        self.assertEqual((r.returncode, r.stdout), (0, "failed head moved\n"))
        self.statuses(3)
        self.assertEqual(self.land("status").returncode, 1)
        self.assertEqual([c[0] for c in self.calls()], ["land-status", "land-status"])

    def test_sync_backend_and_short_head_refused(self):
        self.assertIn("--head must be a full", self.land(head="abc1234").stdout)
        with open(self.manifest) as f:
            text = f.read().split("\n[land]")[0]
        with open(self.manifest, "w") as f:
            f.write(text)
        r = self.land()
        self.assertEqual(r.returncode, 1)
        self.assertIn("land.mode is sync", r.stdout)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main(argv=[a for a in sys.argv if a != "--owner-transcript"])
