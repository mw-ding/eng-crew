#!/usr/bin/env python3
"""Offline reflection effect measures (docs/self-improve.md#effect-measures, #1524).

Joins the metrics CSV (docs/metrics/prs.csv), the sanitized poll/watch observations in
$CREW_STATE/metrics/observations.jsonl, explicitly confirmed false-throttle incidents and, optionally,
schedule/errors.jsonl. Prints one JSON object: each measure with its value, sample size, source refs and coverage.
Missing history stays unknown (value null), and an unconfirmed error stays unclassified. `baseline` saves the window's
measures and cohort bounds for a proposal before its activation; `record` keeps its merge ref and confirmed activation.
Python 3 standard library only; reads local files, never the network. Not run in CI.

Usage: reflection-measures.py measure --since T --until T [--csv F] [--observations F] [--incidents F] [--errors F]
       reflection-measures.py baseline --ledger F --proposal ID (measure options)
       reflection-measures.py record --ledger F --proposal ID --merge-ref REF [--activation REF|not-required]
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

FMT = "%Y-%m-%dT%H:%M:%SZ"


def stamp(text):
    return text + "T00:00:00Z" if len(text) == 10 else text


def minutes(start, end):
    return (datetime.strptime(end, FMT) - datetime.strptime(start, FMT)).total_seconds() / 60


def jsonl(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def measure(value, n, source, refs, coverage, **extra):
    return dict(value=round(value, 1) if n and value is not None else None, n=n, source=source, refs=refs,
                coverage=coverage, **extra)


def csv_means(path, since, until):
    rows = []
    if path and os.path.exists(path):
        with open(path, newline="") as f:
            rows = [r for r in csv.DictReader(f) if since <= (r.get("merged_at") or "") < until]
    out = {}
    for name, column in (("verdict_rounds_per_pr", "verdicts"), ("ci_fix_rounds_per_pr", "ci_fix_rounds")):
        vals = [(r["repo"], r["pr"], int(r[column])) for r in rows if (r.get(column) or "").isdigit()]
        out[name] = measure(sum(v for *_, v in vals) / len(vals) if vals else None, len(vals), path,
                            ["%s#%s" % (repo, pr) for repo, pr, _ in vals], "csv merged_at in window")
    return out


def ready_to_land(obs, since, until):
    """First observed ready to the first observed merge, bounded by each sample's previous poll."""
    first, landed = {}, {}
    for o in (o for o in obs if o.get("source") == "poll"):
        if o.get("ready"):
            first.setdefault(o["pr"], o)
        if o.get("state") == "MERGED":
            landed.setdefault(o["pr"], o)
    durs, lows, highs, refs = [], [], [], []
    for pr, land in sorted(landed.items()):
        ready = first.get(pr)
        if ready and ready["ts"] <= land["ts"] and since <= land["ts"] < until:
            durs.append(minutes(ready["ts"], land["ts"]))
            lows.append(max(0, minutes(ready["ts"], land.get("prev_ts") or ready["ts"])))
            highs.append(minutes(ready["prev_ts"], land["ts"]) if ready.get("prev_ts") else None)
            refs.append("pr#%s" % pr)
    n = len(durs)
    bounds = [round(sum(lows) / n, 1), round(sum(highs) / n, 1) if None not in highs else None] if n else None
    return measure(sum(durs) / n if n else None, n, "observations:poll", refs, None, unit="minutes", bounds=bounds)


