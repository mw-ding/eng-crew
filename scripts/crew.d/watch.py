"""crew watch --project FILE [--org-profile FILE]"""
import contextlib
import json
import os
import shlex
import signal
import subprocess
import time
from crew_shared import dialog, ENGINE_CMD, finished, heartbeat, probe, profile, queue_lock, runs, tmux


def scan(state, session, now, stale, seen):
    """Wake records: new status lines, and runs dead, missing or silent past stale; each fires once per key."""
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    wakes = []
    for name, rec in runs(state):
        status = os.path.join(state, "status", name + ".status")
        size, off = os.path.getsize(status) if os.path.exists(status) else 0, seen["offsets"].get(name, 0)
        if size and size != off:
            with open(status) as f:
                f.seek(off if size > off else 0)  # shorter than seen: a new run's file
                wakes += [{"reason": "status", "window": name, "line": s} for s in f.read().splitlines() if s.strip()]
        seen["offsets"][name] = size
        last, beat = heartbeat(state, name)
        cls = probe(session, name, rec, windows)
        if cls == "ambiguous" and not finished(rec, last) and dialog(session, rec["index"]):
            if seen["keys"].get(name) != "dialog %s" % beat:  # wakes on the next scan, never after --stale (#234 N3)
                seen["keys"][name] = "dialog %s" % beat
                wakes.append({"reason": "dialog", "window": name, "liveness": cls, "silent": int(now - beat),
                              "action": "escalate"})
            continue
        if finished(rec, last) or (cls in ("alive", "ambiguous") and (last.startswith("done:") or now - beat <= stale)):
            continue  # a live builder after done: waits for its inbox; a dead one is restartable (#139 F4)
        key = "stale %s" % beat  # not the class: an ambiguous -> alive flip is the same silence (#234 N4)
        if seen["keys"].get(name) != key:
            seen["keys"][name] = key
            wakes.append({"reason": "stale", "window": name, "liveness": cls, "silent": int(now - beat),
                          "action": "restart" if cls in ("dead", "missing") and not rec.get("restarts") else "escalate"})
    return wakes


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
    p.add_argument("--interval", type=float, default=5, help="seconds between scans; also each --source timeout")
    p.add_argument("--source", action="append", default=[],
                   help="one-shot event command (crew poll --once); each stdout line is a poll wake")
    p.add_argument("--no-nudge", action="store_true", help="do not type the wake line into an idle coordinator")
    p.add_argument("--idle", type=float, default=30, help="seconds with no coordinator output that count as idle")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    """Zero-token watcher: block on status files, liveness, one-shot --source commands and queue growth; queue
    wakes, then exit."""
    _, session, state = profile(args)
    wake = os.path.join(state, "wake")
    os.makedirs(wake, exist_ok=True)
    path, pidfile = os.path.join(wake, "watch-state.json"), os.path.join(wake, "watcher.pid")
    seen = {"offsets": {}, "keys": {}, "idle": 0, "queue": None}
    if os.path.exists(path):
        with open(path) as f:
            seen.update(json.load(f))

    def save(data):
        with open(path + ".tmp", "w") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)

    def stop(signum, _frame):
        raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):  # a killed watcher removes its PID file, saves offsets
        signal.signal(sig, stop)
    busy = any(runs(state))
    seen["idle"] = 0 if busy else seen["idle"]
    deadline = time.monotonic() + min(args.backstop * 2 ** seen["idle"], args.backstop * 16)  # backs off when idle
    try:
        with open(pidfile, "w") as f:
            f.write("%d\n" % os.getpid())
        while True:
            found = []
            for cmd in args.source:  # one-shot commands, each cut off at one scan interval so none wedges the loop
                before = queue_sig(wake)
                try:
                    out = subprocess.run(shlex.split(cmd), capture_output=True, text=True,
                                         timeout=args.interval).stdout
                except subprocess.TimeoutExpired:
                    found.append({"reason": "source-timeout", "event": cmd})
                    continue
                if queue_sig(wake) == before:  # a source that queues its own records (crew poll) is not re-queued
                    found += [{"reason": "poll", "event": line} for line in out.splitlines() if line.strip()]
            trial = json.loads(json.dumps(seen))  # committed only once its wakes are queued
            wakes = scan(state, session, time.time(), args.stale, trial) + found
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
                break
            time.sleep(args.interval)
        p = None if args.no_nudge else tmux.pane(session, 0)
        if p and {p["command"], *tmux.foreground(p["tty"])} & set(ENGINE_CMD.values()) and \
                time.time() - float(p["activity"]) > args.idle:
            tmux.send_keys(session, 0, "wake: watcher")  # the Codex-recipe path, for when exit alone wakes nobody
        wakes += others
        print(reason(wakes[0]) + (" (+%d more in wake/queue.jsonl)" % (len(wakes) - 1) if len(wakes) > 1 else ""))
        return 0
    finally:
        save(seen)
        with contextlib.suppress(FileNotFoundError):
            os.remove(pidfile)
