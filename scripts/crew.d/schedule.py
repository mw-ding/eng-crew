"""Crew scheduler inputs (docs/scheduling.md#inputs): one JSON read of every input, `unknown` where a read fails,
the ranking over it (docs/scheduling.md#priority) and the crew-wide target T (docs/scheduling.md#target), kept in
schedule/target.json, and the decision a lead asks for (docs/scheduling.md#model): admit, defer or hold, with
caller-only reservations in schedule/reservations.json and the log in schedule/decisions-<yyyymmdd>.jsonl.

Usage: crew schedule snapshot|decide|release [--pool builder|reviewer] [REF...] --project FILE [--org-profile FILE]
"""
import datetime
import fcntl
import json
import os
import platform
import re
import subprocess
from crew_shared import BANDS, commands, idle_builder, open_trains, pool_cap, probe, profile, runs, tmux

UNKNOWN = "unknown"
MAC_PRESSURE = {1: "normal", 2: "warn", 4: "critical"}
CLASSES = {("reviewer", "recheck"): 2, ("builder", "merge-up"): 3, ("reviewer", "validate"): 4, ("reviewer", "review"): 5,
           ("builder", "fix"): 6, ("builder", "ci-red"): 6, ("builder", "build"): 7}
TARGET_OPTIONS = {"load_high": 6.0, "load_low": 4.0, "error_high": 3, "schedule_interval": 120, "schedule_ramp": 2}
PSI_HIGH, PSI_LOW = 10.0, 1.0  # Linux memory `some avg10`: high at, low below
RESERVATION_TTL = 600  # seconds a grant counts as busy before its run record appears
LEAD_DOWN = ("dead", "missing", "ambiguous", UNKNOWN)
DEPENDS = re.compile(r"^#*\s*Depends on\b(.*?)(?=^#+\s|\Z)", re.I | re.M | re.S)


def read(fn, *args):
    try:
        return fn(*args)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        return UNKNOWN


def jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def demand(state, values, role):
    """Pending lead inbox ids by kind; reviewer `work` ids carry the event they name, builders add spawn-queue.jsonl."""
    items = []
    for m in commands()["lead"].pending(state, values["identities.%s.name" % role].lower() + "-lead"):
        item = dict(id=m["id"], kind=m["kind"], refs=m["refs"], ts=m.get("ts"))
        if role == "reviewer" and m["kind"] == "work":
            with open(m["refs"][0]) as f:
                item["event"] = json.load(f)
        items.append(item)
    if role == "builder":
        items += [dict(kind=e["pass"], issue=e["issue"], pr=e["pr"], ts=e["queued"], queued=True)
                  for e in jsonl(os.path.join(state, "spawn-queue.jsonl")) if e["role"] == "builder"]
    return items


def workers(session, state):
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    found = []
    for name, rec in runs(state):
        live = read(probe, session, name, rec, windows)
        idle = rec["role"] == "builder" and read(idle_builder, state, name) not in (None, UNKNOWN)
        found.append({"name": name, "role": rec["role"], "item": rec["item"], "pass": rec["pass"], "pr": rec.get("pr"),
                      "start": rec.get("start"),
                      "state": "idle" if idle else "exited" if live in ("dead", "missing") else "busy"})
    return found


def lands(state, values):
    """Outstanding land messages in the synthesizer inbox and its saved queue, read without synthesizer_work's write."""
    name = values["identities.synthesizer.name"].lower()
    status = os.path.join(state, "status", name + ".status")
    lines = open(status).read().splitlines() if os.path.exists(status) else []
    saved = jsonl(os.path.join(state, "inbox", "synthesizer-pending.jsonl"))
    found = []
    for m in {m["id"]: m for m in saved + jsonl(os.path.join(state, "inbox", name + ".jsonl"))}.values():
        ack = next((i for i, line in enumerate(lines) if line == "ack: " + m["id"]), len(lines))
        if m["kind"] == "land" and not any(
                line.split()[1:len(m["refs"][:2]) + 1] == m["refs"][:2] if line.startswith("done: ") else
                line.startswith("blocked: ") and line.split()[1:2] == m["refs"][:1] for line in lines[ack + 1:]):
            found.append(dict(id=m["id"], refs=m["refs"], ts=m.get("ts")))
    return found


