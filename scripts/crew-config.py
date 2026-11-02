#!/usr/bin/env python3
"""Install-time profile (crew.toml) tool for eng-crew. Python 3.11+ stdlib only.

Usage: crew-config.py validate FILE   (a crew.toml profile, or a pack manifest if it has [pack])
       crew-config.py resolve --project FILE [--org-profile FILE]
       paths.pack records an org pack directory relative to the project file.
       crew-config.py sensitive --project FILE [--org-profile FILE] < paths.txt
`validate` checks one profile against the schema; `resolve` merges the config
layers and prints each key with the layer that set it (per-key provenance).
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

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "roles", "eng.toml"), "rb") as f:
    ROLE_REGISTRY = tomllib.load(f)["roles"]

REQUIRED = object()
SENSITIVE_PATHS = [".github/workflows/**", "**/auth/**", "auth/**", "**/secrets/**", "secrets/**",
                   "**/permissions/**", "permissions/**", "**/access-control/**", "access-control/**",
                   "**/migrations/**", "migrations/**", "**/deletions/**", "deletions/**"]
# Operation names per concern, from docs/interfaces.md.
OPERATIONS = {
    "change": ["open", "push", "read-head", "read-diff-paths", "update-from-base", "land", "close"],
    "review": ["post-verdict", "post-narrative", "list-verdicts", "request-rereview"],
    "tracker": ["create-item", "assign", "link", "milestone", "board-status"],
    "state-tags": ["set-clear-read"],
    "markers": ["write", "read", "write-item", "read-item"],
    "ci": ["check-status", "failing-jobs"],
    "events": ["subscribe-or-poll"],
    "owner-channel": ["ask", "notify"],
}
BACKENDS = ["github"]
RUNTIME_OPTIONS = {"grok-bot": {}, "tmux": {"session": (str, None), "builders": (int, 5), "reviewers": (int, 2),
                                        "poll_interval": (int, 60), "train_min": (int, 2), "train_window": (int, 600),
                                        "merge_grant": (str, "none"), "lone_pr_land": (str, "train"),
                                        "train_local_checks": (bool, False), "mirror_deferral": (str, "none"),
                                        "hold_label_blocks": (bool, True), "permission_mode": (str, "bypass"),
                                        "sandbox_env": (str, ""), "notes": (dict, {})}}
PERMISSION_MODES = ["bypass", "auto", "safe"]  # tmux role-window launch (docs/runtimes/tmux.md, #293)
ENGINES = ["claude-code", "codex", "muse", "opencode"]
EFFORTS = ["low", "medium", "high"]
TIER_EFFORT = {"trivial": "low", "default": "medium", "deep": "high"}
CAPABILITY = re.compile(r"supported|unsupported|emulated \(.*\S.*\)")
TYPE_NAMES = {str: "string", int: "integer", bool: "boolean", float: "float", list: "list", dict: "table"}
# Host inventory and project affinity (docs/runtimes/multi-device.md, #204).
HOST_NAME = re.compile(r"[a-z0-9-]{1,63}")
HOST_OS, HOST_ARCH = ["linux", "macos"], ["x86_64", "arm64"]
DEVICES = ["ios-simulator", "ios-device", "android-emulator", "android-device"]
PLACED_PASSES = {"builder": ["build", "fix"], "reviewer": ["review", "validate"]}  # crew spawn passes


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


def check_choices(err, path, values, choices):
    for i, value in enumerate(values):
        check_choice(err, "%s[%d]" % (path, i), value, choices)


def check_platform(err, path, table, fields):
    """os, arch and devices of a host's capabilities or a placement rule's needs."""
    out = check_table(err, path, table, dict({"os": (str, None), "arch": (str, None), "devices": (list, None)}, **fields))
    check_choice(err, path + ".os", out.get("os"), HOST_OS)
    check_choice(err, path + ".arch", out.get("arch"), HOST_ARCH)
    check_choices(err, path + ".devices", out.get("devices", []), DEVICES)
    return out


def validate_hosts(profile, top, err):
    """[hosts.<name>] and [placement]: hosts by overlay network name only, never an address (spec R1)."""
    hosts = {}
    for name, table in top.get("hosts", {}).items():
        path = "hosts." + name
        if not HOST_NAME.fullmatch(name):
            err(path, "expected an overlay network name ([a-z0-9-], 1-63 characters); no IP literal, user@ or :port")
        h = check_table(err, path, table, {"primary": (bool, False), "capabilities": (dict, REQUIRED), "max_runs": (int, REQUIRED),
                                            "roles": (list, None), "root": (str, None), "toolchain_bin": (str, None)})
        caps = check_platform(err, path + ".capabilities", h["capabilities"], {"os": (str, REQUIRED), "arch": (str, REQUIRED),
                                                                            "engines": ("list[str]", REQUIRED)}) if "capabilities" in h else {}
        check_choices(err, path + ".capabilities.engines", caps.get("engines", []), ENGINES)
        check_choices(err, path + ".roles", h.get("roles", []), list(PLACED_PASSES))
        if h.get("max_runs", 1) < 1:
            err(path + ".max_runs", "must be >= 1, got %d" % h["max_runs"])
        hosts[name] = dict(caps, primary=h.get("primary", False), roles=h.get("roles", list(PLACED_PASSES)))
    rt = profile.get("runtime")
    if "hosts" in top and isinstance(rt, dict) and rt.get("name") not in (None, "tmux"):
        err("hosts", "a host inventory needs runtime tmux, got %r" % rt.get("name"))
    primaries = [n for n, h in hosts.items() if h["primary"]]
    if "hosts" in top and len(primaries) != 1:
        err("hosts", "expected exactly one host with primary = true, got %d" % len(primaries))
    if "placement" in top and "hosts" not in top:
        return err("placement", "needs a [hosts] table")
    pl = check_table(err, "placement", top["placement"], {"hosts": ("list[str]", None), "rules": (list, None)}) \
        if "placement" in top else {}
    affinity = pl.get("hosts", primaries[:1])
    for i, name in enumerate(pl.get("hosts", [])):
        if name not in hosts:
            err("placement.hosts[%d]" % i, "names no host in [hosts]: %r" % name)
    for role in PLACED_PASSES if hosts else []:
        if not any(role in hosts[n]["roles"] for n in affinity if n in hosts):
            err("placement.hosts", "no host here takes role %s (default: the primary host)" % role)
    for i, rule in enumerate(pl.get("rules", [])):
        path = "placement.rules[%d]" % i
        r = check_table(err, path, rule, {"role": (str, REQUIRED), "pass": (str, None), "paths": ("list[str]", None),
                                          "needs": (dict, REQUIRED)})
        check_choice(err, path + ".role", r.get("role"), list(PLACED_PASSES))
        if r.get("role") in PLACED_PASSES:
            check_choice(err, path + ".pass", r.get("pass"), PLACED_PASSES[r["role"]])
        needs = check_platform(err, path + ".needs", r["needs"], {}) if "needs" in r else None
        if needs is not None and r.get("role") in PLACED_PASSES and not any(
                r["role"] in h["roles"] and all(h.get(k) == needs[k] for k in ("os", "arch") if k in needs)
                and all(d in h.get("devices", []) for d in needs.get("devices", [])) for h in hosts.values()):
            err(path + ".needs", "no host taking role %s meets these needs" % r["role"])


def check_capabilities(err, path, table, concern, required):
    caps = check_table(err, path, table, {op: (str, REQUIRED if required else None) for op in OPERATIONS[concern]})
    for op, value in caps.items():
        if not CAPABILITY.fullmatch(value):
            err("%s.%s" % (path, op), "expected supported, unsupported or emulated (<how>)")


def validate_manifest(manifest, err):
    """A pack manifest (packs/<name>/manifest.toml): the backend's full capability declaration."""
    top = check_table(err, "", manifest, {"pack": (dict, REQUIRED), "capabilities": (dict, REQUIRED)})
    if "pack" in top:
        pack = check_table(err, "pack", top["pack"], {"name": (str, REQUIRED), "commands": (str, REQUIRED),
                                                     "eng_crew_version": (str, None)})
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
    top = check_table(err, "", profile, dict({k: req for k in ["repo", "runtime", "backends", "identities", "engines", "paths"]},
                                             hosts=(dict, None), placement=(dict, None), sensitive=(dict, None), tools=(dict, None),
                                             size_budget=(dict, None), builder=(dict, None)))
    if "size_budget" in top:
        budgets = check_table(err, "size_budget", top["size_budget"],
                              {r: (int, 16384) for r in ["coordinator", "builder", "reviewer", "synthesizer"]})
        for role, budget in budgets.items():
            if budget < 1:
                err("size_budget." + role, "must be >= 1")
    if "builder" in top:
        builder = check_table(err, "builder", top["builder"], {"precheck": (dict, None)})
        if "precheck" in builder:
            precheck = check_table(err, "builder.precheck", builder["precheck"],
                                  {"enabled": (bool, False), "lint": (str, None), "test": (str, None),
                                   "docs": (str, None), "max_fix_attempts": (int, 2)})
            if precheck.get("max_fix_attempts", 2) < 1:
                err("builder.precheck.max_fix_attempts", "must be >= 1")
    if "tools" in top:
        for name, table in top["tools"].items():
            path = "tools." + name
            tool = check_table(err, path, table, {"running": ("list[str]", REQUIRED),
                                                "installed": ("list[str]", REQUIRED), "pin": (str, None)})
            for key in ("running", "installed"):
                if key in tool and any(not arg.strip() for arg in tool[key]):
                    err(path + "." + key, "command arguments must not be empty")
            if "pin" in tool and not re.fullmatch(r"v?\d+\.\d+\.\d+", tool["pin"]):
                err(path + ".pin", "expected X.Y.Z or vX.Y.Z minimum version")
    if "sensitive" in top:
        rules = check_table(err, "sensitive", top["sensitive"], {"paths": (list, [])})
        for i, pattern in enumerate(rules.get("paths", [])):
            if not isinstance(pattern, str) or not pattern or pattern.startswith("/") or ".." in pattern.split("/"):
                err("sensitive.paths[%d]" % i, "expected a nonempty repo-relative glob without ..")
    if "repo" in top:
        check_table(err, "repo", top["repo"], {"owner": (str, REQUIRED), "name": (str, REQUIRED), "default_branch": (str, "main"),
                                               "control_item": (int, None)})
    if "runtime" in top:
        rt = check_table(err, "runtime", top["runtime"], {"name": (str, REQUIRED), "options": (dict, {}), "timezone": (str, None), "instance": (str, None)})
        check_choice(err, "runtime.name", rt.get("name"), list(RUNTIME_OPTIONS))
        if rt.get("name") in RUNTIME_OPTIONS and "options" in rt:
            opts = check_table(err, "runtime.options", rt["options"], RUNTIME_OPTIONS[rt["name"]])
            check_choice(err, "runtime.options.permission_mode", opts.get("permission_mode"), PERMISSION_MODES)
            check_choice(err, "runtime.options.lone_pr_land", opts.get("lone_pr_land"), ["train", "direct"])
            notes = check_table(err, "runtime.options.notes", opts.get("notes", {}),
                                {r: (list, []) for r in ("coordinator", "builder", "reviewer", "synthesizer")})
            for role, paths in notes.items():
                for i, path in enumerate(paths):
                    if not isinstance(path, str) or not path.strip():
                        err("runtime.options.notes.%s[%d]" % (role, i), "expected a nonempty file path")
            for key, minimum in (("train_min", 2), ("train_window", 1)):
                if key in opts and opts[key] < minimum:
                    err("runtime.options." + key, "must be >= %d, got %d" % (minimum, opts[key]))
    if "backends" in top:
        concerns = check_table(err, "backends", top["backends"], {c: req for c in OPERATIONS})
        for concern, table in concerns.items():
            be = check_table(err, "backends." + concern, table, {"name": (str, REQUIRED), "capabilities": (dict, {})})
            check_choice(err, "backends.%s.name" % concern, be.get("name"), BACKENDS)
            check_capabilities(err, "backends.%s.capabilities" % concern, be.get("capabilities", {}), concern, False)
    if "identities" in top:
        roles = [r["identity_key"].removeprefix("identities.") for r in ROLE_REGISTRY.values()]
        ids = check_table(err, "identities", top["identities"], dict({"owners": ("list[str]", REQUIRED)}, **{r: req for r in roles}))
        for role in roles:
            if role in ids:
                check_table(err, "identities." + role, ids[role], {"gh_user": (str, REQUIRED), "name": (str, None),
                                                                   "title": (str, None), "emoji": (str, None)})
    if "engines" in top:
        sources = list(dict.fromkeys(r["engine_source"] for r in ROLE_REGISTRY.values() if r["engine_source"] != "tier"))
        eng = check_table(err, "engines", top["engines"], dict({s: (str, "claude-code") for s in sources},
                                                               fallback_engine=(str, None), **{t: req for t in TIER_EFFORT}))
        for source in sources:
            check_choice(err, "engines." + source, eng.get(source), ["claude-code", "codex"])
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
        check_table(err, "paths", top["paths"], {"state_dir": (str, REQUIRED), "worktree_root": (str, REQUIRED), "toolchain_bin": (str, None),
                                                  "live_dir": (str, None), "eng_crew": (str, None), "pack": (str, None)})
        pack = top["paths"].get("pack")
        if isinstance(pack, str) and not pack.strip():
            err("paths.pack", "expected a nonempty pack directory")
    if isinstance(profile.get("repo"), dict) and "control_item" in profile["repo"]:
        if type(profile["repo"]["control_item"]) is int and profile["repo"]["control_item"] < 1:
            err("repo.control_item", "must be >= 1")
        runtime = profile.get("runtime")
        instance = runtime.get("instance", "") if isinstance(runtime, dict) else ""
        if not isinstance(instance, str) or not re.fullmatch(r"[a-z0-9-]{1,63}", instance):
            err("runtime.instance", "control_item needs an instance label ([a-z0-9-], 1-63 characters)")
    validate_hosts(profile, top, err)
    scan_tokens(err, "", profile)


