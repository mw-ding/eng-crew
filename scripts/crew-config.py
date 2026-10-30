#!/usr/bin/env python3
"""Install-time profile (crew.toml) tool for eng-crew. Python 3.11+ stdlib only.

Usage: crew-config.py validate FILE   (a crew.toml profile, or a pack manifest if it has [pack])
Every problem prints as `file:key: reason`; exit 1 if any, else 0.
Schema: docs/profile.md.
"""
import argparse
import importlib.util
import os
import re
import sys
import tomllib

_spec = importlib.util.spec_from_file_location(
    "check_repo", os.path.join(os.path.dirname(os.path.abspath(__file__)), "check-repo.py"))
check_repo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_repo)

REQUIRED = object()
# Operation names per concern, from docs/interfaces.md.
OPERATIONS = {
    "change": ["open", "push", "read-head", "read-diff-paths", "update-from-base", "land", "close"],
    "review": ["post-verdict", "post-narrative", "list-verdicts", "request-rereview"],
    "tracker": ["create-item", "assign", "link", "milestone", "board-status"],
    "state-tags": ["set-clear-read"],
    "markers": ["write", "read"],
    "ci": ["check-status", "failing-jobs"],
    "events": ["subscribe-or-poll"],
    "owner-channel": ["ask", "notify"],
}
BACKENDS = ["github"]
RUNTIME_OPTIONS = {"grok-bot": {}, "tmux": {"session": (str, None), "builders": (int, 5), "reviewers": (int, 2)}}
ENGINES = ["claude-code", "codex", "muse", "opencode"]
EFFORTS = ["low", "medium", "high"]
TIER_EFFORT = {"trivial": "low", "default": "medium", "deep": "high"}
CAPABILITY = re.compile(r"supported|unsupported|emulated \(.*\S.*\)")
TYPE_NAMES = {str: "string", int: "integer", bool: "boolean", float: "float", list: "list", dict: "table"}


def type_name(value):
    return TYPE_NAMES.get(type(value), type(value).__name__)


def token_reasons(value):
    """Secret-scan reasons for one string, using check-repo.py's patterns."""
    reasons = [reason for _, rx, reason in check_repo.PATTERNS if rx.search(value)]
    if any(not check_repo.is_placeholder(m.group(1)) for m in check_repo.BEARER.finditer(value)):
        reasons.append("bearer auth header with a literal value")
    if any(not (check_repo.is_placeholder(m.group(1)) and check_repo.is_placeholder(m.group(2)))
           for m in check_repo.URL_CRED.finditer(value)):
        reasons.append("URL with embedded credentials")
    return reasons


def scan_tokens(err, path, value):
    if isinstance(value, dict):
        for k, v in value.items():
            scan_tokens(err, "%s.%s" % (path, k) if path else k, v)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            scan_tokens(err, "%s[%d]" % (path, i), v)
    elif isinstance(value, str):
        for reason in token_reasons(value):
            err(path, "token-shaped value (%s); refer to credentials by mechanism" % reason)


def check_table(err, path, table, fields):
    """Check keys of one table against {key: (type, default-or-REQUIRED)}; return checked values."""
    if not isinstance(table, dict):
        err(path, "expected table, got %s" % type_name(table))
        return {}
    for key in sorted(table.keys() - fields.keys()):
        err("%s.%s" % (path, key), "unknown key")
    out = {}
    for key, (typ, default) in fields.items():
        sub = "%s.%s" % (path, key)
        if key not in table:
            if default is REQUIRED:
                err(sub, "missing required key")
            continue
        value = table[key]
        if typ == "list[str]":
            if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
                err(sub, "expected list of strings, got %s" % type_name(value))
                continue
        elif type(value) is not typ:
            err(sub, "expected %s, got %s" % (TYPE_NAMES[typ], type_name(value)))
            continue
        out[key] = value
    return out


def check_choice(err, path, value, choices):
    if value is not None and value not in choices:
        err(path, "unknown value %r (expected one of: %s)" % (value, ", ".join(choices)))


def check_capabilities(err, path, table, concern, required):
    caps = check_table(err, path, table, {op: (str, REQUIRED if required else None) for op in OPERATIONS[concern]})
    for op, value in caps.items():
        if not CAPABILITY.fullmatch(value):
            err("%s.%s" % (path, op), "expected supported, unsupported or emulated (<how>)")


