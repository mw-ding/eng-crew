"""`crew route` consumes mechanical wakes without a coordinator model turn. The watcher calls it before waking
window 0. New heads start review; approved merge-ups stay queued for synthesizer dispatch; passed reviews start validation. Terminal
reviewers/synthesizers are killed and dequeued; merged PRs are closed out. Progress lines are ignored. Judgement records remain in the queue,
including red CI, changes, stale heads, holds, failed commands, dialogs, blocked runs and owner asks.
Routing is serialized; interrupted batches survive in wake/queue.jsonl.route-* and are retried. Reviewer spawns
are deduplicated by PR/head/pass/round against live and queued runs, section files and posted pass markers.
Synthesizers remain alive while land requests lack completion or other inbox messages lack acknowledgment;
the inbox check and reap share the queue lock with send's inbox append.

Usage: crew route --project FILE [--org-profile FILE] [--timeout SECS]
"""
import argparse
import fcntl
import glob
import json
import os
import re
import subprocess
from urllib.parse import quote
from crew_shared import commands, heartbeat, profile, queue_lock, require_ownership, runs, synthesizer_work, open_trains


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
    if rc:
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


def approved_merge_up(pr, repo, default_branch):
    # Use live verdict history: poll may already have stored the new head as its baseline.
    for m in reversed(markers("\n".join(r["body"] for r in pr["reviews"]))):
        if m.get("role") == "reviewer-validator" and m.get("pass") == "verdict":
            return commands()["poll"].merge_up(pr, {"head": m.get("sha")}, repo, default_branch)
    return None


def review(args, state, pr, head, pass_, round_):
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
    text = "\n".join(r["body"] for r in pr["reviews"])
    posted = markers(text)
    pending = open_rereview(pr, head)
    if pending:
        for i in range(len(posted) - 1, -1, -1):
            m = posted[i]
            if m.get("sha") == head and m.get("pass") == "steer" and m.get("cmd") == "rereview":
                posted = posted[i + 1:]
                break
    section = os.path.join(state, "verdicts", "pr%d-%s-r%d-%s.md" % (pr["number"], head[:7], round_, pass_))
    if os.path.exists(section) and not pending:
        with open(section) as f:
            posted += markers(f.read())
    if any(m.get("role") == "reviewer-validator" and m.get("pr") == str(pr["number"]) and
           m.get("sha") == head and
           m.get("round") == str(round_) and m.get("pass") in (pass_, "verdict") for m in posted):
        return
    if getattr(args, "reviewer_lead", False):
        if not commands()["reviewer-pool"].capacity(args):
            raise RuntimeError("crew: reviewer admission deferred")
    invoke(args, "spawn", role="reviewer", issue=None, pr=pr["number"], pass_=pass_, round=round_,
           tier="default", head=head)
    if steer and getattr(args, "reviewer_lead", False):
        for name, rec in runs(state):
            if rec["role"] == "reviewer" and rec.get("head") == head and rec["pass"] == pass_ and \
                    rec["args"].get("pr") == pr["number"] and rec["args"].get("round") == round_:
                rec["rereview_id"] = steer
                commands()["lead"].save_record(os.path.join(state, "runs", name + ".json"), rec)


def reap(args, name, state=None):
    _, _, pool_state = profile(args)
    role = dict(runs(pool_state))[name]["role"]
    retained = {}
    if state:
        rec = dict(runs(state))[name]
        own = rec.get("verdict")
        for path in [own, own.replace("validate.md", "review.md") if own else None]:
            if path and os.path.exists(path):
                with open(path) as f:
                    retained[path] = f.read()
    invoke(args, "kill", window=name, discard=False, reason=None)
    for path, text in retained.items():
        with open(path, "w") as f:
            f.write(text)
    if not commands()["lead"].enabled(pool_state, role):
        invoke(args, "dequeue")


def pending_inbox(state, name, done):
    return bool(synthesizer_work(state, name, done))


def synthesizer_busy(state, name, done=""):
    return pending_inbox(state, name, done) or bool(open_trains(state)) or commands()["land-lock"].held(state)


