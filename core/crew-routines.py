#!/usr/bin/env python3
"""Role routines (#1247, docs/routines.md): each role's recurring jobs, `routines/<routine>.toml` in its role package.

Usage: crew-routines.py ROLES_DIR [--actions NAME,...] [--events TYPE,...]
Validates every ROLES_DIR/<team>/<role>/routines/<routine>.toml: schedule (an interval with optional jitter and
profile key, or a five-field cron in the owner's timezone), skill, generic actions, inputs, outputs, deadline and
miss policy. With --actions or --events, also checks the named actions and `due_on` events against that vocabulary
(check-repo passes the actions contract's). Prints `file:key: reason` per problem; exit 1 if any, else 0.
Library: load() reads the routines, interval() resolves an interval against the profile, due() decides a slot.
Python 3.11+ stdlib only.
"""
import argparse
import datetime
import os
import re
import sys
import tomllib
import zoneinfo

ID = re.compile(r"[a-z][a-z0-9-]*")
DURATION = re.compile(r"(\d+)([smhd])")
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
KEY_UNITS = {"_seconds": 1, "_minutes": 60, "_hours": 3600, "_days": 86400}  # an every_key's unit is its suffix
MISS = ("skip", "catch-up-once", "escalate")
CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))  # minute hour day-of-month month day-of-week (0 = Sunday)
KEYS = {"description": str, "skill": str, "actions": list, "schedule": dict, "inputs": list, "outputs": list,
        "deadline": str, "on_miss": str, "retry": str, "due_on": list, "enabled": bool, "enabled_key": str,
        "idle_backoff": int}
REQUIRED = ("description", "skill", "actions", "schedule", "inputs", "outputs", "deadline", "on_miss")
SCHEDULE_KEYS = {"every": str, "every_key": str, "jitter": str, "cron": str, "timezone": str}


def seconds(text):
    """A duration such as 90s, 10m, 6h or 7d in seconds; None when malformed or zero."""
    m = DURATION.fullmatch(text) if isinstance(text, str) else None
    return int(m[1]) * UNITS[m[2]] if m and int(m[1]) else None


def cron_fields(text):
    """The five cron fields as sets of allowed values; raises ValueError naming the bad field."""
    parts = text.split() if isinstance(text, str) else []
    if len(parts) != 5:
        raise ValueError("expected five fields: minute hour day-of-month month day-of-week")
    fields = []
    for part, (lo, hi) in zip(parts, CRON_RANGES):
        allowed = set()
        for item in part.split(","):
            m = re.fullmatch(r"(\*|(\d+)(?:-(\d+))?)(?:/(\d+))?", item)
            if not m:
                raise ValueError("bad field %r" % part)
            a, b = (lo, hi) if m[1] == "*" else (int(m[2]), int(m[3] or m[2]))
            step = int(m[4] or 1)
            if not lo <= a <= b <= hi or step < 1 or m[4] and m[1] != "*" and not m[3]:
                raise ValueError("field %r outside %d-%d" % (part, lo, hi))
            allowed.update(range(a, b + 1, step))
        fields.append(allowed)
    return fields


def cron_match(fields, t):
    minute, hour, dom, month, dow = fields
    return t.minute in minute and t.hour in hour and t.day in dom and t.month in month and (t.weekday() + 1) % 7 in dow


def cron_prev(fields, t, limit=400):
    """The latest whole minute at or before the aware datetime t that matches, searching back `limit` days."""
    t, stop = t.replace(second=0, microsecond=0), t - datetime.timedelta(days=limit)
    while t > stop:
        if t.month not in fields[3] or t.day not in fields[2] or (t.weekday() + 1) % 7 not in fields[4]:
            t = t.replace(hour=23, minute=59) - datetime.timedelta(days=1)
        elif t.hour not in fields[1]:
            t = t.replace(minute=59) - datetime.timedelta(hours=1)
        elif t.minute not in fields[0]:
            t -= datetime.timedelta(minutes=1)
        else:
            return t
    return None


