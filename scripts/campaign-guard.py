#!/usr/bin/env python3
"""M25 campaign harness contract (#783): pin a run manifest and refuse a production target before any mutation.

`manifest` resolves the sandbox profile and writes a JSON run manifest that pins the repo, the profile (path and
sha256), the source checkout SHA, the installed release id, the state/worktree/live roots, the tmux session and an
outside-sandbox sentinel file's sha256. `check` re-resolves both profiles and refuses (exit 2) when the sandbox
names the production repo or session, a sandbox root equals or nests with a production root, a root is still a
placeholder, or a pin drifted. `sentinel` re-hashes the sentinel after teardown (exit 1 if changed). Python 3.11+
stdlib only; reads files and runs `git rev-parse`, never writes outside --out. Contract: docs/campaign-harness.md.

Usage: campaign-guard.py manifest --sandbox FILE --production FILE --source DIR --release ID --run-id ID
                                  --sentinel FILE [--scenario AXX ...] --out FILE
       campaign-guard.py check MANIFEST
       campaign-guard.py sentinel MANIFEST
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("crew_config", Path(__file__).with_name("crew-config.py"))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)

ROOTS = ("state_dir", "worktree_root", "live_dir")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target(profile):
    """The repo slug, session and absolute roots a profile would touch; raise ValueError on a resolve problem."""
    merged, _, problems, _ = config.resolve_profile(profile)
    if problems:
        raise ValueError("; ".join(problems))
    owner, name = merged["repo"]["owner"], merged["repo"]["name"]
    session = merged["runtime"].get("options", {}).get("session") or "crew-%s-%s" % (owner, name)
    roots = {k: merged["paths"][k] for k in ROOTS}
    roots = {k: v if re.search(r"<[^<>]+>", v) else os.path.realpath(v) for k, v in roots.items()}
    return {"repo": "%s/%s" % (owner, name), "session": session, "roots": roots}


def head(source):
    return subprocess.run(["git", "-C", source, "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


def nested(a, b):
    return a == b or a.startswith(b.rstrip(os.sep) + os.sep) or b.startswith(a.rstrip(os.sep) + os.sep)


def refusals(m):
    """Every reason the manifest's run must not start; empty means safe to mutate the sandbox."""
    try:
        sand, prod = target(m["profile"]["path"]), target(m["production"]["path"])
    except (OSError, ValueError) as e:
        return ["profile: %s" % e]
    out = []
    if sand["repo"] == prod["repo"]:
        out.append("repo: sandbox names the production repo %s" % prod["repo"])
    if sand["session"] == prod["session"]:
        out.append("session: sandbox uses the production session %s" % prod["session"])
    prod_roots = [v for v in prod["roots"].values() if not re.search(r"<[^<>]+>", v)]
    for key, path in sand["roots"].items():
        if re.search(r"<[^<>]+>", path):
            out.append("paths.%s: still the placeholder %s" % (key, path))
        elif any(nested(path, p) for p in prod_roots):
            out.append("paths.%s: %s overlaps a production root" % (key, path))
    if sha256(m["profile"]["path"]) != m["profile"]["sha256"]:
        out.append("profile: %s changed since the manifest" % m["profile"]["path"])
    if {k: sand[k] for k in ("repo", "session", "roots")} != {k: m[k] for k in ("repo", "session", "roots")}:
        out.append("target: resolved repo/session/roots differ from the manifest")
    if head(m["source"]["path"]) != m["source"]["sha"]:
        out.append("source: %s is no longer at %s" % (m["source"]["path"], m["source"]["sha"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("manifest")
    for flag in ("sandbox", "production", "source", "release", "run-id", "sentinel", "out"):
        mk.add_argument("--" + flag, required=True)
    mk.add_argument("--scenario", action="append", default=[])
    for name in ("check", "sentinel"):
        sub.add_parser(name).add_argument("manifest")
    args = ap.parse_args(argv)
    if args.cmd == "manifest":
        try:
            sand = target(args.sandbox)
        except ValueError as e:
            print("refused: profile: %s" % e)
            return 2
        m = dict(sand, run_id=args.run_id, scenarios=args.scenario, release=args.release,
                 profile={"path": os.path.realpath(args.sandbox), "sha256": sha256(args.sandbox)},
                 production={"path": os.path.realpath(args.production)},
                 source={"path": os.path.realpath(args.source), "sha": head(args.source)},
                 sentinel={"path": os.path.realpath(args.sentinel), "sha256": sha256(args.sentinel)})
        problems = refusals(m)
        if not problems:
            Path(args.out).write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    else:
        m = json.loads(Path(args.manifest).read_text())
        if args.cmd == "sentinel":
            ok = os.path.isfile(m["sentinel"]["path"]) and sha256(m["sentinel"]["path"]) == m["sentinel"]["sha256"]
            print("sentinel %s: %s" % ("unchanged" if ok else "CHANGED", m["sentinel"]["path"]))
            return 0 if ok else 1
        problems = refusals(m)
    for p in problems:
        print("refused: " + p)
    if not problems:
        print("ok: run %s targets %s (session %s)" % (m["run_id"], m["repo"], m["session"]))
    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
