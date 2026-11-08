#!/usr/bin/env python3
"""Require a new CHANGELOG fragment when a PR changes non-exempt content.

Exempt paths are listed only in EXEMPT_PATHS below: cut output, unreleased
fragments, verification artifacts and core memory (`memory/`). Empty diffs (including CI-only train
PRs whose changes are already in their base) are exempt too. A train with
content changes follows the same fragment rule as any other PR.
One case needs no fragment: a release cut (CHANGELOG.md changed, fragments
deleted, a new top version section) whose other changes are all in
RELEASE_PATHS. Its fix entry goes directly into the new section, so that
section must gain an entry naming an issue beyond one per deleted fragment.
With --pr N (CI passes the PR number), every fragment the PR adds or changes
must say `pr: N`; `pr: TBD` or another number fails and names the fragment.
A merge-train PR (head ref `crew/train-*`) carries its members' fragments, so
it is refused only for `pr: TBD`.
Push events pass without inspecting a diff. Fragment format is checked
separately by check-repo.py.

Usage: check-changelog-pr.py --base REF [--head REF] [--root DIR] [--event pull_request|push]
                             [--pr N] [--head-ref BRANCH]
PRs compare the merge base of REF and head to head, ignoring base-only changes.
Exit 1 for a missing fragment, a wrong fragment PR number or an unreadable
diff, otherwise 0.
"""
import argparse
import fnmatch
import os
from pathlib import PurePosixPath
import re
import subprocess
import sys

EXEMPT_PATHS = ("CHANGELOG.md", "changes/unreleased/*", "evidence/**", "memory/**")
RELEASE_PATHS = (".github/workflows/release.yml", ".github/workflows/ci.yml",
                 "scripts/release-*.py", "scripts/changelog-cut.py")
ISSUE_REF = re.compile(r"\bissue #\d+")
PR_FIELD = re.compile(r"^pr:[ \t]*(\S*)[ \t]*$", re.M)
TRAIN_REF = "crew/train-*"


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


def fragment_pr_errors(root, base, head, pr, train):
    """One message per fragment the PR adds or changes whose `pr:` is TBD or,
    outside a train, not the PR's own number."""
    errors = []
    for path in changed_paths(root, base, head, diff_filter="AM"):
        if not is_fragment(path):
            continue
        text = git(root, "show", head + ":" + path).decode("utf-8", "replace")
        front = text.split("\n---", 1)[0] if text.startswith("---") else ""
        m = PR_FIELD.search(front)
        value = m.group(1) if m else ""
        if value == "TBD" or not (train or value == str(pr)):
            errors.append("%s has pr: %s, want pr: %s" % (path, value or "(missing)", pr))
    return errors


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
    ap.add_argument("--pr", type=int, help="the PR's number; its fragments must name it")
    ap.add_argument("--head-ref", default=os.environ.get("GITHUB_HEAD_REF", ""),
                    help="PR head branch; crew/train-* skips the number match (default: $GITHUB_HEAD_REF)")
    args = ap.parse_args(argv)
    if args.event == "push":
        print("check-changelog-pr: OK (push event; no PR fragment required)")
        return 0
    if not args.base:
        ap.error("--base is required for pull_request")
    try:
        paths = changed_paths(args.root, args.base, args.head)
        if args.pr:
            errors = fragment_pr_errors(args.root, args.base, args.head, args.pr,
                                        fnmatch.fnmatchcase(args.head_ref, TRAIN_REF))
            if errors:
                for error in errors:
                    print("check-changelog-pr: FAILED (%s; fill in the PR number before review, "
                          "see CONTRIBUTING.md#changelog)" % error, file=sys.stderr)
                return 1
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
