#!/usr/bin/env python3
"""Golden-file tests for scripts/crew-render.py (stdlib only).

Covers the renderer on a fixture profile and inputs in `fixtures/render/`
(expected tree, unknown-placeholder failure, missing mapping, unsupported
capability), and the real tmux briefs rendered from `profiles/tmux.toml` against
`fixtures/render/tmux/`. Run in CI.
"""
import contextlib
import importlib.util
import io
import os
import re
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("crew_render", os.path.join(HERE, "crew-render.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

FIX = os.path.join(HERE, "fixtures", "render")
PROJECT = os.path.join(FIX, "crew.toml")


def tree(root):
    """{relative path: text} for every file under root."""
    out = {}
    for d, _, names in os.walk(root):
        for name in names:
            path = os.path.join(d, name)
            with open(path, encoding="utf-8") as f:
                out[os.path.relpath(path, root)] = f.read()
    return out


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.inputs = os.path.join(self.tmp, "inputs")
        self.out = os.path.join(self.tmp, "out")
        shutil.copytree(os.path.join(FIX, "inputs"), self.inputs)

    def overlay(self, rel, text):
        with open(os.path.join(self.inputs, rel), "w", encoding="utf-8") as f:
            f.write(text)

    def render(self):
        """Run the renderer on the fixture profile; return (code, stdout lines with tmp paths stripped)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(["--project", PROJECT, "--inputs", self.inputs, "--out", self.out])
        return code, [ln.replace(self.tmp + os.sep, "") for ln in out.getvalue().splitlines()]

    def assertFails(self, expected):
        code, out = self.render()
        self.assertEqual(code, 1)
        self.assertEqual(out, expected)
        self.assertFalse(os.path.exists(self.out), "nothing is written on failure")

    def test_golden_tree(self):
        code, _ = self.render()
        self.assertEqual(code, 0)
        expected = tree(os.path.join(FIX, "expected"))
        got = tree(self.out)
        self.assertEqual(sorted(got), sorted(expected))
        for rel, text in expected.items():
            self.assertEqual(got[rel], text, rel)

    def test_unknown_placeholder_golden(self):
        shutil.copy(os.path.join(FIX, "unknown", "core", "builder.md"), os.path.join(self.inputs, "core", "builder.md"))
        with open(os.path.join(FIX, "unknown", "expected.txt"), encoding="utf-8") as f:
            self.assertFails(f.read().splitlines())

    def test_unsupported_capability(self):
        self.overlay("core/builder.md", "# B\n\nBoard: <op:tracker.board-status>\n")
        self.assertFails(["inputs/core/builder.md:3: unsupported capability tracker.board-status "
                                "(backend github)"])

    def test_missing_command_mapping(self):
        self.overlay("core/builder.md", "# B\n\n<op:ci.check-status>\n")
        self.assertFails(["inputs/core/builder.md:3: missing mapping: no command for ci.check-status "
                                "in backends/github.toml"])

    def test_unknown_operation(self):
        self.overlay("core/builder.md", "<op:change.teleport>\n")
        self.assertFails(["inputs/core/builder.md:1: unknown operation change.teleport"])

    def test_missing_role_brief(self):
        os.remove(os.path.join(self.inputs, "core", "reviewer.md"))
        code, out = self.render()
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1)
        self.assertRegex(out[0], r"^inputs/core/reviewer\.md:1: missing mapping: no brief for role reviewer")

    def test_missing_runtime_binding(self):
        shutil.rmtree(os.path.join(self.inputs, "runtimes", "grok-bot"))
        self.assertFails(["inputs/runtimes/grok-bot:1: missing mapping: no runtime binding for grok-bot"])

    def test_resolve_failure_forwarded(self):
        bad = os.path.join(self.tmp, "bad.toml")
        with open(bad, "w", encoding="utf-8") as f:
            f.write('[runtime]\nname = "nope"\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(["--project", bad, "--inputs", self.inputs, "--out", self.out])
        self.assertEqual(code, 1)
        self.assertIn("runtime.name: unknown value 'nope'", out.getvalue())
        self.assertFalse(os.path.exists(self.out))

    def test_documented_placeholders_known(self):
        """Every placeholder in the templates/README.md table is mapped or kept."""
        with open(os.path.join(os.path.dirname(HERE), "templates", "README.md"), encoding="utf-8") as f:
            text = f.read().split("## Placeholders", 1)[1].split("\n## ", 1)[0]
        names = set()
        for line in text.splitlines():
            if line.startswith("| `<"):
                cell = re.split(r"(?<!\\)\|", line)[1]
                names |= {n.replace("\\|", "|") for n in re.findall(r"`<([^`]+)>`", cell)}
        self.assertGreater(len(names), 20)
        self.assertEqual(sorted(names - set(cr.MAPPED) - cr.KEPT), [])



class TmuxBriefs(unittest.TestCase):
    """The real tmux briefs (templates/runtimes/tmux/) render from profiles/tmux.toml to the golden files (#137)."""

    def test_golden_tmux_briefs(self):
        root = os.path.dirname(HERE)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(["--project", os.path.join(root, "profiles", "tmux.toml"), "--out", tmp])
        self.assertEqual(code, 0, out.getvalue())
        expected = tree(os.path.join(FIX, "tmux"))
        got = tree(tmp)
        self.assertEqual(sorted(got), ["runtime/%s.md" % r for r in sorted(cr.ROLES)])
        self.assertEqual(sorted(got), sorted(expected))
        for rel, text in expected.items():
            with self.subTest(brief=rel):
                self.assertEqual(got[rel], text)

    def test_custom_personas_in_both_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            for runtime in ("tmux", "grok-bot"):
                with self.subTest(runtime=runtime):
                    project = os.path.join(tmp, "crew.toml")
                    with open(project, "w", encoding="utf-8") as f:
                        f.write('[runtime]\nname = "%s"\n' % runtime)
                        for role in cr.ROLES:
                            f.write('[identities.%s]\nname = "%s-custom"\ntitle = "Lead"\nemoji = "🌊"\n' % (role, role))
                    out = os.path.join(tmp, runtime)
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        code = cr.main(["--project", project, "--out", out])
                    self.assertEqual(code, 0)
                    got = tree(out)
                    for role in cr.ROLES:
                        matches = [t for rel, t in got.items() if os.path.basename(rel).startswith(role)
                                   and "Sign every authored post" in t]
                        self.assertTrue(matches, role)
                        for text in matches:
                            self.assertIn("— 🌊 %s-custom (Lead) · <harness> · <model>" % role, text)
                            self.assertIn("including\nany fallback", text)
                            self.assertNotIn("CTO", text)

    def test_profile_values_fill_tmux_briefs(self):
        """14.1d (#233): eng-crew path, merge grant and hold semantics render from the profile; booleans as TOML."""
        root = os.path.dirname(HERE)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        project = os.path.join(tmp, "crew.toml")
        with open(os.path.join(root, "profiles", "tmux.toml"), encoding="utf-8") as f:
            text = f.read().replace('options = { permission_mode = "bypass" }\n', 'options = { merge_grant = "#110 '
                                    'roadmap PRs", hold_label_blocks = false }\n')
        with open(project, "w", encoding="utf-8") as f:
            f.write(text + '\n[repo]\nowner = "acme"\nname = "widgets"\n[paths]\neng_crew = "/opt/eng-crew"\n')
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(["--project", project, "--out", os.path.join(tmp, "out")])
        self.assertEqual(code, 0, out.getvalue())
        got = tree(os.path.join(tmp, "out"))
        synth = got["runtime/synthesizer.md"]
        self.assertIn('`merge_grant = "#110 roadmap PRs"`', synth)
        self.assertIn("`hold_label_blocks = false`", synth)
        self.assertIn("`$CREW_BIN land-lock acquire", synth)
        for rel, brief in got.items():
            with self.subTest(brief=rel):
                self.assertIn("/opt/eng-crew/docs/protocol.md", brief)
                self.assertIn("-R acme/widgets", brief)
                self.assertNotIn("<eng-crew>", brief)


if __name__ == "__main__":
    unittest.main()
