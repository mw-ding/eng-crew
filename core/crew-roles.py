#!/usr/bin/env python3
"""Validate a domain's role definitions, roles/<domain>/<role>.toml, against docs/roles-registry.md.

Usage: crew-roles.py DIR [--project FILE]
Each file is one role's definition, its file stem the role ID; the registry is their union.
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
spec = importlib.util.spec_from_file_location("crew_config", ROOT / "core/crew-config.py")
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)
ID = re.compile(r"[a-z][a-z0-9-]*")
PASSES = {"tmux": {"coordinate", "build", "fix", "review", "validate", "recheck", "land", "research"},
          "grok-bot": {"coordinate", "build", "fix", "review", "validate", "land"}}
EVENTS = {"tmux": {"issue-assigned", "new-head", "ci-passed", "ci-failed", "ci-infra", "review-approved",
                   "review-changes-requested", "pr-merged", "pr-closed", "fix-at-head", "merge-up", "selfgate-passed"},
          "grok-bot": {"issue-assigned", "pr-opened", "new-head", "ci-passed", "ci-failed",
                       "review-requested", "review-approved", "review-changes-requested", "pr-merged", "pr-closed"}}
POLICIES = {"always-on": "min = max", "elastic": "1 <= min < max", "ephemeral": "min = 0"}
WAKES = {"manual", "routine"} | EVENTS["tmux"]  # manual: `crew up <role>`; routine: a due routine (#1247)


def check_lifecycle(err, path, r):
    """A role's lifecycle table (#1231): policy, instance bounds, idle TTL in seconds and wake triggers."""
    life = cc.check_table(err, path, r["lifecycle"], {
        "policy": (str, cc.REQUIRED), "min": (int, cc.REQUIRED), "max": (int, cc.REQUIRED),
        "idle_ttl": (int, cc.REQUIRED), "wake": ("list[str]", cc.REQUIRED)})
    if r.get("engine_source") != "tier" or "cap_key" in r:
        err(path, "expected a tier-sourced role without cap_key (max is its cap)")
    if "policy" in life:
        cc.check_choice(err, path + ".policy", life["policy"], list(POLICIES))
    lo, hi, band = life.get("min", 0), life.get("max", 1), r.get("window_band", [0, 0])
    if lo < 0 or hi < max(lo, 1) or len(band) == 2 and all(type(v) is int for v in band) and hi > band[1] - band[0] + 1:
        err(path + ".max", "expected 0 <= min <= max, max >= 1 and max within window_band")
    elif {"always-on": lo != hi, "elastic": not 1 <= lo < hi, "ephemeral": lo != 0}.get(life.get("policy")):
        err(path + ".policy", "%s expects %s" % (life["policy"], POLICIES[life["policy"]]))
    if life.get("idle_ttl", 0) < 0:
        err(path + ".idle_ttl", "expected nonnegative seconds (0 never idles out)")
    wake = life.get("wake", [])
    if len(set(wake)) != len(wake):
        err(path + ".wake", "expected distinct triggers")
    cc.check_choices(err, path + ".wake", wake, sorted(WAKES))
    passes = r.get("passes") or [None]
    try:
        fields = {f for _, f, _, _ in string.Formatter().parse(r.get("window_name", "")) if f is not None}
    except ValueError:
        fields = set()
    if r.get("inputs", {}).get(passes[0]) != [] or not fields <= {"name", "pass"}:
        err(path, "expected a first pass with no inputs and a window_name of only {name} and {pass}")


