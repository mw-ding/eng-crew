#!/usr/bin/env python3
"""Offline tests for scripts/crew-config.py validate (stdlib only).

Covers the validator (valid profile, missing key, unknown concern and backend,
token-shaped value, wrong type) and the resolver (layer precedence, merge rule,
dropped invariant key, cross-key checks, pack manifest folding with unsupported
and undeclared operations, `resolve_profile` returning what the CLI prints); the
default profile and GitHub pack manifest validate, cover every concern with no
`unsupported` capability, and match the roles.md routing; and the host
inventory and placement keys (#204: overlay names only, secret patterns,
unknown capability, one primary, placement hosts and rule needs, tmux only,
merge across layers). Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("crew_config", os.path.join(HERE, "crew-config.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

CONCERNS = ["change", "review", "tracker", "state-tags", "markers", "ci", "events", "owner-channel", "release"]

VALID = """\
[repo]
owner = "acme"
name = "widgets"

[runtime]
name = "tmux"
options = { builders = 3 }

%s

[identities]
owners = ["acme-owner"]
coordinator = { gh_user = "acme-bot" }
builder = { gh_user = "acme-bot" }
reviewer = { gh_user = "acme-reviewer" }
synthesizer = { gh_user = "acme-bot" }

[engines]
coordinator = "codex"
trivial = { order = ["claude-code/sonnet"] }
default = { order = ["codex/gpt-6.1-sol", "claude-code/sonnet"], effort = "medium" }
deep = { order = ["codex/gpt-6.1-sol"] }

[paths]
state_dir = "/srv/crew-state"
worktree_root = "/srv/wt"
""" % "\n".join('[backends.%s]\nname = "github"' % c for c in CONCERNS)


def validate(text, install=False):
    """Write text to a temp crew.toml, run `validate`, return (code, stdout lines)."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "crew.toml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cc.main(["validate", path] + (["--install"] if install else []))
        lines = [ln.replace(path, "crew.toml") for ln in out.getvalue().splitlines()]
        return code, lines



class IdleBuilderProfile(unittest.TestCase):
    def test_idle_builder_ttl_is_nonnegative_integer(self):
        for ttl in (0, 30, 1800):
            self.assertEqual(validate(VALID.replace("builders = 3", "idle_builder_ttl = %d" % ttl))[0], 0)
        for ttl in ("-1", '"30"', "true"):
            self.assertEqual(validate(VALID.replace("builders = 3", "idle_builder_ttl = " + ttl))[0], 1)


class SlackProfile(unittest.TestCase):
    def test_notify_binding_env_and_closed_scope(self):
        text = VALID.replace('[backends.owner-channel]\nname = "github"',
                             '[backends.owner-channel]\nname = "slack"').replace(
                                 'options = { builders = 3 }',
                                 'options = { slack_webhook_env = "CREW_SLACK_WEBHOOK_URL", slack_digest_interval = 60 }')
        self.assertEqual(validate(text)[0], 0)
        for bad in (text.replace('slack_digest_interval = 60', 'slack_digest_interval = 0'),
                    text.replace('CREW_SLACK_WEBHOOK_URL', 'https://example.test/webhook'),
                    text.replace('slack_webhook_env = "CREW_SLACK_WEBHOOK_URL", ', ''),
                    text.replace('[backends.change]\nname = "github"', '[backends.change]\nname = "slack"'),
                    text.replace('name = "tmux"', 'name = "grok-bot"')):
            self.assertEqual(validate(bad)[0], 1)


class FlavorTest(unittest.TestCase):
    def test_solo_preset_keeps_standard_rigor_and_changes_builder_only(self):
        solo = dict(cc.FLAVOR_PRESETS["solo"])
        self.assertEqual(solo.pop("builder"), "solo")
        standard = dict(cc.FLAVOR_PRESETS["standard"])
        standard.pop("builder")
        self.assertEqual(solo, standard)

    def test_presets_and_custom(self):
        for name in set(cc.FLAVOR_PRESETS) - {"express"}:
            code, lines = validate(VALID + '\n[flavor]\nname = "%s"\n' % name)
            self.assertEqual(code, 0, lines)
        text = VALID + '''
[flavor]
name = "docs-site"
goal = "speed"
[flavor.custom.docs-site]
base = "fast"
review = "light"
merge = "docs"
caps = [1, 2]
parallelism = { builders = 2, reviewers = 1 }
engines = { default = { order = ["codex/gpt-6.1-sol"], effort = "medium" } }
'''
        self.assertEqual(validate(text)[0], 0)

    def test_floor_items(self):
        cases = [("ci = \"off\"", 1), ("ci_waiver = true", 1),
                 ('review = "' + 'ghp_' + 'a' * 36 + '"', 2),
                 ("landing_role = \"builder\"", 3), ("audit = false", 4),
                 ("review = \"off\"", 4), ("hold = false", 5),
                 ("gate_changes = \"auto\"", 6), ("sensitive_merge = \"auto\"", 7),
                 ("caps = [3, 0]", 1)]
        for setting, floor in cases:
            with self.subTest(setting=setting):
                text = VALID + '\n[flavor.custom.test]\nbase = "fast"\n' + setting + '\n'
                code, lines = validate(text)
                self.assertEqual(code, 1, lines)
                self.assertTrue(any("floor F%d:" % floor in line for line in lines), lines)
        for section in ("flavor", "flavor.custom.test", "flavor.classes"):
            prefix = '\n[[%s]]\n' % section if section.endswith('classes') else '\n[%s]\n' % section
            self.assertEqual(validate(VALID + prefix + 'ci = "off"\n')[0], 1)

    def test_express_is_item_only_and_selfgate_engine_knob(self):
        express = cc.FLAVOR_PRESETS["express"]
        self.assertEqual((express["review"], express["validation"], express["merge"], express["selfgate_engine"]),
                         ("off", "off", "auto", "different"))
        for setting, key in [('name = "express"', 'flavor.name'),
                             ('custom = { x = { base = "express" } }', 'flavor.custom.x.base'),
                             ('classes = [{ paths = ["docs/**"], flavor = "express", reason = "r" }]', 'flavor.classes[0].flavor'),
                             ('selfgate_engine = "other"', 'flavor.selfgate_engine'),
                             ('custom = { x = { base = "fast", selfgate_engine = "same" } }', 'flavor.custom.x.selfgate_engine')]:
            with self.subTest(setting=setting):
                code, lines = validate(VALID + '\n[flavor]\n' + setting + '\n')
                self.assertEqual(code, 1, lines)
                self.assertTrue(any(key in line for line in lines), lines)
        for value in cc.SELFGATE_ENGINES:
            self.assertEqual(validate(VALID + '\n[flavor]\nselfgate_engine = "%s"\n' % value)[0], 0)
        code, lines = validate(VALID + '\n[flavor.custom.x]\nbase = "standard"\nreview = "off"\n')
        self.assertEqual(code, 1, lines)
        self.assertTrue(any("floor F4:" in line for line in lines), lines)

    def test_closed_schema_names_bounds_and_engines(self):
        cases = [('name = "unknown"', 'flavor.name'), ('goal = "unknown"', 'flavor.goal'),
                 ('typo = true', 'flavor.typo'), ('custom = []', 'flavor.custom'),
                 ('classes = [1]', 'flavor.classes[0]')]
        cases += [('custom = { test = { base = "fast", %s } }' % setting, key)
                  for setting, key in [('review = "unknown"', '.review'), ('caps = [0, 3]', '.caps'),
                                       ('caps = [3, 4]', '.caps'), ('caps = [true, 2]', '.caps'),
                                       ('caps = [2]', '.caps'), ('parallelism = { builders = 4 }', '.parallelism.builders'),
                                       ('parallelism = { reviewers = 0 }', '.parallelism.reviewers'),
                                       ('engines = { deep = { effort = "low" } }', '.engines.deep.effort'),
                                       ('engines = { default = { order = ["unknown/auto"] } }', '.engines.default.order'),
                                       ('engines = { default = { order = [] } }', '.engines.default.order')]]
        cases += [('custom = { fast = { base = "standard" } }', 'shadows a preset'),
                  ('custom = { solo = { base = "standard" } }', 'shadows a preset'),
                  ('custom = { a = { base = "b" }, b = { base = "fast" } }', '.base')]
        for setting, key in cases:
            with self.subTest(setting=setting):
                code, lines = validate(VALID + '\n[flavor]\n' + setting + '\n')
                self.assertEqual(code, 1, lines)
                self.assertTrue(any(key in line for line in lines), lines)

    def test_class_lowering_reason(self):
        for name, reason, status in [('fast', '', 1), ('fast', 'reason = " "', 1),
                                     ('fast', 'reason = "docs only"', 0), ('thorough', '', 0)]:
            text = VALID + '\n[flavor]\nname = "standard"\n[[flavor.classes]]\npaths = ["docs/**"]\nflavor = "%s"\n%s\n' % (name, reason)
            self.assertEqual(validate(text)[0], status)
        for paths in ('[]', '["../docs/**"]', '["/docs/**"]', '[" "]'):
            text = VALID + '\n[[flavor.classes]]\npaths = %s\nflavor = "thorough"\n' % paths
            self.assertEqual(validate(text)[0], 1)
        text = VALID + '\n[flavor.custom.less]\nbase = "thorough"\ncaps = [2, 3]\n[[flavor.classes]]\npaths = ["docs/**"]\nflavor = "less"\n'
        self.assertEqual(validate(text)[0], 1)

    def test_layer_merging_classes_replacement_and_gap(self):
        with tempfile.TemporaryDirectory() as d:
            project, org = os.path.join(d, "crew.toml"), os.path.join(d, "org.toml")
            with open(project, "w") as f:
                f.write(VALID)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cc.main(["resolve", "--project", project]), 0)
            self.assertIn('flavor.name = "standard"  # core (unset: flagged)', out.getvalue())
            for name in ("thorough", "standard"):
                with open(project, "w") as f:
                    f.write(VALID + '\n[flavor]\nname = "%s"\n' % name)
                profile, prov, problems, _ = cc.resolve_profile(project)
                self.assertEqual((problems, profile["flavor"]["name"], prov["flavor.name"]), ([], name, "project"))
            with open(org, "w") as f:
                f.write('[flavor]\nname = "site"\nclasses = [{ paths = ["old/**"], flavor = "thorough" }]\n[flavor.custom.site]\nbase = "fast"\nmerge = "docs"\n')
            with open(project, "w") as f:
                f.write(VALID + '\n[flavor]\nclasses = []\n[flavor.custom.site]\nreview = "full"\n')
            profile, prov, problems, _ = cc.resolve_profile(project, org)
            self.assertEqual(problems, [])
            self.assertEqual(profile['flavor']['custom']['site'], {'base': 'fast', 'merge': 'docs', 'review': 'full'})
            self.assertEqual(profile['flavor']['classes'], [])
            self.assertEqual(prov['flavor.custom.site.review'], 'project')
            self.assertEqual(prov['flavor.custom.site.base'], 'org')


