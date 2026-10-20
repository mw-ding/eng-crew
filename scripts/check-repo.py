#!/usr/bin/env python3
"""Repo guard for eng-crew (spec R1, R6): secret scan, required docs/sections,
relative markdown links. Python 3 stdlib only, no network.

Usage: check-repo.py [--root DIR] [--config FILE] [--only secrets|docs|links]...
Every failure prints `file:line: [rule] reason`; exit 1 if any, else 0.
"""
import argparse
import os
import re
import sys

SKIP_DIRS = {".git", "node_modules"}
PLACEHOLDER = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*>")  # documented allowlist form

# (rule id, regex, reason). A match is a failure unless the rule has a
# placeholder check below. Placeholders such as `ghp_<token>` never match the
# token regexes because `<` is outside their character classes.
PATTERNS = [
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
     "GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)"),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}"),
     "GitHub fine-grained token (github_pat_)"),
    ("sk-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
     "sk- style API key"),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[A-Z0-9]{16}\b"),
     "AWS access key id"),
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
     "private key block"),
]
BEARER = re.compile(r"""authorization["']?\s*[:=]\s*["']?bearer\s+([^\s"']+)""", re.I)
URL_CRED = re.compile(r"""\b[a-z][a-z0-9+.-]*://([^/\s:@"'<>]+|<[^>\s]+>):([^/\s@"']+)@""", re.I)
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[^)]*)?\)")
REFDEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
FENCE = re.compile(r"^\s{0,3}(```|~~~)")


def is_placeholder(value):
    return PLACEHOLDER.match(value) is not None and PLACEHOLDER.sub("", value, 1).strip(".,;:)`\"'") == ""


def read_lines(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if b"\0" in data:
        return None  # binary
    return data.decode("utf-8", "replace").splitlines()


def walk(root):
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
        in_fence = False
        found = False
        for line in lines:
            if FENCE.match(line):
                in_fence = not in_fence
            elif not in_fence and line.rstrip() == heading:
                found = True
                break
        if not found:
            fail(cfg_rel, n, "missing-section", "%s lacks required section '%s'" % (doc, heading))


def check_links(root, fail):
    root_real = os.path.realpath(root)
    for full, rel in walk(root):
        if not rel.endswith(".md"):
            continue
        lines = read_lines(full)
        if lines is None:
            continue
        in_fence = False
        for n, line in enumerate(lines, 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            text = re.sub(r"`[^`]*`", "", line)  # ignore inline code
            targets = [m.group(1) for m in LINK.finditer(text)]
            ref = REFDEF.match(text)
            if ref:
                targets.append(ref.group(1))
            for t in targets:
                if re.match(r"^([a-z][a-z0-9+.-]*:|//|#)", t, re.I) or PLACEHOLDER.search(t):
                    continue  # external, fragment-only, or documented placeholder
                path = re.split(r"[#?]", t, maxsplit=1)[0]
                if not path:
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
    ap.add_argument("--only", action="append", choices=["secrets", "docs", "links"],
                    help="run only these checks (repeatable)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    config = os.path.abspath(args.config or os.path.join(here, "required-docs.txt"))
    checks = set(args.only or ["secrets", "docs", "links"])

    failures = []

    def fail(path, line, rule, reason):
        failures.append("%s:%d: [%s] %s" % (path, line, rule, reason))

    if "secrets" in checks:
        check_secrets(root, fail)
    if "docs" in checks:
        check_docs(root, config, fail)
    if "links" in checks:
        check_links(root, fail)

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
