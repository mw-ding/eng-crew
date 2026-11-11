"""`mdstack restart` restarts a dead, missing or quota-stopped run once (a builder even after `done:`, as its PR's fix pass; `done:` is
terminal only for reviewer and synthesizer runs), in its own worktree when it holds unlanded work. A run on a role
host (#345) is probed, checked and relaunched there; a clean one is removed there and spawned again, so placement
runs again. A reflection run first rechecks its window's posted report and, when one is there, refuses (#1520); else it
restarts with the same run ID, log issue, input SHA and window. A run probing quota (its harness shows its adapter's
usage-limit line, #631) is stopped and relaunched on the next eligible engine in its role's order, skipping every engine
it has exhausted; with none left it refuses and the run stays for escalation.

On the coordinator's window (window 0) it relaunches the live coordinator in place instead (#1544): the current
sandbox_env and CREW_* environment, resuming --resume ID (else launch.resume). It refuses while the land lock is held,
when run from window 0 itself (beneath its pane process), which the stop would kill first, and for a team reference.

Usage: mdstack restart WINDOW --project FILE [--org-profile FILE] [--resume ID]
"""
import json
import os
import re
import shlex
import subprocess
import time
from crew_shared import (
    BANDS, brief_src, commands, coordinator_harness, coordinator_window, CREW_BIN, crew_render, ENGINE_CMD, fetch, finished,
    harness, harnesses, heartbeat, identity, kill_run, LAUNCH, main, POINTER, probe, profile, remote_run, ROLES, runs, sandbox_env,
    show_icon, stop_pane, tmux, unlanded, wait_harness, window_alias, window_env)


def runs_under(pid):
    """Whether this process runs beneath pid (its parent or an ancestor), on ps's pid/ppid table: a pane id alone
    would match another tmux server's pane."""
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,stat=,comm="], capture_output=True, text=True).stdout
    parents = {row[0]: row[1] for row in (line.split(None, 3) for line in out.splitlines()) if len(row) >= 2}
    node, seen = str(os.getppid()), set()
    while node and node not in seen:
        if node == str(pid):
            return True
        seen.add(node)
        node = parents.get(node)
    return False


def relaunch_coordinator(values, session, state, args):
    """Respawn window 0 in place with the current sandbox_env and CREW_* environment, resuming its conversation."""
    engine, resume = values["engines.coordinator"], args.resume or values.get("runtime.options.launch.resume", "fresh")
    pane = tmux.pane(session, 0)
    problem = ("a team coordinator is not relaunched here" if "#" in args.project
               else "--resume expects fresh, ask or a session id" if resume not in ("fresh", "ask") and
               not crew_render.crew_config.LAUNCH_SESSION_ID.fullmatch(resume)
               else "the land lock is held" if commands()["land-lock"].held(state)
               else "%s is not running" % session if not pane
               else "run it from the owner's terminal, not window 0" if runs_under(pane["pid"])
               else "%s cannot resume" % engine if resume != "fresh" and engine not in harnesses.RESUMABLE
               else "%s has no in-place reload" % tmux.name if "reload" not in tmux.CAPABILITIES else None)
    if problem:
        print("crew: refusing coordinator relaunch: " + problem)
        return 1
    project_dir = os.path.dirname(os.path.abspath(args.project))
    cmd = shlex.join(coordinator_harness(engine, project_dir, state, values["runtime.options.permission_mode"], values,
                                         resume))
    env = {"CREW_ROLE": "coordinator", "CREW_STATE": state, "CREW_IDENTITY": values["identities.coordinator.gh_user"],
           "CREW_BIN": CREW_BIN, "CREW_BRIEF": brief_src(state, "coordinator"),
           "CREW_PROJECT": os.path.abspath(args.project), **sandbox_env(values)}
    tmux.hold(session, 0)
    if stop_pane(session, 0):
        print("crew: refusing coordinator relaunch: window 0's process group survived the stop")
        return 1
    tmux.respawn(session, 0, project_dir, env,
                 LAUNCH.removesuffix(' "%s"') % cmd if resume == "ask" else LAUNCH % (cmd, POINTER))
    try:
        wait_harness(session, 0, coordinator_window(values), ENGINE_CMD[engine], args.timeout)
    except RuntimeError as e:
        print(e)
        return 1
    print("crew: relaunched %s in place (window 0, resume %s)" % (coordinator_window(values), resume))
    return 0


