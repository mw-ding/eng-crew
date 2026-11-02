#!/usr/bin/env python3
"""Validate a domain role registry against docs/roles-registry.md.

Usage: crew-roles.py FILE [--project FILE]
Without a project, check identity/cap keys against shipped profile and tmux defaults.
Print file:key: reason for each error; exit 1 on invalid input, otherwise 0.
Python 3.11+ stdlib only.
"""
import argparse
import importlib.util
from pathlib import Path
import re
import string
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("crew_config", ROOT / "scripts/crew-config.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)
ID = re.compile(r"[a-z][a-z0-9-]*")
PASSES = {"tmux": {"coordinate", "build", "fix", "review", "validate", "recheck", "land"},
          "grok-bot": {"coordinate", "build", "fix", "review", "validate", "land"}}
EVENTS = {"tmux": {"issue-assigned", "new-head", "ci-passed", "ci-failed", "ci-infra", "review-approved",
                   "review-changes-requested", "pr-merged", "pr-closed", "fix-at-head", "merge-up"},
          "grok-bot": {"issue-assigned", "pr-opened", "new-head", "ci-passed", "ci-failed",
                       "review-requested", "review-approved", "review-changes-requested", "pr-merged", "pr-closed"}}


def validate(data, err, profile, root=ROOT):
    top = cc.check_table(err, "", data, {"schema_version": (int, cc.REQUIRED), "roles": (dict, cc.REQUIRED)})
    if top.get("schema_version") != 1:
        err("schema_version", "expected schema version 1")
    roles, bands, consumers = top.get("roles", {}), [], set()
    if not roles:
        err("roles", "expected at least one role")
    fields = {k: (str, cc.REQUIRED) for k in ("display_name", "identity_key", "marker_role", "engine_source", "window_name", "lifetime")}
    fields.update({k: (dict, cc.REQUIRED) for k in ("inputs", "templates", "events")})
    fields.update(passes=("list[str]", cc.REQUIRED), window_band=(list, cc.REQUIRED))
    fields.update({k: (str, None) for k in ("change_pass", "identity_independent_of", "engine_independent_of", "cap_key")})
    for role, table in roles.items():
        path = "roles." + role
        if not ID.fullmatch(role):
            err(path, "invalid role ID")
        r = cc.check_table(err, path, table, fields)
        for key, value in r.items():
            if isinstance(value, str) and not value.strip():
                err(path + "." + key, "must be nonempty")
        if r.get("identity_key") not in {"identities." + k for k, v in profile.get("identities", {}).items() if isinstance(v, dict)}:
            err(path + ".identity_key", "unresolved identity key")
        if "cap_key" in r:
            cap = dict(cc.leaves(profile)).get(r["cap_key"])
            if type(cap) is not int or cap < 1:
                err(path + ".cap_key", "expected a resolved positive integer cap")
        for key in ("identity_independent_of", "engine_independent_of"):
            if key in r and (r[key] not in roles or r[key] == role):
                err(path + "." + key, "expected another role in this registry")
        cc.check_choice(err, path + ".engine_source", r.get("engine_source"), ["coordinator", "tier"])
        cc.check_choice(err, path + ".lifetime", r.get("lifetime"), ["session", "issue", "pass"])
        passes, inputs = r.get("passes", []), r.get("inputs", {})
        if len(set(passes)) != len(passes) or any(not ID.fullmatch(p) for p in passes):
            err(path + ".passes", "expected distinct pass IDs")
        if "change_pass" in r and r["change_pass"] not in passes:
            err(path + ".change_pass", "must name a supported pass")
        if inputs.keys() != set(passes):
            err(path + ".inputs", "keys must equal passes")
        for p, values in inputs.items():
            if not isinstance(values, list) or any(v not in ("issue", "change") for v in values) or len(set(values)) != len(values):
                err(path + ".inputs." + p, "expected distinct issue/change inputs")
        inputs = {p: values for p, values in inputs.items() if isinstance(values, list)}
        band = r.get("window_band", [])
        if len(band) != 2 or any(type(v) is not int or v < 0 for v in band) or band[0] > band[1]:
            err(path + ".window_band", "expected two ordered nonnegative integers")
        else:
            if any(band[0] <= hi and lo <= band[1] for lo, hi in bands):
                err(path + ".window_band", "overlapping band")
            bands.append(band)
        try:
            for _, field, fmt, conv in string.Formatter().parse(r.get("window_name", "")):
                if field is not None and (field not in ("name", "issue", "change", "round", "pass") or fmt or conv):
                    err(path + ".window_name", "unsupported pattern field")
                if field in ("issue", "change") and any(field not in inputs.get(p, []) for p in passes):
                    err(path + ".window_name", "pattern input unavailable for every pass")
        except ValueError:
            err(path + ".window_name", "invalid pattern")
        for key in ("templates", "events"):
            bindings = r.get(key, {})
            if not bindings or bindings.keys() != r.get("events" if key == "templates" else "templates", {}).keys():
                err(path + "." + key, "expected matching nonempty runtime tables")
            for runtime, values in bindings.items():
                sub = path + "." + key + "." + runtime
                if runtime not in PASSES or not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                    err(sub, "expected a known runtime and list of strings")
                    continue
                cc.check_choices(err, path + ".passes", passes, PASSES[runtime])
                if key == "templates":
                    if not values:
                        err(sub, "expected at least one template")
                    for value in values:
                        p = Path(value)
                        if p.is_absolute() or ".." in p.parts or not (root / p).is_file() or not (root / p).resolve().is_relative_to(root.resolve()):
                            err(sub, "expected an existing repo-relative template without traversal")
                for event in values if key == "events" else []:
                    cc.check_choice(err, sub, event, EVENTS[runtime])
                    consumer = (runtime, event)
                    if consumer in consumers and not (runtime == "grok-bot" and event in ("pr-merged", "pr-closed")):
                        err(sub, "event already has a consumer")
                    consumers.add(consumer)
    cc.scan_tokens(err, "", data)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--project")
    args = ap.parse_args(argv)
    profile = tomllib.loads((ROOT / "profiles/default.toml").read_text())
    profile["runtime"]["options"] = {k: v for k, (_, v) in cc.RUNTIME_OPTIONS["tmux"].items()}
    problems = []
    if args.project:
        profile, _, problems, _ = cc.resolve_profile(args.project)
    if not problems:
        try:
            validate(tomllib.loads(Path(args.file).read_text()), lambda k, v: problems.append(f"{args.file}:{k.lstrip('.')}: {v}"), profile)
        except (OSError, tomllib.TOMLDecodeError) as e:
            problems.append(f"{args.file}:(file): {e}")
    print("\n".join(problems) if problems else f"crew-roles: OK ({args.file})")
    return int(bool(problems))


if __name__ == "__main__":
    sys.exit(main())
