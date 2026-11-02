"""Long-lived pool leads, durable reference handoffs and token-free supervision.

Usage: crew lead ensure|capacity|handoff ROLE [KIND REF...] --project FILE
"""
import argparse
import json
import hashlib
import os
import shlex
import time
from crew_shared import (
    BANDS, CAPS, commands, harness, identity, LAUNCH, probe, profile, queue_lock,
    require_ownership, runs, stop_pane, tmux, wait_harness, window_env)


POOLS = {"builder": 2}


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


def admission(cap, active, queued, load, cpus, suites):
    if load is None or not cpus or suites is None or suites or load >= cpus:
        return 0
    return max(0, min(queued, cap - active))


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
        with open(os.path.join(state, "render", "runtime", role + "-lead.md")) as f, open(brief, "w") as out:
            out.write(f.read())
        env = window_env(values, state, role, name, brief, args.project)
        env.update(CREW_ROLE=role + "-lead", CREW_POOL=role)
        argv = harness(engine, model, effort, cwd, state, values["runtime.options.permission_mode"])
        new = dict(name=name, index=index, role=role + "-lead", harness={"codex": "codex", "claude-code": "claude"}[engine],
                   restarts=1 if rec else 0, start=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        save_record(path, new)
        try:
            tmux.new_window(session, index, name, cwd, env, LAUNCH % (shlex.join(argv), "Read your brief at $CREW_BRIEF and follow it."))
            wait_harness(session, index, name, new["harness"], getattr(args, "timeout", 15))
        except RuntimeError:
            tmux.kill_window(session, index)
            raise
        new.update(identity(session, index))
        save_record(path, new)
    print("crew: started lead %s; worker pool and inbox preserved" % name)
    return 0


def handoff(args, role, kind, refs):
    if ensure(args, role):
        return 1
    values, session, state = profile(args)
    name = values["identities.%s.name" % role].lower() + "-lead"
    inbox = os.path.join(state, "inbox", name + ".jsonl")
    if os.path.exists(inbox):
        with open(inbox) as f:
            prior = next((m for m in map(json.loads, f) if m["kind"] == kind and m["refs"] == refs), None)
        if prior:
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


def event(args, role, wake):
    _, _, state = profile(args)
    key = hashlib.sha256(json.dumps(wake, sort_keys=True).encode()).hexdigest()[:20]
    path = os.path.join(state, "leads", role + "-events", key + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(wake, f)
    return handoff(args, role, "work", [path])


def register(sub):
    p = sub.add_parser("lead")
    p.add_argument("action", choices=["ensure", "handoff", "capacity"])
    p.add_argument("role", choices=sorted(POOLS))
    p.add_argument("refs", nargs="*")
    p.add_argument("--suites", type=int, help="observed running local suites; omit if the probe is unavailable")
    p.add_argument("--queued", type=int, default=1)
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--wait-ack", type=float)
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    if args.action == "ensure":
        return ensure(args, args.role)
    if args.action == "handoff":
        if not args.refs:
            return 2
        return handoff(args, args.role, args.refs[0], args.refs[1:])
    values, session, state = profile(args)
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    lo, hi = BANDS[args.role]
    occupied = {n for n, i in windows.items() if lo <= i <= hi} | {n for n, r in runs(state) if r["role"] == args.role}
    try:
        load = os.getloadavg()[0]
    except OSError:
        load = None
    cap = min(values[CAPS[args.role]], hi - lo + 1)
    print(json.dumps({"admit": admission(cap, len(occupied), args.queued, load, os.cpu_count(), args.suites),
                      "active": len(occupied), "cap": cap, "load": load}))
    return 0
