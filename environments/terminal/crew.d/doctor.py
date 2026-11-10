"""`mdstack doctor` checks whether this host can run the crew (docs/bootstrap.md Q5) and prints one line per check, ok,
warn, fail or human, with its fix hint: Python, git, gh, tmux, each profile login in gh, engines, each harness
adapter's host, coordinator and role checks (Codex hook trust, Claude Code folder trust for the project directory and
for the checkout role worktrees come from, #408), placeholder paths, a session sandbox with no writable root over the
checkout's .git and no sandbox_env (#1544), a state dir or worktree root inside a git checkout, the state dir layout, paths.checkout a clone of [repo], bootstrap's install.json
and paths.mdstack link (#1323), the installed version against the latest release (not queried under a non-github [install] source), the
launcher in the root's bin/ (missing or stale) and where PATH resolves its name (#1317, #1324), the
recorded install source and the running/installed/minimum versions for [tools] in the profile, and the runtime
handoff rows (docs/handoff.md): control item set and readable, `runtime.instance` set and the current owning
runtime. On grok-bot a triage row reports that triage.enabled installs no Grok timer (warn) and never claims one.
With no github backend and no github [install] source, gh, its logins and the GitHub repo checks are skipped and a gh row
says why (#1123). Read-only by default. --fix creates the missing state layout and repairs GitHub prerequisites through
crew-repo.py.
--dry-run prints planned repairs without any writes, including local state. --milestone confirms an M number. It never
changes auth or a harness config. Human-only fixes are listed together at the end as the steps only a
person can take. Exit 1 on any fail, else 0. Any runtime; tmux and the adapter checks are checked for tmux only.
Project scope failures and CI/branch-protection policy are human steps.

Usage: mdstack doctor --project FILE [--org-profile FILE] [--fix] [--dry-run] [--milestone M1]
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from crew_shared import (checkout, commands, crew_render, HERE, harnesses, ownership_module, placeholder_paths,
                         sandbox_env, sessions, load as load_module)

repo_fixers = load_module("crew_repo", "connectors/github/crew-repo.py")

UPSTREAM = "mw-ding/mdstack"
LOGGED_IN = r"Logged in to \S+ (account|as) %s(\s|$)"  # a `gh auth status` line, old and new wording
REMOTE = re.compile(r"^(?:[\w+.-]+://[^/]+/|[^/@:]+@[^/:]+:)(?:.+/)?([^/]+)/([^/]+?)(?:\.git)?/?$")  # forge URL owner/name
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


def forge(values):
    """True when the install needs gh (#1123): a concern bound to the github backend, or the github release source.
    The optional release concern counts only with a [release] table, the one case that uses it (#910)."""
    bound = {k.split(".")[1] for k, v in values.items() if v == "github" and re.fullmatch(r"backends\.[\w-]+\.name", k)}
    if not any(k.startswith("release.") for k in values):
        bound.discard("release")
    return values.get("install.source", "github") == "github" or bool(bound)


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
    order = {e.split("/")[0] for k, v in values.items() if re.fullmatch(r"engines\.(roles\.)?\w+\.order", k) for e in v}
    for e in sorted({coord} | order):
        cli = harnesses.CLI.get(e, e)
        code = sh(cli, "--version")[0]
        if code == 0:
            rows.append(("ok", "engine " + e, cli, ""))
        else:
            rows.append(("fail" if e == coord else "warn", "engine " + e, "%s --version exit %d" % (cli, code),
                         "install it, or drop it from [engines]"))
    if sum(r[0] == "ok" for r in rows) < 2:
        rows.append(("fail", "engine diversity", "fewer than two working engines", "install a second engine"))
    return rows


def sandbox(values, project):
    """A launcher that sandboxes sessions with no writable root over the checkout's git directory (its common dir, for a
    linked worktree whose .git is a file) fails, unless
    runtime.options.sandbox_env or CREW_SANDBOX_ENV is set (#1544). Two signals: a create-and-remove probe in that .git
    is denied to this process (it runs inside such a session), or a used engine's adapter declares
    sandbox_roots(values), the writable roots its launcher grants a session by default (None: no sandbox)."""
    if sandbox_env(values):
        return [("ok", "sandbox", "sandbox_env set", "")]
    repo = checkout(values, project)
    code, out = sh("git", "-C", repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    git = out.strip() if code == 0 and os.path.isdir(out.strip()) else os.path.join(repo, ".git")  # a linked worktree
    used = {values["engines.coordinator"], values.get("engines.fallback_engine")} | {
        e.split("/")[0] for k, order in values.items() if re.fullmatch(r"engines\.(roles\.)?\w+\.order", k) for e in order}
    found = []
    if os.path.isdir(git):
        try:
            fd, probe = tempfile.mkstemp(dir=git, prefix="mdstack-probe-")
            os.close(fd)
            os.remove(probe)
        except PermissionError:
            found.append("this session")
    for engine in sorted(e for e in used if e in harnesses.ADAPTERS):
        roots = getattr(harnesses.ADAPTERS[engine], "sandbox_roots", lambda v: None)(values)
        if roots is not None and not any(os.path.commonpath([os.path.realpath(r), os.path.realpath(git)]) ==
                                         os.path.realpath(r) for r in roots):  # git reports resolved paths
            found.append(engine + "'s launcher")
    if not found:
        return [("ok", "sandbox", "no session sandbox over %s" % git, "")]
    return [("fail", "sandbox", "%s sandboxed with no writable root over %s" % (" and ".join(found), git),
             'set runtime.options.sandbox_env = "<NAME>=%s" with the launcher\'s writable-roots variable '
             "(or export CREW_SANDBOX_ENV), then rerun" % git)]


def in_checkout(values):
    """A fail row for each of paths.state_dir and paths.worktree_root inside a git checkout; a profile directory that
    is not one may hold state/, runs/ and live/ itself (#1316)."""
    rows = []
    for key in ("state_dir", "worktree_root"):
        path = os.path.abspath(values["paths." + key])
        while not os.path.isdir(path) and os.path.dirname(path) != path:
            path = os.path.dirname(path)
        code, out = sh("git", "-C", path, "rev-parse", "--show-toplevel")
        if code == 0 and os.path.isabs(out.strip()) and os.path.isdir(out.strip()):
            rows.append(("fail", "paths", "paths.%s is inside the git checkout %s" % (key, out.strip()),
                         "move it outside, for example under ~/.mdstack/"))
    return rows


def checkout_repo(values, project):
    """paths.checkout (else the profile's directory), which role worktrees branch from, is a clone of [repo]: its
    origin names repo.owner/repo.name (#1323). A clone of another repo fails; no origin, or a path or file:// one, warns.
    Checked for a github change backend only, whose remote URL carries the owner and name."""
    if values.get("backends.change.name", "github") != "github":
        return []
    path, want = checkout(values, project), "%s/%s" % (values["repo.owner"], values["repo.name"])
    code, out = sh("git", "-C", path, "remote", "get-url", "origin")
    match = REMOTE.search(out.strip()) if code == 0 else None
    if not match:
        return [("warn", "checkout", "%s has no forge origin URL" % path, "set paths.checkout to a clone of " + want)]
    got = "%s/%s" % match.groups()
    if got.lower() != want.lower():
        return [("fail", "checkout", "%s is a clone of %s, not %s" % (path, got, want),
                 "set paths.checkout to a clone of %s, or clone %s there" % (want, want))]
    return [("ok", "checkout", "%s (%s)" % (path, want), "")]


def install(values):
    """Bootstrap's install.json and the paths.mdstack link whose docs the briefs cite (#1323). Before bootstrap both
    only warn, since bootstrap runs this report before it writes them; a recorded install without the link fails."""
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (values["repo.owner"], values["repo.name"]))
    recorded = os.path.exists(os.path.join(state, "install.json"))
    rows = [("ok", "install", os.path.join(state, "install.json"), "") if recorded else
            ("warn", "install", "no install.json in %s" % state, "run mdstack bootstrap")]
    if not re.search(r"<[^<>]+>", values.get("paths.mdstack", "<unset>")):  # an unset or placeholder value: no link
        link = os.path.abspath(os.path.expanduser(values["paths.mdstack"]))
        if os.path.isdir(link):
            rows.append(("ok", "mdstack link", link, ""))
        else:
            rows.append(("fail" if recorded else "warn", "mdstack link", "paths.mdstack %s is missing" % link,
                         "run mdstack bootstrap, which links the installed release there"))
    return rows


def state_dir(values, fix):
    """claims/, locks/merge.lock and inbox/ (tmux also status/, wake/); --fix creates the missing ones."""
    repo, tmux = "%s__%s" % (values["repo.owner"], values["repo.name"]), values["runtime.name"] == "tmux"
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), repo)
    want = ["claims/", "locks/merge.lock", "inbox/"] + (["status/", "wake/"] if tmux else [])
    missing = [p for p in want if not os.path.exists(os.path.join(state, p))]
    if not missing:
        return [("ok", "state dir", state, "")]
    if not fix:
        return [("fail", "state dir", "missing %s in %s" % (", ".join(missing), state), "mdstack doctor --fix creates "
                 "them")]
    for p in missing:
        os.makedirs(os.path.dirname(os.path.join(state, p)), exist_ok=True)  # a dir's trailing / keeps it whole
        if not p.endswith("/"):
            open(os.path.join(state, p), "a").close()
    return [("ok", "state dir", "created %s in %s" % (", ".join(missing), state), "")]


