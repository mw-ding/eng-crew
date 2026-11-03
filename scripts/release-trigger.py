#!/usr/bin/env python3
"""Detect a landed release cut, wait for green CI and verify owner approval.

Usage: release-trigger.py detect [--skip-invalid] | actor | ci-gate [--wait S]
       [--interval S] | authorize

Used by release.yml. Detect reads CHANGELOG.md and local tags, writing the
version and readiness to GITHUB_OUTPUT. --skip-invalid makes a non-cut push
a green no-op with one line in GITHUB_STEP_SUMMARY. Authorize reads the PR
merged at GITHUB_SHA through gh (including paginated reviews and comments),
checks RELEASE_OWNER against both actors and the merge-ok author, then
writes linked issue numbers to GITHUB_OUTPUT. Actor fails early when the run
was not started by RELEASE_OWNER. Ci-gate waits up to --wait seconds for the
latest ci.yml push run on main at GITHUB_SHA and refuses unless it succeeded.
No tag or release is written.
Standard library only; offline fixtures run in CI.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location(
    "release_check", os.path.join(os.path.dirname(__file__), "release-check.py"))
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


def detect(text, tags):
    heads = [rc.cc.VERSION_HEADING.match(line) for line in text.splitlines()]
    heads = [h.group(1) for h in heads if h]
    if len(heads) < 2 or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", heads[1]):
        raise rc.Failed("no top X.Y.Z release section")
    version = heads[1]
    rc.check(text, version, [])
    if "v" + version in tags:
        raise rc.Failed("tag v%s already exists" % version)
    return version


def approved(pr, posts, owner):
    for post in posts:
        if post.get("user", {}).get("login") != owner:
            continue
        for marker in re.findall(r"<!-- crew:v1 ([^\n]*?) -->", post.get("body") or ""):
            fields = dict(token.split("=", 1) for token in marker.split() if "=" in token)
            if (fields.get("pass") == "steer" and fields.get("cmd") == "merge-ok"
                    and fields.get("sha") == pr["head"]["sha"]
                    and fields.get("pr") == str(pr["number"])):
                return True
    return False


def merged_pr(prs, sha, repo):
    matches = [pr for pr in prs if pr.get("merged_at") and pr.get("merge_commit_sha") == sha
               and pr["base"]["ref"] == "main" and pr["base"]["repo"]["full_name"] == repo]
    if len(matches) != 1:
        raise rc.Failed("expected one merged cut PR at the validated commit")
    return matches[0]


def ci_state(runs, sha):
    """Return "success" or "pending" for the latest ci.yml run at sha, or refuse."""
    runs = [run for run in runs if run.get("head_sha") == sha]
    if not runs:
        return "pending"
    run = max(runs, key=lambda run: run.get("created_at") or "")
    if run.get("status") != "completed":
        return "pending"
    if run.get("conclusion") != "success":
        raise rc.Failed("ci.yml run %s at %s concluded %s; re-run CI to green, then re-run this release"
                        % (run.get("id"), sha[:12], run.get("conclusion")))
    return "success"


def gh(*args):
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def check_actor():
    owner = os.environ.get("RELEASE_OWNER")
    if not owner:
        raise rc.Failed("actor check: RELEASE_OWNER is unset; set the repository variable")
    for key in ("GITHUB_ACTOR", "GITHUB_TRIGGERING_ACTOR"):
        if os.environ.get(key) != owner:
            raise rc.Failed("actor %s (%s) is not RELEASE_OWNER; dispatch release.yml as the owner "
                            "account, or have the synthesizer merge the cut PR" % (os.environ.get(key), key))


def ci_gate(wait, interval, sleep=time.sleep, clock=time.monotonic):
    repo, sha = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    deadline = clock() + wait
    while True:
        runs = gh("api", "repos/%s/actions/workflows/ci.yml/runs?head_sha=%s&event=push&branch=main&per_page=100"
                  % (repo, sha))["workflow_runs"]
        if ci_state(runs, sha) == "success":
            return
        if clock() >= deadline:
            raise rc.Failed("no green ci.yml push run at %s within %ss (missing or still pending)" % (sha[:12], wait))
        sleep(interval)


def authorize():
    check_actor()
    owner = os.environ["RELEASE_OWNER"]
    repo, sha = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"]
    prs = gh("api", "repos/%s/commits/%s/pulls" % (repo, sha), "--paginate", "--slurp")
    pr = merged_pr([pr for page in prs for pr in page], sha, repo)
    files = gh("api", "repos/%s/pulls/%s/files" % (repo, pr["number"]), "--paginate", "--slurp")
    if not any(file["filename"] == "CHANGELOG.md" for page in files for file in page):
        raise rc.Failed("merged PR is not a CHANGELOG cut")
    posts = []
    for endpoint in ("pulls/%s/reviews", "issues/%s/comments"):
        pages = gh("api", "repos/%s/%s" % (repo, endpoint % pr["number"]), "--paginate", "--slurp")
        posts.extend(post for page in pages for post in page)
    if not approved(pr, posts, owner):
        raise rc.Failed("missing owner merge-ok at cut PR head")
    view = gh("pr", "view", str(pr["number"]), "--repo", repo, "--json", "closingIssuesReferences")
    return [str(issue["number"]) for issue in view["closingIssuesReferences"]
            if issue["url"].startswith("https://github.com/%s/issues/" % repo)]


def output(key, value):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
        f.write("%s=%s\n" % (key, value))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=("detect", "actor", "ci-gate", "authorize"))
    ap.add_argument("--skip-invalid", action="store_true")
    ap.add_argument("--wait", type=int, default=2400)
    ap.add_argument("--interval", type=int, default=30)
    args = ap.parse_args(argv)
    try:
        if args.mode == "authorize":
            output("issues", " ".join(authorize()))
        elif args.mode == "actor":
            check_actor()
        elif args.mode == "ci-gate":
            ci_gate(args.wait, args.interval)
            print("release-trigger: ci.yml green at %s" % os.environ["GITHUB_SHA"])
        else:
            with open("CHANGELOG.md", encoding="utf-8") as f:
                version = detect(f.read(), subprocess.check_output(["git", "tag", "--list", "v*"], text=True).splitlines())
            output("version", version)
            output("ready", "true")
    except rc.Failed as e:
        if args.mode == "detect" and args.skip_invalid:
            output("ready", "false")
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
                f.write("Release skipped: %s.\n" % e)
            return 0
        print("release-trigger: refused: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
