"""`crew doctor` checks whether this host can run the crew (docs/bootstrap.md Q5) and prints one line per check, ok,
warn, fail or human, with its fix hint: Python, git, gh, tmux, each profile login in gh, engines, Codex hook trust,
Claude Code folder trust, placeholder paths, the state dir layout, the installed version against the latest release,
and running/installed/minimum versions for [tools] in the profile.
Read-only by default. --fix creates the missing state layout and repairs GitHub prerequisites through crew-repo.py.
--dry-run prints planned repairs without any writes, including local state. --milestone confirms an M number. It never
changes auth or a harness config. Human-only fixes are listed together at the end as the steps only a
person can take. Exit 1 on any fail, else 0. Any runtime; tmux, Codex hook trust and Claude Code folder trust are
checked for tmux only. Project scope failures and CI/branch-protection policy are human steps.

Usage: crew doctor --project FILE [--org-profile FILE] [--fix] [--dry-run] [--milestone M1]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from crew_shared import codex_hooks, crew_render, ENGINE_CMD, HERE, placeholder_paths, load as load_module

repo_fixers = load_module("crew_repo", "crew-repo.py")

UPSTREAM = "mw-ding/eng-crew"
LOGGED_IN = r"Logged in to \S+ (account|as) %s(\s|$)"  # a `gh auth status` line, old and new wording
VERSION_FILE = os.path.join(os.path.dirname(HERE), "VERSION")  # the release bundle's tag (docs/deliverables.md)


def sh(*cmd):
    """(exit code, stdout and stderr) of a read-only command; 127 when it is missing or hangs."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return r.returncode, r.stdout + r.stderr


def load(path, reader):
    try:
        with open(path, "rb") as f:
            return reader(f)
    except FileNotFoundError:
        return {}


def logins(values):
    """Each login the profile names is logged in to gh; read from `gh auth status`, which masks tokens."""
    _, out = sh("gh", "auth", "status")
    users = sorted({v for k, v in values.items() if re.fullmatch(r"identities\.\w+\.gh_user", k)})
    return [("ok", "gh " + u, "logged in", "") if re.search(LOGGED_IN % re.escape(u), out)
            else ("human", "gh " + u, "not logged in", "gh auth login as %s (never gh auth switch)" % u) for u in users]


def engines(values):
    """Each engine's CLI answers --version: the coordinator's must (fail), a tier-order one is skipped (warn), and two
    must work so the reviewer engine can differ from the builder's (invariant 2)."""
    coord, rows = values["engines.coordinator"], []
    order = {e.split("/")[0] for k, v in values.items() if re.fullmatch(r"engines\.\w+\.order", k) for e in v}
    for e in sorted({coord} | order):
        cli = ENGINE_CMD.get(e, e)
        code = sh(cli, "--version")[0]
        if code == 0:
            rows.append(("ok", "engine " + e, cli, ""))
        else:
            rows.append(("fail" if e == coord else "warn", "engine " + e, "%s --version exit %d" % (cli, code),
                         "install it, or drop it from [engines]"))
    if sum(r[0] == "ok" for r in rows) < 2:
        rows.append(("fail", "engine diversity", "fewer than two working engines", "install a second engine"))
    return rows


def claude_trust(values, project_dir):
    """A Claude Code coordinator opens at the folder-trust dialog until it is accepted once for the project directory
    or a parent (docs/runtimes/harness-adapters.md)."""
    path = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~"), ".claude.json")
    projects, d = load(path, json.load).get("projects", {}), os.path.realpath(project_dir)
    while not projects.get(d, {}).get("hasTrustDialogAccepted"):
        if d == os.path.dirname(d):
            window = values.get("identities.coordinator.name", "ash").lower()
            return [("human", "claude trust", "not accepted for " + project_dir, "after crew up, accept the folder-"
                     "trust dialog once with crew attach %s --rw (never a blind Enter: it picks No, exit)" % window)]
        d = os.path.dirname(d)
    return [("ok", "claude trust", d, "")]


def state_dir(values, fix):
    """claims/, locks/merge.lock and inbox/ (tmux also status/, wake/); --fix creates the missing ones."""
    repo, tmux = "%s__%s" % (values["repo.owner"], values["repo.name"]), values["runtime.name"] == "tmux"
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), repo)
    want = ["claims/", "locks/merge.lock", "inbox/"] + (["status/", "wake/"] if tmux else [])
    missing = [p for p in want if not os.path.exists(os.path.join(state, p))]
    if not missing:
        return [("ok", "state dir", state, "")]
    if not fix:
        return [("fail", "state dir", "missing %s in %s" % (", ".join(missing), state), "crew doctor --fix creates "
                 "them")]
    for p in missing:
        os.makedirs(os.path.dirname(os.path.join(state, p)), exist_ok=True)  # a dir's trailing / keeps it whole
        if not p.endswith("/"):
            open(os.path.join(state, p), "a").close()
    return [("ok", "state dir", "created %s in %s" % (", ".join(missing), state), "")]


