"""`crew watch` is the zero-token watcher that queues wakes in `wake/queue.jsonl` (one-shot `--source` commands cut off
at `--source-timeout`, default 60 s, queue growth from another poller, and an `ask:`
wake at each open owner ask's deadline in `asks/<n>.json`; a signal during a scan is held until its children exit)
and retries pending lead admission every 60 s, then exits with one reason line; runs without `start` skip liveness
wakes while their record mtime is less than 60 s
old. Verified panes with a live tool session or recent output get a supervisor heartbeat instead of a stale wake.
Each live run's screen is matched against its harness adapter's transient-error text; each new match is a line in
`schedule/errors.jsonl` (docs/scheduling.md#inputs). Finishing work deferred by the scheduler past `stuck_after` is one
`schedule-stuck` wake per (pool, ref, first deferral), and the exit line is followed by `crew schedule summary`'s line
(docs/scheduling.md#observability).
Its `wake: watcher` line is never typed into a window 0 showing a dialog, which gets
a `dialog` wake instead (#315). Before a coordinator wake, `crew route` consumes mechanical records;
the watcher continues scanning when none of the new records need judgement (#434).
A source cut off at its timeout or exiting 75 (EX_TEMPFAIL, a transient `crew poll` failure) is a line in
`wake/incidents.jsonl`, not a wake; `--source-failures` consecutive ones send one `source-failing` wake with the count.
When `scripts/crew`, `crew.d/*.py` or `crew-*.py` change on disk, the watcher re-execs itself before it queues or
routes that scan's wakes, so new code resolves any new profile keys (#702).
Once another runtime owns the repo (ownership `lost`, after a handoff's ack) the watcher refuses to arm (prompt stop).
With `[triage] enabled`, each scan runs the triage sweep timer, which costs no model turn and queues no wake
(docs/triage.md#triggers-and-cadence, #748); a newly closed milestone makes a sweep due at once (#374).
With `[docs] enabled`, each scan runs the docs-pass timer: the zero-model docs scan, then a docs-pass researcher session
only when the scan changed since the last report (docs/project-docs.md#docs-pass, #1026).

Usage: crew watch --project FILE [--org-profile FILE]
"""
import argparse
import contextlib
import datetime
import glob
import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from crew_shared import commands, dialog, ownership_module, ENGINE_CMD, foreground_matches, finished, gateway_error, HERE, heartbeat, idle_builder, probe, profile, queue_lock, remember_pr, runs, TRANSIENT, tmux, transient_lines


def asks(state):
    """Open owner asks, asks/<n>.json {"deadline": ISO 8601 with UTC offset}: (n, deadline, epoch); an unreadable
    deadline is due now, so a bad record wakes the coordinator instead of dropping the timer (#287)."""
    d, found = os.path.join(state, "asks"), []
    for n in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if n.endswith(".json"):
            try:
                with open(os.path.join(d, n)) as f:
                    text = json.load(f)["deadline"]
                due = datetime.datetime.fromisoformat(text).timestamp()
            except FileNotFoundError:
                continue  # closed between listdir and open
            except (OSError, ValueError, KeyError, TypeError):
                text, due = "unreadable", 0.0
            found.append((n[:-5], text, due))
    return found


def pause(state, now, interval):
    """Seconds to the next scan: --interval, cut short so that a scan lands on the next open ask's deadline."""
    return min([interval] + [due - now for _, _, due in asks(state) if due > now])


def work(state, name, rec):
    """Queued or in-flight work: a lead's undone inbox messages, a synthesizer's unacked messages, uncompleted lands,
    open trains or held land lock; other roles always count as working."""
    if rec["role"].endswith("-lead"):
        return bool(commands()["lead"].pending(state, name))
    if rec["role"] == "synthesizer":
        with queue_lock(state):
            return commands()["route"].synthesizer_busy(state, name)
    return True


