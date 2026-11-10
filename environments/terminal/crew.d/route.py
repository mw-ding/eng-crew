"""`mdstack route` consumes mechanical wakes without a coordinator model turn. The watcher calls it before waking
window 0. Worker completion retries admission in all pending pools. New heads and escalated rechecks start review;
approved merge-ups stay queued for synthesizer dispatch. A change that resolves express never starts a reviewer pass.
Solo build wakes are consumed; solo builder findings stay queued for coordinator pickup.
Passed reviews start validation, including after zero-step CI startup failures (ci-infra goes to the coordinator). Terminal
reviewers/synthesizers are killed and dequeued; a finished relay = coordinator run (the researcher) is killed and its done: wakes
the coordinator, and that queued done: never kills a later run reusing the window name (#1092); a reflection run's
`done: reflection <window> <url>` puts the report URL on the relayed wake and reaps only the run for that window (#1520); merged PRs are closed out,
and a merge that an open issue's `Depends on` names stays queued so the coordinator dispatches the dependent (#814). Progress lines are ignored. Judgement records remain in the queue,
including red CI, changes, stale heads, holds, failed commands, dialogs, blocked runs and owner asks. Red CI for a
superseded head and synthesizer gate-status blocks that only wait (`wait=ci,review,validation,selfgate,train`) are consumed.
Routing is serialized; interrupted batches survive in wake/queue.jsonl.route-* and are retried. Reviewer spawns
are deduplicated by PR/head/pass/round against live and queued runs, section files and pass markers posted by this
runtime's reviewer (its login and signature; #1290); the head-verdict check that gates a reviewer spawn counts only
that reviewer's verdicts too.
Synthesizers remain alive while land requests lack completion or other inbox messages lack acknowledgment, and through
a merged PR's close-out while their own spawn PR lacks completion (its direct-land main CI check, #1339);
the inbox check and reap share the queue lock with send's inbox append.
With the synthesizer lead installed (#1569), `review-approved`, `selfgate-passed`, `ci-passed` with a passing verdict
or self-gate at head, and approved merge-ups become durable `work` events in its land queue, never coordinator
wakes; a superseded one is dropped, and an unapproved `ci-passed` is consumed unless held CI refs for that PR
(`ci/<n>-*.json`) still wait on it. Its waiting gate-status blocks are consumed like a synthesizer's; its other
`blocked:` lines (owner merge-ok, sensitive, holds, `main red`) stay queued for the coordinator.

Usage: mdstack route --project FILE [--org-profile FILE] [--timeout SECS]
"""
import argparse
import fcntl
import glob
import json
import os
import re
import subprocess
from urllib.parse import quote
from crew_shared import commands, heartbeat, profile, queue_lock, require_ownership, ROLES, runs, synthesizer_work, open_trains


# A gate-status block whose only unmet items are pending CI, an in-flight review, validation or express self-gate, or a
# running train.
WAITING = re.compile(r"blocked: #\d+ [0-9a-f]{40} gate-status \S+ wait=(?:ci|review|validation|selfgate|train)"
                     r"(?:,(?:ci|review|validation|selfgate|train))*")
# A reviewer's finished pass; a trailing note after the verdict is allowed (#1343), as on a builder's done line (#695).
# A reflection run's completion with its posted report (templates/policy/researcher/skills/protocol-reflection).
REFLECTION_DONE = re.compile(r"done: reflection (\S+) (https?://\S+)")
LAND_EVENTS = ("review-approved", "selfgate-passed", "ci-passed")
REVIEW_DONE = re.compile(r"done: #(\d+) ([0-9a-f]{40}) (review|validate|recheck) (pass|changes|escalate)(?:\s.*)?")


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("crew: gh %s: %s" % (" ".join(args[:2]), r.stderr.strip()))
    return json.loads(r.stdout) if "--json" in args else None


