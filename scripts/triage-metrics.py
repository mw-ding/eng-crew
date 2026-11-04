#!/usr/bin/env python3
"""Triage shadow-mode measures (docs/triage.md Shadow mode and calibration, Feedback; #750).

Reads the JSON that `gh issue list --state all --json
number,url,state,stateReason,labels,createdAt,comments` prints (one or more repos concatenated into one list)
and the `pass=triage` / `pass=triage-log` hidden lines on it (protocol §4). Pure computation: no network, no gh,
no writes except `eval-freeze --out`. Python 3 standard library only.

  sample       the 10 spot-check issues of a calibration sweep, one ref per line (deterministic per sweep id)
  bar          owner answers on that sample: met at 8 of 10 accepted as is
  report       accuracy, owner override rate, reopen rate, time to triage, proposals per day, tokens per sweep
  eval-freeze  write the eval set: owner-accepted proposals of a sweep (owner-confirmed records)
  eval-score   compare re-classified answers ({"<ref>": {"decision", "priority"}}) with the eval set

Usage: triage-metrics.py {sample,bar,report} --items FILE [--sweep ID] [--n 10] [--need 8]
       triage-metrics.py eval-freeze --items FILE --sweep ID --out FILE
       triage-metrics.py eval-score --set FILE --answers FILE
Exit codes: 0 OK (bar met), 1 bar not met or still pending, 2 usage or input error.
"""
import argparse
import json
import random
import re
import statistics
import sys
from datetime import datetime

LINE = re.compile(r"<!-- crew:v1 ([^>]*?) -->")
CLOSES = {"duplicate", "propose-close"}  # decisions that propose a close
OWNER = {"owner-accepted", "owner-rejected"}


def ref(item):
    m = re.search(r"([\w.-]+/[\w.-]+)/(?:issues|pull)/(\d+)", item.get("url", ""))
    return "%s#%s" % (m[1], m[2]) if m else "#%s" % item["number"]


def records(item, kind="triage"):
    """[(createdAt, fields)] of one item's `pass=<kind>` lines, oldest first."""
    out = []
    for c in item.get("comments") or []:
        for line in LINE.findall(c.get("body") or ""):
            fields = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if fields.get("pass") == kind:
                out.append((c.get("createdAt") or "", fields))
    return out


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def sample(items, sweep, n):
    refs = sorted(ref(i) for i in items if any(f.get("sweep") == sweep for _, f in records(i)))
    return sorted(random.Random(sweep).sample(refs, min(n, len(refs))))


def answer(item, sweep):
    """The owner's answer to the sweep's record, before a newer proposal supersedes it: owner-accepted,
    owner-rejected or None. An answer to a revised proposal never counts for the original."""
    recs = records(item)
    at = next((k for k, (_, f) in enumerate(recs) if f.get("sweep") == sweep), len(recs))
    window = []
    for _, f in recs[at + 1:]:
        if f.get("decision") not in OWNER:
            break
        window.append(f["decision"])
    return window[-1] if window else None


def proposals(items, sweep):
    """{ref: {decision, priority}} for each item whose sweep record the owner accepted as is."""
    out = {}
    for item in items:
        rec = next((f for _, f in records(item) if f.get("sweep") == sweep), None)
        if rec and answer(item, sweep) == "owner-accepted":
            out[ref(item)] = {"decision": rec.get("decision"), "priority": rec.get("priority")}
    return out


def rate(num, den):
    return "%d/%d (%.0f%%)" % (num, den, 100.0 * num / den) if den else "n/a (0 items)"