def check(rel, data, actions=None, events=None, skills=None):
    """Problems (rel, key, reason) with one routine's parsed table. actions/events: the vocabulary, or None to skip;
    skills: the role package's skill names, or None when it has no skills/ folder."""
    out = []

    def err(key, reason):
        out.append((rel, key, reason))

    for key, value in data.items():
        if key not in KEYS:
            err(key, "unknown key")
        elif type(value) is not KEYS[key]:
            err(key, "expected %s" % KEYS[key].__name__)
    for key in REQUIRED:
        if key not in data:
            err(key, "required")
    if isinstance(data.get("skill"), str) and (not ID.fullmatch(data["skill"]) or skills is not None
                                               and data["skill"] not in skills):
        err("skill", "expected a skill ID%s" % (" under the package's skills/" if skills is not None else ""))
    for key in ("actions", "inputs", "outputs", "due_on"):
        value = data.get(key)
        if isinstance(value, list) and (not all(isinstance(v, str) and v for v in value) or len(set(value)) != len(value)):
            err(key, "expected distinct nonempty strings")
    if isinstance(data.get("actions"), list):
        if not data["actions"]:
            err("actions", "expected at least one generic action")
        if actions is not None:
            for name in data["actions"]:
                if name not in actions:
                    err("actions", "%r is not an action of the actions contract" % name)
    if isinstance(data.get("outputs"), list) and not data["outputs"]:
        err("outputs", "expected at least one output")
    if events is not None and isinstance(data.get("due_on"), list):
        for name in data["due_on"]:
            if name not in events:
                err("due_on", "%r is not an event type of the actions contract" % name)
    if "on_miss" in data and data["on_miss"] not in MISS:
        err("on_miss", "expected one of %s" % ", ".join(MISS))
    for key in ("deadline", "retry"):
        if isinstance(data.get(key), str) and not seconds(data[key]):
            err(key, "expected a duration such as 90s, 10m, 6h or 7d")
    if isinstance(data.get("idle_backoff"), int) and data["idle_backoff"] < 1:
        err("idle_backoff", "expected an integer >= 1")
    if "enabled" in data and "enabled_key" in data:
        err("enabled_key", "use enabled or enabled_key, not both")
    sched = data.get("schedule")
    if isinstance(sched, dict):
        for key, value in sched.items():
            if key not in SCHEDULE_KEYS:
                err("schedule." + key, "unknown key")
            elif type(value) is not SCHEDULE_KEYS[key]:
                err("schedule." + key, "expected str")
        if ("every" in sched) == ("cron" in sched):
            err("schedule", "expected exactly one of every and cron")
        if isinstance(sched.get("every"), str) and not seconds(sched["every"]):
            err("schedule.every", "expected a duration such as 90s, 10m, 6h or 7d")
        if isinstance(sched.get("cron"), str):
            try:
                cron_fields(sched["cron"])
            except ValueError as e:
                err("schedule.cron", str(e))
        for key in ("every_key", "jitter"):
            if key in sched and "cron" in sched:
                err("schedule." + key, "only with every")
        if isinstance(sched.get("every_key"), str) and not any(sched["every_key"].endswith(s) for s in KEY_UNITS):
            err("schedule.every_key", "expected a profile key ending in %s" % ", ".join(KEY_UNITS))
        if isinstance(sched.get("jitter"), str):
            jitter = DURATION.fullmatch(sched["jitter"])
            every = seconds(sched.get("every"))
            if not jitter or every and int(jitter[1]) * UNITS[jitter[2]] >= every:
                err("schedule.jitter", "expected a duration shorter than every, such as 0s or 5m")
        if sched.get("timezone", "owner") != "owner":
            err("schedule.timezone", "expected \"owner\" (the profile's runtime.timezone)")
    return out


def load(roles_dir, actions=None, events=None):
    """({(role, routine): table}, problems) for every <team>/<role>/routines/<routine>.toml under roles_dir, checked
    against the actions and events vocabulary when given; a valid table gains `path` (relative to roles_dir's parent),
    `team` and `role`."""
    routines, problems = {}, []
    base = os.path.dirname(os.path.abspath(roles_dir))
    for team in sorted(os.listdir(roles_dir)) if os.path.isdir(roles_dir) else []:
        for role in sorted(os.listdir(os.path.join(roles_dir, team))) if os.path.isdir(os.path.join(roles_dir, team)) else []:
            folder = os.path.join(roles_dir, team, role, "routines")
            for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                full = os.path.join(folder, name)
                rel = os.path.relpath(full, base).replace(os.sep, "/")
                if name == ".gitkeep":
                    continue
                if not name.endswith(".toml") or not ID.fullmatch(name[:-5]):
                    problems.append((rel, "file", "expected <routine>.toml with a kebab-case name"))
                    continue
                try:
                    with open(full, "rb") as f:
                        data = tomllib.load(f)
                except (OSError, tomllib.TOMLDecodeError) as e:
                    problems.append((rel, "file", "unreadable: %s" % e))
                    continue
                skills_dir = os.path.join(roles_dir, team, role, "skills")
                skills = {s for s in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, s))} \
                    if os.path.isdir(skills_dir) else None
                found = check(rel, data, actions, events, skills)
                problems += found
                if not found:
                    routines[(role, name[:-5])] = dict(data, path=rel, team=team, role=role)
    return routines, problems


