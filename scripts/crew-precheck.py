#!/usr/bin/env python3
"""Check the enabled builder pre-review gate from a live GitHub PR JSON record.

Usage: gh pr view N --json body,reviews,headRefOid | python3 scripts/crew-precheck.py --project FILE [--org-profile FILE]
       [--item ID] [--change ID]
Exit 0 when disabled or the latest builder marker at head has all seven steps
pass/n/a; exit 1 for missing, stale, malformed or failed results. Callers check
inline N/A reasons and recorded owner per-change overrides independently.
This checks a report, not proof, approval, CI or other merge gates.

--pass selfgate checks an express change's selfgate record instead (protocol §3):
gh pr view N --json number,body,reviews,headRefOid,commits | ... --pass selfgate
Exit 0 only when the latest builder pass=selfgate marker at head is well formed,
says verdict=pass with open=0 and checks=pass, names the profile's effective
selfgate_engine as mode and, under different, a reviewer engine unlike the
record's builder engine and every commit's Engine: trailer. Callers resolve
whether the change is express (class-flavor --express) independently.

Ids (protocol.md#proposed-precheck-and-selfgate-id-keys, #876): issue= and pr= fully match the resolved ids.item and
ids.change patterns from the backend maps, all digits when none is declared. ids.marker_key = item keys the selfgate
record on issue= instead of pr=. --item (the linked tracker item) and --change (the change, else the record's
number) are the independently known keys a marker must name; a bad argument exits 1 before the record is read.
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
SELFGATE_FIELDS = {"role", "pass", "sha", "base", "round", "verdict", "mode", "builder-engine",
                   "reviewer-engine", "reviews", "findings", "open", "checks"}
ID_KEYS = ("item", "change")


def id_patterns(ids):
    """The resolved ids table as {item, change: pattern or None, marker_key}; None keeps today's all-digits check."""
    return dict({key: ids.get(key) for key in ID_KEYS}, marker_key=ids.get("marker_key", "change"))


def id_ok(value, pattern):
    return bool(re.fullmatch(pattern, value)) if pattern else value.isdigit()


def builder_markers(record, builder, name):
    """Return (fields, pairs) at head of the PR body's and signed builder reviews' pass=name markers, oldest first.

    Raises LookupError with the gate result when the head is malformed or no marker is at head.
    """
    head = record.get("headRefOid", "")
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise LookupError("malformed head")
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
            if fields.get("role") != "builder" or fields.get("pass") != name:
                continue
            seen = True
            if fields.get("sha") == head:
                at_head.append((fields, pairs))
    if not at_head:
        raise LookupError("stale marker" if seen else "missing marker")
    return at_head


def check(record, builder, ids=None, item=None):
    ids = ids or id_patterns({})
    try:
        fields, pairs = builder_markers(record, builder, "precheck")[-1]
    except LookupError as exc:
        return str(exc)
    if (len(fields) != len(pairs) or fields.get("round") != "n/a"
            or fields.get("verdict") != "n/a" or not id_ok(fields.get("issue", ""), ids["item"])
            or (ids["marker_key"] == "item" and "pr" in fields)
            or any(fields.get(step) not in ("pass", "fail", "n/a") for step in STEPS)):
        return "malformed marker"
    if item is not None and fields["issue"] != item:
        return "marker for %s, expected %s" % (fields["issue"], item)
    failed = [step for step in STEPS if fields[step] == "fail"]
    return "failed steps: " + ", ".join(failed) if failed else "pass"


def check_selfgate(record, builder, mode, ids=None, item=None, change=None):
    ids = ids or id_patterns({})
    try:
        fields, pairs = builder_markers(record, builder, "selfgate")[-1]
    except LookupError as exc:
        return str(exc)
    cap = config.FLAVOR_PRESETS["express"]["caps"][0]
    counts = [fields.get(key, "") for key in ("reviews", "findings", "open")]
    key, concern = ("issue", "item") if ids["marker_key"] == "item" else ("pr", "change")
    expected = item if concern == "item" else change if change is not None else record.get("number")
    if (len(fields) != len(pairs) or set(fields) != SELFGATE_FIELDS | {key}
            or not id_ok(fields[key], ids[concern])
            or not re.fullmatch(r"[0-9a-f]{40}", fields["base"]) or fields["round"] != "n/a"
            or fields["verdict"] not in ("pass", "changes") or fields["mode"] not in config.SELFGATE_ENGINES
            or not all(re.fullmatch(r"[^\s/]+/\S+", fields[k]) for k in ("builder-engine", "reviewer-engine"))
            or not all(n.isdigit() for n in counts) or not 1 <= int(counts[0]) <= cap
            or int(counts[2]) > int(counts[1]) or fields["checks"] not in ("pass", "fail")):
        return "malformed marker"
    if expected is None:
        return "missing %s key" % concern
    if fields[key] != str(expected):
        return "marker for %s, expected %s" % (fields[key], expected)
    if fields["verdict"] == "changes":
        return "verdict changes"
    if counts[2] != "0":
        return "verdict pass with open findings"
    if fields["checks"] != "pass":
        return "verdict pass with failed checks"
    if fields["mode"] != mode:
        return "mode %s, effective selfgate_engine %s" % (fields["mode"], mode)
    reviewer = fields["reviewer-engine"].split("/")[0]
    builders = {fields["builder-engine"].split("/")[0]}
    builders |= {m for commit in record.get("commits", [])
                 for m in re.findall(r"(?m)^Engine:\s*(\S+)", commit.get("messageBody", ""))}
    if mode == "different" and reviewer in builders:
        return "engine clash: reviewer %s is a builder engine" % reviewer
    return "pass"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--org-profile")
    ap.add_argument("--pass", dest="name", choices=["precheck", "selfgate"], default="precheck")
    ap.add_argument("--item", help="the tracker item the change is linked to (on GitHub, the issue it closes)")
    ap.add_argument("--change", help="the change under check; default: the record's number")
    args = ap.parse_args(argv)
    profile, _, problems, _ = config.resolve_profile(args.project, args.org_profile)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    ids = id_patterns(profile.get("ids", {}))
    for key in ID_KEYS:
        value = getattr(args, key)
        if value is not None and not id_ok(value, ids[key]):
            print("--%s: %r does not match %s pattern %s" % (key, value, key, ids[key] or "(digits)"), file=sys.stderr)
            return 1
    if args.name == "selfgate":
        try:
            result = check_selfgate(json.load(sys.stdin), profile["identities"]["builder"],
                                    profile["flavor"].get("selfgate_engine", "different"), ids, args.item, args.change)
        except (ValueError, TypeError, AttributeError):
            result = "malformed PR record"
        print("selfgate: " + result)
        return 0 if result == "pass" else 1
    if not profile["builder"]["precheck"]["enabled"]:
        print("precheck: disabled")
        return 0
    try:
        result = check(json.load(sys.stdin), profile["identities"]["builder"], ids, args.item)
    except (ValueError, TypeError, AttributeError):
        result = "malformed PR record"
    print("precheck: " + result)
    return 0 if result == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