def scan(state, session, now, stale, seen, idle_ttl=1800, stuck_after=1800):
    """Wake records: new status lines, runs dead, missing or silent past stale, owner asks past their deadline and
    finishing work deferred past stuck_after; each fires once per key."""
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    wakes = []
    for name, rec in list(runs(state)) + list(commands()["lead"].records(state)):
        identity = [rec.get(k) for k in ("start", "pane_id", "pane_pid", "pane_start", "worktree")]
        identities = seen.setdefault("runs", {})
        if name in identities and identities[name] != identity:
            seen["offsets"].pop(name, None)
            seen["keys"].pop(name, None)
        identities[name] = identity
        previous_pr = rec.get("pr")
        status = os.path.join(state, "status", name + ".status")
        size, off = os.path.getsize(status) if os.path.exists(status) else 0, seen["offsets"].get(name, 0)
        if size and size != off:
            with open(status) as f:
                f.seek(off if size > off else 0)  # shorter than seen: a new run's file
                for line in f.read().splitlines():
                    remember_pr(rec, line)
                    if line.strip():
                        wakes.append({"reason": "status", "window": name, "line": line})
        seen["offsets"][name] = size
        if rec.get("pr") != previous_pr:
            path = os.path.join(state, "runs", name + ".json")
            with open(path + ".tmp", "w") as f:
                json.dump(rec, f, indent=2)
            os.replace(path + ".tmp", path)
        try:
            if not rec.get("start") and now - os.path.getmtime(os.path.join(state, "runs", name + ".json")) < 60:
                continue  # spawn saves its record before the window and pane identity; an older record is a failed spawn
        except FileNotFoundError:
            continue  # reaped between listing and stat (#591)
        last, beat = heartbeat(state, name)
        if beat is None:
            continue
        cls = probe(session, name, rec, windows)
        if cls in ("alive", "ambiguous") and rec.get("harness") in TRANSIENT:
            for line in transient_lines(tmux.capture(session, rec["index"]), rec["harness"]):
                gateway_error(state, name, line, now, once=True)
        idle = idle_builder(state, name) if rec["role"] == "builder" and cls == "alive" else None
        if idle_ttl and idle is not None and now - idle >= idle_ttl:
            key = "idle %s" % idle
            if seen["keys"].get(name) != key:
                seen["keys"][name] = key
                wakes.append({"reason": "idle-builder", "window": name, "event": "idle expiry"})
            continue
        if cls == "ambiguous" and not finished(rec, last) and dialog(session, rec["index"]):
            if seen["keys"].get(name) != "dialog %s" % beat:  # wakes on the next scan, never after --stale (#234 N3)
                seen["keys"][name] = "dialog %s" % beat
                wakes.append({"reason": "dialog", "window": name, "liveness": cls, "silent": int(now - beat),
                              "action": "escalate"})
            continue
        if finished(rec, last) or (cls in ("alive", "ambiguous") and (last.startswith("done:") or now - beat <= stale)):
            continue  # a live builder after done: waits for its inbox; a dead one is restartable (#139 F4)
        p = tmux.pane(session, rec["index"]) if cls in ("alive", "ambiguous") else None
        if p and p["dead"] == "0" and (p["id"], p["pid"]) == (rec.get("pane_id"), rec.get("pane_pid")) and \
                tmux.proc_start(p["pid"]) == rec.get("pane_start") and \
                (now - float(p["activity"]) <= stale or tmux.live_child(p["pid"], rec["harness"])):
            with open(status, "a") as f:
                f.write("heartbeat: %s\n" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)))
            os.utime(status, (now, now))
            continue
        if cls in ("alive", "ambiguous") and not work(state, name, rec):
            continue  # an idle lead or synthesizer has nothing to progress; dead or missing still wakes (#578)
        key = "stale %s" % beat  # not the class: an ambiguous -> alive flip is the same silence (#234 N4)
        if seen["keys"].get(name) != key:
            seen["keys"][name] = key
            wakes.append({"reason": "stale", "window": name, "liveness": cls, "silent": int(now - beat),
                          "action": "restart" if cls in ("dead", "missing") and not rec.get("restarts") else "escalate"})
    for n, text, due in asks(state):  # whatever the backstop: the ask's §6 auto-apply time (tmux.md C8)
        if now >= due and seen["keys"].get("ask " + n) != text:  # once per (ask, deadline)
            seen["keys"]["ask " + n] = text
            wakes.append({"reason": "ask", "event": "%s deadline %s" % (n, text)})
    schedule = commands()["schedule"]
    found = schedule.read(schedule.stuck, state, now, stuck_after)
    for d in [] if found == schedule.UNKNOWN else found:
        if seen["keys"].get("stuck %s %s" % (d["pool"], d["ref"])) != d["since"]:
            seen["keys"]["stuck %s %s" % (d["pool"], d["ref"])] = d["since"]
            line = schedule.read(schedule.latest, state)
            wakes.append({"reason": "schedule-stuck", "snapshot": line["snapshot"] if isinstance(line, dict) else None,
                          "event": "%s %s %s class %s deferred since %s: %s" % (
                              d["pool"], d["ref"], d["kind"], d["class"], d["since"], ", ".join(d["reasons"]))})
    for name, _ in commands()["lead"].records(state):
        retries = seen.setdefault("lead_retries", {})
        if not commands()["lead"].pending(state, name):
            retries.pop(name, None)
        elif now >= retries.setdefault(name, now + 60):
            wakes.append({"reason": "lead-backstop", "window": name, "event": "admission retry"})
            retries[name] = now + 60
    return wakes