def version(values):
    """The installed release against the latest one (docs/release.md update path, Learn); the coordinator decides.
    A non-github [install] source makes no latest-release query (docs/bootstrap.md Release sources)."""
    if not os.path.exists(VERSION_FILE):
        return [("warn", "version", "no VERSION: not a release bundle", "install from a release (README: Install)")]
    have = load(VERSION_FILE, lambda f: f.read().decode().strip())
    kind = values.get("install.source", "github")
    if kind != "github":
        return [("ok", "version", "%s; latest not checked (source %s)" % (have, kind), "")]
    code, out = sh("gh", "release", "view", "-R", UPSTREAM, "--json", "tagName", "--jq", ".tagName")
    if code:
        return [("warn", "version", have, "could not read the latest release of %s with gh" % UPSTREAM)]
    if out.strip() != have:
        return [("warn", "version", "%s installed, %s is the latest release" % (have, out.strip()),
                 "upgrade by the docs/release.md update path; a major needs the owner's OK")]
    return [("ok", "version", have + " (latest)", "")]


def pack(values):
    """The pack name and version the install recorded (#878); no row when install.json has none."""
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (values["repo.owner"], values["repo.name"]))
    recorded = load(os.path.join(state, "install.json"), json.load).get("pack")
    return [("ok", "pack", "%s %s" % (recorded["name"], recorded["version"]), "")] if recorded else []


