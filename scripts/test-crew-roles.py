#!/usr/bin/env python3
"""Role definition schema tests and equivalence with tmux runtime metadata (stdlib only).

The registry is the union of roles/eng/<role>.toml. Included by CI's test-crew-*.py glob.
"""
import ast
import contextlib
import copy
import io
import importlib.util
import importlib.machinery
from pathlib import Path
import re
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("crew_roles", ROOT / "scripts/crew-roles.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)
DATA = {p.stem: tomllib.loads(p.read_text()) for p in sorted((ROOT / "roles/eng").glob("*.toml"))}
PROFILE = tomllib.loads((ROOT / "profiles/default.toml").read_text())
PROFILE["runtime"]["options"] = {k: v for k, (_, v) in registry.cc.RUNTIME_OPTIONS["tmux"].items()}


def constant(file, name):
    for node in ast.parse((ROOT / file).read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{file}: missing {name}")


class RegistryTests(unittest.TestCase):
    def errors(self, data):
        errors = []
        registry.validate(data, lambda key, reason: errors.append(f"{key}: {reason}"), PROFILE)
        return errors

    def test_valid(self):
        self.assertEqual(self.errors(DATA), [])
        self.assertEqual(registry.main([str(ROOT / "roles/eng")]), 0)

    def test_equivalence(self):
        roles = registry.cc.ROLE_REGISTRY
        self.assertEqual(roles, {r: {k: v for k, v in t.items() if k != "schema_version"} for r, t in DATA.items()})
        loader = importlib.machinery.SourceFileLoader("crew_cli", str(ROOT / "scripts/crew"))
        runtime = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(runtime)
        bands = runtime.BANDS
        self.assertEqual({r: tuple(v["window_band"]) for r, v in roles.items()}, dict(coordinator=(0, 0), **bands))
        self.assertEqual({r: v["passes"] for r, v in roles.items()}, dict(coordinator=["coordinate"], **runtime.PASSES))
        self.assertEqual({r: roles[r]["display_name"].lower() for r in bands}, runtime.NAMES)
        self.assertEqual(roles["coordinator"]["display_name"].lower(), "ash")
        self.assertEqual({r: v["cap_key"] for r, v in roles.items() if "cap_key" in v}, runtime.CAPS)
        self.assertEqual({e: r for r, v in roles.items() for e in v["events"]["tmux"]}, runtime.CONSUMER)
        spec = importlib.util.spec_from_file_location("crew_render", ROOT / "scripts/crew-render.py")
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        self.assertEqual(renderer.ROLES, roles)
        examples = re.findall(r"```toml\n# roles/eng/([a-z-]+)\.toml\n(.*?)```", (ROOT / "docs/roles-registry.md").read_text(), re.S)
        self.assertTrue(examples)
        for r, text in examples:
            self.assertEqual(DATA[r], tomllib.loads(text))
        self.assertEqual({r: v["identity_key"] for r, v in roles.items()}, {r: "identities." + r for r in roles})
        self.assertEqual(roles["reviewer"]["marker_role"], "reviewer-validator")
        for relation in ("engine_independent_of", "identity_independent_of"):
            self.assertEqual(roles["reviewer"][relation], "builder")
        for r, v in roles.items():
            self.assertEqual(v["templates"], {"tmux": [f"templates/runtimes/tmux/{r}.md"]})
            self.assertEqual(v["engine_source"], "coordinator" if r == "coordinator" else "tier")
        self.assertEqual(roles["builder"]["change_pass"], "fix")
        self.assertEqual(roles["builder"]["inputs"], {"build": ["issue"], "fix": ["issue", "change"]})
        for p in roles["reviewer"]["passes"]:
            self.assertEqual(roles["reviewer"]["inputs"][p], ["change"])
        self.assertEqual({r: v["lifetime"] for r, v in roles.items()},
                         dict(coordinator="session", builder="issue", reviewer="pass", synthesizer="session", researcher="pass"))
        for r, expected in dict(coordinator="ash", builder="ben-318", reviewer="vera-123-r2-review", synthesizer="sam",
                                researcher="riley-318").items():
            self.assertEqual(roles[r]["window_name"].format(name=roles[r]["display_name"].lower(), issue=318,
                                                           change=123, round=2, **{"pass": "review"}), expected)

    def test_invalid_schema(self):
        mutations = [
            ("builder", "schema_version", True, "schema_version"),
            ("builder", "schema_version", 2, "schema_version"),
            ("builder", "rank", 0, "positive integer"),
            ("builder", "unknown", 1, "unknown key"),
            ("builder", "display_name", "", "nonempty"),
            ("builder", "identity_key", "identities.missing", "unresolved identity"),
            ("builder", "cap_key", "runtime.options.train_local_checks", "positive integer"),
            ("builder", "window_band", [True, 19], "ordered nonnegative"),
            ("builder", "window_band", [19, 10], "ordered nonnegative"),
            ("builder", "window_band", [0, 19], "overlapping"),
            ("builder", "change_pass", "land", "supported pass"),
            ("builder", "passes", ["build", "build"], "distinct pass"),
            ("builder", "passes", ["unknown"], "unknown value"),
            ("builder", "inputs", {"build": ["issue"]}, "keys must equal"),
            ("builder", "inputs", {"build": ["secret"], "fix": ["issue", "change"]}, "issue/change"),
            ("builder", "window_name", "{change}", "unavailable"),
            ("builder", "window_name", "{name.__class__}", "unsupported pattern"),
            ("builder", "window_name", "{name", "invalid pattern"),
            ("reviewer", "engine_independent_of", "reviewer", "another role"),
            ("reviewer", "identity_independent_of", "missing", "another role"),
            ("builder", "templates", {"tmux": ["../templates/builder.md"]}, "repo-relative"),
            ("builder", "templates", {"tmux": ["templates/missing.md"]}, "repo-relative"),
            ("builder", "templates", {"tmux": []}, "at least one template"),
            ("builder", "events", {"tmux": ["new-head"]}, "already has a consumer"),
            ("builder", "events", {"tmux": ["unknown"]}, "unknown value"),
            ("builder", "events", {"missing": []}, "known runtime"),
            ("builder", "display_name", "Authorization: " + "Bearer literal-secret-value", "token-shaped"),
        ]
        for role, key, value, expected in mutations:
            with self.subTest(role=role, key=key, value=value):
                data = copy.deepcopy(DATA)
                data[role][key] = value
                self.assertTrue(any(expected in e for e in self.errors(data)), self.errors(data))
        data = copy.deepcopy(DATA)
        del data["builder"]["display_name"]
        self.assertTrue(any("missing required key" in e for e in self.errors(data)))
        self.assertTrue(any("at least one role" in e for e in self.errors({})))

    def test_main_reports_the_role_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            for role, table in DATA.items():
                text = (ROOT / "roles/eng" / (role + ".toml")).read_text()
                Path(tmp, role + ".toml").write_text(text.replace("window_band = [40, 44]", "window_band = [44, 40]"))
            Path(tmp, "broken.toml").write_text("display_name = \n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(registry.main([tmp]), 1)
            self.assertIn(f"{tmp}/broken.toml:(file): ", out.getvalue())
            Path(tmp, "broken.toml").unlink()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(registry.main([tmp]), 1)
            self.assertEqual(out.getvalue(), f"{tmp}/researcher.toml:window_band: expected two ordered nonnegative integers\n")


if __name__ == "__main__":
    unittest.main()