SWEEP_RETRY = 600  # seconds before a failed sweep spawn is retried


def triage_tick(values, state, now, project, org_profile=None):
    """Triage sweep timer: once `[triage] interval_hours` passed since the last slot in triage/sweep.json (at once when
    none is recorded, so a crew waking overdue sweeps on its first scan), start `crew spawn researcher --sweep`. The slot
    is skipped when triage/queue.json lists no items (`crew poll` queues unplaced issues and owner replies there); an
    unreadable queue sweeps (docs/triage.md#inputs). A failed spawn retries after SWEEP_RETRY. Returns the new slot's
    outcome, or None when disabled or not due. A queued closed milestone that no sweep started with yet makes the slot due
    at once, retried as above, unless the last slot queued a sweep, which takes it when it starts (T6, #374)."""
    if not values.get("triage.enabled"):
        return None
    path = os.path.join(state, "triage", "sweep.json")
    try:
        with open(os.path.join(state, "triage", "queue.json")) as f:
            empty = json.load(f)["items"] == []
    except (OSError, ValueError, KeyError, TypeError):
        empty = False
    milestones = commands()["poll"].triage_untaken(state)
    try:
        with open(path) as f:
            last = json.load(f)
        retry = last["outcome"].startswith("failed")
        wait = SWEEP_RETRY if retry else values["triage.interval_hours"] * 3600
        if now - last["at"] < wait and (retry or not milestones or last["outcome"] == "queued"):
            return None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass  # never swept, or an unreadable record: due now
    if empty and not milestones:
        outcome = "skipped: empty queue"
    else:
        cmd = [sys.executable, os.path.join(HERE, "crew"), "spawn", "researcher", "--sweep", "--project", project]
        try:
            r = subprocess.run(cmd + (["--org-profile", org_profile] if org_profile else []),
                               capture_output=True, text=True, timeout=120)
            out = (r.stdout.strip().splitlines() or ["exit %d" % r.returncode])[-1]
            outcome = ("queued" if out.startswith("queued:") else "started") if r.returncode == 0 else "failed: " + out
        except subprocess.TimeoutExpired:
            outcome = "failed: spawn timed out"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump({"at": now, "outcome": outcome}, f)
    os.replace(path + ".tmp", path)
    return outcome


def scan_digest(values, state):
    """Digest of every `[docs] repos` scan.json with the head, scan date and banner ages left out, so a scan whose
    findings and inventory did not change matches; None when one is unreadable, which never counts as unchanged."""
    out = hashlib.sha256()
    for repo in values["docs.repos"]:
        try:
            with open(os.path.join(os.path.dirname(state), repo.replace("/", "__"), "docs", "scan.json")) as f:
                data = json.load(f)
            for key in ("head", "scanned"):
                data.pop(key, None)
            for item in data.get("stale", []):
                item.pop("age_days", None)
            out.update(json.dumps([repo, data], sort_keys=True).encode())
        except (OSError, ValueError, AttributeError, TypeError):
            return None
    return out.hexdigest()


