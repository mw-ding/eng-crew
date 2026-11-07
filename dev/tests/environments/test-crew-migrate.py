"""Tests for mdstack migrate (#1178); fixtures in crew_testlib.py (stdlib only).

Covers, against a fixture crew with a real builder worktree: the preview is blocked while the old session runs,
and after `mdstack down --preserve` it lists every mapping (the old home, also the unchanged checkout, keeps its
whole-path references and moves the paths under it), the state move, the registered worktree move, an unregistered
directory kept, the old process identities archived, the operational rewrites, the settings copy and the owner's
memory and trust steps, writing nothing; a destination that exists blocks; profiles naming different repos are
refused; on apply, an unrelated compound hook keeps its shell text while the guard is re-quoted, a hook citing an
old path whose new path needs quoting blocks before anything moves, and an interrupted apply's quoted rollback
commands run and restore the state. Run in CI.
"""
import json
import os
import shlex
import subprocess
import unittest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import KillLandedBase, PROFILE


def tree(root):
    """Every file's bytes under root, but the fake tmux's own call log and state."""
    out = {}
    for d, _, names in os.walk(root):
        for n in (n for n in names if not n.startswith("tmux.")):
            p = os.path.join(d, n)
            if os.path.isfile(p) and not os.path.islink(p):
                with open(p, "rb") as f:
                    out[p] = f.read()
    return out


class MigrateBase(KillLandedBase):
    def setUp(self):
        super().setUp()
        self.wt = self.builder()
        with open(os.path.join(self.wt, "wip.txt"), "w") as f:
            f.write("x\n")
        self.old_wt_root = os.path.join(self.tmp, "state", "wt")
        os.makedirs(os.path.join(self.old_wt_root, "orphan-dir"))
        self.root = os.path.join(self.tmp, "home root")
        self.new_home = os.path.join(self.root, "crew-home")
        os.makedirs(self.new_home)
        self.new_project = os.path.join(self.new_home, "crew.toml")
        text = PROFILE.format(runtime="tmux", engine="claude-code", state="x").replace(
            'state_dir = "x"\nworktree_root = "x/wt"\n',
            'root = "%s"\ncheckout = "%s"\nstate_dir = ".crew/state"\nworktree_root = ".crew/runs/widgets"\n'
            % (self.root, self.project_dir))
        with open(self.new_project, "w") as f:
            f.write(text + '[runtime.options.notes]\nbuilder = ["%s/runs/policy.md"]\n' % self.state)
        self.new_state = os.path.join(self.root, ".crew", "state", "acme__widgets")
        self.new_wt_root = os.path.join(self.root, ".crew", "runs", "widgets")

    def migrate(self, *args):
        return self.crew("migrate", "--project", self.project, "--to", self.new_project, *args)

    def stop(self):
        r = self.crew("down", "--project", self.project, "--preserve")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.put("leads/builder.json", json.dumps({"name": "ben-lead", "role": "builder-lead", "index": 2}))