# --- resolve (13.11, #123): layered profile with per-key provenance. ---
import copy  # noqa: E402  (kept with the resolve block)
import json  # noqa: E402

DEFAULT_PROFILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles", "default.toml")
CORE_DEFAULTS = {"repo": {"default_branch": "main"},
                 "size_budget": {r: 16384 for r in ["coordinator", "builder", "reviewer", "synthesizer"]},
                 "builder": {"precheck": {"enabled": False, "max_fix_attempts": 2}},
                 "identities": {r: {"name": n, "title": t, "emoji": e} for r, n, t, e in
                                [("coordinator", "Ash", "Coordinator", "🔥"),
                                 ("builder", "Builder", "Builder", "🛠️"),
                                 ("reviewer", "Reviewer", "Reviewer-validator", "🔎"),
                                 ("synthesizer", "Synthesizer", "Synthesizer", "🔀")]},
                 "engines": dict({"coordinator": "claude-code"}, **{t: {"effort": e} for t, e in TIER_EFFORT.items()})}
# Top-level tables whose keys protect an invariant (docs/interfaces.md); a later layer may not drop them.
INVARIANT_TABLES = ["identities", "backends", "engines"]
# Invariants (I1-I5) each operation protects, from the docs/interfaces.md tables.
PROTECTS = {
    "change": {"open": "5", "push": "3", "read-head": "3", "read-diff-paths": "3", "update-from-base": "3",
               "land": "34", "close": "5"},
    "review": {"post-verdict": "123", "post-narrative": "5", "list-verdicts": "134", "request-rereview": "23"},
    "tracker": {op: "5" for op in OPERATIONS["tracker"]},
    "state-tags": {"set-clear-read": "45"},
    "markers": {"write": "135", "read": "135", "write-item": "45", "read-item": "45"},
    "ci": {"check-status": "3", "failing-jobs": "3"},
    "events": {"subscribe-or-poll": "14"},
    "owner-channel": {"ask": "5", "notify": "5"},
}


