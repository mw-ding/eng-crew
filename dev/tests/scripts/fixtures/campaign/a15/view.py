#!/usr/bin/env python3
"""A15/A16 PR view writer: `view.py N HEAD [EDIT...]` writes $CAMPAIGN_GH_DIR/pr-view-N.json, a PR that passes every
scripted §7 gate at HEAD (passing review, validate and verdict markers under APPROVED, owner merge-ok, green CI,
inline N/A evidence, MERGEABLE, open on main, Closes #N+10). The verdict's base is $CAMPAIGN_GH_DIR/base. Each EDIT
injects one miss: verdict=SHA, ok=SHA (none drops it), validate=fail, ci=FAILURE|PENDING|none, body=TEXT,
label=NAME, state=X, draft, base=B, mergeable=X, review=STATE|BODY and comment=BODY (appended in order)."""
import json
import os
import sys

n, head, edits = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
d = os.environ["CAMPAIGN_GH_DIR"]
opt = dict(e.split("=", 1) if "=" in e else (e, "") for e in edits if not e.startswith(("review=", "comment=", "label=")))
sha, base = opt.get("verdict", head), open(os.path.join(d, "base")).read().strip()
marker = "<!-- crew:v1 role=%s pass=%s pr=%d sha=%s %s-->"
verdict = "\n".join(marker % ("reviewer-validator", k, n, sha, "base=%s round=1 verdict=%s " % (
    base, "fail" if k == "validate" and opt.get("validate") == "fail" else "pass")) for k in ("review", "validate", "verdict"))
reviews = [("APPROVED", verdict)]
if opt.get("ok", head) != "none":
    reviews.append(("COMMENTED", marker % ("coordinator", "steer", n, opt.get("ok", head), "cmd=merge-ok ")))
reviews += [tuple(e[7:].split("|", 1)) for e in edits if e.startswith("review=")]
ci = opt.get("ci", "SUCCESS")
view = dict(number=n, state=opt.get("state", "OPEN"), headRefOid=head, isDraft="draft" in opt, title="feat: %d" % n,
            labels=[dict(name=e[6:]) for e in edits if e.startswith("label=")], headRefName="builder/%d-x" % n,
            reviews=[dict(author=dict(login="<reviewer-login>"), state=s, body=b) for s, b in reviews],
            statusCheckRollup=[] if ci == "none" else [dict(__typename="CheckRun", name="ci", status="IN_PROGRESS" if (
                ci == "PENDING") else "COMPLETED", conclusion=None if ci == "PENDING" else ci)],
            baseRefName=opt.get("base", "main"), isCrossRepository=False, closingIssuesReferences=[dict(number=n + 10)],
            body=opt.get("body", "## Acceptance Evidence\n\nN/A: fixture change with no behaviour\n"), commits=[],
            comments=[dict(author=dict(login="<author-login>"), body=e[8:]) for e in edits if e.startswith("comment=")],
            mergeable=opt.get("mergeable", "MERGEABLE"), files=[])
with open(os.path.join(d, "pr-view-%d.json" % n), "w") as f:
    json.dump(view, f)