def invoke(args, cmd, **kw):
    values, _, _ = profile(args)
    if not require_ownership(values):
        raise RuntimeError("crew: ownership changed before " + cmd)
    rc = commands()[cmd].run(argparse.Namespace(project=args.project, org_profile=args.org_profile,
                            timeout=args.timeout, **kw))
    if rc and not (cmd == "send" and rc == 4):
        raise RuntimeError("crew: %s failed (exit %s)" % (cmd, rc))


def markers(text):
    return [dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            for line in re.findall(r"<!-- crew:v1 ([^>]*?) -->", text)]


def open_rereview(pr, head):
    pending = False
    for m in markers("\n".join(r["body"] for r in pr["reviews"])):
        if m.get("sha") == head:
            if m.get("pass") == "steer" and m.get("cmd") == "rereview":
                pending = True
            elif m.get("role") == "reviewer-validator" and m.get("pass") == "verdict":
                pending = False
    return pending


def rereview_id(pr, head):
    if open_rereview(pr, head):
        return next(m.get("cmd-id", "rereview") for m in reversed(markers("\n".join(r["body"] for r in pr["reviews"])))
                    if m.get("sha") == head and m.get("pass") == "steer" and m.get("cmd") == "rereview")
    return None


def own_reviews(values, pr):
    """Reviews this runtime's reviewer posted: its login and its signature (#1290). Another runtime's records on the
    same PR, even under a shared login, never stand in for this runtime's pass."""
    sign = re.compile(r"^— .*\b%s \(" % re.escape(values["identities.reviewer.name"]), re.M)
    return [r for r in pr["reviews"] if (r.get("author") or {}).get("login") == values["identities.reviewer.gh_user"]
            and sign.search(r["body"])]


def own_view(values, pr):
    """The PR with another runtime's reviewer-validator records dropped (#1290), so a foreign verdict never gates
    dispatch or approves a merge-up; builder and coordinator records stay."""
    own = own_reviews(values, pr)
    return dict(pr, reviews=[r for r in pr["reviews"] if any(r is o for o in own) or
                             not any(m.get("role") == "reviewer-validator" for m in markers(r["body"]))])


def merge_up_delta(pr, head):
    """A signed, head-pinned builder fix recording a resolved conflict or differing patch needs delta review."""
    for review in pr["reviews"]:
        body = review["body"]
        if not re.search(r"^\[[^]\n]+/(?:fix|ci-fix)\]", body) or "— 🛠️" not in body:
            continue
        if not any(m.get("role") == "builder" and m.get("pass") in ("fix", "ci-fix") and
                   m.get("pr") == str(pr["number"]) and m.get("sha") == head for m in markers(body)):
            continue
        if re.search(r"(?<!no )\b(?:resolved|fixed|resolving)\b[^\n]*\bconflicts?\b|(?<!no )(?<!without a )\bdiffering patch\b", body, re.I):
            return True
    return False


def approved_merge_up(pr, repo, default_branch):
    # Use live verdict history: poll may already have stored the new head as its baseline.
    for m in reversed(markers("\n".join(r["body"] for r in pr["reviews"]))):
        if m.get("role") == "reviewer-validator" and m.get("pass") == "verdict":
            return commands()["poll"].merge_up(pr, {"head": m.get("sha")}, repo, default_branch)
    return None


def scheduler(args, **kw):
    return argparse.Namespace(project=args.project, org_profile=args.org_profile, pool="reviewer", **kw)


def admit(args, ref):
    """The reviewer lead starts a pass only when `mdstack schedule decide --pool reviewer` grants its PR."""
    out = commands()["schedule"].schedule_decide(scheduler(args))
    if not any(a["ref"] == ref for a in out["admit"]):
        why = next((a["reasons"][0] for a in out["deferred"] if a["ref"] in (ref, None)), "not-granted")
        raise RuntimeError("crew: reviewer admission deferred: %s %s" % (ref, why))


