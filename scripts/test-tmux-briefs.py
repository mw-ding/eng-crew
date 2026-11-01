#!/usr/bin/env python3
"""Brief lint for the rendered tmux briefs (#257, stdlib only).

Renders templates/runtimes/tmux/ from profiles/tmux.toml and fails on prose bugs the dry runs (#234) and the
live run (#139) found: typing into a role window, a `--project` other than "$CREW_PROJECT", a merge-ok
auto-applied, defaulted or recorded without the owner's words under merge_grant = "none", a raw flock instead
of `crew land-lock`, a `gh` command without -R (except `gh api`), a `--body-file` the brief never places under
`$CREW_STATE/runs/` (`crew kill` cleans it there, #270), a scratch file under `/tmp`, and a restart of an
`ambiguous` window outside the one synthesizer exception (#312). Prose that forbids the bad action (a never / no
/ not in the same clause) passes.

Also passes: a `$CREW_PROJECT` in escaped quotes inside a quoted command, an owner-facing `PATH` the sentence
fills from `$CREW_PROJECT`, and a `gh` command without -R when the brief carries the blanket -R rule. Tests:
a bad and a forbidding fixture per rule, the real rendered briefs pass, and (#303) the rendered reviewer
brief carries the one round-1 intake ack step. Run in CI.
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
PROJECT_OK = re.compile(r'"\$CREW_PROJECT"|\\"\$CREW_PROJECT\\"|\$CREW_PROJECT"')
# An owner-facing command (the owner's shell lacks the variable) may say PATH if the sentence fills it from it.
OWNER_PATH = re.compile(r"PATH replaced by the absolute path in `\$CREW_PROJECT`")
AUTO = re.compile(r"auto-?appl|automatic", re.I)
MERGE_OK = re.compile(r"merge-ok", re.I)
DEFAULTED = re.compile(r"default|deadline|silen|assum|implie|\bno\s+(answer|reply|response|objection)\b", re.I)
CONDITION = re.compile(r"\b(if|when|unless|until)\b[^,]*,", re.I)
FLOCK = re.compile(r"\bflock\b")
BODY_FILE = re.compile(r"--body-file|-F body=@")
TMP = re.compile(r"(?<![\w.$-])/tmp\b")
CODE = re.compile(r"`([^`]+)`")
RESTART = re.compile(r"\b(restart|respawn|kill)", re.I)
BLANKET_R = re.compile(r"Add\s+`-R\s+[^`]+`\s+to\s+every\s+`gh`\s+command\s+except\s+`gh\s+api`")


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
            if TMP.search(c) and not negated:
                flag("scratch file under /tmp, use $CREW_STATE/runs/", c)
        main = CONDITION.sub("", s)
        if merge_grant == "none" and not NEGATION.search(main) and (
                (AUTO.search(s) and "merge" in s.lower())
                or (MERGE_OK.search(s) and DEFAULTED.search(s))
                or (MERGE_OK.search(s) and re.search(r"record", s, re.I) and not re.search(r"owner", s, re.I))):
            flag('merge-ok without the owner\'s words under merge_grant = "none"', s)
        if "ambiguous" in s and RESTART.search(s) and not NEGATION.search(s) and "synthesizer" not in s.lower():
            flag("restarts an ambiguous window outside the synthesizer exception", s)
        for m in PROJECT.finditer(s):
            arg = m.group(2) or ""
            if not (PROJECT_OK.match(arg) or (arg.startswith("PATH") and OWNER_PATH.search(s))):
                flag('--project is not "$CREW_PROJECT"', s[m.start():m.end() + 20])
    if BODY_FILE.search(text) and "$CREW_STATE/runs/" not in text:
        flag("body file without a $CREW_STATE/runs/ location", BODY_FILE.search(text).group(0))
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
        self.check('`$CREW_BIN watch --source "$CREW_BIN poll --once --project ..." --project ...`\n',
                   '`$CREW_BIN watch --source "$CREW_BIN poll --once --project \\"$CREW_PROJECT\\"" '
                   '--project "$CREW_PROJECT"`\n', rule)
        self.check("Ask the owner with a runnable `crew attach WINDOW --rw --project PATH`.\n",
                   "Ask the owner with a runnable `crew attach WINDOW --rw --project PATH` for that window, "
                   "with PATH replaced by the absolute path in `$CREW_PROJECT`.\n", rule)
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

    def test_ambiguous_restart(self):
        rule = "restarts an ambiguous window outside the synthesizer exception"
        good = ("A window that misses its ack after the re-nudge is `ambiguous`: never restart it. One exception: the "
                "synthesizer window, once per PR, `$CREW_BIN kill WINDOW --project \"$CREW_PROJECT\"` and respawn it.\n")
        self.check("A window that misses its ack after the re-nudge is `ambiguous`: kill and respawn it.\n", good, rule)
        self.check("When `crew send` exits 4, the window is `ambiguous`, so restart it.\n", good, rule)

    def test_raw_flock(self):
        self.check("Take the land lock with `flock <state-dir>/locks/merge.lock`.\n",
                   "Use `$CREW_BIN land-lock acquire`, never a raw `flock`.\n", "raw flock")

    def test_body_file_location(self):
        self.check("Post it with `gh pr review <n> -R o/r --comment --body-file <file>`.\n",
                   "Post it with `gh pr review <n> -R o/r --comment --body-file <file>`, `<file>` being "
                   "`$CREW_STATE/runs/$CREW_ID.body.md`.\n", "body file without a $CREW_STATE/runs/ location")
        self.check("Write the PR body to `/tmp/crew-pr-body.md` first.\n",
                   "Never write the PR body under `/tmp`.\n", "scratch file under /tmp")

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
        briefs, grant = render()
        self.assertEqual(sorted(briefs), ["builder.md", "coordinator.md", "reviewer.md", "synthesizer.md"])
        problems = [p for n, t in briefs.items() for p in lint(n, t, grant)]
        self.assertEqual(problems, [])

    def test_coordinator_failed_nudge_rule(self):
        """#312: a failed nudge or a missed ack is `ambiguous`; only the synthesizer window gets one respawn."""
        text = " ".join(render()[0]["coordinator.md"].split())
        rule = text[text.index("A window whose nudge"):text.index("Beyond a band cap")]
        for want in ("exit 4", "no ack after the re-nudge", "is `ambiguous`", "never restart it", "One exception: the "
                     "synthesizer window", "once per PR", "locks/merge.pid", "$CREW_BIN kill WINDOW",
                     "$CREW_BIN spawn synthesizer --pr <n>", "re-send each other pending `land`", "ask the owner"):
            self.assertIn(want, rule)
        for other in ("builder", "reviewer", "ben", "vera"):
            self.assertNotIn(other, rule.lower())


