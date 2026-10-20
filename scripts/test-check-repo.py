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

if failed:
    print("test-check-repo: %d FAILED" % len(failed))
    sys.exit(1)
print("test-check-repo: all passed")
