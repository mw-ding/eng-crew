#!/usr/bin/env python3
"""Refresh the cycle-time / rounds metrics artifact (docs/metrics/).

Lists closed crew PRs per repo, derives the metrics described in
docs/metrics/README.md from the hidden crew:v1 markers in review bodies, and
writes prs.csv and prs.md. Python 3 standard library only. Read-only: it shells
out to the `gh` CLI and relies on gh's own auth (GH_TOKEN or gh login); it
never reads or prints a token. Not run in CI.

Usage: metrics-refresh.py [--repo OWNER/REPO]... [--since YYYY-MM-DD] [--days N] [--out-dir DIR]
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_REPOS = ["mw-ding/eng-crew", "mw-ding/agentconnect"]
DEFAULT_DAYS = 14
FIELDS = [
    "repo", "pr", "state", "opened_at", "merged_at", "open_to_merge_min",
    "ci_fix_rounds", "builder_fix_rounds", "verdicts", "changes_verdicts",
    "reopened", "flavor", "escaped_defects", "engine_runs",
]
ESCAPED_LINE = re.compile(r"^Escaped from: ([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([1-9][0-9]*)$", re.M)
ENGINE_LINE = re.compile(r"^Engine: (.+)$", re.M)
RUN_SIGNATURES = {
    "review": re.compile(r"(?im)^\*?Reviewed by .+|^Review engine: .+"),
    "validate": re.compile(r"(?im)^\*?Validated by .+|^Validation engine: .+"),
}
MARKER_LINE = re.compile(r"^<!--\s*crew:v1\s+(.*?)\s*-->$")


def parse_markers(body):
    """Return a list of dicts, one per whole-line hidden crew:v1 marker."""
    out = []
    for line in (body or "").splitlines():
        m = MARKER_LINE.match(line.strip())
        if m:
            out.append(dict(t.split("=", 1) for t in m.group(1).split() if "=" in t))
    return out


def is_crew_pr(body, labels):
    if any(m.get("role") == "builder" for m in parse_markers(body)):
        return True
    return any(name.startswith("crew:") for name in labels)


def minutes_between(start, end):
    if not start or not end:
        return ""
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    delta = datetime.strptime(end, fmt) - datetime.strptime(start, fmt)
    return int(round(delta.total_seconds() / 60))


def review_metrics(reviews):
    """Count rounds and verdicts from a list of review objects."""
    ci_fix, fix, verdicts, changes = set(), set(), set(), set()
    for review in reviews:
        for mk in parse_markers(review.get("body")):
            key = (mk.get("round"), mk.get("sha"))
            role, step = mk.get("role"), mk.get("pass")
            if role == "builder" and step == "ci-fix":
                ci_fix.add(key)
            elif role == "builder" and step == "fix":
                fix.add(key)
            elif role == "reviewer-validator" and step == "verdict":
                verdicts.add(key)
                if mk.get("verdict") == "changes":
                    changes.add(key)
    return {
        "ci_fix_rounds": len(ci_fix),
        "builder_fix_rounds": len(fix),
        "verdicts": len(verdicts),
        "changes_verdicts": len(changes),
    }


def flavor_at_head(reviews, head):
    for review in reversed(reviews):
        for mk in reversed(parse_markers(review.get("body"))):
            if (mk.get("role") == "reviewer-validator" and mk.get("pass") == "verdict"
                    and mk.get("sha") == head):
                return mk.get("flavor", "")
    return ""


def escaped_counts(issues):
    counts = {}
    for issue in issues:
        if "pull_request" in issue:
            continue
        for repo, number in set(ESCAPED_LINE.findall((issue.get("body") or "").replace("\r\n", "\n"))):
            key = (repo.lower(), int(number))
            counts.setdefault(key, set()).add(issue["html_url"])
    return {key: len(refs) for key, refs in counts.items()}


def engine_runs(commits, reviews):
    # End a builder run at each recorded verdict or fix head, in commit order.
    boundaries = set()
    reviewer_runs = set()
    for review in reviews:
        body = review.get("body") or ""
        for mk in parse_markers(body):
            role, step = mk.get("role"), mk.get("pass")
            if ((role == "builder" and step in ("fix", "ci-fix"))
                    or (role == "reviewer-validator" and step == "verdict")):
                boundaries.add(mk.get("sha"))
        for section in re.split(r"(?m)^## ", body):
            markers = parse_markers(section)
            for mk in markers:
                if (mk.get("role") == "reviewer-validator"
                        and mk.get("pass") in ("review", "validate")
                        and (mk.get("engine") or RUN_SIGNATURES[mk["pass"]].search(section))):
                    reviewer_runs.add((mk.get("round"), mk.get("sha"), mk.get("pass")))
    count, engines = 0, set()
    for commit in commits:
        engines.update(e.strip() for e in ENGINE_LINE.findall(commit["commit"]["message"])
                       if not e.startswith("none ") and e != "none")
        if commit["sha"] in boundaries:
            count += len(engines)
            engines.clear()
    count += len(engines) + len(reviewer_runs)
    return count if count else ""


def build_row(repo, pr, reviews, events, commits=(), escaped_defects=0):
    merged_at = pr.get("merged_at") or ""
    row = {
        "repo": repo,
        "flavor": flavor_at_head(reviews, pr.get("head_sha")),
        "escaped_defects": escaped_defects,
        "engine_runs": engine_runs(commits, reviews),
        "pr": pr["number"],
        "state": "merged" if merged_at else "closed",
        "opened_at": pr["created_at"],
        "merged_at": merged_at,
        "open_to_merge_min": minutes_between(pr["created_at"], merged_at),
        "reopened": "reopened" if any(e.get("event") == "reopened" for e in events) else "",
    }
    row.update(review_metrics(reviews))
    return {k: row[k] for k in FIELDS}


def gh_json(path, *params):
    """Run a read-only `gh api --paginate` call; return a flat list or a single object."""
    cmd = ["gh", "api", "--method", "GET", "--paginate", path]
    for p in params:
        cmd += ["-f", p]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit("gh api %s failed: %s" % (path, proc.stderr.strip()))
    # --paginate prints one JSON document per page, back to back.
    dec, text, pos, items = json.JSONDecoder(), proc.stdout, 0, []
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            break
        doc, pos = dec.raw_decode(text, pos)
        if isinstance(doc, dict) and "items" not in doc:
            return doc
        items.extend(doc["items"] if isinstance(doc, dict) else doc)
    return items


def collect(repo, since):
    query = "repo:%s is:pr is:closed closed:>=%s" % (repo, since)
    defects = escaped_counts(gh_json("search/issues",
        'q=is:issue "Escaped from:" "%s"' % repo, "per_page=100"))
    rows = []
    for hit in gh_json("search/issues", "q=" + query, "per_page=100"):
        labels = [l["name"] for l in hit.get("labels", [])]
        if not is_crew_pr(hit.get("body"), labels):
            continue
        n = hit["number"]
        reviews = gh_json("repos/%s/pulls/%d/reviews" % (repo, n), "per_page=100")
        events = gh_json("repos/%s/issues/%d/events" % (repo, n), "per_page=100")
        commits = gh_json("repos/%s/pulls/%d/commits" % (repo, n), "per_page=100")
        details = gh_json("repos/%s/pulls/%d" % (repo, n))
        pr = dict(details, head_sha=details["head"]["sha"])
        rows.append(build_row(repo, pr, reviews, events, commits,
                              defects.get((repo.lower(), n), 0)))
    return rows


def render_md(rows, repos, since, generated):
    lines = [
        "# Crew PR metrics",
        "",
        "Closed crew PRs in %s," % ", ".join("`%s`" % r for r in repos),
        "closed on or after %s (UTC). Generated %s by" % (since, generated),
        "`scripts/metrics-refresh.py`. Field definitions: [README.md](README.md).",
        "",
        "| " + " | ".join(FIELDS) + " |",
        "|" + "|".join("---" for _ in FIELDS) + "|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r[f]) for f in FIELDS) + " |")
    return "\n".join(lines) + "\n"


def sort_rows(rows):
    return sorted(rows, key=lambda r: (r["repo"], int(r["pr"])))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", action="append", metavar="OWNER/REPO",
                    help="repeatable; default: %s" % ", ".join(DEFAULT_REPOS))
    ap.add_argument("--since", metavar="YYYY-MM-DD",
                    help="lookback start by closed date (overrides --days)")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS,
                    help="lookback in days when --since is absent (default %(default)s)")
    ap.add_argument("--out-dir", default="docs/metrics")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    since = args.since or (now - timedelta(days=args.days)).strftime("%Y-%m-%d")
    datetime.strptime(since, "%Y-%m-%d")
    repos = args.repo or DEFAULT_REPOS

    rows = []
    for repo in repos:
        found = collect(repo, since)
        print("%s: %d crew PRs" % (repo, len(found)))
        rows.extend(found)
    rows = sort_rows(rows)

    with open(args.out_dir + "/prs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    with open(args.out_dir + "/prs.md", "w") as fh:
        fh.write(render_md(rows, repos, since, now.strftime("%Y-%m-%d %H:%M UTC")))


if __name__ == "__main__":
    main()
