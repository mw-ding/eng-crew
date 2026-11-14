"""Shared team leads and repo-bound worker lifecycle (#1858, docs/specs/team.md §9.3-§9.4), through the shipped
`mdstack up --team`, `lead handoff`, `spawn`, `kill` and `restart` entry points. Two disposable repos share issue 42,
pass and round under one team file; a fake gh logs every backend call and fake tmux/ps answer panes. Each refusal
pairs with a valid same-repo control. No model or network calls. Run in CI.
"""
import argparse
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, CREW, FAKE_PS, FAKE_TMUX_PANES, INPUTS, SECRET

SESSION = "crew-team-eng"
GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
open(os.environ["FAKE_GH_LOG"], "a").write(json.dumps(args) + "\\n")
if args[:1] == ["api"]:
    sys.exit(1)  # a control item never reads: its repo is read-only
repo = args[args.index("-R") + 1] if "-R" in args else ""
if args[:2] in (["issue", "view"], ["pr", "view"]):
    print(json.dumps({"url": "https://github.com/%%s/%%s/%%s" %% (repo, "issues" if args[0] == "issue" else "pull", args[2]),
                      "labels": [], "comments": [], "state": "OPEN", "closingIssuesReferences": [{"number": 42}],
                      "body": "", "headRefOid": "2" * 40, "isDraft": False}))
else:
    print(%r)
""" % SECRET
LEAD = "Lead the pool for <owner>/<repo>; never build.\n"


class TeamBase(Base):
    def git(self, *args, cwd):
        r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t", *args], cwd=cwd, capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def setUp(self):
        super().setUp()
        bindir = os.path.join(self.tmp, "bin")
        os.rename(os.path.join(bindir, "tmux"), os.path.join(bindir, "tmux-base"))
        for name, text in [("tmux", FAKE_TMUX_PANES), ("ps", FAKE_PS), ("gh", GH)]:
            with open(os.path.join(bindir, name), "w") as f:
                f.write(text)
            os.chmod(os.path.join(bindir, name), 0o755)
        self.panes, self.gh_log = os.path.join(self.tmp, "panes.json"), os.path.join(self.tmp, "gh.log")
        self.env.update(FAKE_PANES=self.panes, FAKE_PS=os.path.join(self.tmp, "ps.json"), FAKE_GH_LOG=self.gh_log,
                        GH_TOKEN=SECRET)
        self.checkouts = {}
        for repo in ("alpha", "beta"):
            origin, work = os.path.join(self.tmp, repo + ".git"), os.path.join(self.tmp, repo)
            os.makedirs(work)
            self.git("init", "-q", "--bare", "-b", "main", origin, cwd=self.tmp)
            self.git("init", "-q", "-b", "main", cwd=work)
            self.git("remote", "add", "origin", origin, cwd=work)
            self.git("commit", "-q", "--allow-empty", "-m", "base", cwd=work)
            self.git("push", "-q", "origin", "main", cwd=work)
            self.checkouts[repo] = work
        self.inputs = os.path.join(self.tmp, "inputs")
        shutil.copytree(INPUTS, self.inputs)
        for role in ("builder", "reviewer"):
            with open(os.path.join(self.inputs, "runtimes", "tmux", role + "-lead.md"), "w") as f:
                f.write(LEAD)
        self.team = os.path.join(self.project_dir, "teams", "eng.toml")
        os.makedirs(os.path.dirname(self.team))
        self.write_team()
        self.root = os.path.join(self.tmp, "state", "eng")
        self.states = {r: os.path.join(self.root, "example__" + r) for r in ("alpha", "beta")}
        self.refs = {"alpha": self.team + "#a", "beta": self.team + "#b"}
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        self.mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(self.mod)

    def write_team(self, extra_a=""):
        with open(self.team, "w") as f:
            f.write('[team]\npersonas = { builder = "Ben", reviewer = "Vera" }\n'
                    'accounts = { all = "acme-bot", reviewer = "acme-reviewer" }\n'
                    '[team.runtime]\nname = "tmux"\ninstance = "local"\n[team.identities]\nowners = ["acme-owner"]\n'
                    '[team.paths]\nstate_dir = "%s"\nworktree_root = "%s"\ntoolchain_bin = "/opt/node/bin"\n'
                    '[repos.a]\nrepo = "example/alpha"\ncheckout = "%s"\n%s'
                    '[repos.b]\nrepo = "example/beta"\ncheckout = "%s"\n'
                    % (os.path.join(self.tmp, "state"), os.path.join(self.tmp, "wt"), self.checkouts["alpha"], extra_a,
                       self.checkouts["beta"]))

    def up(self):
        return self.crew("up", "--team", self.team, "--inputs", self.inputs)

    def spawn(self, repo, *args):
        return self.crew("spawn", "builder", *args, "--project", self.refs[repo], "--timeout", "1")

    def record(self, repo, name):
        with open(os.path.join(self.states[repo], "runs", name + ".json")) as f:
            return json.load(f)

    def tmux_state(self):
        with open(self.state_file) as f:
            return json.load(f)

    def allocations(self):
        d = os.path.join(self.root, "allocations")
        return sorted(n for n in os.listdir(d) if n.endswith(".json")) if os.path.isdir(d) else []

    def new_windows(self):
        return [c[c.index("-n") + 1] for c in self.calls() if c[0] == "new-window"]

    def snapshot(self, repo):
        """B's records, allocation and window as files and the session sees them."""
        state = self.states[repo]
        files = {}
        for d in ("runs", "claims", "inbox", "status"):
            for n in sorted(os.listdir(os.path.join(state, d))) if os.path.isdir(os.path.join(state, d)) else []:
                with open(os.path.join(state, d, n), "rb") as f:
                    files[d + "/" + n] = f.read()
        windows = {i: n for i, n in self.tmux_state()[SESSION].items() if repo in n}
        mine = []
        for n in self.allocations():
            with open(os.path.join(self.root, "allocations", n)) as f:
                rec = json.load(f)
            mine += [rec] if rec["repo"] == "example/" + repo else []
        return files, windows, mine