def enabled(routine, values):
    """Whether the environment schedules it: `enabled` (default true) or the profile's `enabled_key` value."""
    if "enabled_key" in routine:
        return bool(values.get(routine["enabled_key"]))
    return routine.get("enabled", True)


def interval(routine, values):
    """An interval routine's period in seconds: the profile's every_key value in its suffix's unit when set, else
    `every`; None for a cron routine."""
    sched = routine["schedule"]
    key = sched.get("every_key")
    if key and isinstance(values.get(key), int):
        return values[key] * next(u for s, u in KEY_UNITS.items() if key.endswith(s))
    return seconds(sched["every"]) if "every" in sched else None


def zone(values):
    try:
        return zoneinfo.ZoneInfo(values.get("runtime.timezone") or "UTC")
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return datetime.timezone.utc


def slot(routine, values, last, now):
    """The latest slot start (epoch) at or before now that follows the last run at `last`, else None. Interval slots
    fall every period after the last run, each plus a jitter derived from the routine and last run (stable across
    scans); a cron slot is a matching minute in the owner's timezone. Earlier slots of a gap count as missed."""
    sched = routine["schedule"]
    if "cron" in sched:
        t = cron_prev(cron_fields(sched["cron"]), datetime.datetime.fromtimestamp(now, zone(values)))
        return t.timestamp() if t and t.timestamp() > last else None
    period = interval(routine, values)
    jitter = DURATION.fullmatch(sched.get("jitter", "0s"))
    jitter = int(jitter[1]) * UNITS[jitter[2]]
    start = last + period
    if start <= now:
        start += (now - start) // period * period  # the latest slot of the series; earlier ones were missed
    if jitter:
        start += sum(map(ord, "%s/%s/%d" % (routine.get("role"), routine.get("path"), int(last)))) % (jitter + 1)
    return start if start <= now else None


def due(routine, values, last, now, events=()):
    """The decision for one routine: (action, slot). action is None (not due), "run", "skip" (a missed slot the
    caller records without running) or "escalate" (a missed slot to report, then run once).

    last: None when the routine never ran, else {"at": epoch, "outcome": text}. A routine that never ran runs now,
    which anchors its schedule. A failed last run with `retry` is due again `retry` after it. An event named in
    `due_on` that occurred after the last run makes it due now. Otherwise a slot is due from its start; past start +
    `deadline` it is missed, and `on_miss` decides: skip records it unrun, catch-up-once runs once for every missed
    slot, escalate reports the miss and runs once."""
    if not enabled(routine, values):
        return None, None
    if last is None:
        return "run", now
    at = last["at"]
    if str(last.get("outcome", "")).startswith("failed") and "retry" in routine:
        return ("run", now) if now - at >= seconds(routine["retry"]) else (None, None)
    if any(when > at for name, when in events if name in routine.get("due_on", [])):
        return "run", now
    start = slot(routine, values, at, now)
    if start is None:
        return None, None
    if now - start < seconds(routine["deadline"]):
        return "run", start
    return {"skip": "skip", "catch-up-once": "run", "escalate": "escalate"}[routine["on_miss"]], start


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("roles_dir")
    p.add_argument("--actions", help="comma-separated action names the routines may use")
    p.add_argument("--events", help="comma-separated event types due_on may name")
    args = p.parse_args(argv)
    _, problems = load(args.roles_dir, args.actions and set(args.actions.split(",")),
                       args.events and set(args.events.split(",")))
    for rel, key, reason in problems:
        print("%s:%s: %s" % (rel, key, reason))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
