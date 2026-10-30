#!/usr/bin/env python3
"""Repo guard for eng-crew (spec R1, R6): secret scan, required docs/sections,
relative markdown links, crew marker SHAs, optional name denylist. Python 3
stdlib only, no network.

Usage: check-repo.py [--root DIR] [--config FILE] [--only secrets|docs|links|markers|blockers|shapes|denylist]...
Every failure prints `file:line: [rule] reason`; exit 1 if any, else 0.
"""
import argparse
import os
import re
import subprocess
import sys
from urllib.parse import unquote

SKIP_DIRS = {".git"}  # only used by the fallback walk; see walk()
PLACEHOLDER = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*>")  # documented allowlist form

# (rule id, regex, reason). A match is a failure unless the rule has a
# placeholder check below. Placeholders such as `ghp_<token>` never match the
# token regexes because `<` is outside their character classes.
# Boundaries are alnum-only lookarounds, not `\b`: `\b` treats `_` as a word
# character, so Markdown emphasis like `_ghp_<token>_` would slip through.
PATTERNS = [
    ("github-token", re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}"),
     "GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)"),
    ("github-pat", re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
     "GitHub fine-grained token (github_pat_)"),
    ("sk-key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
     "sk- style API key"),
    ("aws-access-key", re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[A-Z0-9]{16}(?![A-Za-z0-9])"),
     "AWS access key id"),
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
     "private key block"),
]
BEARER = re.compile(r"""authorization["']?\s*[:=]\s*["']?bearer\s+([^\s"']+)""", re.I)
URL_CRED = re.compile(r"""(?<![A-Za-z0-9])[a-z][a-z0-9+.-]*://([^/\s:@"'<>]+|<[^>\s]+>):([^/\s@"']+)@""", re.I)
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
# A `crew:v1` marker, possibly wrapped over several lines; group `body` excludes
# the `<!--` / `-->` delimiters. Its `key=value` fields are whitespace-separated;
# a value is a run of non-space characters and `<...>` placeholders (which may
# contain spaces but not `<`, `>` or `=`, so a placeholder never crosses into the
# next field). A stray `<` with no closing `>` before the next `<`, `>` or `=` is
# an ordinary value character, so the value runs to the next whitespace and any
# junk tail is checked.
MARKER = re.compile(r"<!--\s*crew:v1\b(?P<body>.*?)-->", re.S)
MARKER_FIELD = re.compile(r"(?<!\S)(?P<key>[^\s=<]+)=(?P<value>(?:<[^<>=]*>|<(?![^<>=]*>)|[^\s<])*)")
PLACEHOLDER_VALUE = re.compile(r"<[^<>=]*>")
FULL_SHA = re.compile(r"[0-9a-f]{40}")
SHORT_SHA_NAME = re.compile(r"sha7|short", re.I)


def is_placeholder(value):
    return PLACEHOLDER.match(value) is not None and PLACEHOLDER.sub("", value, 1).strip(".,;:)`\"'") == ""


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


