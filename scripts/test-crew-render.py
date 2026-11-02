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
from unittest.mock import patch

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

    def render(self, project=PROJECT):
        """Run the renderer on the fixture profile; return (code, stdout lines with tmp paths stripped)."""
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(["--project", project, "--inputs", self.inputs, "--out", self.out])
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

    def test_placeholders_follow_registry_identity_keys(self):
        roles = {key: dict(value, identity_key="identities.custom_" + key) for key, value in cr.ROLES.items()}
        load = cr.tomllib.load

        def registry_load(file):
            return {"roles": roles} if os.path.basename(file.name) == "eng.toml" else load(file)

        spec = importlib.util.spec_from_file_location("registry_renderer", os.path.join(HERE, "crew-render.py"))
        renderer = importlib.util.module_from_spec(spec)
        with patch("tomllib.load", side_effect=registry_load):
            spec.loader.exec_module(renderer)
        self.assertEqual(renderer.ROLES, roles)
        values = {metadata["identity_key"] + "." + field: role + "-" + field
                  for role, metadata in roles.items() for field in ("name", "title", "emoji")}
        values.update({metadata["identity_key"] + ".gh_user": "reviewer" if "identity_independent_of" in metadata else "author"
                       for metadata in roles.values()})
        fill = renderer.Renderer(values, self.inputs)
        for role in roles:
            self.assertEqual(fill.line("<%sBot> <%sTitle> <%sEmoji>" % ((role.title(),) * 3)),
                             "%s-name %s-title %s-emoji" % ((role,) * 3))
        self.assertEqual(fill.line("<author-login> <reviewer-login>"), "author reviewer")

    def test_precheck_enabled_disabled_and_missing_commands(self):
        with open(PROJECT, encoding="utf-8") as f:
            profile = f.read()
        project = os.path.join(self.tmp, "crew.toml")
        for settings in ('enabled = false\nlint = "do-lint"', 'enabled = true',
                         'enabled = true\nlint = "do-lint"\ntest = "do-test"\ndocs = "do-docs"\nmax_fix_attempts = 3',
                         'enabled = true\nlint = " "\ntest = ""'):
            with open(project, "w", encoding="utf-8") as f:
                f.write(profile + '\n[builder.precheck]\n' + settings + '\n')
            code, output = self.render(project)
            self.assertEqual(code, 0, output)
            got = tree(self.out)
            if 'enabled = false' in settings:
                self.assertEqual(got, tree(os.path.join(FIX, "expected")))
                continue
            brief = got["briefs/builder.md"]
            self.assertIn("## Builder pre-review check", brief)
            self.assertIn("`pass=precheck` at the final full head SHA", brief)
            for step in range(1, 8):
                self.assertIn("\n%d. " % step, brief)
            if "do-lint" in settings:
                for command in ("do-lint", "do-test", "do-docs"):
                    self.assertIn("```sh\n%s\n```" % command, brief)
                self.assertIn("at most 3 fix attempts", brief)
            else:
                for label in ("Lint / format", "Tests / build", "Docs command"):
                    self.assertIn(label + ": `n/a` (no configured command)", brief)
                self.assertIn("at most 2 fix attempts", brief)
            for name in ("coordinator", "reviewer", "synthesizer"):
                self.assertNotIn("## Builder pre-review check", got["briefs/%s.md" % name])

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
        self.assertEqual(sorted(got), sorted(["runtime/%s.md" % r for r in cr.ROLES] + ["runtime/builder-lead.md", "runtime/reviewer-lead.md"]))
        self.assertEqual(sorted(got), sorted(expected))
        for rel, text in expected.items():
            with self.subTest(brief=rel):
                self.assertEqual(got[rel], text)

    def test_precheck_runtime_briefs_and_org_override(self):
        root = os.path.dirname(HERE)
        with tempfile.TemporaryDirectory() as tmp:
            org = os.path.join(tmp, "org.toml")
            project = os.path.join(tmp, "crew.toml")
            with open(org, "w") as f:
                f.write('[builder.precheck]\nenabled = true\nlint = "org-lint"\ntest = "org-test"\n')
            for runtime, name in (("tmux", "builder.md"), ("grok-bot", "builder-b1.md")):
                for enabled in (True, False):
                    with open(project, "w") as f:
                        f.write('[runtime]\nname = "%s"\n[builder.precheck]\nenabled = %s\ntest = "project-test"\n'
                                % (runtime, str(enabled).lower()))
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        code = cr.main(["--project", project, "--org-profile", org, "--out", tmp])
                    self.assertEqual(code, 0)
                    got = tree(os.path.join(tmp, "runtime"))
                    brief = got[name]
                    self.assertEqual("## Builder pre-review check" in brief, enabled)
                    if enabled:
                        fence = "~~~" if runtime == "grok-bot" else "```"
                        self.assertIn(fence + "sh\norg-lint\n" + fence, brief)
                        self.assertIn(fence + "sh\nproject-test\n" + fence, brief)
                        self.assertNotIn("org-test", brief)
                        if runtime == "grok-bot":
                            self.assertIn("## Builder pre-review check", brief.split("```text\n", 1)[1].split("\n```", 1)[0])
                    self.assertNotIn("## Builder pre-review check", got["synthesizer.md"])

    def test_box_skills_include_reviewed_docs_and_preserve_examples(self):
        root = os.path.dirname(HERE)
        with tempfile.TemporaryDirectory() as tmp:
            project = os.path.join(tmp, "crew.toml")
            with open(project, "w") as f:
                f.write('[paths]\neng_crew = "/opt/bundle"\n')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cr.main(["--project", project, "--out", tmp])
            self.assertEqual(code, 0)
            for skill, doc in (("eng-pr-pipeline", "protocol"), ("eng-crew-roles", "roles")):
                with open(os.path.join(tmp, "runtime", "skills", skill, "SKILL.md")) as f:
                    text = f.read()
                with open(os.path.join(root, "docs", doc + ".md")) as f:
                    reviewed = f.read()
                self.assertIn("name: " + skill, text)
                self.assertIn("<owner>/<repo>", text)
                self.assertIn(reviewed.splitlines()[0], text)
                self.assertIn("](/opt/bundle/docs/", text)
                # Every line survives, apart from rebased link destinations.
                strip_links = lambda body: re.sub(r"\]\([^)]+\)", "]", body)
                self.assertIn(strip_links(reviewed), strip_links(text))

    def test_box_skill_missing_source_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(cr, "HERE", os.path.join(tmp, "scripts")):
                renderer = cr.Renderer({"paths.eng_crew": "/bundle"}, tmp)
                with self.assertRaisesRegex(ValueError, "cannot read included doc"):
                    renderer.line("<include:docs/protocol.md>")
            inputs = os.path.join(tmp, "inputs")
            shutil.copytree(os.path.join(FIX, "inputs"), inputs)
            with open(os.path.join(inputs, "core", "builder.md"), "w") as f:
                f.write("<include:docs/unknown.md>\n")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cr.main(["--project", PROJECT, "--inputs", inputs, "--out", os.path.join(tmp, "out")])
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(os.path.join(tmp, "out")))

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

    def test_lone_pr_land_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = os.path.join(tmp, "crew.toml")
            for policy in (None, "train", "direct"):
                with self.subTest(policy=policy):
                    with open(project, "w") as f:
                        f.write('[runtime]\nname = "tmux"\n')
                        if policy is not None:
                            f.write('[runtime.options]\nlone_pr_land = "%s"\n' % policy)
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        code = cr.main(["--project", project, "--out", os.path.join(tmp, "out")])
                    self.assertEqual(code, 0)
                    got = tree(os.path.join(tmp, "out"))
                    for role in ("coordinator", "synthesizer"):
                        self.assertIn('lone_pr_land = "%s"' % (policy or "train"), got["runtime/%s.md" % role])
                    synth = " ".join(got["runtime/synthesizer.md"].split())
                    for rule in ('exactly one ready PR lands immediately',
                                 'no update-branch, no one-member train',
                                 'Only the tested-with-default-branch gate is waived',
                                 'two or more ready PRs use a merge train',
                                 'Re-survey under the land lock immediately before the squash',
                                 'Tested-with-default-branch waiver: lone_pr_land=direct, exactly one ready PR',
                                 'default-branch push CI run at that exact SHA',
                                 'blocked: main red after #<n> <run-url>'):
                        self.assertIn(rule, synth)
                    coordinator = " ".join(got["runtime/coordinator.md"].split())
                    self.assertIn('file a blocking `crew:ready` fix issue linking the landed PR', coordinator)

    def test_profile_values_fill_tmux_briefs(self):
        """14.1d (#233): eng-crew path, merge grant and hold semantics render from the profile; booleans as TOML."""
        root = os.path.dirname(HERE)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        project = os.path.join(tmp, "crew.toml")
        with open(os.path.join(root, "profiles", "tmux.toml"), encoding="utf-8") as f:
            text = f.read().replace('options = { permission_mode = "bypass" }\n', 'options = { merge_grant = "#110 '
                                    'roadmap PRs", hold_label_blocks = false, mirror_deferral = "#110 roadmap PRs per #140", train_min = 4, train_window = 120 }\n')
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
        self.assertIn('`mirror_deferral = "#110 roadmap PRs per #140"`', synth)
        self.assertIn("do not change live Grok Bot behaviour", synth)
        self.assertIn("--mirror-deferred", synth)
        self.assertIn("`train_min = 4`", synth)
        self.assertIn("`train_window = 120` seconds", synth)
        self.assertIn("A single ready PR with none close merges alone immediately", synth)
        self.assertIn("`$CREW_BIN land-lock acquire", synth)
        for rel, brief in got.items():
            with self.subTest(brief=rel):
                self.assertIn("/opt/eng-crew/docs/protocol.md", brief)
                self.assertIn("-R acme/widgets", brief)
                self.assertNotIn("<eng-crew>", brief)


if __name__ == "__main__":
    unittest.main()
