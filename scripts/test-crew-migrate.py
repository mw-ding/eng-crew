"""Tests for crew migrate (#1178); fixtures in crew_testlib.py (stdlib only).

Covers, against a fixture crew with a real builder worktree: the preview is blocked while the old session runs,
and after `crew down --preserve` it lists every mapping (the old home, also the unchanged checkout, keeps its
whole-path references and moves the paths under it), the state move, the registered worktree move, an unregistered
directory kept, the old process identities archived, the operational rewrites, the settings copy and the owner's
memory and trust steps, writing nothing; a destination that exists blocks; profiles naming different repos are
refused. Run in CI.
"""
import json
import os
import unittest
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
        self.assertIn("blocked: session crew-acme-widgets is running; run crew down --preserve", r.stdout)

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


if __name__ == "__main__":
    unittest.main()