def docs_tick(values, state, now, project, org_profile=None):
    """Docs-pass timer: once `[docs] interval_days` passed since the last slot in docs/pass.json (at once when none is
    recorded, so a crew waking with a pass overdue runs it on its first scan), fetch the default branch into the
    project's checkout, run `docs-scan.py` on it (no model), then start `crew spawn researcher --docs-pass`. The slot is
    skipped when the scans digest as the slot that last started or queued a pass (the last report) recorded. A failed
    scan or spawn retries after SWEEP_RETRY. Returns the new slot's outcome, or None when disabled or not due. The timer
    passes only the project's own checkout, so another `[docs] repos` entry fails the scan (docs/project-docs.md#triggers)."""
    if not values.get("docs.enabled"):
        return None
    path, reported = os.path.join(state, "docs", "pass.json"), None
    try:
        with open(path) as f:
            last = json.load(f)
        reported = last.get("reported")
        wait = SWEEP_RETRY if last["outcome"].startswith("failed") else values["docs.interval_days"] * 86400
        if now - last["at"] < wait:
            return None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass  # never run, or an unreadable record: due now
    org = ["--org-profile", org_profile] if org_profile else []
    repo = os.path.dirname(os.path.abspath(project))
    try:
        repo = subprocess.run(["git", "-C", repo, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                              timeout=60).stdout.strip() or repo
        subprocess.run(["git", "-C", repo, "fetch", "-q", "origin", values["repo.default_branch"]], capture_output=True,
                       timeout=120)  # a failed fetch scans the last fetched head
        r = subprocess.run([sys.executable, os.path.join(HERE, "docs-scan.py"), "--project", project, "--checkout",
                            "%s/%s=%s" % (values["repo.owner"], values["repo.name"], repo)] + org,
                           capture_output=True, text=True, timeout=300)
        digest = None if r.returncode else scan_digest(values, state)
        if r.returncode:
            outcome = "failed: scan: " + ((r.stderr.strip() or r.stdout.strip()).splitlines() or ["exit %d" % r.returncode])[-1]
        elif digest is not None and digest == reported:
            outcome = "skipped: scan unchanged"
        else:
            r = subprocess.run([sys.executable, os.path.join(HERE, "crew"), "spawn", "researcher", "--docs-pass",
                                "--project", project] + org, capture_output=True, text=True, timeout=120)
            out = (r.stdout.strip().splitlines() or ["exit %d" % r.returncode])[-1]
            outcome = ("queued" if out.startswith("queued:") else "started") if r.returncode == 0 else "failed: " + out
            reported = digest if r.returncode == 0 else reported
    except subprocess.TimeoutExpired as e:
        outcome = "failed: timed out: " + " ".join(os.path.basename(str(a)) for a in e.cmd[:3])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump({"at": now, "outcome": outcome, "reported": reported}, f)
    os.replace(path + ".tmp", path)
    return outcome


def armed(pidfile):
    """PID of another live `crew watch` named in wake/watcher.pid, else None; a stale or reused PID is not armed."""
    try:
        with open(pidfile) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None
    if pid == os.getpid():
        return None
    command = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout
    return pid if "watch" in command.split() else None


def reason(w):
    if "event" in w:
        return "%s: %s" % (w["reason"], w["event"])
    if "line" in w:
        return "status: %s %s" % (w["window"], w["line"])
    return "%s: %s %s, silent %ds, %s" % (w["reason"], w["window"], w["liveness"], w["silent"], w["action"])


def queue_sig(wake):
    """(inode, byte size, mtime) of wake/queue.jsonl, or None; a change means records were appended or drained."""
    try:
        st = os.stat(os.path.join(wake, "queue.jsonl"))
    except FileNotFoundError:
        return None
    return [st.st_ino, st.st_size, st.st_mtime_ns]


def queued(state, wake, seen):
    """Records appended to queue.jsonl since the offset in seen (another poller's); never queued again."""
    with queue_lock(state):
        sig, old = queue_sig(wake), seen.get("queue")
        if sig == old or sig is None:
            seen["queue"] = sig
            return []
        with open(os.path.join(wake, "queue.jsonl"), encoding="utf-8") as f:
            f.seek(old[1] if old and old[0] == sig[0] and sig[1] > old[1] else 0)  # else drained: a new file
            lines = f.read().splitlines()
        seen["queue"] = sig
    records = []
    for line in lines:
        with contextlib.suppress(ValueError):  # a source killed mid-append leaves a partial line
            records.append(json.loads(line))
    return records


def code_sig():
    """mtimes of the crew CLI and the modules it loads; a change means a tooling update landed under this watcher."""
    paths = [os.path.join(HERE, "crew")] + glob.glob(os.path.join(HERE, "crew.d", "*.py")) + \
        glob.glob(os.path.join(HERE, "crew-*.py"))
    return sorted((p, os.stat(p).st_mtime_ns) for p in paths if os.path.exists(p))


def reexec():
    """Replace this process with a fresh `crew watch` on the same argv; the PID, so wake/watcher.pid, is kept."""
    sys.stdout.flush()
    print("crew: watch: crew code changed on disk; re-exec", file=sys.stderr, flush=True)
    os.execv(sys.executable, [sys.executable, *sys.argv])


def source_failure(wake, seen, cmd, error, limit):
    """Record one transient source failure in wake/incidents.jsonl; return a wake only at the limit-th in a row."""
    failures = seen.setdefault("source_failures", {})
    n = failures[cmd] = failures.get(cmd, 0) + 1
    with open(os.path.join(wake, "incidents.jsonl"), "a") as f:
        f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": cmd, "error": error,
                            "consecutive": n}) + "\n")
    if n < limit:
        return []
    failures[cmd] = 0
    return [{"reason": "source-failing", "event": "%s: %d failures in a row, last: %s" % (cmd, n, error)}]


