"""Offline repository fixer tests (#338): persistent fake GitHub state, collision guards, dry-run, idempotency,
closed milestones, pending invitations, Project scope failures and populated Status safety. No network or credentials.
"""
import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location("crew_repo", os.path.join(os.path.dirname(__file__), "crew-repo.py"))
repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo)


class Fixers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.values = {"repo.owner": "acme", "repo.name": "widgets", "runtime.name": "tmux",
                       "identities.builder.gh_user": "builder", "identities.reviewer.gh_user": "reviewer",
                       "paths.state_dir": self.tmp.name}
        self.labels = [{"name": "bug", "color": "ffffff", "description": "product label"}]
        self.milestones = []
        self.permission = "read"
        self.invitations = []
        self.projects = []
        self.linked = []
        self.options = ["Todo", "In Progress", "Done"]
        self.item_count = 0
        self.calls = []
        self.writes = []
        self.scope = True
        patch = mock.patch.object(repo.subprocess, "run", side_effect=self.gh)
        patch.start()
        self.addCleanup(patch.stop)

    def gh(self, args, **kwargs):
        a = args[1:]
        self.calls.append(a)
        output = None
        if a[:2] == ["auth", "token"]:
            return subprocess.CompletedProcess(args, 0, "fixture-token\n", "")
        self.assertEqual(kwargs["env"]["GH_TOKEN"], "fixture-token")
        if a[0] == "label":
            self.writes.append(a)
            label = {"name": a[2], "color": a[a.index("--color") + 1], "description": a[a.index("--description") + 1]}
            self.labels[:] = [x for x in self.labels if x["name"] != a[2]] + [label]
        elif a[0] == "api" and "-X" in a:
            self.writes.append(a)
            if a[2] == "PUT":
                self.invitations.append({"invitee": {"login": "reviewer"}})
            else:
                self.milestones.append({"title": a[-1].split("=", 1)[1], "state": "open"})
        elif a[:2] == ["api", "graphql"]:
            if not self.scope:
                return subprocess.CompletedProcess(args, 1, "", "scope missing")
            if "mutation(" in a[3]:
                self.writes.append(a)
                self.options = list(repo.STATUS)
            else:
                output = {"data": {"repository": {"projectsV2": {"nodes": [{"id": x} for x in self.linked], "pageInfo": {"hasNextPage": False}}}}}
        elif a[0] == "api":
            path = a[1]
            if "/labels" in path:
                output = [copy.deepcopy(self.labels)]
            elif "/invitations" in path:
                output = [self.invitations]
            elif "/milestones" in path:
                output = [self.milestones]
            else:
                output = {"permission": self.permission}
        elif a[0] == "project":
            if not self.scope:
                return subprocess.CompletedProcess(args, 1, "", "scope missing")
            if a[1] == "list":
                output = {"projects": self.projects, "totalCount": len(self.projects)}
            elif a[1] == "create":
                self.writes.append(a)
                self.projects.append({"id": "P1", "number": 1, "title": "widgets crew board", "closed": False})
            elif a[1] == "link":
                self.writes.append(a)
                self.linked.append("P" + a[2])
            elif a[1] == "field-list":
                output = {"fields": [{"id": "F1", "name": "Status", "options": [{"name": x} for x in self.options]}]}
            elif a[1] == "item-list":
                output = {"totalCount": self.item_count}
        else:
            self.fail("unexpected gh call " + repr(a))
        return subprocess.CompletedProcess(args, 0, json.dumps(output) if output is not None else "", "")

    def check(self, **kwargs):
        with mock.patch("builtins.print"):
            return {name: (status, detail, hint) for status, name, detail, hint in repo.checks(self.values, **kwargs)}

    def ready_labels(self):
        self.labels += [{"name": n, "color": c, "description": d} for n, c, d in repo.LABELS]

    def board(self):
        self.projects = [{"id": "P1", "number": 1, "title": "widgets crew board", "closed": False}]
        self.linked = ["P1"]

    def test_read_only_and_dry_run_never_write(self):
        for kwargs in ({}, {"dry_run": True}, {"fix": True, "dry_run": True}):
            with self.subTest(kwargs=kwargs):
                self.check(milestone="M1", **kwargs)
                self.assertEqual(self.writes, [])
                self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "acme__widgets")))

    def test_apply_then_rerun_is_idempotent_and_preserves_product_label(self):
        product = copy.deepcopy(self.labels[0])
        result = self.check(fix=True, milestone="M1")
        self.assertEqual(result["crew labels"][0], "ok")
        self.assertEqual(result["Project"][0], "ok")
        self.assertEqual(result["reviewer access"][0], "human")
        self.assertEqual(self.options, repo.STATUS)
        self.assertIn(product, self.labels)
        writes = len(self.writes)
        self.check(fix=True, milestone="M1")
        self.assertEqual(len(self.writes), writes)
        self.assertEqual(len(self.invitations), 1)

    def test_unknown_namespace_or_mismatch_blocks_all_label_writes(self):
        for name in ("crew:foreign", "crew:ready"):
            self.labels.append({"name": name, "color": "000000", "description": "foreign"})
            result = self.check(fix=True)
            self.assertEqual(result["crew labels"][0], "fail")
            self.assertFalse(any(a[0] == "label" for a in self.writes))
            self.labels.pop()

    def test_existing_install_repairs_mismatch(self):
        self.ready_labels()
        self.labels[1]["color"] = "000000"
        state = os.path.join(self.tmp.name, "acme__widgets")
        os.makedirs(state)
        with open(os.path.join(state, "install.json"), "w") as f:
            json.dump({"tag": "v2.1.0", "runtime": "tmux"}, f)
        self.check(fix=True)
        label_writes = [a for a in self.writes if a[0] == "label"]
        self.assertEqual(len(label_writes), 1)
        self.assertIn("--force", label_writes[0])

    def test_unrelated_install_record_does_not_allow_label_update(self):
        self.ready_labels()
        self.labels[1]["color"] = "000000"
        state = os.path.join(self.tmp.name, "acme__widgets")
        os.makedirs(state)
        with open(os.path.join(state, "install.json"), "w") as f:
            json.dump({"runtime": "grok-bot", "tag": "v2.1.0"}, f)
        self.assertEqual(self.check(fix=True)["crew labels"][0], "fail")
        self.assertFalse(any(a[0] == "label" for a in self.writes))

    def test_missing_milestone_needs_confirmation_and_closed_stays_frozen(self):
        self.assertEqual(self.check(fix=True)["milestone"][0], "human")
        self.milestones = [{"title": "M1", "state": "closed"}]
        self.assertEqual(self.check(fix=True, milestone="M1")["milestone"][0], "fail")
        self.assertEqual(self.milestones, [{"title": "M1", "state": "closed"}])
        self.assertEqual(self.check(fix=True, milestone="M2")["milestone"][0], "ok")

    def test_open_milestone_and_write_access_are_not_changed(self):
        self.permission = "maintain"
        self.milestones = [{"title": "M7 — Current milestone", "state": "open"}]
        result = self.check(fix=True, milestone="M8")
        self.assertEqual(result["reviewer access"][0], "ok")
        self.assertEqual(len(self.invitations), 0)
        self.assertEqual(len(self.milestones), 1)

    def test_populated_board_never_replaces_options(self):
        self.board()
        self.item_count = 1
        self.assertEqual(self.check(fix=True)["Project"][0], "human")
        self.assertFalse(any("graphql" in a and "mutation(" in " ".join(a) for a in self.writes))

    def test_project_scope_missing_is_human(self):
        self.scope = False
        self.assertEqual(self.check(fix=True)["Project"][0], "human")
        self.assertFalse(any(a[0] == "project" for a in self.writes))

    def test_ambiguous_projects_are_not_changed(self):
        self.board()
        self.projects.append(dict(self.projects[0], id="P2", number=2))
        self.assertEqual(self.check(fix=True)["Project"][0], "human")
        self.assertFalse(any(a[0] == "project" for a in self.writes))

    def test_named_existing_board_is_linked_without_duplicate_create(self):
        self.board()
        self.linked = []
        self.check(fix=True)
        self.assertEqual(len(self.projects), 1)
        self.assertEqual(self.linked, ["P1"])

    def test_new_collision_before_next_label_stops_writes(self):
        original = self.gh
        def race(args, **kwargs):
            result = original(args, **kwargs)
            if args[1:3] == ["label", "create"]:
                self.labels.append({"name": "crew:foreign", "color": "000000", "description": "foreign"})
            return result
        with mock.patch.object(repo.subprocess, "run", side_effect=race):
            self.assertEqual(self.check(fix=True)["crew labels"][0], "fail")
        self.assertEqual(len([a for a in self.writes if a[0] == "label"]), 1)