def stall_minutes(obs, since, until):
    """Union of stall intervals [since, resume ts or, still open, the stall's observed ts], clipped to the covered
    part of the window (since/until); only stalls overlapping it count. No coverage: null."""
    stalls, ends = {}, {}
    for o in (o for o in obs if o.get("source") == "watch"):
        key = (o["key"], o["since"])
        if o["kind"] == "stall":
            stalls.setdefault(key, o["ts"])  # a replayed sample repeats (key, since): one stall
        elif o["kind"] == "resume":
            ends.setdefault(key, o["ts"])
    clipped = {key: (max(key[1], since), min(ends.get(key, ts), until)) for key, ts in stalls.items()}
    clipped = {key: span for key, span in clipped.items() if span[0] < span[1]}
    spans = sorted(clipped.values())
    total, cur = 0.0, None
    for start, end in spans:
        if cur and start <= cur[1]:
            cur[1] = max(cur[1], end)
            continue
        total += minutes(*cur) if cur else 0
        cur = [start, end]
    total += minutes(*cur) if cur else 0
    covered = since is not None
    return dict(measure(total, len(clipped), "observations:watch", sorted({key for key, _ in clipped}), None,
                        unit="minutes", open=sum(key not in ends for key in clipped)),
                value=round(total, 1) if covered else None)  # observed and none stalled: zero


def throttles(path, errors, since, until):
    """Explicitly confirmed false-throttles by incident id; zero only when an incident file was read."""
    incidents = jsonl(path)
    confirmed = {i["id"]: i for i in incidents if i.get("kind") == "false-throttle" and i.get("confirmed")
                 and since <= i.get("ts", "") < until}
    seen = {(e.get("source"), e.get("text"), e.get("ts", "")[:16]) for e in errors if since <= e.get("ts", "") < until}
    known = bool(path and os.path.exists(path))
    return dict(measure(len(confirmed), len(confirmed), "incidents (explicitly confirmed)", sorted(confirmed),
                        "confirmed incidents in window" if known else "unknown", unclassified_errors=len(seen)),
                value=len(confirmed) if known else None)


def measures(args):
    since, until = stamp(args.since), stamp(args.until)
    obs = jsonl(args.observations)
    stamps = sorted(o["ts"] for o in obs)
    lo, hi = (max(stamps[0], since), min(stamps[-1], until)) if stamps else (None, None)
    if lo is not None and lo >= hi:  # samples exist but none during the window: its history is unknown
        lo = hi = None
    coverage = {"from": lo, "to": hi, "partial": lo > since or hi < until} if lo is not None else "unknown"
    stalls = stall_minutes(obs, lo, hi) if lo is not None else stall_minutes([], None, None)
    out = {"window": {"since": since, "until": until}, **csv_means(args.csv, since, until),
           "ready_to_land": ready_to_land(obs, since, until), "stall_minutes": stalls,
           "false_throttles": throttles(args.incidents, jsonl(args.errors), since, until)}
    for name in ("ready_to_land", "stall_minutes"):
        out[name]["coverage"] = coverage
    return out


def append(path, record):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("measure", "baseline", "record"):
        p = sub.add_parser(name)
        if name != "measure":
            p.add_argument("--ledger", required=True)
            p.add_argument("--proposal", required=True)
        if name == "record":
            p.add_argument("--merge-ref", required=True)
            p.add_argument("--activation", help="release or install ref, or not-required; omitted: pending")
            continue
        p.add_argument("--since", required=True)
        p.add_argument("--until", required=True)
        p.add_argument("--csv", default="docs/metrics/prs.csv")
        p.add_argument("--observations")
        p.add_argument("--incidents")
        p.add_argument("--errors")
    args = ap.parse_args(argv)
    now = datetime.now(timezone.utc).strftime(FMT)
    if args.cmd == "measure":
        print(json.dumps(measures(args), indent=2, sort_keys=True))
        return 0
    if args.cmd == "record":
        append(args.ledger, {"type": "activation", "proposal": args.proposal, "merge_ref": args.merge_ref,
                             "activation": args.activation or "pending", "recorded_at": now})
        print("recorded %s: merge %s, activation %s" % (args.proposal, args.merge_ref, args.activation or "pending"))
        return 0
    if any(r.get("proposal") == args.proposal and r.get("activation", "pending") != "pending"
           for r in jsonl(args.ledger)):
        print("refused: %s already has a confirmed activation; a baseline must precede it" % args.proposal,
              file=sys.stderr)
        return 1
    append(args.ledger, {"type": "baseline", "proposal": args.proposal, "saved_at": now, **measures(args)})
    print("baseline saved for %s: %s to %s" % (args.proposal, stamp(args.since), stamp(args.until)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