def validate_manifest(manifest, err):
    """A pack manifest (packs/<name>/manifest.toml): the backend's full capability declaration."""
    top = check_table(err, "", manifest, {"pack": (dict, REQUIRED), "capabilities": (dict, REQUIRED)})
    if "pack" in top:
        pack = check_table(err, "pack", top["pack"], {"name": (str, REQUIRED), "commands": (str, REQUIRED)})
        check_choice(err, "pack.name", pack.get("name"), BACKENDS)
    if "capabilities" in top:
        concerns = check_table(err, "capabilities", top["capabilities"], {c: (dict, REQUIRED) for c in OPERATIONS})
        for concern, table in concerns.items():
            check_capabilities(err, "capabilities." + concern, table, concern, True)
    scan_tokens(err, "", manifest)


def validate(profile, err):
    if "pack" in profile:
        return validate_manifest(profile, err)
    req = (dict, REQUIRED)
    top = check_table(err, "", profile, {k: req for k in ["repo", "runtime", "backends", "identities", "engines", "paths"]})
    if "repo" in top:
        check_table(err, "repo", top["repo"], {"owner": (str, REQUIRED), "name": (str, REQUIRED), "default_branch": (str, "main")})
    if "runtime" in top:
        rt = check_table(err, "runtime", top["runtime"], {"name": (str, REQUIRED), "options": (dict, {}), "timezone": (str, None)})
        check_choice(err, "runtime.name", rt.get("name"), list(RUNTIME_OPTIONS))
        if rt.get("name") in RUNTIME_OPTIONS and "options" in rt:
            check_table(err, "runtime.options", rt["options"], RUNTIME_OPTIONS[rt["name"]])
    if "backends" in top:
        concerns = check_table(err, "backends", top["backends"], {c: req for c in OPERATIONS})
        for concern, table in concerns.items():
            be = check_table(err, "backends." + concern, table, {"name": (str, REQUIRED), "capabilities": (dict, {})})
            check_choice(err, "backends.%s.name" % concern, be.get("name"), BACKENDS)
            check_capabilities(err, "backends.%s.capabilities" % concern, be.get("capabilities", {}), concern, False)
    if "identities" in top:
        roles = ["coordinator", "builder", "reviewer", "synthesizer"]
        ids = check_table(err, "identities", top["identities"], dict({"owners": ("list[str]", REQUIRED)}, **{r: req for r in roles}))
        for role in roles:
            if role in ids:
                check_table(err, "identities." + role, ids[role], {"gh_user": (str, REQUIRED), "name": (str, None)})
    if "engines" in top:
        eng = check_table(err, "engines", top["engines"], dict({"coordinator": (str, "claude-code"), "fallback_engine": (str, None)}, **{t: req for t in TIER_EFFORT}))
        check_choice(err, "engines.coordinator", eng.get("coordinator"), ["claude-code", "codex"])
        check_choice(err, "engines.fallback_engine", eng.get("fallback_engine"), ENGINES)
        for tier in TIER_EFFORT:
            if tier in eng:
                t = check_table(err, "engines." + tier, eng[tier], {"order": ("list[str]", REQUIRED), "effort": (str, None)})
                check_choice(err, "engines.%s.effort" % tier, t.get("effort"), EFFORTS)
                for i, entry in enumerate(t.get("order", [])):
                    if entry.partition("/")[0] not in ENGINES or not entry.partition("/")[2]:
                        err("engines.%s.order[%d]" % (tier, i), "unknown engine %r (expected <engine>/<model>, engine one of: %s)"
                            % (entry.partition("/")[0], ", ".join(ENGINES)))
    if "paths" in top:
        check_table(err, "paths", top["paths"], {"state_dir": (str, REQUIRED), "worktree_root": (str, REQUIRED), "toolchain_bin": (str, None)})
    scan_tokens(err, "", profile)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="validate a crew.toml profile").add_argument("file")
    args = ap.parse_args(argv)
    problems = []

    def err(key, reason):
        problems.append("%s:%s: %s" % (args.file, key.lstrip("."), reason))

    try:
        with open(args.file, "rb") as f:
            validate(tomllib.load(f), err)
    except OSError as e:
        err("(file)", "cannot read (%s)" % e.strerror)
    except tomllib.TOMLDecodeError as e:
        err("(toml)", "invalid TOML (%s)" % e)
    for p in problems:
        print(p)
    if problems:
        print("crew-config: FAILED (%d problem%s)" % (len(problems), "" if len(problems) == 1 else "s"), file=sys.stderr)
        return 1
    print("crew-config: OK (%s)" % args.file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
