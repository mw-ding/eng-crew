"""`crew watch` is the zero-token watcher that queues wakes in `wake/queue.jsonl` (one-shot `--source` commands cut off
at `--source-timeout`, default the scan interval but at least 5 s, queue growth from another poller, and an `ask:`
wake at each open owner ask's deadline in `asks/<n>.json`; a signal during a scan is held until its children exit)
and retries pending lead admission every 60 s, then exits with one reason line; runs without `start` skip liveness
wakes while their record mtime is less than 60 s
old. Verified panes with a live tool session or recent output get a supervisor heartbeat instead of a stale wake.
Each live run's screen is matched against its harness adapter's transient-error text; each new match is a line in
`schedule/errors.jsonl` (docs/scheduling.md#inputs).
Its `wake: watcher` line is never typed into a window 0 showing a dialog, which gets
a `dialog` wake instead (#315). Before a coordinator wake, `crew route` consumes mechanical records;
the watcher continues scanning when none of the new records need judgement (#434).

Usage: crew watch --project FILE [--org-profile FILE]
"""
import argparse
import contextlib
import datetime
import json
import os
import shlex
import signal
import subprocess
import time
from crew_shared import commands, dialog, ENGINE_CMD, foreground_matches, finished, gateway_error, heartbeat, idle_builder, probe, profile, queue_lock, remember_pr, runs, TRANSIENT, tmux, transient_lines


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


def scan(state, session, now, stale, seen, idle_ttl=1800):
    """Wake records: new status lines, runs dead, missing or silent past stale, and owner asks past their deadline;
    each fires once per key."""
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
                gateway_error(state, name, line, now)
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
    for name, _ in commands()["lead"].records(state):
        retries = seen.setdefault("lead_retries", {})
        if not commands()["lead"].pending(state, name):
            retries.pop(name, None)
        elif now >= retries.setdefault(name, now + 60):
            wakes.append({"reason": "lead-backstop", "window": name, "event": "admission retry"})
            retries[name] = now + 60
    return wakes


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


def register(sub):
    p = sub.add_parser("watch")
    p.add_argument("--stale", type=float, default=900, help="seconds without status progress before a stale wake")
    p.add_argument("--backstop", type=float, default=1800, help="seconds to a backstop wake; x2 per idle wake, max x16")
    p.add_argument("--interval", type=float, default=5, help="seconds between scans")
    p.add_argument("--source-timeout", type=float,
                   help="seconds before a --source run is cut off (default: --interval, at least 5)")
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
    limit = max(args.interval, 5) if args.source_timeout is None else args.source_timeout  # floor: #272
    try:
        with open(pidfile, "w") as f:
            f.write("%d\n" % os.getpid())
        while True:
            found = commands()["notify"].tick(values, state, time.time())
            found = [w for w in found if seen["keys"].get("notify-digest") != [w["entry"], w["slot"]]]
            for w in found:
                seen["keys"]["notify-digest"] = [w["entry"], w["slot"]]
            for cmd in args.source:  # one-shot commands, each cut off at the source timeout so none wedges the loop
                before = queue_sig(wake)
                try:
                    out = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=limit).stdout
                except subprocess.TimeoutExpired:
                    found.append({"reason": "source-timeout", "event": cmd})
                    continue
                if queue_sig(wake) == before:  # a source that queues its own records (crew poll) is not re-queued
                    found += [{"reason": "poll", "event": line} for line in out.splitlines() if line.strip()]
            trial = json.loads(json.dumps(seen))  # committed only once its wakes are queued
            wakes = scan(state, session, time.time(), args.stale, trial, values["runtime.options.idle_builder_ttl"]) + found
            others = queued(state, wake, trial)
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
        return 0
    finally:
        save(seen)
        with contextlib.suppress(OSError, ValueError):
            with open(pidfile) as f:
                mine = int(f.read().strip()) == os.getpid()
            if mine:  # never another watcher's (#591)
                os.remove(pidfile)
