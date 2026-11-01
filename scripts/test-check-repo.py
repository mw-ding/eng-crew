#!/usr/bin/env python3
"""Tests for check-repo.py. Python 3 stdlib only, no network.

Bad secret fixtures are stored defanged (a `~~` marker splits each token) so
the repo never contains a matching string; this runner strips the marker into a
temp dir and expects check-repo.py to fail with `file:3: [<rule>]`, where
<rule> is named on the fixture's `# expect:` line. Structural checks (missing
file/section, broken link) are built in temp dirs so no extra .md fixtures
exist for markdownlint/lychee to see.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "check-repo.py")
FIX = os.path.join(HERE, "fixtures")
failed = []


def run(root, *extra):
    p = subprocess.run([sys.executable, CHECK, "--root", root, *extra],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


def expect(name, ok, detail=""):
    print("%s %s" % ("ok  " if ok else "FAIL", name))
    if not ok:
        failed.append(name)
        print("     " + detail.replace("\n", "\n     "))


def assembled(src, dst_dir):
    with open(src, encoding="utf-8") as f:
        text = f.read().replace("~~", "")
    dst = os.path.join(dst_dir, os.path.basename(src))
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.basename(src)


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


for name in sorted(os.listdir(os.path.join(FIX, "bad"))):
    src = os.path.join(FIX, "bad", name)
    rule = next(l.split(":", 1)[1].strip() for l in open(src) if l.startswith("# expect:"))
    with tempfile.TemporaryDirectory() as d:
        rel = assembled(src, d)
        rc, out = run(d, "--only", "secrets")
        want = "%s:3: [%s]" % (rel, rule)
        expect("bad/" + name + " fails with " + want, rc == 1 and want in out, out)

with tempfile.TemporaryDirectory() as d:
    for name in sorted(os.listdir(os.path.join(FIX, "good"))):
        assembled(os.path.join(FIX, "good", name), d)
    rc, out = run(d, "--only", "secrets")
    expect("good fixtures pass", rc == 0 and out.startswith("check-repo: OK"), out)

CFG = "R.md\nR.md :: ## Need\n"
with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n## Need\n\n[ok](other/x.md#frag) [web](https://example.invalid/x)\n")
    write(d, "other/x.md", "# X\n")
    rc, out = run(d, "--config", os.path.join(d, "cfg.txt"))
    expect("good tree passes", rc == 0, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n## Need\n")
    os.remove(os.path.join(d, "R.md"))
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("missing file fails", rc == 1 and "cfg.txt:1: [missing-file]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n```\n## Need\n```\n")
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("missing section fails (fenced heading ignored)",
           rc == 1 and "cfg.txt:2: [missing-section]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "# R\n\nok\n\nsee [gone](missing.md) and `[code](nope.md)`\n\n```\n[fenced](nope.md)\n```\n")
    rc, out = run(d, "--only", "links")
    expect("broken link fails with file:line",
           rc == 1 and "R.md:5: [broken-link]" in out and out.count("broken-link") == 1, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "[up](../outside.md)\n")
    rc, out = run(d, "--only", "links")
    expect("link escaping repo fails", rc == 1 and "R.md:1: [broken-link]" in out, out)

# Fence handling (CommonMark): a fence closes only on the same character, at
# least as long as the opener, with nothing but whitespace after it.
with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "# R\n\n```md\n~~~\n```\n\n[broken](missing.md)\n")
    rc, out = run(d, "--only", "links")
    expect("mixed fences: ~~~ inside ``` does not close it",
           rc == 1 and "R.md:7: [broken-link]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "# R\n\n````md\n```\n[inside](nope.md)\n```\n````\n\n[broken](missing.md)\n")
    rc, out = run(d, "--only", "links")
    expect("longer opener: ``` lines inside ```` stay fenced",
           rc == 1 and "R.md:9: [broken-link]" in out and out.count("broken-link") == 1, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "# R\n\n~~~\n```\n~~~ not a closer\n[inside](nope.md)\n  ~~~~  \n\n[broken](missing.md)\n")
    rc, out = run(d, "--only", "links")
    expect("closer needs same char, >= length, only whitespace after",
           rc == 1 and "R.md:9: [broken-link]" in out and out.count("broken-link") == 1, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n```md\n~~~\n## Need\n```\n")
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("heading inside a mixed fence does not satisfy a section",
           rc == 1 and "cfg.txt:2: [missing-section]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n````\n```\n## Need\n```\n````\n")
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("heading inside a longer fence does not satisfy a section",
           rc == 1 and "cfg.txt:2: [missing-section]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n```\ncode\n```\n\n## Need\n")
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("heading after a closed fence satisfies a section", rc == 0, out)

# Link destinations: URL-decoding and balanced parentheses.
with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "[x](other%20file.md) [y](other(v1).md) [z](<other file.md>)\n")
    write(d, "other file.md", "# O\n")
    write(d, "other(v1).md", "# O\n")
    rc, out = run(d, "--only", "links")
    expect("%20 and (parenthesized) destinations resolve", rc == 0, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "[x](gone%20file.md) [y](gone(v1).md) [z](bad%00.md)\n")
    rc, out = run(d, "--only", "links")
    expect("missing decoded/parenthesized destinations fail",
           rc == 1 and out.count("R.md:1: [broken-link]") == 3, out)

# Fences opened on list-item / block-quote lines (round-2 finding): the content
# indent is recognised, so the indented closer does not open a new fence.
LIST_FENCE = "- ```sh\n  echo hi\n  ```\n\nSee [c](missing.md).\n"
for label, body in [
    ("dash list item", LIST_FENCE),
    ("star list item", LIST_FENCE.replace("- ```", "* ```", 1)),
    ("plus list item", LIST_FENCE.replace("- ```", "+ ```", 1)),
    ("1. list item", "1. ```sh\n   echo hi\n   ```\n\nSee [c](missing.md).\n"),
    ("1) list item", "1) ```sh\n   echo hi\n   ```\n\nSee [c](missing.md).\n"),
    ("nested list item", "- a\n  - ```sh\n    echo hi\n    ```\n\nSee [c](missing.md).\n"),
    ("block quote", "> ```sh\n> echo hi\n> ```\n\nSee [c](missing.md).\n"),
    ("quoted list item", "> - ```sh\n>   echo hi\n>   ```\n\nSee [c](missing.md).\n"),
]:
    with tempfile.TemporaryDirectory() as d:
        write(d, "R.md", body)
        rc, out = run(d, "--only", "links")
        expect("fence after " + label + " does not hide a broken link",
               rc == 1 and out.count("[broken-link]") == 1 and "R.md:" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "- ```sh\n  [inside](nope.md)\n  ```\n")
    rc, out = run(d, "--only", "links")
    expect("link inside a list-item fence is skipped", rc == 0, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n- ```sh\n  echo hi\n  ```\n\n## Need\n")
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("heading after a list-item fence satisfies a section", rc == 0, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n- ```sh\n  ## Need\n  ```\n")
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("heading inside a list-item fence does not satisfy a section",
           rc == 1 and "cfg.txt:2: [missing-section]" in out, out)

# Safety rule: an unclosed fence is plain text for the link check, so a stray
# fence line (e.g. the closer of a fence the scanner did not recognise) cannot
# hide the rest of the file. The section check stays CommonMark (fail closed)
# and says why.
with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "# R\n\nintro\n\n```\n\nSee [c](missing.md).\n")
    rc, out = run(d, "--only", "links")
    expect("unclosed bare fence does not hide a broken link",
           rc == 1 and "R.md:7: [broken-link]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "# R\n\n```sh\necho hi\n\nSee [c](missing.md).\n")
    rc, out = run(d, "--only", "links")
    expect("unclosed fence with an info string does not hide a broken link",
           rc == 1 and "R.md:6: [broken-link]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "cfg.txt", CFG)
    write(d, "R.md", "# R\n\n```\n\n## Need\n")
    rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
    expect("unclosed fence: section stays unsatisfied and the report names the fence",
           rc == 1 and "[missing-section]" in out and "unclosed code fence at R.md:3" in out, out)

# Inline code spans: matched by backtick-run length; escaped backticks are literal.
for label, body, want in [
    ("escaped backticks are not a span", "Use \\` [broken](missing.md) \\` here.\n", 1),
    ("unmatched backtick is literal", "A ` stray [broken](missing.md) here.\n", 1),
    ("double-backtick span hides its link", "Use `` a ` [x](missing.md) `` here.\n", 0),
    ("single-backtick span hides its link", "Use `[x](missing.md)` here.\n", 0),
    ("span then real link", "`a` [x](missing.md) `b`\n", 1),
    ("run-length mismatch is not a span", "``[x](missing.md)` and [y](missing.md)\n", 2),
]:
    with tempfile.TemporaryDirectory() as d:
        write(d, "R.md", body)
        rc, out = run(d, "--only", "links")
        expect("code span: " + label, out.count("[broken-link]") == want and rc == (1 if want else 0), out)

# HTML comments do not satisfy a required heading.
for label, body, ok in [
    ("multi-line comment", "# R\n\n<!--\n## Need\n-->\n", False),
    ("single-line comment", "# R\n\n<!-- ## Need -->\n", False),
    ("unclosed comment", "# R\n\n<!--\n## Need\n", False),
    ("heading after a closed comment", "# R\n\n<!--\nx\n-->\n\n## Need\n", True),
    ("comment marker inside a fence is text", "# R\n\n```\n<!--\n```\n\n## Need\n", True),
]:
    with tempfile.TemporaryDirectory() as d:
        write(d, "cfg.txt", CFG)
        write(d, "R.md", body)
        rc, out = run(d, "--only", "docs", "--config", os.path.join(d, "cfg.txt"))
        expect("html comment: " + label,
               rc == 0 if ok else (rc == 1 and "cfg.txt:2: [missing-section]" in out), out)

# Reference definitions share the inline <dest> handling.
with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", '[ref]: <other file.md> "t"\n[ref2]: other%20file.md\n[ref3]: <>\n')
    write(d, "other file.md", "# O\n")
    rc, out = run(d, "--only", "links")
    expect("refdef <dest> with spaces resolves", rc == 0, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", '[ref]: <gone file.md> "t"\n')
    rc, out = run(d, "--only", "links")
    expect("missing refdef <dest> with spaces fails whole",
           rc == 1 and "R.md:1: [broken-link]" in out and "gone file.md" in out, out)

# Marker SHA rule (lesson: the `pass=watch` marker carried a 7-char SHA, #69):
# every `crew:v1` marker's sha= is a full 40-hex SHA or a non-short placeholder.
FULL = "0123456789abcdef0123456789abcdef01234567"
for label, body, want in [
    ("7-char hex sha fails", "# R\n\n<!-- crew:v1 role=builder pass=watch pr=1 sha=0123abc round=n/a -->\n", 1),
    ("39-char hex sha fails", "<!-- crew:v1 pass=watch sha=" + FULL[:39] + " -->\n", 1),
    ("41-char hex sha fails", "<!-- crew:v1 pass=watch sha=" + FULL + "0 -->\n", 1),
    ("<sha7> placeholder fails", "<!-- crew:v1 pass=watch sha=<sha7> round=n/a -->\n", 1),
    ("<short-sha> placeholder fails", "<!-- crew:v1 pass=watch sha=<short-sha> -->\n", 1),
    ("40-hex sha passes", "<!-- crew:v1 pass=watch sha=" + FULL + " round=n/a -->\n", 0),
    ("<head-sha> placeholder passes", "<!-- crew:v1 pass=ack sha=<head-sha> round=n/a -->\n", 0),
    ("<new-head-sha> placeholder passes", "<!-- crew:v1 pass=verdict sha=<new-head-sha> -->\n", 0),
    ("<full-40-char-head-sha> placeholder passes", "<!-- crew:v1 pass=hold sha=<full-40-char-head-sha> -->\n", 0),
    ("wrapped <40-char head sha> placeholder passes", "<!-- crew:v1 role=<role> sha=<40-char\nhead sha> round=<k> -->\n", 0),
    ("short sha on a wrapped marker fails with its own line", "<!-- crew:v1 role=builder\n  pass=watch sha=abc1234\n  round=n/a -->\n", 1),
    ("marker inside a fence is still checked", "```md\n<!-- crew:v1 pass=watch sha=abc1234 -->\n```\n", 1),
    ("40-hex sha with no space before --> passes", "<!-- crew:v1 pass=watch sha=" + FULL + "-->\n", 0),
    ("short sha with no space before --> fails", "<!-- crew:v1 pass=watch sha=abc1234-->\n", 1),
    ("placeholder followed by trailing chars fails", "<!-- crew:v1 pass=watch sha=<head-sha>abc1234 -->\n", 1),
    ("full sha followed by unclosed < fails", "<!-- crew:v1 pass=watch sha=" + FULL + "<junk -->\n", 1),
    ("placeholder followed by unclosed < fails", "<!-- crew:v1 pass=watch sha=<head-sha><junk -->\n", 1),
    ("unclosed placeholder earlier in marker does not hide short sha", "<!-- crew:v1 pass=watch pr=<n sha=abc1234 round=<k> -->\n", 1),
    ("closed placeholder earlier in marker still checks short sha", "<!-- crew:v1 pass=watch pr=<n> sha=abc1234 round=<k> -->\n", 1),
    ("previous-sha= short value is not the sha", "<!-- crew:v1 pass=watch previous-sha=abc1234 sha=" + FULL + " -->\n", 0),
    ("only previous-sha= is not reported as sha", "<!-- crew:v1 pass=watch previous-sha=abc1234 -->\n", 0),
    ("non-marker comment is ignored", "<!-- note sha=abc1234 -->\n", 0),
]:
    with tempfile.TemporaryDirectory() as d:
        write(d, "R.md", body)
        rc, out = run(d, "--only", "markers")
        expect("marker sha: " + label, out.count("[marker-sha]") == want and rc == (1 if want else 0), out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "<!-- crew:v1 role=builder\n  pass=watch sha=abc1234\n  round=n/a -->\n")
    rc, out = run(d, "--only", "markers")
    expect("marker sha: failure reports file:line of the sha=", "R.md:2: [marker-sha]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "<!-- crew:v1 pass=watch sha=abc1234 -->\n")
    rc, out = run(d)
    expect("marker sha: runs by default", rc == 1 and "[marker-sha]" in out, out)

# Synthesizer blockers: protocol and template must name hold-until and an open
# rereview; a file absent from the root is skipped.
GOOD = "A hold-until-X blocks. An open `steer cmd=rereview` at head blocks.\n"
for label, files, want in [
    ("both files name both blockers", {"docs/protocol.md": GOOD, "templates/runtimes/grok-bot/synthesizer.md": GOOD}, 0),
    ("template missing hold-until", {"docs/protocol.md": GOOD, "templates/runtimes/grok-bot/synthesizer.md": "open steer cmd=rereview\n"}, 1),
    ("protocol missing open rereview", {"docs/protocol.md": "hold-until\nsteer cmd=rereview\n", "templates/runtimes/grok-bot/synthesizer.md": GOOD}, 1),
    ("neither file present is skipped", {"R.md": "x\n"}, 0),
]:
    with tempfile.TemporaryDirectory() as d:
        for rel, body in files.items():
            write(d, rel, body)
        rc, out = run(d, "--only", "blockers")
        expect("blockers: " + label, out.count("[synthesizer-blockers]") == want and rc == (1 if want else 0), out)

# Verification shapes: the table in docs/verification.md has all five rows.
def shape_table(shapes):
    return "| Shape | Required when |\n|---|---|\n" + "".join("| %s | x |\n" % s for s in shapes)


ALL_SHAPES = ["Web", "CLI", "Service", "API", "Mobile"]
for label, files, want in [
    ("all five shapes present", {"docs/verification.md": shape_table(ALL_SHAPES)}, 0),
    ("mobile row missing", {"docs/verification.md": shape_table(ALL_SHAPES[:-1])}, 1),
    ("two rows missing", {"docs/verification.md": shape_table(["Web", "CLI", "API"])}, 2),
    ("shape only in prose does not count", {"docs/verification.md": shape_table(ALL_SHAPES[:-1]) + "\nMobile is TBD.\n"}, 1),
    ("commented-out row does not count", {"docs/verification.md": shape_table(ALL_SHAPES[:-1]) + "<!-- | Mobile | x |\n-->\n"}, 1),
    ("single-line commented row does not count", {"docs/verification.md": shape_table(ALL_SHAPES[:-1]) + "<!-- | Mobile | x | -->\n"}, 1),
    ("unterminated comment hides the row after it", {"docs/verification.md": shape_table(ALL_SHAPES[:-1]) + "<!--\n| Mobile | x |\n"}, 1),
    ("comment opener inside a fence is not a comment",
     {"docs/verification.md": "```\n<!--\n```\n" + shape_table(ALL_SHAPES) + "<!-- note -->\n"}, 0),
    ("doc absent is skipped", {"R.md": "x\n"}, 0),
]:
    with tempfile.TemporaryDirectory() as d:
        for rel, body in files.items():
            write(d, rel, body)
        rc, out = run(d, "--only", "shapes")
        expect("shapes: " + label, out.count("[verification-shapes]") == want and rc == (1 if want else 0), out)

# Spec status (#259): every slice row in portable.md section 5 has a Status cell.
SPEC_HEAD = "# Spec\n\n## 5. Milestones and slices\n\n### M1\n\n"
SPEC_TAIL = "\n## 6. Decisions\n\n| Date | Decision |\n|---|---|\n| d | x |\n"


def slice_table(*statuses, header="| ID | Issue | Status |"):
    return header + "\n|---|---|---|\n" + "".join("| 1.%d | #%d | %s |\n" % (i, i, s) for i, s in enumerate(statuses))


for label, body, want in [
    ("all statuses valid", SPEC_HEAD + slice_table("open", "done", "dropped") + SPEC_TAIL, 0),
    ("empty status fails", SPEC_HEAD + slice_table("done", "") + SPEC_TAIL, 1),
    ("unknown status fails", SPEC_HEAD + slice_table("closed", "wip") + SPEC_TAIL, 2),
    ("missing cell fails", SPEC_HEAD + slice_table("done") + "| 1.9 | #9 |\n" + SPEC_TAIL, 1),
    ("header without Status fails", SPEC_HEAD + slice_table("done", header="| ID | Issue | Scope |") + SPEC_TAIL, 1),
    ("second table is checked too", SPEC_HEAD + slice_table("done") + "\n### M2\n\n" + slice_table("todo") + SPEC_TAIL, 1),
    ("tables outside section 5 are ignored", "# Spec\n\n## 4. Layout\n\n| Path | X |\n|---|---|\n| a | b |\n\n"
     + SPEC_HEAD[len("# Spec\n\n"):] + slice_table("done") + SPEC_TAIL, 0),
    ("fenced table is ignored", SPEC_HEAD + slice_table("done") + "\n```\n| ID | Issue |\n| 1 | #1 |\n```\n" + SPEC_TAIL, 0),
    ("no slice tables fails closed", SPEC_HEAD + "No tables.\n" + SPEC_TAIL, 1),
]:
    with tempfile.TemporaryDirectory() as d:
        write(d, "docs/specs/portable.md", body)
        rc, out = run(d, "--only", "spec-status")
        expect("spec-status: " + label, out.count("[spec-status]") == want and rc == (1 if want else 0), out)

with tempfile.TemporaryDirectory() as d:
    write(d, "R.md", "x\n")
    rc, out = run(d, "--only", "spec-status")
    expect("spec-status: spec absent is skipped", rc == 0, out)

rc, out = run(os.path.dirname(HERE), "--only", "spec-status")
expect("spec-status: the current tree passes", rc == 0, out)

# CHANGELOG fragments (#264): every file under changes/ is a valid fragment.
FRAG = "---\ntype: added\nissue: 7\npr: 9\ndate: 2026-10-31\nbox-skill: none\n---\n\nA change,\nwrapped.\n"
OK_FRAG = "changes/unreleased/7-a-b.md"
for label, rel, body, line in [
    ("valid fragment passes", OK_FRAG, FRAG, None),
    ("pr TBD passes", OK_FRAG, FRAG.replace("pr: 9", "pr: TBD"), None),
    ("bad name fails", "changes/unreleased/7_A.md", FRAG, 1),
    ("fragment outside changes/unreleased fails", "changes/7-a-b.md", FRAG, 1),
    ("nested fragment fails", "changes/unreleased/x/7-a-b.md", FRAG, 1),
    ("no front matter fails", OK_FRAG, "A change.\n", 1),
    ("unclosed front matter fails", OK_FRAG, "---\ntype: added\n", 1),
    ("unknown type fails", OK_FRAG, FRAG.replace("type: added", "type: misc"), 2),
    ("issue not the file name's fails", OK_FRAG, FRAG.replace("issue: 7", "issue: 8"), 3),
    ("bad pr fails", OK_FRAG, FRAG.replace("pr: 9", "pr: #9"), 4),
    ("bad date fails", OK_FRAG, FRAG.replace("2026-10-31", "2026-02-30"), 5),
    ("duplicate field fails", OK_FRAG, FRAG.replace("pr: 9", "pr: 9\npr: 10"), 5),
    ("missing field fails", OK_FRAG, FRAG.replace("box-skill: none\n", ""), 6),
    ("unknown field fails", OK_FRAG, FRAG.replace("box-skill: none", "box-skill: none\nowner: x"), 7),
    ("empty entry fails", OK_FRAG, FRAG.split("\nA change")[0] + "\n", 7),
    ("blank line in entry fails", OK_FRAG, FRAG.replace("A change,\n", "A change,\n\n"), 10),
]:
    with tempfile.TemporaryDirectory() as d:
        write(d, rel, body)
        rc, out = run(d, "--only", "fragments")
        ok = rc == 0 if line is None else (
            rc == 1 and "%s:%d: [changelog-fragment]" % (rel, line) in out and out.count("[changelog-fragment]") == 1)
        expect("fragments: " + label, ok, out)

rc, out = run(os.path.dirname(HERE), "--only", "fragments")
expect("fragments: the current tree passes", rc == 0, out)

# File selection: in a git work tree only tracked files are scanned (a tracked
# node_modules is checked, an untracked one is not); elsewhere, everything.
GIT_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(d, *args):
    return subprocess.run(["git", "-C", d, *args], capture_output=True, env=GIT_ENV).returncode == 0


with tempfile.TemporaryDirectory() as d:
    if git(d, "init", "-q"):
        write(d, "docs/node_modules/x.md", "[b](missing.md)\n")
        write(d, "untracked/node_modules/y.md", "[b](missing.md)\n")
        write(d, "untracked/z.md", "[b](missing.md)\n")
        git(d, "add", "docs/node_modules/x.md")
        rc, out = run(d, "--only", "links")
        expect("git tree: tracked node_modules is scanned, untracked is not",
               rc == 1 and "docs/node_modules/x.md:1:" in out and out.count("[broken-link]") == 1, out)
    else:
        print("skip git tree test (git unavailable)")

with tempfile.TemporaryDirectory() as d:
    write(d, "a/node_modules/x.md", "[b](missing.md)\n")
    write(d, ".git/y.md", "[b](missing.md)\n")
    rc, out = run(d, "--only", "links")
    expect("outside git: node_modules is scanned, .git is not",
           rc == 1 and "a/node_modules/x.md:1:" in out and out.count("[broken-link]") == 1, out)

# Denylist (#127): names come only from the file named by $CREW_DENYLIST, so
# none is committed. The fixture names here are made up.
def run_denylist(root, denylist):
    env = {k: v for k, v in os.environ.items() if k != "CREW_DENYLIST"}
    if denylist is not None:
        env["CREW_DENYLIST"] = denylist
    p = subprocess.run([sys.executable, CHECK, "--root", root, "--only", "denylist"],
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr


with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as lists:
    write(d, "docs/a.md", "# A\n\nRun it with the Zorblax CLI.\n")
    write(d, "docs/b.md", "# B\n\nzorblaxian and xzorblax are other words; quux-tool is fine.\n")
    names = os.path.join(lists, "deny.txt")
    write(lists, "deny.txt", "# fake names\n\nzorblax\nquux tool\n")
    rc, out, _ = run_denylist(d, names)
    expect("denylist: case-insensitive whole-word hit fails with file:line, term not echoed",
           rc == 1 and "docs/a.md:3: [denylist]" in out and out.count("[denylist]") == 1
           and "zorblax" not in out.lower(), out)
    write(lists, "deny.txt", "frobnicator\n")
    rc, out, _ = run_denylist(d, names)
    expect("denylist: miss passes", rc == 0 and out.startswith("check-repo: OK (denylist)"), out)
    rc, out, err = run_denylist(d, None)
    expect("denylist: var unset skips", rc == 0 and "CREW_DENYLIST unset" in err, out + err)
    rc, out, _ = run_denylist(d, os.path.join(lists, "missing.txt"))
    expect("denylist: unreadable file fails closed", rc == 1 and "[denylist]" in out, out)

# Deliverables manifest (#235): every tracked path matches exactly one row.
MANIFEST_ROWS = ("# rows\n"
                 "docs/*.md\tdeliverable\tall\n"
                 "docs/specs/**\tinternal\tn/a\n"
                 "scripts/deliverables.txt\tinternal\tn/a\n")


def deliverables_tree(d, manifest, *paths):
    write(d, "scripts/deliverables.txt", manifest)
    for rel in paths:
        write(d, rel, "x\n")
    git(d, "add", "-A")
    return run(d, "--only", "deliverables")


with tempfile.TemporaryDirectory() as d:
    if git(d, "init", "-q"):
        rc, out = deliverables_tree(d, MANIFEST_ROWS, "docs/a.md", "docs/specs/p/q.md")
        expect("deliverables: each tracked path matches one row (`*` stays in a segment)",
               rc == 0 and out.startswith("check-repo: OK (deliverables)"), out)
        write(d, "docs/untracked.txt", "x\n")
        rc, out = run(d, "--only", "deliverables")
        expect("deliverables: an untracked path is ignored", rc == 0, out)
        os.remove(os.path.join(d, "docs/untracked.txt"))
        rc, out = deliverables_tree(d, MANIFEST_ROWS, "docs/b.txt")
        expect("deliverables: unclassified tracked path fails",
               rc == 1 and "docs/b.txt:1: [unclassified]" in out and out.count("[unclassified]") == 1, out)
    else:
        print("skip deliverables tests (git unavailable)")

with tempfile.TemporaryDirectory() as d:
    if git(d, "init", "-q"):
        rc, out = deliverables_tree(d, MANIFEST_ROWS + "docs/**\tinternal\tn/a\n", "docs/a.md")
        expect("deliverables: double match fails and names both rows",
               rc == 1 and "docs/a.md:1: [double-classified]" in out and "rows 2, 5" in out
               and out.count("[double-classified]") == 1, out)
        rc, out = deliverables_tree(d, MANIFEST_ROWS + "docs/**\tshipped\tall\n")
        expect("deliverables: bad manifest row fails",
               rc == 1 and "scripts/deliverables.txt:5: [deliverables-config]" in out, out)
        os.remove(os.path.join(d, "scripts/deliverables.txt"))
        rc, out = run(d, "--only", "deliverables")
        expect("deliverables: missing manifest fails closed",
               rc == 1 and "scripts/deliverables.txt:1: [deliverables-config]" in out, out)

with tempfile.TemporaryDirectory() as d:
    write(d, "a.md", "# A\n")
    p = subprocess.run([sys.executable, CHECK, "--root", d, "--only", "deliverables"],
                       capture_output=True, text=True)
    expect("deliverables: outside a git work tree it is skipped",
           p.returncode == 0 and "deliverables skipped" in p.stderr, p.stdout + p.stderr)

rc, out = run(os.path.dirname(HERE), "--only", "deliverables")
expect("deliverables: the current tree passes", rc == 0, out)

if failed:
    print("test-check-repo: %d FAILED" % len(failed))
    sys.exit(1)
print("test-check-repo: all passed")
