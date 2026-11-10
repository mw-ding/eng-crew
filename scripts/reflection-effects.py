#!/usr/bin/env python3
"""Reflection effect table: before/after rows for every accepted reflection proposal (M39 R9, #1525; #1403).

Reads, offline: forge snapshots (`--forge`, repeatable; the `gh issue list` / `gh pr list` JSON with comments) for
the proposal -> issue -> PR chain, the effect ledger of `reflection-measures.py baseline` / `record` (`--ledger`) and
the same measure inputs (`--csv`, `--observations`, `--incidents`, `--errors`). Python 3 standard library only; no
network, no writes but stdout. Informational: it recommends keep, revise or revert, claims no cause and reverts
nothing; the metrics gate (docs/metrics/decisions.md) and its thresholds are unchanged.

Chain: a `- rp-ID: ... accept -> #n` line in a `[<Bot>/reflection-decision]` comment names the issue (a later
decision wins); a merged PR whose body closes it lands it. Before: the proposal's latest ledger baseline. After: the
measure over whole 14-day windows from the confirmed activation's `recorded_at`, CSV rows limited to the baseline's
repos (the cohort). The measure is the issue's `Effect metric`. Status: `pending` (not merged, activation pending or
no whole window yet), `insufficient` (no baseline or metric, fewer than 3 PRs on a side of a PR measure, or a
counter's coverage unknown), else `evaluated`. Only an evaluated row recommends: keep when the measure did not rise,
revert when it rose more than 30% (the latency sensor's default), else revise. Lower is better for every measure.

Usage: reflection-effects.py --forge FILE... --ledger FILE [--now T] [--json] (reflection-measures measure options)
Exit codes: 0 table printed, 2 usage or malformed input.
"""
import argparse
import csv
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = module("reflection_scan", "reflection-scan.py")
rm = module("reflection_measures", "reflection-measures.py")
tc = rs.tc
WINDOW = timedelta(days=14)
MIN_PRS = 3
REVERT_PCT = 30
PR_MEASURES = ("verdict_rounds_per_pr", "ci_fix_rounds_per_pr", "ready_to_land")
MEASURES = PR_MEASURES + ("stall_minutes", "false_throttles")
ACCEPT = re.compile(r"(?m)^- (rp-[\w.-]+):.*?\baccept\s*(?:→|->)\s*((?:[\w.-]+/[\w.-]+)?#\d+)")
METRIC = re.compile(r"(?im)^[-*\s]*(?:\*\*)?Effect metric(?:\*\*)?:?(?:\*\*)?(.*)$")


def chain(items):
    """Proposal ID -> (issue ref, merged PR or None, issue item or None), from decision comments."""
    by_ref = {tc.ref(i).lower(): i for i in items}
    accepted = {}
    comments = [(c, i) for i in items for c in i.get("comments") or []]
    for c, item in sorted(comments, key=lambda ci: ci[0].get("createdAt") or ""):
        m = rs.SIGNED.match(c.get("body") or "")
        if m and m[2] == "reflection-decision":
            for proposal, target in ACCEPT.findall(c["body"]):
                accepted[proposal] = rs.refs(target, tc.repo_of(item))[0]
    merged = [i for i in items if "/pull/" in (i.get("url") or "") and i.get("state") == "MERGED"]
    out = {}
    for proposal, issue in sorted(accepted.items()):
        prs = sorted((p for p in merged if issue in rs.fixes(p, tc.repo_of(p))), key=lambda p: p.get("closedAt") or "")
        out[proposal] = (issue, prs[0] if prs else None, by_ref.get(issue))
    return out


def metric(issue):
    m = METRIC.search((issue or {}).get("body") or "")
    return next((name for name in MEASURES if m and name in m[1]), None)


def cohort_csv(path, repos):
    """The CSV limited to the cohort's repos, as a temp file; all rows when the cohort names none."""
    if not repos or not path or not os.path.exists(path):
        return path
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("repo") in repos]
        fields = reader.fieldnames
    out = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    with out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return out.name