def review(args, state, pr, head, pass_, round_):
    if commands()["poll"].express_lane(args, profile(args)[0], pr):  # the self-gate replaces review (express-lane.md)
        print("crew: route: #%d resolves express; the reviewer pool skips it" % pr["number"])
        return
    steer = rereview_id(pr, head)
    for name, rec in list(runs(state)):
        if rec["role"] == "reviewer" and rec.get("args", {}).get("pr") == pr["number"] and \
                rec.get("head", head if head[:7] in rec.get("claim", "") else None) != head:
            reap(args, name)
            continue
        if rec["role"] == "reviewer" and rec.get("args", {}).get("pr") == pr["number"] and \
                rec.get("head", head if head[:7] in rec.get("claim", "") else None) == head and \
                rec["pass"] == pass_ and rec.get("args", {}).get("round") == round_:
            if getattr(args, "reviewer_lead", False) and steer and rec.get("rereview_id") != steer:
                raise RuntimeError("crew: reviewer still finishing before rereview " + steer)
            return
    path = os.path.join(state, "spawn-queue.jsonl")
    if os.path.exists(path):
        with open(path) as f:
            if any(e.get("pr") == pr["number"] and e.get("head") == head and e["pass"] == pass_ and
                   e["round"] == round_ for e in (json.loads(line) for line in f if line.strip())):
                return
    own = own_reviews(profile(args)[0], pr)
    posted = [(r in own, m) for r in pr["reviews"] for m in markers(r["body"])]
    pending = open_rereview(pr, head)
    if pending:
        for i in range(len(posted) - 1, -1, -1):
            m = posted[i][1]
            if m.get("sha") == head and m.get("pass") == "steer" and m.get("cmd") == "rereview":
                posted = posted[i + 1:]
                break
    posted = [m for mine, m in posted if mine]
    section = os.path.join(state, "verdicts", "pr%d-%s-r%d-%s.md" % (pr["number"], head[:7], round_, pass_))
    if os.path.exists(section) and not pending:
        with open(section) as f:
            posted += markers(f.read())
    if any(m.get("role") == "reviewer-validator" and m.get("pr") == str(pr["number"]) and
           m.get("sha") == head and
           m.get("round") == str(round_) and m.get("pass") in (pass_, "verdict") for m in posted):
        return
    lead = getattr(args, "reviewer_lead", False)
    if lead:
        admit(args, "#%d" % pr["number"])
    try:
        invoke(args, "spawn", role="reviewer", issue=None, pr=pr["number"], pass_=pass_, round=round_,
               tier="default", head=head)
    except RuntimeError:
        if lead:
            commands()["schedule"].schedule_release(scheduler(args, refs=["#%d" % pr["number"]]))
        raise
    if steer and getattr(args, "reviewer_lead", False):
        for name, rec in runs(state):
            if rec["role"] == "reviewer" and rec.get("head") == head and rec["pass"] == pass_ and \
                    rec["args"].get("pr") == pr["number"] and rec["args"].get("round") == round_:
                rec["rereview_id"] = steer
                commands()["lead"].save_record(os.path.join(state, "runs", name + ".json"), rec)


def reap(args, name, state=None, dequeue=True):
    _, _, pool_state = profile(args)
    role = dict(runs(pool_state))[name]["role"]
    retained = {}
    if state:
        rec = dict(runs(state))[name]
        own = rec.get("verdict")
        for path in [own, own.replace("validate.md", "review.md") if own else None,
                     own.replace("validate.md", "verdict.md") if own else None]:
            if path and os.path.exists(path):
                with open(path) as f:
                    retained[path] = f.read()
    invoke(args, "kill", window=name, discard=False, reason=None)
    for path, text in retained.items():
        with open(path, "w") as f:
            f.write(text)
    if dequeue and not commands()["lead"].enabled(pool_state, role):
        invoke(args, "dequeue")


def pending_inbox(state, name, done):
    return bool(synthesizer_work(state, name, done))


def synthesizer_busy(state, name, done=""):
    return pending_inbox(state, name, done) or bool(open_trains(state)) or commands()["land-lock"].held(state)


def land_open(state, name, n):
    """The synthesizer's spawn PR #n has no `done:`/`blocked:` line yet: a direct land waits for main CI (#1339)."""
    status = os.path.join(state, "status", name + ".status")
    lines = []
    if os.path.exists(status):
        with open(status) as f:
            lines = [line.split() for line in f]
    ref = "#%d" % n
    return not any(w[:2] in (["done:", ref], ["blocked:", ref]) or w[:5] == ["blocked:", "main", "red", "after", ref]
                   for w in lines)