def leaves(value, path=""):
    if isinstance(value, dict) and value:
        for k, v in value.items():
            yield from leaves(v, "%s.%s" % (path, k) if path else k)
    else:
        yield path, value


def source(prov, key):
    """Layer that set key, its nearest ancestor table or a key under it; None if no layer did."""
    up = key
    while up not in prov and "." in up:
        up = up.rsplit(".", 1)[0]
    return prov.get(up) or next((v for q, v in prov.items() if q.startswith(key + ".")), None)


def merge(dst, src, prov, layer, err, path=""):
    """Tables merge by key; scalars and arrays replace. Dropping an invariant-protecting key is an error."""
    for k, v in src.items():
        p = "%s.%s" % (path, k) if path else k
        if isinstance(dst.get(k), dict) and isinstance(v, dict):
            merge(dst[k], v, prov, layer, err, p)
            continue
        if isinstance(dst.get(k), dict):
            for q, _ in leaves(dst[k], p):
                if q.split(".")[0] in INVARIANT_TABLES:
                    err(layer, q, "cannot remove invariant-protecting key (set by %s)" % source(prov, q))
        dst[k] = copy.deepcopy(v)
        for q, _ in leaves(v, p):
            prov[q] = layer


def cross_check(profile, err):
    """Checks that need the whole resolved profile (docs/interfaces.md, #111)."""
    caps = {(c, op): v for c in OPERATIONS for op, v in profile["backends"][c].get("capabilities", {}).items()}
    kept, lost = set(), {}
    for concern, ops in PROTECTS.items():
        for op, invariants in ops.items():
            for i in invariants:
                if caps.get((concern, op), "unsupported") == "unsupported":
                    word = "unsupported" if (concern, op) in caps else "undeclared (counts as unsupported)"
                    lost.setdefault(i, ("backends.%s.capabilities.%s" % (concern, op), word))
                else:
                    kept.add(i)
    for i in sorted(lost.keys() - kept):
        err(lost[i][0], "%s leaves I%s with no other operation keeping it; profile unsupported "
            "(docs/interfaces.md)" % (lost[i][1], i))
    ids = profile["identities"]
    if ids["reviewer"]["gh_user"] == ids["builder"]["gh_user"] and \
            not caps.get(("review", "post-verdict"), "").startswith("emulated"):
        err("backends.review.capabilities.post-verdict", "reviewer gh_user equals builder gh_user; "
            "a single-identity profile must declare emulated (<how>) (#111)")
    for key, value in profile["runtime"].get("options", {}).items():
        if type(value) is int and value < 1:
            err("runtime.options." + key, "must be >= 1, got %d" % value)


