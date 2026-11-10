"""Long-lived pool leads, durable reference handoffs and token-free supervision.
Solo-labelled items skip builder build/fix/CI/merge-up handoffs. The synthesizer lead (window 1, #1569) is the
long-lived lander itself: its durable inbox is the land queue, and route hands it approval, self-gate, green-CI and
approved merge-up events.

Usage: mdstack lead ensure|suites|handoff|report ROLE [KIND REF...] --project FILE
"""
import argparse
import json
import hashlib
import os
import shlex
import time
from crew_shared import (
    commands, coordinator_window, ENGINE_CMD, harness, identity, LAUNCH, probe, proc, profile, queue_lock, remember_pr,
    require_ownership, runs, show_icon, stop_pane, tmux, wait_harness, window_env)


POOLS = {"builder": 2, "reviewer": 3, "synthesizer": 1}
DEFERRALS = {"capacity", "load", "suites", "probe-unavailable"}
BLOCKS = {"spawn-failure", "missing-dependency", "owner-decision", "lead-fault"}


def solo(values, issue=None, pr=None):
    """Read the lane label live, including a PR's linked issues; read failures stop dispatch."""
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    read = commands()["route"].gh
    if pr:
        change = read("pr", "view", str(pr), "-R", repo, "--json", "labels,closingIssuesReferences")
        if any(label["name"] == "crew:solo" for label in change["labels"]):
            return True
        issues = {item["number"] for item in change["closingIssuesReferences"]}
    else:
        issues = set()
    if issue:
        issues.add(issue)
    return any(any(label["name"] == "crew:solo" for label in
                   read("issue", "view", str(n), "-R", repo, "--json", "labels")["labels"])
               for n in sorted(issues))


def record_path(state, role):
    return os.path.join(state, "leads", role + ".json")


def save_record(path, rec):
    with open(path + ".tmp", "w") as out:
        json.dump(rec, out)
    os.replace(path + ".tmp", path)


def records(state):
    for role in POOLS:
        path = record_path(state, role)
        if os.path.exists(path):
            with open(path) as f:
                rec = json.load(f)
            yield rec["name"], rec


def enabled(state, role):
    return role in POOLS and os.path.exists(os.path.join(state, "render", "runtime", role + "-lead.md"))


def recovery(liveness, restarts):
    return "none" if liveness == "alive" else "restart" if liveness in ("dead", "missing") and not restarts else "blocked"


