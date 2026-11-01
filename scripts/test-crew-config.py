#!/usr/bin/env python3
"""Offline tests for scripts/crew-config.py validate (stdlib only)."""
import contextlib
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("crew_config", os.path.join(HERE, "crew-config.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

CONCERNS = ["change", "review", "tracker", "state-tags", "markers", "ci", "events", "owner-channel"]

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


def validate(text):
    """Write text to a temp crew.toml, run `validate`, return (code, stdout lines)."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "crew.toml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cc.main(["validate", path])
        lines = [ln.replace(path, "crew.toml") for ln in out.getvalue().splitlines()]
        return code, lines


class ValidateTest(unittest.TestCase):
    def assertFails(self, text, expected):
        code, lines = validate(text)
        self.assertEqual(code, 1, lines)
        self.assertIn(expected, lines)

    def test_valid_profile(self):
        code, lines = validate(VALID)
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines, ["crew-config: OK (crew.toml)"])

    def test_doc_example_is_valid(self):
        with open(os.path.join(HERE, "..", "docs", "profile.md"), encoding="utf-8") as f:
            m = re.search(r"```toml\n(.*?)```", f.read(), re.S)
        code, lines = validate(m.group(1))
        self.assertEqual(code, 0, lines)

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

    def test_engines(self):
        self.assertFails(VALID.replace('trivial = { order = ["claude-code/sonnet"] }', 'trivial = { order = ["cursor/auto"] }'),
                         "crew.toml:engines.trivial.order[0]: unknown engine 'cursor' "
                         "(expected <engine>/<model>, engine one of: claude-code, codex, muse, opencode)")
        self.assertFails(VALID.replace('effort = "medium"', 'effort = "max"'),
                         "crew.toml:engines.default.effort: unknown value 'max' (expected one of: low, medium, high)")

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
        self.assertFails(ok.replace('fallback_engine = "claude-code"', 'fallback_engine = "cursor"'),
                         "crew.toml:engines.fallback_engine: unknown value 'cursor' "
                         "(expected one of: claude-code, codex, muse, opencode)")

    assertFails = ValidateTest.assertFails

    def test_manifest_validation(self):
        manifest = read(os.path.join(ROOT, "packs", "github", "manifest.toml"))
        self.assertFails(manifest.replace('name = "github"', 'name = "gitlab"', 1),
                         "crew.toml:pack.name: unknown value 'gitlab' (expected one of: github)")
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


class ResolveTest(unittest.TestCase):
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
        self.assertFails(VALID + HOSTS.replace('engines = ["codex"]', 'engines = ["cursor"]'),
                         "crew.toml:hosts.host-b.capabilities.engines[0]: unknown value 'cursor' "
                         "(expected one of: claude-code, codex, muse, opencode)")
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


if __name__ == "__main__":
    unittest.main()
