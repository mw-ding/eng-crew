"""crew spawn ROLE --issue N | --pr N [--pass PASS] [--round K] [--tier T] --project FILE [--org-profile FILE]"""
import json
import os
import shlex
import time
from crew_shared import (
    BANDS, brief_src, ENGINE_CMD, fetch, git, harness, identity, kill_run, LAUNCH, NAMES, over_cap, PASSES, POINTER,
    profile, tmux, wait_harness, window_env)


def pick_engine(values, tier, avoid=None):
    """First interactive engine in the tier's order; a reviewer avoids every actual builder engine of the PR, and
    an unknown builder engine counts as non-Claude (roles.md Reviewer engine selection)."""
    order = [e.split("/", 1) for e in values["engines.%s.order" % tier]]
    order = [e for e in order if e[0] in ENGINE_CMD and e[0] not in (avoid or ())]
    if avoid == set():
        order.sort(key=lambda e: e[0] != "claude-code")
    if not order:
        raise RuntimeError("crew: no %s engine in engines.%s.order differs from the builder's %s" %
                           ("/".join(ENGINE_CMD), tier, sorted(avoid or ())))
    return order[0][0], order[0][1], values["engines.%s.effort" % tier]


def enqueue(state, args, pass_):
    """Append a capped spawn request to spawn-queue.jsonl for the coordinator; no window is created."""
    entry = {"role": args.role, "issue": args.issue, "pr": args.pr, "pass": pass_, "round": args.round,
             "tier": args.tier, "queued": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "spawn-queue.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    print("queued: %s %s %s (%s cap reached; run crew dequeue when a window closes)" % (
        args.role, pass_, "issue #%s" % args.issue if args.issue else "PR #%s" % args.pr, args.role))
    return 0


