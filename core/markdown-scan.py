"""Markdown line scanning shared by the repo guard (`scripts/check-repo.py`,
`links` check), `scripts/release-bundle.py` and the shipped
`scripts/docs-scan.py` (#281): fenced code blocks (CommonMark rules), inline
code spans, HTML comments, inline link destinations and reference
definitions. Python 3 stdlib only.
"""
import re

LINK_OPEN = re.compile(r"!?\[[^\]]*\]\(\s*")
REFDEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(?:<([^>]*)>|(\S+))")
# Fence opener: optional container prefixes (block-quote `>`, list markers
# `-`/`*`/`+`/`1.`/`1)`, nested to any depth), then up to 3 spaces, then the fence.
FENCE_OPEN = re.compile(
    r"^(?P<pre>(?:[ \t]*(?:>|[-*+]|\d{1,9}[.)])(?=[ \t]|$)[ \t]*)*)"
    r" {0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$")
# Fence closer: optional block-quote markers/indent, then the fence and nothing else.
FENCE_CLOSE = re.compile(r"^(?P<pre>[ \t>]*)(?P<fence>`{3,}|~{3,})[ \t]*$")
HTML_COMMENT_OPEN, HTML_COMMENT_CLOSE = "<!--", "-->"


def _closer_index(lines, start, opener, max_indent):
    char, length = opener
    for j in range(start, len(lines)):
        m = FENCE_CLOSE.match(lines[j])
        if (m and m.group("fence")[0] == char and len(m.group("fence")) >= length
                and len(m.group("pre").expandtabs(4)) <= max_indent):
            return j
    return None


def scan_fences(lines, unclosed_as_text):
    """Return ([(line number, line)] outside fenced code blocks, line number of
    the first unclosed fence or None). Fence lines themselves are not returned.

    CommonMark rules: a fence opens with 3+ backticks or tildes (a backtick
    opener's info string has no backtick), also after list markers and
    block-quote `>` prefixes, and closes only on a fence of the same character,
    at least as long, followed by nothing but whitespace, indented at most 3
    columns past the opener's own column (more lenient inside containers, so a
    closer is never missed). CommonMark runs an unclosed fence to the end of
    the file. With unclosed_as_text, such an opener is instead treated as plain
    text (and still reported), so a stray fence line, e.g. the closer of a fence
    this scanner failed to recognise, cannot hide the rest of the file."""
    out, unclosed = [], None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = FENCE_OPEN.match(line)
        if m and not (m.group("fence")[0] == "`" and "`" in m.group("info")):
            col = len(line[:m.start("fence")].expandtabs(4))
            max_indent = col + 3 if m.group("pre") else 3
            j = _closer_index(lines, i + 1, (m.group("fence")[0], len(m.group("fence"))), max_indent)
            if j is not None:
                i = j + 1
                continue
            if unclosed is None:
                unclosed = i + 1
            if not unclosed_as_text:
                break  # the fence runs to the end of the file
        else:
            out.append((i + 1, line))
        i += 1
    return out, unclosed


def unfenced(lines, unclosed_as_text=True):
    return scan_fences(lines, unclosed_as_text)[0]


def strip_code_spans(line):
    """Remove inline code spans: a backtick run closes at the next run of the
    same length; a backslash-escaped backtick is literal; an unmatched run is
    literal (so the text after it is still checked)."""
    tokens = list(re.finditer(r"\\.|`+", line))
    out, pos, i = [], 0, 0
    while i < len(tokens):
        run = tokens[i].group()
        close = None if run.startswith("\\") else next(
            (j for j in range(i + 1, len(tokens)) if tokens[j].group() == run), None)
        if close is None:
            i += 1
            continue
        out.append(line[pos:tokens[i].start()])
        pos, i = tokens[close].end(), close + 1
    out.append(line[pos:])
    return "".join(out)


def strip_html_comments(lines):
    """Yield (line number, line) for lines with no HTML comment text on them;
    `<!-- ... -->` may span lines, and an unclosed one runs to the end."""
    in_comment = False
    for n, line in lines:
        touched, pos = in_comment, 0
        while True:
            if in_comment:
                k = line.find(HTML_COMMENT_CLOSE, pos)
                if k < 0:
                    break
                in_comment, pos = False, k + len(HTML_COMMENT_CLOSE)
            else:
                k = line.find(HTML_COMMENT_OPEN, pos)
                if k < 0:
                    break
                touched = in_comment = True
                pos = k + len(HTML_COMMENT_OPEN)
        if not touched:
            yield n, line


def link_destinations(text):
    """Destinations of inline links/images in one line. Handles `<dest>` and
    balanced parentheses in bare destinations (`other(v1).md`)."""
    out = []
    for m in LINK_OPEN.finditer(text):
        i, depth = m.end(), 0
        if text.startswith("<", i):
            j = text.find(">", i)
            if j > 0:
                out.append(text[i + 1:j])
            continue
        j = i
        while j < len(text) and not text[j].isspace():
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                if depth == 0:
                    break
                depth -= 1
            j += 1
        if j > i:
            out.append(text[i:j])
    return out