def install_source(values):
    """The release source and bundle digest the install recorded (#882); no row for a github record."""
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (values["repo.owner"], values["repo.name"]))
    record = load(os.path.join(state, "install.json"), json.load)
    transport = record.get("transport")
    if not transport:
        return []
    detail = "%s %s; bundle sha256 %s" % (transport["kind"], transport["location"], record.get("bundle_sha256"))
    if "commit" in transport:
        detail += "; commit " + transport["commit"]
    elif transport.get("pinned"):
        detail += "; SHA256SUMS pinned"
    return [("ok", "install source", detail, "")]


def launcher(values):
    """The root's bin/ launcher (mdstack, or the name `mdstack install --name` gave it) is present and current, and
    PATH resolves its name to it (#1317). The root is the profile's paths.root, else $CREW_ROOT or ~/.mdstack (#1324)."""
    install = commands()["install"]
    root = Path(values.get("paths.root") or install.home())
    current, text = root / "releases" / "current", install.launcher_text(root).encode()
    named = sorted(p for p in (root / "bin").glob("*") if p.is_file() and p.read_bytes() == text)
    path = named[0] if named else root / "bin" / "mdstack"
    hint = "run mdstack install from the bundle in %s/" % (root / "releases")
    if not path.is_file():
        rows = [("warn", "launcher", "%s missing" % path, hint)]
    elif path.read_bytes() != text or not (current / "cli" / "mdstack").is_file():
        rows = [("warn", "launcher", "%s stale: not the install launcher, or no releases/current" % path, hint)]
    else:
        rows = [("ok", "launcher", "%s -> %s" % (path, current.resolve().name), "")]
    found = shutil.which(path.name)
    if not found:
        rows.append(("warn", path.name + " on PATH", "not found", install.path_hint(root)))
    elif os.path.realpath(found) != os.path.realpath(path):
        rows.append(("warn", path.name + " on PATH", "resolves to %s, not the launcher" % found,
                     "remove or reorder it on PATH, or " + install.path_hint(root)))
    else:
        rows.append(("ok", path.name + " on PATH", found, ""))
    return rows


