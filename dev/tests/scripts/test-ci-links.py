#!/usr/bin/env python3
"""Tests for the `links` job in .github/workflows/ci.yml (#1352, offline).

Runs the job's install step with a fake `curl` and `sleep` on PATH: a
transient download error is retried with backoff, an exhausted retry and a
checksum mismatch fail with a clear `::error::`, and the link-check step
passes lychee's failing exit through. The pinned version and sha256 stay
explicit and the job has no `continue-on-error`. Run in CI.
"""
import hashlib
import io
import os
import subprocess
import tarfile
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
WORKFLOW = open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8").read()
JOB = WORKFLOW.split("\n  links:\n", 1)[1].split("\n\n  ", 1)[0]


def step_shell(name):
    step = JOB.split("      - name: %s" % name, 1)[1].split("      - name:", 1)[0]
    return "\n".join(line[10:] for line in step.split("        run: |\n", 1)[1].splitlines())


FAKE_CURL = """#!/bin/sh
n=$(($(cat "$FAKE/calls" 2>/dev/null || echo 0) + 1))
echo "$n" > "$FAKE/calls"
[ "$n" -le "$FAKE_FAILS" ] && { echo "curl: (22) The requested URL returned error: 502" >&2; exit 22; }
while [ "$#" -gt 0 ]; do [ "$1" = -o ] && cp "$FAKE/asset.tar.gz" "$2"; shift; done
"""


class LinksJobTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.fake, self.home, self.runner = (os.path.join(d, n) for n in ("fake", "home", "runner"))
        for path in (self.fake, self.home, self.runner):
            os.mkdir(path)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            body = b"#!/bin/sh\necho fake lychee\n"
            info = tarfile.TarInfo("lychee")
            info.size, info.mode = len(body), 0o755
            tar.addfile(info, io.BytesIO(body))
        self.asset = buf.getvalue()
        with open(os.path.join(self.fake, "asset.tar.gz"), "wb") as f:
            f.write(self.asset)
        for name, text in (("curl", FAKE_CURL), ("sleep", '#!/bin/sh\necho "$1" >> "$FAKE/sleeps"\n')):
            path = os.path.join(self.fake, name)
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, fails, sha=None):
        env = dict(os.environ, PATH=self.fake + os.pathsep + os.environ["PATH"], FAKE=self.fake,
                   FAKE_FAILS=str(fails), HOME=self.home, RUNNER_TEMP=self.runner, LYCHEE_VERSION="0.24.2",
                   LYCHEE_SHA256=sha or hashlib.sha256(self.asset).hexdigest())
        return subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step_shell("Install lychee")],
                              env=env, capture_output=True, text=True)

    def read(self, name):
        path = os.path.join(self.fake, name)
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return f.read().split()

    def test_transient_errors_retry_with_backoff(self):
        out = self.install(fails=2)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(self.read("calls"), ["3"])
        self.assertEqual(self.read("sleeps"), ["5", "10"])
        self.assertTrue(os.access(os.path.join(self.home, ".local", "lychee", "lychee"), os.X_OK))

    def test_unrecoverable_download_fails_with_message(self):
        out = self.install(fails=99)
        self.assertEqual(out.returncode, 1)
        self.assertEqual(self.read("calls"), ["5"])
        self.assertIn("::error::lychee 0.24.2 download failed after 5 attempts", out.stdout)

    def test_checksum_mismatch_fails_with_message(self):
        out = self.install(fails=0, sha="0" * 64)
        self.assertEqual(out.returncode, 1)
        self.assertIn("::error::lychee 0.24.2 checksum mismatch", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".local", "lychee", "lychee")))

    def test_link_failure_fails_the_step(self):
        lychee = os.path.join(self.home, ".local", "lychee", "lychee")
        os.makedirs(os.path.dirname(lychee))
        with open(lychee, "w") as f:
            f.write("#!/bin/sh\necho 'broken link' >&2\nexit 2\n")
        os.chmod(lychee, 0o755)
        out = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step_shell("Check relative links")],
                             env=dict(os.environ, HOME=self.home), capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)

    def test_pin_explicit_and_never_waived(self):
        self.assertIn('LYCHEE_VERSION: "0.24.2"', JOB)
        self.assertRegex(JOB, r'LYCHEE_SHA256: "[0-9a-f]{64}"')
        self.assertIn("key: lychee-${{ env.LYCHEE_VERSION }}-${{ env.LYCHEE_SHA256 }}", JOB)
        self.assertNotIn("continue-on-error", JOB)
        self.assertNotIn("lychee-action", JOB)


if __name__ == "__main__":
    unittest.main()
