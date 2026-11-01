#!/usr/bin/env python3
"""Cut the CHANGELOG `## [Unreleased]` section into a dated version section.

Usage: changelog-cut.py <version> [--file CHANGELOG.md] [--fragments DIR] [--date YYYY-MM-DD] [--dry-run]

Moves every line under `## [Unreleased]` (its `###` subsections and entries,
byte for byte) under a new `## [<version>] - <date>` heading and leaves an
empty `## [Unreleased]` above it (Keep a Changelog 1.1.0). Each fragment in
--fragments (default: `changes/unreleased/` next to --file; format in
check-repo.py) becomes an entry under its `### <Type>` heading, newest PR
first and ahead of the existing entries; a missing heading is added in Keep a
Changelog order. The fragments are then deleted (kept on --dry-run). The date
defaults to today in UTC. Refuses, with exit 1 and nothing changed: no
entries and no fragments, a malformed fragment or one with `pr: TBD`, a
version that is not SemVer, a version that already exists, and a version not
greater than the latest one. Standard library only. Not run in CI.
"""
import argparse
import importlib.util
import os
import re
import sys
from datetime import date, datetime, timezone

_spec = importlib.util.spec_from_file_location(
    "check_repo", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-repo.py"))
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)

# semver.org 2.0.0 regex: MAJOR.MINOR.PATCH[-pre-release][+build], no leading v.
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
VERSION_HEADING = re.compile(r"^## \[([^\]]+)\]")
UNRELEASED = "## [Unreleased]"
HEADINGS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")


class Refused(Exception):
    pass


def precedence(version):
    m = SEMVER.match(version)
    core = tuple(int(x) for x in m.group(1, 2, 3))
    if m.group(4) is None:
        return core, (1,)
    ids = tuple((0, int(i), "") if i.isdigit() else (1, 0, i)
                for i in m.group(4).split("."))
    return core, (0, ids)


def fragment_names(directory):
    """Non-hidden names in the fragments directory; [] if it is absent."""
    if not os.path.isdir(directory):
        return []
    return sorted(n for n in os.listdir(directory) if not n.startswith("."))


def load_fragments(directory):
    frags = []
    for name in fragment_names(directory):
        path = os.path.join(directory, name)
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        try:
            frag = cr.parse_fragment(name, lines)
        except cr.FragmentError as e:
            raise Refused("malformed fragment %s:%d: %s" % (path, e.line, e.reason))
        if frag["pr"] is None:
            raise Refused("fragment %s has pr: TBD; set the PR number first" % path)
        frags.append(dict(frag, path=path))
    return frags


def add_fragments(body, frags, nl):
    """Insert one entry per fragment into the [Unreleased] body lines."""
    rank = {h: i for i, h in enumerate(HEADINGS)}
    for name in HEADINGS:
        group = sorted((f for f in frags if f["type"] == name.lower()), key=lambda f: -f["pr"])
        if not group:
            continue
        entries = []
        for f in group:
            tail = " (issue #%d, PR #%d, %s) Box skill copy: %s." % (
                f["issue"], f["pr"], f["date"], f["box-skill"].rstrip("."))
            text = ["- " + f["body"][0]] + ["  " + l for l in f["body"][1:]]
            text[-1] += tail
            entries += [l + nl for l in text]
        at = next((i for i, l in enumerate(body) if l.rstrip() == "### " + name), None)
        if at is not None:  # under the existing heading, after its blank line
            at += 1
            if at < len(body) and not body[at].strip():
                at += 1
            if at == len(body) or not body[at].startswith("- "):
                entries.append(nl)
            body[at:at] = entries
            continue
        at = next((i for i, l in enumerate(body) if l.startswith("### ")
                   and rank.get(l[4:].strip(), len(HEADINGS)) > rank[name]), len(body))
        if at == len(body) and (not body or body[-1].strip()):
            body.append(nl)
            at += 1
        body[at:at] = ["### " + name + nl, nl] + entries + [nl]
    return body


def cut(text, version, day, frags=()):
    if not SEMVER.match(version):
        raise Refused("not a SemVer version (MAJOR.MINOR.PATCH): %r" % version)
    lines = text.splitlines(keepends=True)
    heads = [i for i, l in enumerate(lines) if l.startswith("## ")]
    start = next((i for i in heads if lines[i].rstrip() == UNRELEASED), None)
    if start is None:
        raise Refused("no %s section" % UNRELEASED)
    existing = [m.group(1) for l in lines for m in [VERSION_HEADING.match(l)]
                if m and m.group(1) != "Unreleased"]
    if version in existing:
        raise Refused("version %s already exists" % version)
    known = [v for v in existing if SEMVER.match(v)]
    if known:
        latest = max(known, key=precedence)
        if precedence(version) <= precedence(latest):
            raise Refused("version %s is not greater than %s" % (version, latest))
    end = next((i for i in heads if i > start), len(lines))
    body = lines[start + 1:end]
    if not frags and not any(l.strip() and not l.startswith("### ") for l in body):
        raise Refused("%s has no entries and there are no fragments" % UNRELEASED)
    nl = "\r\n" if lines[start].endswith("\r\n") else "\n"
    body = add_fragments(body, frags, nl)
    new = [lines[start], nl, "## [%s] - %s%s" % (version, day, nl)] + body
    return "".join(lines[:start] + new + lines[end:])


def parse_date(text):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD: %r" % text)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--file", default="CHANGELOG.md")
    ap.add_argument("--fragments", help="fragments directory (default: changes/unreleased next to --file)")
    ap.add_argument("--date", type=parse_date,
                    default=datetime.now(timezone.utc).date().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    fragments = args.fragments or os.path.join(os.path.dirname(args.file), cr.FRAGMENT_DIR)
    try:
        with open(args.file, encoding="utf-8", newline="") as f:
            text = f.read()
        frags = load_fragments(fragments)
        result = cut(text, args.version, args.date, frags)
    except (OSError, Refused) as e:
        print("changelog-cut: refused: %s" % e, file=sys.stderr)
        return 1
    if args.dry_run:
        sys.stdout.write(result)
        return 0
    with open(args.file, "w", encoding="utf-8", newline="") as f:
        f.write(result)
    for f in frags:
        os.remove(f["path"])
    print("changelog-cut: %s cut as [%s] - %s (%d fragment%s assembled and deleted)"
          % (args.file, args.version, args.date, len(frags), "" if len(frags) == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
