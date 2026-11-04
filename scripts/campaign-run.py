#!/usr/bin/env python3
"""M25 scenario runner (#784): run selected campaign scenarios against a guarded manifest and record durable results.

Each scenario is `SCENARIOS/<Axx>.json`: {"id", "title", "requires": [tool...], "limitation": text, "steps": [...]}.
A step is either {"name", "run": SHELL, "exit": N} (a public CLI call; default expected exit 0) or
{"name", "wait": PATH, "match": REGEX, "deadline": SECS}, an explicit completion wait that polls PATH until REGEX
matches and fails at the deadline instead of sleeping a fixed time. `{state_dir}`, `{worktree_root}`, `{live_dir}`,
`{run_id}`, `{seed}` and `{source}` (the pinned eng-crew checkout) expand in `run` and `wait`. Children get the sandbox profile as CREW_PROJECT, no other
inherited CREW_* variable, and CAMPAIGN_SEED for replayable fake responses.

Statuses stay distinct: PASS (every step met), FAIL (a step's command exit differed or a wait timed out),
BLOCKED (a required tool is missing), LIMITATION (the scenario declares a known gap and is not run) and NOT RUN
(a manifest scenario not selected or without a spec). Each step records the command's own exit, stdout and stderr
apart from whether the capture itself worked. The seed (random unless given) fixes the scenario order and
CAMPAIGN_SEED, so `--rerun RESULTS` replays the same selection, seed, events and failure. The guard check
(campaign-guard.py) runs first; a refusal writes nothing and exits 2. It reruns before every `run` step; a refusal
there marks the scenario BLOCKED, the rest NOT RUN, stops the run and exits 2. Results are rewritten atomically after every
scenario, only inside a sandbox root. Exit 0 only when every result is PASS, else 1. Python 3.11+ stdlib only.

Usage: campaign-run.py MANIFEST --scenarios DIR --out FILE [--scenario AXX ...] [--seed N | --rerun RESULTS]
"""
import argparse
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("campaign_guard", Path(__file__).with_name("campaign-guard.py"))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def expand(text, m, seed):
    for key, val in dict(m["roots"], run_id=m["run_id"], seed=str(seed), source=m["source"]["path"]).items():
        text = text.replace("{%s}" % key, val)
    return text


def run_step(step, m, seed, env):
    """Return (ok, event, record) for one step; the event carries no timing so a rerun can compare it."""
    if "wait" in step:
        path, deadline = expand(step["wait"], m, seed), time.monotonic() + step.get("deadline", 30)
        while time.monotonic() < deadline:
            if os.path.isfile(path) and re.search(step["match"], Path(path).read_text()):
                return True, "wait %s: matched" % step["name"], {"name": step["name"], "wait": path, "matched": True}
            time.sleep(0.05)
        return False, "wait %s: deadline" % step["name"], {"name": step["name"], "wait": path, "matched": False}
    want = step.get("exit", 0)
    try:
        p = subprocess.run(["sh", "-c", expand(step["run"], m, seed)], capture_output=True, text=True, env=env,
                           timeout=step.get("deadline", 600))
        rec = {"capture": "ok", "exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except subprocess.TimeoutExpired as e:
        rec = {"capture": "timeout", "exit": None, "stdout": str(e.stdout or ""), "stderr": str(e.stderr or "")}
    ok = rec["exit"] == want
    return ok, "run %s: exit %s (want %s)" % (step["name"], rec["exit"], want), dict(rec, name=step["name"], want=want)


def run_scenario(sid, sdir, m, seed):
    path = Path(sdir, sid + ".json")
    if not path.is_file():
        return {"id": sid, "status": "NOT RUN", "reason": "no scenario spec %s" % path, "events": []}
    sc = json.loads(path.read_text())
    if sc.get("limitation"):
        return {"id": sid, "status": "LIMITATION", "reason": sc["limitation"], "events": []}
    missing = [t for t in sc.get("requires", []) if not shutil.which(t)]
    if missing:
        return {"id": sid, "status": "BLOCKED", "reason": "missing tool: " + ", ".join(missing), "events": []}
    env = {k: v for k, v in os.environ.items() if not k.startswith("CREW_")}
    env.update(CREW_PROJECT=m["profile"]["path"], CAMPAIGN_SEED=str(seed), CAMPAIGN_RUN=m["run_id"])
    res = {"id": sid, "status": "PASS", "events": [], "steps": []}
    for step in sc["steps"]:
        problems = [] if "wait" in step else guard.refusals(m)
        if problems:
            res.update(status="BLOCKED", reason="refused: " + "; ".join(problems), refused=True)
            break
        ok, event, rec = run_step(step, m, seed, env)
        res["events"].append(event)
        res["steps"].append(rec)
        if not ok:
            res.update(status="FAIL", reason=event)
            break
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest")
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scenario", action="append", default=[])
    ap.add_argument("--seed", type=int)
    ap.add_argument("--rerun")
    args = ap.parse_args(argv)
    m = json.loads(Path(args.manifest).read_text())
    seed, chosen = args.seed if args.seed is not None else random.randrange(2 ** 32), args.scenario or m["scenarios"]
    if args.rerun:
        prev = json.loads(Path(args.rerun).read_text())
        seed, chosen = prev["seed"], prev["selected"]
    out = os.path.realpath(args.out)
    problems = guard.refusals(m)
    problems += ["scenario: %s is not in the manifest" % s for s in chosen if s not in m["scenarios"]]
    if not any(out.startswith(r.rstrip(os.sep) + os.sep) for r in m["roots"].values()):
        problems.append("out: %s is outside the sandbox roots" % out)
    for p in problems:
        print("refused: " + p)
    if problems:
        return 2
    order = sorted(chosen)
    random.Random(seed).shuffle(order)
    doc = {"run_id": m["run_id"], "source_sha": m["source"]["sha"], "seed": seed, "selected": sorted(chosen),
           "order": order, "results": [{"id": s, "status": "NOT RUN", "reason": "not selected", "events": []}
                                       for s in m["scenarios"] if s not in chosen]}
    for i, sid in enumerate(order):
        res = run_scenario(sid, args.scenarios, m, seed)
        doc["results"].append(res)
        if res.get("refused"):
            doc["results"] += [{"id": s, "status": "NOT RUN", "reason": "run stopped: guard refused", "events": []}
                               for s in order[i + 1:]]
        Path(out + ".tmp").write_text(json.dumps(doc, indent=2) + "\n")
        os.replace(out + ".tmp", out)
        if res.get("refused"):
            break
    if not order:
        Path(out).write_text(json.dumps(doc, indent=2) + "\n")
    for r in doc["results"]:
        print("%s %s%s" % (r["id"], r["status"], ": " + r["reason"] if r.get("reason") else ""))
    print("seed %d; results %s" % (seed, out))
    if any(r.get("refused") for r in doc["results"]):
        return 2
    return 0 if all(r["status"] == "PASS" for r in doc["results"]) else 1


if __name__ == "__main__":
    sys.exit(main())
