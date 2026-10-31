#!/usr/bin/env python3
"""Brief lint for the rendered tmux briefs (#257, stdlib only).

Renders templates/runtimes/tmux/ from profiles/tmux.toml and fails on prose bugs the dry runs (#234) and the
live run (#139) found: typing into a role window, a `--project` other than "$CREW_PROJECT", a merge-ok
auto-applied, defaulted or recorded without the owner's words under merge_grant = "none", a raw flock instead
of `crew land-lock`, and a `gh` command without -R (except `gh api`). Prose that forbids the bad action
(a never / no / not in the same clause) passes.
"""
import contextlib
import importlib.util
import io
import os
import re
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("crew_render", os.path.join(HERE, "crew-render.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)

NEGATION = re.compile(r"\b(never|not|nor)\b|n't\b|\bno\b(?!\s+(answer|reply|response|objection))", re.I)
KEYS = re.compile(r"send[- ]keys|\b(type|types|typing|press|presses|pressing)\b.*"
                  r"(\b(window|pane|keys?|enter|return)\b)", re.I)
PROJECT = re.compile(r"--project(?![\w-])(\s+(\S+))?")
PROJECT_OK = re.compile(r'"\$CREW_PROJECT"|\$CREW_PROJECT"')
AUTO = re.compile(r"auto-?appl|automatic", re.I)
MERGE_OK = re.compile(r"merge-ok", re.I)
DEFAULTED = re.compile(r"default|deadline|silen|assum|implie|\bno\s+(answer|reply|response|objection)\b", re.I)
CONDITION = re.compile(r"\b(if|when|unless|until)\b[^,]*,", re.I)
FLOCK = re.compile(r"\bflock\b")
CODE = re.compile(r"`([^`]+)`")
BLANKET_R = re.compile(r"Add\s+`-R\s+[^`]+`\s+to\s+every\s+`gh`\s+command\s+except\s+`gh\s+api`")
# The current briefs pass once #256 lands (its CHANGELOG entry is the marker); until then the check is skipped.
GATE = "(issue #255, refs #139, PR #256,"


def sentences(text):
    """Paragraphs and list items, whitespace collapsed, split into sentences."""
    for block in re.split(r"\n\s*\n|\n(?=\s*(?:- |\d+\. ))", text):
        block = " ".join(block.split())
        yield from (s for s in re.split(r"(?<=[.!?;])\s+", block) if s)


def clauses(sentence):
    return [c for c in re.split(r"[,:;]\s+|[()]", sentence) if c.strip()]


def lint(name, text, merge_grant):
    """Return 'name: rule: snippet' problems for one rendered brief."""
    problems = []

    def flag(rule, snippet):
        problems.append("%s: %s: %s" % (name, rule, snippet.strip()))

    for s in sentences(text):
        for c in clauses(s):
            negated = bool(NEGATION.search(c))
            if KEYS.search(c) and not negated:
                flag("types into a role window", c)
            if FLOCK.search(c) and not negated:
                flag("raw flock, use crew land-lock", c)
        main = CONDITION.sub("", s)
        if merge_grant == "none" and not NEGATION.search(main) and (
                (AUTO.search(s) and "merge" in s.lower())
                or (MERGE_OK.search(s) and DEFAULTED.search(s))
                or (MERGE_OK.search(s) and re.search(r"record", s, re.I) and not re.search(r"owner", s, re.I))):
            flag('merge-ok without the owner\'s words under merge_grant = "none"', s)
        for m in PROJECT.finditer(s):
            if not (m.group(2) and PROJECT_OK.match(m.group(2))):
                flag('--project is not "$CREW_PROJECT"', s[m.start():m.end() + 20])
    if not BLANKET_R.search(" ".join(text.split())):
        for span in CODE.findall(text):
            for cmd in re.split(r";|&&|\|", " ".join(span.split())):
                words = cmd.split()
                if words[:1] == ["gh"] and words[1:2] != ["api"] and not ({"-R", "--repo"} & set(words)):
                    flag("gh command without -R", cmd)
    return problems


def render():
    """Render the real tmux briefs; return ({name: text}, merge_grant)."""
    project = os.path.join(ROOT, "profiles", "tmux.toml")
    values, problems = cr.resolve(project, None)
    assert not problems, problems
    tmp = tempfile.mkdtemp()
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(["--project", project, "--out", tmp])
        assert code == 0, out.getvalue()
        rt = os.path.join(tmp, "runtime")
        briefs = {}
        for n in sorted(os.listdir(rt)):
            with open(os.path.join(rt, n), encoding="utf-8") as f:
                briefs[n] = f.read()
    finally:
        shutil.rmtree(tmp)
    return briefs, values.get("runtime.options.merge_grant", "none")


def gate_open():
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        return GATE in f.read()


R = "Add `-R <owner>/<repo>` to every `gh` command except `gh api`.\n"


class Patterns(unittest.TestCase):
    """Each rule: the bad wording fails, the forbidding wording passes."""

    def check(self, bad, good, rule):
        got = lint("b.md", R + bad, "none")
        self.assertTrue(got and all(rule in p for p in got), got)
        self.assertEqual(lint("g.md", R + good, "none"), [])

    def test_send_keys(self):
        self.check("On a dialog, run `tmux send-keys -t WINDOW Enter` in the role window.\n",
                   "NEVER type into that window (no `tmux send-keys`, no `--rw` attach).\n",
                   "types into a role window")

    def test_type_or_press_in_role_window(self):
        self.check("If a trust prompt shows, type `y` into the builder window.\n",
                   "Never type into a role window. A typed line `inbox: <id>` names a line in `$CREW_INBOX`.\n",
                   "types into a role window")
        self.check("Then press Enter in the reviewer pane.\n", "Do not press keys in a role pane.\n",
                   "types into a role window")

    def test_project_argument(self):
        rule = '--project is not "$CREW_PROJECT"'
        self.check("Run `$CREW_BIN land-lock acquire --project crew.toml`.\n",
                   'Run `$CREW_BIN land-lock acquire --project "$CREW_PROJECT"`.\n', rule)
        self.check("every `$CREW_BIN` command takes `--project` with this repo's `crew.toml`.\n",
                   'every `$CREW_BIN` command takes `--project "$CREW_PROJECT"`.\n', rule)
        self.check("`$CREW_BIN watch --source \"$CREW_BIN poll --once --project ...\" --project ...`\n",
                   '`$CREW_BIN watch --source "$CREW_BIN poll --once --project $CREW_PROJECT" '
                   '--project "$CREW_PROJECT"`\n', rule)
        self.assertEqual(lint("g.md", R + "`gh project item-edit --project-id <id> -R o/r`\n", "none"), [])

    def test_merge_ok_auto_apply(self):
        rule = "merge-ok without the owner's words"
        good = ("A merge-ok ask never carries an auto-apply merge default: its default at the deadline is "
                "`hold` (keep the PR on hold and record that) or an escalation, never a merge. Record a merge-ok "
                "only from the owner's own words for that PR. An applied ask default is never a merge-ok.\n")
        self.check("If the owner does not answer by the deadline, auto-apply the merge-ok.\n", good, rule)
        self.check("The merge-ok ask defaults to merge at the deadline.\n", good, rule)
        self.check("Record the merge-ok from the standing doc-only grant.\n", good, rule)
        self.check("With no answer, treat the merge-ok as given.\n", good, rule)
        self.assertEqual(lint("b.md", R + "The merge-ok ask defaults to merge at the deadline.\n", "#110 PRs"), [])

    def test_raw_flock(self):
        self.check("Take the land lock with `flock <state-dir>/locks/merge.lock`.\n",
                   "Use `$CREW_BIN land-lock acquire`, never a raw `flock`.\n", "raw flock")

    def test_gh_without_repo(self):
        bad = "Run `gh pr merge <n> --squash` then `gh pr list --state open; gh api repos/o/r/pulls`.\n"
        got = lint("b.md", bad, "none")
        self.assertEqual(got, ["b.md: gh command without -R: gh pr merge <n> --squash",
                               "b.md: gh command without -R: gh pr list --state open"])
        self.assertEqual(lint("g.md", "Run `gh pr merge <n> -R o/r` and `gh api repos/o/r/pulls`.\n", "none"), [])
        self.assertEqual(lint("g.md", R + bad, "none"), [])


class CurrentBriefs(unittest.TestCase):
    """The real tmux briefs rendered from profiles/tmux.toml pass every rule."""

    def test_rendered_briefs_pass(self):
        if not gate_open():
            self.skipTest("waiting for #256 (tmux briefs: $CREW_PROJECT, no auto-apply) to land")
        briefs, grant = render()
        self.assertEqual(sorted(briefs), ["builder.md", "coordinator.md", "reviewer.md", "synthesizer.md"])
        problems = [p for n, t in briefs.items() for p in lint(n, t, grant)]
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
