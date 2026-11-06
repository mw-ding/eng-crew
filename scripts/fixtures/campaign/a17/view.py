#!/usr/bin/env python3
"""A17/A18 forge writer: `view.py N HEAD [EDIT...]` writes $CAMPAIGN_GH_DIR/pr-view-N.json, an open crew:express PR
closing #N+10 that passes every scripted §7 gate at HEAD by the express gate: a signed builder selfgate pass
(different mode, claude-code builder, codex reviewer), owner merge-ok, green CI, inline N/A evidence, MERGEABLE on
main. It also writes issue-view-(N+10).json with the coordinator's express item record and Reason, the PR's changed
files and pr-list.json (every open view). Each EDIT changes one thing: sg=none, sg.KEY=VALUE (a selfgate field; a
new key makes it malformed), sgby=LOGIN, label=NAME, nolabel=NAME, ilabel=NAME, flavor=NAME, reason=none, override
(Owner override: line), files=PATH[<OLD],..., ci=FAILURE|PENDING|none, ok=SHA|none, engine=TEXT (commit trailer),
review=STATE|BODY (by the reviewer) and state=X."""
import glob
import json
import os
import sys

n, head, edits = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
d, slug = os.environ["CAMPAIGN_GH_DIR"], "campaign/sandbox-" + os.environ["CAMPAIGN_RUN"]
opt = dict(e.split("=", 1) if "=" in e else (e, "") for e in edits)
many = {k: [e.split("=", 1)[1] for e in edits if e.startswith(k + "=")] for k in ("label", "nolabel", "ilabel", "review")}
base = open(os.path.join(d, "base")).read().strip()
sign = "\n— 🛠️ Builder (Builder) · claude-code · opus"
sg = dict(role="builder", **{"pass": "selfgate"}, pr=n, sha=head, base=base, round="n/a", verdict="pass",
          mode="different", **{"builder-engine": "claude-code/opus", "reviewer-engine": "codex/gpt-6.1-sol"},
          reviews=1, findings=0, open=0, checks="pass")
sg.update({e[3:].split("=", 1)[0]: e.split("=", 1)[1] for e in edits if e.startswith("sg.")})
reviews = [] if opt.get("sg") == "none" else [(opt.get("sgby", "<author-login>"), "COMMENTED", "[Builder/selfgate] %s @ %s"
           "\n\n<!-- crew:v1 %s -->%s" % (sg["verdict"], head[:7], " ".join("%s=%s" % kv for kv in sg.items()), sign))]
if opt.get("ok", head) != "none":
    reviews.append(("<author-login>", "COMMENTED", "<!-- crew:v1 role=coordinator pass=steer pr=%d sha=%s cmd=merge-ok -->"
                    % (n, opt.get("ok", head))))
reviews += [("<reviewer-login>",) + tuple(r.split("|", 1)) for r in many["review"]]
labels = [x for x in ["crew:in-review", "crew:express"] + many["label"] if x not in many["nolabel"]]
ci = opt.get("ci", "SUCCESS")
view = dict(number=n, state=opt.get("state", "OPEN"), headRefOid=head, isDraft=False, title="feat: %d" % n,
            labels=[dict(name=x) for x in labels], headRefName="builder/%d-x" % n, baseRefName="main",
            reviews=[dict(author=dict(login=a), state=s, body=b, submittedAt="2026-11-06T00:00:%02dZ" % i)
                     for i, (a, s, b) in enumerate(reviews)],
            statusCheckRollup=[] if ci == "none" else [dict(__typename="CheckRun", name="ci", status="IN_PROGRESS" if (
                ci == "PENDING") else "COMPLETED", conclusion=None if ci == "PENDING" else ci)],
            headRepositoryOwner=dict(login="campaign"), headRepository=dict(name=slug.split("/")[1]),
            isCrossRepository=False, closingIssuesReferences=[dict(number=n + 10)], mergeable="MERGEABLE",
            body="## Acceptance Evidence\n\nN/A: fixture change with no behaviour\n", comments=[],
            commits=[dict(messageBody="Engine: " + opt.get("engine", "claude-code opus medium"))])
record = "[Ash/flavor] #%d: %s\n\n%s<!-- crew:v1 role=coordinator pass=flavor issue=%d flavor=%s default=standard -->" % (
    n + 10, opt.get("flavor", "express"), ("" if opt.get("reason") == "none" else "Reason: small, well-specified\n") +
    ("Owner override: \"express is fine here\"\n" if "override" in opt else ""), n + 10, opt.get("flavor", "express"))
issue = dict(number=n + 10, state="OPEN", labels=[dict(name=x) for x in many["ilabel"]],
             comments=[dict(author=dict(login="<author-login>"), body=record)])
files = [dict(zip(("filename", "previous_filename"), f.split("<"))) for f in opt.get("files", "lib/f%d.py" % n).split(",")]
os.makedirs(os.path.join(d, "api-repos", slug, "pulls", str(n)), exist_ok=True)
for path, data in (("pr-view-%d.json" % n, view), ("issue-view-%d.json" % (n + 10), issue),
                   ("api-repos/%s/pulls/%d/files?per_page=100.json" % (slug, n), files)):
    with open(os.path.join(d, path), "w") as f:
        json.dump(data, f)
views = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(d, "pr-view-*.json")))]
with open(os.path.join(d, "pr-list.json"), "w") as f:
    json.dump([v for v in views if v["state"] == "OPEN"], f)