def close_out(args, values, state, pr):
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    labels = {label["name"] for label in pr["labels"]}
    for label in ("crew:approved", "crew:hold", "crew:in-review", "crew:changes"):
        if label in labels:
            gh("pr", "edit", str(pr["number"]), "-R", repo, "--remove-label", label)
    issues = {i["number"] for i in pr["closingIssuesReferences"]}
    for n in sorted(issues):
        issue = gh("issue", "view", str(n), "-R", repo, "--json", "labels,state,stateReason")
        if any(label["name"] == "crew:ready" for label in issue["labels"]):
            gh("issue", "edit", str(n), "-R", repo, "--remove-label", "crew:ready")
        # GitHub's auto-close can miss (train lands, #846); a reopened issue stays open on purpose (#917)
        if issue["state"] == "OPEN" and issue.get("stateReason") != "REOPENED":
            gh("issue", "close", str(n), "-R", repo, "--comment",
               "[%s/close-out] #%d merged and closes this issue, but GitHub left it open; closed by close-out." % (
                   values.get("identities.coordinator.name", "Ash"), pr["number"]))
    default = gh("repo", "view", repo, "--json", "defaultBranchRef")["defaultBranchRef"]["name"]
    branch = pr["headRefName"]
    if not pr["isCrossRepository"] and pr["headRepositoryOwner"]["login"] == values["repo.owner"] and \
            pr["headRepository"] and pr["headRepository"]["name"] == values["repo.name"] and \
            branch not in (default, pr["baseRefName"]):
        ref = "repos/%s/git/refs/heads/%s" % (repo, quote(branch, safe="/"))
        r = subprocess.run(["gh", "api", ref], capture_output=True, text=True)
        if r.returncode and "404" not in r.stderr:
            raise RuntimeError("crew: branch lookup: " + r.stderr.strip())
        if not r.returncode:
            gh("api", "-X", "DELETE", ref)
    else:
        print("crew: close-out #%d: branch retained (fork, default or base branch)" % pr["number"])
    for name, rec in list(runs(state)):
        item = rec.get("args", {})
        done = heartbeat(state, name)[0].split()
        if item.get("pr") == pr["number"] or item.get("issue") in issues or \
                (rec["role"] == "builder" and done[:1] == ["done:"] and
                 len(done) > 2 and done[2] == "#%d" % pr["number"]):
            if rec["role"] == "synthesizer":
                with queue_lock(state):
                    if not synthesizer_busy(state, name) and \
                            not (item.get("pr") == pr["number"] and land_open(state, name, pr["number"])):
                        reap(args, name, dequeue=False)
                invoke(args, "dequeue")
            else:
                reap(args, name)


def dependents(repo, pr):
    """Open issues whose `Depends on` block names the merged PR or an issue it closes (#814)."""
    refs = {pr["number"]} | {i["number"] for i in pr["closingIssuesReferences"]}
    issues = gh("issue", "list", "-R", repo, "--state", "open", "--limit", "1000", "--json", "number,body")
    return sorted(i["number"] for i in issues
                  if refs & {int(n) for block in commands()["schedule"].DEPENDS.findall(i["body"] or "")
                             for n in re.findall(r"#(\d+)", block)})