def tracker(values):
    """Open milestones and open issues with their milestone and `Depends on #n` refs (critical-path input)."""
    repo = "%s/%s" % (values["repo.owner"], values["repo.name"])
    gh = commands()["route"].gh
    milestones = json.loads(subprocess.run(["gh", "api", "repos/%s/milestones?state=open&per_page=100" % repo],
                                           capture_output=True, text=True, check=True).stdout)
    issues = gh("issue", "list", "-R", repo, "--state", "open", "--limit", "1000", "--json", "number,milestone,body")
    return dict(milestones=[dict(number=m["number"], title=m["title"]) for m in milestones],
                max_active=values.get("runtime.options.max_active_milestones", 1),
                issues=[dict(number=i["number"], milestone=(i["milestone"] or {}).get("title"),
                             depends=sorted({int(n) for block in DEPENDS.findall(i["body"] or "")
                                             for n in re.findall(r"#(\d+)", block)}))
                        for i in issues])


def memory():
    if platform.system() == "Darwin":
        out = subprocess.run(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
                             capture_output=True, text=True, check=True).stdout
        return dict(os="darwin", level=MAC_PRESSURE[int(out)])
    with open("/proc/pressure/memory") as f:
        some = next(line for line in f if line.startswith("some "))
    return dict(os="linux", some_avg10=float(re.search(r"avg10=([\d.]+)", some)[1]))


def errors(state, now):
    """Gateway errors (HTTP 429/5xx, rate limits) recorded in the last 10 minutes."""
    since = now - datetime.timedelta(minutes=10)
    return sum(datetime.datetime.fromisoformat(e["ts"].replace("Z", "+00:00")) >= since
               for e in jsonl(os.path.join(state, "schedule", "errors.jsonl")))


def cap(values, state, role):
    lo, hi = BANDS[role]
    return min(pool_cap(values, role, state), hi - lo + 1)


def snapshot(args):
    values, session, state = profile(args)
    now = datetime.datetime.now(datetime.timezone.utc)
    reservations = os.path.join(state, "schedule", "reservations.json")
    cpus = os.cpu_count()
    return dict(
        ts=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        demand={role: read(demand, state, values, role) for role in ("builder", "reviewer")},
        workers=read(workers, session, state),
        reservations=read(lambda: json.load(open(reservations)) if os.path.exists(reservations) else []),
        lands=read(lands, state, values),
        trains=read(lambda: [os.path.basename(p) for p in open_trains(state)]),
        tracker=read(tracker, values),
        cpus=cpus or UNKNOWN,
        load=read(lambda: round(os.getloadavg()[0] / cpus, 3)),
        memory=read(memory),
        suites=read(commands()["lead"].suites, values, state),
        errors=read(errors, state, now),
        caps={role: read(cap, values, state, role) for role in ("builder", "reviewer")})


def critical_path(issues):
    """Open issues waiting on each issue, directly or transitively, from their `Depends on` refs."""
    waiters = {}
    for i in issues:
        for n in i["depends"]:
            waiters.setdefault(n, set()).add(i["number"])
    counts = {}
    for n in waiters:
        seen, todo = set(), list(waiters[n])
        while todo:
            w = todo.pop()
            if w not in seen:
                seen.add(w)
                todo += waiters.get(w, ())
        counts[n] = len(seen - {n})
    return counts


