#!/usr/bin/env python3
"""Print intake candidate cards for blocked or stale open PRs.

Reads the JSON that `gh pr list --json number,title,url,labels,updatedAt,isDraft`
produces (a file argument, or stdin) and prints one markdown card per PR that is
labelled `crew:blocked` (see --label) or has had no update for more than
--stale-days days. Cards follow templates/intake-candidate.md, with Scope
defaulting to `repo:`. Draft PRs are skipped: unfinished work is not stuck.
Python 3 standard library only. Offline and read-only: it makes no network
call, files no issue and edits no skill; the coordinator reviews the drafts and
files the ones it accepts (docs/self-improve.md).
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_LABEL = "crew:blocked"
DEFAULT_STALE_DAYS = 7


def parse_time(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def label_names(pr):
    return {l["name"] if isinstance(l, dict) else l for l in pr.get("labels") or []}


def classify(pr, now, stale_days, label):
    """Return (failure_class, reason) for a stuck PR, or None."""
    if pr.get("isDraft"):
        return None
    if label in label_names(pr):
        return "blocked-pr", "labelled %s" % label
    updated = parse_time(pr["updatedAt"])
    if now - updated > timedelta(days=stale_days):
        days = (now - updated).days
        return "stale-pr", "no update for %d days (limit %d)" % (days, stale_days)
    return None


def card(pr, failure_class, reason, repo):
    n = pr["number"]
    return "\n".join([
        "### intake: %s on %s#%d" % (failure_class, repo, n),
        "",
        "**Source:** %s#%d (%s) - %s" % (repo, n, pr.get("url", ""), pr.get("title", "")),
        "**Trigger:** weekly-sweep - %s" % reason,
        "**Failure class:** %s" % failure_class,
        "**Proposed fix:** <one line: unblock or close the PR, and what to change "
        "so it does not recur>",
        "**Scope:** repo: - default, product-local until shown otherwise "
        "(triage: confirm or promote)",
        "**Lesson:** none yet",
        "**Findings entry:** none yet",
        "**Decision:** pending",
        "**Decided by:** <CoordinatorBot> on <date>",
        "",
    ])


def build_cards(prs, now, stale_days=DEFAULT_STALE_DAYS, label=DEFAULT_LABEL,
                repo="<owner>/<repo>"):
    cards = []
    for pr in sorted(prs, key=lambda p: p["number"]):
        hit = classify(pr, now, stale_days, label)
        if hit:
            cards.append(card(pr, hit[0], hit[1], repo))
    return cards


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default="-",
                    help="gh pr list JSON file (default: stdin)")
    ap.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS,
                    help="days without an update before a PR is stale "
                         "(default %(default)s)")
    ap.add_argument("--label", default=DEFAULT_LABEL,
                    help="label that marks a blocked PR (default %(default)s)")
    ap.add_argument("--repo", default="<owner>/<repo>",
                    help="repo shown on the cards (default %(default)s)")
    ap.add_argument("--now", metavar="YYYY-MM-DDTHH:MM:SSZ",
                    help="override the current time (for tests)")
    args = ap.parse_args(argv)

    try:
        raw = sys.stdin.read() if args.file == "-" else open(args.file).read()
        prs = json.loads(raw) if raw.strip() else []
        now = parse_time(args.now) if args.now else datetime.now(timezone.utc)
        cards = build_cards(prs, now, args.stale_days, args.label, args.repo)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("intake-sweep: %s" % exc, file=sys.stderr)
        return 2
    if cards:
        print("\n".join(cards))
    return 0


if __name__ == "__main__":
    sys.exit(main())
