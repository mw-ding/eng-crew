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

HERE = Path(__file__).resolve().parents[3] / "scripts"
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


def selfgate(**updates):
    fields = {"role": "builder", "pass": "selfgate", "pr": "7", "sha": HEAD, "base": "b" * 40, "round": "n/a",
              "verdict": "pass", "mode": "different", "builder-engine": "claude-code/opus",
              "reviewer-engine": "codex/gpt-5", "reviews": "1", "findings": "2", "open": "0", "checks": "pass"}
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

    def test_signature_with_emoji_off_or_team_still_authorizes(self):  # #431, #1291: marker reading unchanged
        for signature in ("— Ben (Builder) · Codex · model", "— 🧰 Ben (Builder) · md · Codex · model"):
            record = dict(body="", headRefOid=HEAD, reviews=[dict(body=marker() + "\n" + signature,
                                                                   author=dict(login="author"), submittedAt="1")])
            self.assertEqual(precheck.check(record, BUILDER), "pass", signature)
        record["reviews"][0]["body"] = marker() + "\n— Bob (Builder) · Codex · model"
        self.assertEqual(precheck.check(record, BUILDER), "missing marker")

    def test_selfgate_missing_stale_malformed_changes_and_rules(self):
        cases = [("", "missing marker"), (marker(), "missing marker"), (selfgate(sha="c" * 40), "stale marker"),
                 (selfgate(), "pass"), (selfgate(verdict="changes", open="1"), "verdict changes"),
                 (selfgate(round="1"), "malformed marker"), (selfgate(base="b" * 7), "malformed marker"),
                 (selfgate(pr="8"), "marker for 8, expected 7"), (selfgate(reviews="0"), "malformed marker"),
                 (selfgate(reviews="4"), "malformed marker"), (selfgate(open="3"), "malformed marker"),
                 (selfgate(mode="other"), "malformed marker"), (selfgate(**{"reviewer-engine": "codex"}), "malformed marker"),
                 (selfgate(**{"builder-engine": "/opus"}), "malformed marker"),
                 (selfgate(**{"reviewer-engine": "codex/"}), "malformed marker"),
                 (selfgate().replace(" checks=pass", ""), "malformed marker"),
                 (selfgate().replace(" -->", " extra=1 -->"), "malformed marker"),
                 (selfgate().replace(" -->", " open=0 -->"), "malformed marker"),
                 (selfgate(open="1"), "verdict pass with open findings"),
                 (selfgate(checks="fail"), "verdict pass with failed checks")]
        for body, expected in cases:
            with self.subTest(expected=expected, body=body):
                record = dict(number=7, body=body, headRefOid=HEAD)
                self.assertEqual(precheck.check_selfgate(record, BUILDER, "different"), expected)

    def test_selfgate_mode_and_engine_clash(self):
        def record(body, *trailers):
            return dict(number=7, body=body, headRefOid=HEAD,
                        commits=[dict(messageBody="msg\n\nEngine: %s model medium" % t) for t in trailers])
        clash = selfgate(**{"reviewer-engine": "claude-code/sonnet"})
        cases = [(record(selfgate(), "claude-code"), "different", "pass"),
                 (record(selfgate(), "claude-code"), "same", "mode different, effective selfgate_engine same"),
                 (record(clash), "different", "engine clash: reviewer claude-code is a builder engine"),
                 (record(selfgate(), "claude-code", "codex"), "different", "engine clash: reviewer codex is a builder engine"),
                 (record(selfgate(mode="same", **{"reviewer-engine": "claude-code/opus"}), "claude-code"), "same", "pass"),
                 (record(selfgate(**{"reviewer-engine": "opencode/deepseek/deepseek-v4-pro"}), "claude-code"),
                  "different", "pass"),
                 (record(selfgate(**{"builder-engine": "opencode/deepseek/deepseek-v4-pro"}), "opencode"),
                  "different", "pass"),
                 (record(selfgate(**{"reviewer-engine": "opencode/deepseek/deepseek-v4-pro"}), "claude-code", "opencode"),
                  "different", "engine clash: reviewer opencode is a builder engine"),
                 (record(selfgate(**{"builder-engine": "opencode/deepseek/deepseek-v4-pro",
                                     "reviewer-engine": "opencode/other"})), "different",
                  "engine clash: reviewer opencode is a builder engine")]
        for rec, mode, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(precheck.check_selfgate(rec, BUILDER, mode), expected)
        signed = dict(body=clash + "\n— 🛠️ Ben (Builder) · Codex · model", author=dict(login="author"), submittedAt="2")
        rec = record(selfgate(), "claude-code")
        rec["reviews"] = [signed, dict(signed, author=dict(login="other"), submittedAt="3")]
        self.assertEqual(precheck.check_selfgate(rec, BUILDER, "different"),
                         "engine clash: reviewer claude-code is a builder engine")

    def test_selfgate_change_key_comes_from_outside_the_marker(self):
        record = dict(body=selfgate(), headRefOid=HEAD)
        self.assertEqual(precheck.check_selfgate(record, BUILDER, "different"), "missing change key")
        self.assertEqual(precheck.check_selfgate(record, BUILDER, "different", change="7"), "pass")
        self.assertEqual(precheck.check_selfgate(dict(record, number=7), BUILDER, "different", change="8"),
                         "marker for 7, expected 8")

    def test_cli_selfgate_reads_effective_mode_without_precheck_switch(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "crew.toml"
            for settings, body, code, output in [
                ("", selfgate(), 0, "pass"), ("", "", 1, "missing marker"),
                ('\n[flavor]\nselfgate_engine = "same"\n', selfgate(), 1,
                 "mode different, effective selfgate_engine same")]:
                project.write_text('[runtime]\nname = "tmux"\n' + settings)
                rec = json.dumps(dict(number=7, body=body, headRefOid=HEAD))
                with patch("sys.stdin", io.StringIO(rec)), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(precheck.main(["--project", str(project), "--pass", "selfgate"]), code)
                self.assertIn("selfgate: " + output, out.getvalue())

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


ALNUM = precheck.id_patterns({"item": "[A-Z]+-[0-9]+", "change": "D[0-9]+"})
ITEM_KEY = precheck.id_patterns({"item": "[A-Z]+-[0-9]+", "change": "D[0-9]+", "marker_key": "item"})


def item_selfgate(issue="OPS-1042", **updates):
    return selfgate(**updates).replace(" pr=7 ", " issue=%s " % issue)


class IdKeys(unittest.TestCase):
    """protocol.md#precheck-and-selfgate-id-keys (#876): declared patterns, marker_key and independent keys."""

    def test_precheck_issue_matches_item_pattern_and_item(self):
        cases = [(marker(issue="OPS-1042"), None, "pass"), (marker(issue="OPS-1042"), "OPS-1042", "pass"),
                 (marker(issue="OPS-7"), "OPS-1042", "marker for OPS-7, expected OPS-1042"),
                 (marker(issue="182"), None, "malformed marker"), (marker(issue="ops-1042"), None, "malformed marker"),
                 (marker(issue="OPS-1042x"), None, "malformed marker"),
                 (marker(issue="OPS-1042").replace(" sha=", " issue=OPS-1042 sha="), None, "malformed marker"),
                 (marker(issue="OPS-1042", sha="b" * 40), None, "stale marker")]
        for body, item, expected in cases:
            with self.subTest(expected=expected, body=body):
                self.assertEqual(precheck.check(dict(body=body, headRefOid=HEAD), BUILDER, ALNUM, item), expected)

    def test_precheck_item_mode_refuses_pr_field(self):
        body = marker(issue="OPS-1042").replace(" sha=", " pr=D9 sha=")
        self.assertEqual(precheck.check(dict(body=body, headRefOid=HEAD), BUILDER, ALNUM), "pass")
        self.assertEqual(precheck.check(dict(body=body, headRefOid=HEAD), BUILDER, ITEM_KEY), "malformed marker")

    def test_selfgate_change_mode_alphanumeric(self):
        cases = [(selfgate(pr="D4711"), "D4711", "pass"),
                 (selfgate(pr="D4711"), "D4712", "marker for D4711, expected D4712"),
                 (selfgate(pr="7"), "7", "malformed marker"),
                 (selfgate(pr="D4711").replace(" -->", " issue=OPS-1042 -->"), "D4711", "malformed marker"),
                 (selfgate(pr="D4711").replace(" -->", " pr=D4711 -->"), "D4711", "malformed marker")]
        for body, change, expected in cases:
            with self.subTest(expected=expected, body=body):
                record = dict(number=4711, body=body, headRefOid=HEAD)
                self.assertEqual(precheck.check_selfgate(record, BUILDER, "different", ALNUM, change=change), expected)

    def test_selfgate_item_mode(self):
        cases = [(item_selfgate(), "OPS-1042", "pass"),
                 (item_selfgate(), None, "missing item key"),
                 (item_selfgate(issue="OPS-7"), "OPS-1042", "marker for OPS-7, expected OPS-1042"),
                 (selfgate(), "OPS-1042", "malformed marker"),
                 (item_selfgate().replace(" -->", " pr=D1 -->"), "OPS-1042", "malformed marker"),
                 (item_selfgate().replace(" -->", " issue=OPS-1042 -->"), "OPS-1042", "malformed marker"),
                 (item_selfgate(issue="1042"), "OPS-1042", "malformed marker"),
                 (item_selfgate(sha="c" * 40), "OPS-1042", "stale marker"),
                 (item_selfgate(verdict="changes", open="1"), "OPS-1042", "verdict changes")]
        for body, item, expected in cases:
            with self.subTest(expected=expected, body=body):
                record = dict(number=4711, body=body, headRefOid=HEAD)
                self.assertEqual(precheck.check_selfgate(record, BUILDER, "different", ITEM_KEY, item, "D4711"),
                                 expected)

    def test_github_defaults_unchanged(self):
        self.assertEqual(precheck.check(dict(body=marker(), headRefOid=HEAD), BUILDER, precheck.id_patterns({})), "pass")
        self.assertEqual(precheck.check(dict(body=marker(issue="OPS-1"), headRefOid=HEAD), BUILDER), "malformed marker")
        self.assertEqual(precheck.check(dict(body=marker(), headRefOid=HEAD), BUILDER, item="182"), "pass")
        record = dict(number=7, body=selfgate(), headRefOid=HEAD)
        self.assertEqual(precheck.check_selfgate(record, BUILDER, "different", precheck.id_patterns({})), "pass")

    def test_cli_item_and_change_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "crew.toml"
            project.write_text('[runtime]\nname = "tmux"\n\n[builder.precheck]\nenabled = true\n')
            for args, body, code, output in [
                (["--item", "182"], marker(), 0, "precheck: pass"),
                (["--item", "183"], marker(), 1, "precheck: marker for 182, expected 183"),
                (["--pass", "selfgate", "--change", "7"], selfgate(), 0, "selfgate: pass"),
                (["--pass", "selfgate", "--change", "8"], selfgate(), 1, "selfgate: marker for 7, expected 8")]:
                rec = json.dumps(dict(number=7, body=body, headRefOid=HEAD))
                with patch("sys.stdin", io.StringIO(rec)), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(precheck.main(["--project", str(project)] + args), code)
                self.assertIn(output, out.getvalue())
            for args in (["--item", "OPS-1"], ["--pass", "selfgate", "--change", "D7"]):
                with patch("sys.stdin", io.StringIO("not json")), contextlib.redirect_stderr(io.StringIO()) as err, \
                        contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(precheck.main(["--project", str(project)] + args), 1)
                self.assertIn("does not match", err.getvalue())
                self.assertEqual(out.getvalue(), "")

    def test_cli_reads_resolved_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "crew.toml"
            project.write_text('[runtime]\nname = "tmux"\n')
            resolved = precheck.config.resolve_profile(str(project))
            profile = dict(resolved[0], ids={"item": "[A-Z]+-[0-9]+", "change": "D[0-9]+", "marker_key": "item"})
            rec = json.dumps(dict(number=4711, body=item_selfgate(), headRefOid=HEAD))
            for args, code, output in [(["--item", "OPS-1042"], 0, "selfgate: pass"),
                                       ([], 1, "selfgate: missing item key")]:
                with patch.object(precheck.config, "resolve_profile", return_value=(profile,) + resolved[1:]), \
                        patch("sys.stdin", io.StringIO(rec)), contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(precheck.main(["--project", str(project), "--pass", "selfgate"] + args), code)
                self.assertIn(output, out.getvalue())


    def test_cli_keys_on_issue_from_a_backend_map(self):
        """#1031: a change map's [ids] marker_key = "item" reaches the selfgate check through resolve."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "crew.toml"
            project.write_text('[runtime]\nname = "tmux"\n\n[paths]\npack = "pack"\n')
            overlay = Path(tmp) / "pack" / "render" / "backends" / "github.toml"
            overlay.parent.mkdir(parents=True)
            item_record = dict(number=7, body=item_selfgate(issue="182"), headRefOid=HEAD)
            change_record = dict(number=7, body=selfgate(), headRefOid=HEAD)
            cases = [('[ids]\nmarker_key = "item"\n', item_record, ["--item", "182"], 0, "selfgate: pass"),
                     ('[ids]\nmarker_key = "item"\n', item_record, [], 1, "selfgate: missing item key"),
                     ('[ids]\nmarker_key = "item"\n', change_record, ["--item", "182"], 1, "selfgate: malformed marker"),
                     ("", change_record, [], 0, "selfgate: pass"),
                     ("", item_record, ["--item", "182"], 1, "selfgate: malformed marker")]
            for ids, record, args, code, output in cases:
                with self.subTest(ids=ids, args=args, output=output):
                    overlay.write_text(ids)
                    with patch("sys.stdin", io.StringIO(json.dumps(record))), \
                            contextlib.redirect_stdout(io.StringIO()) as out:
                        self.assertEqual(precheck.main(["--project", str(project), "--pass", "selfgate"] + args), code)
                    self.assertIn(output, out.getvalue())

if __name__ == "__main__":
    unittest.main()
