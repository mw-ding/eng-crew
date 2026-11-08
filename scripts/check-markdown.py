#!/usr/bin/env python3
"""Local markdown lint for mdstack (issue #644): a dependency-free subset of
the markdownlint rules this repo configures (.markdownlint-cli2.yaml) and has
failed in CI, so a builder catches them before pushing. CI's markdownlint stays
the authority; this check aims to flag nothing markdownlint would not.

Rules: MD001 heading increment, MD003 heading style (consistent), MD009
trailing spaces (2 allowed as a hard break), MD012 multiple blank lines, MD018
no space after hash, MD022 blank lines around headings, MD031 blank lines
around fences, MD032 blank lines around lists (top-level lists only), MD040
fence language, MD047 final newline, MD056 table column count. Front matter is
skipped. Lines in fenced code are skipped; indented code and block quotes are
only partly understood, so some findings there are left to CI.

By default it checks the `*.md` files changed against the merge base with
`--base` (default origin/main), including uncommitted and untracked files.
`check-repo.py` runs it on every tracked `*.md` file (its `markdown` check).

Usage: check-markdown.py [--root DIR] [--base REF] [--all] [FILE...]
Every finding prints `path:line rule message`; exit 1 if any, else 0.
"""
import argparse
import os
import re
import subprocess
import sys