def close_out(args, values, state, pr):
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    labels = {label["name"] for label in pr["labels"]}
    for label in ("crew:approved", "crew:hold", "crew:in-review", "crew:changes"):
        if label in labels:
            gh("pr", "edit", str(pr["number"]), "-R", repo, "--remove-label", label)
    issues = {i["number"] for i in pr["closingIssuesReferences"]}
    for n in sorted(issues):
        issue = gh("issue", "view", str(n), "-R", repo, "--json", "labels")
        if any(label["name"] == "crew:ready" for label in issue["labels"]):
            gh("issue", "edit", str(n), "-R", repo, "--remove-label", "crew:ready")
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
                    if not synthesizer_busy(state, name):
                        reap(args, name)
            else:
                reap(args, name)


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
    rec = dict(runs(state)).get(w.get("window"))
    lead = commands()["lead"]
    leader = dict(lead.records(state)).get(w.get("window"))
    if leader and w.get("reason") == "status" and line.startswith("done:"):
        return True
    if w.get("reason") == "backstop":
        _, session, _ = profile(args)
        for name, r in lead.records(state):
            messages = lead.pending(state, name)
            if messages and lead.ensure(args, r["role"].removesuffix("-lead")) == 0:
                commands()["send"].nudge(session, r["index"], "inbox: " + messages[0]["id"])
    if leader and w.get("reason") == "stale":
        return w.get("liveness") in ("dead", "missing") and lead.ensure(args, leader["role"].removesuffix("-lead")) == 0
    pool = rec.get("role") if rec else "builder" if event == "issue-assigned" else None
    if lead.enabled(state, pool) and (event == "issue-assigned" or w.get("reason") in ("stale", "dialog")):
        return lead.event(args, pool, w) == 0
    if event == "pr-closed" and lead.enabled(state, "reviewer"):
        lead.event(args, "reviewer", w)
        return False  # coordinator still owns the rest of close-out
    reviewer_event = event in ("new-head", "fix-at-head") or \
        re.fullmatch(r"done: #\d+ [0-9a-f]{40} (review|validate|recheck) (pass|changes|escalate)", line)
    if not getattr(args, "reviewer_lead", False) and lead.enabled(state, "reviewer") and reviewer_event:
        if rec and rec["role"] == "reviewer":
            w = dict(w, round=rec["args"]["round"])
        return lead.event(args, "reviewer", w) == 0
    built = re.fullmatch(r"done: #(\d+) #(\d+) ([0-9a-f]{40})", line)
    done = re.fullmatch(r"done: #(\d+) ([0-9a-f]{40}) (review|validate|recheck) (pass|changes|escalate)", line)
    terminal = line.startswith("done:") and rec and rec["role"] in ("reviewer", "synthesizer")
    if event not in ("new-head", "merge-up", "pr-merged", "fix-at-head") and not terminal and not built and not done:
        return False
    if built:
        n, head = int(built[2]), built[3]
    elif terminal or done:
        if " stale" in line or (rec and rec["role"] == "reviewer" and not done):
            return False
        if rec and rec["role"] == "synthesizer":
            with queue_lock(state):
                if not synthesizer_busy(state, w["window"], line):
                    reap(args, w["window"])
            return True
        n, head = int(done[1]), done[2]
    else:
        n, head = int(w["refs"][0].lstrip("#")), w["refs"][1]
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    fields = "number,state,headRefOid,isDraft,labels,reviews,statusCheckRollup,headRefName,baseRefName," \
             "headRepositoryOwner,headRepository,isCrossRepository,closingIssuesReferences"
    pr = gh("pr", "view", str(n), "-R", repo, "--json", fields)
    if event == "pr-merged":
        if pr["state"] != "MERGED":
            return False
        close_out(args, values, state, pr)
        return True
    labels = {label["name"] for label in pr["labels"]}
    if pr["state"] != "OPEN" or pr["headRefOid"] != head or pr["isDraft"] or "crew:escalated" in labels or \
            (values["runtime.options.hold_label_blocks"] and "crew:hold" in labels):
        return False
    if event == "merge-up" and open_rereview(pr, head) and lead.enabled(state, "reviewer") and not getattr(args, "reviewer_lead", False):
        return lead.event(args, "reviewer", w) == 0
    if built and lead.enabled(state, "reviewer") and not getattr(args, "reviewer_lead", False):
        return lead.event(args, "reviewer", w) == 0
    if built:
        snapshot = commands()["poll"].pr_snapshot(pr)
        pending = open_rereview(pr, head)
        if not pending and approved_merge_up(pr, repo, values["repo.default_branch"]):
            return True
        if pending or snapshot["verdict"] is None or snapshot["fixed"]:
            review(args, state, pr, head, "review", snapshot["round"])
        return True
    if done and done[4] == "changes":
        if rec:
            reap(args, w["window"], state)
        return False  # findings stay queued, with their section files retained for the builder
    round_ = rec["args"]["round"] if rec else w.get("round", commands()["poll"].pr_snapshot(pr)["round"])
    if terminal and done and getattr(args, "reviewer_lead", False):
        steer = rereview_id(pr, head)
        if steer and rec.get("rereview_id") != steer:
            reap(args, w["window"])
            review(args, state, pr, head, "review", round_)
            return True
        reap(args, w["window"])
        terminal = False
    if done and done[3] == "recheck" and done[4] == "escalate":
        review(args, state, pr, head, "review", round_)
    elif done and done[3] == "review":
        commands()["poll"].observe_ci(pr, repo)
        if commands()["poll"].pr_snapshot(pr)["ci"] == "failed":
            return False
        review(args, state, pr, head, "validate", round_)
    elif event in ("new-head", "merge-up", "fix-at-head"):
        if event == "merge-up" and not open_rereview(pr, head):
            return False
        review(args, state, pr, head, "review", w["round"])
    if terminal:
        reap(args, w["window"])
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
        with queue_lock(state):
            return int(os.path.exists(queue) and os.path.getsize(queue) > 0)


def register(sub):
    p = sub.add_parser("route")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--timeout", type=float, default=15, help="spawn timeout in seconds")


def run(args):
    pending = route_queue(args)
    print("crew: route: %s" % ("judgement records remain" if pending else "mechanical wakes consumed"))
    return 0