class ClassFlavorTest(unittest.TestCase):
    def profile(self):
        return {"flavor": {"name": "standard", "classes": [
            {"paths": ["docs/**", "*.md"], "flavor": "fast", "reason": "docs only"},
            {"paths": ["docs/private/*"], "flavor": "thorough"},
            {"paths": ["src/?.py"], "flavor": "fast", "reason": "spikes"}]}}

    def test_dialect_overlap_and_unmatched_paths(self):
        profile = self.profile()
        cases = [("README.md", [0], "thin"), ("docs/nested/a.md", [0], "thin"),
                 ("docs/private/a.md", [0, 1], "full"), ("docs/private/nested/a.md", [0], "thin"),
                 ("src/a.py", [2], "thin"), ("src/ab.py", [], "thin"),
                 ("nested/README.md", [], "thin")]
        for path, indexes, review in cases:
            with self.subTest(path=path):
                result = cc.class_flavor(profile, [path])
                self.assertEqual(result["matches"], {path: indexes})
                self.assertEqual(result["rigor"]["review"], review)
                expected = "off" if indexes == [0] or indexes == [2] else "always" if 1 in indexes else "behaviour"
                self.assertEqual(result["rigor"]["validation"], expected)

    def test_mixed_paths_and_order_independence(self):
        profile = self.profile()
        result = cc.class_flavor(profile, ["docs/a.md", "src/main.py"])
        self.assertEqual(result["rigor"]["validation"], "behaviour")
        self.assertEqual(result["rigor"]["caps"], [3, 3])
        self.assertEqual(result, cc.class_flavor(profile, ["src/main.py", "docs/a.md", "docs/a.md"]))
        profile["flavor"]["classes"].reverse()
        self.assertEqual(result["rigor"], cc.class_flavor(profile, ["src/main.py", "docs/a.md"])["rigor"])

    def test_custom_knob_wise_combination_without_resources(self):
        profile = {"flavor": {"name": "standard", "custom": {
            "a": {"base": "fast", "review": "full", "caps": [1, 3], "parallelism": {"builders": 1}},
            "b": {"base": "standard", "diversity": "required", "caps": [3, 1]}}, "classes": [
                {"paths": ["docs/**"], "flavor": "a", "reason": "docs"},
                {"paths": ["docs/**"], "flavor": "b", "reason": "docs"}]}}
        rigor = cc.class_flavor(profile, ["docs/a.md"])["rigor"]
        self.assertEqual(rigor, {"review": "full", "validation": "behaviour", "diversity": "required",
                                 "evidence": "typed", "merge": "docs", "precheck": "on",
                                 "lighter_lane": "docs", "validation_scope": "bounded", "caps": [3, 3]})

    def test_defaults_empty_paths_and_invalid_paths(self):
        self.assertEqual(cc.class_flavor({}, ["unknown.py"])["rigor"]["review"], "thin")
        self.assertEqual(cc.class_flavor(self.profile(), [])["rigor"]["validation"], "behaviour")
        for path in ("/docs/a.md", "../docs/a.md", "docs/../a.md", "./README.md", "docs//a.md", " "):
            with self.subTest(path=path), self.assertRaises(ValueError):
                cc.class_flavor(self.profile(), [path])

    def test_express_resolution(self):
        profile = self.profile()
        result = cc.class_flavor(profile, ["src/main.py", "docs/a.md"], express=True)
        self.assertEqual((result["lane"], result["tightening"]), ("express", []))
        self.assertEqual(result["rigor"], {"review": "off", "validation": "off", "diversity": "waivable",
                                           "evidence": "typed", "merge": "auto", "precheck": "on",
                                           "lighter_lane": "docs", "validation_scope": "bounded", "caps": [3, 3],
                                           "selfgate_engine": "different"})
        profile["flavor"]["selfgate_engine"] = "same"
        self.assertEqual(cc.class_flavor(profile, [], express=True)["rigor"]["selfgate_engine"], "same")
        tight = cc.class_flavor(profile, ["src/main.py", "docs/private/a.md"], express=True)
        self.assertEqual((tight["lane"], tight["tightening"]), ("crew", [1]))
        self.assertEqual(tight["rigor"], cc.class_flavor(profile, ["src/main.py", "docs/private/a.md"])["rigor"])
        self.assertEqual(cc.class_flavor(profile, ["src/main.py"])["lane"], "crew")
        caps = {"flavor": {"name": "standard", "custom": {"more": {"base": "fast", "caps": [3, 3]}},
                           "classes": [{"paths": ["a/**"], "flavor": "more", "reason": "r"}]}}
        self.assertEqual(cc.class_flavor(caps, ["a/b.py"], express=True)["lane"], "express")
        caps["flavor"]["name"] = "fast"
        caps["flavor"]["custom"]["more"]["review"] = "full"
        self.assertEqual(cc.class_flavor(caps, ["a/b.py"], express=True)["lane"], "crew")

    def test_cli_layers_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            project, org = os.path.join(d, "crew.toml"), os.path.join(d, "org.toml")
            with open(org, "w") as f:
                f.write('[flavor]\nname = "standard"\nclasses = [{ paths = ["docs/**"], flavor = "thorough" }]\n')
            with open(project, "w") as f:
                f.write(VALID + '\n[flavor]\nclasses = [{ paths = ["docs/**"], flavor = "fast", reason = "docs" }]\n')
            def run(paths):
                out, err = io.StringIO(), io.StringIO()
                with patch("sys.stdin", io.StringIO(paths)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = cc.main(["class-flavor", "--project", project, "--org-profile", org])
                return code, out.getvalue(), err.getvalue()
            code, out, err = run("docs/a.md\n")
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out)["rigor"]["validation"], "off")
            self.assertEqual(json.loads(out)["project"], "standard")
            out, err = io.StringIO(), io.StringIO()
            with patch("sys.stdin", io.StringIO("docs/a.md\n")), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cc.main(["class-flavor", "--project", project, "--org-profile", org, "--express"])
            self.assertEqual((code, json.loads(out.getvalue())["lane"]), (0, "express"), err.getvalue())
            self.assertEqual(run("../docs/a.md\n")[0:2], (1, ""))
            with open(project, "a") as f:
                f.write('name = "unknown"\n')
            code, out, err = run("docs/a.md\n")
            self.assertEqual((code, out), (1, ""))
            self.assertIn("flavor.name", err)


