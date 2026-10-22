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

if failed:
    print("test-check-repo: %d FAILED" % len(failed))
    sys.exit(1)
print("test-check-repo: all passed")
