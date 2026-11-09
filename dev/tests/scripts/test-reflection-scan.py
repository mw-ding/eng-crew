#!/usr/bin/env python3
"""Offline self-test for scripts/reflection-scan.py (no network).

Runs the CLI on sanitized extracts of real cards (fixtures/reflection/, fetched 2026-11-09T13:00Z) and checks
selection of issues opened, closed or only corrected in the window whatever their state; one incident per card and
fix chain (#1474/#1475/#1482), one per site for a card naming several (#1398, #1483), and one per class and site
however many cards report it; confirmed, reported and superseded evidence kept apart; lessons and findings read at
the named SHA, with an older linked lesson kept as context; missing inputs listed and null, never zero; triage's
open-only clusters unchanged; a compact, deterministic JSON index (#1518). Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
FIX = os.path.join(TESTS, "scripts", "fixtures", "reflection")
FORGE = os.path.join(FIX, "forge-20261109T1300Z.json")
spec = importlib.util.spec_from_file_location("reflection_scan", os.path.join(SCRIPTS, "reflection-scan.py"))
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)
R = "mw-ding/mdstack#"
WINDOW = ["--since", "2026-11-08T21:00:00Z", "--until", "2026-11-09T13:00:00Z"]


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rs.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def scan(*argv):
    code, out, err = run(*WINDOW, *argv)
    assert code == 0, err
    return json.loads(out)


def forge():
    with open(FORGE, encoding="utf-8") as f:
        return json.load(f)


def incidents(index):
    return {i["id"].split(":", 1)[1]: i for i in index["incidents"]}


def states(incident):
    return [(e["ref"].split("#")[1], e["kind"], e["state"]) for e in incident["evidence"]]


class Store:
    """A throwaway git repo holding the lesson and findings fixtures at one commit.

    `lessons=False` leaves `docs/lessons/` out; `extra` adds lesson files by name."""

    def __init__(self, lessons=True, extra=None):
        self.lessons, self.extra = lessons, extra or {}

    def __enter__(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "docs", "findings"))
        shutil.copy(os.path.join(FIX, "buffer.md"), os.path.join(self.root, "docs", "findings", "buffer.md"))
        if self.lessons:
            shutil.copytree(os.path.join(FIX, "lessons"), os.path.join(self.root, "docs", "lessons"))
            for name, text in dict(self.extra, **{"README.md": "# Lessons log\n\n- **Date:** YYYY-MM-DD\n"}).items():
                with open(os.path.join(self.root, "docs", "lessons", name), "w") as f:
                    f.write(text)
        git = ["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(git[:3] + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-qm", "fixtures"], check=True)
        self.sha = subprocess.run(git[:3] + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True
                                  ).stdout.strip()
        os.remove(os.path.join(self.root, "docs", "findings", "buffer.md"))  # the work tree is never read
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.root)


class Incidents(unittest.TestCase):
    def test_card_and_fix_chain_are_one_incident(self):
        got = incidents(scan("--forge", FORGE))
        one = got[R + "1474"]
        self.assertEqual(one["refs"], [R + "1474", R + "1475", R + "1482"])
        self.assertEqual(one["selected"][R + "1474"], ["opened", "closed", "corrected"])
        self.assertEqual([k for k in one["keys"] if k.startswith("class:")], ["class:session-loss"])
        self.assertFalse(any(R + "1475" in i["refs"] for k, i in got.items() if k != R + "1474"))

    def test_card_naming_several_sites_reports_one_incident_each(self):
        index = scan("--forge", FORGE)
        got = incidents(index)
        sites = sorted(k for k in got if k.endswith("~conflicting-pr-gets-no-ci"))
        self.assertEqual(sites, [R + n + "~conflicting-pr-gets-no-ci" for n in ("1341", "1373", "1392")])
        for k in sites:
            self.assertEqual(got[k]["reported_by"], [R + "1398"])
            self.assertEqual(got[k]["refs"], [])
        self.assertEqual(index["keys"]["class:conflicting-pr-gets-no-ci"], ["incident:" + k for k in sites])
        self.assertNotIn(R + "1398", got)

    def test_site_missing_from_the_snapshot_is_unresolved_not_dropped(self):
        got = incidents(scan("--forge", FORGE))
        self.assertEqual(got[R + "1472~stale-changes-label"]["unresolved"], [R + "1472"])
        self.assertEqual(got[R + "1467~stale-changes-label"]["unresolved"], [])
        self.assertEqual(got[R + "1053~deferred-handoff-renudge"]["unresolved"], [R + "1053"])

    def test_several_cards_on_one_site_are_one_incident(self):
        items = forge()
        items.append({"number": 1600, "url": "https://github.com/mw-ding/mdstack/issues/1600", "state": "OPEN",
                      "title": "intake: conflicting-pr-gets-no-ci", "labels": [], "comments": [],
                      "createdAt": "2026-11-09T06:00:00Z", "closedAt": None,
                      "body": "**Source:** mw-ding/mdstack#1373\n**Failure class:** conflicting-pr-gets-no-ci\n"})
        items.append({"number": 1601, "url": "https://github.com/mw-ding/mdstack/issues/1601", "state": "OPEN",
                      "title": "intake: reviewer-done-line-unmatched", "labels": [], "comments": [],
                      "createdAt": "2026-11-09T06:00:00Z", "closedAt": None,
                      "body": "**Source:** mw-ding/mdstack#1373\n**Failure class:** reviewer-done-line-unmatched\n"})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(items, f)
        try:
            got = incidents(scan("--forge", f.name))
        finally:
            os.remove(f.name)
        same = got[R + "1373~conflicting-pr-gets-no-ci"]
        self.assertEqual((same["refs"], same["reported_by"]), ([R + "1600"], [R + "1398"]))
        self.assertEqual(len([k for k in got if k.endswith("~conflicting-pr-gets-no-ci")]), 3)
        self.assertEqual(got[R + "1373~reviewer-done-line-unmatched"]["refs"], [R + "1601"])

    def test_selected_items_without_a_card_are_listed_not_incidents(self):
        index = scan("--forge", FORGE)
        self.assertEqual(index["items"], {R + "1514": ["opened", "closed"]})


class Evidence(unittest.TestCase):
    def test_confirmed_reported_and_superseded_stay_distinct(self):
        one = incidents(scan("--forge", FORGE))[R + "1474"]
        self.assertEqual(states(one), [
            ("1474", "card", "superseded"), ("1474", "research", "confirmed"), ("1475", "body", "reported"),
            ("1474", "triage", "confirmed"), ("1482", "body", "reported"), ("1474", "triage", "superseded"),
            ("1474", "correction", "confirmed")])
        by_kind = {e["kind"]: e for e in one["evidence"] if e["ref"] == R + "1474"}
        self.assertEqual(by_kind["card"]["superseded_by"], by_kind["research"]["url"])

    def test_unconfirmed_report_stays_reported(self):
        got = incidents(scan("--forge", FORGE))[R + "1053~deferred-handoff-renudge"]
        self.assertEqual(states(got), [("1502", "card", "reported"), ("1502", "triage", "reported")])

    def test_a_correction_alone_selects_its_item(self):
        code, out, err = run("--since", "2026-11-09T05:09:00Z", "--until", "2026-11-09T06:00:00Z", "--forge", FORGE)
        self.assertEqual(code, 0, err)
        got = incidents(json.loads(out))
        self.assertEqual(list(got), [R + "1474"])
        self.assertEqual(got[R + "1474"]["selected"], {R + "1474": ["corrected"]})


class Stores(unittest.TestCase):
    def test_lessons_and_findings_at_the_named_sha(self):
        with Store() as s:
            index = scan("--forge", FORGE, "--root", s.root, "--sha", s.sha)
        lessons = {e["path"].rsplit("/", 1)[1]: e for e in index["lessons"]}
        self.assertEqual(sorted(lessons), ["2026-11-01-conflict-ci.md", "2026-11-09-session-loss.md"])
        now, old = lessons["2026-11-09-session-loss.md"], lessons["2026-11-01-conflict-ci.md"]
        self.assertEqual((now["state"], now["context"], now["incidents"]),
                         ("confirmed", False, ["incident:" + R + "1474"]))
        self.assertEqual((old["state"], old["context"]), ("superseded", True))
        self.assertEqual(len(old["incidents"]), 3)
        [finding] = index["findings"]
        self.assertEqual((finding["state"], finding["incidents"]), ("reported", [
            "incident:" + R + "1467~stale-changes-label", "incident:" + R + "1472~stale-changes-label"]))
        self.assertEqual(index["missing"], ["decisions: not provided", "observations: not provided"])

    def test_older_lesson_naming_a_selected_item_without_a_card_is_context(self):
        with open(os.path.join(FIX, "lessons", "2026-10-20-unrelated.md")) as f:
            text = f.read().replace("#12", "#1514")
        with Store(extra={"2026-10-21-selected-pr.md": text}) as s:
            index = scan("--forge", FORGE, "--root", s.root, "--sha", s.sha)
        self.assertEqual(index["items"], {R + "1514": ["opened", "closed"]})
        [kept] = [e for e in index["lessons"] if e["path"].endswith("2026-10-21-selected-pr.md")]
        self.assertEqual((kept["context"], kept["incidents"], kept["items"]), (True, [], [R + "1514"]))

    def test_missing_lessons_store_at_a_valid_sha_is_missing_not_zero(self):
        with Store(lessons=False) as s:
            index = scan("--forge", FORGE, "--root", s.root, "--sha", s.sha)
        self.assertIsNone(index["lessons"])
        self.assertIsNone(index["inputs"]["lessons"])
        self.assertIn("lessons: unreadable at %s" % s.sha, index["missing"])
        self.assertEqual(index["inputs"]["findings"], 1)

    def test_decisions_and_observations_in_window_link_incidents(self):
        index = scan("--forge", FORGE, "--decisions", os.path.join(FIX, "decisions.json"),
                     "--observations", os.path.join(FIX, "observations.jsonl"))
        [decision] = index["decisions"]
        self.assertEqual(decision["incidents"], ["incident:" + R + "1474"])
        [obs] = index["observations"]
        self.assertEqual((obs["kind"], obs["incidents"]),
                         ("nudge", ["incident:" + R + "1053~deferred-handoff-renudge"]))


class Missing(unittest.TestCase):
    def test_missing_inputs_are_listed_and_null(self):
        index = scan("--decisions", "/nonexistent/decisions.json", "--root", ".", "--sha", "0" * 40)
        self.assertEqual(index["inputs"], {"forge": None, "lessons": None, "findings": None, "decisions": None,
                                           "observations": None})
        self.assertEqual(index["missing"], [
            "forge: not provided", "lessons: unreadable at %s" % ("0" * 40),
            "findings: unreadable at %s" % ("0" * 40), "decisions /nonexistent/decisions.json: not found",
            "observations: not provided"])
        for name in ("lessons", "findings", "decisions", "observations"):
            self.assertIsNone(index[name])
        self.assertEqual(index["incidents"], [])

    def test_no_sha_lists_both_stores(self):
        index = scan("--forge", FORGE)
        self.assertIn("lessons: no --sha", index["missing"])
        self.assertIn("findings: no --sha", index["missing"])
        self.assertEqual(index["inputs"]["forge"], 11)

    def test_malformed_input_exits_2(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{not json")
        try:
            code, out, err = run(*WINDOW, "--forge", f.name)
        finally:
            os.remove(f.name)
        self.assertEqual((code, out), (2, ""))
        self.assertIn("reflection-scan: unreadable input", err)


class Contract(unittest.TestCase):
    def test_triage_clusters_stay_open_only(self):
        items = forge()
        clustered = {m["ref"] for c in rs.tc.build(items, {}, {}, 10)["clusters"] for m in c["members"]}
        self.assertNotIn(R + "1474", clustered)
        self.assertIn(R + "1474", incidents(scan("--forge", FORGE)))

    def test_compact_deterministic_index_without_conclusions(self):
        with Store() as s:
            argv = ("--forge", FORGE, "--root", s.root, "--sha", s.sha)
            first, second = run(*WINDOW, *argv), run(*WINDOW, *argv)
        self.assertEqual(first, second)
        self.assertEqual(first[1].count("\n"), 1)
        self.assertEqual(sorted(json.loads(first[1])), [
            "decisions", "findings", "incidents", "inputs", "items", "keys", "lessons", "missing", "observations",
            "sha", "window"])

    def test_out_file_matches_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "index.json")
            code, out, _ = run(*WINDOW, "--forge", FORGE, "--out", path)
            with open(path) as f:
                self.assertEqual((code, f.read()), (0, out))


if __name__ == "__main__":
    unittest.main()
