#!/usr/bin/env python3
"""Fixture test for scripts/evidence-cli.py (offline, temp git repo only).

Covers the header, exit codes, separate streams, setup, scrubbing and fences,
and stored runner results (pass, red, fallback, head mismatch refused).
Run in CI.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
HELPER = os.path.join(SCRIPTS, "evidence-cli.py")
PY = sys.executable


class EvidenceCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = os.path.realpath(self.tmp.name)
        for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"],
                    ["config", "user.name", "t"],
                    ["commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git", *cmd], cwd=self.repo, check=True)
        self.sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, check=True,
            capture_output=True, text=True).stdout.strip()

    def tearDown(self):
        self.tmp.cleanup()

    def capture(self, *argv, env=None, cwd=None):
        out = subprocess.run([PY, HELPER, *argv], cwd=cwd or self.repo,
                             capture_output=True, text=True,
                             env={**os.environ, "HOME": "/nonexistent-home-652",
                                  **(env or {})})
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def test_header_and_success(self):
        text = self.capture("--label", "R2", "--", PY, "-c", "print('hi')")
        self.assertTrue(text.startswith(
            f"Proof R2 · `scripts/evidence-cli.py` · sha `{self.sha}` · cwd `.`\n"))
        self.assertIn("```sh\n", text)
        self.assertIn("-c 'print('\"'\"'hi'\"'\"')'\n```\n", text)
        self.assertIn("```text\nexit: 0\n--- stdout\nhi\n--- stderr\n```\n", text)

    def test_nonzero_exit_and_separate_streams(self):
        code = "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)"
        text = self.capture("--", PY, "-c", code)
        self.assertIn("exit: 3\n--- stdout\nout\n--- stderr\nerr\n```", text)

    def test_dirty_checkout_and_subdir(self):
        os.mkdir(os.path.join(self.repo, "sub"))
        open(os.path.join(self.repo, "sub", "f"), "w").close()
        text = self.capture("--", "true", cwd=os.path.join(self.repo, "sub"))
        self.assertIn(f"sha `{self.sha} (dirty)` · cwd `sub`", text)

    def test_setup_runs_in_same_shell(self):
        setup = os.path.join(self.repo, ".setup.sh")
        with open(setup, "w") as fh:
            fh.write("export GREETING=hello")
        text = self.capture("--setup", setup, "--", "sh", "-c", 'echo "$GREETING"')
        self.assertIn("```sh\nexport GREETING=hello\nsh -c '", text)
        self.assertIn("exit: 0\n--- stdout\nhello\n", text)

    def test_scrubbing(self):
        code = ("import os; print(os.environ['SECRET_X']); print(os.getcwd());"
                " print('ghp_' + 'a' * 30)")
        text = self.capture("--scrub-env", "SECRET_X", "--volatile",
                            "timestamps", "--", PY, "-c", code,
                            env={"SECRET_X": "s3cr3t-value"})
        self.assertNotIn("s3cr3t-value", text)
        self.assertNotIn(self.repo, text)
        self.assertIn("# scrubbed: $SECRET_X (value of env var SECRET_X)\n", text)
        self.assertIn("# scrubbed: <cwd> (capture working directory)\n", text)
        self.assertIn("# scrubbed: <redacted> (token-shaped value)\n", text)
        self.assertIn("# volatile: timestamps\nexit: 0\n", text)
        self.assertIn("--- stdout\n$SECRET_X\n<cwd>\n<redacted>\n", text)

    def test_key_value_text_is_not_redacted(self):
        setup = os.path.join(self.repo, ".setup.sh")
        with open(setup, "w") as fh:
            fh.write("export DEMO_TOKEN=demo-value")
        text = self.capture("--setup", setup, "--", "sh", "-c",
                            'echo "token=$DEMO_TOKEN"')
        self.assertIn("```sh\nexport DEMO_TOKEN=demo-value\n", text)
        self.assertIn("--- stdout\ntoken=demo-value\n", text)
        self.assertNotIn("# scrubbed:", text)

    def test_fence_grows_past_backticks_in_output(self):
        text = self.capture("--", PY, "-c", "print('```')")
        self.assertIn("````text\n", text)
        self.assertTrue(text.rstrip().endswith("````"))

    def test_missing_command_and_unknown_binary(self):
        out = subprocess.run([PY, HELPER, "--"], cwd=self.repo,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        out = subprocess.run([PY, HELPER, "--", "no-such-binary-652"],
                             cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("cannot run no-such-binary-652", out.stderr)


    def runner_result(self, head=None, exits=(0, 0)):
        path = os.path.join(self.repo, ".result.json")
        commands = [dict(command="check-repo", exit=exits[0], tail="check-repo: OK\n"),
                    dict(command="tests", exit=exits[1], tail="Ran 3 tests\n")]
        with open(path, "w") as fh:
            json.dump(dict(result="ok", host="host-c", job_id="abc1234-0123456789ab",
                           head=head or self.sha, commands=commands,
                           spec=[dict(command="check-repo"),
                                 dict(command="tests", files=["test-a.py", "test-b.py"])]), fh)
        return path

    def test_runner_pass(self):
        text = self.capture("--label", "R3", "--runner", self.runner_result())
        self.assertTrue(text.startswith(
            f"Proof R3 · `runner:host-c/abc1234-0123456789ab` · head `{self.sha}`"
            " · `scripts/evidence-cli.py --runner`\n"))
        self.assertIn(f"```sh\ncrew runner run --head {self.sha} -- check-repo "
                      "test-a.py test-b.py\n```\n", text)
        self.assertIn(f"```text\nrunner:host-c/abc1234-0123456789ab head={self.sha}\n"
                      "result: pass\n--- check-repo exit 0\ncheck-repo: OK\n"
                      "--- tests exit 0\nRan 3 tests\n```", text)

    def test_runner_red(self):
        text = self.capture("--runner", self.runner_result(exits=(0, 1)))
        self.assertIn("result: red\n--- check-repo exit 0\n", text)
        self.assertIn("--- tests exit 1\nRan 3 tests\n", text)

    def test_runner_job_id_under_crew_state(self):
        state = os.path.join(self.repo, ".state")
        os.makedirs(os.path.join(state, "runner", "abc1234-0123456789ab"))
        os.rename(self.runner_result(), os.path.join(
            state, "runner", "abc1234-0123456789ab", "result.json"))
        text = self.capture("--runner", "abc1234-0123456789ab", env={"CREW_STATE": state})
        self.assertIn("result: pass\n", text)

    def test_runner_head_mismatch_refused(self):
        out = subprocess.run([PY, HELPER, "--runner", self.runner_result(head="f" * 40)],
                             cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertEqual(out.stdout, "")
        self.assertIn(f"runner result is at {'f' * 40}, not the checkout head {self.sha}",
                      out.stderr)

    def test_runner_fallback(self):
        line = "runner: host-c unreachable; ran locally"
        text = self.capture("--runner-fallback", line, "--", PY, "-c", "print('ok')")
        self.assertTrue(text.startswith(f"Proof R1 · `scripts/evidence-cli.py` · sha `{self.sha}"))
        self.assertIn(f"```text\n# {line}\nexit: 0\n--- stdout\nok\n", text)
        out = subprocess.run([PY, HELPER, "--runner-fallback", "ran locally", "--", "true"],
                             cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("must be a `runner: ...; ran locally` line", out.stderr)


if __name__ == "__main__":
    unittest.main()