def version():
    """The installed release against the latest one (docs/release.md update path, Learn); the coordinator decides."""
    if not os.path.exists(VERSION_FILE):
        return [("warn", "version", "no VERSION: not a release bundle", "install from a release (README: Install)")]
    have = load(VERSION_FILE, lambda f: f.read().decode().strip())
    code, out = sh("gh", "release", "view", "-R", UPSTREAM, "--json", "tagName", "--jq", ".tagName")
    if code:
        return [("warn", "version", have, "could not read the latest release of %s with gh" % UPSTREAM)]
    if out.strip() != have:
        return [("warn", "version", "%s installed, %s is the latest release" % (have, out.strip()),
                 "upgrade by the docs/release.md update path; a major needs the owner's OK")]
    return [("ok", "version", have + " (latest)", "")]


def register(sub):
    p = sub.add_parser("doctor", help="check this host can run the crew; --fix repairs what it safely can")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--fix", action="store_true", help="repair local state and GitHub prerequisites (idempotent)")
    p.add_argument("--dry-run", action="store_true", help="print repair plans without local or remote writes")
    p.add_argument("--milestone", type=milestone_name, help="confirmed current milestone, e.g. M1")


def milestone_name(value):
    if not re.fullmatch(r"M\d+(?:\s.+)?", value):
        raise argparse.ArgumentTypeError("milestone must be M followed by a number")
    return value


def tool_drift(values):
    """Profile probes distinguish a running session from the installed CLI; numeric X.Y.Z pins are minimums.
    Probes are argv arrays run without a shell, using the existing read-only command timeout. Never reload a tool.
    """
    rows = []
    names = sorted(k[len("tools."):-len(".running")] for k in values
                   if k.startswith("tools.") and k.endswith(".running"))
    for name in names:
        versions, problem = {}, ""
        for kind in ("running", "installed"):
            code, out = sh(*values["tools.%s.%s" % (name, kind)])
            match = re.search(r"(?<![\w.])v?(\d+\.\d+\.\d+)(?![\w.+-])", out)
            if code or not match:
                problem = "%s probe exit %d or no X.Y.Z version" % (kind, code)
                break
            versions[kind] = tuple(map(int, match[1].split(".")))
        if problem:
            rows.append(("warn", "tool " + name, problem, "check the profile's read-only version probes"))
            continue
        pin = values.get("tools.%s.pin" % name)
        minimum = tuple(map(int, pin.lstrip("v").split("."))) if pin else None
        detail = "running %s, installed %s" % tuple(".".join(map(str, versions[k])) for k in ("running", "installed"))
        if pin:
            detail += ", pin >= " + pin
        hints = []
        if versions["running"] != versions["installed"]:
            hints.append("restart the session using the installed tool")
        if minimum and any(v < minimum for v in versions.values()):
            hints.append("upgrade to at least %s and restart the session" % pin)
        rows.append(("warn" if hints else "ok", "tool " + name, detail, "; ".join(hints)))
    return rows


def run(args):
    values, problems = crew_render.resolve(args.project, args.org_profile)
    if problems:
        print("\n".join(problems))
        return 1
    tmux = values["runtime.name"] == "tmux"
    rows = [("ok" if sys.version_info >= (3, 11) else "fail", "python", sys.version.split()[0], "install Python 3.11+")]
    rows += [("ok", t, shutil.which(t), "") if shutil.which(t) else ("fail", t, "not on PATH", "install " + t)
             for t in ["git", "gh"] + ([values.get("runtime.options.session_backend", "tmux")] if tmux else [])]
    rows += logins(values) + engines(values)
    if tmux and any(r[1] == "engine codex" for r in rows):
        rows += codex_hooks()
    if tmux and values["engines.coordinator"] == "claude-code":
        rows += claude_trust(values, os.path.dirname(os.path.abspath(args.project)))
    bad = placeholder_paths(args, values, ("state_dir", "worktree_root"))
    rows += [("fail", "paths", b, "") for b in bad] if bad else state_dir(values, args.fix and not args.dry_run)
    if not bad:
        rows += repo_fixers.checks(values, args.fix, args.dry_run, args.milestone)
    rows += version() + tool_drift(values)
    for status, check, detail, hint in rows:
        print("%-5s %-18s %s%s" % (status, check, detail, "; " + hint if hint and status in ("warn", "fail") else ""))
    human = [hint for status, _, _, hint in rows if status == "human"]
    if human:
        print("\nSteps only a person can take:\n" + "\n".join("- " + h for h in human))
    return 1 if any(r[0] == "fail" for r in rows) else 0
