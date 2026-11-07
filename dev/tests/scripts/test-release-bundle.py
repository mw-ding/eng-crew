#!/usr/bin/env python3
"""Offline tests for scripts/release-bundle.py on temp git repos.

Covers: two builds give identical bytes and `SHA256SUMS`, deliverable-only
contents under `eng-crew-<version>/` and tar metadata, `SOURCE_DATE_EPOCH`, link
rewriting (inline, image, reference, root-relative; code spans and fences
untouched), `raw/` URLs for images, `--repo` over the remote, a dangling link
failing the link check, refusals, and a build of the current repo, extracted to
a temp dir, where `scripts/crew --help`, `scripts/crew-config.py validate
profiles/default.toml` and `scripts/crew-render.py --project
profiles/default.toml --out <tmp>` and `scripts/check-repo.py --only markdown`
(its `check-markdown.py` dependency ships, #644) must exit 0. Run in CI.
"""
import contextlib
import hashlib
import importlib.util
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
spec = importlib.util.spec_from_file_location("release_bundle", os.path.join(SCRIPTS, "release-bundle.py"))
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

MANIFEST = ("# test manifest\n"
            "docs/a.md\tdeliverable\tall\n"
            "docs/b.md\tdeliverable\tall\n"
            "bin/tool\tdeliverable\tall\n"
            "docs/internal/**\tinternal\tn/a\n"
            "scripts/deliverables.txt\tinternal\tn/a\n")
A_MD = """# A

See [b](b.md), [notes](internal/notes.md#why) and ![pic](./internal/pic.png).
Plain link to an image: [diagram](internal/pic.png). Image of a page: ![p](internal/notes.md).
[ref]: internal/notes.md
Root-relative: [notes](/docs/internal/notes.md). Web: [x](https://example.com/y.md).
Code span stays: `[n](internal/notes.md)`.

```text
[fenced](internal/notes.md)
```
"""
URL = "https://github.com/acme/widgets/blob/v1.2.3/docs/internal/"
RAW = "https://github.com/acme/widgets/raw/v1.2.3/docs/internal/"
TOP = "eng-crew-1.2.3/"
ENV = {"SOURCE_DATE_EPOCH": ""}


class ReleaseBundleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "repo")
        self.files = {"scripts/deliverables.txt": MANIFEST, "docs/a.md": A_MD,
                      "docs/b.md": "# B\n\n[a](a.md)\n", "bin/tool": "#!/bin/sh\n",
                      "docs/internal/notes.md": "# Notes\n", "docs/internal/pic.png": "png"}
        self.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        rb.git(self.root, *args)

    def commit(self):
        for rel, text in self.files.items():
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        os.chmod(os.path.join(self.root, "bin/tool"), 0o755)
        if not os.path.isdir(os.path.join(self.root, ".git")):
            subprocess.run(["git", "init", "-q", self.root], check=True)
            self.git("remote", "add", "origin", "git@github.com:acme/widgets.git")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "c",
                 "--date=2026-10-01T00:00:00Z")

    def build(self, out, *extra, env=ENV):
        err = io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err):
            code = rb.main(["1.2.3", "--root", self.root, "--out", out, *extra])
        return code, err.getvalue()

    def members(self, out):
        with tarfile.open(os.path.join(out, "eng-crew-1.2.3.tar.gz")) as tar:
            names = [m.name for m in tar.getmembers()]
            self.assertTrue(all(n.startswith(TOP) for n in names), names)
            return {m.name[len(TOP):]: (m, tar.extractfile(m).read().decode()) for m in tar.getmembers()}

    def test_deterministic(self):
        a, b = os.path.join(self.tmp.name, "a"), os.path.join(self.tmp.name, "b")
        self.assertEqual(self.build(a)[0], 0)
        self.assertEqual(self.build(b)[0], 0)
        with open(os.path.join(a, "SHA256SUMS")) as f:
            sums = f.read()
        with open(os.path.join(b, "SHA256SUMS")) as f:
            self.assertEqual(sums, f.read())
        with open(os.path.join(a, "eng-crew-1.2.3.tar.gz"), "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(sums, "%s  eng-crew-1.2.3.tar.gz\n" % digest)

    def test_deliverable_only_contents_and_metadata(self):
        out = os.path.join(self.tmp.name, "out")
        self.assertEqual(self.build(out)[0], 0)
        members = self.members(out)
        self.assertEqual(list(members), ["VERSION", "bin/tool", "docs/a.md", "docs/b.md"])
        self.assertEqual(members["VERSION"][1], "v1.2.3\n")
        commit_time = int(subprocess.run(["git", "-C", self.root, "log", "-1", "--format=%ct"],
                                         capture_output=True, check=True).stdout)
        for m, _ in members.values():
            self.assertEqual((m.uid, m.gid, m.uname, m.gname, m.mtime), (0, 0, "", "", commit_time))
        self.assertEqual(members["bin/tool"][0].mode, 0o755)
        self.assertEqual(members["docs/a.md"][0].mode, 0o644)

    def test_source_date_epoch(self):
        out = os.path.join(self.tmp.name, "out")
        self.assertEqual(self.build(out, env={"SOURCE_DATE_EPOCH": "1000"})[0], 0)
        self.assertTrue(all(m.mtime == 1000 for m, _ in self.members(out).values()))

    def test_link_rewrite(self):
        out = os.path.join(self.tmp.name, "out")
        self.assertEqual(self.build(out)[0], 0)
        text = self.members(out)["docs/a.md"][1]
        self.assertIn("[b](b.md)", text)
        self.assertIn("[notes](%snotes.md#why)" % URL, text)
        self.assertIn("[ref]: %snotes.md\n" % URL, text)
        self.assertIn("Root-relative: [notes](%snotes.md)." % URL, text)
        self.assertIn("[x](https://example.com/y.md)", text)
        self.assertIn("`[n](internal/notes.md)`", text)
        self.assertIn("[fenced](internal/notes.md)", text)

    def test_image_links_use_raw(self):
        out = os.path.join(self.tmp.name, "out")
        self.assertEqual(self.build(out)[0], 0)
        text = self.members(out)["docs/a.md"][1]
        self.assertIn("![pic](%spic.png)" % RAW, text)
        self.assertIn("[diagram](%spic.png)" % RAW, text)
        self.assertIn("![p](%snotes.md)" % RAW, text)

    def test_repo_argument_overrides_remote(self):
        out = os.path.join(self.tmp.name, "out")
        self.assertEqual(self.build(out, "--repo", "o/r")[0], 0)
        self.assertIn("https://github.com/o/r/blob/v1.2.3/docs/internal/notes.md#why",
                      self.members(out)["docs/a.md"][1])

    def test_dangling_link_fails_and_writes_nothing(self):
        self.files["docs/b.md"] = "# B\n\n[gone](missing.md)\n"
        self.commit()
        out = os.path.join(self.tmp.name, "out")
        code, err = self.build(out)
        self.assertEqual(code, 1)
        self.assertIn("docs/b.md:3: [broken-link] relative link does not resolve: missing.md", err)
        self.assertFalse(os.path.exists(out))

    def test_unclassified_path_and_bad_version_refused(self):
        self.files["stray.md"] = "# stray\n"
        self.commit()
        out = os.path.join(self.tmp.name, "out")
        self.assertIn("stray.md matches 0 manifest rows", self.build(out)[1])
        with mock.patch.dict(os.environ, ENV), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(rb.main(["v1.2.3", "--root", self.root, "--out", out]), 1)
        self.assertIn("not a SemVer version", err.getvalue())

    def test_current_repo_builds_and_install_cli_runs(self):
        out = os.path.join(self.tmp.name, "real")
        with mock.patch.dict(os.environ, ENV), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = rb.main(["0.0.0", "--out", out, "--repo", "o/r"])
        self.assertEqual(code, 0, err.getvalue())
        with tarfile.open(os.path.join(out, "eng-crew-0.0.0.tar.gz")) as tar:
            self.assertIn("eng-crew-0.0.0/roles/eng/builder.toml", tar.getnames())
            tar.extractall(out, filter="data")
        render = os.path.join(self.tmp.name, "render")
        for cmd in (["scripts/crew", "--help"],
                    ["scripts/crew-config.py", "validate", "profiles/default.toml"],
                    ["scripts/crew-render.py", "--project", "profiles/default.toml", "--out", render],
                    ["scripts/check-repo.py", "--only", "markdown"]):
            with self.subTest(cmd=" ".join(cmd)):
                run = subprocess.run([sys.executable, *cmd], cwd=os.path.join(out, "eng-crew-0.0.0"),
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stderr)
        for skill in ("eng-pr-pipeline", "eng-crew-roles"):
            with open(os.path.join(render, "runtime", "skills", skill, "SKILL.md")) as f:
                text = f.read()
            self.assertIn("name: " + skill, text)
            self.assertNotIn("<include:", text)
            self.assertIn("## ", text)


if __name__ == "__main__":
    unittest.main()