def read_lines(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if b"\0" in data:
        return None  # binary
    return data.decode("utf-8", "replace").splitlines()


def tracked_files(root):
    """Paths from `git ls-files` when root is the top of a git work tree, else
    None (e.g. the test temp dirs)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*args):
        return subprocess.run(["git", "-C", root, *args], capture_output=True, env=env, check=True).stdout

    try:
        top = git("rev-parse", "--show-toplevel").decode("utf-8", "replace").strip()
        if os.path.realpath(top) != os.path.realpath(root):
            return None
        return sorted(p for p in git("ls-files", "-z").decode("utf-8", "replace").split("\0") if p)
    except (OSError, subprocess.CalledProcessError):
        return None


def walk(root):
    """Yield (full path, repo-relative path) for every file to scan: the tracked
    files in a git work tree (so a tracked `node_modules/` is scanned and an
    untracked or ignored one is not), else everything except `.git/`."""
    names = tracked_files(root)
    if names is not None:
        for rel in names:
            yield os.path.join(root, rel), rel
        return
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            full = os.path.join(dirpath, name)
            yield full, os.path.relpath(full, root).replace(os.sep, "/")


def check_secrets(root, fail):
    for full, rel in walk(root):
        lines = read_lines(full)
        if lines is None:
            continue
        for n, line in enumerate(lines, 1):
            for rule, rx, reason in PATTERNS:
                if rx.search(line):
                    fail(rel, n, rule, reason + "; use a placeholder like <token>")
            for m in BEARER.finditer(line):
                if not is_placeholder(m.group(1)):
                    fail(rel, n, "bearer-header",
                         "bearer auth header with a literal value; use <token>")
            for m in URL_CRED.finditer(line):
                if not (is_placeholder(m.group(1)) and is_placeholder(m.group(2))):
                    fail(rel, n, "url-credentials",
                         "URL with embedded credentials; use <user>:<password>")


def check_markers(root, fail):
    """Lesson 2026-10-23 (`pass=watch` marker carried a 7-char SHA): every
    `crew:v1` marker's sha= is a full 40-hex SHA or a placeholder that does not
    name a short SHA (sha7, short). Fenced examples are checked too."""
    for full, rel in walk(root):
        if not rel.endswith(".md"):
            continue
        lines = read_lines(full)
        if lines is None:
            continue
        text = "\n".join(lines)
        for marker in MARKER.finditer(text):
            for m in MARKER_FIELD.finditer(marker.group("body")):
                if m.group("key") != "sha":
                    continue
                value = m.group("value")
                n = text.count("\n", 0, marker.start("body") + m.start()) + 1
                if PLACEHOLDER_VALUE.fullmatch(value):
                    if SHORT_SHA_NAME.search(value):
                        fail(rel, n, "marker-sha",
                             "sha= placeholder names a short SHA; use <head-sha> (full 40-char head SHA)")
                elif not FULL_SHA.fullmatch(value):
                    fail(rel, n, "marker-sha",
                         "sha= must be the full 40-char head SHA, got '%s'" % value)


BLOCKER_FILES = ("docs/protocol.md", "templates/runtimes/grok-bot/synthesizer.md")
BLOCKER_PATTERNS = [
    ("hold-until", re.compile(r"hold-until")),
    ("open rereview", re.compile(r"open\s+`?steer\s+cmd=rereview`?")),
]


def check_blockers(root, fail):
    """Lesson 2026-10-29 (synthesizer squashed past an open hold-until / rereview):
    protocol §7 and the synthesizer template both still name the two blockers.
    Static presence guard only; the live PR state is not checkable offline.
    A file that is absent from the root is skipped."""
    for rel in BLOCKER_FILES:
        lines = read_lines(os.path.join(root, rel))
        if lines is None:
            continue
        text = "\n".join(lines)
        for name, pat in BLOCKER_PATTERNS:
            if not pat.search(text):
                fail(rel, 1, "synthesizer-blockers",
                     "merge-gate text must name the '%s' blocker (see docs/lessons/2026-10-29-synthesizer-hold-race.md)" % name)


VERIFICATION_DOC = "docs/verification.md"
VERIFICATION_SHAPES = ("web", "cli", "service", "api", "mobile")


def check_shapes(root, fail):
    """Issue #83 (typed verification evidence): the shape table in the
    verification doc has a row for each of web, CLI, service, API and mobile.
    A row is a table line whose first cell is the shape name. Fenced code blocks and HTML comments are
    ignored: a `<!--` inside a fence opens nothing, and an unterminated `<!--`
    hides everything after it. A doc absent from the root is skipped."""
    lines = read_lines(os.path.join(root, VERIFICATION_DOC))
    if lines is None:
        return
    # Fences first (a `<!--` in a fence is not a comment), then comments, so a
    # commented-out row is not a row; an unterminated comment runs to EOF.
    visible, _ = scan_fences(lines, unclosed_as_text=False)
    first = set()
    for _, line in strip_html_comments(visible):
        if line.lstrip().startswith("|"):
            cell = line.strip().strip("|").split("|", 1)[0]
            first.add(cell.strip().strip("*`").strip().lower())
    for shape in VERIFICATION_SHAPES:
        if shape not in first:
            fail(VERIFICATION_DOC, 1, "verification-shapes",
                 "shape table lacks a row for '%s' (see docs/lessons/2026-10-29-typed-verify-evidence.md)" % shape)


def check_denylist(root, fail):
    """Portable spec P6 (#127): no org-internal names in eng-crew. The names live
    only in a file outside the repo, one per line (`#` comments and blank lines
    ignored), named by $CREW_DENYLIST; unset means skip. Case-insensitive
    whole-word match over the scanned files. A hit names the denylist line, never
    the term, so CI logs do not leak it either."""
    path = os.environ.get("CREW_DENYLIST")
    if not path:
        print("check-repo: denylist skipped (CREW_DENYLIST unset)", file=sys.stderr)
        return
    lines = read_lines(path)
    if lines is None:
        fail("$CREW_DENYLIST", 1, "denylist", "denylist file missing or unreadable")
        return
    terms = [(n, re.compile(r"(?<!\w)%s(?!\w)" % re.escape(t.strip()), re.I))
             for n, t in enumerate(lines, 1) if t.strip() and not t.strip().startswith("#")]
    for full, rel in walk(root):
        text = read_lines(full)
        for n, line in enumerate(text or [], 1):
            for entry, rx in terms:
                if rx.search(line):
                    fail(rel, n, "denylist", "matches $CREW_DENYLIST entry on line %d; remove the internal name" % entry)


def parse_config(path, fail):
    """Lines: `path` (file must exist) or `path :: ## Heading` (heading line
    must exist, exact text). `#` at line start and blank lines are ignored."""
    files, sections = [], []
    lines = read_lines(path)
    if lines is None:
        fail(os.path.basename(path), 1, "config", "required-docs config missing or unreadable")
        return files, sections
    rel = os.path.basename(path)
    for n, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "::" in line:
            doc, _, heading = (p.strip() for p in line.partition("::"))
            if not doc or not re.match(r"#{1,6} \S", heading):
                fail(rel, n, "config", "bad section line; expected `path :: ## Heading`")
                continue
            sections.append((n, doc, heading))
        else:
            files.append((n, line))
    return files, sections


def check_docs(root, config, fail):
    cfg_rel = os.path.relpath(config, root).replace(os.sep, "/")
    quiet = lambda f, n, r, why: fail(cfg_rel, n, r, why)
    files, sections = parse_config(config, quiet)
    for n, doc in files:
        if not os.path.isfile(os.path.join(root, doc)):
            fail(cfg_rel, n, "missing-file", "required file not found: " + doc)
    for n, doc, heading in sections:
        lines = read_lines(os.path.join(root, doc))
        if lines is None:
            fail(cfg_rel, n, "missing-file", "required file not found: " + doc)
            continue
        # Fail closed: an unclosed fence hides its heading-like lines (CommonMark)
        visible, unclosed = scan_fences(lines, unclosed_as_text=False)
        if not any(line.rstrip() == heading for _, line in strip_html_comments(visible)):
            hint = "" if unclosed is None else " (unclosed code fence at %s:%d)" % (doc, unclosed)
            fail(cfg_rel, n, "missing-section", "%s lacks required section '%s'%s" % (doc, heading, hint))


def check_links(root, fail):
    root_real = os.path.realpath(root)
    for full, rel in walk(root):
        if not rel.endswith(".md"):
            continue
        lines = read_lines(full)
        if lines is None:
            continue
        for n, line in unfenced(lines):
            text = strip_code_spans(line)
            targets = link_destinations(text)
            ref = REFDEF.match(text)
            if ref:
                targets.append(ref.group(1) if ref.group(1) is not None else ref.group(2))
            for t in targets:
                if re.match(r"^([a-z][a-z0-9+.-]*:|//|#)", t, re.I) or PLACEHOLDER.search(t):
                    continue  # external, fragment-only, or documented placeholder
                path = unquote(re.split(r"[#?]", t, maxsplit=1)[0])
                if not path:
                    continue
                if "\0" in path:
                    fail(rel, n, "broken-link", "relative link does not resolve: " + t)
                    continue
                base = root if path.startswith("/") else os.path.dirname(full)
                dest = os.path.realpath(os.path.join(base, path.lstrip("/")))
                inside = dest == root_real or dest.startswith(root_real + os.sep)
                if not inside:
                    fail(rel, n, "broken-link", "link escapes the repo: " + t)
                elif not os.path.exists(dest):
                    fail(rel, n, "broken-link", "relative link does not resolve: " + t)


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=os.path.dirname(here), help="repo root (default: parent of scripts/)")
    ap.add_argument("--config", help="required-docs config (default: <script dir>/required-docs.txt)")
    ap.add_argument("--only", action="append", choices=["secrets", "docs", "links", "markers", "blockers", "shapes", "denylist"],
                    help="run only these checks (repeatable)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    config = os.path.abspath(args.config or os.path.join(here, "required-docs.txt"))
    checks = set(args.only or ["secrets", "docs", "links", "markers", "blockers", "shapes", "denylist"])

    failures = []

    def fail(path, line, rule, reason):
        failures.append("%s:%d: [%s] %s" % (path, line, rule, reason))

    if "secrets" in checks:
        check_secrets(root, fail)
    if "docs" in checks:
        check_docs(root, config, fail)
    if "links" in checks:
        check_links(root, fail)
    if "markers" in checks:
        check_markers(root, fail)
    if "blockers" in checks:
        check_blockers(root, fail)
    if "shapes" in checks:
        check_shapes(root, fail)
    if "denylist" in checks:
        check_denylist(root, fail)

    for f in failures:
        print(f)
    if failures:
        print("check-repo: FAILED (%d problem%s)" % (len(failures), "" if len(failures) == 1 else "s"),
              file=sys.stderr)
        return 1
    print("check-repo: OK (%s)" % ", ".join(sorted(checks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
