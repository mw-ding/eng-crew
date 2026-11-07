#!/usr/bin/env python3
"""Tests for core/crew-memory.py (#1230): core memory layout, size limits, personal-data refusal and the brief section.

Covers: the shipped memory/ passes; a stray file and an unregistered role fail the layout; each size limit at and
over the boundary; each personal-data kind refused with the knowledge connector route, and placeholders and dates
passing; the section's order, a missing role file, no memory at all, and problems returned with the section; the
CLI's exit code and output. Stdlib only. Run in CI.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SCRIPT = os.path.join(ROOT, "core", "crew-memory.py")
spec = importlib.util.spec_from_file_location("crew_memory", SCRIPT)
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)


class Memory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def rules(self):
        return [(rel, rule) for rel, _, rule, _ in memory.lint(self.root)]

    def test_shipped_memory_passes(self):
        self.assertEqual(memory.lint(ROOT), [])
        self.assertTrue(os.path.exists(os.path.join(ROOT, memory.OWNER)))
        for role in memory.crew_config.ROLE_REGISTRY:
            self.assertTrue(os.path.exists(os.path.join(ROOT, memory.ROLE % role)), role)

    def test_no_memory_dir_passes(self):
        self.assertEqual(memory.lint(self.root), [])

    def test_layout(self):
        self.write("memory/owner.md", "# Owner\n")
        self.write("memory/roles/builder.md", "# Builder\n")
        self.write("memory/notes.md", "x\n")
        self.write("memory/roles/intern.md", "x\n")
        self.assertEqual(self.rules(), [("memory/notes.md", "memory-layout"), ("memory/roles/intern.md", "memory-layout")])

    def test_size_limits(self):
        for rel, limit in ((memory.OWNER, memory.LIMITS["owner"]), (memory.ROLE % "reviewer", memory.LIMITS["role"])):
            with self.subTest(rel=rel):
                self.write(rel, "x" * limit)
                self.assertEqual(self.rules(), [])
                self.write(rel, "x" * (limit + 1))
                problems = memory.lint(self.root)
                self.assertEqual(problems, [(rel, 1, "memory-size", "%d bytes, over the %d-byte limit; curate it down"
                                             % (limit + 1, limit))])
                os.remove(os.path.join(self.root, rel))

    def test_personal_data_refused_and_routed(self):
        cases = [("Reach me at jane.doe@example.com.", "email address"),
                 ("Call (425) 555-0134 after six.", "phone number"),
                 ("Call +1 425 555 0134.", "phone number"),
                 ("Lives at 12 Elm Street.", "street address"),
                 ("Birthday is in May.", "personal detail"),
                 ("Ask my wife first.", "personal detail")]
        for line, kind in cases:
            with self.subTest(line=line):
                self.write(memory.OWNER, "# Owner\n\n- Prefers short replies.\n- %s\n" % line)
                self.assertEqual(memory.lint(self.root), [(memory.OWNER, 4, "memory-personal", "%s: %s"
                                                           % (kind, memory.ROUTE))])
                self.assertIn("knowledge connector", memory.ROUTE)

    def test_placeholders_dates_and_issue_refs_pass(self):
        self.write(memory.OWNER, "# Owner\n\n- Mail <user>@<domain> only in examples.\n"
                                 "- Decided 2026-11-07 at 09:00Z on #985 (comment 6704002487).\n"
                                 "- Sign as `@md-mt` on reviews; SHA 60bb806bc9f574e93ef8fa458cec79d88a613d3e.\n")
        self.assertEqual(memory.lint(self.root), [])

    def test_section(self):
        self.assertEqual(memory.section(self.root, "builder"), ("", []))
        self.write(memory.OWNER, "# Owner\n\n- A.\n")
        text, problems = memory.section(self.root, "builder")
        self.assertEqual(problems, [])
        self.assertTrue(text.startswith("\n## Core memory\n\n"), text)
        self.assertTrue(text.endswith("\n### memory/owner.md\n\n# Owner\n\n- A.\n"), text)
        self.write(memory.ROLE % "builder", "# Builder\n\n- B.\n")
        text, _ = memory.section(self.root, "builder")
        self.assertTrue(text.endswith("\n### memory/owner.md\n\n# Owner\n\n- A.\n"
                                      "\n### memory/roles/builder.md\n\n# Builder\n\n- B.\n"), text)
        self.assertNotIn("roles/builder.md", memory.section(self.root, "reviewer")[0])
        self.write(memory.ROLE % "builder", "- Email ben@example.org.\n")
        _, problems = memory.section(self.root, "builder")
        self.assertEqual([(rel, rule) for rel, _, rule, _ in problems], [(memory.ROLE % "builder", "memory-personal")])

    def test_cli(self):
        r = subprocess.run([sys.executable, SCRIPT, "--root", self.root], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "crew-memory: OK\n", ""))
        self.write(memory.OWNER, "- Phone 425-555-0134.\n")
        r = subprocess.run([sys.executable, SCRIPT, "--root", self.root], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "memory/owner.md:1: [memory-personal] phone number: %s\n" % memory.ROUTE)
        self.assertEqual(r.stderr, "crew-memory: FAILED (1 problem)\n")


if __name__ == "__main__":
    unittest.main()