def route_record(args, values, state, w):
    line = w.get("line", "")
    if w.get("reason") == "status" and line.startswith(("ack:", "heartbeat:")):
        if line.startswith("ack:"):
            rec = dict(runs(state)).get(w.get("window"))
            if rec and rec["role"] == "synthesizer":
                with queue_lock(state):
                    synthesizer_work(state, w["window"])
        return True
    event = w.get("event")
    if event == "ci-failed" and len(w.get("refs", [])) < 2:
        return False  # a source's narrative wake has no PR/head to classify
    rec = dict(runs(state)).get(w.get("window"))
    lead = commands()["lead"]
    leader = dict(lead.records(state)).get(w.get("window"))
    if leader and w.get("reason") == "status" and line.startswith(("done:", "deferred:")):
        return True
    if (rec and rec["role"] == "synthesizer" or leader and leader["role"] == "synthesizer-lead") and \
            WAITING.fullmatch(line):
        return True  # recorded in the status file and gate-status review; CI or a pass will wake it again (#578)
    if w.get("reason") == "lead-backstop":
        lead.retry_pending(args, w["window"])
        return True
    if w.get("reason") == "idle-builder":
        if lead.enabled(state, "builder"):
            return lead.event(args, "builder", w) == 0
        invoke(args, "dequeue", idle_only=True)
        return True
    if w.get("reason") == "backstop":
        lead.retry_pending(args)
    if rec and ROLES.get(rec["role"], {}).get("relay") == "coordinator" and line.startswith(("done:", "failed:")):
        run = commands()["watch"].run_identity(rec)
        report, mode = REFLECTION_DONE.fullmatch(line), rec.get("args", {}).get("reflection")
        if report:
            w["report"] = report.group(2)  # the coordinator relays the posted report
        if w.get("run", run) == run and not (mode and report and report.group(1) != mode["window"]):
            reap(args, w["window"])  # one fresh session per request; the result is on the item (#584)
        # else a queued wake of an earlier run: a respawn under the same name stays alive (#1092)
        return False  # the coordinator relays the result
    if rec and line.startswith("done:") and not getattr(args, "reviewer_lead", False):
        lead.retry_pending(args)
    if leader and w.get("reason") == "stale":
        return w.get("liveness") in ("dead", "missing") and lead.ensure(args, leader["role"].removesuffix("-lead")) == 0
    pool = "builder" if event in ("issue-assigned", "builder-message", "builder-queued") else rec.get("role") if rec else None
    if event in ("issue-assigned", "builder-message"):
        n = int(w["refs"][0].lstrip("#"))
        if lead.solo(values, **{"issue" if event == "issue-assigned" else "pr": n}):
            if event == "issue-assigned":
                return True
            w["consumer"] = "coordinator"
            return False
    if lead.enabled(state, pool) and (event in ("issue-assigned", "builder-message", "builder-queued") or w.get("reason") in ("stale", "dialog")):
        return lead.event(args, pool, w) == 0
    if event == "pr-closed" and lead.enabled(state, "reviewer"):
        lead.event(args, "reviewer", w)
    reviewer_event = event in ("new-head", "fix-at-head") or \
        REVIEW_DONE.fullmatch(line)
    if not getattr(args, "reviewer_lead", False) and lead.enabled(state, "reviewer") and reviewer_event:
        if rec and rec["role"] == "reviewer":
            w = dict(w, round=rec["args"]["round"])
        return lead.event(args, "reviewer", w) == 0
    if event == "builder-queued":
        return True
    built = re.fullmatch(r"done: #(\d+) #(\d+) ([0-9a-f]{40})", line)
    done = REVIEW_DONE.fullmatch(line)
    if done and done[4] in ("pass", "escalate") and rec is None and not getattr(args, "reviewer_lead", False):
        return True
    terminal = line.startswith("done:") and rec and rec["role"] in ("reviewer", "synthesizer")
    landing = event in LAND_EVENTS and lead.enabled(state, "synthesizer")
    if event not in ("new-head", "merge-up", "pr-merged", "pr-closed", "builder-message", "fix-at-head", "ci-failed") and not terminal and not built and not done and not landing:
        return False
    if built:
        n, head = int(built[2]), built[3]
    elif terminal or done:
        stale = not done and " stale" in line  # a verdict's note may say "stale"
        if stale and rec and rec["role"] == "reviewer":
            pr = gh("pr", "view", str(rec["args"]["pr"]), "-R", "%s/%s" % (values["repo.owner"], values["repo.name"]),
                    "--json", "state")
            if pr["state"] != "OPEN":  # merged or closed by anyone, another runtime included: free the slot (#811)
                reap(args, w["window"], state)
                return True
        if rec and rec["role"] == "synthesizer":  # its `done: <refs> stale` closes a land request too (#1187)
            with queue_lock(state):
                if not synthesizer_busy(state, w["window"], line):
                    reap(args, w["window"], dequeue=False)
            invoke(args, "dequeue")
            return True
        if stale or (rec and rec["role"] == "reviewer" and not done):
            return False
        n, head = int(done[1]), done[2]
    else:
        n, head = int(w["refs"][0].lstrip("#")), w["refs"][1]
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    fields = "number,state,headRefOid,isDraft,labels,reviews,statusCheckRollup,headRefName,baseRefName," \
             "headRepositoryOwner,headRepository,isCrossRepository,closingIssuesReferences"
    pr = gh("pr", "view", str(n), "-R", repo, "--json", fields)
    if event in ("pr-merged", "pr-closed"):
        if pr["state"] != ("MERGED" if event == "pr-merged" else "CLOSED"):
            return False
        if event == "pr-merged":
            close_out(args, values, state, pr)
            if values["backends.owner-channel.name"] == "slack":
                return False  # The coordinator records the away land notification after cleanup.
            if waiting := dependents(repo, pr):
                w.update(consumer="coordinator", dependents=["#%d" % n for n in waiting])
                return False  # the coordinator dispatches the unblocked dependents now, not at the backstop (#814)
        else:
            issues = {i["number"] for i in pr["closingIssuesReferences"]}
            for name, run in list(runs(state)):
                if run["role"] == "builder" and (run.get("pr") == n or run["args"].get("pr") == n or
                                                run["args"].get("issue") in issues):
                    reap(args, name)
        return True
    if (event == "ci-failed" or landing) and pr["state"] == "OPEN" and pr["headRefOid"] != head:
        return True  # superseded head: its new head gets its own CI (#578) and its own land event (#1569)
    labels = {label["name"] for label in pr["labels"]}
    if pr["state"] != "OPEN" or pr["headRefOid"] != head or pr["isDraft"] or labels & {"crew:escalated", "crew:hold"}:
        if terminal:  # a finished reviewer frees its slot, keeping its verdict files, even when its PR moved on (#719)
            reap(args, w["window"], state)
        return False
    if landing:
        snapshot = commands()["poll"].pr_snapshot(own_view(values, pr))
        if event == "ci-passed" and "pass" not in (snapshot["verdict"], snapshot["selfgate"]) and \
                not commands()["poll"].express_lane(args, values, pr):  # poll gates an express ci-passed already
            return not glob.glob(os.path.join(state, "ci", "%d-*.json" % n))  # held CI refs: the coordinator drops them
        return lead.event(args, "synthesizer", w) == 0
    delta = merge_up_delta(pr, head)
    if event == "merge-up" and (open_rereview(pr, head) or delta) and lead.enabled(state, "reviewer") and not getattr(args, "reviewer_lead", False):
        return lead.event(args, "reviewer", w) == 0
    if built and lead.enabled(state, "reviewer") and not getattr(args, "reviewer_lead", False):
        return lead.event(args, "reviewer", w) == 0
    if event == "ci-failed":
        if commands()["poll"].ci_state(pr, repo) == "infra":
            w.update(event="ci-infra", consumer="coordinator")
        return False
    if event == "builder-message":
        issue = int(w["window"].rsplit("-", 1)[1])
        if issue not in {i["number"] for i in pr["closingIssuesReferences"]}:
            return False
        if w["window"] not in dict(runs(state)):
            queued = os.path.join(state, "spawn-queue.jsonl")
            if os.path.exists(queued):
                with open(queued) as f:
                    entries = [json.loads(line) for line in f if line.strip()]
                for entry in entries:
                    if entry.get("role") == "builder" and entry.get("issue") == issue:
                        messages = entry.setdefault("messages", [])
                        if not any(m["id"] == w["id"] for m in messages):
                            messages.append(w)
                        with open(queued, "w") as f:
                            f.writelines(json.dumps(e) + "\n" for e in entries)
                        return True
            invoke(args, "spawn", role="builder", issue=issue, pr=n, pass_="fix", round=w.get("round", 1),
                   tier="default", head=head, messages=[w], wake=False)
        if w["window"] not in dict(runs(state)):
            return True  # capped spawn carries the message until dequeue
        invoke(args, "send", window=w["window"], kind=w["kind"], refs=w["refs"], wait_ack=None)
        return True
    if built:
        if rec and rec["role"] == "builder":
            rec["pr"] = n
            with open(os.path.join(state, "runs", w["window"] + ".json"), "w") as f:
                json.dump(rec, f, indent=2)
        own = own_view(values, pr)
        snapshot = commands()["poll"].pr_snapshot(own)
        pending = open_rereview(pr, head)
        if not pending and not delta and approved_merge_up(own, repo, values["repo.default_branch"]):
            return True
        if pending or delta or snapshot["verdict"] is None or snapshot["fixed"]:
            review(args, state, pr, head, "review", snapshot["round"])
        return True
    if done and done[4] == "changes":
        if rec:
            reap(args, w["window"], state)
        return False  # findings stay queued, with their section files retained for the builder
    round_ = rec["args"]["round"] if rec else w.get("round", commands()["poll"].pr_snapshot(own_view(values, pr))["round"])
    if terminal and done and getattr(args, "reviewer_lead", False):
        steer = rereview_id(pr, head)
        if steer and rec.get("rereview_id") != steer:
            reap(args, w["window"], state)
            review(args, state, pr, head, "review", round_)
            return True
        reap(args, w["window"], state)
        terminal = False
    if done and done[3] == "recheck" and done[4] == "escalate":
        review(args, state, pr, head, "review", round_)
    elif done and done[3] == "review":
        if commands()["poll"].ci_state(pr, repo) == "failed":
            return False
        review(args, state, pr, head, "validate", round_)
    elif event in ("new-head", "merge-up", "fix-at-head"):
        if event == "merge-up" and not open_rereview(pr, head) and not delta:
            return lead.enabled(state, "synthesizer") and lead.event(args, "synthesizer", w) == 0
        snapshot = commands()["poll"].pr_snapshot(own_view(values, pr))
        if event != "merge-up" and snapshot["verdict"] and not snapshot["fixed"] and not open_rereview(pr, head):
            return True  # this head already has the newest round's verdict: a replayed event opens no round (#1124)
        review(args, state, pr, head, "review", w["round"])
    if terminal:
        reap(args, w["window"], state)
    return True


