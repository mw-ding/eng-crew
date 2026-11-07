#!/usr/bin/env python3
"""Report median pipeline latencies and per-PR counts for closed crew PRs.

A baseline to compare later crew changes against (docs/metrics/README.md,
Baseline report). Measurement only. Python 3 standard library only. Read-only:
it reuses metrics-refresh.py's `gh` calls and marker parsing and relies on gh's
own auth (GH_TOKEN or gh login); it never reads or prints a token. Not run in CI.

Usage: metrics-baseline.py --repo OWNER/REPO [--since YYYY-MM-DD | --days N]
                           [--until YYYY-MM-DD] [--milestone N] [--out FILE]
"""
import argparse
import importlib.util
import os
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("metrics_refresh", os.path.join(HERE, "metrics-refresh.py"))
mr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mr)

CLOSES = re.compile(r"(?im)^\s*(?:closes|fixes|resolves)\s+#([1-9][0-9]*)\b")
COLUMNS = ["pr", "issue", "state", "issue_to_pr_min", "pr_to_first_verdict_min",
           "verdict_to_land_min", "ack_latency_min", "rounds", "defects", "engine_runs"]
METRICS = [
    ("issue_to_pr_min", "Issue to PR (min)", "Closing issue created to PR opened"),
    ("pr_to_first_verdict_min", "PR to first verdict (min)",
     "PR opened to the first reviewer-validator `pass=verdict` review"),
    ("verdict_to_land_min", "Verdict to land (min)", "Last verdict before merge to merge; merged PRs only"),
    ("ack_latency_min", "Handoff ack latency (min)",
     "PR opened to the first reviewer-validator `pass=ack` review before any verdict"),
    ("rounds", "Rounds per PR", "Distinct reviewer-validator verdicts"),
    ("defects", "Defects caught per PR", "Distinct `verdict=changes` verdicts (review or validation)"),
    ("engine_runs", "Engine cost per PR (runs)", "Recorded engine runs, where recorded; a run proxy, not tokens"),
]


def closing_issue(body):
    m = CLOSES.search(body or "")
    return int(m.group(1)) if m else None


def marker_times(reviews, step):
    """Submit times of reviews carrying a reviewer-validator marker for `step`, oldest first."""
    return sorted(r["submitted_at"] for r in reviews if r.get("submitted_at") and any(
        mk.get("role") == "reviewer-validator" and mk.get("pass") == step
        for mk in mr.parse_markers(r.get("body"))))


def pr_row(pr, issue, reviews, commits):
    """One report row from PR details, its closing issue (or None), reviews and commits."""
    merged = pr.get("merged_at") or ""
    verdicts = marker_times(reviews, "verdict")
    first = verdicts[0] if verdicts else ""
    acks = [t for t in marker_times(reviews, "ack") if not first or t <= first]
    landed = [t for t in verdicts if t <= merged] if merged else []
    counts = mr.review_metrics(reviews)
    return {
        "pr": pr["number"],
        "issue": issue["number"] if issue else "",
        "state": "merged" if merged else "closed",
        "issue_to_pr_min": mr.minutes_between(issue["created_at"], pr["created_at"]) if issue else "",
        "pr_to_first_verdict_min": mr.minutes_between(pr["created_at"], first),
        "verdict_to_land_min": mr.minutes_between(landed[-1], merged) if landed else "",
        "ack_latency_min": mr.minutes_between(pr["created_at"], acks[0]) if acks else "",
        "rounds": counts["verdicts"],
        "defects": counts["changes_verdicts"],
        "engine_runs": mr.engine_runs(commits, reviews),
    }


def summarize(rows):
    """(key, label, definition, median or 'n/a', n) for each metric; blanks are skipped."""
    out = []
    for key, label, definition in METRICS:
        values = [r[key] for r in rows if r[key] != ""]
        med = statistics.median(values) if values else None
        shown = "n/a" if med is None else ("%d" % med if med == int(med) else "%.1f" % med)
        out.append((key, label, definition, shown, len(values)))
    return out


def render(rows, repo, since, until, milestone, generated):
    scope = "closed %s to %s (UTC)" % (since, until)
    if milestone:
        scope += ", closing issue in milestone %s" % milestone
    lines = [
        "# Crew baseline metrics",
        "",
        "Closed crew PRs in `%s`, %s. Generated %s by" % (repo, scope, generated),
        "`scripts/metrics-baseline.py`. Definitions: [README.md](README.md#baseline-report).",
        "",
        "## Medians",
        "",
        "| Metric | Median | PRs | How derived |",
        "|---|---|---|---|",
    ]
    for _, label, definition, shown, n in summarize(rows):
        lines.append("| %s | %s | %d | %s |" % (label, shown, n, definition))
    total = sum(r["defects"] for r in rows)
    lines += ["", "PRs: %d (%d merged). Defects caught in total: %d." % (
        len(rows), sum(r["state"] == "merged" for r in rows), total), "",
        "## Per PR", "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "|".join("---" for _ in COLUMNS) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in COLUMNS) + " |")
    return "\n".join(lines) + "\n"


def collect(repo, since, until, milestone):
    rows, title = [], ""
    query = "q=repo:%s is:pr is:closed closed:%s..%s" % (repo, since, until)
    for hit in mr.gh_json("search/issues", query, "per_page=100"):
        if not mr.is_crew_pr(hit.get("body"), [l["name"] for l in hit.get("labels", [])]):
            continue
        n = hit["number"]
        number = closing_issue(hit.get("body"))
        issue = mr.gh_json("repos/%s/issues/%d" % (repo, number)) if number else None
        ms = (issue or {}).get("milestone") or {}
        if milestone and ms.get("number") != milestone:
            continue
        title = title or ms.get("title", "")
        pr = mr.gh_json("repos/%s/pulls/%d" % (repo, n))
        reviews = mr.gh_json("repos/%s/pulls/%d/reviews" % (repo, n), "per_page=100")
        commits = mr.gh_json("repos/%s/pulls/%d/commits" % (repo, n), "per_page=100")
        rows.append(pr_row(pr, issue, reviews, commits))
    return sorted(rows, key=lambda r: r["pr"]), title


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, metavar="OWNER/REPO")
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="window start by closed date (overrides --days)")
    ap.add_argument("--days", type=int, default=mr.DEFAULT_DAYS,
                    help="window length when --since is absent (default %(default)s)")
    ap.add_argument("--until", metavar="YYYY-MM-DD", help="window end by closed date (default today)")
    ap.add_argument("--milestone", type=int, metavar="N",
                    help="keep only PRs whose closing issue is in milestone number N")
    ap.add_argument("--out", help="write the report here (default stdout)")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    since = args.since or (now - timedelta(days=args.days)).strftime("%Y-%m-%d")
    until = args.until or now.strftime("%Y-%m-%d")
    for day in (since, until):
        datetime.strptime(day, "%Y-%m-%d")
    rows, title = collect(args.repo, since, until, args.milestone)
    label = ("#%d %s" % (args.milestone, title)).strip() if args.milestone else ""
    text = render(rows, args.repo, since, until, label, now.strftime("%Y-%m-%d %H:%M UTC"))
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
        print("%s: %d crew PRs -> %s" % (args.repo, len(rows), args.out), file=sys.stderr)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