# --- pack manifests (13.15, #127): each backend's capability declaration, under every layer. ---
PACKS_DIR = os.path.join(os.path.dirname(os.path.dirname(DEFAULT_PROFILE)), "packs")


def fold_manifests(merged, prov, files, err):
    """Fill each backend's undeclared operations from packs/<name>/manifest.toml; a layer's value wins."""
    backends = merged.get("backends")
    for concern, be in (backends.items() if isinstance(backends, dict) else []):
        if not isinstance(be, dict) or be.get("name") not in BACKENDS or concern not in OPERATIONS:
            continue
        layer = "pack:" + be["name"]
        files[layer] = os.path.join(PACKS_DIR, be["name"], "manifest.toml")
        try:
            with open(files[layer], "rb") as f:
                declared = tomllib.load(f).get("capabilities")
        except OSError:
            continue  # no manifest: its operations stay undeclared
        except tomllib.TOMLDecodeError as e:
            return err(layer, "(toml)", "invalid TOML (%s)" % e)
        declared = declared.get(concern) if isinstance(declared, dict) else None
        caps = be.setdefault("capabilities", {}) if isinstance(declared, dict) and declared else None
        if not isinstance(caps, dict):
            continue
        for op, value in declared.items():
            if op not in caps:
                caps[op], prov["backends.%s.capabilities.%s" % (concern, op)] = value, layer


