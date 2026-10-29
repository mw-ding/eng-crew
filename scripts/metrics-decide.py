#!/usr/bin/env python3
"""Evaluate the metrics -> decisions sensors on docs/metrics/prs.csv.

Reads the CSV written by scripts/metrics-refresh.py, splits merged crew PRs into
a current window and the prior baseline window, computes per-repo and rollup
medians and rates, and prints a markdown report with a verdict. Pure
computation on the CSV: no network, no gh. Python 3 standard library only.
Protocol: docs/metrics/decisions.md.

Exit codes: 0 OK or INSUFFICIENT data, 1 TRIP (rollup sensor tripped: the
gate), 2 usage or input error, 3 FOLLOW-UP (a single repo tripped, rollup did
not: file a project follow-up, no gate).
"""
import argparse
import csv
import statistics
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_REPOS = ["mw-ding/eng-crew", "mw-ding/agentconnect"]
DEFAULTS = {
    "window_days": 14,
    "baseline_days": 14,
    "latency_pct": 30.0,
    "rework_pct": 20.0,
    "rework_changes": 3,
    "min_prs": 3,
}
REQUIRED = ["repo", "pr", "merged_at", "open_to_merge_min", "ci_fix_rounds",
            "changes_verdicts", "reopened"]
TS = "%Y-%m-%dT%H:%M:%SZ"


def load_rows(path):
    """Return merged-PR rows from a metrics-refresh.py CSV, typed."""
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [f for f in REQUIRED if f not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("%s: missing columns: %s" % (path, ", ".join(missing)))
        rows = []
        for r in reader:
            if not r["merged_at"] or not r["open_to_merge_min"]:
                continue  # closed unmerged: no merge time, outside both windows
            rows.append({
                "repo": r["repo"],
                "pr": int(r["pr"]),
                "merged": datetime.strptime(r["merged_at"], TS).replace(
                    tzinfo=timezone.utc),
                "minutes": int(r["open_to_merge_min"]),
                "ci_fix": int(r["ci_fix_rounds"] or 0),
                "changes": int(r["changes_verdicts"] or 0),
                "reopened": r["reopened"] == "reopened",
            })
    return rows


def split_windows(rows, as_of, window_days, baseline_days):
    """Current = (as_of+1d - window, as_of+1d]; baseline = the span before it."""
    end = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc) \
        + timedelta(days=1)
    mid = end - timedelta(days=window_days)
    start = mid - timedelta(days=baseline_days)
    cur = [r for r in rows if mid <= r["merged"] < end]
    base = [r for r in rows if start <= r["merged"] < mid]
    return cur, base


def is_rework(row, rework_changes):
    """Proxy for rework after clearance: reopened, or changes at the cap."""
    return row["reopened"] or row["changes"] >= rework_changes


def stats(rows, rework_changes):
    n = len(rows)
    rework = [r for r in rows if is_rework(r, rework_changes)]
    return {
        "n": n,
        "median": statistics.median(r["minutes"] for r in rows) if n else None,
        "rework": len(rework),
        "rate": len(rework) / n if n else None,
        "ci_per_pr": sum(r["ci_fix"] for r in rows) / n if n else None,
    }


def evaluate(cur_rows, base_rows, cfg):
    """Return per-sensor results for one scope (a repo or the rollup)."""
    cur = stats(cur_rows, cfg["rework_changes"])
    base = stats(base_rows, cfg["rework_changes"])
    min_prs = cfg["min_prs"]
    delta = None
    latency = "INSUFFICIENT"
    if cur["n"] >= min_prs and base["n"] >= min_prs and base["median"]:
        delta = (cur["median"] - base["median"]) / base["median"] * 100
        latency = "TRIP" if delta > cfg["latency_pct"] else "OK"
    quality = "INSUFFICIENT"
    if cur["n"] >= min_prs:
        quality = "TRIP" if cur["rate"] * 100 > cfg["rework_pct"] else "OK"
    return {"cur": cur, "base": base, "delta": delta,
            "latency": latency, "quality": quality,
            "tripped": "TRIP" in (latency, quality)}


def verdict(rollup, per_repo):
    if rollup["tripped"]:
        return "TRIP", 1
    if any(e["tripped"] for e in per_repo.values()):
        return "FOLLOW-UP", 3
    if rollup["latency"] == rollup["quality"] == "INSUFFICIENT":
        return "INSUFFICIENT", 0
    return "OK", 0


