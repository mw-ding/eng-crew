#!/usr/bin/env python3
"""Builder pre-review marker gates: live-record fixtures and layered profiles."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("precheck", HERE / "crew-precheck.py")
precheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(precheck)
HEAD = "a" * 40
BUILDER = {"gh_user": "author", "name": "Ben"}


def marker(**updates):
    fields = dict(role="builder", **{"pass": "precheck"}, issue="182", sha=HEAD,
                  round="n/a", verdict="n/a", **dict.fromkeys(precheck.STEPS, "pass"))
    fields.update(updates)
    return "<!-- crew:v1 " + " ".join(k + "=" + v for k, v in fields.items()) + " -->"


class Gate(unittest.TestCase):
    def test_missing_stale_failed_passing(self):
        cases = [("", "missing marker"), (marker(sha="b" * 40), "stale marker"),
                 (marker(tests="fail"), "failed steps: tests"), (marker(), "pass"),
                 (marker(build="n/a"), "pass"), (marker(evidence="unknown"), "malformed marker"),
                 (marker().replace(" docs=pass", ""), "malformed marker"),
                 (marker(sha=HEAD[:7]), "stale marker")]
        for body, expected in cases:
            with self.subTest(expected=expected, body=body):
                self.assertEqual(precheck.check(dict(body=body, headRefOid=HEAD), BUILDER), expected)

    def test_latest_signed_builder_report_at_head_wins(self):
        def review(body, time, login="author", signed=True):
            return dict(body=body + ("\n— 🛠️ Ben (Builder) · Codex · model" if signed else ""),
                        author=dict(login=login), submittedAt=time)
        record = dict(body=marker(sha="b" * 40), headRefOid=HEAD,
                      reviews=[review(marker(tests="fail"), "2"), review(marker(), "1")])
        self.assertEqual(precheck.check(record, BUILDER), "failed steps: tests")
        record["reviews"] += [review(marker(), "3", login="other"), review(marker(), "4", signed=False)]
        self.assertEqual(precheck.check(record, BUILDER), "failed steps: tests")
        record["reviews"].append(review(marker(), "5"))
        self.assertEqual(precheck.check(record, BUILDER), "pass")
        record["headRefOid"] = "c" * 40
        self.assertEqual(precheck.check(record, BUILDER), "stale marker")

    def test_cli_profile_switch_and_org_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, org = Path(tmp) / "crew.toml", Path(tmp) / "org.toml"
            org.write_text('[builder.precheck]\nenabled = true\n')
            for settings, layer, body, code, output in [
                ("", None, "", 0, "disabled"),
                ("", org, "", 1, "missing marker"),
                ("\n[builder.precheck]\nenabled = false\n", org, "", 0, "disabled"),
                ("", org, marker(), 0, "pass")]:
                project.write_text('[runtime]\nname = "tmux"\n' + settings)
                args = ["--project", str(project)] + (["--org-profile", str(layer)] if layer else [])
                record = json.dumps(dict(body=body, headRefOid=HEAD))
                with patch("sys.stdin", io.StringIO(record)), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(precheck.main(args), code)
                self.assertIn("precheck: " + output, out.getvalue())


if __name__ == "__main__":
    unittest.main()