def resolve_profile(project, org_profile=None):
    """Layered effective profile: (merged, provenance, problems, layer names).

    provenance maps each leaf key of merged (as `leaves` yields it) to the layer that set it.
    On any problem, merged and provenance are None.
    """
    files = {"core": "core", "default": DEFAULT_PROFILE, "org": org_profile, "project": project,
             None: "(resolved)"}
    problems = []

    def err(layer, key, reason):
        problems.append("%s:%s: %s" % (files[layer], key, reason))

    layers = [("core", copy.deepcopy(CORE_DEFAULTS))]
    for name in ["default", "project", "org"]:
        if files[name] is None or (name == "default" and not os.path.exists(files[name])):
            continue
        try:
            with open(files[name], "rb") as f:
                data = tomllib.load(f)
                layers.append((name, data))
            paths = data.get("paths")
            pack = paths.get("pack") if isinstance(paths, dict) else None
            if name == "project" and files["org"] is None and isinstance(pack, str) and pack.strip():
                directory = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(project)),
                                                        os.path.expanduser(pack)))
                if not os.path.isdir(directory):
                    err("project", "paths.pack", "pack directory missing or unreadable")
                else:
                    org = os.path.join(directory, "profile.toml")
                    if os.path.exists(org):
                        files["org"] = org
        except OSError as e:
            err(name, "(file)", "cannot read (%s)" % e.strerror)
        except tomllib.TOMLDecodeError as e:
            err(name, "(toml)", "invalid TOML (%s)" % e)
    layers.sort(key=lambda layer: ["core", "default", "org", "project"].index(layer[0]))
    merged, prov = {}, {}
    if not problems:
        for name, data in layers:
            merge(merged, data, prov, name, err)
        rt = merged.get("runtime")
        if isinstance(rt, dict) and rt.get("name") in RUNTIME_OPTIONS and isinstance(rt.setdefault("options", {}), dict):
            for key, (_, default) in RUNTIME_OPTIONS[rt["name"]].items():
                if default is not None and key not in rt["options"]:
                    rt["options"][key], prov["runtime.options." + key] = default, "core"
        fold_manifests(merged, prov, files, err)

        def verr(key, reason):
            key = key.lstrip(".")
            err(source(prov, re.sub(r"\[\d+\]", "", key)), key, reason)
        count = len(problems)
        validate(merged, verr)
        if len(problems) == count:
            cross_check(merged, verr)
    names = [name for name, _ in layers]
    if problems:
        return None, None, problems, names
    return merged, {key: source(prov, key) or "core" for key, _ in leaves(merged)}, [], names


