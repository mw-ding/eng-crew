"""Tests for mdstack layout and the paths.root resolver (#1178); fixtures in crew_testlib.py (stdlib only).

Covers: relative children resolve under paths.root from any caller cwd, CREW_ROOT overrides paths.root, a profile
without paths.root keeps its values, absolute children and placeholders stay as they are, --write writes runnable
start wrappers whose quoting survives spaces, and an unmarked wrapper file is refused and left unchanged. Run in CI.
"""
import os
import shlex
import subprocess
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, CREW, PROFILE


class Layout(Base):
    def write_root_profile(self, root, extra=""):
        text = PROFILE.format(runtime="tmux", engine="claude-code", state="x").replace(
            'state_dir = "x"\nworktree_root = "x/wt"\n',
            'root = "%s"\nstate_dir = ".crew/state"\nworktree_root = ".crew/runs/widgets"\nlive_dir = ".crew/live"\n'
            'mdstack = ".crew/state/acme__widgets/mdstack"\ncheckout = "mdstack"\n%s' % (root, extra))
        self.project_dir = os.path.join(root, "crew home")
        os.makedirs(self.project_dir, exist_ok=True)
        self.project = os.path.join(self.project_dir, "crew.toml")
        with open(self.project, "w") as f:
            f.write(text)

    def layout(self, *args, cwd=None, **env):
        r = subprocess.run([sys.executable, CREW, "layout",
                            "--project", self.project, *args], capture_output=True, text=True,
                           env=dict(self.env, **env), cwd=cwd or self.tmp)
        rows = dict(line.split(None, 1) for line in r.stdout.splitlines() if line and not line.startswith(("wrote", "crew:")))
        return r, rows

    def test_children_resolve_under_root_from_any_cwd(self):
        root = os.path.join(self.tmp, "my root")
        self.write_root_profile(root)
        seen = []
        for cwd in (self.tmp, "/"):
            r, rows = self.layout(cwd=cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            seen.append(rows)
        self.assertEqual(seen[0], seen[1])
        rows = seen[0]
        self.assertEqual(rows["root"], root)
        self.assertEqual(rows["state"], os.path.join(root, ".crew/state/acme__widgets"))
        self.assertEqual(rows["worktree_root"], os.path.join(root, ".crew/runs/widgets"))
        self.assertEqual(rows["live_dir"], os.path.join(root, ".crew/live"))
        self.assertEqual(rows["checkout"], os.path.join(root, "mdstack"))
        self.assertEqual(rows["home"], os.path.join(root, "crew home"))
        self.assertEqual(rows["cli"], os.path.join(root, ".crew/state/acme__widgets/mdstack/cli/mdstack"))

    def test_crew_root_overrides_paths_root(self):
        self.write_root_profile(os.path.join(self.tmp, "old"))
        moved = os.path.join(self.tmp, "mdstack")
        r, rows = self.layout(CREW_ROOT=moved)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(rows["root"], moved)
        self.assertEqual(rows["state"], os.path.join(moved, ".crew/state/acme__widgets"))
        self.assertEqual(rows["checkout"], os.path.join(moved, "mdstack"))

    def test_without_root_values_are_unchanged(self):
        r, rows = self.layout(CREW_ROOT=os.path.join(self.tmp, "ignored"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(rows["root"], "(unset)")
        self.assertEqual(rows["state"], self.state)
        self.assertEqual(rows["worktree_root"], os.path.join(self.tmp, "state", "wt"))
        self.assertEqual(rows["checkout"], self.project_dir)

    def test_write_makes_runnable_quoted_wrappers(self):
        root = os.path.join(self.tmp, "my root")
        self.write_root_profile(root)
        cli = os.path.join(root, ".crew/state/acme__widgets/mdstack/cli/mdstack")
        os.makedirs(os.path.dirname(cli))
        with open(cli, "w") as f:
            f.write('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        os.chmod(cli, 0o755)
        os.makedirs(os.path.join(root, "mdstack"))
        r, _ = self.layout("--write", "--owner-cmd", "pwd")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        start = os.path.join(root, "crew home", "start")
        owner = os.path.join(root, "mdstack", ".crew", "start-owner")
        self.assertIn("wrote " + start, r.stdout)
        self.assertIn("wrote " + owner, r.stdout)
        out = subprocess.run([start, "--coordinator-only"], capture_output=True, text=True, cwd="/").stdout
        self.assertEqual(out.splitlines(), ["up", "--project", self.project, "--coordinator-only"])
        out = subprocess.run([owner], capture_output=True, text=True, cwd="/").stdout
        self.assertEqual(os.path.realpath(out.strip()), os.path.realpath(os.path.join(root, "mdstack")))
        self.assertEqual(self.layout("--write")[0].returncode, 0)  # its own files are rewritten
        for path in (start, owner):  # wrappers written before the rename (#1233) carry the old crew marker
            with open(path) as f:
                text = f.read()
            with open(path, "w") as f:
                f.write(text.replace("# Generated by mdstack layout", "# Generated by crew layout")
                        .replace("cli/mdstack", "scripts/crew"))
        r, _ = self.layout("--write")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(start) as f:
            text = f.read()
        self.assertIn("# Generated by mdstack layout", text)
        self.assertIn(shlex.quote(cli) + " up --project", text)

    def test_write_refuses_an_unmarked_file(self):
        root = os.path.join(self.tmp, "root")
        self.write_root_profile(root)
        start = os.path.join(root, "crew home", "start")
        with open(start, "w") as f:
            f.write("#!/bin/sh\necho mine\n")
        r, _ = self.layout("--write")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("refusing layout --write", r.stdout)
        with open(start) as f:
            self.assertEqual(f.read(), "#!/bin/sh\necho mine\n")
        self.assertFalse(os.path.exists(os.path.join(root, "mdstack", ".crew", "start-owner")))


if __name__ == "__main__":
    unittest.main()
