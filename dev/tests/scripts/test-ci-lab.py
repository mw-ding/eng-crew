#!/usr/bin/env python3
"""Tests for the opt-in `lab` job in .github/workflows/ci.yml (#1362, offline).

Runs the job's prerequisites step with a fake `docker` and `uname` on PATH: a
missing or unpinned LAB_BASE, a non-ARM64 runner, no Docker daemon or an image
that does not pull each records an explicit skip (notice, step summary, empty
scenarios step), and with every prerequisite present nothing is skipped. The
job only runs on a PR labelled `lab`, is no other job's dependency and has no
`continue-on-error`, so it adds no mandatory Docker requirement and waives
nothing. Run in CI.
"""
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
WORKFLOW = open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8").read()
JOB = WORKFLOW.split("\n  lab:\n", 1)[1]
PINNED = "mdstack-lab-base@sha256:" + "a" * 64
FAKE_DOCKER = '#!/bin/sh\necho "$*" >> "$FAKE/calls"\ncase "$1" in info) exit "$FAKE_INFO";; ' \
              'pull) exit "$FAKE_PULL";; esac\n'


def step(name):
    return JOB.split("      - name: %s" % name, 1)[1].split("      - name:", 1)[0]


def step_shell(name):
    return "\n".join(line[10:] for line in step(name).split("        run: |\n", 1)[1].splitlines())


class LabJobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake = self.tmp.name
        for name, text in (("docker", FAKE_DOCKER), ("uname", '#!/bin/sh\necho "$FAKE_ARCH"\n')):
            path = os.path.join(self.fake, name)
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def pre(self, base=PINNED, arch="aarch64", info=0, pull=0):
        out, summary = os.path.join(self.fake, "out"), os.path.join(self.fake, "summary")
        for path in (out, summary):
            if os.path.exists(path):
                os.remove(path)
        env = dict(os.environ, PATH=self.fake + os.pathsep + os.environ["PATH"], FAKE=self.fake, LAB_BASE=base,
                   FAKE_ARCH=arch, FAKE_INFO=str(info), FAKE_PULL=str(pull), GITHUB_OUTPUT=out,
                   GITHUB_STEP_SUMMARY=summary)
        r = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step_shell("Lab prerequisites")],
                           env=env, capture_output=True, text=True)
        read = lambda p: open(p).read() if os.path.exists(p) else ""
        return r.returncode, r.stdout, read(out), read(summary)

    def assert_skip(self, why, **kw):
        code, stdout, out, summary = self.pre(**kw)
        self.assertEqual(code, 0, stdout)
        self.assertIn("::notice::lab skipped: %s; no lab evidence" % why, stdout)
        self.assertEqual(summary, "lab: skipped (%s); no lab evidence\n" % why)
        self.assertEqual(out, "skip=%s\n" % why)

    def test_unset_or_unpinned_base_is_a_recorded_skip(self):
        for base in ("", "mdstack-lab-base:bookworm", "mdstack-lab-base@sha256:abc"):
            self.assert_skip("LAB_BASE is unset or not pinned by digest", base=base)

    def test_non_arm64_runner_is_a_recorded_skip(self):
        self.assert_skip("runner is x86_64, not ARM64", arch="x86_64")

    def test_no_docker_daemon_is_a_recorded_skip(self):
        self.assert_skip("no Docker daemon", info=1)

    def test_an_image_that_does_not_pull_is_a_recorded_skip(self):
        self.assert_skip("LAB_BASE %s did not pull" % PINNED, pull=1)

    def test_all_prerequisites_present_runs_the_scenarios(self):
        code, stdout, out, summary = self.pre()
        self.assertEqual((code, stdout, out, summary), (0, "", "skip=\n", ""))
        with open(os.path.join(self.fake, "calls")) as f:
            self.assertEqual(f.read().split("\n")[:2], ["info", "pull -q " + PINNED])

    def test_job_is_opt_in_and_never_required_or_waived(self):
        self.assertIn("    if: contains(github.event.pull_request.labels.*.name, 'lab')\n", JOB)
        self.assertNotIn("continue-on-error", WORKFLOW)
        self.assertNotIn("needs:", WORKFLOW)
        self.assertIn("        if: steps.pre.outputs.skip == ''\n", step("Lab scenarios"))
        run = step_shell("Lab scenarios")
        for script in ("crew-lab-docker.py setup", "crew-lab-scenarios.py", "crew-lab-docker.py teardown"):
            self.assertIn(script, run)


if __name__ == "__main__":
    unittest.main()