def rank(snap, red_fixes=()):
    """Both pools' demand in one list (docs/scheduling.md#priority): class, then milestone order, critical path
    (more waiters first) and age (oldest first). `red_fixes` are the issue or PR numbers whose builds or fixes repair
    a red default branch (class 1). Kinds outside the eight classes and pools with unknown demand are left out."""
    tracker = snap["tracker"] if snap["tracker"] != UNKNOWN else dict(milestones=[], max_active=1, issues=[])
    titles = [m["title"] for m in tracker["milestones"]]
    latest = max(min(tracker["max_active"], len(titles)) - 1, 0)
    milestone = {i["number"]: i["milestone"] for i in tracker["issues"]}
    waiting = critical_path(tracker["issues"])
    issue_of = {w["pr"]: int(re.search(r"issue #(\d+)", w["item"])[1]) for w in snap["workers"] if w.get("pr")} \
        if snap["workers"] != UNKNOWN else {}
    ranked = []
    for pool in ("builder", "reviewer"):
        if snap["demand"][pool] == UNKNOWN:
            continue
        for d in snap["demand"][pool]:
            cls = CLASSES.get((pool, d["kind"]))
            if not cls:
                continue
            build = d["kind"] == "build"
            if d.get("queued"):
                n = d["issue"] if build else d["pr"]
                issue = d["issue"] or issue_of.get(n)
            else:
                n = int(d["refs"][0].lstrip("#"))
                issue = n if build else issue_of.get(n)
            order = titles.index(milestone.get(issue)) if milestone.get(issue) in titles else latest
            if pool == "builder" and n in red_fixes and d["kind"] in ("build", "fix", "ci-red"):
                cls = 1
            elif build:
                cls = 7 if order == 0 else 8
            ranked.append(dict(d, pool=pool, ref="#%d" % n, issue=issue, milestone_order=order,
                               waiting=waiting.get(issue, 0), **{"class": cls}))
    return sorted(ranked, key=lambda r: (r["class"], r["milestone_order"], -r["waiting"], r.get("ts") or "~"))


def stamp(when):
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(ts):
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def target_options(values):
    return {k: values.get("runtime.options." + k, v) for k, v in TARGET_OPTIONS.items()}


def level(value, high, low):
    return UNKNOWN if value == UNKNOWN else "high" if value >= high else "low" if value < low else "between"


def signals(snap, opts):
    """Each machine signal of docs/scheduling.md#target as high, low, between or unknown."""
    mem = snap["memory"]
    if mem != UNKNOWN and "level" in mem:
        memory = "low" if mem["level"] == "normal" else "high"
    else:
        memory = level(UNKNOWN if mem == UNKNOWN else mem["some_avg10"], PSI_HIGH, PSI_LOW)
    return dict(load=level(snap["load"], opts["load_high"], opts["load_low"]), memory=memory,
                errors=level(snap["errors"], opts["error_high"], 1))


def target(snap, opts, doc, now):
    """The next schedule/target.json document from the previous one (None on the first run). T starts at the busy
    count, stays within [1, sum of pool caps] and moves by one at most once per schedule_interval: down when any
    signal is high, up when every signal is low and demand waits. Unknown signals, caps or workers hold T."""
    busy = None if snap["workers"] == UNKNOWN else sum(w["state"] == "busy" for w in snap["workers"])
    ceiling = None if UNKNOWN in snap["caps"].values() else sum(snap["caps"].values())
    clamp = lambda t: max(1, t if ceiling is None else min(t, ceiling))
    if doc is None:
        return dict(target=clamp(busy or 1), changed=stamp(now), starts=[])
    t, changed = clamp(doc["target"]), doc["changed"]
    sig = signals(snap, opts)
    due = (now - parse(changed)).total_seconds() >= opts["schedule_interval"]
    if due and UNKNOWN not in sig.values() and None not in (busy, ceiling):
        if "high" in sig.values():
            nxt = max(1, min(t, busy) - 1)
        elif set(sig.values()) == {"low"} and rank(snap):
            nxt = clamp(t + 1)
        else:
            nxt = t
        if nxt != t:
            t, changed = nxt, stamp(now)
    since = now - datetime.timedelta(seconds=opts["schedule_interval"])
    return dict(target=t, changed=changed, starts=[s for s in doc.get("starts", []) if parse(s) > since])


def ramp_left(doc, opts):
    """Starts the ramp limit still allows in the current schedule_interval (`starts` is pruned by target())."""
    return max(0, opts["schedule_ramp"] - len(doc["starts"]))


def update_target(state, snap, values, now):
    """Read, advance and write schedule/target.json; return the new document."""
    path = os.path.join(state, "schedule", "target.json")
    doc = None
    if os.path.exists(path):
        with open(path) as f:
            doc = json.load(f)
    doc = target(snap, target_options(values), doc, now)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
    os.replace(path + ".tmp", path)
    return doc


