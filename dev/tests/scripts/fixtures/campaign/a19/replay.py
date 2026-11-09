#!/usr/bin/env python3
"""A19 declared-operation replay: `replay.py SOURCE LEDGER [--no-tests]` checks the ledger against what SOURCE ships
and declares, then replays every oracle. Enumeration: the discovered harness and session backend adapters, the
harness adapter-module table rows and the session backend Operations and Capability rows must each match the ledger
exactly. Each adapter x row entry is `oracle` (the row's names present; tests replay it), `default` (absent; the spec's
default applies and tests prove it), `gap` (a quote from its spec section, or an undocumented `finding`) or
`unsupported` (absent; a quote from its spec section). Refusal and ambiguous `cases` and runtime gaps carry the same
spec link. `live` holds one entry per harness x backend binding and per runtime's mirror/watch: `evidence` (the source
SHA, versions and an https `link` to the smoke capture), `fail` (the same plus the filed `finding`), a `block` naming
at least installation, version, account and sandbox, with its `link`, or `unsupported` with a quote. Every spec anchor
and test must exist; the tests run once per file. Exit 0 only when all of it holds."""
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys

src, ledger, run_tests = sys.argv[1], json.load(open(sys.argv[2])), "--no-tests" not in sys.argv
errors, tests = [], {}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(src, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def section(spec):
    """The lines under spec's heading (`path#slug`), up to the next heading of the same or a higher level."""
    path, slug = spec.split("#")
    lines = open(os.path.join(src, path)).read().split("\n")
    for i, line in enumerate(lines):
        m = re.match(r"(#+) (.*)", line)
        if m and re.sub(r"[^\w\- ]", "", m.group(2).lower()).replace(" ", "-") == slug:
            end = next((j for j in range(i + 1, len(lines)) if re.match(r"#{1,%d} " % len(m.group(1)), lines[j])), None)
            return lines[i:end]
    errors.append("spec %s: no such heading" % spec)
    return []


def flat(spec):
    return " ".join(" ".join(section(spec)).split())


def rows(spec, header):
    """First cells of the table under spec whose header row starts with `| header |`."""
    lines = section(spec)
    start = next(i for i, line in enumerate(lines) if line.startswith("| %s |" % header)) + 2
    out = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        out.append(line.split("|")[1].strip())
    return out


def check(where, entry, present, spec):
    status = next(k for k in ("oracle", "default", "gap", "unsupported") if k in entry)
    spec = entry.get("spec", spec)
    quote = entry[status] if status in ("gap", "unsupported") else None
    if status == "oracle" and not present or status in ("default", "unsupported") and present:
        errors.append("%s: %s but the adapter %s it" % (where, status, "lacks" if status == "oracle" else "declares"))
    for q in (quote, entry.get("accepted")):
        if q and " ".join(q.split()) not in flat(spec):
            errors.append("%s: quote %r not in %s" % (where, q, spec))
    if status == "gap" and not quote and not entry.get("finding"):
        errors.append("%s: gap needs a spec quote or a finding" % where)
    if status in ("oracle", "default") and not entry.get("tests"):
        errors.append("%s: %s needs tests" % (where, status))
    for t in entry.get("tests", []):
        tests.setdefault(t, []).append(where)
    print("%-44s %-11s %s %s" % (where, entry.get("kind", status).upper(), spec, entry.get("finding", "")))
    return status
    return status


def replay(kind, adapters, declared, present):
    """One entry per discovered adapter and declared row; the ledger names neither more nor fewer."""
    led = ledger[kind]
    if sorted(led["adapters"]) != sorted(adapters):
        errors.append("%s adapters: ledger %s, shipped %s" % (kind, sorted(led["adapters"]), sorted(adapters)))
    for name, mod in sorted(adapters.items()):
        entries = led["adapters"].get(name, {})
        rows_named = sorted(k for k in entries if k != "spec")
        if rows_named != sorted(declared):
            errors.append("%s %s rows: ledger %s, declared %s" % (kind, name, rows_named, sorted(declared)))
        for row in declared:
            if row in entries:
                yield check("%s %s" % (name, row), entries[row], present(mod, row), entries["spec"])


H, S = "docs/runtimes/harness-adapters.md", "docs/runtimes/session-backends.md"
harness = {re.findall(r"`(\w+)", cell)[0]: re.findall(r"`(\w+)", cell)
           for cell in rows(H + "#adapter-modules", "Name")}
funcs = re.findall(r"`(\w+)`", re.sub(r"\([^)]*\)", "", re.search(r"as functions: (.*?)\. ", flat(S + "#adapter-modules")).group(1)))
backend = rows(S + "#operations", "Operation") + ["cap:" + c.strip("`") for c in rows(S + "#adapter-modules", "Capability")]
statuses = list(replay("harness", load("harnesses/crew-harness.py", "a19_harness").ADAPTERS, sorted(harness),
                       lambda mod, row: any(getattr(mod, n, None) is not None for n in harness[row])))
statuses += replay("backend", load("environments/terminal/crew-session.py", "a19_session").ADAPTERS, backend,
                   lambda mod, row: row[4:] in mod.CAPABILITIES if row.startswith("cap:") else all(hasattr(mod, f) for f in funcs))
for case in ledger["cases"]:
    where = "%s %s: %s" % (case["adapter"], case["kind"], case["case"])
    statuses.append(check(where, {"oracle": True, **case}, True, case["spec"]) and case["kind"])
for runtime, gaps in ledger["runtimes"].items():
    statuses += [check("%s %s" % (runtime, cap), entry, False, gaps["spec"]) for cap, entry in gaps.items() if cap != "spec"]
live = {k: v for k, v in ledger.get("live", {}).items() if k != "spec"}
bindings = sorted(["%s/%s" % (h, b) for h in ledger["harness"]["adapters"] for b in ledger["backend"]["adapters"]] +
                  ["%s/mirror-watch" % r for r in ledger["runtimes"]])
if sorted(live) != bindings:
    errors.append("live bindings: ledger %s, shipped %s" % (sorted(live), bindings))
for binding, entry in sorted(live.items()):
    kind = next((k for k in ("evidence", "fail", "block", "unsupported") if k in entry), None)
    if kind == "unsupported":
        statuses.append(check("live " + binding, entry, False, entry.get("spec", "")))
        continue
    if kind is None or not str(entry.get("link", "")).startswith("https://"):
        errors.append("live %s: needs evidence, a fail or a block, with an https link to its capture" % binding)
    pinned = re.fullmatch(r"[0-9a-f]{40}", entry.get("source", "")) and entry.get("versions")
    if kind in ("evidence", "fail") and not pinned:
        errors.append("live %s: %s needs the source SHA and the versions" % (binding, kind))
    if kind == "fail" and not str(entry.get("finding", "")).startswith("https://"):
        errors.append("live %s: a fail needs its filed finding" % binding)
    if kind == "block" and not {"account", "installation", "sandbox", "version"} <= set(entry["block"]):
        errors.append("live %s: a block names installation, version, account and sandbox" % binding)
    statuses.append("live-" + str(kind))
    print("%-44s %-11s %s" % ("live " + binding, str(kind).upper(), entry.get("link", "")))

by_file = {}
for t in tests:
    path, name = t.split(":")
    try:
        tree = ast.parse(open(os.path.join(src, "dev/tests", path)).read())
        cls = next(c.name for c in tree.body if isinstance(c, ast.ClassDef) for f in c.body
                   if isinstance(f, ast.FunctionDef) and f.name == name)
        by_file.setdefault(path, []).append(cls + "." + name)
    except (OSError, StopIteration):
        errors.append("test %s (for %s): not found" % (t, ", ".join(tests[t])))
ran = 0
for path, ids in sorted(by_file.items()) if run_tests else []:
    r = subprocess.run([sys.executable, os.path.join(src, "dev/tests", path)] + ids, capture_output=True, text=True)
    ran += len(ids)
    print("replay %s: %d test(s), exit %d" % (path, len(ids), r.returncode))
    if r.returncode:
        errors.append("replay %s failed:\n%s" % (path, r.stderr[-2000:]))
counts = {s: statuses.count(s) for s in ("oracle", "default", "gap", "unsupported", "refusal", "ambiguous",
                                         "live-evidence", "live-fail", "live-block")}
print("A19: %d harness x %d rows, %d backends x %d rows; %s; tests %s" % (
    len(ledger["harness"]["adapters"]), len(harness), len(ledger["backend"]["adapters"]), len(backend),
    ", ".join("%s %d" % kv for kv in counts.items()), "%d replayed" % ran if run_tests else "not run"))
for e in errors:
    print("FAIL " + e)
sys.exit(1 if errors else 0)
