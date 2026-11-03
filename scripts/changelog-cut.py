#!/usr/bin/env python3
"""Cut the CHANGELOG `## [Unreleased]` section into a dated version section.

Usage: changelog-cut.py <version> [--project crew.toml] [--file CHANGELOG.md] [--fragments DIR] [--date YYYY-MM-DD] [--dry-run]

Moves every line under `## [Unreleased]` (its `###` subsections and entries,
byte for byte) under a new `## [<version>] - <date>` heading and leaves an
empty `## [Unreleased]` above it (Keep a Changelog 1.1.0). Each fragment in
--fragments becomes an entry under its `### <Type>` heading, newest PR first
and ahead of the existing entries; a missing heading is added in Keep a
Changelog order. The fragments are then deleted (kept on --dry-run). Paths
come from the flags, else the profile's `[release]` table (`changelog`,
`fragments`, relative to the profile), else `CHANGELOG.md` and
`changes/unreleased/` next to it (docs/profile.md). A fragment is
`<slug>.md`: front matter with `type` and optionally `issue`, `pr`, `date`
and `box-skill`, then one paragraph of entry text; a `<n>-` name prefix must
match `issue`. The repo guard may require more fields (eng-crew:
check-repo.py). The date defaults to today in UTC. Refuses, with exit 1 and
nothing changed: no entries and no fragments, a malformed fragment or one
with `pr: TBD`, a version that is not SemVer, a version that already exists,
and a version not greater than the latest one. Standard library only. Not
run in CI.
"""
import argparse
import os
import re
import sys
import tomllib
from datetime import date, datetime, timezone

# semver.org 2.0.0 regex: MAJOR.MINOR.PATCH[-pre-release][+build], no leading v.
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")
VERSION_HEADING = re.compile(r"^## \[([^\]]+)\]")
UNRELEASED = "## [Unreleased]"
HEADINGS = ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")
FRAGMENT_DIR = "changes/unreleased"
FRAGMENT_NAME = re.compile(r"(?:([1-9]\d*)-)?[a-z0-9]+(?:-[a-z0-9]+)*\.md")
FRAGMENT_FIELDS = ("type", "issue", "pr", "date", "box-skill")


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


def field_error(key, value, prefix):
    """What a bad front matter value should be, or None if it is fine."""
    if key == "type" and value not in [h.lower() for h in HEADINGS]:
        return "one of " + ", ".join(h.lower() for h in HEADINGS)
    if key == "issue" and not re.fullmatch(r"[1-9]\d*", value):
        return "an issue number"
    if key == "issue" and prefix and value != prefix:
        return prefix + ", the issue in the file name"
    if key == "pr" and value != "TBD" and not re.fullmatch(r"[1-9]\d*", value):
        return "a PR number or TBD"
    if key == "date":
        try:
            date.fromisoformat(value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else "")
        except ValueError:
            return "a YYYY-MM-DD date"
    return None


def parse_fragment(name, lines):
    """Fields (issue and pr as int, pr "TBD" kept, absent ones None) plus `body`,
    the stripped entry lines; raises Refused with `<line>: <reason>`."""
    m = FRAGMENT_NAME.fullmatch(name)
    if not m:
        raise Refused("1: name must be <slug>.md or <issue>-<slug>.md (lowercase slug)")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
    if end is None or lines[0].rstrip() != "---":
        raise Refused("1: must start with front matter between '---' lines")
    out = {}
    for n in range(1, end):
        key, sep, value = (p.strip() for p in lines[n].partition(":"))
        if not sep or key not in FRAGMENT_FIELDS or key in out or not value:
            raise Refused("%d: expected one '<field>: <value>' line per field: %s" % (n + 1, ", ".join(FRAGMENT_FIELDS)))
        want = field_error(key, value, m.group(1))
        if want:
            raise Refused("%d: %s must be %s, got '%s'" % (n + 1, key, want, value))
        out[key] = value
    if "type" not in out:
        raise Refused("%d: front matter lacks type" % (end + 1))
    body = [l.strip() for l in lines[end + 1:]]
    filled = [i for i, l in enumerate(body) if l]
    if not filled:
        raise Refused("%d: no entry text after the front matter" % (end + 1))
    body = body[filled[0]:filled[-1] + 1]
    if "" in body:
        raise Refused("%d: entry text must be one paragraph (no blank lines)" % (end + 2 + filled[0] + body.index("")))
    pr = out.get("pr")
    return dict(out, issue=int(out["issue"]) if "issue" in out else None,
                pr=pr if pr in (None, "TBD") else int(pr), body=body)


def load_fragments(directory):
    frags = []
    for name in fragment_names(directory):
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except IsADirectoryError:
            raise Refused("malformed fragment %s:1: not a file" % path)
        try:
            frag = parse_fragment(name, lines)
        except Refused as e:
            raise Refused("malformed fragment %s:%s" % (path, e))
        if frag["pr"] == "TBD":
            raise Refused("fragment %s has pr: TBD; set the PR number first" % path)
        frags.append(dict(frag, path=path))
    return frags


def add_fragments(body, frags, nl):
    """Insert one entry per fragment into the [Unreleased] body lines."""
    rank = {h: i for i, h in enumerate(HEADINGS)}
    for name in HEADINGS:
        group = sorted((f for f in frags if f["type"] == name.lower()), key=lambda f: -(f["pr"] or 0))
        if not group:
            continue
        entries = []
        for f in group:
            refs = ", ".join(x for x in ("issue #%s" % f["issue"] if f["issue"] else "",
                                         "PR #%s" % f["pr"] if f["pr"] else "", f.get("date", "")) if x)
            tail = (" (%s)" % refs if refs else "") + (
                " Box skill copy: %s." % f["box-skill"].rstrip(".") if "box-skill" in f else "")
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
    ap.add_argument("--project", help="profile whose [release] table names the changelog and fragments paths")
    ap.add_argument("--file", help="changelog (default: [release].changelog, else CHANGELOG.md)")
    ap.add_argument("--fragments", help="fragments directory (default: [release].fragments, else changes/unreleased next to --file)")
    ap.add_argument("--date", type=parse_date,
                    default=datetime.now(timezone.utc).date().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        release, base = {}, ""
        if args.project:
            with open(args.project, "rb") as f:
                release = tomllib.load(f).get("release", {})
            base = os.path.dirname(os.path.abspath(args.project))
        args.file = args.file or os.path.join(base, release.get("changelog", "CHANGELOG.md"))
        fragments = args.fragments or (os.path.join(base, release["fragments"]) if "fragments" in release
                                       else os.path.join(os.path.dirname(args.file), FRAGMENT_DIR))
        with open(args.file, encoding="utf-8", newline="") as f:
            text = f.read()
        frags = load_fragments(fragments)
        result = cut(text, args.version, args.date, frags)
    except (OSError, tomllib.TOMLDecodeError, Refused) as e:
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