def live_reservations(reservations, workers, now):
    """Reservations younger than RESERVATION_TTL whose ref has no run record yet: a busy worker of the pool on the
    ref, or one started since the grant, ends a reservation."""
    def started(r):
        return any(w["role"] == r["pool"] and int(r["ref"][1:]) in {w.get("pr"), *map(int, re.findall(r"#(\d+)", w["item"]))}
                   and (w["state"] == "busy" or (w.get("start") or "") >= r["time"]) for w in workers)
    return [r for r in reservations if (now - parse(r["time"])).total_seconds() < RESERVATION_TTL and not started(r)]


def ceiling_hit(snap, values):
    """The optional hard ceiling a start would exceed (an unobserved input counts as exceeded), else None."""
    max_suites, max_load = values.get("runtime.options.max_suites"), values.get("runtime.options.max_load")
    if max_suites is not None and (snap["suites"] == UNKNOWN or snap["suites"] >= max_suites):
        return "max_suites"
    if max_load is not None and (UNKNOWN in (snap["load"], snap["cpus"]) or snap["load"] * snap["cpus"] >= max_load):
        return "max_load"
    return None


def walk(pool, ranked, snap, reserved, target_doc, opts, leads, ceiling=None):
    """Walk the crew's ranked demand (docs/scheduling.md#model). The caller's items are admitted (already reserved
    ones again, as `reserved`) or deferred with the first failed condition; the other pool's would-be grants are
    holds for this walk only, dropped as `lead-down` when that pool's lead is down. A pool with no busy worker or
    reservation may admit its top-ranked item past the target, ramp and ceiling (its floor)."""
    used = {p: sum(w["role"] == p and w["state"] == "busy" for w in snap["workers"]) +
            sum(r["pool"] == p for r in reserved) for p in ("builder", "reviewer")}
    floor = {p: used[p] == 0 for p in used}
    held = {(r["pool"], r["ref"]) for r in reserved}
    total, starts, actions = sum(used.values()), len(target_doc["starts"]), []
    for item in ranked:
        p, act = item["pool"], dict(pool=item["pool"], ref=item["ref"], kind=item["kind"], **{"class": item["class"]})
        if (p, item["ref"]) in held:
            if p == pool:
                actions.append(dict(act, action="admit", reasons=["reserved"]))
            continue
        if p != pool and leads.get(p, UNKNOWN) in LEAD_DOWN:
            actions.append(dict(act, action="drop", reasons=["lead-down"]))
            continue
        fails = [why for why, ok in (("cap", used[p] < snap["caps"][p]), ("target", total < target_doc["target"]),
                                     ("ramp", starts < opts["schedule_ramp"]), (ceiling, ceiling is None)) if not ok]
        if fails and not (floor[p] and fails[0] != "cap"):
            if p == pool:
                actions.append(dict(act, action="defer", reasons=fails[:1]))
            floor[p] = False
            continue
        actions.append(dict(act, action="admit" if p == pool else "hold", reasons=["floor"] if fails else []))
        used[p], total, starts, floor[p] = used[p] + 1, total + 1, starts + 1, False
    return actions


def save_json(path, doc):
    with open(path + ".tmp", "w") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
    os.replace(path + ".tmp", path)


def log(state, pool, snap, target_doc, actions, now):
    """Append the snapshot line and each action to the UTC day's decisions file (7 days kept); a defer repeated with
    the same reasons as the caller's previous decision is not written again."""
    sched = os.path.join(state, "schedule")
    keep = (now - datetime.timedelta(days=7)).strftime("decisions-%Y%m%d.jsonl")
    for name in os.listdir(sched):
        if name.startswith("decisions-") and name < keep:
            os.remove(os.path.join(sched, name))
    last_path = os.path.join(sched, "deferred.json")
    last = json.load(open(last_path)) if os.path.exists(last_path) else {}
    caps = snap["caps"]
    lines = [dict(action="snapshot", pool=pool, ts=stamp(now), snapshot=snap, target=target_doc["target"], caps=caps,
                  ceiling=UNKNOWN if UNKNOWN in caps.values() else sum(caps.values()))]
    lines += [a for a in actions if a["action"] != "defer" or last.get(pool, {}).get(a["ref"]) != a["reasons"]]
    last[pool] = {a["ref"]: a["reasons"] for a in actions if a["action"] == "defer"}
    save_json(last_path, last)
    with open(os.path.join(sched, now.strftime("decisions-%Y%m%d.jsonl")), "a") as f:
        f.writelines(json.dumps(line, sort_keys=True) + "\n" for line in lines)


