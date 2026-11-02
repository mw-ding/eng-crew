#!/usr/bin/env python3
"""Check the enabled builder pre-review gate from a live GitHub PR JSON record.

Usage: gh pr view N --json body,reviews,headRefOid | python3 scripts/crew-precheck.py --project FILE [--org-profile FILE]
Exit 0 when disabled or the latest builder marker at head has all seven steps
pass/n/a; exit 1 for missing, stale, malformed or failed results. Callers check
inline N/A reasons and recorded owner per-change overrides independently.
This checks a report, not proof, approval, CI or other merge gates.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("crew_config", os.path.join(HERE, "crew-config.py"))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
STEPS = ("rebase", "lint", "tests", "build", "self-review", "docs", "evidence")


def check(record, builder):
    head = record.get("headRefOid", "")
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        return "malformed head"
    texts = [record.get("body", "")]
    texts += [review.get("body", "") for review in
              sorted(record.get("reviews", []), key=lambda r: r.get("submittedAt", ""))
              if review.get("author", {}).get("login") == builder["gh_user"]
              and re.search(r"(?m)^— .* " + re.escape(builder["name"]) + r" \(", review.get("body", ""))]
    at_head, seen = [], False
    for text in texts:
        for raw in re.findall(r"<!-- crew:v1\s+(.*?)\s*-->", text, re.DOTALL):
            pairs = re.findall(r"([^\s=]+)=([^\s]+)", raw)
            fields = dict(pairs)
            if fields.get("role") != "builder" or fields.get("pass") != "precheck":
                continue
            seen = True
            if fields.get("sha") == head:
                at_head.append((fields, pairs))
    if not at_head:
        return "stale marker" if seen else "missing marker"
    fields, pairs = at_head[-1]
    if (len(fields) != len(pairs) or fields.get("round") != "n/a"
            or fields.get("verdict") != "n/a" or not fields.get("issue", "").isdigit()
            or any(fields.get(step) not in ("pass", "fail", "n/a") for step in STEPS)):
        return "malformed marker"
    failed = [step for step in STEPS if fields[step] == "fail"]
    return "failed steps: " + ", ".join(failed) if failed else "pass"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--org-profile")
    args = ap.parse_args(argv)
    profile, _, problems, _ = config.resolve_profile(args.project, args.org_profile)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if not profile["builder"]["precheck"]["enabled"]:
        print("precheck: disabled")
        return 0
    try:
        result = check(json.load(sys.stdin), profile["identities"]["builder"])
    except (ValueError, TypeError, AttributeError):
        result = "malformed PR record"
    print("precheck: " + result)
    return 0 if result == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