class TeamLeads(TeamBase):
    def test_team_up_starts_one_lead_per_pool_and_a_repeat_starts_none(self):
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(self.new_windows()), ["ben-lead", "vera-lead"])
        with open(os.path.join(self.root, "team.json")) as f:
            team = json.load(f)
        self.assertEqual(sorted(team["repos"]), ["example/alpha", "example/beta"])
        self.assertEqual(team["repos"]["example/beta"]["state"], self.states["beta"])
        with open(os.path.join(self.root, "leads", "builder.json")) as f:
            self.assertEqual(json.load(f)["name"], "ben-lead")
        self.assertFalse(os.path.exists(os.path.join(self.states["alpha"], "leads", "builder.json")))
        call = next(c for c in self.calls() if c[0] == "new-window" and "ben-lead" in c)
        env = dict(call[i + 1].split("=", 1) for i, a in enumerate(call) if a == "-e")
        self.assertEqual((env["CREW_STATE"], env["CREW_PROJECT"], env["CREW_TEAM"], env["CREW_STATUS"]),
                         (self.root, self.team, self.team, os.path.join(self.root, "status", "ben-lead.status")))
        with open(env["CREW_BRIEF"]) as f:
            brief = f.read()
        for repo, sel in (("alpha", "a"), ("beta", "b")):  # each repo's own brief and project, never the first's
            self.assertIn("| example/%s | `%s#%s` | `%s` | `%s` |" % (repo, os.path.realpath(self.team), sel,
                          self.states[repo], os.path.join(self.states[repo], "render", "runtime", "builder-lead.md")),
                          brief)
        r = self.up()  # idempotent: the live leads are found, none started
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("already running", r.stdout)
        self.assertEqual(sorted(self.new_windows()), ["ben-lead", "vera-lead"])

    def test_a_ownership_refusal_leaves_the_lead_serving_b(self):
        self.write_team(extra_a="control_item = 5\n")  # its control record never reads: A is read-only
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ownership: read-only; refusing start", r.stdout)
        self.assertEqual(sorted(self.new_windows()), ["ben-lead", "vera-lead"])  # started through B
        with mock.patch.dict(os.environ, self.env):
            refused = self.mod.commands()["lead"].handoff(argparse.Namespace(
                project=self.refs["alpha"], org_profile=None, timeout=1), "builder", "build", ["#42"])
            served = self.mod.commands()["lead"].handoff(argparse.Namespace(
                project=self.refs["beta"], org_profile=None, timeout=1), "builder", "build", ["#42"])
        self.assertEqual((refused, served), (1, 0))  # control: B's identical handoff is delivered
        with open(os.path.join(self.root, "inbox", "ben-lead.jsonl")) as f:
            self.assertEqual([m["context"]["repo"] for m in map(json.loads, f)], ["example/beta"])

    def test_lead_messages_and_waits_stay_with_their_repo(self):
        self.assertEqual(self.up().returncode, 0)
        lead = self.mod.commands()["lead"]
        with mock.patch.dict(os.environ, self.env):
            for repo in ("alpha", "beta", "alpha"):  # A's repeat is the same pending handoff
                lead.handoff(argparse.Namespace(project=self.refs[repo], org_profile=None, timeout=1),
                             "builder", "build", ["#42"])
        with open(os.path.join(self.root, "inbox", "ben-lead.jsonl")) as f:
            inbox = [json.loads(line) for line in f]
        self.assertEqual([(m["refs"], m["context"]["repo"], m["context"]["project"].rsplit("#", 1)[1]) for m in inbox],
                         [(["#42"], "example/alpha", "a"), (["#42"], "example/beta", "b")])
        a, b = inbox[0]["id"], inbox[1]["id"]
        self.assertEqual([m["id"] for m in lead.pending(self.states["alpha"], "ben-lead")], [a])
        self.assertEqual([m["id"] for m in lead.pending(self.states["beta"], "ben-lead")], [b])
        self.assertEqual(len(lead.pending(self.root, "ben-lead")), 2)
        with open(os.path.join(self.root, "status", "ben-lead.status"), "w") as f:
            f.write("ack: %s\nack: %s\nwaiting: #42 hold id=%s\nwaiting: #42 hold id=%s\n" % (a, b, a, b))
        for state in self.states.values():
            with open(os.path.join(state, "poll-state.json"), "w") as f:
                json.dump({"observed": {"42": {"state": "OPEN", "head": "1" * 40, "ci": "pending"}}}, f)
        self.assertEqual([lead.actionable(s, "ben-lead") for s in self.states.values()], [[], []])  # parked
        self.assertEqual([lead.actionable(s, "ben-lead") for s in self.states.values()], [[], []])  # unchanged: no nudge
        with open(os.path.join(self.states["alpha"], "poll-state.json"), "w") as f:  # only A's state moves
            json.dump({"observed": {"42": {"state": "OPEN", "head": "2" * 40, "ci": "pending"}}}, f)
        self.assertEqual([m["id"] for m in lead.actionable(self.states["alpha"], "ben-lead")], [a])
        self.assertEqual(lead.actionable(self.states["beta"], "ben-lead"), [])

    def test_reviewer_pool_settles_only_its_repos_same_id_pass(self):
        self.assertEqual(self.up().returncode, 0)
        lead, head = self.mod.commands()["lead"], "1" * 40
        with mock.patch.dict(os.environ, self.env):
            for repo in ("alpha", "beta"):  # change 7, head, pass and round equal in both repos
                lead.handoff(argparse.Namespace(project=self.refs[repo], org_profile=None, timeout=1),
                             "reviewer", "review", ["#7", head, "1"])
        with open(os.path.join(self.root, "inbox", "vera-lead.jsonl")) as f:
            a, b = [json.loads(line)["id"] for line in f]
        r = self.crew("reviewer-pool", "--project", self.refs["alpha"], CREW_POOL="reviewer")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.root, "status", "vera-lead.status")) as f:
            self.assertEqual(f.read(), "ack: %s\ndone: %s\n" % (a, a))  # the live head moved: A's settles, at the root
        self.assertFalse(os.path.exists(os.path.join(self.states["alpha"], "status", "vera-lead.status")))
        self.assertEqual([m["id"] for m in lead.pending(self.states["beta"], "vera-lead")], [b])


