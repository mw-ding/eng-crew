#!/usr/bin/env python3
"""Cut the CHANGELOG `## [Unreleased]` section into a dated version section.

Usage: changelog-cut.py <version> [--file CHANGELOG.md] [--date YYYY-MM-DD] [--dry-run]

Moves every line under `## [Unreleased]` (its `###` subsections and entries,
byte for byte) under a new `## [<version>] - <date>` heading and leaves an
empty `## [Unreleased]` above it (Keep a Changelog 1.1.0). The date defaults
to today in UTC. Refuses, with exit 1 and the file untouched: an empty
Unreleased section, a version that is not SemVer, a version that already
exists, and a version not greater than the latest one. Standard library only.
"""
import argparse
import re
import sys
from datetime import date, datetime, timezone

# semver.org 2.0.0 regex: MAJOR.MINOR.PATCH[-pre-release][+build], no leading v.
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
VERSION_HEADING = re.compile(r"^## \[([^\]]+)\]")
UNRELEASED = "## [Unreleased]"


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


def cut(text, version, day):
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
    if not any(l.strip() and not l.startswith("### ") for l in body):
        raise Refused("%s has no entries" % UNRELEASED)
    nl = "\r\n" if lines[start].endswith("\r\n") else "\n"
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
    ap = argparse.ArgumentParser(description="Cut [Unreleased] into a version.")
    ap.add_argument("version")
    ap.add_argument("--file", default="CHANGELOG.md")
    ap.add_argument("--date", type=parse_date,
                    default=datetime.now(timezone.utc).date().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        with open(args.file, encoding="utf-8", newline="") as f:
            text = f.read()
        result = cut(text, args.version, args.date)
    except (OSError, Refused) as e:
        print("changelog-cut: refused: %s" % e, file=sys.stderr)
        return 1
    if args.dry_run:
        sys.stdout.write(result)
        return 0
    with open(args.file, "w", encoding="utf-8", newline="") as f:
        f.write(result)
    print("changelog-cut: %s cut as [%s] - %s" % (args.file, args.version, args.date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
