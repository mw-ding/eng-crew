"""crew restart WINDOW --project FILE [--org-profile FILE]"""
import json
import os
import re
import shlex
import time
from crew_shared import (
    BANDS, finished, harness, heartbeat, identity, kill_run, LAUNCH, main, POINTER, probe, profile, runs, tmux,
    unlanded, wait_harness, window_env)


def relaunch(values, session, state, name, rec, items, timeout, project):
    """Restart a run whose worktree holds unlanded work: new window, same worktree, brief and claim."""
    brief = os.path.join(state, "runs", name + ".brief.md")
    for index, n in tmux.list_windows(session):
        if n == name:
            tmux.kill_window(session, index)
    used = [i for i, _ in tmux.list_windows(session)]
    free = [i for i in range(BANDS[rec["role"]][0], BANDS[rec["role"]][1] + 1) if i not in used]
    if not free or not os.path.exists(brief):
        print("crew: refusing restart: %s" % ("band %d-%d full" % BANDS[rec["role"]] if not free else
                                             "no brief %s" % brief))
        return 1
    index = rec["index"] if rec["index"] in free else free[0]
    wt = rec["worktree"]
    tmux.new_window(session, index, name, wt, window_env(values, state, rec["role"], name, brief, project),
                    LAUNCH % (shlex.join(harness(rec["engine"], rec["model"], rec["effort"], wt, state)), POINTER))
    try:
        wait_harness(session, index, name, rec["harness"], timeout)
    except RuntimeError as e:
        tmux.kill_window(session, index)
        print("%s; worktree, claim and run record kept" % str(e).replace("; cleaned up", ""))
        return 1
    rec.update(identity(session, index), index=index, restarts=1,
               start=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(os.path.join(state, "runs", name + ".json"), "w") as f:
        json.dump(rec, f, indent=2)
    print("crew: restarted %s (window %d) in its worktree %s, keeping unlanded work:\n  %s" % (
        name, index, wt, "\n  ".join(items)))
    return 0


def register(sub):
    p = sub.add_parser("restart")
    p.add_argument("window")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    """Restart a dead or missing run once: fresh worktree when clean, else its own worktree (tmux.md Q7)."""
    values, session, state = profile(args, "worktree_root")
    rec = dict(runs(state)).get(args.window)
    if rec is None:
        print("crew: no run %s" % args.window)
        return 1
    cls = probe(session, args.window, rec, dict((n, i) for i, n in tmux.list_windows(session)))
    last = heartbeat(state, args.window)[0]
    problem = ("%s is %s; only dead or missing runs restart" % (args.window, cls) if cls not in ("dead", "missing")
               else "%s finished (%s); use crew kill" % (args.window, last) if finished(rec, last)
               else "%s already restarted once; escalate (crew:escalated, owner channel)" % args.window
               if rec.get("restarts") else None)
    if problem or "args" not in rec:
        print("crew: refusing restart: " + (problem or "%s has no spawn arguments" % args.window))
        return 1
    wt, a = rec.get("worktree"), rec["args"]
    done = rec["role"] == "builder" and re.match(r"done: #\d+ #(\d+)\b", last)
    if done:  # its PR is open: restart as that PR's fix pass, never a second build pass (#234 N2)
        a = {**a, "pr": int(done.group(1)), "pass": "fix"}
        rec.update({"args": a, "pass": "fix", "item": "issue #%s, PR #%d" % (a["issue"], a["pr"])})
    try:
        items = unlanded(values, rec, wt) if wt and os.path.isdir(wt) else []
    except RuntimeError as e:
        items = ["unchecked: %s" % e]
    if items:  # never delete unlanded work (#172): relaunch in the same worktree and claim instead
        if done:
            with open(os.path.join(state, "runs", args.window + ".brief.md"), "a", encoding="utf-8") as f:
                f.write("- Restarted after done: as Pass fix, Item %s\n" % rec["item"])
        return relaunch(values, session, state, args.window, rec, items, args.timeout, args.project)
    if kill_run(values, session, state, args.window):
        return 1
    argv = ["spawn", rec["role"], "--pass", a["pass"], "--round", str(a["round"]), "--tier", a["tier"],
            "--project", args.project] + (["--org-profile", args.org_profile] if args.org_profile else [])
    argv += (["--issue", str(a["issue"])] if a["issue"] else []) + (["--pr", str(a["pr"])] if a["pr"] else [])
    code = main(argv + ["--timeout", str(args.timeout)])
    for name, new in runs(state):
        if new.get("args") == a:
            new["restarts"] = 1
            with open(os.path.join(state, "runs", name + ".json"), "w") as f:
                json.dump(new, f, indent=2)
    return code