def evidence():
    fixture = Fixers()
    fixture.setUp()
    try:
        fixture.check(fix=True, dry_run=True, milestone="M1")
        fixture.assertEqual(fixture.writes, [])
        print("dry-run: 0 writes; no local state created")
        result = fixture.check(fix=True, milestone="M1")
        print("apply: %d crew labels; product bug label preserved" % sum(x["name"].startswith("crew:") for x in fixture.labels))
        print("milestone: M1 open; reviewer invitation pending (human acceptance)")
        print("Project: linked; Status = " + ", ".join(fixture.options))
        writes = len(fixture.writes)
        fixture.check(fix=True, milestone="M1")
        fixture.assertEqual(len(fixture.writes), writes)
        print("rerun: 0 additional writes")
        fixture.item_count = 1
        fixture.options = ["Todo", "In Progress", "Done"]
        fixture.assertEqual(fixture.check(fix=True)["Project"][0], "human")
        print("populated board: Status replacement blocked (human)")
        fixture.labels.append({"name": "crew:foreign", "color": "000000", "description": "foreign"})
        fixture.assertEqual(fixture.check(fix=True)["crew labels"][0], "fail")
        fixture.assertEqual(len(fixture.writes), writes)
        print("namespace collision: fail; 0 additional writes")
    finally:
        path = fixture.tmp.name
        fixture.doCleanups()
        assert not os.path.exists(path)
        print("cleanup: temporary fixture deleted; no live GitHub mutations")


if __name__ == "__main__":
    if sys.argv[1:] == ["--evidence"]:
        evidence()
    else:
        unittest.main()