def register(sub):
    p = sub.add_parser("watch")
    p.add_argument("--stale", type=float, default=900, help="seconds without status progress before a stale wake")
    p.add_argument("--backstop", type=float, default=1800, help="seconds to a backstop wake; x2 per idle wake, max x16")
    p.add_argument("--interval", type=float, default=5, help="seconds between scans")
    p.add_argument("--source-timeout", type=float, default=60, help="seconds before a --source run is cut off")
    p.add_argument("--source-failures", type=int, default=3,
                   help="consecutive source timeouts or exit-75 failures before one source-failing wake")
    p.add_argument("--source", action="append", default=[],
                   help="one-shot event command (crew poll --once); each stdout line is a poll wake")
    p.add_argument("--no-nudge", action="store_true", help="do not type the wake line into an idle coordinator")
    p.add_argument("--idle", type=float, default=30, help="seconds with no coordinator output that count as idle")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    """Zero-token watcher: block on status files, liveness, owner-ask deadlines, one-shot --source commands and
    queue growth; queue wakes, then exit."""
    values, session, state = profile(args)
    wake = os.path.join(state, "wake")
    os.makedirs(wake, exist_ok=True)
    path, pidfile = os.path.join(wake, "watch-state.json"), os.path.join(wake, "watcher.pid")
    if other := armed(pidfile):  # leave its PID file and state alone (#591)
        print("crew: a watcher is already armed (pid %d)" % other)
        return 1
    if ownership_module.status(values) == "lost":  # prompt stop: never re-armed once ownership moved away
        print("crew: ownership: lost; watcher not armed (run crew down, then crew handoff stopped)")
        return 1
    seen = {"offsets": {}, "keys": {}, "idle": 0, "queue": None}
    if os.path.exists(path):
        with open(path) as f:
            seen.update(json.load(f))

    def save(data):
        with open(path + ".tmp", "w") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)

    held, sleeping = [], False  # a signal is held while a child may be starting, so none is orphaned (#272)

    def stop(signum, _frame):
        held.append(signum)
        if sleeping or len(held) > 1:  # between scans, or a second signal: exit at once
            raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):  # a killed watcher removes its PID file, saves offsets
        signal.signal(sig, stop)
    busy = any(runs(state)) or any(commands()["lead"].pending(state, n) for n, _ in commands()["lead"].records(state))
    seen["idle"] = 0 if busy else seen["idle"]
    deadline = time.monotonic() + min(args.backstop * 2 ** seen["idle"], args.backstop * 16)  # backs off when idle
    code = code_sig()
    try:
        with open(pidfile, "w") as f:
            f.write("%d\n" % os.getpid())
        while True:
            triage_tick(values, state, time.time(), args.project, args.org_profile)
            docs_tick(values, state, time.time(), args.project, args.org_profile)
            found = commands()["notify"].tick(values, state, time.time())
            found = [w for w in found if seen["keys"].get("notify-digest") != [w["entry"], w["slot"]]]
            for w in found:
                seen["keys"]["notify-digest"] = [w["entry"], w["slot"]]
            for cmd in args.source:  # one-shot commands, each cut off at the source timeout so none wedges the loop
                before = queue_sig(wake)
                try:
                    r = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=args.source_timeout)
                except subprocess.TimeoutExpired:
                    found += source_failure(wake, seen, cmd, "timed out after %gs" % args.source_timeout,
                                            args.source_failures)
                    continue
                out = r.stdout
                if r.returncode == os.EX_TEMPFAIL:
                    error = (out.strip().splitlines() or ["exit %d" % r.returncode])[-1]
                    found += source_failure(wake, seen, cmd, error, args.source_failures)
                    continue
                seen.get("source_failures", {}).pop(cmd, None)
                if queue_sig(wake) == before:  # a source that queues its own records (crew poll) is not re-queued
                    found += [{"reason": "poll", "event": line} for line in out.splitlines() if line.strip()]
            trial = json.loads(json.dumps(seen))  # committed only once its wakes are queued
            wakes = scan(state, session, time.time(), args.stale, trial, values["runtime.options.idle_builder_ttl"],
                         values["runtime.options.stuck_after"]) + found
            others = queued(state, wake, trial)
            if code_sig() != code and not held:  # before route resolves the live profile with old code (#702)
                reexec()  # trial is not committed, so the new image finds this scan's status lines and records again
            if not wakes and not others and time.monotonic() > deadline:
                trial["idle"] += 0 if busy else 1
                wakes = [{"reason": "backstop", "event": "due (%s in flight)" % ("work" if busy else "nothing")}]
            if wakes:
                with queue_lock(state), open(os.path.join(wake, "queue.jsonl"), "a") as f:
                    for w in wakes:
                        f.write(json.dumps(dict(w, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
                    f.flush()
                    trial["queue"] = queue_sig(wake)
            save(trial)
            seen = trial
            if wakes or others:
                candidates = [{k: v for k, v in w.items() if k not in ("at", "route_error")}
                              for w in wakes + others]
                commands()["route"].route_queue(argparse.Namespace(
                    project=args.project, org_profile=args.org_profile, timeout=15))
                trial["queue"] = queue_sig(wake)
                save(trial)
                with queue_lock(state):
                    queue = os.path.join(wake, "queue.jsonl")
                    remaining = []
                    if os.path.exists(queue):
                        with open(queue) as f:
                            remaining = [json.loads(line) for line in f if line.strip()]
                wakes = []
                for w in reversed(remaining):
                    key = {k: v for k, v in w.items() if k not in ("at", "route_error")}
                    if key in candidates:
                        wakes.insert(0, w)
                        candidates.remove(key)
                others = []
                if wakes:
                    break
            sleeping = True
            if held:
                raise SystemExit(128 + held[0])
            time.sleep(pause(state, time.time(), args.interval))
            sleeping = False
        if held:  # held during the last scan, whose wakes are queued
            raise SystemExit(128 + held[0])
        p = None if args.no_nudge else tmux.pane(session, 0)
        if p and foreground_matches(ENGINE_CMD.values(), {p["command"], *tmux.foreground(p["tty"])}) and \
                time.time() - float(p["activity"]) > args.idle:
            if dialog(session, 0):  # never type into a prompt: its Enter could approve a command (#315)
                w = {"reason": "dialog", "window": dict(tmux.list_windows(session)).get(0, "0"),
                     "liveness": "ambiguous", "silent": int(time.time() - float(p["activity"])), "action": "escalate"}
                with queue_lock(state), open(os.path.join(wake, "queue.jsonl"), "a") as f:
                    f.write(json.dumps(dict(w, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
                    f.flush()
                    seen["queue"] = queue_sig(wake)
                wakes.append(w)
            else:
                if tmux.name == "herdr":
                    if error := commands()["send"].nudge(session, 0, "wake: watcher"):
                        print("crew: coordinator nudge not submitted: " + error)
                else:
                    tmux.send_keys(session, 0, "wake: watcher")  # the Codex-recipe path, for when exit alone wakes nobody
        wakes += others
        print(reason(wakes[0]) + (" (+%d more in wake/queue.jsonl)" % (len(wakes) - 1) if len(wakes) > 1 else ""))
        if (line := commands()["schedule"].read(commands()["schedule"].summary, state)) not in (None, "unknown"):
            print(line)
        return 0
    finally:
        save(seen)
        with contextlib.suppress(OSError, ValueError):
            with open(pidfile) as f:
                mine = int(f.read().strip()) == os.getpid()
            if mine:  # never another watcher's (#591)
                os.remove(pidfile)
