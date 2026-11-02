"""`crew spawn` creates a role window with its own worktree, engine, identity and brief, and queues beyond the profile
band cap for `crew dequeue`.
Refuses solo-labelled builder items before creating a claim, queue entry or window.

Usage: crew spawn ROLE --issue N | --pr N [--pass PASS] [--round K] [--tier T] --project FILE [--org-profile FILE]
"""
import json
import os
import shlex
import time
from crew_shared import (
    BANDS, brief_src, commands, ENGINE_CMD, fetch, git, harness, identity, kill_run, LAUNCH, NAMES, over_cap, PASSES, POINTER,
    profile, queue_lock, role_notes, ROLES, tmux, wait_harness, window_env, open_trains, synthesizer_work)


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


def exclude_crew(wt):
    """Exclude step summaries (.crew/) in the worktree's info/exclude, so they never count as unlanded (#234 N7)."""
    path = os.path.join(wt, git(wt, "rev-parse", "--git-path", "info/exclude"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+", encoding="utf-8") as f:
        f.seek(0)
        if ".crew/" not in f.read().split():
            f.write("\n.crew/\n")


def enqueue(state, args, pass_):
    """Append a capped spawn request to spawn-queue.jsonl for the coordinator; no window is created."""
    entry = {"role": args.role, "issue": args.issue, "pr": args.pr, "pass": pass_, "round": args.round,
             "tier": args.tier, "head": getattr(args, "head", None), "queued": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if getattr(args, "messages", None):
        entry["messages"] = args.messages
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "spawn-queue.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    if args.role == "builder" and getattr(args, "wake", True):
        with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a") as f:
            f.write(json.dumps(dict(event="builder-queued", reason="spawn")) + "\n")
    print("queued: %s %s %s (%s cap reached; run crew dequeue when a window closes)" % (
        args.role, pass_, "issue #%s" % args.issue if args.issue else "PR #%s" % args.pr, args.role))
    return 0


def register(sub):
    p = sub.add_parser("spawn")
    p.add_argument("role", choices=sorted(BANDS))
    p.add_argument("--issue", type=int)
    p.add_argument("--pr", type=int)
    p.add_argument("--pass", dest="pass_", choices=sorted({p for v in PASSES.values() for p in v}))
    p.add_argument("--head", help="expected PR head; refuse a changed head, including a queued spawn")
    p.add_argument("--round", type=int, default=1, help="verdict round k, for reviewer window names")
    p.add_argument("--tier", default="default", choices=["trivial", "default", "deep"])
    p.add_argument("--timeout", type=float, default=15.0, help="seconds to see the harness in the foreground")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    role = args.role
    data = ROLES[role]
    tool = ("toolchain_bin",) if data["lifetime"] == "issue" else ()
    values, session, state = profile(args, "worktree_root", *tool)
    pass_ = args.pass_ or (data.get("change_pass", PASSES[role][0]) if args.pr else PASSES[role][0])
    inputs = data["inputs"].get(pass_, [])
    if pass_ not in PASSES[role] or bool(args.issue) != ("issue" in inputs) or \
            bool(args.pr) != ("change" in inputs):
        error_inputs = next((v["inputs"][pass_] for v in ROLES.values() if v.get("change_pass") == pass_),
                            data["inputs"][PASSES[role][0]])
        expected = " ".join("--%s N" % ("pr" if i == "change" else i) for i in error_inputs)
        print("crew: %s %s takes %s" % (role, pass_, expected))
        return 2
    if role == "builder":
        try:
            if commands()["lead"].solo(values, args.issue, args.pr):
                print("crew: refusing spawn: solo item belongs to the owner's session")
                return 1
        except RuntimeError as e:
            print(e)
            return 1
    nm = values.get(data["identity_key"] + ".name", NAMES[role]).lower()
    name = data["window_name"].format(name=nm, issue=args.issue, change=args.pr, round=args.round, **{"pass": pass_})
    if not tmux.has_session(session):
        print("crew: session %s not reachable (tmux socket, or run crew up first)" % session)
        return 1
    tmux.pin_layout(session)
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    free = [i for i in range(BANDS[role][0], BANDS[role][1] + 1) if i not in windows.values()]
    if name not in windows and over_cap(values, role, windows, state):
        return enqueue(state, args, pass_)
    if role == "synthesizer" and name not in windows and os.path.exists(os.path.join(state, "runs", name + ".json")):
        if kill_run(values, session, state, name):
            return 1
    src = brief_src(state, role)
    problem = ("%s already running" % name if name in windows else "band %d-%d full" % BANDS[role] if not free
               else "no rendered brief %s (run crew up)" % src if not os.path.exists(src) else None)
    if problem:
        print("crew: refusing spawn: " + problem)
        return 1
    try:
        notes = role_notes(values, state, role)
        repo = git(os.path.dirname(os.path.abspath(args.project)), "rev-parse", "--show-toplevel")
        sha = fetch(repo, "pull/%d/head" % args.pr if args.pr else values["repo.default_branch"])
        if getattr(args, "head", None) and args.head != sha:
            raise RuntimeError("crew: stale spawn: expected %s, live head %s" % (args.head, sha))
        engine, model, effort = pick_engine(values, args.tier) if "engine_independent_of" not in data else pick_engine(
            values, args.tier, {line.split()[0] for line in git(
                repo, "log", "--format=%(trailers:key=Engine,valueonly)",
                "%s..%s" % (fetch(repo, values["repo.default_branch"]), sha)).splitlines()
                if line.strip() and not line.startswith("none")})
    except RuntimeError as e:
        print(e)
        return 1
    run = "%s-pr%d-%s" % (role, args.pr, sha[:7]) if args.pr else ""
    run += "-r%d-%s" % (args.round, pass_) if data["lifetime"] == "pass" else ""  # review and validate coexist (#139 F3)
    claim = os.path.join(state, "claims", "%s-issue%s" % (role, args.issue) if not args.pr else run)
    for d in ["claims", "runs", "inbox", "status"]:
        os.makedirs(os.path.join(state, d), exist_ok=True)
    try:
        os.close(os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY))  # atomic claim (protocol §6 step 2)
    except FileExistsError:
        print("crew: refusing spawn: claim %s exists" % claim)
        return 1
    item = ", ".join("issue #%s" % args.issue if i == "issue" else "PR #%d" % args.pr for i in inputs)
    wt = os.path.join(os.path.abspath(values["paths.worktree_root"]), "%d-%s-%s-%s%s" % (
        args.pr or args.issue, sha[:7], role, "r%d-" % args.round if data["lifetime"] == "pass" else "", pass_))
    rec = {"index": free[0], "role": role, "item": item, "pass": pass_, "repo": repo, "worktree": None, "claim": claim,
           "engine": engine, "model": model, "effort": effort, "harness": ENGINE_CMD[engine], "head": sha}
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
        exclude_crew(wt)
        brief = os.path.join(state, "runs", name + ".brief.md")
        with open(src, encoding="utf-8") as f, open(brief, "w", encoding="utf-8") as out:
            out.write(f.read() + "\n## This run\n\n" + "".join("- %s: %s\n" % kv for kv in [
                ("Window", name), ("Item", item), ("Pass", pass_), ("Worktree", wt), ("Base", sha),
                ("Engine", "%s %s %s" % (engine, model, effort)), ("Claim", claim)]))
        prompt = POINTER
        if role == "synthesizer":
            pending = os.path.join(state, "inbox", "synthesizer-pending.jsonl")
            inbox = os.path.join(state, "inbox", name + ".jsonl")
            if os.path.exists(pending):
                os.replace(pending, inbox)
            messages = synthesizer_work(state, name)
            rec["pending_lands"] = [m for m in messages if m["kind"] == "land"]
            trains = open_trains(state)
            if trains or messages:
                prompt += " Resume open trains: %s. Pending inbox IDs: %s." % (
                    ", ".join(trains) or "none", ", ".join(m["id"] for m in messages) or "none")
            with open(brief, "a", encoding="utf-8") as out:
                out.write("\n## Recovered work\n\nResume open trains before choosing a new land rule:\n" +
                          "".join("- " + p + "\n" for p in trains) +
                          "\nProcess every pending inbox message, acknowledging its ID again:\n" +
                          "".join("- inbox: " + m["id"] + "\n" for m in messages))
        with open(brief, "a", encoding="utf-8") as out:
            out.write(notes)
        argv = harness(engine, model, effort, wt, state, values["runtime.options.permission_mode"])
        tmux.new_window(session, free[0], name, wt, window_env(values, state, role, name, brief, args.project),
                        LAUNCH % (shlex.join(argv), prompt))
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