def fmt_min(v):
    return "-" if v is None else "%d" % round(v)


def fmt_pct(v):
    return "-" if v is None else "%d%%" % round(v * 100)


def fmt_delta(v):
    return "-" if v is None else "%+d%%" % round(v)


def table_row(name, e):
    return "| %s | %d | %s | %d | %s | %s | %s | %s | %s | %s |" % (
        name, e["cur"]["n"], fmt_min(e["cur"]["median"]), e["base"]["n"],
        fmt_min(e["base"]["median"]), fmt_delta(e["delta"]), e["latency"],
        fmt_pct(e["cur"]["rate"]), e["quality"],
        "-" if e["cur"]["ci_per_pr"] is None else "%.1f" % e["cur"]["ci_per_pr"])


HEADER = [
    "| Scope | PRs | Median min | Base PRs | Base median min | Change "
    "| Latency | Rework rate | Quality | CI-fix per PR |",
    "|---|---|---|---|---|---|---|---|---|---|",
]


def offenders(rows, cfg, limit=3):
    """Rework PRs, plus the slowest PRs, as owner/repo#N for the issue body."""
    out = {("%s#%d" % (r["repo"], r["pr"])): r for r in rows
           if is_rework(r, cfg["rework_changes"])}
    for r in sorted(rows, key=lambda r: -r["minutes"])[:limit]:
        out.setdefault("%s#%d" % (r["repo"], r["pr"]), r)
    return ["%s (%d min, changes=%d%s)" % (
        k, v["minutes"], v["changes"], ", reopened" if v["reopened"] else "")
        for k, v in sorted(out.items())]


def report(repos, cur_rows, base_rows, cfg, as_of):
    rollup = evaluate(cur_rows, base_rows, cfg)
    per_repo = {
        repo: evaluate([r for r in cur_rows if r["repo"] == repo],
                       [r for r in base_rows if r["repo"] == repo], cfg)
        for repo in repos}
    word, code = verdict(rollup, per_repo)
    lines = [
        "# Metrics decision report",
        "",
        "As of %s (UTC). Current window %d days, baseline the %d days before it."
        % (as_of, cfg["window_days"], cfg["baseline_days"]),
        "Thresholds: median open-to-merge up more than %g%%; rework rate above "
        "%g%% (rework = reopened or %d+ changes verdicts); at least %d merged "
        "PRs per window." % (cfg["latency_pct"], cfg["rework_pct"],
                             cfg["rework_changes"], cfg["min_prs"]),
        "",
        "## Rollup (decides the gate)",
        "",
        *HEADER,
        table_row("rollup", rollup),
        "",
        "## Per repo (project follow-up only)",
        "",
        *HEADER,
        *[table_row(repo, per_repo[repo]) for repo in repos],
        "",
    ]
    flagged = [r for r in repos if per_repo[r]["tripped"]]
    if rollup["tripped"]:
        flagged = repos
    if flagged:
        lines += ["## Pull requests to link", ""]
        for repo in flagged:
            items = offenders([r for r in cur_rows if r["repo"] == repo], cfg)
            lines += ["- %s: %s" % (repo, "; ".join(items) or "none")]
        lines.append("")
    lines.append("VERDICT: %s" % word)
    return "\n".join(lines) + "\n", code


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", default="docs/metrics/prs.csv")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="last day of the current window (default: today, UTC)")
    ap.add_argument("--repo", action="append", metavar="OWNER/REPO",
                    help="repeatable; default: every repo in the CSV plus %s"
                    % ", ".join(DEFAULT_REPOS))
    for key, val in DEFAULTS.items():
        ap.add_argument("--" + key.replace("_", "-"), type=type(val), default=val,
                        help="default %(default)s")
    args = ap.parse_args(argv)
    cfg = {k: getattr(args, k) for k in DEFAULTS}
    as_of = args.as_of or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        datetime.strptime(as_of, "%Y-%m-%d")
        rows = load_rows(args.csv)
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    repos = args.repo or sorted(set(DEFAULT_REPOS) | {r["repo"] for r in rows})
    rows = [r for r in rows if r["repo"] in repos]
    cur, base = split_windows(rows, as_of, cfg["window_days"], cfg["baseline_days"])
    text, code = report(repos, cur, base, cfg, as_of)
    sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