def handoff(values):
    """Control item set and readable, `runtime.instance` set, and who owns the repo now (docs/handoff.md). No control
    item keeps legacy operation, so it only warns; an unreadable one fails, since every wake is then read-only."""
    item, instance = values.get("repo.control_item"), values.get("runtime.instance")
    rows = [("ok", "runtime instance", instance, "") if instance else
            ("warn", "runtime instance", "not set", "set runtime.instance to a short label (docs/handoff.md Terms)")]
    if not item:
        return [("warn", "control item", "not set: no ownership record",
                 "set repo.control_item (docs/handoff.md)")] + rows
    shown = item if isinstance(item, str) else "#%s" % item  # a native id as written (docs/handoff.md Doctor)
    try:
        owner, phase, opened = ownership_module.read_record(values)
    except (OSError, ValueError, KeyError, TypeError):
        return [("fail", "control item", "%s unreadable" % shown, "check the markers backend can read it; every wake "
                 "is read-only until then")] + rows
    runtime = "%s@%s" % (values["runtime.name"], instance)
    if phase in ("offered", "takeover"):
        owning = ("warn", "in transit %s → %s (%s)" % (opened["from"], opened["to"], opened["handoff"]),
                  "read-only until %s acks or the owner aborts" % opened["to"])
    elif phase:
        owning = ("warn", "%s, draining to %s (%s)" % (owner, opened["to"], opened["handoff"]), "it starts no new pass")
    elif owner is None:
        owning = ("warn", "no record yet", "this runtime's first start posts claimed")
    elif owner == runtime:
        owning = ("ok", owner + " (this runtime)", "")
    else:
        owning = ("warn", "%s; this runtime is %s" % (owner, runtime), "read-only here until a handoff to it")
    return [("ok", "control item", shown, "")] + rows + [(owning[0], "owning runtime") + owning[1:]]


def triage(values):
    """Grok Bot has no triage timer, scan queue or sweep binding (docs/triage.md): triage.enabled only warns."""
    if values["runtime.name"] != "grok-bot":
        return []
    if values.get("triage.enabled"):
        return [("warn", "triage", "enabled: grok-bot installs no Grok timer; triage stays coordinator dispositions",
                 "set triage.enabled = false (docs/triage.md)")]
    return [("ok", "triage", "off: no Grok timer; coordinator dispositions", "")]


def register(sub):
    p = sub.add_parser("doctor", help="check this host can run the crew; --fix repairs what it safely can")
    p.add_argument("--project")
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
    backend = values.get("runtime.options.session_backend", "tmux")  # its adapter names the CLI to look for
    rows = [("ok" if sys.version_info >= (3, 11) else "fail", "python", sys.version.split()[0], "install Python 3.11+")]
    github = forge(values)
    rows += [("ok", t, shutil.which(t), "") if shutil.which(t) else ("fail", t, "not on PATH", "install " + t)
             for t in ["git"] + (["gh"] if github else []) + ([sessions.ADAPTERS[backend].EXECUTABLE] if tmux else [])]
    if not github:
        rows.append(("ok", "gh", "not checked: no github backend or release source", ""))
    rows += (logins(values) if github else []) + engines(values)
    used = [r[1].removeprefix("engine ") for r in rows if r[1].startswith("engine ")]
    for engine in harnesses.LAUNCHABLE if tmux else []:  # each adapter's host and coordinator preflight
        if engine in used and hasattr(harnesses.ADAPTERS[engine], "host_checks"):
            rows += harnesses.ADAPTERS[engine].host_checks()
    coordinator = harnesses.ADAPTERS.get(values["engines.coordinator"])
    project_dir = os.path.dirname(os.path.abspath(args.project))
    if tmux and hasattr(coordinator, "coordinator_checks"):
        rows += coordinator.coordinator_checks(values, project_dir)
    repo = checkout(values, args.project)
    for engine in harnesses.LAUNCHABLE if tmux else []:  # role worktrees key trust on the checkout (#408)
        adapter = harnesses.ADAPTERS[engine]
        if engine in used and hasattr(adapter, "role_checks") and not (adapter is coordinator and repo == project_dir):
            rows += adapter.role_checks(values, repo)
    bad = placeholder_paths(args, values, ("state_dir", "worktree_root"))
    rows += [("fail", "paths", b, "") for b in bad] if bad else in_checkout(values) or state_dir(
        values, args.fix and not args.dry_run)
    if not bad and github:
        rows += repo_fixers.checks(values, args.fix, args.dry_run, args.milestone)
    rows += checkout_repo(values, args.project) + install(values) + (sandbox(values, args.project) if tmux else [])
    rows += handoff(values) + triage(values) + version(values) + launcher(values) + pack(values) + install_source(values)
    rows += tool_drift(values)
    for status, check, detail, hint in rows:
        print("%-5s %-18s %s%s" % (status, check, detail, "; " + hint if hint and status in ("warn", "fail") else ""))
    human = [hint for status, _, _, hint in rows if status == "human"]
    if human:
        print("\nSteps only a person can take:\n" + "\n".join("- " + h for h in human))
    return 1 if any(r[0] == "fail" for r in rows) else 0