class TeamWorkers(TeamBase):
    def setUp(self):
        super().setUp()
        r = self.up()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for repo in ("alpha", "beta"):
            r = self.spawn(repo, "--issue", "42", "--handoff", "h-" + repo)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.a, self.b = "ben-42-example__alpha", "ben-42-example__beta"

    def test_same_issue_in_two_repos_runs_in_distinct_windows_runs_and_worktrees(self):
        a, b = self.record("alpha", self.a), self.record("beta", self.b)
        self.assertNotEqual(a["index"], b["index"])
        self.assertNotEqual(a["run_id"], b["run_id"])
        for rec, repo, sel in ((a, "alpha", "a"), (b, "beta", "b")):
            self.assertEqual(rec["worktree"], os.path.join(self.tmp, "wt", "example__" + repo, rec["run_id"]))
            self.assertTrue(os.path.isdir(rec["worktree"]))
            self.assertEqual((rec["context"]["repo"], rec["context"]["item"], rec["context"]["change"],
                              rec["context"]["head"], rec["context"]["pass"], rec["context"]["round"]),
                             ("example/" + repo, 42, None, None, "build", 1))
            self.assertEqual((rec["checkout"], rec["repo"], rec["handoff"], rec["args"]["tier"]),
                             (os.path.realpath(self.checkouts[repo]),) * 2 + ("h-" + repo, "default"))
            self.assertEqual(rec["claim"], os.path.join(self.states[repo], "claims", "builder-issue42"))
            self.assertTrue(os.path.exists(rec["claim"]))
        self.assertEqual(self.allocations(), sorted([a["run_id"] + ".json", b["run_id"] + ".json"]))
        with open(os.path.join(self.root, "allocations", a["run_id"] + ".json")) as f:
            self.assertEqual((json.load(f)["repo"]), "example/alpha")

    def test_kill_and_restart_of_a_leave_b_untouched(self):
        before = self.snapshot("beta")
        r = self.crew("kill", self.a, "--project", self.refs["alpha"], CREW_POOL="builder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.states["alpha"], "runs", self.a + ".json")))
        self.assertEqual(self.snapshot("beta"), before)
        self.assertTrue(os.path.isdir(self.record("beta", self.b)["worktree"]))
        self.assertEqual(self.spawn("alpha", "--issue", "42").returncode, 0)
        first = self.record("alpha", self.a)
        session = self.tmux_state()
        session[SESSION].pop(str(first["index"]))  # A's window is gone: restart spawns it fresh
        with open(self.state_file, "w") as f:
            json.dump(session, f)
        before = self.snapshot("beta")
        r = self.crew("restart", self.a, "--project", self.refs["alpha"], "--timeout", "1", CREW_POOL="builder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        second = self.record("alpha", self.a)
        self.assertNotEqual(second["run_id"], first["run_id"])  # a new execution generation
        self.assertEqual(self.snapshot("beta")[:2], before[:2])
        self.assertIn(self.record("beta", self.b)["run_id"] + ".json", self.allocations())
        self.assertNotIn(first["run_id"] + ".json", self.allocations())

    def test_restart_keeps_the_durable_handoff_clean_and_in_place(self):
        for repo, name, dirty in (("alpha", self.a, False), ("beta", self.b, True)):  # fresh spawn; own worktree
            first = self.record(repo, name)
            if dirty:
                with open(os.path.join(first["worktree"], "wip.txt"), "w") as f:
                    f.write("unlanded\n")
            session = self.tmux_state()
            session[SESSION].pop(str(first["index"]))
            with open(self.state_file, "w") as f:
                json.dump(session, f)
            r = self.crew("restart", name, "--project", self.refs[repo], "--timeout", "1", CREW_POOL="builder")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("in its worktree" if dirty else "started " + name, r.stdout)
            second = self.record(repo, name)
            self.assertEqual(second["handoff"], "h-" + repo)
            self.assertNotEqual(second["run_id"], first["run_id"])  # a new execution generation, same handoff

    def test_kill_refuses_a_successor_process_in_the_same_pane(self):
        rec = self.record("alpha", self.a)
        target = "%s:%s" % (SESSION, rec["index"])
        before, b = self.snapshot("alpha"), self.snapshot("beta")
        for pane, ps in (({"pid": "9999999"}, {}),  # the pane handle stays, another process runs in it
                         ({}, {"start": {rec["pane_pid"]: "Sat Oct 31 11:00:00 2026"}})):  # same pid, reused
            with open(self.panes, "w") as f:
                json.dump({target: dict({"id": rec["pane_id"]}, **pane)}, f)
            with open(os.path.join(self.tmp, "ps.json"), "w") as f:
                json.dump(ps, f)
            r = self.crew("kill", self.a, "--project", self.refs["alpha"], CREW_POOL="builder")
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("its pane is not this repo's run", r.stdout)
            self.assertEqual((self.snapshot("alpha"), self.snapshot("beta")), (before, b))
        os.remove(self.panes)  # control: the recorded process again, kill stops it
        os.remove(os.path.join(self.tmp, "ps.json"))
        r = self.crew("kill", self.a, "--project", self.refs["alpha"], CREW_POOL="builder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.states["alpha"], "runs", self.a + ".json")))

    def test_restart_with_unlanded_work_refuses_a_successor_in_the_same_pane(self):
        rec = self.record("alpha", self.a)
        with open(os.path.join(rec["worktree"], "wip.txt"), "w") as f:
            f.write("unlanded\n")
        target = "%s:%s" % (SESSION, rec["index"])
        before, b, alloc = self.snapshot("alpha"), self.snapshot("beta"), self.allocations()
        for pane, ps in (({"pid": "9999999"}, {}),  # another process in the run's pane
                         ({}, {"start": {rec["pane_pid"]: "Sat Oct 31 11:00:00 2026"}})):  # same pid, reused
            with open(self.panes, "w") as f:
                json.dump({target: dict({"id": rec["pane_id"]}, **pane)}, f)
            with open(os.path.join(self.tmp, "ps.json"), "w") as f:
                json.dump(ps, f)
            calls = len(self.calls())
            r = self.crew("restart", self.a, "--project", self.refs["alpha"], "--timeout", "1", CREW_POOL="builder")
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("is not this repo's run", r.stdout)
            self.assertEqual([c for c in self.calls()[calls:] if c[0] in ("kill-window", "new-window")], [])
            self.assertEqual((self.snapshot("alpha"), self.snapshot("beta"), self.allocations()), (before, b, alloc))

    def test_restart_with_unlanded_work_relaunches_its_own_dead_pane(self):
        rec = self.record("alpha", self.a)
        with open(os.path.join(rec["worktree"], "wip.txt"), "w") as f:
            f.write("unlanded\n")
        with open(self.panes, "w") as f:  # control: the run's own pane, its process exited
            json.dump({"%s:%s" % (SESSION, rec["index"]): {"id": rec["pane_id"], "dead": "1"}}, f)
        calls = len(self.calls())
        r = self.crew("restart", self.a, "--project", self.refs["alpha"], "--timeout", "1", CREW_POOL="builder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("in its worktree", r.stdout)
        self.assertIn("kill-window", [c[0] for c in self.calls()[calls:]])
        self.assertNotEqual(self.record("alpha", self.a)["run_id"], rec["run_id"])

    def test_kill_stops_a_dead_pane_of_the_run(self):
        rec = self.record("alpha", self.a)
        with open(self.panes, "w") as f:  # its process exited: the pane keeps handle and pid, the start time is gone
            json.dump({"%s:%s" % (SESSION, rec["index"]): {"id": rec["pane_id"], "dead": "1"}}, f)
        with open(os.path.join(self.tmp, "ps.json"), "w") as f:
            json.dump({"start": {rec["pane_pid"]: ""}}, f)
        r = self.crew("kill", self.a, "--project", self.refs["alpha"], CREW_POOL="builder")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.states["alpha"], "runs", self.a + ".json")))

    def test_kill_refuses_a_window_whose_pane_is_not_the_run(self):
        rec = self.record("alpha", self.a)
        rec["pane_id"] = "%999"  # the window now shows another process: a successor, not this run
        with open(os.path.join(self.states["alpha"], "runs", self.a + ".json"), "w") as f:
            json.dump(rec, f)
        before, b = self.snapshot("alpha"), self.snapshot("beta")
        r = self.crew("kill", self.a, "--project", self.refs["alpha"], CREW_POOL="builder")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("its pane is not this repo's run", r.stdout)
        self.assertEqual((self.snapshot("alpha"), self.snapshot("beta")), (before, b))

    def test_cleanup_removes_only_this_repos_worktrees(self):
        a, b = self.record("alpha", self.a), self.record("beta", self.b)
        with mock.patch.dict(os.environ, self.env):
            values, _, _ = self.mod.profile(argparse.Namespace(project=self.refs["beta"], org_profile=None))
            mine = self.mod.own_worktree(values, b["worktree"], self.root)
            foreign = self.mod.own_worktree(values, a["worktree"], self.root)
        self.assertEqual((mine, foreign), (True, False))
        rec = dict(b, worktree=a["worktree"])  # a B record naming A's tree: kill keeps A's worktree
        with open(os.path.join(self.states["beta"], "runs", self.b + ".json"), "w") as f:
            json.dump(rec, f)
        self.crew("kill", self.b, "--project", self.refs["beta"], CREW_POOL="builder")
        self.assertTrue(os.path.isdir(a["worktree"]))
        self.assertTrue(os.path.exists(os.path.join(self.states["alpha"], "runs", self.a + ".json")))

    def test_another_repos_release_never_frees_a_slot(self):
        a = self.record("alpha", self.a)
        with mock.patch.dict(os.environ, self.env):
            self.assertFalse(self.mod.team_module.release(self.root, a["run_id"], "example/beta"))
            self.assertIn(a["run_id"] + ".json", self.allocations())
            self.assertTrue(self.mod.team_module.release(self.root, a["run_id"], "example/alpha"))
        self.assertNotIn(a["run_id"] + ".json", self.allocations())


class RepoTags(TeamBase):
    def test_valid_repos_whose_names_differ_only_in_punctuation_get_distinct_windows(self):
        with open(self.team) as f:
            text = f.read()
        with open(self.team, "w") as f:
            f.write(text.replace('"example/alpha"', '"example/alpha.foo"').replace('"example/beta"', '"example/alpha-foo"'))
        self.assertEqual(self.up().returncode, 0)
        a, b = self.spawn("alpha", "--issue", "42"), self.spawn("beta", "--issue", "42")
        self.assertEqual((a.returncode, b.returncode), (0, 0), a.stdout + b.stdout)
        self.assertEqual(sorted(n for n in self.new_windows() if n.startswith("ben-42")),
                         ["ben-42-example__alpha-foo", "ben-42-example__alpha_2efoo"])

    def test_tag_is_one_to_one_and_keeps_plain_names(self):
        tag = self.mod.team_module.tag
        self.assertEqual(tag("Example/Alpha"), "example__alpha")
        repos = ["example/alpha.foo", "example/alpha-foo", "example/alpha_foo", "example/alpha__foo", "ex/ample__a",
                 "ex__ample/a", "example/alpha_2efoo"]
        tags = [tag(r) for r in repos]
        self.assertEqual(len(set(tags)), len(repos), tags)
        for t in tags:
            self.assertRegex(t, r"^[a-z0-9_-]+$")


class OneRepo(Base):
    def test_a_one_repo_profile_keeps_its_names_and_lead_home(self):
        with mock.patch.dict(os.environ, self.env):
            loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
            mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
            loader.exec_module(mod)
            values, _, state = mod.profile(argparse.Namespace(project=self.project, org_profile=None))
        self.assertEqual((mod.team_name(values, "ben-42"), mod.lead_state(state), mod.team_module.root(state)),
                         ("ben-42", state, None))
        self.assertEqual(mod.commands()["lead"].record_path(state, "builder"),
                         os.path.join(state, "leads", "builder.json"))


if __name__ == "__main__":
    unittest.main()