def ensure(args, role):
    values, session, state = profile(args)
    if not require_ownership(values) or not enabled(state, role):
        return 1
    path = record_path(state, role)
    with queue_lock(state):
        rec = dict(records(state)).get(values["identities.%s.name" % role].lower() + "-lead")
        windows = dict((n, i) for i, n in tmux.list_windows(session))
        name = values["identities.%s.name" % role].lower() + "-lead"
        index = POOLS[role]
        if rec:
            action = recovery(probe(session, name, rec, windows), rec.get("restarts", 0))
            if action == "none":
                return 0
            if action == "blocked":
                print("crew: blocked lead %s; coordinator must arrange owner-directed repair" % name)
                return 1
        elif name in windows:
            print("crew: blocked lead %s; window has no recorded identity" % name)
            return 1
        if index in windows.values() and windows.get(name) != index:
            print("crew: lead window %d occupied" % index)
            return 1
        if name in windows:
            if stop_pane(session, windows[name]):
                return 1
            tmux.kill_window(session, windows[name])
        engine, model, effort = commands()["spawn"].pick_engine(values, "default")
        cwd = os.path.dirname(os.path.abspath(args.project))
        brief = os.path.join(state, "leads", role + ".brief.md")
        os.makedirs(os.path.dirname(brief), exist_ok=True)
        os.makedirs(os.path.join(state, "status"), exist_ok=True)  # a fresh lead appends its first ack here (#1176)
        with open(os.path.join(state, "render", "runtime", role + "-lead.md")) as f, open(brief, "w") as out:
            out.write(f.read())
        env = window_env(values, state, role, name, brief, args.project)
        env.update(CREW_ROLE=role + "-lead", CREW_POOL=role)
        argv = harness(engine, model, effort, cwd, state, values["runtime.options.permission_mode"], values)
        new = dict(name=name, index=index, role=role + "-lead", harness=ENGINE_CMD[engine],
                   restarts=1 if rec else 0, start=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        save_record(path, new)
        try:
            tmux.new_window(session, index, name, cwd, env, LAUNCH % (shlex.join(argv), "Read your brief at $CREW_BRIEF and follow it."))
            show_icon(values, session, index, role)
            wait_harness(session, index, name, new["harness"], getattr(args, "timeout", 15))
        except RuntimeError:
            tmux.kill_window(session, index)
            raise
        new.update(identity(session, index))
        save_record(path, new)
    print("crew: started lead %s; worker pool and inbox preserved" % name)
    return 0


def handoff(args, role, kind, refs):
    if role == "builder" and kind in ("build", "fix", "ci-red", "merge-up"):
        values, _, _ = profile(args)
        n = int(refs[0].lstrip("#"))
        if solo(values, **{"issue" if kind == "build" else "pr": n}):
            print("crew: solo item; skip builder handoff; post findings/CI on the PR for the owner's session")
            return 0
    if ensure(args, role):
        return 1
    values, session, state = profile(args)
    name = values["identities.%s.name" % role].lower() + "-lead"
    prior = next((m for m in pending(state, name) if m["kind"] == kind and m["refs"] == refs), None)
    if prior:  # a done (completed or withdrawn) message is never reused: a re-send starts a new handoff
        if commands()["send"].wait_ack(state, name, prior["id"], 0) == 0:
            return 0
        if commands()["send"].nudge(session, POOLS[role], "inbox: " + prior["id"]):
            return 4
        return commands()["send"].wait_ack(state, name, prior["id"], args.wait_ack) \
            if getattr(args, "wait_ack", None) is not None else 0
    if not require_ownership(values):
        return 1
    return commands()["send"].run(argparse.Namespace(project=args.project, org_profile=args.org_profile,
                                window=name, kind=kind, refs=refs, wait_ack=getattr(args, "wait_ack", None)))


def pending(state, name):
    inbox = os.path.join(state, "inbox", name + ".jsonl")
    status = os.path.join(state, "status", name + ".status")
    if not os.path.exists(inbox):
        return []
    done = set()
    if os.path.exists(status):
        with open(status) as f:
            done = {line.split()[1] for line in f if line.startswith("done: ")}
    with open(inbox) as f:
        return [m for m in map(json.loads, f) if m["id"] not in done]


def retry_pending(args, name=None):
    _, session, state = profile(args)
    for worker, rec in records(state):
        if name is not None and worker != name:
            continue
        messages = pending(state, worker)
        if messages:
            if ensure(args, rec["role"].removesuffix("-lead")):
                raise RuntimeError("crew: cannot retry lead " + worker)
            if commands()["send"].nudge(session, rec["index"], "inbox: " + messages[0]["id"]):
                raise RuntimeError("crew: cannot nudge lead " + worker)


def event(args, role, wake):
    _, _, state = profile(args)
    key = hashlib.sha256(json.dumps(wake, sort_keys=True).encode()).hexdigest()[:20]
    path = os.path.join(state, "leads", role + "-events", key + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(wake, f)
    return handoff(args, role, "work", [path])


def report(args):
    if args.role != "builder" or len(args.refs) < 2 or args.refs[0] not in DEFERRALS | BLOCKS:
        print("crew: report builder requires a deferral/block reason and refs")
        return 2
    values, _, state = profile(args)
    if not require_ownership(values, "write"):
        return 1
    reason, refs = args.refs[0], args.refs[1:]
    deferred = reason in DEFERRALS
    key = hashlib.sha256(json.dumps([reason, refs, args.detail]).encode()).hexdigest()[:20]
    path = os.path.join(state, "leads", "builder-admission.md" if deferred else "builder-blocks/" + key + ".md")
    coordinator = coordinator_window(values)
    sent_refs = refs + [path]
    inbox = os.path.join(state, "inbox", coordinator + ".jsonl")
    if not deferred and os.path.exists(inbox):
        with open(inbox) as f:
            if any(m["kind"] == "blocked" and m["refs"] == sent_refs for m in map(json.loads, f)):
                print("crew: identical block already reported: %s %s" % (reason, " ".join(refs)))
                return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as out:
        out.write("# Builder %s\n\nReason: %s\nRefs: %s\n%s\n" % (
            "admission deferred" if deferred else "blocked", reason, " ".join(refs), args.detail))
    name = values["identities.builder.name"].lower() + "-lead"
    os.makedirs(os.path.join(state, "status"), exist_ok=True)
    with open(os.path.join(state, "status", name + ".status"), "a") as out:
        out.write("%s: %s %s %s\n" % ("deferred" if deferred else "blocked", " ".join(refs), reason, path))
    if deferred:
        print("crew: admission deferred locally: %s %s" % (reason, " ".join(refs)))
        return 0
    return commands()["send"].run(argparse.Namespace(project=args.project, org_profile=args.org_profile,
                                window=coordinator, kind="blocked", refs=sent_refs, wait_ack=None))


def suites(values, state, closed=None):
    """Live tool sessions of runs whose item is open; runs with a live session on a closed item go to `closed`."""
    count = 0
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    for name, rec in runs(state):
        if not rec.get("pane_pid") or not proc.live_child(rec["pane_pid"], rec["harness"]):
            continue
        last = os.path.join(state, "status", name + ".status")
        if os.path.exists(last):
            with open(last) as f:
                for line in f.read().splitlines():
                    remember_pr(rec, line)
        item = rec.get("pr") or rec.get("args", {}).get("pr")
        kind = "pr" if item else "issue"
        item = item or rec.get("args", {}).get("issue")
        if item and commands()["route"].gh(kind, "view", str(item), "-R", repo, "--json", "state")["state"] != "OPEN":
            if closed is not None:
                closed.append(dict(window=name, pid=rec["pane_pid"]))
            continue
        count += 1
    return count


def register(sub):
    p = sub.add_parser("lead")
    p.add_argument("action", choices=["ensure", "handoff", "suites", "report"])
    p.add_argument("role", choices=sorted(POOLS))
    p.add_argument("refs", nargs="*")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--wait-ack", type=float)
    p.add_argument("--detail", default="", help="report: observed admission inputs or actionable block details")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    if args.action == "report":
        return report(args)
    if args.action == "ensure":
        return ensure(args, args.role)
    if args.action == "handoff":
        if not args.refs:
            return 2
        return handoff(args, args.role, args.refs[0], args.refs[1:])
    values, _, state = profile(args)
    print(suites(values, state))
    return 0
