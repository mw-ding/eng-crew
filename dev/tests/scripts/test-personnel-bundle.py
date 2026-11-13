#!/usr/bin/env python3
"""Personnel producer entry point, fake-host loading and refusal controls."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/personnel-bundle.py"
FIXTURE = ROOT / "dev/tests/fixtures/personnel/fake-host.toml"
ROLES = ["eng/" + r for r in ("coordinator", "builder", "reviewer", "synthesizer", "researcher")]


class PersonnelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.producer = Path(cls.temp.name) / "producer"
        cls.producer.mkdir()
        # Snapshot the candidate, including new files, into an isolated producer.
        for name in ("scripts", "templates", "roles", "docs", "actions", "core", "profiles", "harnesses", "environments", "connectors", "cli", "packs", "dev", "changes", "memory", ".github"):
            shutil.copytree(ROOT / name, cls.producer / name)
        for path in ROOT.iterdir():
            if path.is_file() and path.name != ".git":
                shutil.copyfile(path, cls.producer / path.name)
        (cls.producer / "VERSION").write_text("v7.11.0\n")
        def git(*args):
            return subprocess.check_output(["git", "-C", str(cls.producer), *args], stderr=subprocess.PIPE).decode().strip()
        git("init", "-q")
        git("remote", "add", "origin", "https://github.com/example/mdstack.git")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "producer")
        cls.ref = git("rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "personnel"
        self.binding = Path(self.temp.name) / "binding.toml"
        self.binding.write_text(FIXTURE.read_text())

    def run_cli(self, roles=ROLES, ref=None):
        command = [sys.executable, str(SCRIPT), "--root", str(self.producer),
                   "--ref", ref or self.ref, "--binding", str(self.binding), "--out", str(self.out)]
        for role in roles:
            command += ["--role", role]
        return subprocess.run(command, capture_output=True, text=True)

    def refused(self, roles=ROLES, ref=None):
        result = self.run_cli(roles, ref)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("refused:", result.stderr)
        self.assertFalse(self.out.exists())
        print("negative control:", result.stderr.strip())

    def test_fake_host_load_and_idempotency(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        manifest = json.loads((self.out / "personnel.json").read_text())
        self.assertEqual(manifest["source"]["commit"], self.ref)
        self.assertEqual(manifest["roles"], sorted(ROLES))
        self.assertEqual(manifest["source"]["version"], "v7.11.0")
        self.assertIn("presentation", manifest["provenance"]["eng/builder"])
        for path, expected in manifest["files"].items():
            self.assertEqual(hashlib.sha256((self.out / path).read_bytes()).hexdigest(), expected)
        self.assertFalse(any((self.out / d).exists() for d in ("environments", "core", "cli", "harnesses", "connectors")))
        self.assertFalse(any(p.suffix in (".py", ".sh") for p in self.out.rglob("*")))
        for role in ROLES:
            name = role.split("/")[1]
            brief = self.out / f"briefs/eng/{name}.md"
            self.assertIn("synthesizer may", brief.read_text())
            policy = self.out / f"templates/policy/{name}/SKILL.md"
            self.assertTrue(policy.is_file())
            procedures = list(policy.parent.glob("skills/*/SKILL.md"))
            self.assertTrue(procedures)
            for p in [brief, policy, *procedures]:
                for target in re.findall(r"\]\(([^)]+)\)", p.read_text()):
                    if not target.startswith(("http", "#")):
                        self.assertTrue((p.parent / target.split("#")[0]).exists(), (p, target))
        for p in (self.out / "templates/policy").rglob("*.md"):
            self.assertNotRegex(p.read_text(), r"<op:[a-z][a-z0-9.-]*>")
        before = {str(p): p.stat().st_mtime_ns for p in self.out.rglob("*")}
        again = self.run_cli()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("unchanged", again.stdout)
        self.assertEqual(before, {str(p): p.stat().st_mtime_ns for p in self.out.rglob("*")})
        print("fake-host: 5 briefs and all procedures load; no terminal/core/CLI; hashes verified; rerun unchanged")

    def test_missing_collision_and_pin(self):
        for roles, ref in [(["eng/builder", "eng/unknown"], None), (["eng/builder"] * 2, None), (ROLES, "HEAD")]:
            with self.subTest(roles=roles, ref=ref):
                self.refused(roles, ref)

    def test_binding_and_authority_controls(self):
        valid = FIXTURE.read_text()
        mutations = [
            valid.replace('"head-bound-land" = true', '"head-bound-land" = false'),
            valid.replace('"heartbeat" = "fake-host heartbeat"', ''),
            valid.replace('"change.open" = "fake-host change.open"', ''),
            valid + '\nclass = "owner-facing"\n',
            valid + '\nmarker_role = "synthesizer"\n',
            valid + '\nengine_independent_of = "none"\n',
            valid + '\nescalation = []\n',
            valid + '\npasses = ["land"]\n',
            valid.replace('gaps = []', 'gaps = ["no independent validation"]'),
            valid.replace('extra_skills = []', 'extra_skills = ["outside/SKILL.md"]'),
            valid.replace('"land" = "fake-host land"', '"land" = "$CREW_BIN land"'),
        ]
        for text in mutations:
            with self.subTest(text=text[-90:]):
                self.binding.write_text(text)
                self.refused()
        self.binding.write_text(valid)
        self.assertEqual(self.run_cli().returncode, 0)
        print("restored control: valid binding installs")

    def test_additive_skill_provenance(self):
        self.binding.write_text(FIXTURE.read_text().replace('extra_skills = []',
            'extra_skills = ["templates/policy/researcher/skills/research/SKILL.md"]'))
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.out / "personnel.json").read_text())
        self.assertEqual(manifest["provenance"]["eng/builder"]["extra_skills"], "binding:fake-host@1.0.0")

    def test_unresolved_policy_control(self):
        path = self.producer / "templates/policy/builder/SKILL.md"
        original = path.read_text()
        try:
            path.write_text(original + '\n[Required policy](missing-policy.md)\n')
            def git(*args):
                return subprocess.check_output(["git", "-C", str(self.producer), *args], stderr=subprocess.PIPE).decode().strip()
            git("add", str(path))
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "negative control")
            self.refused(ref=git("rev-parse", "HEAD"))
        finally:
            path.write_text(original)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        print("restored policy: pinned valid source installs")

    def test_existing_content_is_not_overwritten(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        marker = self.out / "personnel.json"
        marker.write_text("consumer edit")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(marker.read_text(), "consumer edit")


if __name__ == "__main__":
    unittest.main()
