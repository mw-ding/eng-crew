#!/usr/bin/env python3
"""Resolve an item's recorded rigor (offline; stdlib only).

Usage: item-flavor.py --project FILE --issue N [--default NAME] < bodies.json
Input: JSON list of comment body strings, oldest first, from the coordinator.
Output: flavor, default, status and project_gap as JSON. Refusal exits 1;
missing records use thorough and flag flavor-missing. express is accepted as an item flavor
(a lowering, so it needs Reason:) but never as a default. No writes or gate changes.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location("crew_config", Path(__file__).with_name("crew-config.py"))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def resolve_item(profile, issue, bodies, default=None):
    flavors = dict(config.FLAVOR_PRESETS)
    for name, knobs in profile.get("flavor", {}).get("custom", {}).items():
        flavors[name] = dict(flavors[knobs["base"]], **{k: v for k, v in knobs.items() if k != "base"})
    default = default or profile.get("flavor", {}).get("name", config.UNSET_FLAVOR)
    if default not in flavors or default == "express":
        raise ValueError("unknown default flavor: " + default)
    record = None
    for body in bodies:
        for marker in re.findall(r"<!-- crew:v1 (.*?) -->", body):
            fields = dict(re.findall(r"(\S+)=(\S+)", marker))
            if fields.get("role") == "coordinator" and fields.get("pass") == "flavor" and fields.get("issue") == str(issue):
                record = fields, body
    if record is None:
        return dict(flavor="thorough", default=default, status="flavor-missing")
    fields, body = record
    chosen = fields.get("flavor")
    if chosen not in flavors or fields.get("default") not in flavors or fields.get("default") == "express":
        return dict(flavor=default, default=default, status="flavor-refused")
    candidate, baseline = flavors[chosen], flavors[default]
    lower = any(config.FLAVOR_ORDER[k].index(candidate[k]) > config.FLAVOR_ORDER[k].index(baseline[k])
                for k in config.FLAVOR_ORDER if k != "builder")
    lower = lower or any(a < b for a, b in zip(candidate["caps"], baseline["caps"]))
    reasons = re.findall(r"^Reason:[ \t]*(.*\S)[ \t]*$", body, re.M)
    if lower and not reasons:
        return dict(flavor=default, default=default, status="flavor-refused")
    return dict(flavor=chosen, default=default, status="recorded")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True)
    parser.add_argument("--org-profile")
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--default", help="resolved class default for explicitly named item paths")
    args = parser.parse_args(argv)
    profile, provenance, problems, _ = config.resolve_profile(args.project, args.org_profile)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    try:
        result = resolve_item(profile, args.issue, json.load(sys.stdin), args.default)
    except (ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    result["project_gap"] = "unset: flagged" in provenance["flavor.name"]
    print(json.dumps(result))
    return 1 if result["status"] == "flavor-refused" else 0


if __name__ == "__main__":
    sys.exit(main())