class Preview(MigrateBase):
    def test_blocked_while_the_session_runs(self):
        r = self.migrate()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("blocked: session crew-acme-widgets is running; run mdstack down --preserve", r.stdout)

    def test_preview_lists_every_operation_and_writes_nothing(self):
        self.stop()
        before = tree(self.tmp)
        r = self.migrate()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        self.assertIn("map %s -> %s" % (self.project, self.new_project), lines)
        self.assertIn("map %s -> %s" % (self.state, self.new_state), lines)
        self.assertIn("map %s -> %s" % (self.old_wt_root, self.new_wt_root), lines)
        # The old home is also the unchanged checkout: a whole-path reference (a run's repo) stays, paths under it move.
        self.assertIn("map %s -> %s (under it: %s)" % (self.project_dir, self.project_dir, self.new_home), lines)
        self.assertIn("move %s -> %s" % (self.state, self.new_state), lines)
        name = os.path.basename(self.wt)
        self.assertIn("worktree-move %s -> %s" % (self.wt, os.path.join(self.new_wt_root, name)), lines)
        self.assertIn("keep %s (not a registered worktree of %s)" % (
            os.path.join(self.old_wt_root, "orphan-dir"), self.project_dir), lines)
        self.assertIn("archive %s" % os.path.join(self.state, "leads", "builder.json"), lines)
        self.assertTrue(any(line.startswith("rewrite %s (" % os.path.join(self.state, "runs", "ben-7.json"))
                            for line in lines), lines)
        self.assertIn("rewrite %s (1 refs)" % self.new_project, lines)
        self.assertIn("copy %s -> %s" % (os.path.join(self.project_dir, ".claude", "settings.local.json"),
                                         os.path.join(self.new_home, ".claude", "settings.local.json")), lines)
        self.assertTrue(any(line.startswith("owner: Claude Code memory for %s" % self.project_dir) for line in lines))
        self.assertFalse([line for line in lines if line.startswith("blocked:")])
        self.assertEqual(tree(self.tmp), before)

    def test_existing_destination_blocks(self):
        self.stop()
        os.makedirs(os.path.join(self.new_wt_root, os.path.basename(self.wt)))
        r = self.migrate()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("blocked: destination exists: %s" % os.path.join(self.new_wt_root, os.path.basename(self.wt)),
                      r.stdout)

    def test_different_repos_refused(self):
        with open(self.new_project) as f:
            text = f.read()
        with open(self.new_project, "w") as f:
            f.write(text.replace('name = "widgets"', 'name = "gadgets"'))
        r = self.migrate()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("name different repos", r.stdout)



