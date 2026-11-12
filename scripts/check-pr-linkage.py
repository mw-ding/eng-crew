#!/usr/bin/env python3
"""Check a PR body's issue linkage before the PR opens (#1418).

Usage:
  check-pr-linkage.py --body-file BODY --closes N [--closes M] --allocation URL
  check-pr-linkage.py --body-file BODY --release N

With --closes, each N (the issue the newest signed allocation gives this PR)
needs exactly one whole line `Closes #N`, and the body must cite the
allocation URL. With --release (a release cut, #1416), the body needs one
whole line `Release issue: #N` and `Refs #N`, and no closing keyword at all.
Every other closing keyword (close, closes, closed, fix, fixes, fixed,
resolve, resolves, resolved, before `#N`, `owner/repo#N` or an issue URL) is
flagged with its line, including descriptive mentions of closed issues.
Findings print the keyword and reference apart, so pasting them into a PR
body or comment adds no closing reference.
Exit 0 when clean, 1 with one finding per line, 2 on a usage error.
Python 3 standard library only. See docs/backends/github.md#linkage.
"""
import argparse
import re
import sys

KEYWORD = re.compile(
    r"\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?):?[ \t]+"
    r"([\w.-]+/[\w.-]+#\d+|#\d+|https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+)", re.I)


def findings(body, closes=(), release=None, allocation=None):
    """Return the list of linkage findings for body; empty means clean."""
    out = []
    intended = {"Closes #%d" % n: n for n in closes}
    seen = {n: 0 for n in closes}
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip() in intended:
            seen[intended[line.strip()]] += 1
            if seen[intended[line.strip()]] == 1:
                continue
        for m in KEYWORD.finditer(line):
            out.append("line %d: closing keyword `%s` before `%s` outside the intended closing line; "
                       "reword it (for example `#N, now closed`)" % (i, m.group(1), m.group(2)))
    for n, count in seen.items():
        if count == 0:
            out.append("no whole `Closes` line for #%d, the issue the allocation gives this PR" % n)
    if release is not None:
        lines = [l.strip() for l in body.splitlines() if l.strip().lower().startswith("release issue:")]
        if lines != ["Release issue: #%d" % release]:
            out.append("need exactly one whole line `Release issue: #%d`" % release)
        if not re.search(r"(?<![\w/])Refs #%d\b" % release, body):
            out.append("no `Refs #%d`" % release)
    if allocation is not None and allocation not in body:
        out.append("the body does not cite the allocation %s" % allocation)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body-file", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--closes", type=int, action="append", metavar="N")
    mode.add_argument("--release", type=int, metavar="N")
    ap.add_argument("--allocation", metavar="URL")
    args = ap.parse_args(argv)
    if args.closes and not args.allocation:
        ap.error("--closes needs --allocation, the newest signed allocation's URL")
    try:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    except OSError as e:
        ap.error("cannot read %s: %s" % (args.body_file, e.strerror))
    found = findings(body, args.closes or (), args.release, args.allocation)
    for line in found:
        print("check-pr-linkage: " + line)
    if found:
        return 1
    what = "release issue #%d" % args.release if args.release is not None else \
        "closing line for " + ", ".join("#%d" % n for n in args.closes) + "; allocation cited"
    print("check-pr-linkage: OK (%s)" % what)
    return 0


if __name__ == "__main__":
    sys.exit(main())
