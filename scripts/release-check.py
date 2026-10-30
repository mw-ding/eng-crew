#!/usr/bin/env python3
"""Check that a CHANGELOG is cut for a release and print its notes.

Usage: release-check.py <version> [--file CHANGELOG.md] [--notes OUT] [--tags TAG ...]

Passes (exit 0) only when `## [Unreleased]` has no entries, the next version
section is `## [<version>]`, the tag `v<version>` is not in --tags and the
version is greater than every SemVer tag there. Writes that section's body
(the release notes) to --notes, or stdout. Any failure: exit 1, no notes.
Used by `.github/workflows/release.yml`. Standard library only.
"""
import argparse
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location(
    "changelog_cut", os.path.join(os.path.dirname(os.path.abspath(__file__)), "changelog-cut.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


class Failed(Exception):
    pass


def check(text, version, tags):
    if not cc.SEMVER.match(version):
        raise Failed("not a SemVer version (MAJOR.MINOR.PATCH): %r" % version)
    lines = text.splitlines()
    heads = [i for i, l in enumerate(lines) if cc.VERSION_HEADING.match(l)]
    if len(heads) < 2 or lines[heads[0]].rstrip() != cc.UNRELEASED:
        raise Failed("expected %s followed by a version section" % cc.UNRELEASED)
    if any(l.strip() and not l.startswith("### ") for l in lines[heads[0] + 1:heads[1]]):
        raise Failed("%s still has entries; land the cut PR first" % cc.UNRELEASED)
    top = cc.VERSION_HEADING.match(lines[heads[1]]).group(1)
    if top != version:
        raise Failed("top version section is [%s], not [%s]" % (top, version))
    if "v" + version in tags:
        raise Failed("tag v%s already exists" % version)
    known = [t[1:] for t in tags if t.startswith("v") and cc.SEMVER.match(t[1:])]
    if known:
        latest = max(known, key=cc.precedence)
        if cc.precedence(version) <= cc.precedence(latest):
            raise Failed("version %s is not greater than tag v%s" % (version, latest))
    end = next((i for i, l in enumerate(lines) if i > heads[1] and l.startswith("## ")), len(lines))
    return "\n".join(lines[heads[1] + 1:end]).strip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check a release cut; print its notes.")
    ap.add_argument("version")
    ap.add_argument("--file", default="CHANGELOG.md")
    ap.add_argument("--notes")
    ap.add_argument("--tags", nargs="*", default=[])
    args = ap.parse_args(argv)
    try:
        with open(args.file, encoding="utf-8") as f:
            notes = check(f.read(), args.version, args.tags)
    except (OSError, Failed) as e:
        print("release-check: failed: %s" % e, file=sys.stderr)
        return 1
    if args.notes:
        with open(args.notes, "w", encoding="utf-8") as f:
            f.write(notes)
    else:
        sys.stdout.write(notes)
    print("release-check: %s ok for v%s" % (args.file, args.version), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
