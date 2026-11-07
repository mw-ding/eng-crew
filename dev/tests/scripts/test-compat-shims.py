"""Compatibility shims at the old script paths (#1222), stdlib only.

Each moved file keeps a shim at its old scripts/ path for one release. Every shim names an existing target; loading a
shim gives the target's names with __file__ at the target; running one prints the target's --help; `scripts/crew`
dispatches commands; the claude-code Stop hook still names scripts/crew and that command runs the guard; and an adapter
left in the old scripts/harness.d/ or scripts/session.d/ is still discovered, through the new and the old discovery
paths, beside the shipped adapters, whose shims do not register twice. The remote forced command through
scripts/crew-remote.py is covered in test-crew-remote.py. The GitHub pack manifest left at packs/github/ (#1223) stays
equal to connectors/github/manifest.toml and validates. Run in CI.
"""
import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
ROOT = os.path.dirname(SCRIPTS)
TARGET = re.compile(r"Compatibility shim: this file moved to (\S+) \(#1222\)")


def shims():
    """{old path: new path} for every shim under scripts/, from its docstring."""
    found = {}
    for d, _, files in os.walk(SCRIPTS):
        for name in files:
            path = os.path.join(d, name)
            if name.endswith(".py") or name == "crew":
                with open(path, encoding="utf-8") as f:
                    m = TARGET.match(ast.get_docstring(ast.parse(f.read())) or "")
                if m:
                    found[os.path.relpath(path, ROOT)] = m.group(1)
    return found


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(*argv, **kw):
    return subprocess.run([sys.executable, *argv], capture_output=True, text=True, cwd=ROOT, **kw)


class Shims(unittest.TestCase):
    def test_every_moved_file_has_a_shim_with_its_mode(self):
        found = shims()
        self.assertIn("scripts/crew", found)
        self.assertEqual(found["scripts/crew"], "cli/crew")
        self.assertEqual(len(found), 56)
        for old, new in found.items():
            with self.subTest(old=old):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, new)), new)
                self.assertEqual(os.stat(os.path.join(ROOT, old)).st_mode, os.stat(os.path.join(ROOT, new)).st_mode)

    def test_loading_a_shim_gives_the_moved_module(self):
        for old, new in [("scripts/crew-config.py", "core/crew-config.py"),
                         ("scripts/harness.d/claude-code.py", "harnesses/claude-code/adapter.py"),
                         ("scripts/crew-session.py", "environments/terminal/crew-session.py")]:
            with self.subTest(old=old):
                shim, moved = load("shim_" + str(abs(hash(old))), os.path.join(ROOT, old)), load(
                    "moved_" + str(abs(hash(new))), os.path.join(ROOT, new))
                self.assertEqual(shim.__file__, os.path.join(ROOT, new))
                self.assertEqual(shim.__doc__, moved.__doc__)
                self.assertEqual(sorted(k for k in vars(shim) if not k.startswith("_")),
                                 sorted(k for k in vars(moved) if not k.startswith("_")))

    def test_running_a_shim_runs_the_moved_script(self):
        for old, new in [("scripts/crew-config.py", "core/crew-config.py"),
                         ("scripts/crew-render.py", "core/crew-render.py"),
                         ("scripts/crew-roles.py", "core/crew-roles.py"),
                         ("scripts/crew-remote.py", "environments/terminal/remote/crew-remote.py")]:
            with self.subTest(old=old):
                self.assertEqual(run(old, "--help").stdout, run(new, "--help").stdout)
        p = run("scripts/crew-config.py", "validate", "profiles/default.toml")
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "crew-config: OK (profiles/default.toml)"))

    def test_scripts_crew_dispatches_commands(self):
        self.assertEqual(run("scripts/crew", "--help").stdout, run("cli/crew", "--help").stdout)
        p = run("scripts/crew", "send", "--help")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("usage: crew send", p.stdout)

    def test_stop_hook_names_scripts_crew_and_runs_the_guard(self):
        adapter = load("shim_claude", os.path.join(ROOT, "harnesses/claude-code/adapter.py"))
        with tempfile.TemporaryDirectory() as state:
            command = adapter.stop_hook_settings({}, state)["hooks"]["Stop"][0]["hooks"][0]["command"]
            argv = command.split()
            self.assertEqual(argv[1], os.path.realpath(os.path.join(ROOT, "scripts", "crew")))
            p = subprocess.run(argv, input=json.dumps({"stop_hook_active": False}), capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)


    def test_adapters_left_in_the_old_directories_are_still_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = os.path.join(os.path.realpath(tmp), "eng-crew")
            shutil.copytree(ROOT, bundle, ignore=shutil.ignore_patterns(".git", ".crew", "__pycache__", "fixtures"))
            for d in ("harness.d", "session.d"):
                with open(os.path.join(bundle, "scripts", d, "legacy.py"), "w") as f:
                    f.write('"""Legacy adapter: test only."""\nEXECUTABLE = "legacy"\nTITLE = "Legacy"\n')
            shipped_h = load("shipped_h", os.path.join(ROOT, "harnesses", "crew-harness.py"))
            shipped_s = load("shipped_s", os.path.join(ROOT, "environments", "terminal", "crew-session.py"))
            for path in ("harnesses/crew-harness.py", "scripts/crew-harness.py"):
                with self.subTest(path=path):
                    h = load("legacy_h_" + str(abs(hash(path))), os.path.join(bundle, path))
                    self.assertEqual(h.ENGINES, shipped_h.ENGINES + ["legacy"])
                    self.assertEqual(h.CLI["legacy"], "legacy")
                    self.assertEqual(h.ADAPTERS["legacy"].__file__, os.path.join(bundle, "scripts", "harness.d", "legacy.py"))
                    self.assertEqual(h.ADAPTERS["claude-code"].__file__,
                                     os.path.join(bundle, "harnesses", "claude-code", "adapter.py"))
            for path in ("environments/terminal/crew-session.py", "scripts/crew-session.py"):
                with self.subTest(path=path):
                    s = load("legacy_s_" + str(abs(hash(path))), os.path.join(bundle, path))
                    self.assertEqual(s.CHOICES, shipped_s.CHOICES + ["legacy"])
                    self.assertEqual(s.ADAPTERS["tmux"].__file__,
                                     os.path.join(bundle, "environments", "terminal", "sessions", "tmux", "adapter.py"))

    def test_old_pack_manifest_matches_the_connector(self):
        old, new = "packs/github/manifest.toml", "connectors/github/manifest.toml"
        with open(os.path.join(ROOT, old), "rb") as a, open(os.path.join(ROOT, new), "rb") as b:
            self.assertEqual(tomllib.load(a), tomllib.load(b))
        p = run("scripts/crew-config.py", "validate", old)
        self.assertEqual((p.returncode, p.stdout.strip()), (0, "crew-config: OK (%s)" % old))


if __name__ == "__main__":
    unittest.main()