def report(items):
    hits = closed = rejected = answered = reopened = proposed_closed = 0
    hours, per_day, tokens, unknown = [], {}, [], 0
    for item in items:
        recs = records(item)
        decisions = [f.get("decision") for _, f in recs]
        rejected += decisions.count("owner-rejected")
        answered += sum(d in OWNER for d in decisions)
        if recs:
            hours.append((ts(recs[0][0]) - ts(item["createdAt"])).total_seconds() / 3600)
        last = next((f for _, f in reversed(recs) if f.get("decision") not in OWNER), None)
        reason = (item.get("stateReason") or "").upper()
        if last and last.get("decision") in CLOSES and (item.get("state") == "CLOSED" or reason == "REOPENED"):
            proposed_closed += 1
            reopened += reason == "REOPENED"
        if last and item.get("state") == "CLOSED":
            closed += 1
            bands = {lab["name"] for lab in item.get("labels") or []} & {"P0", "P1", "P2", "P3"}
            closes = reason in ("NOT_PLANNED", "DUPLICATE")
            hits += (not bands or last.get("priority") in bands) and closes == (last.get("decision") in CLOSES)
        for when, f in records(item, "triage-log"):
            per_day[when[:10]] = per_day.get(when[:10], 0) + int(f.get("proposed", 0))
            if f.get("tokens", "").isdigit():
                tokens.append(int(f["tokens"]))
            else:
                unknown += 1
    return ["accuracy: %s closed items match the newest record (band and close)" % rate(hits, closed),
            "override rate: %s owner answers rejected" % rate(rejected, answered),
            "reopen rate: %s closed-as-proposed items reopened" % rate(reopened, proposed_closed),
            "time to triage: median %s h over %d items" % (
                "%.1f" % statistics.median(hours) if hours else "n/a", len(hours)),
            "proposals per day: mean %s over %d days" % (
                "%.1f" % statistics.mean(per_day.values()) if per_day else "n/a", len(per_day)),
            "tokens per sweep: median %s over %d sweeps (%d unknown)" % (
                statistics.median(tokens) if tokens else "n/a", len(tokens), unknown)]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["sample", "bar", "report", "eval-freeze", "eval-score"])
    p.add_argument("--items")
    p.add_argument("--sweep")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--need", type=int, default=8)
    p.add_argument("--out")
    p.add_argument("--set")
    p.add_argument("--answers")
    a = p.parse_args(argv)
    need = {"sample": ["items", "sweep"], "bar": ["items", "sweep"], "report": ["items"],
            "eval-freeze": ["items", "sweep", "out"], "eval-score": ["set", "answers"]}[a.cmd]
    missing = [o for o in need if not getattr(a, o)]
    if missing:
        p.error("%s needs --%s" % (a.cmd, " --".join(missing)))
    try:
        items = load(a.items) if a.items else []
        if a.cmd == "eval-score":
            frozen, answers = load(a.set)["records"], load(a.answers)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print("triage-metrics: unreadable input: %s" % e, file=sys.stderr)
        return 2
    if a.cmd == "sample":
        print("\n".join(sample(items, a.sweep, a.n)))
    elif a.cmd == "bar":
        by_ref = {ref(i): i for i in items}
        got = [answer(by_ref[r], a.sweep) for r in sample(items, a.sweep, a.n)]
        accepted, pending = got.count("owner-accepted"), got.count(None)
        state = "met" if accepted >= a.need else "pending" if accepted + pending >= a.need else "not met"
        print("bar: %d/%d accepted as is, %d rejected, %d pending (need %d): %s" % (
            accepted, len(got), got.count("owner-rejected"), pending, a.need, state))
        return 0 if state == "met" else 1
    elif a.cmd == "report":
        print("\n".join(report(items)))
    elif a.cmd == "eval-freeze":
        frozen = proposals(items, a.sweep)
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"sweep": a.sweep, "records": frozen}, f, indent=2, sort_keys=True)
        print("eval set: %d owner-confirmed records -> %s" % (len(frozen), a.out))
    else:
        match = sum({k: (answers.get(r) or {}).get(k) for k in v} == v for r, v in frozen.items())
        print("eval: %s records match the eval set" % rate(match, len(frozen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
