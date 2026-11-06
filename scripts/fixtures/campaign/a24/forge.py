#!/usr/bin/env python3
"""A24 fake forge answers for release-trigger.py authorize and ci-gate (gh api reads $CAMPAIGN_GH_DIR/api.json).

Usage: forge.py GH_DIR REPO MAIN CUT EARLY init | ci STATUS [CONCLUSION [SHA]] | files NAME | pulls none | approve
init: merged cut PR 2 at MAIN (head CUT, closes issue 7) with no ci.yml run and three merge-ok markers that must
not authorize: the owner's at the earlier head EARLY and at the merge commit MAIN, and a non-owner's at CUT.
"""
import json
import os
import sys

d, repo, main, cut, early, cmd, *rest = sys.argv[1:]
path = os.path.join(d, "api.json")


def marker(user, sha):
    body = "[owner/merge-ok]\n\n<!-- crew:v1 role=owner pass=steer cmd=merge-ok pr=2 sha=%s -->\n" % sha
    return {"user": {"login": user}, "body": body, "created_at": "2026-11-06T00:00:00Z"}


def run(status, conclusion=None, sha=main):
    return {"id": 24, "head_sha": sha, "status": status, "conclusion": conclusion,
            "created_at": "2026-11-06T00:00:00Z"}


if cmd == "init":
    os.makedirs(d, exist_ok=True)
    data = {"commits/%s/pulls" % main: [{"number": 2, "merged_at": "2026-11-06T00:00:00Z", "merge_commit_sha": main,
                                         "head": {"sha": cut}, "base": {"ref": "main", "repo": {"full_name": repo}}}],
            "pulls/2/files": [{"filename": "CHANGELOG.md"}, {"filename": "changes/unreleased/1-a24-sandbox.md"}],
            "pulls/2/reviews": [marker("sandbox-owner", early)],
            "issues/2/comments": [marker("sandbox-owner", main), marker("sandbox-builder", cut)],
            "actions/workflows/ci.yml/runs": {"workflow_runs": []}}
    with open(os.path.join(d, "pr-view-2.json"), "w") as f:
        json.dump({"closingIssuesReferences": [{"number": 7, "url": "https://github.com/%s/issues/7" % repo}]}, f)
else:
    with open(path) as f:
        data = json.load(f)
    if cmd == "ci":
        data["actions/workflows/ci.yml/runs"] = {"workflow_runs": [run(*rest)]}
    elif cmd == "files":
        data["pulls/2/files"] = [{"filename": rest[0]}]
    elif cmd == "pulls":
        data["commits/%s/pulls" % main] = []
    elif cmd == "approve":
        data["pulls/2/reviews"].append(marker("sandbox-owner", cut))
with open(path, "w") as f:
    json.dump(data, f, indent=1)
