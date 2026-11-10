"""Role registration seam tests (#1185; docs/roles-registry.md#adding-a-role), stdlib only.

A copy of this bundle gets one role definition, roles/eng/scout.toml, and the brief it binds,
templates/runtimes/tmux/scout.md, and nothing else. The scout reuses the researcher's lifecycle. Against a fake
tmux and gh it then validates and resolves with its identity and cap defaults, renders its brief, takes host
placement, `mdstack spawn` starts it and queues it at its cap, a `done:` ends its run, `mdstack route` closes it and
leaves the wake for the coordinator to relay, bootstrap's self-test requires its brief, and `mdstack kill` tears it
down and dequeues the next one. Run in CI.
"""
from argparse import Namespace
import importlib.util
from importlib.machinery import SourceFileLoader
import io
import contextlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import SCRIPTS, SpawnBase

ROLE = '''schema_version = 1
display_name = "Skye"
class = "internal"
seat = "cto"
escalation = ["coordinator"]
identity_key = "identities.scout"
marker_role = "scout"
passes = ["research"]
inputs = { research = ["issue"] }
engine_source = "tier"
templates = { tmux = ["templates/runtimes/tmux/scout.md"] }
events = { tmux = [] }
window_band = [45, 49]
window_name = "{name}-{issue}"
lifetime = "pass"
cap_key = "runtime.options.scouts"
identity_defaults = { name = "Skye", title = "Scout", emoji = "🧭" }
identity_optional = true
cap_default = 1
completion = "done"
relay = "coordinator"
placement = ["research"]
discovery = { tmux = "scout" }
'''
BRIEF = "# Scout brief\n\nSign as <ScoutEmoji> <ScoutBot> (<ScoutTitle>).\n"
BUNDLE = None


def setUpModule():
    global BUNDLE
    BUNDLE = tempfile.mkdtemp()
    root = os.path.join(BUNDLE, "eng-crew")
    shutil.copytree(os.path.dirname(SCRIPTS), root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".crew"))
    Path(root, "roles", "eng", "scout.toml").write_text(ROLE)
    Path(root, "templates", "runtimes", "tmux", "scout.md").write_text(BRIEF)


def tearDownModule():
    shutil.rmtree(BUNDLE)


def bundle(*parts):
    return os.path.join(BUNDLE, "eng-crew", *parts)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cli():
    """The bundle copy's crew CLI, in process (its crew_shared replaces any other in sys.modules)."""
    spec = importlib.util.spec_from_loader("crew_scout_cli", SourceFileLoader("crew_scout_cli", bundle("cli", "mdstack")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ScoutRole(SpawnBase):
    """The scout, added as one role definition, through every consumer."""

    def crew(self, *args, stdin="", **env):
        return subprocess.run([sys.executable, bundle("cli", "mdstack"), *args], input=stdin, capture_output=True,
                              text=True, env=dict(self.env, **env))

    def up(self):
        return self.crew("up", "--project", self.project, "--inputs", bundle("templates"))

    def test_validates_resolves_and_takes_placement(self):
        r = subprocess.run([sys.executable, bundle("core", "crew-roles.py"), bundle("roles", "eng")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        cc = load("crew_config_scout", bundle("core", "crew-config.py"))
        self.assertEqual(list(cc.ROLE_REGISTRY)[-1], "scout")
        merged, _, problems, _ = cc.resolve_profile(self.project)
        self.assertEqual(problems, [])
        self.assertEqual(merged["identities"]["scout"], {"name": "Skye", "title": "Scout", "emoji": "🧭",
                                                         "gh_user": merged["identities"]["coordinator"]["gh_user"]})
        self.assertEqual(merged["runtime"]["options"]["scouts"], 1)
        self.assertEqual(cc.PLACED_PASSES["scout"], ["research"])
        rendered = Path(self.state, "render", "runtime", "scout.md").read_text()
        self.assertIn("Sign as 🧭 Skye (Scout).", rendered)

    def test_spawn_queue_completion_relay_and_teardown(self):
        r = self.spawn("scout", "--issue", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("skye-7")
        self.assertEqual((rec["role"], rec["index"], rec["pass"], rec["args"]["tier"]), ("scout", 45, "research", "default"))
        r = self.spawn("scout", "--issue", "8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("queued: scout research issue #8 (scout cap reached", r.stdout)

        crew = cli()
        self.assertTrue(crew.finished(rec, "done: #7 finding posted"))
        self.put("status/skye-7.status", "done: #7 finding posted\n")
        route = crew.commands()["route"]
        args = Namespace(project=self.project, org_profile=None, timeout=1)
        values, _, state = crew.profile(args)
        with mock.patch.object(route, "reap") as reap, contextlib.redirect_stdout(io.StringIO()):
            consumed = route.route_record(args, values, state, {"window": "skye-7", "reason": "status",
                                                                "line": "done: #7 finding posted"})
        self.assertFalse(consumed, "the coordinator relays the result")
        reap.assert_called_once_with(args, "skye-7")

        r = self.crew("kill", "skye-7", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("crew: killed skye-7", r.stdout)
        self.assertIn("crew: started skye-8 (window 45", r.stdout)

    def test_bootstrap_self_test_requires_the_brief(self):
        bootstrap = cli().commands()["bootstrap"]
        rendered = Path(self.tmp, "rendered")
        (rendered / "runtime").mkdir(parents=True)
        for name in ("coordinator", "builder", "reviewer", "synthesizer"):
            (rendered / "runtime" / (name + ".md")).write_text("brief\n")
        self.assertEqual(bootstrap.missing_briefs(rendered, "tmux"), ["scout"])
        (rendered / "runtime" / "scout.md").write_text("brief\n")
        self.assertEqual(bootstrap.missing_briefs(rendered, "tmux"), [])


class ShippedDiscovery(unittest.TestCase):
    """The shipped roles keep the former self-test brief lists for tmux and grok-bot; session uses the tmux names (#1541)."""

    def test_former_brief_lists(self):
        spec = importlib.util.spec_from_loader("crew_shipped_cli", SourceFileLoader("crew_shipped_cli", os.path.join(os.path.dirname(SCRIPTS), "cli", "mdstack")))
        crew = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(crew)
        bootstrap = crew.commands()["bootstrap"]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(bootstrap.missing_briefs(tmp, "tmux"), ["coordinator", "builder", "reviewer", "synthesizer"])
            for name in ("coordinator-after-merge", "builder-b1", "reviewer-validator", "synthesizer"):
                Path(tmp, "runtime").mkdir(exist_ok=True)
                Path(tmp, "runtime", name + ".md").write_text("brief\n")
            self.assertEqual(bootstrap.missing_briefs(tmp, "grok-bot"), [])
            self.assertEqual(bootstrap.missing_briefs(tmp, "tmux"), ["coordinator", "builder", "reviewer"])
            self.assertEqual(bootstrap.missing_briefs(tmp, "session"), ["coordinator", "builder", "reviewer"])


if __name__ == "__main__":
    unittest.main()