def register(sub):
    p = sub.add_parser("spawn")
    p.add_argument("role", choices=sorted(BANDS))
    p.add_argument("--issue", type=int)
    p.add_argument("--pr", type=int)
    p.add_argument("--pass", dest="pass_", choices=sorted({p for v in PASSES.values() for p in v}))
    p.add_argument("--round", type=int, default=1, help="verdict round k, for reviewer window names")
    p.add_argument("--tier", default="default", choices=["trivial", "default", "deep"])
    p.add_argument("--timeout", type=float, default=15.0, help="seconds to see the harness in the foreground")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    values, session, state = profile(args)
    role = args.role
    pass_ = args.pass_ or PASSES[role][1 if role == "builder" and args.pr else 0]
    if pass_ not in PASSES[role] or bool(args.issue) != (role == "builder") or \
            bool(args.pr) != (role != "builder" or pass_ == "fix"):
        print("crew: %s %s takes %s" % (role, pass_, "--issue N --pr N" if pass_ == "fix" else
                                         "--issue N" if role == "builder" else "--pr N"))
        return 2
    nm = values.get("identities.%s.name" % role, NAMES[role]).lower()
    name = {"builder": "%s-%s" % (nm, args.issue), "synthesizer": nm,
            "reviewer": "%s-%s-r%d-%s" % (nm, args.pr, args.round, pass_)}[role]
    if not tmux.has_session(session):
        print("crew: session %s not reachable (tmux socket, or run crew up first)" % session)
        return 1
    tmux.pin_layout(session)
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    free = [i for i in range(BANDS[role][0], BANDS[role][1] + 1) if i not in windows.values()]
    if name not in windows and over_cap(values, role, windows):
        return enqueue(state, args, pass_)
    src = brief_src(state, role)
    problem = ("%s already running" % name if name in windows else "band %d-%d full" % BANDS[role] if not free
               else "no rendered brief %s (run crew up)" % src if not os.path.exists(src) else None)
    if problem:
        print("crew: refusing spawn: " + problem)
        return 1
    try:
        repo = git(os.path.dirname(os.path.abspath(args.project)), "rev-parse", "--show-toplevel")
        sha = fetch(repo, "pull/%d/head" % args.pr if args.pr else values["repo.default_branch"])
        engine, model, effort = pick_engine(values, args.tier) if role != "reviewer" else pick_engine(
            values, args.tier, {line.split()[0] for line in git(
                repo, "log", "--format=%(trailers:key=Engine,valueonly)",
                "%s..%s" % (fetch(repo, values["repo.default_branch"]), sha)).splitlines()
                if line.strip() and not line.startswith("none")})
    except RuntimeError as e:
        print(e)
        return 1
    run = "%s-pr%d-%s" % (role, args.pr, sha[:7]) if args.pr else ""
    run += "-r%d-%s" % (args.round, pass_) if role == "reviewer" else ""  # review and validate coexist (#139 F3)
    claim = os.path.join(state, "claims", "builder-issue%s" % args.issue if pass_ == "build" else run)
    for d in ["claims", "runs", "inbox", "status"]:
        os.makedirs(os.path.join(state, d), exist_ok=True)
    try:
        os.close(os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY))  # atomic claim (protocol §6 step 2)
    except FileExistsError:
        print("crew: refusing spawn: claim %s exists" % claim)
        return 1
    item = "issue #%s" % args.issue if role == "builder" else "PR #%d" % args.pr
    item += ", PR #%d" % args.pr if pass_ == "fix" else ""
    wt = os.path.join(os.path.abspath(values["paths.worktree_root"]), "%d-%s-%s-%s%s" % (
        args.pr or args.issue, sha[:7], role, "r%d-" % args.round if role == "reviewer" else "", pass_))
    rec = {"index": free[0], "role": role, "item": item, "pass": pass_, "repo": repo, "worktree": None, "claim": claim,
           "engine": engine, "model": model, "effort": effort, "harness": ENGINE_CMD[engine]}
    if role == "reviewer":  # the brief's verdict file, removed by crew kill
        rec["verdict"] = os.path.join(state, "verdicts", "pr%d-%s-r%d-%s.md" % (args.pr, sha[:7], args.round, pass_))

    def save():
        with open(os.path.join(state, "runs", name + ".json"), "w") as f:
            json.dump(rec, f, indent=2)

    save()
    try:
        real, top = os.path.realpath(wt), os.path.realpath(repo)
        if real == top or real.startswith(top + os.sep):
            raise RuntimeError("crew: refusing spawn: %s is inside the primary checkout %s" % (wt, repo))
        if os.path.lexists(wt):
            raise RuntimeError("crew: refusing spawn: %s exists" % wt)
        os.makedirs(os.path.dirname(wt), exist_ok=True)
        git(repo, "worktree", "add", "-q", "--detach", wt, sha)
        rec["worktree"] = wt
        save()
        brief = os.path.join(state, "runs", name + ".brief.md")
        with open(src, encoding="utf-8") as f, open(brief, "w", encoding="utf-8") as out:
            out.write(f.read() + "\n## This run\n\n" + "".join("- %s: %s\n" % kv for kv in [
                ("Window", name), ("Item", item), ("Pass", pass_), ("Worktree", wt), ("Base", sha),
                ("Engine", "%s %s %s" % (engine, model, effort)), ("Claim", claim)]))
        tmux.new_window(session, free[0], name, wt, window_env(values, state, role, name, brief),
                        LAUNCH % (shlex.join(harness(engine, model, effort, pass_, wt)), POINTER))
        wait_harness(session, free[0], name, ENGINE_CMD[engine], args.timeout)
    except (RuntimeError, OSError) as e:
        kill_run(values, session, state, name)
        print(e)
        return 1
    rec["start"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec.update(identity(session, free[0]), args={"issue": args.issue, "pr": args.pr, "pass": pass_,
                                                 "round": args.round, "tier": args.tier})
    save()
    print("crew: started %s (window %d, %s %s %s) in %s" % (name, free[0], engine, model, effort, wt))
    return 0