FENCE_OPEN = re.compile(
    r"^(?P<pre>(?:[ \t]*(?:>|[-*+]|\d{1,9}[.)])(?=[ \t]|$)[ \t]*)*)"
    r" {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
FENCE_CLOSE = re.compile(r"^[ \t>]*(?P<fence>`{3,}|~{3,})[ \t]*$")
ATX = re.compile(r"^ {0,3}(#{1,6})(?=[ \t]|$)(.*)$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
LIST_ITEM = re.compile(r"^( {0,3})([-*+]|\d{1,9}[.)])(?:([ \t]+)(.*))?$")
TABLE_DELIM = re.compile(r"^ *\|? *:?-+:? *(?:\| *:?-+:? *)*\|? *$")
FRONT_MATTER = re.compile(r"^---[ \t]*$")


def is_blank(line):
    """markdownlint's isBlankLine: empty, whitespace, `>` markers or only
    HTML comment text."""
    return not re.sub(r"<!--.*?-->|<!--.*|^.*?-->", "", line).replace(">", "").strip()


def indent(line):
    return len(line) - len(line.lstrip(" "))


def fences(body):
    """{open index: (close index or None, info)} for fenced code blocks."""
    out, i = {}, 0
    while i < len(body):
        m = FENCE_OPEN.match(body[i])
        if m and not (m.group("fence")[0] == "`" and "`" in m.group("info")):
            char, size = m.group("fence")[0], len(m.group("fence"))
            close = next((j for j in range(i + 1, len(body))
                          if (c := FENCE_CLOSE.match(body[j])) and c.group("fence")[0] == char
                          and len(c.group("fence")) >= size), None)
            out[i] = (close, m.group("info").strip())
            if close is None:
                break
            i = close
        i += 1
    return out


def comment_lines(body, code):
    """Indexes of lines touched by an HTML comment (outside code)."""
    out, inside = set(), False
    for i, line in enumerate(body):
        if i in code:
            continue
        touched, pos = inside, 0
        while True:
            k = line.find("-->" if inside else "<!--", pos)
            if k < 0:
                break
            touched, inside, pos = True, not inside, k + (3 if inside else 4)
        if touched:
            out.add(i)
    return out


def list_item(line):
    m = LIST_ITEM.match(line)
    if not m or HR.match(line):
        return None
    pad = len((m.group(3) or " ").expandtabs(4))
    return {"col": len(m.group(1)) + len(m.group(2)) + (1 if pad > 4 or not m.group(4) else pad),
            "ordered": m.group(2)[0].isdigit(), "start": m.group(2)[:-1],
            "empty": not (m.group(4) or "").strip()}


def cells(line):
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    return len(re.split(r"(?<!\\)\|", s))


def headings(body, code, skip):
    """[(start, end, level, style)] for ATX and setext headings."""
    out = []
    for i, line in enumerate(body):
        if i in code or i in skip:
            continue
        m = ATX.match(line)
        if m:
            closed = re.search(r"(?:^|[ \t])#+[ \t]*$", m.group(2))
            out.append((i, i, len(m.group(1)), "atx_closed" if closed else "atx"))
            continue
        m = SETEXT.match(line)
        if m and i > 0 and paragraph_end(body, i - 1, code, skip):
            out.append((i - 1, i, 1 if m.group(1)[0] == "=" else 2, "setext"))
    return out


def paragraph_end(body, i, code, skip):
    """True when line i ends a plain top-level paragraph (setext underline
    candidate): no list, quote, table, heading or HTML line in it."""
    j = i
    while j >= 0 and body[j].strip() and j not in code:
        line = body[j]
        if (j in skip or indent(line) > 3 or list_item(line) or ATX.match(line) or HR.match(line)
                or line.lstrip()[:1] in (">", "|", "<")):
            return False
        j -= 1
    return j < i


def lint(text):
    """[(line number, rule, message)] for one markdown document."""
    lines = re.split(r"\r\n|\r|\n", text)
    off = 0
    if lines and FRONT_MATTER.match(lines[0]):
        end = next((j for j in range(1, len(lines)) if FRONT_MATTER.match(lines[j])), None)
        if end is not None:
            off = end + 1
    body = lines[off:]
    found = []

    def flag(i, rule, msg):
        found.append((i + off + 1, rule, msg))

    fence = fences(body)
    code = set()
    for o, (c, _) in fence.items():
        code.update(range(o, (len(body) - 1 if c is None else c) + 1))
    skip = comment_lines(body, code)
    fence_end = {o: (len(body) - 1 if c is None else c) for o, (c, _) in fence.items()}

    heads = headings(body, code, skip)
    prev_level, style = None, None
    for s, e, level, kind in heads:
        if prev_level is not None and level > prev_level + 1:
            flag(s, "MD001", "Heading levels should only increment by one level at a time "
                 "[Expected: h%d; Actual: h%d]" % (prev_level + 1, level))
        prev_level = level
        style = style or kind
        if kind != style:
            flag(s, "MD003", "Heading style [Expected: %s; Actual: %s]" % (style, kind))
        if s > 0 and not is_blank(body[s - 1]):
            flag(s, "MD022", "Headings should be surrounded by blank lines [Above]")
        if e + 1 < len(body) and not is_blank(body[e + 1]):
            flag(s, "MD022", "Headings should be surrounded by blank lines [Below]")

    blanks = 0
    for i, line in enumerate(body):
        if i in code:
            blanks = 0
            continue
        trailing = len(line) - len(line.rstrip())
        if trailing and trailing != 2:
            flag(i, "MD009", "Trailing spaces [Expected: 0 or 2; Actual: %d]" % trailing)
        blanks = blanks + 1 if not line.strip() else 0
        if blanks > 1:
            flag(i, "MD012", "Multiple consecutive blank lines [Expected: 1; Actual: %d]" % blanks)
        if i not in skip and re.match(r"^#+[^# \t]", line) and not re.search(r"#\s*$", line) \
                and not line.startswith("#️⃣"):
            flag(i, "MD018", "No space after hash on atx style heading")

    for o, (c, info) in sorted(fence.items()):
        if o > 0 and not is_blank(body[o - 1]):
            flag(o, "MD031", "Fenced code blocks should be surrounded by blank lines [Above]")
        if c is not None and c + 1 < len(body) and not is_blank(body[c + 1]):
            flag(c, "MD031", "Fenced code blocks should be surrounded by blank lines [Below]")
        if not info:
            flag(o, "MD040", "Fenced code blocks should have a language specified")

    check_lists(body, fence_end, skip, flag)
    check_tables(body, code, skip, flag)

    if not is_blank(lines[-1]):
        found.append((len(lines), "MD047", "Files should end with a single newline character"))
    return sorted(found)


def block_start(line):
    return bool(ATX.match(line) or HR.match(line) or FENCE_OPEN.match(line)
                or line.lstrip().startswith((">", "<!--")))


def check_lists(body, fence_end, skip, flag):
    """MD032 for top-level lists: blank (or comment) line before the first
    line and after the last; lazy continuation lines belong to the list."""
    in_list, col, last, prev_blank, prev_para = False, 0, -1, True, False
    i = 0
    while i < len(body):
        line = body[i]
        end = fence_end.get(i, i)
        blank = not line.strip()
        item = None if i in skip or line.lstrip().startswith(">") else list_item(line)
        if in_list and not blank:
            if item or indent(line) >= col:
                col = item["col"] if item and indent(line) < col else col
                last = end
            elif not prev_blank and i not in fence_end and not block_start(line):
                last = end
            else:
                in_list = False
                if not prev_blank and not is_blank(line):
                    flag(last, "MD032", "Lists should be surrounded by blank lines [Below]")
        if not in_list and item and not (prev_para and (
                item["empty"] or (item["ordered"] and item["start"] != "1"))):
            if i > 0 and not is_blank(body[i - 1]):
                flag(i, "MD032", "Lists should be surrounded by blank lines [Above]")
            in_list, col, last = True, item["col"], end
        prev_blank = blank
        prev_para = (not blank and not in_list and i not in fence_end and i not in skip
                     and not block_start(line) and not SETEXT.match(line))
        i = end + 1


def check_tables(body, code, skip, flag):
    """MD056: every row has the header's cell count. A table is a header row
    with a pipe, then a delimiter row with the same cell count; rows run to a
    blank line or another block start."""
    i = 0
    while i + 1 < len(body):
        head, delim = body[i], body[i + 1]
        if (i in code or i + 1 in code or i in skip or "|" not in head or head.lstrip().startswith(">")
                or not TABLE_DELIM.match(delim.strip()) or cells(head) != cells(delim)):
            i += 1
            continue
        want, j = cells(head), i + 2
        while j < len(body) and body[j].strip() and j not in code and not block_start(body[j]) \
                and not list_item(body[j]):
            got = cells(body[j])
            if got != want:
                flag(j, "MD056", "Table column count [Expected: %d; Actual: %d]" % (want, got))
            j += 1
        i = j


def lint_file(path):
    """lint() for a file, or None when it is unreadable or binary."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if b"\0" in data:
        return None
    return lint(data.decode("utf-8", "replace"))


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=True).stdout


def changed_files(root, base):
    """`*.md` files changed since the merge base with `base`: committed,
    uncommitted and untracked; deleted files are skipped."""
    mb = git(root, "merge-base", base, "HEAD").strip()
    names = git(root, "diff", "--name-only", "--diff-filter=d", mb, "--", "*.md").split("\n")
    names += git(root, "ls-files", "--others", "--exclude-standard", "--", "*.md").split("\n")
    return sorted({n for n in names if n})


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.dirname(here), help="repo root (default: parent of scripts/)")
    ap.add_argument("--base", default="origin/main", help="ref to diff against (default: origin/main)")
    ap.add_argument("--all", action="store_true", help="check every tracked *.md file")
    ap.add_argument("files", nargs="*", help="files to check instead (repo-relative or absolute)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        if args.files:
            names = args.files
        elif args.all:
            names = [n for n in git(root, "ls-files", "-z", "--", "*.md").split("\0") if n]
        else:
            names = changed_files(root, args.base)
    except (OSError, subprocess.CalledProcessError) as e:
        print("check-markdown: cannot list files: %s" % (getattr(e, "stderr", "") or e).strip(), file=sys.stderr)
        return 2
    count = 0
    for name in names:
        for n, rule, msg in lint_file(os.path.join(root, name)) or []:
            print("%s:%d %s %s" % (name, n, rule, msg))
            count += 1
    if count:
        print("check-markdown: FAILED (%d finding%s)" % (count, "" if count == 1 else "s"), file=sys.stderr)
        return 1
    print("check-markdown: OK (%d file%s)" % (len(names), "" if len(names) == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
