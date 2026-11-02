#!/usr/bin/env python3
"""Role registry schema tests and equivalence with tmux runtime metadata (stdlib only).

Profile and renderer migration remains in 15.10. Included by CI's test-crew-*.py glob.
"""
import ast
import copy
import importlib.util
import importlib.machinery
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("crew_roles", ROOT / "scripts/crew-roles.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)
DATA = tomllib.loads((ROOT / "roles/eng.toml").read_text())
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
        self.assertEqual(registry.main([str(ROOT / "roles/eng.toml")]), 0)

    def test_equivalence(self):
        roles = DATA["roles"]
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
        example = re.search(r"```toml\n(.*?)```", (ROOT / "docs/roles-registry.md").read_text(), re.S).group(1)
        self.assertEqual(DATA, tomllib.loads(example))
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
                         dict(coordinator="session", builder="issue", reviewer="pass", synthesizer="session"))
        for r, expected in dict(coordinator="ash", builder="ben-318", reviewer="vera-123-r2-review", synthesizer="sam").items():
            self.assertEqual(roles[r]["window_name"].format(name=roles[r]["display_name"].lower(), issue=318,
                                                           change=123, round=2, **{"pass": "review"}), expected)

    def test_invalid_schema(self):
        mutations = [
            (None, "schema_version", True, "schema_version"),
            (None, "schema_version", 2, "schema_version"),
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
                (data["roles"][role] if role else data)[key] = value
                self.assertTrue(any(expected in e for e in self.errors(data)), self.errors(data))
        data = copy.deepcopy(DATA)
        del data["roles"]["builder"]["display_name"]
        self.assertTrue(any("missing required key" in e for e in self.errors(data)))


if __name__ == "__main__":
    unittest.main()