class Apply(MigrateBase):
    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_apply_moves_rewrites_and_reconciles(self):
        self.stop()
        status = "ack: m1\nnote: %s\ndone: #7 #9 %s\n" % (self.wt, "a" * 40)
        self.put("status/ben-7.status", status)
        self.put("inbox/ben-7.jsonl", json.dumps({"id": "m1", "kind": "fix", "refs": [self.wt]}) + "\n")
        self.put("wake/watch-state.json", json.dumps({"offsets": {"ben-7": len(status.encode())}, "keys": {}}))
        r = self.migrate("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(self.state))
        name = os.path.basename(self.wt)
        new_wt = os.path.join(self.new_wt_root, name)
        self.assertTrue(os.path.isfile(os.path.join(new_wt, "wip.txt")))
        self.assertIn(os.path.realpath(new_wt), [os.path.realpath(line[9:]) for line in self.git(
            "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")])
        rec = json.loads(self.read(os.path.join(self.new_state, "runs", "ben-7.json")))
        self.assertEqual((rec["worktree"], os.path.realpath(rec["repo"]), rec["claim"]),
                         (new_wt, os.path.realpath(self.project_dir), os.path.join(self.new_state, "claims", "builder-issue7")))
        self.assertNotIn(self.state, self.read(os.path.join(self.new_state, "runs", "ben-7.brief.md")))
        new_status = self.read(os.path.join(self.new_state, "status", "ben-7.status"))
        self.assertEqual(new_status, status.replace(self.wt, new_wt))
        seen = json.loads(self.read(os.path.join(self.new_state, "wake", "watch-state.json")))
        self.assertEqual(seen["offsets"]["ben-7"], len(new_status.encode()))
        msg = json.loads(self.read(os.path.join(self.new_state, "inbox", "ben-7.jsonl")))
        self.assertEqual((msg["id"], msg["refs"]), ("m1", [new_wt]))
        self.assertIn('builder = ["%s/runs/policy.md"]' % self.new_state, self.read(self.new_project))
        self.assertIn('checkout = "%s"' % self.project_dir, self.read(self.new_project))
        hooks = json.loads(self.read(os.path.join(self.new_home, ".claude", "settings.local.json")))["hooks"]["Stop"]
        self.assertEqual([shlex.split(h["command"])[-1] for e in hooks for h in e["hooks"]], [self.new_state])
        self.assertFalse(os.path.exists(os.path.join(self.new_state, "leads", "builder.json")))
        work = [line.split(" in ", 1)[1] for line in r.stdout.splitlines() if line.startswith("crew migrate: applied")][0]
        self.assertTrue(os.path.isfile(os.path.join(work, "identities", "leads", "builder.json")))
        self.assertEqual(self.read(os.path.join(work, "originals", "status", "ben-7.status")), status)
        mapped = json.loads(self.read(os.path.join(work, "map.json")))
        self.assertEqual(mapped["kept"], [os.path.join(self.old_wt_root, "orphan-dir")])
        self.assertTrue(os.path.isdir(os.path.join(self.old_wt_root, "orphan-dir")))
        self.assertIn("next: mdstack up --project %s --coordinator-only" % self.new_project, r.stdout)
        r = self.crew("migrate", "--project", self.new_project, "--to", self.new_project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse([line for line in r.stdout.splitlines() if line.startswith(("map ", "rewrite ", "move "))])

    def settings_hooks(self, *commands):
        path = os.path.join(self.project_dir, ".claude", "settings.local.json")
        settings = json.loads(self.read(path))
        settings["hooks"]["Stop"][0]["hooks"] += [{"type": "command", "command": c} for c in commands]
        with open(path, "w") as f:
            json.dump(settings, f)

    def test_unrelated_hook_keeps_its_shell_text_and_the_guard_is_requoted(self):  # r1 P1
        self.settings_hooks("printf first && printf second > /dev/null")
        self.stop()
        r = self.migrate("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        hooks = json.loads(self.read(os.path.join(self.new_home, ".claude", "settings.local.json")))["hooks"]["Stop"]
        commands = [h["command"] for e in hooks for h in e["hooks"]]
        self.assertEqual(commands[-1], "printf first && printf second > /dev/null")
        self.assertEqual(shlex.split(commands[0])[2:], ["guard", "--state", self.new_state])

    def test_hook_citing_an_old_path_that_needs_quoting_blocks(self):  # r1 P1: refuse before moving anything
        self.settings_hooks("cat %s/runs/policy.md && true" % self.state)
        self.stop()
        r = self.migrate("--apply")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("needs shell quoting; edit it by hand first", r.stdout)
        self.assertTrue(os.path.isdir(self.state))
        self.assertFalse(os.path.exists(self.new_state))

    def test_interrupted_apply_reports_completed_steps_and_rollback(self):
        self.stop()
        self.git("worktree", "lock", self.wt)
        r = self.migrate("--apply")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("crew: migrate --apply failed: git worktree move", r.stdout)
        self.assertIn("completed: move %s -> %s" % (self.state, self.new_state), r.stdout)
        rollback = "mv %s %s" % (shlex.quote(self.new_state), shlex.quote(self.state))  # r1 P2: quoted, runnable
        self.assertIn("rollback: " + rollback, r.stdout)
        journals = [os.path.join(d, "journal.json") for d, _, n in os.walk(self.new_state) if "journal.json" in n]
        self.assertEqual(len(journals), 1)
        self.assertEqual(json.loads(self.read(journals[0]))[0]["op"], "move %s -> %s" % (self.state, self.new_state))
        self.assertTrue(os.path.isdir(self.wt))
        for line in [line for line in r.stdout.splitlines() if line.startswith("rollback: ")]:
            run = subprocess.run(["sh", "-c", line[len("rollback: "):]], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.state, "runs", "ben-7.json")))
        self.assertFalse(os.path.exists(self.new_state))

    def test_apply_refused_while_blocked(self):
        r = self.migrate("--apply")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("refusing migrate --apply: blocked", r.stdout)
        self.assertTrue(os.path.isdir(self.state))
        self.assertFalse(os.path.exists(self.new_state))


class Rename(MigrateBase):
    """--rename-to (#1234): the repo-keyed names and paths; the GitHub rename stays the owner's step."""

    def setUp(self):
        super().setUp()
        self.renamed_state = os.path.join(self.tmp, "state", "acme__gadgets")
        with open(self.project, "a") as f:
            f.write('[runtime.options.notes]\nbuilder = ["%s/runs/policy.md"]\n[triage]\nrepos = ["acme/widgets"]\n'
                    % self.state)

    def rename(self, *args):
        return self.crew("migrate", "--project", self.project, "--rename-to", "acme/gadgets", *args)

    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_preview_lists_every_repo_keyed_name_and_writes_nothing(self):
        self.stop()
        before = tree(self.tmp)
        r = self.rename()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        settings = os.path.join(self.project_dir, ".claude", "settings.local.json")
        for line in ("map %s -> %s" % (self.state, self.renamed_state),
                     "name repo acme/widgets -> acme/gadgets",
                     "name session crew-acme-widgets -> crew-acme-gadgets (from the next mdstack up)",
                     "move %s -> %s" % (self.state, self.renamed_state),
                     "rewrite %s (3 refs)" % self.project,  # notes path, [repo] name, triage slug
                     "rewrite %s (1 refs)" % settings,
                     "owner: before --apply, rename acme/widgets to acme/gadgets on GitHub and check that the old "
                     "URLs redirect (docs/runbooks/repo-rename.md steps 3 and 4)"):
            self.assertIn(line, lines)
        self.assertTrue(any(line.startswith("keep product names: bundle eng-crew-<version>.tar.gz") for line in lines))
        self.assertFalse([line for line in lines if line.startswith(("blocked:", "worktree-move ", "copy "))])
        self.assertEqual(tree(self.tmp), before)

    def test_apply_refused_while_the_session_runs(self):
        r = self.rename("--apply")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("blocked: session crew-acme-widgets is running", r.stdout)
        self.assertTrue(os.path.isdir(self.state))
        self.assertFalse(os.path.exists(self.renamed_state))

    def test_apply_moves_state_and_rewrites_profile_and_guard(self):
        self.stop()
        r = self.rename("--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(self.state))
        self.assertTrue(os.path.isfile(os.path.join(self.renamed_state, "runs", "ben-7.json")))
        profile = self.read(self.project)
        self.assertIn('[repo]\nowner = "acme"\nname = "gadgets"\n', profile)
        self.assertIn('name = "Ash"', profile)
        self.assertIn('repos = ["acme/gadgets"]', profile)
        self.assertIn('builder = ["%s/runs/policy.md"]' % self.renamed_state, profile)
        rec = json.loads(self.read(os.path.join(self.renamed_state, "runs", "ben-7.json")))
        self.assertEqual((rec["worktree"], rec["claim"]),
                         (self.wt, os.path.join(self.renamed_state, "claims", "builder-issue7")))
        hooks = json.loads(self.read(os.path.join(self.project_dir, ".claude", "settings.local.json")))["hooks"]["Stop"]
        self.assertEqual([shlex.split(h["command"])[-1] for e in hooks for h in e["hooks"]], [self.renamed_state])
        work = [line.split(" in ", 1)[1] for line in r.stdout.splitlines() if line.startswith("crew migrate: applied")][0]
        self.assertIn('name = "widgets"', self.read(os.path.join(work, "originals", "profile", "crew.toml")))
        r = self.crew("migrate", "--project", self.project, "--to", self.project)  # resolves to the moved state
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse([line for line in r.stdout.splitlines() if line.startswith(("map ", "rewrite ", "move "))])

    def test_owner_change_or_same_name_refused(self):
        for target in ("other/gadgets", "acme/widgets", "acme/a/b"):
            r = self.crew("migrate", "--project", self.project, "--rename-to", target)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("--rename-to must keep the owner acme and give a new repo name", r.stdout)

    def test_needs_one_of_to_or_rename_to(self):
        r = self.crew("migrate", "--project", self.project, "--to", self.new_project, "--rename-to", "acme/gadgets")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("migrate needs one of --to or --rename-to", r.stdout)


if __name__ == "__main__":
    unittest.main()