def route_queue(args):
    values, _, state = profile(args)
    wake = os.path.join(state, "wake")
    os.makedirs(wake, exist_ok=True)
    with open(os.path.join(wake, "route.lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not require_ownership(values):
            return 1
        queue = os.path.join(wake, "queue.jsonl")
        with queue_lock(state):
            if os.path.exists(queue):
                os.rename(queue, queue + ".route-" + os.urandom(6).hex())
        for path in sorted(glob.glob(queue + ".route-*"), key=os.path.getmtime):
            with open(path) as f:
                records = [json.loads(line) for line in f if line.strip()]
            for w in records:
                try:
                    consumed = route_record(args, values, state, w)
                except (RuntimeError, OSError) as e:
                    consumed = False
                    w = dict(w, route_error=str(e))
                if not consumed:
                    with queue_lock(state), open(queue, "a") as f:
                        f.write(json.dumps(w) + "\n")
            os.remove(path)
        spawn_queue = os.path.join(state, "spawn-queue.jsonl")
        if os.path.exists(spawn_queue) and os.path.getsize(spawn_queue):
            invoke(args, "dequeue", role="builder")
        with queue_lock(state):
            return int(os.path.exists(queue) and os.path.getsize(queue) > 0)


def register(sub):
    p = sub.add_parser("route")
    p.add_argument("--project")
    p.add_argument("--org-profile")
    p.add_argument("--timeout", type=float, default=15, help="spawn timeout in seconds")


def run(args):
    pending = route_queue(args)
    print("crew: route: %s" % ("judgement records remain" if pending else "mechanical wakes consumed"))
    return 0
