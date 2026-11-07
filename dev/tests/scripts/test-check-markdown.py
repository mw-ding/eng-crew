#!/usr/bin/env python3
"""Tests for check-markdown.py (issue #644). Python 3 stdlib only, no network.

Fixtures are inline strings, not .md files, so CI's markdownlint never sees
the failing ones. Covers a pass and a fail fixture per rule (MD001, MD003,
MD009, MD012, MD018, MD022, MD031, MD032, MD040, MD047, MD056), front matter
and fenced-code skipping, the CLI's `path:line rule message` output and exit
codes, changed-file selection in a temp git repo (committed, uncommitted,
untracked; deleted and unchanged files skipped), `--all` on the current tree
(parity: no findings), and the `check-repo.py --only markdown` section.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
CHECK = os.path.join(SCRIPTS, "check-markdown.py")
spec = importlib.util.spec_from_file_location("check_markdown", CHECK)
md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md)
failed = []
F = "```"


def expect(name, ok, detail=""):
    print("%s %s" % ("ok  " if ok else "FAIL", name))
    if not ok:
        failed.append(name)
        print("     " + str(detail).replace("\n", "\n     "))


# (rule, passing text, failing text, failing line)
CASES = [
    ("MD001", "# A\n\n## B\n\n### C\n\n## D\n", "# A\n\n### C\n", 3),
    ("MD003", "# A\n\n## B\n", "# A\n\n## B ##\n", 3),
    ("MD003", "A\n=\n\nB\n-\n", "A\n=\n\n## B\n", 4),
    ("MD009", "# A\n\nhard break  \nnext\n", "# A\n\ntext \n", 3),
    ("MD009", "# A\n\n%s sh\nx   \n%s\n" % (F, F), "# A\n\ntext   \n", 3),
    ("MD012", "# A\n\ntext\n", "# A\n\n\ntext\n", 3),
    ("MD012", "# A\n\n%s sh\n\n\n%s\n" % (F, F), "# A\n\ntext\n\n", 5),
    ("MD018", "# A #\n\n## B #\n\n<!-- #1 -->\n", "# A\n\n#102: lane\n", 3),
    ("MD018", "# A\n\n%s sh\n#!/bin/sh\n%s\n" % (F, F), "#A\n", 1),
    ("MD022", "# A\n\ntext\n\n## B\n", "# A\ntext\n", 1),
    ("MD022", "# A\n\n<!-- x -->\n## B\n<!-- y -->\n", "# A\n\ntext\n## B\n", 4),
    ("MD031", "# A\n\n%s sh\nx\n%s\n" % (F, F), "# A\n\ntext\n%s sh\nx\n%s\n" % (F, F), 4),
    ("MD031", "# A\n\n- item\n\n  %s sh\n  x\n  %s\n" % (F, F), "# A\n\n%s sh\nx\n%s\ntext\n" % (F, F), 5),
    ("MD032", "# A\n\n- a\n- b\n\ntext\n", "# A\n\ntext\n- a\n", 4),
    ("MD032", "# A\n\n- a\n  lazy\ncontinued\n\n1. b\n\n   - nested\n", "# A\n\n- a\n# B\n", 3),
    ("MD032", "# A\n\ntext\n2. not a list\n", "# A\n\n- a\n%s sh\nx\n%s\n" % (F, F), 3),
    ("MD040", "# A\n\n~~~ text\nx\n~~~\n", "# A\n\n%s\nx\n%s\n" % (F, F), 3),
    ("MD047", "# A\n", "# A", 1),
    ("MD047", "# A\n<!-- end -->", "# A\n\ntext", 3),
    ("MD056", "# A\n\n| a | b |\n| - | - |\n| 1 | \\| 2 |\n\ntext | x\n",
     "# A\n\n| a | b | c |\n| --- | --- | --- |\n| only one |\n", 5),
    ("MD056", "# A\n\n| a |\n| - |\n| 1 |\n\n- after\n", "# A\n\na | b\n--|--\n1 | 2 | 3\n", 5),
]

for k, (rule, good, bad, line) in enumerate(CASES):
    got = md.lint(good)
    expect("%s pass fixture %d has no findings" % (rule, k), got == [], got)
    got = md.lint(bad)
    expect("%s fail fixture %d flags %s at line %d" % (rule, k, rule, line), (line, rule) in [(n, r) for n, r, _ in got], got)

fm = "---\ntype: fixed\nissue: 1\n---\n\nEntry text.\n"
expect("front matter is skipped", md.lint(fm) == [], md.lint(fm))
got = md.lint("---\nx: 1\n---\n\n# A\n\n\nB\n")
expect("line numbers count front matter lines", [(n, r) for n, r, _ in got] == [(7, "MD012")], got)
code = "# A\n\n%s md\n#bad  \n\n\n- x\n| a |\n%s\n" % (F, F)
expect("fenced code lines are skipped", md.lint(code) == [], md.lint(code))


def run(*args, cwd=None):
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout, p.stderr


def git(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True,
                   env={**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@x"})


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


with tempfile.TemporaryDirectory() as d:
    git(d, "init", "-q", "-b", "main")
    write(d, "old.md", "#bad\n")
    write(d, "gone.md", "# ok\n")
    write(d, "keep.md", "# ok\n")
    git(d, "add", ".")
    git(d, "commit", "-q", "-m", "base")
    git(d, "checkout", "-q", "-b", "topic")
    write(d, "docs/committed.md", "# A\ntext\n")
    git(d, "rm", "-q", "gone.md")
    git(d, "add", ".")
    git(d, "commit", "-q", "-m", "topic")
    write(d, "keep.md", "# ok\n\n\nx\n")
    write(d, "new.md", "# A")
    write(d, "notes.txt", "#bad\n")
    rc, out, err = run(CHECK, "--root", d, "--base", "main")
    lines = out.splitlines()
    want = ["docs/committed.md:1 MD022", "keep.md:3 MD012", "new.md:1 MD047"]
    expect("changed files: committed, uncommitted and untracked *.md, as path:line rule message",
           rc == 1 and [" ".join(l.split()[:2]) for l in lines] == want, out + err)
    expect("changed files: unchanged old.md and deleted gone.md are skipped",
           "old.md" not in out and "gone.md" not in out, out)
    rc, out, err = run(CHECK, "--root", d, "--all")
    expect("--all checks every tracked *.md file", rc == 1 and "old.md:1 MD018" in out
           and "new.md" not in out, out + err)
    rc, out, err = run(CHECK, "--root", d, "--base", "no-such-ref")
    expect("an unknown --base exits 2", rc == 2 and "cannot list files" in err, out + err)
    git(d, "checkout", "-q", "-f", "main")
    git(d, "clean", "-qfd")
    rc, out, err = run(CHECK, "--root", d, "--base", "main")
    expect("no changed files exits 0", rc == 0 and "OK (0 files)" in out, out + err)

rc, out, err = run(CHECK, "--all")
expect("parity: --all on the current tree has no findings", rc == 0, out + err)
rc, out, err = run(os.path.join(SCRIPTS, "check-repo.py"), "--only", "markdown")
expect("check-repo.py --only markdown passes on the current tree", rc == 0, out + err)
with tempfile.TemporaryDirectory() as d:
    write(d, "doc.md", "# A\n\n#bad\n")
    write(d, "other.txt", "#bad")
    rc, out, err = run(os.path.join(SCRIPTS, "check-repo.py"), "--root", d, "--only", "markdown")
    expect("check-repo.py markdown section reports file:line [markdown] rule",
           rc == 1 and "doc.md:3: [markdown] MD018" in out and "other.txt" not in out, out + err)

if failed:
    print("\n%d failed" % len(failed))
    sys.exit(1)
print("\nall passed")