def resolve_main(args):
    merged, provenance, problems, layers = resolve_profile(args.project, args.org_profile)
    for p in problems:
        print(p)
    if problems:
        print("crew-config: FAILED (%d problem%s)" % (len(problems), "" if len(problems) == 1 else "s"), file=sys.stderr)
        return 1
    for key, value in leaves(merged):
        print("%s = %s  # %s" % (key, json.dumps(value, ensure_ascii=False), provenance[key]))
    print("crew-config: OK (layers: %s)" % ", ".join(layers), file=sys.stderr)
    return 0


def sensitive_matches(profile, paths):
    """Match repo-relative diff paths against mandatory defaults plus profile additions."""
    rules = SENSITIVE_PATHS + profile.get("sensitive", {}).get("paths", [])
    return {path: [rule for rule in rules if check_repo.glob_regex(rule).fullmatch(path)]
            for path in sorted(set(paths)) if any(check_repo.glob_regex(rule).fullmatch(path) for rule in rules)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="validate a crew.toml profile").add_argument("file")
    rp = sub.add_parser("resolve", help="print the layered effective profile with the layer that set each key")
    rp.add_argument("--project", required=True)
    rp.add_argument("--org-profile")
    sp = sub.add_parser("sensitive", help="classify newline-separated diff paths from stdin; print JSON")
    sp.add_argument("--project", required=True)
    sp.add_argument("--org-profile")
    args = ap.parse_args(argv)
    if args.cmd == "sensitive":
        profile, _, problems, _ = resolve_profile(args.project, args.org_profile)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        matches = sensitive_matches(profile, sys.stdin.read().splitlines())
        print(json.dumps({"label": "crew:sensitive" if matches else None, "matches": matches}))
        return 0
    if args.cmd == "resolve":
        return resolve_main(args)
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
