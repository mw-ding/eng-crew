#!/usr/bin/env python3
"""Offline tests for scripts/crew-config.py validate (stdlib only)."""
import contextlib
import importlib.util
import io
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


if __name__ == "__main__":
    unittest.main()
