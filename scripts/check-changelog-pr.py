#!/usr/bin/env python3
"""Require a new CHANGELOG fragment when a PR changes non-exempt content.

Exempt paths are listed only in EXEMPT_PATHS below: cut output, unreleased
fragments and verification artifacts. Empty diffs (including CI-only train
PRs whose changes are already in their base) are exempt too. A train with
content changes follows the same fragment rule as any other PR.
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
import subprocess
import sys

EXEMPT_PATHS = ("CHANGELOG.md", "changes/unreleased/*", "evidence/**")


def changed_paths(root, base, head, added_only=False):
    command = ["git", "-C", root, "diff", "--no-renames", "--name-only", "-z"]
    if added_only:
        command.append("--diff-filter=A")
    command.extend([base + "..." + head, "--"])
    result = subprocess.run(command, capture_output=True, check=True)
    return [p for p in result.stdout.decode("utf-8", "replace").split("\0") if p]


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
        if all(any(fnmatch.fnmatchcase(p, pattern) for pattern in EXEMPT_PATHS) for p in paths):
            print("check-changelog-pr: OK (exempt-only or empty diff)")
            return 0
        added = changed_paths(args.root, args.base, args.head, added_only=True)
    except (OSError, subprocess.CalledProcessError) as error:
        print("check-changelog-pr: FAILED (cannot read PR diff: %s)" % error, file=sys.stderr)
        return 1
    if any(PurePosixPath(p).parent == PurePosixPath("changes/unreleased")
           and p.endswith(".md") for p in added):
        print("check-changelog-pr: OK (new fragment added)")
        return 0
    print("check-changelog-pr: FAILED (add changes/unreleased/<issue>-<slug>.md; "
          "see CONTRIBUTING.md#changelog)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