def lead_states(session, state, values):
    lead = commands()["lead"]
    recs, windows = dict(lead.records(state)), dict((n, i) for i, n in tmux.list_windows(session))
    names = {p: values["identities.%s.name" % p].lower() + "-lead" for p in ("builder", "reviewer")}
    return {p: read(probe, session, n, recs[n], windows) if n in recs else "missing" for p, n in names.items()}


def decide(args):
    """One decision for args.pool under schedule/lock; returns the JSON printed to the lead."""
    values, session, state = profile(args)
    sched = os.path.join(state, "schedule")
    os.makedirs(sched, exist_ok=True)
    with open(os.path.join(sched, "lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        now = datetime.datetime.now(datetime.timezone.utc)
        snap = snapshot(args)
        doc = update_target(state, snap, values, now)
        workers = [] if snap["workers"] == UNKNOWN else snap["workers"]
        reserved = live_reservations(snap["reservations"] if isinstance(snap["reservations"], list) else [], workers, now)
        unreadable = "demand" if snap["demand"][args.pool] == UNKNOWN else "caps" if UNKNOWN in snap["caps"].values() \
            else "workers" if snap["workers"] == UNKNOWN else None
        if unreadable:
            actions = [dict(pool=args.pool, ref=None, action="defer", reasons=[unreadable + "-unreadable"])]
        else:
            leads = read(lead_states, session, state, values)
            actions = walk(args.pool, rank(snap), snap, reserved, doc, target_options(values),
                           {} if leads == UNKNOWN else leads, ceiling_hit(snap, values))
        grants = [a for a in actions if a["action"] == "admit" and a["reasons"] != ["reserved"]]
        save_json(os.path.join(sched, "reservations.json"),
                  reserved + [dict(ref=a["ref"], pool=args.pool, time=stamp(now)) for a in grants])
        if grants:
            save_json(os.path.join(sched, "target.json"), dict(doc, starts=doc["starts"] + [stamp(now)] * len(grants)))
        log(state, args.pool, snap, doc, actions, now)
    other = "reviewer" if args.pool == "builder" else "builder"
    if any(a["action"] == "hold" for a in actions):
        try:  # the owning lead's backstop wake, so the held item is claimed before the next tick
            commands()["lead"].retry_pending(args, values["identities.%s.name" % other].lower() + "-lead")
        except (RuntimeError, OSError):
            pass
    return dict(pool=args.pool, target=doc["target"], admit=[a for a in actions if a["action"] == "admit"],
                deferred=[a for a in actions if a["action"] == "defer"], holds=[a for a in actions if a["action"] == "hold"])


def release(args):
    """Drop the caller's reservations for REFs (after a spawn failure)."""
    _, _, state = profile(args)
    sched = os.path.join(state, "schedule")
    os.makedirs(sched, exist_ok=True)
    path = os.path.join(sched, "reservations.json")
    with open(os.path.join(sched, "lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        kept = [r for r in (json.load(open(path)) if os.path.exists(path) else [])
                if not (r["pool"] == args.pool and r["ref"] in args.refs)]
        save_json(path, kept)
    return dict(pool=args.pool, released=args.refs)


def register(sub):
    p = sub.add_parser("schedule")
    p.add_argument("action", choices=["snapshot", "decide", "release"])
    p.add_argument("refs", nargs="*")
    p.add_argument("--pool", choices=["builder", "reviewer"])
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    if args.action != "snapshot" and not args.pool:
        print("crew: schedule %s requires --pool" % args.action)
        return 2
    out = snapshot(args) if args.action == "snapshot" else decide(args) if args.action == "decide" else release(args)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0
