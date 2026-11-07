"""On-demand role lifecycle tests (#1231; docs/roles-registry.md#lifecycle), stdlib only.

A copy of this bundle gets two lifecycle roles and their briefs and nothing else: `analyst` (ephemeral, min 0, max 2,
idle_ttl 600, manual wake) and `scribe` (always-on, min = max = 1). Against a fake tmux and gh, `crew up` starts the
scribe's floor, `crew up analyst` starts instances up to max and then refuses, `crew up builder` is refused, and
the watcher's scale_down kills idle analysts to zero while it keeps a busy one, one with an unacknowledged inbox
message, the scribe at its min and every eng role run. Run in CI.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import SCRIPTS, SpawnBase

COMMON = '''schema_version = 1
identity_key = "identities.{role}"
marker_role = "{role}"
passes = ["research"]
inputs = {{ research = [] }}
engine_source = "tier"
templates = {{ tmux = ["templates/runtimes/tmux/{role}.md"] }}
events = {{ tmux = [] }}
window_name = "{{name}}"
lifetime = "session"
identity_optional = true
completion = "done"
relay = "coordinator"
'''
ROLES = {
    "analyst": COMMON.format(role="analyst") + '''display_name = "Ana"
window_band = [50, 52]
identity_defaults = { name = "Ana", title = "Analyst", emoji = "📊" }
lifecycle = { policy = "ephemeral", min = 0, max = 2, idle_ttl = 600, wake = ["manual"] }
''',
    "scribe": COMMON.format(role="scribe") + '''display_name = "Sol"
window_band = [53, 53]
identity_defaults = { name = "Sol", title = "Scribe", emoji = "📝" }
lifecycle = { policy = "always-on", min = 1, max = 1, idle_ttl = 600, wake = ["manual"] }
''',
}
BUNDLE = None


def setUpModule():
    global BUNDLE
    BUNDLE = tempfile.mkdtemp()
    root = os.path.join(BUNDLE, "eng-crew")
    shutil.copytree(os.path.dirname(SCRIPTS), root, ignore=shutil.ignore_patterns(".git", "__pycache__", ".crew"))
    for role, text in ROLES.items():
        Path(root, "roles", "eng", role + ".toml").write_text(text)
        Path(root, "templates", "runtimes", "tmux", role + ".md").write_text("# %s brief\n" % role)


def tearDownModule():
    shutil.rmtree(BUNDLE)


def bundle(*parts):
    return os.path.join(BUNDLE, "eng-crew", *parts)


def cli():
    """The bundle copy's crew CLI, in process."""
    spec = importlib.util.spec_from_loader("crew_lifecycle_cli",
                                           SourceFileLoader("crew_lifecycle_cli", bundle("scripts", "crew")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Lifecycle(SpawnBase):
    def crew(self, *args, stdin="", **env):
        return subprocess.run([sys.executable, bundle("scripts", "crew"), *args], input=stdin, capture_output=True,
                              text=True, env=dict(self.env, **env))

    def up(self):
        return self.crew("up", "--project", self.project, "--inputs", bundle("templates"))

    def up_role(self, role):
        return self.crew("up", role, "--project", self.project)

    def test_validates(self):
        r = subprocess.run([sys.executable, bundle("scripts", "crew-roles.py"), bundle("roles", "eng")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_up_starts_the_floor_and_role_instances_up_to_max(self):
        self.assertEqual(self.record("sol")["role"], "scribe")  # crew up in setUp started the always-on floor
        self.assertEqual(self.up_role("scribe").stdout, "crew: refusing up scribe: at its lifecycle max 1 (sol)\n")
        r = self.up_role("analyst")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rec = self.record("ana")
        self.assertEqual((rec["role"], rec["index"], rec["pass"], rec["item"]),
                         ("analyst", 50, "research", "on demand (crew up analyst)"))
        self.assertEqual(os.path.basename(rec["claim"]), "analyst-ana")
        r = self.up_role("analyst")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.record("ana2")["index"], 51)
        r = self.up_role("analyst")
        self.assertEqual((r.returncode, r.stdout), (1, "crew: refusing up analyst: at its lifecycle max 2 (ana, ana2)\n"))

    def test_eng_roles_keep_their_behaviour(self):
        r = self.up_role("builder")
        self.assertEqual(r.returncode, 2)
        self.assertIn("crew: refusing up builder: no lifecycle with the manual wake", r.stdout)
        self.assertFalse(any(name.startswith("ben") for name in os.listdir(os.path.join(self.state, "runs"))))

    def test_non_owner_starts_no_instance(self):
        """Another runtime holds the control record: neither crew up ROLE nor the floor starts a run (#1275 R1)."""
        p = Path(self.project)
        p.write_text(p.read_text().replace("[repo]\n", "[repo]\ncontrol_item = 99\n")
                     .replace("[runtime]\n", "[runtime]\ninstance = \"local\"\n"))
        marker = ("<!-- crew:v1 role=coordinator pass=handoff handoff=20261107-abcdef state=claimed from=none "
                  "to=grok-bot@box cmd-id=chat sha=" + "1" * 40 + " round=n/a verdict=n/a -->")
        gh = Path(self.tmp, "bin", "gh")
        gh.write_text(gh.read_text().replace("args = sys.argv[1:]\n", "args = sys.argv[1:]\nif args[0] == 'api':\n print(%r)\n"
                      " sys.exit(0)\n" % json.dumps([[{"user": {"login": "acme-bot"}, "body": marker}]])))
        before = (sorted(os.listdir(os.path.join(self.state, "runs"))), sorted(os.listdir(os.path.join(self.state, "claims"))),
                  len(self.windows()))
        r = self.up_role("analyst")
        self.assertEqual((r.returncode, r.stdout), (1, "crew: ownership: read-only; refusing start\n"))
        os.remove(os.path.join(self.state, "runs", "sol.json"))  # the floor is short again
        crew = cli()
        values, _, state = crew.profile(mock.Mock(project=self.project, org_profile=None))
        with mock.patch.dict(os.environ, self.env):
            self.assertEqual(crew.commands()["up"].start_instance(mock.Mock(project=self.project, org_profile=None),
                                                                  values, state, "scribe"), 1)
        after = (sorted(os.listdir(os.path.join(self.state, "runs"))), sorted(os.listdir(os.path.join(self.state, "claims"))),
                 len(self.windows()))
        self.assertEqual(after, ([n for n in before[0] if n != "sol.json"], before[1], before[2]))

    def test_scale_down_to_min(self):
        for _ in range(2):
            self.assertEqual(self.up_role("analyst").returncode, 0)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        crew = cli()
        up = crew.commands()["up"]
        values, session, state = crew.profile(mock.Mock(project=self.project, org_profile=None))
        now = time.time()
        activity = {"ana": now - 700, "ana2": now - 10, "sol": now - 7000, "ben-7": now - 7000}
        names = {rec["index"]: (n, rec) for n, rec in crew.runs(state)}

        def pane(_session, index):
            name, rec = names[index]
            return {"id": rec["pane_id"], "pid": "999999999", "dead": "0", "activity": str(int(activity[name])),
                    "tty": "", "command": ""}

        with mock.patch.object(crew.tmux, "pane", pane), mock.patch.dict(os.environ, self.env):
            self.assertEqual(up.scale_down(values, session, state, now), ["ana"])
            self.put("inbox/ana2.jsonl", json.dumps({"id": "m1"}) + "\n")
            self.assertEqual(up.scale_down(values, session, state, now + 700), [], "an unacknowledged message")
            self.put("status/ana2.status", "ack: m1\n")
            os.utime(os.path.join(state, "inbox", "ana2.jsonl"), (now - 5, now - 5))
            self.assertEqual(up.scale_down(values, session, state, now + 700), ["ana2"])
        self.assertEqual(sorted(n for n, _ in crew.runs(state)), ["ben-7", "sol"])


if __name__ == "__main__":
    import unittest
    unittest.main()