class ValidateTest(unittest.TestCase):
    def test_runtime_notes_schema(self):
        for notes in ('{}', '{ builder = [], reviewer = ["review.md"], synthesizer = ["/srv/land.md"] }',
                      '{ render = { coordinator = ["c.md"], builder-lead = ["lead.md"], reviewer-lead = [] } }'):
            code, lines = validate(VALID.replace('options = { builders = 3 }', 'options = { notes = %s }' % notes))
            self.assertEqual(code, 0, lines)
        for notes, expected in [('[]', 'notes: expected table, got list'),
                                ('{ unknown = [] }', 'notes.unknown: unknown key'),
                                ('{ builder = "a.md" }', 'notes.builder: expected list, got string'),
                                ('{ builder = [1] }', 'notes.builder[0]: expected a nonempty file path'),
                                ('{ builder = [" "] }', 'notes.builder[0]: expected a nonempty file path'),
                                ('{ builder-lead = [] }', 'notes.builder-lead: unknown key'),
                                ('{ render = [] }', 'notes.render: expected table, got list'),
                                ('{ render = { solo = [] } }', 'notes.render.solo: unknown key'),
                                ('{ render = { reviewer-lead = [""] } }',
                                 'notes.render.reviewer-lead[0]: expected a nonempty file path')]:
            self.assertFails(VALID.replace('options = { builders = 3 }', 'options = { notes = %s }' % notes),
                             'crew.toml:runtime.options.' + expected)

    def test_launch_topology_schema(self):
        """#606: absent launch adds no resolved key; each key and its values validate."""
        code, lines = resolve(VALID)
        self.assertEqual(code, 0, lines)
        self.assertFalse([ln for ln in lines if "launch" in ln], lines)
        for launch in ('{}', '{ coordinator = "tmux", roles = "hosted", resume = "ask", reconcile = "backend" }',
                       '{ coordinator = "none", roles = "none", resume = "0f9c-ab_1.2:x" }', '{ roles = "tmux" }'):
            code, lines = validate(VALID.replace('options = { builders = 3 }', 'options = { launch = %s }' % launch))
            self.assertEqual(code, 0, lines)
        for launch, expected in [('"hosted"', 'launch: expected table, got string'),
                                 ('{ roles = "remote" }', "launch.roles: unknown value 'remote' (expected one of: tmux, hosted, none)"),
                                 ('{ coordinator = "none" }', 'launch.roles: roles = tmux needs coordinator = tmux (role windows join its session)'),
                                 ('{ resume = "$(id)" }', 'launch.resume: expected fresh, ask or a session id ([A-Za-z0-9._:-])'),
                                 ('{ reconcile = "github" }', "launch.reconcile: unknown value 'github' (expected one of: backend)")]:
            self.assertFails(VALID.replace('options = { builders = 3 }', 'options = { launch = %s }' % launch),
                             'crew.toml:runtime.options.' + expected)

    def assertFails(self, text, expected):
        code, lines = validate(text)
        self.assertEqual(code, 1, lines)
        self.assertIn(expected, lines)

    def test_valid_profile(self):
        code, lines = validate(VALID)
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines, ["crew-config: OK (crew.toml)"])

    def test_pi_coordinator_and_provider_qualified_tier(self):
        text = VALID.replace('coordinator = "codex"', 'coordinator = "pi"').replace(
            '"codex/gpt-6.1-sol"', '"pi/anthropic/claude-sonnet-4-5"')
        code, lines = validate(text)
        self.assertEqual(code, 0, lines)

    def test_role_keys_follow_registry(self):
        roles = {key: dict(value) for key, value in cc.ROLE_REGISTRY.items()}
        roles["builder"]["identity_key"] = "identities.worker"
        roles["coordinator"]["engine_source"] = "lead"
        with patch.object(cc, "ROLE_REGISTRY", roles):
            renamed = VALID.replace("builder = { gh_user", "worker = { gh_user").replace('coordinator = "codex"', 'lead = "codex"')
            self.assertEqual(validate(renamed)[0], 0)
            self.assertFails(VALID, "crew.toml:identities.builder: unknown key")
            self.assertFails(VALID, "crew.toml:identities.worker: missing required key")
            self.assertFails(VALID, "crew.toml:engines.coordinator: unknown key")
            self.assertEqual(validate(renamed.replace('lead = "codex"', 'lead = "muse"'))[0], 0)
            self.assertFails(renamed.replace('lead = "codex"', 'lead = "opencode"'),
                             "crew.toml:engines.lead: unknown value 'opencode' (expected one of: claude-code, codex, pi, cursor, muse)")

    def test_size_budget_schema(self):
        self.assertEqual(validate(VALID + "\n[size_budget]\nbuilder = 8192\n")[0], 0)
        for value, reason in (("0", "must be >= 1"), ("-1", "must be >= 1"),
                              ("true", "expected integer, got boolean"), ('"8192"', "expected integer, got string")):
            self.assertFails(VALID + "\n[size_budget]\nbuilder = " + value + "\n",
                             "crew.toml:size_budget.builder: " + reason)
        self.assertFails(VALID + "\n[size_budget]\nunknown = 1\n", "crew.toml:size_budget.unknown: unknown key")

    def test_precheck_valid_and_optional(self):
        for settings in ('', 'enabled = true', 'enabled = false',
                         'enabled = true\nlint = "lint"\ntest = "test"\ndocs = "docs"\nmax_fix_attempts = 3'):
            code, lines = validate(VALID + '\n[builder.precheck]\n' + settings + '\n')
            self.assertEqual(code, 0, lines)

    def test_precheck_unknown_keys_types_and_attempts(self):
        for settings, expected in [('unknown = true', 'unknown: unknown key'),
                                   ('enabled = "yes"', 'enabled: expected boolean'),
                                   ('lint = []', 'lint: expected string'),
                                   ('test = false', 'test: expected string'),
                                   ('docs = 1', 'docs: expected string'),
                                   ('max_fix_attempts = true', 'max_fix_attempts: expected integer'),
                                   ('max_fix_attempts = 0', 'max_fix_attempts: must be >= 1'),
                                   ('max_fix_attempts = -1', 'max_fix_attempts: must be >= 1')]:
            code, lines = validate(VALID + '\n[builder.precheck]\n' + settings + '\n')
            self.assertEqual(code, 1, lines)
            self.assertTrue(any('builder.precheck.' + expected in line for line in lines), lines)
        self.assertFails(VALID + '\n[builder]\nunknown = true\n', 'crew.toml:builder.unknown: unknown key')

    def test_persona_fields(self):
        for role in ("coordinator", "builder", "reviewer", "synthesizer"):
            original = '%s = { gh_user = "%s" }' % (role, "acme-reviewer" if role == "reviewer" else "acme-bot")
            for field in ("title", "emoji"):
                with self.subTest(role=role, field=field):
                    self.assertEqual(validate(VALID.replace(original, original[:-2] + ', %s = "custom" }' % field))[0], 0)
                    self.assertFails(VALID.replace(original, original[:-2] + ', %s = 42 }' % field),
                                     "crew.toml:identities.%s.%s: expected string, got integer" % (role, field))
        self.assertFails(VALID.replace('coordinator = { gh_user = "acme-bot" }',
                                      'coordinator = { gh_user = "acme-bot", harness = "codex" }'),
                         "crew.toml:identities.coordinator.harness: unknown key")

    def test_persona_layers_and_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            project, org = os.path.join(d, "project.toml"), os.path.join(d, "org.toml")
            with open(project, "w") as f:
                f.write(VALID.replace('coordinator = { gh_user = "acme-bot" }',
                                     'coordinator = { gh_user = "acme-bot", name = "River", emoji = "🌊" }'))
            with open(org, "w") as f:
                f.write('[identities.coordinator]\ntitle = "Lead"\nemoji = "🌲"\n')
            profile, provenance, problems, _ = cc.resolve_profile(project, org)
            self.assertEqual(problems, [])
            self.assertEqual(profile["identities"]["coordinator"],
                             {"gh_user": "acme-bot", "name": "River", "title": "Lead", "emoji": "🌊"})
            self.assertEqual(provenance["identities.coordinator.title"], "org")
            self.assertEqual(provenance["identities.coordinator.emoji"], "project")
            profile, _, problems, _ = cc.resolve_profile(project)
            self.assertEqual(problems, [])
            self.assertEqual(profile["identities"]["coordinator"]["title"], "Coordinator")
            self.assertEqual(profile["identities"]["reviewer"]["emoji"], "🔎")

    def test_train_local_and_mirror_deferral_options(self):
        opts = 'options = { train_local_checks = true, mirror_deferral = "#110 roadmap PRs per #140" }'
        code, lines = validate(VALID.replace('options = { builders = 3 }', opts))
        self.assertEqual(code, 0, lines)
        for option, value, expected in [("train_local_checks", '"yes"', "boolean"),
                                        ("mirror_deferral", "true", "string")]:
            code, lines = validate(VALID.replace('options = { builders = 3 }',
                                                 'options = { %s = %s }' % (option, value)))
            self.assertEqual(code, 1, lines)
            self.assertTrue(any(option in line and expected in line for line in lines), lines)

    def test_doc_example_is_valid(self):
        with open(os.path.join(HERE, "..", "docs", "profile.md"), encoding="utf-8") as f:
            m = re.search(r"```toml\n(.*?)```", f.read(), re.S)
        code, lines = validate(m.group(1))
        self.assertEqual(code, 0, lines)

    def test_sandbox_env_option(self):
        self.assertEqual(validate(VALID.replace('builders = 3', 'sandbox_env = "CREW_TEST_SANDBOX=1"'))[0], 0)
        self.assertFails(VALID.replace('builders = 3', 'sandbox_env = 1'),
                         "crew.toml:runtime.options.sandbox_env: expected string, got integer")

    def test_missing_required_key(self):
        self.assertFails(VALID.replace('owner = "acme"\n', ""),
                         "crew.toml:repo.owner: missing required key")
        self.assertFails(VALID.replace('[backends.ci]\nname = "github"\n', ""),
                         "crew.toml:backends.ci: missing required key")

    def test_unknown_concern(self):
        self.assertFails(VALID + '\n[backends.chat]\nname = "github"\n',
                         "crew.toml:backends.chat: unknown key")

    def test_unknown_backend(self):
        self.assertFails(VALID.replace('[backends.change]\nname = "github"', '[backends.change]\nname = "gitlab"'),
                         "crew.toml:backends.change.name: unknown value 'gitlab' (expected one of: github)")

    def test_token_shaped_value(self):
        token = "ghp_" + "A" * 36  # built at runtime so the repo never holds a token
        code, lines = validate(VALID.replace('builder = { gh_user = "acme-bot" }',
                                             'builder = { gh_user = "%s" }' % token))
        self.assertEqual(code, 1)
        self.assertTrue(any(ln.startswith("crew.toml:identities.builder.gh_user: token-shaped value")
                            for ln in lines), lines)
        bearer = VALID.replace('worktree_root = "/srv/wt"', 'worktree_root = "Authorization: " "Bearer abc123"'.replace('" "', ''))
        self.assertFails(bearer, "crew.toml:paths.worktree_root: token-shaped value "
                         "(bearer auth header with a literal value); refer to credentials by mechanism")

    def test_placeholder_is_not_a_token(self):
        code, lines = validate(VALID.replace('"/srv/wt"', '"Authorization: Bearer <token>"'))
        self.assertEqual(code, 0, lines)

    def test_wrong_type(self):
        self.assertFails(VALID.replace("builders = 3", 'builders = "3"'),
                         "crew.toml:runtime.options.builders: expected integer, got string")
        self.assertFails(VALID.replace('owners = ["acme-owner"]', 'owners = "acme-owner"'),
                         "crew.toml:identities.owners: expected list of strings, got string")
        self.assertFails(VALID.replace("builders = 3", "builders = true"),
                         "crew.toml:runtime.options.builders: expected integer, got boolean")

    def test_unknown_key_and_option(self):
        self.assertFails(VALID + '\n[extra]\nx = 1\n', "crew.toml:extra: unknown key")
        self.assertFails(VALID.replace('name = "tmux"\noptions = { builders = 3 }', 'name = "grok-bot"\noptions = { builders = 3 }'),
                         "crew.toml:runtime.options.builders: unknown key")

    def test_max_active_milestones_validation(self):
        for runtime in ("tmux", "grok-bot"):
            profile = VALID.replace('name = "tmux"', 'name = "%s"' % runtime)
            for options in ("", "max_active_milestones = 2"):
                code, lines = validate(profile.replace("builders = 3", options))
                self.assertEqual(code, 0, lines)
            for value, reason in (("0", "must be >= 1, got 0"),
                                  ("true", "expected integer, got boolean"),
                                  ('"2"', "expected integer, got string")):
                self.assertFails(profile.replace("builders = 3", "max_active_milestones = " + value),
                                 "crew.toml:runtime.options.max_active_milestones: " + reason)

    def test_admission_and_train_option_validation(self):
        self.assertEqual(validate(VALID.replace("builders = 3", "train_min = 3, train_window = 120, max_suites = 2"))[0], 0)
        for key, minimum in (("train_min", 2), ("train_window", 1), ("max_suites", 1)):
            for value, reason in (("true", "expected integer, got boolean"),
                                  ('"2"', "expected integer, got string"),
                                  (str(minimum - 1), "must be >= %d, got %d" % (minimum, minimum - 1)),
                                  ("-1", "must be >= %d, got -1" % minimum)):
                self.assertFails(VALID.replace("builders = 3", "%s = %s" % (key, value)),
                                 "crew.toml:runtime.options.%s: %s" % (key, reason))
        for value in ("12", "12.5"):
            self.assertEqual(validate(VALID.replace("builders = 3", "max_load = " + value))[0], 0)
        for value, reason in (("true", "expected number, got boolean"), ('"12"', "expected number, got string"),
                              ("0", "must be > 0, got 0"), ("-1.5", "must be > 0, got -1.5")):
            self.assertFails(VALID.replace("builders = 3", "max_load = " + value),
                             "crew.toml:runtime.options.max_load: " + reason)

    def test_schedule_target_option_validation(self):  # #623
        ok = "load_high = 8, load_low = 2.5, error_high = 1, schedule_interval = 60, schedule_ramp = 1, stuck_after = 1"
        self.assertEqual(validate(VALID.replace("builders = 3", ok))[0], 0)
        for key in ("error_high", "schedule_interval", "schedule_ramp", "stuck_after"):
            for value, reason in (("true", "expected integer, got boolean"), ("1.5", "expected integer, got float"),
                                  ("0", "must be >= 1, got 0")):
                self.assertFails(VALID.replace("builders = 3", "%s = %s" % (key, value)),
                                 "crew.toml:runtime.options.%s: %s" % (key, reason))
        for key in ("load_high", "load_low"):
            for value, reason in (('"5"', "expected number, got string"), ("0", "must be > 0, got 0")):
                self.assertFails(VALID.replace("builders = 3", "%s = %s" % (key, value)),
                                 "crew.toml:runtime.options.%s: %s" % (key, reason))
        for pair, reason in (("load_high = 5, load_low = 5", "must be < load_high (5), got 5"),
                             ("load_low = 7", "must be < load_high (6.0), got 7"),
                             ("load_high = 3.5", "must be < load_high (3.5), got 4.0")):
            self.assertFails(VALID.replace("builders = 3", pair), "crew.toml:runtime.options.load_low: " + reason)

    def test_engines(self):
        cursor = VALID.replace('coordinator = "codex"', 'coordinator = "cursor"').replace('claude-code/sonnet', 'cursor/composer-1')
        self.assertEqual(validate(cursor)[0], 0)
        self.assertFails(VALID.replace('trivial = { order = ["claude-code/sonnet"] }', 'trivial = { order = ["unknown/auto"] }'),
                         "crew.toml:engines.trivial.order[0]: unknown engine 'unknown' "
                         "(expected <engine>/<model>, engine one of: claude-code, codex, muse, opencode, pi, cursor)")
        self.assertFails(VALID.replace('effort = "medium"', 'effort = "max"'),
                         "crew.toml:engines.default.effort: unknown value 'max' (expected one of: low, medium, high)")

    def test_engine_role_overrides(self):  # #597
        roles = '\n[engines.roles]\nsynthesizer = { order = ["codex/gpt-6.1-sol"] }\n'
        self.assertEqual(validate(VALID + roles)[0], 0)
        for old, new, expected in (
                ("synthesizer", "coordinator", "crew.toml:engines.roles.coordinator: unknown key"),
                ('"codex/gpt-6.1-sol"', '"bogus/auto"', "crew.toml:engines.roles.synthesizer.order[0]: unknown engine 'bogus'"),
                ('order = ["codex/gpt-6.1-sol"]', 'effort = "low"', "crew.toml:engines.roles.synthesizer.effort: unknown key"),
                ('{ order = ["codex/gpt-6.1-sol"] }', '"codex"', "crew.toml:engines.roles.synthesizer: expected table")):
            code, lines = validate(VALID + roles.replace(old, new))
            self.assertEqual(code, 1, lines)
            self.assertTrue(any(line.startswith(expected) for line in lines), lines)

    def test_tool_probes(self):
        tools = '\n[tools.example]\nrunning = ["session", "version"]\ninstalled = ["example", "--version"]\npin = "2.10.0"\n'
        self.assertEqual(validate(VALID + tools)[0], 0)
        for old, new, key, reason in (
                ('running = ["session", "version"]', 'running = "session"', "running", "expected list of strings, got string"),
                ('running = ["session", "version"]', 'running = []', "running", "expected list of strings, got list"),
                ('running = ["session", "version"]', 'running = [""]', "running", "command arguments must not be empty"),
                ('installed = ["example", "--version"]', '', "installed", "missing required key"),
                ('pin = "2.10.0"', 'pin = "latest"', "pin", "expected X.Y.Z or vX.Y.Z minimum version")):
            self.assertFails(VALID + tools.replace(old, new), "crew.toml:tools.example.%s: %s" % (key, reason))

    def test_capabilities(self):
        ok = VALID.replace('[backends.review]\nname = "github"',
                           '[backends.review]\nname = "github"\ncapabilities = { post-verdict = "emulated (COMMENT review)" }')
        self.assertEqual(validate(ok)[0], 0)
        self.assertFails(ok.replace("emulated (COMMENT review)", "emulated"),
                         "crew.toml:backends.review.capabilities.post-verdict: expected supported, "
                         "unsupported or emulated (<how>)")
        self.assertFails(ok.replace("post-verdict", "merge"),
                         "crew.toml:backends.review.capabilities.merge: unknown key")

    def test_invalid_toml(self):
        code, lines = validate("[repo\n")
        self.assertEqual(code, 1)
        self.assertTrue(lines[0].startswith("crew.toml:(toml): invalid TOML"), lines)

    def test_missing_file(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            code = cc.main(["validate", "/nonexistent/crew.toml"])
        self.assertEqual(code, 1)
        self.assertIn("/nonexistent/crew.toml:(file): cannot read", out.getvalue())


ROOT = os.path.join(HERE, "..")
DEFAULT_PROFILE = os.path.join(ROOT, "profiles", "default.toml")
CAPABILITY_OK = re.compile(r"supported|emulated \(.*\S.*\)")


def load_toml(path):
    with open(path, "rb") as f:
        return cc.tomllib.load(f)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class DefaultProfileTest(unittest.TestCase):
    """Default GitHub profile and pack manifest (13.12, #124)."""

    def test_default_profile_and_manifest_validate(self):
        for path in [DEFAULT_PROFILE, os.path.join(ROOT, "packs", "github", "manifest.toml")]:
            code, lines = validate(read(path))
            self.assertEqual(code, 0, (path, lines))

    def test_default_profile_covers_every_concern_none_unsupported(self):
        backends = load_toml(DEFAULT_PROFILE)["backends"]
        self.assertEqual(sorted(backends), sorted(CONCERNS))
        for concern, table in backends.items():
            manifest = load_toml(os.path.join(ROOT, "packs", table["name"], "manifest.toml"))
            effective = dict(manifest["capabilities"].get(concern, {}), **table.get("capabilities", {}))
            for op in cc.OPERATIONS[concern]:
                value = effective.get(op, "unsupported")
                self.assertTrue(CAPABILITY_OK.fullmatch(value), "%s.%s: %s" % (concern, op, value))

    def test_default_profile_sets_renderer_keys(self):
        p = load_toml(DEFAULT_PROFILE)
        for role in ["coordinator", "builder", "reviewer", "synthesizer"]:
            self.assertTrue(p["identities"][role].get("name"), role)
        self.assertTrue(p["paths"].get("toolchain_bin"))
        self.assertTrue(p["engines"].get("fallback_engine"))
        self.assertTrue(p["runtime"].get("timezone"))
        self.assertEqual(p["runtime"]["name"], "grok-bot")
        self.assertNotEqual(p["identities"]["reviewer"]["gh_user"], p["identities"]["builder"]["gh_user"])

    def test_engine_routing_matches_roles_md(self):
        """Each tier's order is roles.md Current routing, private-repo case: no Muse,
        no Cursor; Codex `-p <profile>` fallbacks are not <engine>/<model> entries."""
        roles = read(os.path.join(ROOT, "docs", "roles.md"))
        section = roles.split("### Current routing", 1)[1].split("\n### ", 1)[0]
        token = re.compile(r"Muse Code|Claude Code `([^`]+)`|Codex `([^`-][^`]*)`|OpenCode \+ DeepSeek `([^`]+)`")
        engines = load_toml(DEFAULT_PROFILE)["engines"]
        for tier, label in [("trivial", "trivial"), ("default", "default"), ("deep", "deep / risky")]:
            row = re.search(r"^\| %s \|(.*)$" % re.escape(label), section, re.M).group(1)
            expected = []
            for m in token.finditer(row):
                if m.group(1):
                    expected.append("claude-code/" + m.group(1))
                elif m.group(2):
                    expected.append("codex/" + m.group(2))
                elif m.group(3):
                    expected.append("opencode/" + m.group(3))
            self.assertEqual(engines[tier]["order"], expected, tier)
            self.assertEqual(engines[tier]["effort"], cc.TIER_EFFORT[tier])
            self.assertIn(cc.TIER_EFFORT[tier], row.split("|")[1])
            self.assertFalse(any(e.startswith(("muse/", "cursor/")) for e in engines[tier]["order"]))
        self.assertEqual(engines["coordinator"], "claude-code")
        self.assertIn(engines["fallback_engine"], ["claude-code", "codex"])

    def test_renderer_keys_validated(self):
        ok = (VALID.replace('builder = { gh_user = "acme-bot" }', 'builder = { gh_user = "acme-bot", name = "Bob" }')
              .replace('options = { builders = 3 }', 'options = { builders = 3 }\ntimezone = "UTC"')
              .replace('coordinator = "codex"', 'coordinator = "codex"\nfallback_engine = "claude-code"')
              .replace('worktree_root = "/srv/wt"', 'worktree_root = "/srv/wt"\ntoolchain_bin = "/opt/node/bin"'))
        self.assertEqual(validate(ok)[0], 0, validate(ok)[1])
        self.assertFails(ok.replace('name = "Bob"', "name = 1"),
                         "crew.toml:identities.builder.name: expected string, got integer")
        self.assertFails(ok.replace('timezone = "UTC"', "timezone = 0"),
                         "crew.toml:runtime.timezone: expected string, got integer")
        self.assertFails(ok.replace('toolchain_bin = "/opt/node/bin"', "toolchain_bin = []"),
                         "crew.toml:paths.toolchain_bin: expected string, got list")
        self.assertFails(ok.replace('fallback_engine = "claude-code"', 'fallback_engine = "unknown"'),
                         "crew.toml:engines.fallback_engine: unknown value 'unknown' "
                         "(expected one of: claude-code, codex, muse, opencode, pi, cursor)")

    assertFails = ValidateTest.assertFails

    def test_manifest_validation(self):
        manifest = read(os.path.join(ROOT, "packs", "github", "manifest.toml"))
        self.assertFails(manifest.replace('name = "github"', 'name = "gitlab"', 1),
                         "crew.toml:pack.eng_crew_version: required for an external backend")
        self.assertFails(re.sub(r"\nland = .*", "", manifest),
                         "crew.toml:capabilities.change.land: missing required key")
        self.assertFails(manifest.replace('close = "supported"', 'close = "maybe"'),
                         "crew.toml:capabilities.change.close: expected supported, unsupported or emulated (<how>)")
        self.assertFails(manifest + '\n[capabilities.chat]\nask = "supported"\n',
                         "crew.toml:capabilities.chat: unknown key")


def resolve(project, default=None, org=None, org_path=None):
    """Write layer files to a temp dir, run `resolve`, return (code, stdout lines) with the dir stripped."""
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for name, text in (("default", default), ("org", org), ("crew", project)):
            paths[name] = os.path.join(d, name + ".toml")
            if text is not None:
                with open(paths[name], "w", encoding="utf-8") as f:
                    f.write(text)
        argv = ["resolve", "--project", paths["crew"]]
        if org is not None or org_path:
            argv += ["--org-profile", org_path or paths["org"]]
        saved, cc.DEFAULT_PROFILE = cc.DEFAULT_PROFILE, paths["default"]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cc.main(argv)
        finally:
            cc.DEFAULT_PROFILE = saved
        return code, [ln.replace(d + os.sep, "") for ln in out.getvalue().splitlines()]


class ResearcherProfile(unittest.TestCase):
    """#584: the optional researcher identity and the `researchers` cap."""

    def test_researcher_identity_is_optional_and_checked(self):
        self.assertEqual(validate(VALID)[0], 0)
        ok = VALID.replace('synthesizer = { gh_user = "acme-bot" }',
                           'synthesizer = { gh_user = "acme-bot" }\nresearcher = { gh_user = "acme-bot", name = "Riley" }')
        self.assertEqual(validate(ok)[0], 0)
        code, lines = validate(ok.replace('researcher = { gh_user = "acme-bot", name = "Riley" }',
                                          'researcher = { name = "Riley" }'))
        self.assertEqual(code, 1)
        self.assertTrue(any("identities.researcher.gh_user" in ln for ln in lines), lines)
        code, lines = validate(ok.replace('name = "Riley" }', 'name = "Riley", role = "x" }'))
        self.assertEqual(code, 1)
        self.assertTrue(any("identities.researcher.role" in ln for ln in lines), lines)

    def test_researchers_cap_defaults_to_one_and_must_be_positive(self):
        for value in ("0", "-1", "true", '"2"', "1.5"):
            text = VALID.replace("builders = 3", "builders = 3, researchers = " + value)
            self.assertEqual(validate(text)[0], 1, value)
        self.assertEqual(validate(VALID.replace("builders = 3", "builders = 3, researchers = 2"))[0], 0)
        code, lines = resolve(VALID, default=VALID)
        self.assertEqual(code, 0, lines)
        self.assertIn("runtime.options.researchers = 1  # core", lines)

    def test_researcher_identity_resolves_to_the_author_login(self):  # #584 part 2: a registry role
        code, lines = resolve(VALID, default=VALID)
        self.assertEqual(code, 0, lines)
        for line in ('identities.researcher.gh_user = "acme-bot"  # core', 'identities.researcher.name = "Riley"  # core',
                     "size_budget.researcher = 16384  # core"):
            self.assertIn(line, lines)
        own = VALID.replace('synthesizer = { gh_user = "acme-bot" }',
                            'synthesizer = { gh_user = "acme-bot" }\nresearcher = { gh_user = "acme-research" }')
        self.assertIn('identities.researcher.gh_user = "acme-research"  # project', resolve(own, default=VALID)[1])


class ResolveTest(unittest.TestCase):
    def test_present_caps_validation_and_resolved_defaults(self):
        for key in ("present_builders", "present_reviewers"):
            for value in ("0", "-1", "true", '"2"', "1.5"):
                text = VALID.replace('options = { builders = 3 }',
                                     'options = { builders = 3, %s = %s }' % (key, value))
                self.assertEqual(validate(text)[0], 1, (key, value))
                self.assertEqual(resolve(text, default=VALID)[0], 1, (key, value))
        for options, expected in (('builders = 3, reviewers = 4', (3, 4)),
                                  ('builders = 3, reviewers = 4, present_builders = 1, present_reviewers = 2', (1, 2))):
            text = VALID.replace('options = { builders = 3 }', 'options = { %s }' % options)
            code, lines = resolve(text, default=VALID)
            self.assertEqual(code, 0, lines)
            for key, value in zip(("present_builders", "present_reviewers"), expected):
                self.assertIn('runtime.options.%s = %s  # %s' %
                              (key, value, "core" if "present_" not in options else "project"), lines)

    def test_size_budget_defaults_and_layer_overrides(self):
        self.assertResolves(['size_budget.builder = 16384  # core',
                             'size_budget.reviewer = 16384  # core'], VALID)
        self.assertResolves(['size_budget.builder = 8192  # project',
                             'size_budget.reviewer = 4096  # org',
                             'size_budget.coordinator = 16384  # core'],
                            VALID + "\n[size_budget]\nbuilder = 8192\n",
                            org="[size_budget]\nbuilder = 12288\nreviewer = 4096\n")

    def assertResolves(self, expected, *args, **kwargs):
        code, lines = resolve(*args, **kwargs)
        self.assertEqual(code, 0, lines)
        for line in expected:
            self.assertIn(line, lines)
        return lines

    def assertFails(self, expected, *args, **kwargs):
        code, lines = resolve(*args, **kwargs)
        self.assertEqual(code, 1, lines)
        self.assertIn(expected, lines)

    def test_core_defaults_under_project(self):
        self.assertResolves(['repo.default_branch = "main"  # core',
                             'repo.owner = "acme"  # project',
                             'runtime.options.builders = 3  # project',
                             'runtime.options.reviewers = 2  # core',
                             'engines.trivial.effort = "low"  # core',
                             'engines.default.effort = "medium"  # project'], VALID)

    def test_each_layer_overrides_the_one_before(self):
        default = VALID.replace('name = "widgets"', 'name = "widgets"\ndefault_branch = "trunk"')
        org = '[engines]\ndefault = { order = ["claude-code/opus"] }\ndeep = { effort = "medium" }\n'
        project = '[repo]\nowner = "other"\n[engines]\ndeep = { effort = "low" }\n'
        self.assertResolves(['repo.default_branch = "trunk"  # default',
                             'repo.name = "widgets"  # default',
                             'engines.default.order = ["claude-code/opus"]  # org',
                             'engines.default.effort = "medium"  # default',
                             'engines.deep.effort = "low"  # project',
                             'repo.owner = "other"  # project'], project, default=default, org=org)

    def test_table_merge_and_scalar_array_replace(self):
        project = '[identities]\nowners = ["a", "b"]\n[engines]\ndefault = { order = ["claude-code/opus"] }\n'
        lines = self.assertResolves(['identities.owners = ["a", "b"]  # project',
                                     'identities.builder.gh_user = "acme-bot"  # default',
                                     'engines.default.order = ["claude-code/opus"]  # project'],
                                    project, default=VALID)
        self.assertNotIn('engines.default.order = ["codex/gpt-6.1-sol", "claude-code/sonnet"]  # default', lines)

    def test_engine_role_override_resolves(self):  # #597
        project = '[engines.roles]\nsynthesizer = { order = ["codex/gpt-6.1-sol"] }\n'
        self.assertResolves(['engines.roles.synthesizer.order = ["codex/gpt-6.1-sol"]  # project'], project, default=VALID)
        self.assertFails("crew.toml:engines.roles.lead: unknown key", project.replace("synthesizer", "lead"), default=VALID)

    def test_missing_org_layer(self):
        self.assertResolves(['repo.owner = "acme"  # project'], VALID)
        self.assertResolves(['repo.owner = "acme"  # default'], "", default=VALID)
        code, lines = resolve(VALID, org_path="/nonexistent/org.toml")
        self.assertEqual(code, 1)
        self.assertTrue(lines[0].startswith("/nonexistent/org.toml:(file): cannot read"), lines)

    def test_drop_invariant_key_is_an_error(self):
        self.assertFails("crew.toml:identities.reviewer.gh_user: cannot remove invariant-protecting key (set by default)",
                         'identities = "none"\n', default=VALID)
        default = VALID.replace('[backends.review]\nname = "github"',
                                '[backends.review]\nname = "github"\ncapabilities = { post-verdict = "supported" }')
        self.assertFails("org.toml:backends.review.capabilities.post-verdict: cannot remove invariant-protecting key "
                         "(set by default)", "", default=default, org='[backends.review]\ncapabilities = "none"\n')

    def test_resolved_profile_is_validated(self):
        self.assertFails("(resolved):repo.owner: missing required key", VALID.replace('owner = "acme"\n', ""))
        self.assertFails("crew.toml:extra: unknown key", '[extra]\nx = 1\n', default=VALID)

    def test_unsupported_invariant_rule(self):
        one = VALID.replace('[backends.review]\nname = "github"',
                            '[backends.review]\nname = "github"\ncapabilities = { request-rereview = "unsupported" }')
        self.assertResolves([], one)
        self.assertFails("crew.toml:backends.review.capabilities.post-verdict: unsupported leaves I2 with no other "
                         "operation keeping it; profile unsupported (docs/interfaces.md)",
                         one.replace('{ request-rereview', '{ post-verdict = "unsupported", request-rereview'))

    def test_single_identity_requires_emulated_verdict(self):
        single = VALID.replace('reviewer = { gh_user = "acme-reviewer" }', 'reviewer = { gh_user = "acme-bot" }')
        self.assertFails(os.path.join(cc.PACKS_DIR, "github", "manifest.toml") +
                         ":backends.review.capabilities.post-verdict: reviewer gh_user equals builder "
                         "gh_user; a single-identity profile must declare emulated (<how>) (#111)", single)
        self.assertResolves([], single.replace('[backends.review]\nname = "github"',
                                               '[backends.review]\nname = "github"\n'
                                               'capabilities = { post-verdict = "emulated (COMMENT review)" }'))

    def test_release_table_and_gate_operations(self):
        """#585: the optional [release] table and the release concern."""
        release = '\n[release]\nchangelog = "docs/HISTORY.md"\nrelease_id = "commit"\n'
        self.assertResolves(['release.release_id = "commit"  # project'], VALID + release)
        no_release = VALID.replace('[backends.release]\nname = "github"', "")
        self.assertResolves([], no_release)
        self.assertFails("(resolved):backends.release.capabilities.approve-check: undeclared (counts as unsupported) "
                         "with a [release] table leaves the release gate unkept; profile unsupported for release "
                         "(docs/interfaces.md)", no_release + release)
        self.assertFails("crew.toml:backends.release.capabilities.record-release: unsupported with a [release] table "
                         "leaves the release gate unkept; profile unsupported for release (docs/interfaces.md)",
                         VALID.replace('[backends.release]\nname = "github"', '[backends.release]\nname = "github"\n'
                                       'capabilities = { record-release = "unsupported" }') + release)
        for bad in ('release_id = "hash"', 'versioning = "calver"', 'tag_prefix = "v"', 'changelog = 1'):
            self.assertEqual(validate(VALID + "\n[release]\n" + bad + "\n")[0], 1, bad)

    def test_merge_grant_and_hold_options(self):
        """14.1d (#233): tmux synthesizer options default to per-PR merge-ok and a blocking crew:hold."""
        self.assertResolves(['runtime.options.merge_grant = "none"  # core',
                             'runtime.options.hold_label_blocks = true  # core'], VALID)
        self.assertResolves(['runtime.options.merge_grant = "#110 roadmap PRs per #111"  # project',
                             'runtime.options.hold_label_blocks = false  # project',
                             'paths.eng_crew = "/srv/eng-crew"  # project'],
                            VALID.replace("builders = 3", 'builders = 3, merge_grant = "#110 roadmap PRs per #111", '
                                          "hold_label_blocks = false")
                            + 'eng_crew = "/srv/eng-crew"\n')
        self.assertFails("crew.toml:runtime.options.hold_label_blocks: expected boolean, got string",
                         VALID.replace("builders = 3", 'builders = 3, hold_label_blocks = "no"'))

    def test_lone_pr_land_option(self):
        self.assertResolves(['runtime.options.lone_pr_land = "train"  # core'], VALID)
        for policy in ("train", "direct"):
            self.assertResolves(['runtime.options.lone_pr_land = "%s"  # project' % policy],
                                VALID.replace("builders = 3", 'lone_pr_land = "%s"' % policy),
                                org='[runtime.options]\nlone_pr_land = "direct"\n')
        self.assertFails("crew.toml:runtime.options.lone_pr_land: unknown value 'skip' (expected one of: train, direct)",
                         VALID.replace("builders = 3", 'lone_pr_land = "skip"'))
        self.assertFails("crew.toml:runtime.options.lone_pr_land: expected string, got boolean",
                         VALID.replace("builders = 3", "lone_pr_land = true"))

    def test_suite_cap_resolves_explicit_override(self):
        self.assertResolves(["runtime.options.max_suites = 3  # project"],
                            VALID.replace("builders = 3", "max_suites = 3"),
                            org="[runtime.options]\nmax_suites = 2\n")
        code, lines = resolve(VALID)
        self.assertEqual(code, 0, lines)
        self.assertFalse(any(line.startswith("runtime.options.max_suites =") for line in lines))

    def test_max_active_milestones_resolve(self):
        for runtime in ("tmux", "grok-bot"):
            profile = VALID.replace('name = "tmux"', 'name = "%s"' % runtime)
            self.assertResolves(['runtime.options.max_active_milestones = 1  # core'],
                                profile.replace("builders = 3", ""))
            self.assertResolves(['runtime.options.max_active_milestones = 2  # project'],
                                profile.replace("builders = 3", "max_active_milestones = 2"),
                                org='[runtime.options]\nmax_active_milestones = 3\n')
            self.assertFails("crew.toml:runtime.options.max_active_milestones: must be >= 1, got 0",
                             profile.replace("builders = 3", "max_active_milestones = 0"))

    def test_train_options_resolve(self):
        self.assertResolves(['runtime.options.train_min = 2  # core',
                             'runtime.options.train_window = 600  # core'], VALID)
        self.assertResolves(['runtime.options.train_min = 4  # project',
                             'runtime.options.train_window = 120  # org'],
                            VALID.replace("builders = 3", "train_min = 4"),
                            org='[runtime.options]\ntrain_min = 3\ntrain_window = 120\n')
        self.assertFails("crew.toml:runtime.options.train_min: must be >= 2, got 1",
                         VALID.replace("builders = 3", "train_min = 1"))
        self.assertFails("crew.toml:runtime.options.train_window: must be >= 1, got 0",
                         VALID.replace("builders = 3", "train_window = 0"))

    def test_permission_mode_option(self):
        """#293: tmux role windows launch unattended by default (bypass); auto and safe are opt-in."""
        self.assertResolves(['runtime.options.permission_mode = "bypass"  # core'], VALID)
        for mode in ["bypass", "auto", "safe"]:
            self.assertResolves(['runtime.options.permission_mode = "%s"  # project' % mode],
                                VALID.replace("builders = 3", 'builders = 3, permission_mode = "%s"' % mode))
        self.assertFails("crew.toml:runtime.options.permission_mode: unknown value 'yolo' (expected one of: bypass, "
                         "auto, safe)", VALID.replace("builders = 3", 'builders = 3, permission_mode = "yolo"'))
        self.assertFails("crew.toml:runtime.options.permission_mode: expected string, got boolean",
                         VALID.replace("builders = 3", "builders = 3, permission_mode = true"))

    def test_integer_option_range(self):
        self.assertFails("crew.toml:runtime.options.builders: must be >= 1, got 0",
                         VALID.replace("builders = 3", "builders = 0"))

    def test_doc_example_resolves(self):
        with open(os.path.join(HERE, "..", "docs", "profile.md"), encoding="utf-8") as f:
            m = re.search(r"```toml\n(.*?)```", f.read(), re.S)
        self.assertResolves(['runtime.options.builders = 5  # project'], m.group(1))

    def test_resolve_profile_is_what_the_cli_prints(self):
        """#165: resolve_profile returns the merged profile and per-leaf provenance; `resolve` prints exactly that."""
        with tempfile.TemporaryDirectory() as d:
            project = os.path.join(d, "crew.toml")
            with open(project, "w", encoding="utf-8") as f:
                f.write(VALID)
            saved, cc.DEFAULT_PROFILE = cc.DEFAULT_PROFILE, os.path.join(d, "absent.toml")
            try:
                merged, provenance, problems, layers = cc.resolve_profile(project)
                failed = cc.resolve_profile(os.path.join(d, "missing.toml"))
            finally:
                cc.DEFAULT_PROFILE = saved
        self.assertEqual((problems, layers), ([], ["core", "project"]))
        self.assertEqual(merged["runtime"]["options"]["builders"], 3)
        self.assertEqual([provenance[k] for k in ("repo.owner", "repo.default_branch", "backends.change.capabilities.land")],
                         ["project", "core", "pack:github"])
        self.assertEqual(resolve(VALID), (0, ["%s = %s  # %s" % (k, json.dumps(v, ensure_ascii=False), provenance[k])
                                              for k, v in cc.leaves(merged)]))
        self.assertEqual(failed[:2], (None, None))
        self.assertEqual([p.replace(d + os.sep, "") for p in failed[2]],
                         ["missing.toml:(file): cannot read (No such file or directory)"])




# --- team files (#634): one [team] table plus small [repos.<name>] sections. ---
TEAM = """\
[team]
pack = "github"
personas = { builder = "Ben", reviewer = "Vera" }
accounts = { all = "acme-bot", reviewer = "acme-reviewer" }
runtime = { name = "tmux", options = { builders = 3 } }
identities = { owners = ["acme-owner"] }
engines = { coordinator = "codex", trivial = { order = ["claude-code/sonnet"] }, default = { order = ["codex/gpt-6.1-sol", "claude-code/sonnet"], effort = "medium" }, deep = { order = ["codex/gpt-6.1-sol"] } }
paths = { state_dir = "/srv/crew-state", worktree_root = "/srv/wt" }

[repos.widgets]
repo = "acme/widgets"

[repos.gadgets]
repo = "acme/gadgets"
default_branch = "trunk"
merge_grant = "docs PRs"
train_window = 120
sensitive = ["billing/**"]
precheck = { enabled = true, lint = "make lint" }
"""


class TeamFileTest(unittest.TestCase):
    def resolve(self, text, ref=""):
        """Resolve teams/ext.toml (plus #ref) with no default layer; return (merged, provenance, problems)."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ext.toml")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            saved, cc.DEFAULT_PROFILE = cc.DEFAULT_PROFILE, os.path.join(d, "absent.toml")
            try:
                merged, prov, problems, layers = cc.resolve_profile(path + ref)
            finally:
                cc.DEFAULT_PROFILE = saved
        return merged, prov, [p.replace(d + os.sep, "") for p in problems], layers

    def test_repo_sections_layer_over_the_team(self):
        merged, prov, problems, layers = self.resolve(TEAM, "#gadgets")
        self.assertEqual((problems, layers), ([], ["core", "team", "repo"]))
        self.assertEqual((merged["repo"], prov["repo.name"]), ({"owner": "acme", "name": "gadgets", "default_branch": "trunk"}, "repo"))
        opts = merged["runtime"]["options"]
        self.assertEqual((opts["merge_grant"], opts["train_window"], opts["builders"]), ("docs PRs", 120, 3))
        self.assertEqual((merged["sensitive"]["paths"], merged["builder"]["precheck"]["lint"]), (["billing/**"], "make lint"))
        self.assertEqual([merged["identities"][r]["gh_user"] for r in ("builder", "reviewer")], ["acme-bot", "acme-reviewer"])
        self.assertEqual((merged["identities"]["builder"]["name"], prov["identities.builder.name"]), ("Ben", "team"))
        self.assertEqual((merged["paths"]["state_dir"], opts["session"]), ("/srv/crew-state/ext", "crew-team-ext"))
        self.assertEqual(merged["backends"]["change"]["name"], "github")
        merged, prov, problems, _ = self.resolve(TEAM, "#widgets")
        self.assertEqual((problems, merged["repo"]["name"], merged["runtime"]["options"]["merge_grant"]), ([], "widgets", "none"))

    def test_repo_selection(self):
        self.assertEqual(self.resolve(TEAM)[2], ["ext.toml:repos: lists 2 repos; select one as ext.toml#<repo>"])
        self.assertEqual(self.resolve(TEAM, "#nope")[2], ["ext.toml:repos: names no repo 'nope' (repos: widgets, gadgets)"])
        one = TEAM[:TEAM.index("[repos.gadgets]")]
        self.assertEqual(self.resolve(one)[0]["repo"]["name"], "widgets")
        self.assertEqual(self.resolve(VALID, "#widgets")[2],
                         ["ext.toml:(file): not a team file; ext.toml#widgets needs [team] and [repos.<name>]"])

    def test_repo_sections_take_only_allowlisted_keys(self):
        bad = TEAM.replace('repo = "acme/widgets"', 'repo = "acme/widgets"\nbuilders = 9\nidentities = {}')
        problems = self.resolve(bad, "#widgets")[2]
        allowed = "repo, default_branch, precheck, sensitive, merge_grant, mirror_deferral, lone_pr_land, train_min, " \
            "train_window, train_local_checks"
        self.assertEqual(problems, ["ext.toml:repos.widgets.builders: not allowed in a repo section (team-only; allowed: %s)" % allowed,
                                    "ext.toml:repos.widgets.identities: not allowed in a repo section (team-only; allowed: %s)" % allowed])
        problems = self.resolve(TEAM.replace("[team]\n", '[team]\nmerge_grant = "x"\n').replace(
            'repo = "acme/widgets"', 'repo = "widgets"'), "#widgets")[2]
        self.assertEqual(problems, ["ext.toml:team.merge_grant: unknown team key (per-repo; set it in [repos.<name>])",
                                    "ext.toml:repos.widgets.repo: expected <owner>/<name>"])
        self.assertIn("ext.toml[repos.gadgets]:runtime.options.train_window: expected integer, got string",
                      self.resolve(TEAM.replace("train_window = 120", 'train_window = "2m"'), "#gadgets")[2])

    def test_legacy_profile_is_a_one_repo_team(self):
        """VALID as a one-repo team file resolves to the same values; only the team state root and session differ."""
        team = TEAM[:TEAM.index("[repos.widgets]")].replace(
            'personas = { builder = "Ben", reviewer = "Vera" }\n', "") + '[repos.widgets]\nrepo = "acme/widgets"\n'
        with tempfile.TemporaryDirectory() as d:
            legacy = os.path.join(d, "crew.toml")
            with open(legacy, "w", encoding="utf-8") as f:
                f.write(VALID)
            saved, cc.DEFAULT_PROFILE = cc.DEFAULT_PROFILE, os.path.join(d, "absent.toml")
            try:
                old = cc.resolve_profile(legacy)[0]
            finally:
                cc.DEFAULT_PROFILE = saved
        new = self.resolve(team)[0]
        self.assertEqual(new["paths"].pop("state_dir"), "/srv/crew-state/ext")
        self.assertEqual(new["runtime"]["options"].pop("session"), "crew-team-ext")
        del old["paths"]["state_dir"]
        self.assertEqual(new, old)

# --- pack manifest folding (13.15, #127) ---
GITHUB_MANIFEST = read(os.path.join(ROOT, "packs", "github", "manifest.toml"))


def resolve_with_packs(project, manifest):
    """Run `resolve` with cc.PACKS_DIR pointed at a temp dir holding github/manifest.toml (None: no manifest)."""
    with tempfile.TemporaryDirectory() as packs:
        if manifest is not None:
            os.makedirs(os.path.join(packs, "github"))
            with open(os.path.join(packs, "github", "manifest.toml"), "w", encoding="utf-8") as f:
                f.write(manifest)
        saved, cc.PACKS_DIR = cc.PACKS_DIR, packs
        try:
            code, lines = resolve(project)
        finally:
            cc.PACKS_DIR = saved
        return code, [ln.replace(packs + os.sep, "packs/") for ln in lines]


class ManifestFoldTest(unittest.TestCase):
    def test_external_backend_by_manifest_path(self):
        manifest = GITHUB_MANIFEST.replace('name = "github"', 'name = "example"')
        manifest = manifest.replace('[pack]\n', '[pack]\neng_crew_version = "v1.0.0"\n')
        with tempfile.TemporaryDirectory() as d:
            pack, project = os.path.join(d, "manifest.toml"), os.path.join(d, "crew.toml")
            with open(pack, "w") as f:
                f.write(manifest)
            with open(project, "w") as f:
                f.write(VALID.replace('[backends.review]\nname = "github"',
                                     '[backends.review]\nname = "example"\n'
                                     'capabilities = { post-verdict = "emulated (COMMENT review)" }'))
            profile, provenance, problems, _ = cc.resolve_profile(project, pack_manifest=pack)
            self.assertEqual(problems, [])
            self.assertEqual(profile["backends"]["review"]["name"], "example")
            self.assertEqual(provenance["backends.review.capabilities.list-verdicts"], "external-pack")
            self.assertEqual(provenance["backends.review.capabilities.post-verdict"], "project")
            self.assertEqual(provenance["backends.change.capabilities.land"], "pack:github")
            for command in (["validate", project, "--pack-manifest", pack],
                            ["resolve", "--project", project, "--pack-manifest", pack]):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cc.main(command), 0)
            with open(project, "a") as f:
                f.write('toolchain_bin = "/opt/bin"\nlive_dir = "/srv/live"\neng_crew = "/srv/eng-crew"\n')
            for command in (["validate", project], ["resolve", "--project", project]):
                command += ["--install", "--pack-manifest", pack]
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cc.main(command), 0)
            with open(project) as f:
                concrete = f.read()
            with open(project, "w") as f:
                f.write(concrete.replace('owner = "acme"', 'owner = "<owner>"'))
            for command in (["validate", project], ["resolve", "--project", project]):
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cc.main(command + ["--install", "--pack-manifest", pack]), 1)
                self.assertIn("repo.owner: unfilled install-time placeholder <owner>", out.getvalue())
            with open(project, "w") as f:
                f.write(concrete)
            self.assertTrue(cc.resolve_profile(project)[2])
            org = os.path.join(d, "profile.toml")
            with open(org, "w") as f:
                f.write('[repo]\nname = "org-default"\n')
            self.assertEqual(cc.resolve_profile(project, org)[2], [])
            with open(project, "a") as f:
                f.write('pack = "."\n')
            profile, provenance, problems, layers = cc.resolve_profile(project)
            self.assertEqual(problems, [])
            self.assertEqual(layers, ["core", "default", "org", "project"])
            self.assertEqual(profile["repo"]["name"], "widgets")
            self.assertEqual(provenance["backends.review.capabilities.list-verdicts"], "external-pack")
            for bad in (manifest.replace('eng_crew_version = "v1.0.0"\n', ''),
                        manifest.replace('list-verdicts = "supported"', 'list-verdicts = "invalid"'),
                        '[pack\n'):
                with open(pack, "w") as f:
                    f.write(bad)
                self.assertTrue(cc.resolve_profile(project, pack_manifest=pack)[2])
            os.unlink(pack)
            self.assertTrue(cc.resolve_profile(project, pack_manifest=pack)[2])

    def test_external_manifest_name_and_pin(self):
        manifest = GITHUB_MANIFEST.replace('name = "github"', 'name = "example"')
        self.assertEqual(validate(manifest)[0], 1)
        pinned = manifest.replace('[pack]\n', '[pack]\neng_crew_version = "v1.0.0"\n')
        self.assertEqual(validate(pinned)[0], 0)
        self.assertEqual(validate(pinned.replace('name = "example"', 'name = "../example"'))[0], 1)

    def test_manifest_capabilities_fold_under_profile(self):
        project = VALID.replace('[backends.review]\nname = "github"', '[backends.review]\nname = "github"\n'
                                'capabilities = { post-verdict = "emulated (COMMENT review)" }')
        code, lines = resolve(project)
        self.assertEqual(code, 0, lines)
        self.assertIn('backends.change.capabilities.land = "supported"  # pack:github', lines)
        self.assertIn('backends.review.capabilities.post-verdict = "emulated (COMMENT review)"  # project', lines)
        self.assertIn('backends.review.capabilities.list-verdicts = "supported"  # pack:github', lines)

    def test_manifest_unsupported_counts(self):
        bad = re.sub(r'(post-verdict|request-rereview) = "supported"', r'\1 = "unsupported"', GITHUB_MANIFEST)
        code, lines = resolve_with_packs(VALID, bad)
        self.assertEqual(code, 1, lines)
        self.assertIn("packs/github/manifest.toml:backends.review.capabilities.post-verdict: unsupported leaves I2 "
                      "with no other operation keeping it; profile unsupported (docs/interfaces.md)", lines)
        rescued = VALID.replace('[backends.review]\nname = "github"', '[backends.review]\nname = "github"\n'
                                'capabilities = { post-verdict = "supported" }')
        self.assertEqual(resolve_with_packs(rescued, bad)[0], 0)

    def test_manifest_undeclared_counts(self):
        missing = re.sub(r"\n(post-verdict|request-rereview) = .*", "", GITHUB_MANIFEST)
        code, lines = resolve_with_packs(VALID, missing)
        self.assertEqual(code, 1, lines)
        self.assertIn("(resolved):backends.review.capabilities.post-verdict: undeclared (counts as unsupported) "
                      "leaves I2 with no other operation keeping it; profile unsupported (docs/interfaces.md)", lines)
        code, lines = resolve_with_packs(VALID, None)
        self.assertEqual(code, 1, lines)
        self.assertTrue(any("undeclared (counts as unsupported) leaves I1 " in ln for ln in lines), lines)

    def test_broken_manifest_fails(self):
        code, lines = resolve_with_packs(VALID, "[pack\n")
        self.assertEqual(code, 1, lines)
        self.assertTrue(lines[0].startswith("packs/github/manifest.toml:(toml): invalid TOML"), lines)

    def test_manifest_version_pin_validates(self):
        pinned = GITHUB_MANIFEST.replace('[pack]\n', '[pack]\neng_crew_version = "0123456789abcdef0123456789abcdef01234567"\n')
        self.assertEqual(validate(pinned), (0, ["crew-config: OK (crew.toml)"]))
        self.assertIn("crew.toml:pack.eng_crew_version: expected string, got integer",
                      validate(pinned.replace('"0123456789abcdef0123456789abcdef01234567"', "1"))[1])


# --- host inventory and project affinity (20.2, #204) ---
HOSTS = """
[hosts.host-a]
primary = true
capabilities = { os = "macos", arch = "arm64", engines = ["claude-code", "codex"] }
max_runs = 2

[hosts.host-b]
capabilities = { os = "linux", arch = "x86_64", devices = ["ios-simulator"], engines = ["codex"] }
max_runs = 4
roles = ["reviewer"]
root = "/srv/crew"

[placement]
hosts = ["host-a", "host-b"]

[[placement.rules]]
role = "reviewer"
pass = "validate"
paths = ["ios/**"]
needs = { devices = ["ios-simulator"] }
"""
OK = (0, ["crew-config: OK (crew.toml)"])


class HostInventoryTest(unittest.TestCase):
    assertFails = ValidateTest.assertFails

    def test_inventory_validates_and_is_optional(self):
        self.assertEqual(validate(VALID + HOSTS), OK)
        self.assertEqual(validate(VALID), OK)

    def test_doc_example_validates(self):
        doc = read(os.path.join(ROOT, "docs", "profile.md")).split("### `[hosts.<name>]` and `[placement]`", 1)[1]
        self.assertEqual(validate(VALID + re.search(r"```toml\n(.*?)```", doc, re.S).group(1)), OK)

    def test_secret_pattern_rejected(self):
        token = "ghp_" + "B" * 36  # built at runtime so the repo never holds a token
        code, lines = validate(VALID + HOSTS.replace('root = "/srv/crew"', 'root = "/srv/%s"' % token))
        self.assertEqual(code, 1)
        self.assertIn("crew.toml:hosts.host-b.root: token-shaped value (GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)); "
                      "refer to credentials by mechanism", lines)
        self.assertFails(VALID + HOSTS.replace('root = "/srv/crew"', 'toolchain_bin = "ssh://ops:" "hunter2@host-b/bin"'
                                               .replace('" "', "")),
                         "crew.toml:hosts.host-b.toolchain_bin: token-shaped value (URL with embedded credentials); "
                         "refer to credentials by mechanism")

    def test_host_named_by_overlay_name_only(self):
        for bad in ["10.0.0.7", "fd7a::7", "ops@host-b", "host-b:22", "Host_B"]:
            text = HOSTS.replace("[hosts.host-b]", '[hosts."%s"]' % bad).replace('"host-b"', '"%s"' % bad)
            self.assertFails(VALID + text, "crew.toml:hosts.%s: expected an overlay network name ([a-z0-9-], "
                             "1-63 characters); no IP literal, user@ or :port" % bad)

    def test_unknown_capability(self):
        self.assertFails(VALID + HOSTS.replace('arch = "arm64",', 'arch = "arm64", gpu = "a100",'),
                         "crew.toml:hosts.host-a.capabilities.gpu: unknown key")
        self.assertFails(VALID + HOSTS.replace('devices = ["ios-simulator"], engines', 'devices = ["usb-camera"], engines'),
                         "crew.toml:hosts.host-b.capabilities.devices[0]: unknown value 'usb-camera' (expected one of: "
                         "ios-simulator, ios-device, android-emulator, android-device)")
        self.assertFails(VALID + HOSTS.replace('os = "linux"', 'os = "windows"'),
                         "crew.toml:hosts.host-b.capabilities.os: unknown value 'windows' (expected one of: linux, macos)")
        self.assertFails(VALID + HOSTS.replace('engines = ["codex"]', 'engines = ["unknown"]'),
                         "crew.toml:hosts.host-b.capabilities.engines[0]: unknown value 'unknown' "
                         "(expected one of: claude-code, codex, muse, opencode, pi, cursor)")
        self.assertFails(VALID + HOSTS.replace('needs = { devices', 'needs = { gpu = "a100", devices'),
                         "crew.toml:placement.rules[0].needs.gpu: unknown key")
        self.assertFails(VALID + HOSTS.replace("max_runs = 4", 'max_runs = 4\naddress = "host-b"'),
                         "crew.toml:hosts.host-b.address: unknown key")

    def test_required_keys_and_types(self):
        self.assertFails(VALID + HOSTS.replace("max_runs = 4\n", ""), "crew.toml:hosts.host-b.max_runs: missing required key")
        self.assertFails(VALID + HOSTS.replace('os = "linux", ', ""), "crew.toml:hosts.host-b.capabilities.os: missing required key")
        self.assertFails(VALID + HOSTS.replace("max_runs = 4", "max_runs = 0"), "crew.toml:hosts.host-b.max_runs: must be >= 1, got 0")
        self.assertFails(VALID + HOSTS.replace("primary = true", 'primary = "yes"'),
                         "crew.toml:hosts.host-a.primary: expected boolean, got string")

    def test_exactly_one_primary(self):
        self.assertFails(VALID + HOSTS.replace("primary = true\n", ""),
                         "crew.toml:hosts: expected exactly one host with primary = true, got 0")
        self.assertFails(VALID + HOSTS.replace("max_runs = 4", "max_runs = 4\nprimary = true"),
                         "crew.toml:hosts: expected exactly one host with primary = true, got 2")

    def test_placement(self):
        self.assertFails(VALID + '[placement]\nhosts = ["host-a"]\n', "crew.toml:placement: needs a [hosts] table")
        self.assertFails(VALID + HOSTS.replace('hosts = ["host-a", "host-b"]', 'hosts = ["host-a", "host-c"]'),
                         "crew.toml:placement.hosts[1]: names no host in [hosts]: 'host-c'")
        self.assertFails(VALID + HOSTS.replace('roles = ["reviewer"]', 'roles = ["coordinator"]'),
                         "crew.toml:hosts.host-b.roles[0]: unknown value 'coordinator' (expected one of: builder, reviewer)")
        self.assertFails(VALID + HOSTS.replace('hosts = ["host-a", "host-b"]', 'hosts = ["host-b"]'),
                         "crew.toml:placement.hosts: no host here takes role builder (default: the primary host)")
        no_placement = HOSTS.split("[placement]")[0]
        self.assertEqual(validate(VALID + no_placement), OK)
        self.assertFails(VALID + no_placement.replace("max_runs = 2", 'max_runs = 2\nroles = ["builder"]'),
                         "crew.toml:placement.hosts: no host here takes role reviewer (default: the primary host)")

    def test_rule_needs_and_pass(self):
        self.assertFails(VALID + HOSTS.replace('needs = { devices = ["ios-simulator"] }', 'needs = { devices = ["android-emulator"] }'),
                         "crew.toml:placement.rules[0].needs: no host taking role reviewer meets these needs")
        self.assertFails(VALID + HOSTS.replace('role = "reviewer"\npass = "validate"', 'role = "builder"'),
                         "crew.toml:placement.rules[0].needs: no host taking role builder meets these needs")
        self.assertEqual(validate(VALID + HOSTS.replace('needs = { devices', 'needs = { os = "linux", arch = "x86_64", devices')), OK)
        self.assertFails(VALID + HOSTS.replace('pass = "validate"', 'pass = "land"'),
                         "crew.toml:placement.rules[0].pass: unknown value 'land' (expected one of: review, validate)")
        self.assertFails(VALID + HOSTS.replace('paths = ["ios/**"]\n', "").replace('needs = { devices = ["ios-simulator"] }\n', ""),
                         "crew.toml:placement.rules[0].needs: missing required key")

    def test_hosts_need_tmux(self):
        grok = VALID.replace('name = "tmux"\noptions = { builders = 3 }', 'name = "grok-bot"')
        self.assertFails(grok + HOSTS, "crew.toml:hosts: a host inventory needs runtime tmux, got 'grok-bot'")

    def test_resolve_merges_hosts_across_layers(self):
        org = HOSTS.split("[placement]")[0]
        project = '[hosts.host-c]\ncapabilities = { os = "linux", arch = "arm64", engines = ["codex"] }\nmax_runs = 1\n' \
                  '[placement]\nhosts = ["host-c", "host-a"]\n'
        lines = ResolveTest.assertResolves(self, ['hosts.host-a.max_runs = 2  # org', 'hosts.host-c.max_runs = 1  # project',
                                                  'placement.hosts = ["host-c", "host-a"]  # project'],
                                           project, default=VALID, org=org)
        self.assertNotIn("placement.rules", "\n".join(lines))


class SensitiveTest(unittest.TestCase):
    def test_defaults_match_root_and_nested_security_paths(self):
        paths = [".github/workflows/release.yml"] + [prefix + directory + "/change.py"
                 for prefix in ["", "src/"]
                 for directory in ["auth", "secrets", "permissions", "access-control", "migrations", "deletions"]]
        self.assertEqual(set(cc.sensitive_matches({}, paths)), set(paths))
        self.assertEqual(cc.sensitive_matches({}, ["docs/auth.md", "src/authentication/change.py",
                                                   ".github/ISSUE_TEMPLATE/bug.md", "README.md"]), {})

    def test_profile_additions_cannot_remove_defaults_and_globs_respect_segments(self):
        profile = {"sensitive": {"paths": ["infra/iam/*", "scripts/drop-?.py", "docs/protocol.md"]}}
        paths = ["infra/iam/policy.json", "infra/iam/nested/policy.json", "scripts/drop-a.py",
                 "scripts/drop-all.py", "docs/protocol.md", "auth/login.py"]
        matches = cc.sensitive_matches(profile, paths)
        self.assertEqual(set(matches), {"infra/iam/policy.json", "scripts/drop-a.py", "docs/protocol.md", "auth/login.py"})
        self.assertIn("auth/login.py", cc.sensitive_matches({"sensitive": {"paths": []}}, paths))

    def test_validation_and_layer_replacement(self):
        self.assertEqual(validate(VALID + '\n[sensitive]\npaths = []\n')[0], 0)
        for paths in ['"auth/**"', '[1]', '[""]', '["/auth/**"]', '["src/../auth/**"]']:
            self.assertEqual(validate(VALID + '\n[sensitive]\npaths = ' + paths + '\n')[0], 1)
        code, lines = resolve('[sensitive]\npaths = ["project/**"]\n', default=VALID,
                              org='[sensitive]\npaths = ["org/**"]\n')
        self.assertEqual(code, 0, lines)
        self.assertIn('sensitive.paths = ["project/**"]  # project', lines)

    def test_cli_reports_matches_and_rejects_bad_config(self):
        with tempfile.TemporaryDirectory() as d:
            project = os.path.join(d, "crew.toml")
            for config, paths, status, label in [(VALID, "auth/login.py\n", 0, "crew:sensitive"),
                                                 (VALID, "README.md\n", 0, None),
                                                 (VALID + '\n[sensitive]\npaths = [1]\n', "README.md\n", 1, None)]:
                with open(project, "w") as f:
                    f.write(config)
                out = io.StringIO()
                with patch("sys.stdin", io.StringIO(paths)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    code = cc.main(["sensitive", "--project", project])
                self.assertEqual(code, status)
                if not status:
                    self.assertEqual(json.loads(out.getvalue())["label"], label)
                else:
                    self.assertEqual(out.getvalue(), "")


class RecordedPackTest(unittest.TestCase):
    def test_pack_path_schema(self):
        self.assertEqual(validate(VALID + '\npack = "org"\n')[0], 0)
        self.assertEqual(validate(VALID + '\npack = 1\n')[0], 1)
        self.assertEqual(validate(VALID + '\npack = " "\n')[0], 1)

    def test_recorded_pack_resolution_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as d:
            project = os.path.join(d, "crew.toml")
            pack = os.path.join(d, "org")
            os.mkdir(pack)
            org = os.path.join(pack, "profile.toml")
            with open(org, "w") as f:
                f.write('[identities.coordinator]\ntitle = "Org lead"\n[runtime.options]\nbuilders = 4\n')
            for directory in ("org", pack):
                with open(project, "w") as f:
                    f.write(VALID + '\npack = "%s"\n' % directory)
                profile, prov, problems, layers = cc.resolve_profile(project)
                self.assertEqual(problems, [])
                self.assertEqual(layers, ["core", "default", "org", "project"])
                self.assertEqual(profile["identities"]["coordinator"]["title"], "Org lead")
                self.assertEqual(prov["identities.coordinator.title"], "org")
                self.assertEqual(profile["runtime"]["options"]["builders"], 3)
            other = os.path.join(d, "override.toml")
            with open(other, "w") as f:
                f.write('[identities.coordinator]\ntitle = "Explicit lead"\n')
            self.assertEqual(cc.resolve_profile(project, other)[0]["identities"]["coordinator"]["title"],
                             "Explicit lead")
            with open(org, "w") as f:
                f.write('[invalid\n')
            self.assertTrue(cc.resolve_profile(project)[2])
            os.unlink(org)
            self.assertEqual(cc.resolve_profile(project)[2], [])
            os.rmdir(pack)
            self.assertTrue(any("paths.pack: pack directory missing" in p for p in cc.resolve_profile(project)[2]))


class InstallValidationTest(unittest.TestCase):
    def test_install_placeholders_rejected_with_key_paths(self):
        for original, leftover, key in [('"acme"', '"<owner>"', "repo.owner"),
                                        ('"acme-owner"', '"<user-login>"', "identities.owners[0]"),
                                        ('"/srv/crew-state"', '"/srv/<state-dir>"', "paths.state_dir")]:
            text = VALID.replace(original, leftover)
            self.assertEqual(validate(text)[0], 0)
            code, lines = validate(text, install=True)
            self.assertEqual(code, 1)
            self.assertTrue(any(key + ": unfilled install-time placeholder" in line for line in lines), lines)

    def test_runtime_placeholders_and_concrete_values_stay_allowed(self):
        text = VALID.replace('builders = 3', 'builders = 3, notes = { builder = ["<n>-<head-sha>.md"] }')
        self.assertEqual(validate(text, install=True)[0], 0)
        self.assertEqual(validate(VALID, install=True)[0], 0)

    def test_install_resolve_scans_effective_profile(self):
        with tempfile.TemporaryDirectory() as d:
            project, org = os.path.join(d, "crew.toml"), os.path.join(d, "org.toml")
            with open(project, "w") as f:
                f.write(VALID)
            with open(org, "w") as f:
                f.write('[paths]\ntoolchain_bin = "/opt/bin"\nlive_dir = "/srv/live"\neng_crew = "/srv/eng-crew"\n')
            for extra, expected in (([], 0), (["--install"], 1),
                                    (["--install", "--org-profile", org], 0)):
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    code = cc.main(["resolve", "--project", project] + extra)
                self.assertEqual(code, expected, out.getvalue())
                if expected:
                    self.assertIn("paths.toolchain_bin: unfilled install-time placeholder <toolchain-bin>",
                                  out.getvalue())


if __name__ == "__main__":
    unittest.main()
