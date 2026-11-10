"""`mdstack reflection` prints the reflection schedule's ledger (docs/self-improve.md#reflection, #1521).

With `[reflection] enabled`, each `mdstack watch` scan runs tick(), a zero-model timer independent of `[triage]` and
triage's milestone ledger. The researcher's `protocol-reflection` routine's weekly cron slot makes the last full ISO
week (`week-YYYY-Www`, UTC) pending; a project-repo milestone closed since the ledger's baseline makes `close-N`
pending at once (the first read records a baseline only). Pending windows not yet requested coalesce into one
`mdstack spawn researcher --reflection A+B --run-id ID`. The ledger, reflection/ledger.json, keeps pending windows, the
one request in flight and completed windows, so it survives sleep and a full researcher pool. A started or queued
request is never completion: once no run or spawn-queue entry carries its window, the log's posted `pass=reflection`
report completes every window it names, with its URL; with none, the request failed. A failed request retries after
the routine's retry under the same run ID, never while a queue entry or run still holds it. A missed weekly slot
catches up once; a quiet window still runs and completes on its `proposals=0` report.

Usage: mdstack reflection --project FILE [--org-profile FILE]
"""
import datetime
import json
import os
import subprocess
import sys
import time
from crew_shared import commands, CREW_BIN, profile, runs


def week_id(now):
    """The last full ISO week before now, Monday to Sunday UTC."""
    day = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date()
    year, week, _ = (day - datetime.timedelta(days=day.isoweekday())).isocalendar()
    return "week-%d-W%02d" % (year, week)


def load(state):
    try:
        with open(os.path.join(state, "reflection", "ledger.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save(state, ledger):
    path = os.path.join(state, "reflection", "ledger.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(ledger, f, indent=2)
    os.replace(path + ".tmp", path)


def held(state, window):
    """Whether a run record or a spawn-queue.jsonl entry carries the window; an unreadable queue counts as holding it."""
    if any((rec.get("args", {}).get("reflection") or {}).get("window") == window for _, rec in runs(state)):
        return True
    try:
        with open(os.path.join(state, "spawn-queue.jsonl")) as f:
            return any((json.loads(line).get("reflection") or {}).get("window") == window for line in f if line.strip())
    except FileNotFoundError:
        return False
    except (OSError, ValueError, AttributeError):
        return True


def tick(values, state, now, project, org_profile=None, read=None):
    """One timer pass; returns this pass's request or completion outcome, or None when disabled or nothing changed."""
    routines = commands()["up"].crew_routines
    routine = commands()["up"].ROUTINES[("researcher", "protocol-reflection")]
    if not routines.enabled(routine, values):
        return None
    ledger = load(state)
    pending, done = ledger.setdefault("pending", []), ledger.setdefault("completed", {})

    def add(window):
        if window not in pending and window not in done:
            pending.append(window)
    action, _ = routines.due(routine, values, {"at": ledger["slot"]} if "slot" in ledger else None, now)
    if action:  # the latest weekly slot only: downtime catches up once
        add(week_id(now))
        ledger["slot"] = now
    if now - ledger.get("checked", 0) >= values.get("runtime.options.poll_interval", 60):
        ledger["checked"] = now
        repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
        try:
            closed = sorted(m["number"] for m in (read or commands()["poll"].gh_json)(
                "api", "repos/%s/milestones?state=closed&per_page=100" % repo))
        except (RuntimeError, ValueError, KeyError, TypeError):
            closed = None  # unreadable: the baseline holds and the next read finds the close
        if closed is not None:
            for n in closed if "closed" in ledger else []:
                if n not in ledger["closed"]:
                    add("close-%d" % n)
            ledger["closed"] = closed
    outcome, req = None, ledger.get("request")
    retry = req and req["outcome"].startswith("failed") and now - req["at"] < routines.seconds(routine["retry"])
    if req and not retry and not held(state, req["window"]):
        try:
            url = commands()["restart"].reflection_posted(values, {"window": req["window"], "log": None})
        except RuntimeError as e:  # unverified: never a second run over a report that may be posted
            req.update(at=now, outcome="failed: cannot read the reflection log: %s" % e)
            retry, url = True, None
        if url:
            for w in req["window"].split("+"):
                done[w] = {"url": url, "run": req["run"], "at": now}
            pending[:] = [w for w in pending if w not in done]
            del ledger["request"]
            outcome, req = "completed: " + url, None
        elif not retry and not req["outcome"].startswith("failed"):
            req.update(at=now, outcome="failed: run ended without a posted report")
            outcome, retry = req["outcome"], True
    if pending and (not req or req["outcome"].startswith("failed") and not retry and not held(state, req["window"])):
        window = "+".join(sorted(pending))
        run = req["run"] if req and req["window"] == window else "%s-%s" % (
            window, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now)))
        cmd = [sys.executable, CREW_BIN, "spawn", "researcher", "--reflection", window, "--run-id", run,
               "--project", project] + (["--org-profile", org_profile] if org_profile else [])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            out = (r.stdout.strip().splitlines() or ["exit %d" % r.returncode])[-1]
            outcome = ("queued" if out.startswith("queued:") else "started") if r.returncode == 0 else "failed: " + out
        except subprocess.TimeoutExpired:
            outcome = "failed: spawn timed out"
        ledger["request"] = {"window": window, "run": run, "at": now, "outcome": outcome}
    save(state, ledger)
    return outcome


def register(sub):
    p = sub.add_parser("reflection")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    _, _, state = profile(args)
    print(json.dumps(load(state), indent=2, sort_keys=True))
    return 0
