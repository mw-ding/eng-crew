#!/usr/bin/env python3
"""Fixture test for scripts/campaign-lint.py (offline, temp dirs only; #1412).

Covers the unhandled-assertion rule (a failed chain before a passing tail, a lone assertion, loop bodies,
groups and functions) and what stays allowed (the step's own result, a `VAR=$?` capture, `|| exit`, a `||`
handler, `&& break`-style control flow, if conditions, quotes, `$()` and here-documents); a step that does not
parse; the disposition shape; every committed campaign scenario linting clean; and the base/head retention
check: a deleted case, a case deleted with its disposition and a deleted scenario fail unless retired with a
reason. Run in CI.
"""
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts", "campaign-lint.py")
spec = importlib.util.spec_from_file_location("campaign_lint", SCRIPT)
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)


class StepLintTest(unittest.TestCase):
    def bad(self, src):
        self.assertTrue(cl.lint_step(src), "expected a finding: %r" % src)

    def good(self, src):
        self.assertEqual(cl.lint_step(src), [], src)

    def test_unhandled_assertions(self):
        self.bad("test 1 -eq 2 && grep -q x f; echo tail")
        self.bad("cd d && ! grep -q x f && echo ok\necho tail")
        self.bad("[ -s f ]; true")
        self.bad("grep --quiet x f && cat f; true")
        self.bad("for r in a b; do test -e $r; done; true")
        self.bad("for r in a b; do grep -q x $r; done")
        self.bad("{ test -e a; true; } && echo ok")
        self.bad("check() { grep -q x f; echo after; }; check")
        self.bad("if true; then test -e a; echo b; fi")
        self.bad("x=$(cat f) && test -n \"$x\"; true")

    def test_handled_or_not_assertions(self):
        self.good("cd d && test 1 -eq 1 && grep -q x f")
        self.good("cmd > o 2>&1; rc=$?; cat o; test $rc -eq 1 && grep -q 'select one' o")
        self.good("grep -q x f; rc=$?; test $rc = 1")
        self.good("test -e a && grep -q x a || exit 1; echo tail")
        self.good("grep -qF -- \"$s\" f && echo hit || { echo miss; exit 1; }; true")
        self.good("test -f a || touch a; true")
        self.good("while true; do grep -q done f && break; sleep 1; done; true")
        self.good("w() { grep -q \"$1\" f && return 0; return 1; }; w x")
        self.good("[ -s f ] && n=$((n+1)); echo $n")
        self.good("if grep -q x f; then echo y; fi; true")
        self.good("for r in a b; do test -e $r || exit 1; done; true")
        self.good("echo \"$(echo \"a; test 1 = 2 && b\")\"; grep -c x f; true")
        self.good("cat > s.py <<'PY'\nimport os; test = 1 && x\nPY\npython3 s.py <<< \"x\"; test -s s.py")
        self.good("case $x in a) test -e a ;; *) true ;; esac")
        self.good("echo 'a && test 1 = 2; b' # test -e c; true\ntrue")

    def test_unparseable_step_refused(self):
        for src in ("echo 'open", "if true; then echo", "echo $(open", "for x in a; do true"):
            with self.assertRaises(ValueError):
                cl.lint_step(src)
            self.assertIn("step does not parse", cl.step_problems({"run": src})[0])

    def test_disposition_shape(self):
        self.assertEqual(cl.step_problems({"run": "exit 1", "disposition": {"state": "accepted", "reason": "#9"}}), [])
        for d in ({"state": "accepted"}, {"state": "skip", "reason": "x"}, {"state": "expected-fail", "reason": ""},
                  "expected-fail"):
            self.assertEqual(len(cl.step_problems({"run": "true", "disposition": d})), 1, d)

    def test_committed_scenarios_lint_clean(self):
        d = os.path.join(TESTS, "scripts", "fixtures", "campaign")
        self.assertEqual(cl.check(d), [])
        self.assertGreater(len(cl.cases(cl.load_dir(d)[0])), 100)


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.d = os.path.join(self.root, "sc")
        os.makedirs(self.d)
        self.git("init", "-q", "-b", "main")
        self.put("A01", [{"name": "one", "run": "true"}, {"name": "two", "run": "exit 1",
                                                          "disposition": {"state": "expected-fail", "reason": "#9"}}])
        self.put("A02", [{"name": "only", "run": "true"}])
        self.git("add", "-A")
        self.git("commit", "-qm", "base")
        self.git("checkout", "-qb", "topic")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@t"] + list(args), check=True)

    def put(self, sid, steps):
        with open(os.path.join(self.d, sid + ".json"), "w") as fh:
            json.dump({"id": sid, "steps": steps}, fh)

    def run_cli(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "head", "--allow-empty")
        return subprocess.run(["python3", SCRIPT, self.d, "--base", "main"], capture_output=True, text=True)

    def test_unchanged_passes_and_removals_fail_until_retired(self):
        self.assertEqual(self.run_cli().returncode, 0)
        self.put("A01", [{"name": "one", "run": "true"}])  # the case and its disposition, both gone
        os.remove(os.path.join(self.d, "A02.json"))
        p = self.run_cli()
        self.assertEqual(p.returncode, 1)
        self.assertEqual(sorted(l.split(":")[0] for l in p.stdout.splitlines()), ["A01/two", "A02/only"])
        self.assertIn("required case at", p.stdout)
        with open(os.path.join(self.d, "retired-cases.json"), "w") as fh:
            json.dump({"A01/two": "fixed by #9; the oracle moved into A01/one", "A02/only": ""}, fh)
        p = self.run_cli()
        base = subprocess.run(["git", "-C", self.root, "rev-parse", "main"], capture_output=True, text=True).stdout
        self.assertEqual(p.stdout.splitlines(), ["retired-cases.json: A02/only needs a non-empty reason",
                                                 "A02/only: required case at %s is gone; keep the step, give it a "
                                                 "disposition, or retire it with a reason in retired-cases.json"
                                                 % base[:12]])
        with open(os.path.join(self.d, "retired-cases.json"), "w") as fh:
            json.dump({"A01/two": "fixed by #9", "A02/only": "scenario folded into A01 (#10)"}, fh)
        self.assertEqual(self.run_cli().returncode, 0)

    def test_dropping_a_disposition_keeps_the_case(self):
        self.put("A01", [{"name": "one", "run": "true"}, {"name": "two", "run": "true"}])
        self.assertEqual(self.run_cli().returncode, 0, "a repaired case stays required; the run proves it passes")

    def test_unknown_base_exits_2(self):
        p = subprocess.run(["python3", SCRIPT, self.d, "--base", "nope"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("cannot find the merge base of nope", p.stderr)


if __name__ == "__main__":
    unittest.main()