class ReviewWithoutCI(unittest.TestCase):
    """#380: rendered routing holds red CI for findings and keeps CI out of verdicts."""

    def test_coordinator_routes_new_head_and_combines_failures(self):
        text = " ".join(render()[0]["coordinator.md"].split())
        route = text[text.index("- `new-head`"):text.index("- A reviewer `done:")]
        self.assertIn("spawn reviewer", route)
        self.assertIn("even with CI pending or red", route)
        for rule in ("hold while a review or validation pass", "running or queued",
                     "$CREW_STATE/ci/<n>-<head-sha>.json",
                     "one kind `fix` message", "both the findings refs and held CI refs",
                     "one fix handoff per PR/head/round", "If CI recovered", "never deliver a stale fix",
                     "CI green alone never spawns review or supplies approval", "`fix-at-head`",
                     "PATH CI_PATH", "failed checks and links", "retain referenced files until the builder reports `done:`", "A CI fix after an approval gets the light re-check",
                     "with the approval's round number"):
            self.assertIn(rule, text)

    def test_reviewer_records_ci_and_preserves_merge_gate(self):
        text = " ".join(render()[0]["reviewer.md"].split())
        for rule in ("without waiting for CI", "pending, red or green", "as information only",
                     "alone never fails an acceptance criterion or changes the verdict",
                     "independently reproduced failures", "CI green at head remains a synthesizer merge gate",
                     "For a CI fix after approval", "fresh review and validation sessions",
                     "Broader behavioural edits require normal review"):
            self.assertIn(rule, text)


class ReviewerIntakeAck(unittest.TestCase):
    """#303: the round-1 review pass posts the protocol §6 intake ack once per head, and nothing repeats it."""

    @classmethod
    def setUpClass(cls):
        briefs, _ = render()
        text = " ".join(briefs["reviewer.md"].split())
        cls.text = text
        cls.step = re.search(r"3\. Intake ack.*?(?= 4\. )", text).group(0)

    def test_ack_is_posted_once_by_the_round_one_review_pass(self):
        step = self.step
        self.assertEqual(self.text.count("[Vera/ack] intake @ <sha7>"), 1)
        self.assertIn("on a `review` pass for round `<k>` = 1 only (never the `validate` pass or a later round)", step)
        self.assertIn("post one COMMENT review `[Vera/ack] intake @ <sha7>`", step)
        self.assertIn("<!-- crew:v1 role=reviewer-validator pass=ack pr=<n> sha=<head-sha> round=n/a verdict=n/a -->",
                      step)

    def test_ack_skips_a_draft_and_a_head_that_already_has_one(self):
        self.assertIn("unless the PR is a draft or the live PR already has a `pass=ack` post at this head headed "
                      "`[Vera/ack] intake`", self.step)

    def test_ack_comes_after_the_guards_and_before_the_pass_work(self):
        order = [self.text.index(s) for s in ("1. Re-read the PR live", "2. Your engine must differ",
                                              "3. Intake ack", "4. Do the pass per")]
        self.assertEqual(order, sorted(order))
        self.assertIn("After steps 1 and 2", self.step)
        self.assertIn("before the review work", self.step)

    def test_ack_is_narrative_only(self):
        self.assertIn("It is narrative only: no round, no verdict, no state tag change, and never an approval.",
                      self.step)
        self.assertNotIn("pass=ack", self.text.replace(self.step, ""))


if __name__ == "__main__":
    unittest.main()
