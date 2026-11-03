#!/usr/bin/env python3
"""Render parity for the Grok Bot templates and tmux reviewer brief (stdlib only).

Renders the real input tree (templates/) from profiles/default.toml, alone and
with the agentconnect example values, and diffs every runtime file against the
pre-conversion template text (fixtures/parity/pre/) filled in by plain string
replacement. Whitespace is normalized (trailing spaces, trailing blank lines).
Any diff fails. Placeholder table and backend mapping checks ride along.

The tmux reviewer uses a literal-command oracle in `fixtures/parity/tmux-reviewer.md.txt`.
Fixtures in `fixtures/parity/`. A seeded one-word drift fails; every placeholder
has a profile-key row and every operation a command in
`templates/backends/github.toml`. Run in CI.
"""
import contextlib
import difflib
import importlib.util
import io
import json
import os
import re
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("crew_render", os.path.join(HERE, "crew-render.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

INPUTS = os.path.join(ROOT, "templates")
PRE = os.path.join(HERE, "fixtures", "parity", "pre")
DEFAULT_PROFILE = os.path.join(ROOT, "profiles", "default.toml")
EXAMPLE_PROFILE = os.path.join(HERE, "fixtures", "parity", "crew.toml")
# Placeholder -> value, written out by hand so the oracle does not reuse the renderer's map.
# Placeholders not listed render as written (the default profile's placeholder-valued keys).
DEFAULT_VALUES = {
    "flavor-name": "standard", "flavor-review": "thin", "flavor-validation": "behaviour",
    "flavor-evidence": "typed", "flavor-caps": "[3, 3]", "flavor-merge": "docs", "flavor-builder": "crew",
    "max-active-milestones": "1",
    "control-item": "none", "runtime-id": "grok-bot@unconfigured",
    "default-branch": "main", "timezone": "UTC", "fallback-engine": "claude-code",
    "CoordinatorBot": "Ash", "BuilderBot": "Builder", "ReviewerBot": "Reviewer",
    "SynthesizerBot": "Synthesizer", "user-logins": "<user-login>",
    "CoordinatorTitle": "Coordinator", "CoordinatorEmoji": "🔥",
    "BuilderTitle": "Builder", "BuilderEmoji": "🛠️",
    "ReviewerTitle": "Reviewer-validator", "ReviewerEmoji": "🔎",
    "SynthesizerTitle": "Synthesizer", "SynthesizerEmoji": "🔀",
}
EXAMPLE_VALUES = dict(DEFAULT_VALUES, **{
    "owner": "mw-ding", "repo": "agentconnect", "author-login": "mw-ding", "reviewer-login": "md-mt",
    "user-logins": 'mw-ding", "md-mt', "CoordinatorBot": "Ash", "BuilderBot": "Ben", "ReviewerBot": "Vera",
    "SynthesizerBot": "Sam",
})
TOKEN = re.compile(r"<([^<>\s!/=-][^<>\n]*)>")


def normalize(text):
    return "\n".join(line.rstrip() for line in text.splitlines()).rstrip("\n").splitlines()


def expected(values):
    """{runtime/<name>: pre-conversion text with values filled in}."""
    out = {}
    for name in sorted(os.listdir(PRE)):
        with open(os.path.join(PRE, name), encoding="utf-8") as f:
            text = f.read()
        for key, value in values.items():
            text = text.replace("<%s>" % key, value)
        out[os.path.join("runtime", name[:-len(".txt")])] = text
    return out


def render(project, inputs, out):
    """Run the renderer; return (code, stdout)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        code = cr.main(["--project", project, "--inputs", inputs, "--out", out])
    return code, buf.getvalue()


def parity_diff(project, values, inputs=INPUTS):
    """Unified diff (empty on parity) between the rendered runtime files and the filled pre-conversion text."""
    tmp = tempfile.mkdtemp()
    try:
        code, stdout = render(project, inputs, os.path.join(tmp, "out"))
        if code:
            return "render failed:\n" + stdout
        got = {}
        for d, dirs, names in os.walk(os.path.join(tmp, "out")):
            if os.path.relpath(d, os.path.join(tmp, "out")) == "runtime":
                dirs[:] = [name for name in dirs if name != "skills"]
            for name in names:
                path = os.path.join(d, name)
                with open(path, encoding="utf-8") as f:
                    got[os.path.relpath(path, os.path.join(tmp, "out"))] = f.read()
    finally:
        shutil.rmtree(tmp)
    want, diff = expected(values), []
    for rel in sorted(set(got) | set(want)):
        diff += difflib.unified_diff(normalize(want.get(rel, "")), normalize(got.get(rel, "")),
                                     "pre/" + rel, "rendered/" + rel, lineterm="")
    return "\n".join(diff)


class Parity(unittest.TestCase):
    def test_flavor_gate_contract_in_rendered_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            for runtime, names in (
                ("tmux", ("builder.md", "reviewer.md", "synthesizer.md")),
                ("grok-bot", ("builder-b1.md", "builder-b2.md", "reviewer-v2-watch.md", "synthesizer.md")),
            ):
                project = os.path.join(tmp, "crew.toml")
                with open(project, "w") as f:
                    f.write('[runtime]\nname = "%s"\n[flavor]\nname = "fast"\n' % runtime)
                out = os.path.join(tmp, runtime)
                code, output = render(project, INPUTS, out)
                self.assertEqual(code, 0, output)
                for name in names:
                    with self.subTest(runtime=runtime, role=name):
                        with open(os.path.join(out, "runtime", name)) as f:
                            text = " ".join(f.read().split())
                        for rule in ("newest signed item pass=flavor record",
                                     "including both rename paths",
                                     "knob-wise strictest item/path rigor",
                                     "missing record means thorough",
                                     "Unreadable resolution blocks",
                                     "never waives CI, holds or F1–F7"):
                            self.assertIn(rule, text)
                        if "reviewer" in name:
                            for rule in ("pass=validate verdict=pass marker plus validation=skipped",
                                         "a failed validation never becomes a skip",
                                         "mixed rigor lists knobs and omits it"):
                                self.assertIn(rule, text)
                        if "synthesizer" in name:
                            for rule in ("Until follow-up B, existing recorded owner grants retain their scope regardless of merge mode.",
                                         "eligible under the live knobs",
                                         "An older verdict must still satisfy any tightening",
                                         "sensitive/spec and gate-contract changes always require owner merge-ok at head"):
                                self.assertIn(rule, text)

    def test_landing_authority_contract_in_all_runtime_briefs(self):
        with open(os.path.join(HERE, "fixtures", "parity", "landing-authority.json")) as f:
            rules = json.load(f)
        with open(os.path.join(HERE, "fixtures", "parity", "landing-authority-reference.json")) as f:
            reference = json.load(f)
        with open(os.path.join(ROOT, "docs", "protocol.md")) as f:
            protocol = " ".join(f.read().split("### Land rules and merge trains", 1)[1].split())
        for rule in reference["protocol"]:
            self.assertIn(rule, protocol)
        with tempfile.TemporaryDirectory() as tmp:
            for runtime in ("tmux", "grok-bot"):
                project = os.path.join(tmp, "crew.toml")
                with open(project, "w") as f:
                    f.write('[runtime]\nname = "%s"\n' % runtime)
                out = os.path.join(tmp, "out", runtime)
                code, output = render(project, INPUTS, out)
                self.assertEqual(code, 0, output)
                for name in os.listdir(os.path.join(out, "runtime")):
                    if not name.startswith(("coordinator", "synthesizer")):
                        continue
                    with open(os.path.join(out, "runtime", name)) as f:
                        raw = f.read()
                    self.assertLessEqual(len(raw.encode("utf-8")), 16384, (runtime, name))
                    text = " ".join(raw.split())
                    brief_rules = reference["brief"] if runtime == "tmux" else rules
                    for rule in brief_rules:
                        self.assertIn(rule, text, (runtime, name))
                    if runtime == "grok-bot" and name == "coordinator-steering-dispatcher.md":
                        self.assertIn("resume-landing: record stop-id on that same landing-control issue, "
                                      "then wake the synthesizer", text)

    def test_tmux_merge_up_recheck_contract(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        code, stdout = render(os.path.join(ROOT, "profiles", "tmux.toml"), INPUTS, tmp)
        self.assertEqual(code, 0, stdout)
        with open(os.path.join(HERE, "fixtures", "parity", "merge-up-recheck.json")) as f:
            contract = json.load(f)
        for name, rules in contract.items():
            with open(os.path.join(tmp, "runtime", name + ".md")) as f:
                text = " ".join(f.read().split())
            for rule in rules:
                self.assertIn(rule, text, name)

    def test_coordinator_milestone_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            for runtime, brief in (("tmux", "coordinator.md"), ("grok-bot", "wiring.md")):
                for settings, limit in (("", 1), ("max_active_milestones = 2", 2)):
                    with self.subTest(runtime=runtime, limit=limit):
                        project = os.path.join(tmp, "crew.toml")
                        with open(project, "w") as f:
                            f.write('[runtime]\nname = "%s"\n[runtime.options]\n%s\n' % (runtime, settings))
                        out = os.path.join(tmp, "out")
                        code, output = render(project, INPUTS, out)
                        self.assertEqual(code, 0, output)
                        with open(os.path.join(out, "runtime", brief)) as f:
                            text = " ".join(f.read().split())
                        self.assertIn('max_active_milestones = %d' % limit, text)
                        self.assertIn('Dispatch new builds from at most %d open milestones, in milestone order' % limit, text)
                        for rule in ("The earliest active milestone keeps priority",
                                     "A later milestone only fills builder capacity the earlier one cannot use",
                                     "remaining items are blocked by dependencies or already in flight",
                                     "In-flight PRs in any milestone still finish"):
                            self.assertIn(rule, text)

    def test_tmux_lone_land_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(HERE, "fixtures", "parity", "lone-land.json")) as f:
                contract = json.load(f)
            for policy in ("train", "direct"):
                project = os.path.join(tmp, "crew.toml")
                with open(project, "w") as f:
                    f.write('[runtime]\nname = "tmux"\n[runtime.options]\nlone_pr_land = "%s"\n' % policy)
                out = os.path.join(tmp, "out")
                code, output = render(project, INPUTS, out)
                self.assertEqual(code, 0, output)
                for name, rules in contract.items():
                    with open(os.path.join(out, "runtime", name + ".md")) as f:
                        text = " ".join(f.read().split())
                    self.assertIn('lone_pr_land = "%s"' % policy, text)
                    for rule in rules:
                        self.assertIn(rule, text, name)

    def assertParity(self, diff):
        if diff:
            self.fail("rendered text differs from the pre-conversion text:\n" + diff)

    def test_default_profile_parity(self):
        self.assertParity(parity_diff(DEFAULT_PROFILE, DEFAULT_VALUES))

    def test_example_values_parity(self):
        self.assertParity(parity_diff(EXAMPLE_PROFILE, EXAMPLE_VALUES))

    def test_tmux_reviewer_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, output = render(os.path.join(ROOT, "profiles", "tmux.toml"), INPUTS, tmp)
            self.assertEqual(code, 0, output)
            with open(os.path.join(HERE, "fixtures", "parity", "tmux-reviewer.md.txt")) as f:
                expected_text = f.read().replace("<ReviewerBot>", "Vera").replace("<hold-label-blocks>", "true")
                for key, value in DEFAULT_VALUES.items():
                    if key.startswith("flavor-"):
                        expected_text = expected_text.replace("<" + key + ">", value)
            with open(os.path.join(tmp, "runtime", "reviewer.md")) as f:
                self.assertEqual(normalize(f.read()), normalize(expected_text))

    def test_seeded_one_word_drift_fails(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        inputs = os.path.join(tmp, "templates")
        shutil.copytree(INPUTS, inputs)
        path = os.path.join(inputs, "runtimes", "grok-bot", "synthesizer.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Guard first", text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace("Guard first", "Guard last", 1))
        diff = parity_diff(EXAMPLE_PROFILE, EXAMPLE_VALUES, inputs)
        self.assertIn("-Guard first", diff)
        self.assertIn("+Guard last", diff)

    def test_inputs_default_to_templates(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(["--project", DEFAULT_PROFILE, "--out", tmp])
        self.assertEqual(code, 0, buf.getvalue())
        self.assertEqual(sorted(os.listdir(os.path.join(tmp, "runtime"))),
                         sorted([n[:-len(".txt")] for n in os.listdir(PRE)] + ["skills"]))

    def test_every_operation_maps_from_backend_file(self):
        values, problems = cr.resolve(DEFAULT_PROFILE, None)
        self.assertEqual(problems, [])
        renderer = cr.Renderer(values, INPUTS)
        mapping = renderer.table(os.path.join(INPUTS, "backends", "github.toml"))
        self.assertEqual({c: sorted(t) for c, t in mapping.items()},
                         {c: sorted(ops) for c, ops in cr.crew_config.OPERATIONS.items()})
        for concern, ops in cr.crew_config.OPERATIONS.items():
            for op in ops:
                self.assertTrue(renderer.line("<op:%s.%s>" % (concern, op)).strip(), op)

    def test_placeholder_table_maps_every_placeholder(self):
        """Every token in the input tree has a templates/README.md row; its profile key matches the renderer."""
        with open(os.path.join(INPUTS, "README.md"), encoding="utf-8") as f:
            text = f.read().split("## Placeholders", 1)[1].split("\n## ", 1)[0]
        rows = {}
        for line in text.splitlines():
            if line.startswith("| `<"):
                cells = re.split(r"(?<!\\)\|", line)
                for name in re.findall(r"`<([^`]+)>`", cells[1]):
                    rows[name.replace("\\|", "|")] = cells[3]
        used = set()
        for d, _, names in [w for sub in ("core", "runtimes", "backends") for w in os.walk(os.path.join(INPUTS, sub))]:
            for name in names:
                path = os.path.join(d, name)
                if name.endswith(".toml"):  # only the command values render, not the comments
                    text = "\n".join(v for t in cr.Renderer(None, None).table(path).values() for v in t.values())
                else:
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
                for token in TOKEN.findall(text):
                    if token.startswith("include:"):
                        self.assertIn(token, ("include:docs/protocol.md", "include:docs/roles.md",
                                              "include:docs/roles.md#pr-conventions"))
                    elif not token.startswith("op:"):
                        used.add(token)
        self.assertEqual(sorted(used - set(rows)), [])
        for name, cell in rows.items():
            if name in cr.MAPPED:
                for key in cr.MAPPED[name]:
                    self.assertIn("`%s`" % key, cell, name)
            else:
                self.assertIn(name, cr.KEPT)
                self.assertIn("none (run-time)", cell, name)


if __name__ == "__main__":
    unittest.main()
