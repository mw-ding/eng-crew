#!/usr/bin/env python3
"""A28 two-full-team preflight and lifecycle (docs/campaign-harness.md#a28, #1440): `teams.py SOURCE ROOT --production
FILE --sentinel FILE [--engine ENGINE/MODEL] [--release ID] [--ready SECS]` first tears down every earlier run under
ROOT through its manifest (`campaign-sandbox.py teardown`, never a bare tmux call; a run without a valid manifest is
refused, #1474), then sets up a fresh level-a sandbox with two teams in ROOT/<run> (`campaign-sandbox.py setup --teams
2`), checks the preflight (separate roots, sessions and runtime instances; one repo
and control item; the same source, release and skills), starts both full teams with `mdstack up`, waits until every
required role (the coordinator and each enabled lead) probes alive, leaves one unlanded commit in each team's checkout
and tears down: both teams stopped, the commits retained, the sentinel unchanged. Without --engine every role is an
engine stub; with it both teams run that real engine, from an operator shell only. One JSON line per phase; exit 0
only when every phase passed."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SRC, path))
    mod = sys.modules[name] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def emit(phase, problems, **rec):
    print(json.dumps(dict(phase=phase, result="fail" if problems else "pass", problems=problems, **rec)), flush=True)
    return not problems


def git(path, *args):
    return subprocess.run(["git", "-C", path, *args], capture_output=True, text=True).stdout.strip()


def preflight(m, teams):
    """Each team's resolved target and parity facts, and every problem: shared roots, session or instance, another
    repo or control item, or a different source, release or skills (the templates and roles trees at the source)."""
    recs, out = [], guard.refusals(m)
    for t in teams:
        merged, _, problems, _ = guard.config.resolve_profile(t["project"], t["org_profile"])
        if problems:
            return recs, out + problems
        src, opts = t["source"], merged["runtime"].get("options", {})
        trees = git(src, "rev-parse", "HEAD:templates", "HEAD:roles") + git(src, "status", "--porcelain", "--",
                                                                             "templates", "roles")
        recs.append({"team": t["name"], "session": opts.get("session"), "instance": merged["runtime"].get("instance"),
                     "roots": [os.path.realpath(merged["paths"][k]) for k in guard.ROOTS],
                     "repo": "%s/%s" % (merged["repo"]["owner"], merged["repo"]["name"]),
                     "control_item": merged["repo"].get("control_item"), "source": git(src, "rev-parse", "HEAD"),
                     "release": t["release"], "skills": hashlib.sha256(trees.encode()).hexdigest()})
    a, b = recs
    out += ["%s: both teams have %r" % (k, a[k]) for k in ("session", "instance") if not a[k] or a[k] == b[k]]
    out += ["roots: %s and %s nest" % (x, y) for x in a["roots"] for y in b["roots"] if guard.nested(x, y)]
    out += ["%s: %r and %r differ" % (k, a[k], b[k]) for k in ("repo", "control_item", "source", "release", "skills")
            if a[k] != b[k] or a[k] is None]
    return recs, out


def roles(t):
    """Every required role's liveness (the coordinator, each enabled lead, each recorded run) and the rendered
    briefs."""
    values, session, state = shared.profile(argparse.Namespace(project=t["project"], org_profile=t["org_profile"]))
    lead, windows = shared.commands()["lead"], {n: i for i, n in shared.tmux.list_windows(session)}
    p = shared.tmux.pane(session, 0) if 0 in windows.values() else None
    got = {"coordinator": "missing" if not p else "dead" if p["dead"] == "1" else
           shared.harness_up(session, 0, p, shared.ENGINE_CMD.values())}
    got.update({values["identities.%s.name" % r].lower() + "-lead": "missing"
                for r in lead.POOLS if lead.enabled(state, r)})
    got.update({name: shared.probe(session, name, rec, windows)
                for name, rec in [*lead.records(state), *shared.runs(state)]})
    briefs = sorted(os.listdir(os.path.join(state, "render", "runtime")))
    return got, briefs


ap = argparse.ArgumentParser()
for flag in ("source", "root"):
    ap.add_argument(flag)
for flag in ("production", "sentinel"):
    ap.add_argument("--" + flag, required=True)
ap.add_argument("--engine")
ap.add_argument("--release", default="dev")
ap.add_argument("--ready", type=float, default=300)
a = ap.parse_args()
SRC, PARENT, RUN = os.path.realpath(a.source), os.path.realpath(a.root), "teams-%d" % os.getpid()
ROOT = os.path.join(PARENT, RUN)
guard, cr = load("campaign_guard", "scripts/campaign-guard.py"), load("campaign_run", "scripts/campaign-run.py")
sandbox = [sys.executable, os.path.join(SRC, "scripts", "campaign-sandbox.py")]
problems, earlier = [], sorted(os.listdir(PARENT)) if os.path.isdir(PARENT) else []
for d in earlier:  # a repeated run stops what an earlier one left running, keeping its work (#1474)
    old = os.path.join(PARENT, d, "state", "manifest.json")
    r = subprocess.run(sandbox + ["teardown", old], capture_output=True, text=True) if os.path.isfile(old) else None
    if not r or r.returncode:
        problems.append("%s: no valid manifest; refusing to clean it up" % d if not r else
                        "%s: teardown exit %d: %s" % (d, r.returncode, (r.stdout + r.stderr).strip()))
if not emit("cleanup", problems, runs=earlier):
    sys.exit(1)
r = subprocess.run(sandbox + ["setup", "--root", ROOT, "--run-id", RUN, "--production", a.production, "--source", SRC,
                              "--release", a.release, "--sentinel", a.sentinel, "--scenario", "A28", "--teams", "2"] +
                   (["--engine", a.engine] if a.engine else []), capture_output=True, text=True)
if not emit("setup", [] if r.returncode == 0 else (r.stdout + r.stderr).strip().splitlines(), run=RUN):
    sys.exit(1)
manifest = os.path.join(ROOT, "state", "manifest.json")
with open(manifest) as f:
    m = json.load(f)
with open(os.path.join(ROOT, "state", "sandbox.json")) as f:
    teams = json.load(f)["teams"]
state, base = m["roots"]["state_dir"], dict(os.environ)
os.environ.clear()  # the scenario environment: no forge token, SSH agent, inherited CREW_* or TMUX (#817)
os.environ.update(cr.scenario_env(m, 0, base), TMUX_TMPDIR=os.path.join(state, "tmux"))
os.makedirs(os.path.join(state, "gh"), exist_ok=True)
for name, body in (("pr-list", "[]"), ("issue-list", "[]"), ("repo-view", '{"defaultBranchRef":{"name":"main"}}')):
    with open(os.path.join(state, "gh", name + ".json"), "w") as f:
        f.write(body)
shared = load("crew_shared", "environments/terminal/crew.d/_shared.py")
engine = a.engine.split("/")[0] if a.engine else None
versions = {e: (subprocess.run([e, "-V" if e == "tmux" else "--version"], capture_output=True, text=True).stdout
                .strip().splitlines() or ["?"])[-1] for e in ["tmux"] + ([shared.ENGINE_CMD[engine]] if engine else [])}
try:
    recs, problems = preflight(m, teams)
    ok = emit("preflight", problems, teams=recs, versions=versions)
    for t in teams if ok else []:
        r = subprocess.run([sys.executable, os.path.join(SRC, "cli", "mdstack"), "up", "--project", t["project"],
                            "--org-profile", t["org_profile"]], capture_output=True, text=True,
                           env=dict(os.environ, CREW_PROJECT=t["project"]))
        ok = emit("up-" + t["name"], [] if r.returncode == 0 else ["exit %d" % r.returncode],
                  out=(r.stdout + r.stderr).strip().splitlines()[-4:]) and ok
    deadline, got = time.monotonic() + a.ready, {}
    while ok and time.monotonic() < deadline:
        got = {t["name"]: roles(t) for t in teams}
        if all(v == "alive" for live, _ in got.values() for v in live.values()):
            break
        time.sleep(2)
    if ok:
        problems = ["%s %s: %s" % (n, role, v) for n, (live, _) in got.items() for role, v in live.items()
                    if v != "alive"]
        problems += ["briefs: the teams render different roles"] if len({tuple(b) for _, b in got.values()}) > 1 else []
        ok = emit("ready", problems, roles={n: live for n, (live, _) in got.items()}, briefs=got["a"][1]) and ok
    for t in teams:  # unlanded work the teardown must keep (docs/campaign-harness.md#cleanup-checks)
        subprocess.run(["git", "-C", t["repo"], "checkout", "-q", "-b", "wip-" + t["name"]], check=True)
        subprocess.run(["git", "-C", t["repo"], "-c", "user.name=c", "-c", "user.email=c@x", "commit", "-q",
                        "--allow-empty", "-m", "wip: team %s unlanded" % t["name"]], check=True)
finally:
    r = subprocess.run(sandbox + ["teardown", manifest], capture_output=True, text=True)
    try:
        with open(os.path.join(state, "cleanup.json")) as f:
            c = json.load(f)
    except OSError:  # a refused teardown records nothing
        c = {"teams": [], "retained": [], "sentinel_unchanged": False}
    kept = {k["path"] for k in c["retained"] if any(" wip: team " in u for u in k["unpushed"])}
    problems = ["team %s still running" % s["team"] for s in c["teams"] if not s["stopped"]]
    problems += ["teams: %d stopped" % len(c["teams"])] if len(c["teams"]) != 2 else []
    problems += ["retained: %s lost its unlanded commit" % t["repo"] for t in teams if t["repo"] not in kept]
    problems += [] if c["sentinel_unchanged"] else ["sentinel changed (P0 isolation finding)"]
    ok = emit("teardown", problems, teams=c["teams"], retained=sorted(kept)) and ok
print("A28 teams: " + ("pass" if ok else "fail"))
sys.exit(0 if ok else 1)
