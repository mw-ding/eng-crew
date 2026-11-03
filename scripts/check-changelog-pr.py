#!/usr/bin/env python3
"""Require a new CHANGELOG fragment when a PR changes non-exempt content.

Exempt paths are listed only in EXEMPT_PATHS below: cut output, unreleased
fragments and verification artifacts. Empty diffs (including CI-only train
PRs whose changes are already in their base) are exempt too. A train with
content changes follows the same fragment rule as any other PR.
One case needs no fragment: a release cut (CHANGELOG.md changed, fragments
deleted, a new top version section) whose other changes are all in
RELEASE_PATHS. Its fix entry goes directly into the new section, so that
section must gain an entry naming an issue beyond one per deleted fragment.
Push events pass without inspecting a diff. Fragment format is checked
separately by check-repo.py.

Usage: check-changelog-pr.py --base REF [--head REF] [--root DIR] [--event pull_request|push]
PRs compare the merge base of REF and head to head, ignoring base-only changes.
Exit 1 for a missing fragment or an unreadable diff, otherwise 0.
"""
import argparse
import fnmatch
import os
from pathlib import PurePosixPath
import re
import subprocess
import sys

EXEMPT_PATHS = ("CHANGELOG.md", "changes/unreleased/*", "evidence/**")
RELEASE_PATHS = (".github/workflows/release.yml", ".github/workflows/ci.yml",
                 "scripts/release-*.py", "scripts/changelog-cut.py")
ISSUE_REF = re.compile(r"\bissue #\d+")


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, check=True).stdout


def changed_paths(root, base, head, diff_filter=None):
    command = ["diff", "--no-renames", "--name-only", "-z"]
    if diff_filter:
        command.append("--diff-filter=" + diff_filter)
    command.extend([base + "..." + head, "--"])
    return [p for p in git(root, *command).decode("utf-8", "replace").split("\0") if p]


def is_fragment(path):
    return PurePosixPath(path).parent == PurePosixPath("changes/unreleased") and path.endswith(".md")


def entries(lines):
    """Changelog entries: a `- ` line joined with its indented continuation lines."""
    out = []
    for line in lines:
        if line.startswith("- "):
            out.append(line.rstrip())
        elif out and line.startswith("  ") and line.strip():
            out[-1] += " " + line.strip()
    return out


def top_section(text):
    """(heading, lines) of the first `## [x]` section after [Unreleased], or (None, [])."""
    lines = text.splitlines()
    heads = [i for i, l in enumerate(lines) if l.startswith("## [") and l.rstrip() != "## [Unreleased]"]
    if not heads:
        return None, []
    end = next((i for i, l in enumerate(lines) if i > heads[0] and l.startswith("## ")), len(lines))
    return lines[heads[0]].rstrip(), lines[heads[0] + 1:end]


def cut_fix_entry(root, base, head, deleted):
    """True when the head CHANGELOG has a new top version section with more new
    issue-naming entries than the deleted fragments account for."""
    merge_base = git(root, "merge-base", base, head).decode().strip()
    before = git(root, "show", merge_base + ":CHANGELOG.md").decode("utf-8", "replace")
    after = git(root, "show", head + ":CHANGELOG.md").decode("utf-8", "replace")
    heading, section = top_section(after)
    if heading is None or heading in before.splitlines():
        return False
    old = set(entries(before.splitlines()))
    new = [e for e in entries(section) if e not in old and ISSUE_REF.search(e)]
    return len(new) > len(deleted)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", help="PR base ref or SHA (required for pull_request)")
    ap.add_argument("--head", default="HEAD", help="PR head ref or SHA (default: HEAD)")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--event", choices=("pull_request", "push"),
                    default=os.environ.get("GITHUB_EVENT_NAME", "pull_request"))
    args = ap.parse_args(argv)
    if args.event == "push":
        print("check-changelog-pr: OK (push event; no PR fragment required)")
        return 0
    if not args.base:
        ap.error("--base is required for pull_request")
    try:
        paths = changed_paths(args.root, args.base, args.head)
        if all(matches(p, EXEMPT_PATHS) for p in paths):
            print("check-changelog-pr: OK (exempt-only or empty diff)")
            return 0
        added = changed_paths(args.root, args.base, args.head, diff_filter="A")
        if any(is_fragment(p) for p in added):
            print("check-changelog-pr: OK (new fragment added)")
            return 0
        deleted = [p for p in changed_paths(args.root, args.base, args.head, diff_filter="D")
                   if is_fragment(p)]
        release_cut = ("CHANGELOG.md" in paths and bool(deleted)
                       and all(matches(p, EXEMPT_PATHS + RELEASE_PATHS) for p in paths))
        if release_cut and cut_fix_entry(args.root, args.base, args.head, deleted):
            print("check-changelog-pr: OK (release cut with a release-pipeline fix entry)")
            return 0
    except (OSError, subprocess.CalledProcessError) as error:
        print("check-changelog-pr: FAILED (cannot read PR diff: %s)" % error, file=sys.stderr)
        return 1
    if release_cut:
        print("check-changelog-pr: FAILED (release cut with release-pipeline changes: add an entry "
              "naming the issue to the new version section; see CONTRIBUTING.md#changelog)",
              file=sys.stderr)
        return 1
    print("check-changelog-pr: FAILED (add changes/unreleased/<issue>-<slug>.md; "
          "see CONTRIBUTING.md#changelog)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