def next_engine(values, state, rec, exhausted):
    """The first eligible engine of the run's role order past every exhausted one, as spawn would pick it; a reviewer
    still avoids the PR's builder engines (#631). RuntimeError when none is left."""
    spawn, a = commands()["spawn"], rec["args"]
    avoid = set(exhausted)
    if "engine_independent_of" in ROLES[rec["role"]]:
        avoid |= spawn.builder_engines(values, state, rec["repo"], fetch(rec["repo"], values["repo.default_branch"]),
                                       rec["head"], a["pr"])
    return spawn.engine_order(values, a["tier"], avoid, rec["role"])[0]


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
    argv = harness(rec["engine"], rec["model"], rec["effort"], wt, state, values["runtime.options.permission_mode"], values)
    tmux.new_window(session, index, name, wt, window_env(values, state, rec["role"], name, brief, project),
                    LAUNCH % (shlex.join(argv), POINTER))
    try:
        show_icon(values, session, index, rec["role"])
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


def relaunch_remote(values, state, name, rec, items):
    """Restart a run on its role host in its own worktree, which holds unlanded work; the brief travels again."""
    reply = remote_run.spawn(values, state, name, rec, os.path.join(state, "runs", name + ".brief.md"))
    if reply["result"] != "ok":
        print("crew: refusing restart on %s: %s: %s; worktree, claim and run record kept" % (
            rec["host"], reply["result"], reply.get("reason") or reply.get("error")))
        return 1
    rec.update({k: reply[k] for k in ("pane_id", "pane_pid", "pane_start")}, restarts=1,
               start=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with open(os.path.join(state, "runs", name + ".json"), "w") as f:
        json.dump(rec, f, indent=2)
    print("crew: restarted %s on %s in its worktree %s, keeping unlanded work:\n  %s" % (
        name, rec["host"], rec["worktree"], "\n  ".join(items)))
    return 0


def reflection_posted(values, r):
    """The URL of a posted report covering the reflection run's window on its log issue (or the open reflection:log
    issues when none was given), else None: a restart writes nothing over a finished report (#1520)."""
    route, repo = commands()["route"], "%s/%s" % (values["repo.owner"], values["repo.name"])
    logs = [r["log"]] if r.get("log") else [i["number"] for i in route.gh(
        "issue", "list", "-R", repo, "--label", "reflection:log", "--state", "open", "--json", "number")]
    want = set(r["window"].split("+"))
    for n in logs:
        for c in route.gh("issue", "view", str(n), "-R", repo, "--json", "comments")["comments"]:
            if any(m.get("role") == "researcher" and m.get("pass") == "reflection" and
                   want <= set(m.get("window", "").split("+")) for m in route.markers(c["body"])):
                return c["url"]
    return None


def register(sub):
    p = sub.add_parser("restart")
    p.add_argument("window")
    p.add_argument("--timeout", type=float, default=15.0)
    p.add_argument("--project")
    p.add_argument("--org-profile")
    p.add_argument("--resume", metavar="ID", help="coordinator window: resume this conversation (fresh, ask or an id)")


def run(args):
    """Restart a dead or missing run once: fresh worktree when clean, else its own worktree (tmux.md Q7)."""
    values, session, state = profile(args, "worktree_root")
    if window_alias(values, args.window) == coordinator_window(values):
        return relaunch_coordinator(values, session, state, args)
    rec = dict(runs(state)).get(args.window)
    if rec is None:
        print("crew: no run %s" % args.window)
        return 1
    host = remote_run.host_of(rec)
    cls = remote_run.probe(values, args.window, rec) if host else \
        probe(session, args.window, rec, dict((n, i) for i, n in tmux.list_windows(session)))
    last = heartbeat(state, args.window)[0]
    problem = ("%s is %s; only dead, missing or quota runs restart" % (args.window, cls) if cls not in ("dead", "missing", "quota")
               else "%s finished (%s); use mdstack kill" % (args.window, last) if finished(rec, last)
               else "%s already restarted once; escalate (crew:escalated, owner channel)" % args.window
               if rec.get("restarts") else "a quota run on a role host is not relaunched here; escalate"
               if cls == "quota" and host else None)
    if problem or "args" not in rec:
        print("crew: refusing restart: " + (problem or "%s has no spawn arguments" % args.window))
        return 1
    wt, a = rec.get("worktree"), rec["args"]
    exhausted = rec.get("exhausted", []) + [rec["engine"]] if cls == "quota" else []
    if exhausted:
        try:
            engine, model = next_engine(values, state, rec, exhausted)
        except RuntimeError as e:
            print("crew: refusing restart: %s is out of quota and no eligible engine is left: %s; escalate" % (
                rec["engine"], e))
            return 1
    if a.get("reflection"):
        try:
            url = reflection_posted(values, a["reflection"])
        except RuntimeError as e:
            print("crew: refusing restart: cannot recheck reflection %s's report: %s" % (a["reflection"]["window"], e))
            return 1
        if url:
            print("crew: refusing restart: reflection %s already posted at %s; use mdstack kill" % (
                a["reflection"]["window"], url))
            return 1
    done = rec["role"] == "builder" and re.match(r"done: #\d+ #(\d+)\b", last)
    if done:  # its PR is open: restart as that PR's fix pass, never a second build pass (#234 N2)
        a = {**a, "pr": int(done.group(1)), "pass": "fix"}
        rec.update({"args": a, "pass": "fix", "item": "issue #%s, PR #%d" % (a["issue"], a["pr"])})
    if host:  # the host stops the run, then removes the worktree only when it is clean
        reply = remote_run.kill(values, args.window, rec)
        if reply["result"] != "ok":
            print("crew: refusing restart on %s: %s: %s" % (host, reply["result"], reply.get("reason") or reply.get("error")))
            return 1
        items = reply["unlanded"]
    else:
        try:
            items = unlanded(values, rec, wt) if wt and os.path.isdir(wt) else []
        except RuntimeError as e:
            items = ["unchecked: %s" % e]
    if items:  # never delete unlanded work (#172): relaunch in the same worktree and claim instead
        if done:
            with open(os.path.join(state, "runs", args.window + ".brief.md"), "a", encoding="utf-8") as f:
                f.write("- Restarted after done: as Pass fix, Item %s\n" % rec["item"])
        if exhausted:  # the quota pane is still up: stop it first (kill-window alone leaves Codex running, #139 F2)
            if stop_pane(session, rec["index"]):
                print("crew: refusing restart: %s's process group survived the stop" % args.window)
                return 1
            with open(os.path.join(state, "runs", args.window + ".brief.md"), "a", encoding="utf-8") as f:
                f.write("- Quota fallback: %s is out of quota; this session runs %s %s %s. Attribute that engine.\n" % (
                    rec["engine"], engine, model, rec["effort"]))
            rec.update(engine=engine, model=model, harness=ENGINE_CMD[engine], exhausted=exhausted)
        if host:
            return relaunch_remote(values, state, args.window, rec, items)
        return relaunch(values, session, state, args.window, rec, items, args.timeout, args.project)
    if kill_run(values, session, state, args.window):
        return 1
    mode = ["--train", str(a["train"])] if a.get("train") else ["--pass", a["pass"]]  # a train worker has no pass flag (#1391)
    argv = ["spawn", rec["role"], *mode, "--round", str(a["round"]), "--tier", a["tier"],
            "--project", args.project] + (["--org-profile", args.org_profile] if args.org_profile else [])
    argv += (["--issue", str(a["issue"])] if a["issue"] else []) + (["--pr", str(a["pr"])] if a["pr"] else [])
    if rec.get("rereview_id"):  # same PR/head/pass/round keeps its steer; a moved head refuses as stale (#1477)
        argv += ["--rereview-id", rec["rereview_id"], "--head", rec["head"]]
    r = a.get("reflection")
    argv += ["--reflection", r["window"], "--run-id", r["run"], "--input-sha", r["sha"]] + (
        ["--log", str(r["log"])] if r["log"] else []) if r else []
    argv += [x for e in exhausted for x in ("--skip-engine", e)]  # spawn picks past them (#631)
    code = main(argv + ["--timeout", str(args.timeout)])
    for name, new in runs(state):
        if new.get("args") == a:
            new["restarts"] = 1
            if exhausted:
                new["exhausted"] = exhausted
            with open(os.path.join(state, "runs", name + ".json"), "w") as f:
                json.dump(new, f, indent=2)
    return code