def verdict(name, before, after):
    """Status, missing-data reasons and recommendation for one before/after pair."""
    missing = []
    for side, m in (("before", before), ("after", after)):
        if name in PR_MEASURES and m["n"] < MIN_PRS:
            missing.append("%s n=%d < %d" % (side, m["n"], MIN_PRS))
        elif m["value"] is None:
            missing.append("%s coverage %s" % (side, m.get("coverage") or "unknown"))
    if missing:
        return "insufficient", missing, "none"
    b, a = before["value"], after["value"]
    if a <= b:
        return "evaluated", [], "keep"
    return "evaluated", [], "revert" if b == 0 or round((a - b) * 100 / b, 1) > REVERT_PCT else "revise"


def row(proposal, link, ledger, args, now):
    issue, pr, item = link
    records = [r for r in ledger if r.get("proposal") == proposal]
    baselines = [r for r in records if r.get("type") == "baseline"]
    active = [r for r in records if r.get("type") == "activation" and r.get("activation", "pending") != "pending"]
    name = metric(item)
    out = {"proposal": proposal, "issue": issue, "pr": tc.ref(pr).lower() if pr else None, "metric": name,
           "class": tc.card(item or {}, "Failure class") or "unknown", "repos": [], "before": None, "after": None,
           "activation": active[-1]["activation"] if active else "pending", "missing": [], "next_evaluation": None,
           "status": "pending", "recommendation": "none"}
    if not pr:
        out["missing"].append("not merged")
        return out
    if not active:
        out["missing"].append("activation pending")
        return out
    start = datetime.strptime(active[-1]["recorded_at"], rm.FMT).replace(tzinfo=timezone.utc)
    windows = int((now - start) / WINDOW)
    out["next_evaluation"] = (start + WINDOW * (windows + 1)).strftime("%Y-%m-%d")
    if not windows:
        out["missing"].append("first 14-day window open")
        return out
    out["status"] = "insufficient"
    if not baselines or not name:
        out["missing"] += (["no baseline"] if not baselines else []) + (["no effect metric"] if not name else [])
        return out
    before = baselines[-1][name]
    out["repos"] = sorted({r.split("#")[0] for r in before["refs"] if "#" in r and "/" in r}) or [tc.repo_of(pr)]
    window = argparse.Namespace(since=start.strftime(rm.FMT), until=(start + WINDOW * windows).strftime(rm.FMT),
                                csv=cohort_csv(args.csv, out["repos"]), observations=args.observations,
                                incidents=args.incidents, errors=args.errors)
    after = rm.measures(window)[name]
    if window.csv != args.csv:
        os.unlink(window.csv)
    out["before"], out["after"] = before, after
    out["status"], out["missing"], out["recommendation"] = verdict(name, before, after)
    return out


def cell(m):
    return "unknown" if not m or m["value"] is None else "%s (n=%d)" % (m["value"], m["n"])


def render(rows):
    lines = ["Recommendations only: a before/after comparison, not a cause; nothing is reverted automatically.", "",
             "| Proposal | Issue → PR | Activation | Metric | Before | After | Cohort | Missing data | Status "
             "| Next evaluation | Recommendation |", "|" + " --- |" * 11]
    for r in rows:
        lines.append("| %s |" % " | ".join([
            r["proposal"], "%s → %s" % (r["issue"], r["pr"] or "none"), r["activation"], r["metric"] or "unknown",
            cell(r["before"]), cell(r["after"]), "%s; %s" % (", ".join(r["repos"]) or "n/a", r["class"]),
            "; ".join(r["missing"]) or "none", r["status"], r["next_evaluation"] or "on activation",
            r["recommendation"]]))
    if not rows:
        lines.append("| none | | | | | | | | | | |")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--forge", action="append", required=True)
    p.add_argument("--ledger", required=True)
    p.add_argument("--now", help="evaluation time, default now (UTC)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--csv", default="docs/metrics/prs.csv")
    p.add_argument("--observations")
    p.add_argument("--incidents")
    p.add_argument("--errors")
    args = p.parse_args(argv)
    try:
        items = [i for path in args.forge for i in rs.load(path)]
        now = datetime.strptime(rm.stamp(args.now), rm.FMT) if args.now else datetime.now(timezone.utc)
        now = now.replace(tzinfo=timezone.utc)
        ledger = rm.jsonl(args.ledger)
        rows = [row(proposal, link, ledger, args, now) for proposal, link in chain(items).items()]
    except (OSError, ValueError, KeyError, TypeError) as e:
        print("reflection-effects: unreadable input: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(rows, indent=2, sort_keys=True) if args.json else render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