def validate(roles, err, profile, root=ROOT):
    """roles: {role ID: its file's table}; err(key, reason) gets keys as <role>.<key>."""
    bands, consumers = [], set()
    if not roles:
        err("(dir)", "expected at least one role")
    fields = {"schema_version": (int, cc.REQUIRED)}
    fields.update({k: (str, cc.REQUIRED) for k in ("display_name", "identity_key", "marker_role", "engine_source", "window_name", "lifetime")})
    fields.update({k: (dict, cc.REQUIRED) for k in ("inputs", "templates", "events")})
    fields.update(passes=("list[str]", cc.REQUIRED), window_band=(list, cc.REQUIRED))
    fields.update({k: (str, None) for k in ("change_pass", "identity_independent_of", "engine_independent_of", "cap_key")})
    fields.update(rank=(int, None), identity_defaults=(dict, cc.REQUIRED), identity_optional=(bool, None), cap_default=(int, None),
                  cap_min=(int, None), default_tier=(str, None), completion=(str, None), relay=(str, None),
                  placement=("list[str]", None), discovery=(dict, None), lifecycle=(dict, None),
                  knowledge=("list[str]", None))
    for role, table in roles.items():
        path = role
        if not ID.fullmatch(role):
            err(path, "invalid role ID")
        r = cc.check_table(err, path, table, fields)
        if "schema_version" in r and r["schema_version"] != 1:
            err(path + ".schema_version", "expected schema version 1")
        if "rank" in r and r["rank"] < 1:
            err(path + ".rank", "expected a positive integer")
        for key, value in r.items():
            if isinstance(value, str) and not value.strip():
                err(path + "." + key, "must be nonempty")
        if r.get("identity_key") not in {"identities." + k for k, v in profile.get("identities", {}).items() if isinstance(v, dict)} and \
                not r.get("identity_optional"):
            err(path + ".identity_key", "unresolved identity key")
        cc.check_table(err, path + ".identity_defaults", r.get("identity_defaults", {}),
                       {k: (str, cc.REQUIRED) for k in ("name", "title", "emoji")})
        if "cap_key" in r:
            cap = dict(cc.leaves(profile)).get(r["cap_key"], r.get("cap_default"))
            if type(cap) is not int or cap < r.get("cap_min", 1):
                err(path + ".cap_key", "expected a resolved integer cap >= cap_min (default 1)")
        if ("cap_default" in r or "cap_min" in r) and not re.fullmatch(r"runtime\.options\.[a-z_]+", r.get("cap_key", "")):
            err(path + ".cap_key", "cap_default and cap_min need a runtime.options.<name> cap_key")
        if r.get("cap_min", 1) not in (0, 1):
            err(path + ".cap_min", "expected 0 or 1")
        if r.get("cap_default", 1) < r.get("cap_min", 1):
            err(path + ".cap_default", "must be >= cap_min")
        if "default_tier" in r:
            cc.check_choice(err, path + ".default_tier", r["default_tier"], list(cc.TIER_EFFORT))
        spawned = r.get("engine_source") == "tier"
        for key, choices in (("completion", ["done", "failed"]), ("relay", ["core", "coordinator"])):
            if spawned and key not in r:
                err(path + "." + key, "required for a tier-sourced role")
            elif not spawned and key in r:
                err(path + "." + key, "only a tier-sourced role has a run to complete")
            elif key in r:
                cc.check_choice(err, path + "." + key, r[key], choices)
        if r.get("relay") == "coordinator" and r.get("completion") != "done":
            err(path + ".relay", "relay = coordinator needs completion = done")
        if "placement" in r and (not spawned or any(p not in r.get("passes", []) for p in r["placement"])):
            err(path + ".placement", "expected passes of a tier-sourced role")
        if "knowledge" in r and (len(set(r["knowledge"])) != len(r["knowledge"]) or not all(ID.fullmatch(k) for k in r["knowledge"])):
            err(path + ".knowledge", "expected distinct knowledge source names")
        for runtime, name in r.get("discovery", {}).items():
            if runtime not in PASSES or not isinstance(name, str) or not ID.fullmatch(name):
                err(path + ".discovery." + runtime, "expected a known runtime and a brief name")
        for key in ("identity_independent_of", "engine_independent_of"):
            if key in r and (r[key] not in roles or r[key] == role):
                err(path + "." + key, "expected another role in this registry")
        cc.check_choice(err, path + ".engine_source", r.get("engine_source"), ["coordinator", "tier"])
        if "lifecycle" in r:
            check_lifecycle(err, path + ".lifecycle", r)
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
    cc.scan_tokens(err, "", roles)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--project")
    args = ap.parse_args(argv)
    profile = tomllib.loads((ROOT / "profiles/default.toml").read_text())
    profile["runtime"]["options"] = {k: v for k, (_, v) in cc.RUNTIME_OPTIONS["tmux"].items()}
    problems, roles, directory = [], {}, Path(args.dir)
    if args.project:
        profile, _, problems, _ = cc.resolve_profile(args.project)
    for path in sorted(directory.glob("*.toml")) if not problems else []:
        try:
            roles[path.stem] = tomllib.loads(path.read_text())
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
            problems.append(f"{path}:(file): {e}")

    def err(key, reason):
        role, _, rest = key.lstrip(".").partition(".")
        problems.append(f"{directory / (role + '.toml')}:{rest or '(file)'}: {reason}" if role in roles else
                        f"{directory}:{key.lstrip('.')}: {reason}")
    if not problems:
        validate(roles, err, profile)
    print("\n".join(problems) if problems else f"crew-roles: OK ({args.dir})")
    return int(bool(problems))


if __name__ == "__main__":
    sys.exit(main())
