"""Check a named inventory host; default project is CREW_PROJECT or crew.toml. Primary uses doctor locally.

Usage: crew host check HOST [--project FILE] [--org-profile FILE] [--fix]

Remote checks use the fixed crew-host entrypoint (runner supplied by #208), with one JSON request on stdin:
verb=check, root, project=owner__repo, default_branch, capabilities, roles, identities, toolchain_bin and fix.
Reply: checks=[{status: ok|warn|fail|human|unverified, check, detail, hint?}], projects=[owner__repo], load=int.
The runner probes tools, harness logins and project mirrors; fix requests safe repairs and human steps only.
No credentials, profile contents or shell snippets cross SSH. A missing runner never reports ready.
Exit 1 for fail, human or unverified (doctor's human rows also block placement), otherwise 0.
"""
from argparse import Namespace
import contextlib
import io
import json
import os
import subprocess
from crew_shared import commands, ENGINE_CMD, profile, tmux


def options(p):
    p.add_argument("--project", default=os.environ.get("CREW_PROJECT", "crew.toml"))
    p.add_argument("--org-profile")


def inventory(values):
    return sorted({k.split(".")[1] for k in values if k.startswith("hosts.")})


def setting(values, host, key, default=None):
    return values.get("hosts.%s.%s" % (host, key), default)


def inspect_host(args, values, session, state, host):
    project = values["repo.owner"] + "__" + values["repo.name"]
    if setting(values, host, "primary", False):
        with contextlib.redirect_stdout(io.StringIO()) as report:
            code = commands()["doctor"].run(Namespace(project=args.project, org_profile=args.org_profile,
                                                       fix=getattr(args, "fix", False), dry_run=False, milestone=None))
        text = report.getvalue()
        login_ok = True
        for engine in setting(values, host, "capabilities.engines", []):
            verb = "login" if engine == "codex" else "auth"
            ok = commands()["doctor"].sh(ENGINE_CMD.get(engine, engine), verb, "status")[0] == 0
            login_ok = login_ok and ok
            text += ("ok" if ok else "human") + " engine login " + engine + (": logged in\n" if ok else
                    ": log in on the host\n")
        mirror = commands()["doctor"].sh("git", "-C", os.path.dirname(os.path.abspath(args.project)),
                                         "rev-parse", "--verify", "refs/remotes/origin/" + values["repo.default_branch"])[0] == 0
        text += ("ok" if mirror else "fail") + " project mirror: default branch " + values["repo.default_branch"] + "\n"
        load = sum(i >= 10 for i, _ in tmux.list_windows(session)) if tmux.has_session(session) else 0
        ready = mirror and login_ok and not code and not any(line.startswith("human") for line in text.splitlines())
        return dict(reachable=True, ready=ready, report=text, projects=[project] if ready else [], load=load)
    roles = setting(values, host, "roles", ["builder", "reviewer"])
    request = dict(verb="check", root=setting(values, host, "root", "~/.crew"), project=project,
                   default_branch=values["repo.default_branch"], roles=roles,
                   capabilities={k: setting(values, host, "capabilities." + k, []) for k in
                                 ("os", "arch", "devices", "engines")},
                   identities={r: values["identities.%s.gh_user" % r] for r in roles},
                   toolchain_bin=setting(values, host, "toolchain_bin"), fix=getattr(args, "fix", False))
    ssh = ["ssh", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
           "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5",
           "-o", "ServerAliveCountMax=2", host, "crew-host"]
    try:
        r = subprocess.run(ssh, input=json.dumps(request), capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return dict(reachable=False, ready=False, report="fail reachable: SSH unavailable or timed out\n",
                    projects=[], load="?")
    if r.returncode:
        return dict(reachable=r.returncode != 255, ready=False,
                    report="fail remote check: SSH/entrypoint exit %d; check overlay, host key and runner\n" % r.returncode,
                    projects=[], load="?")
    try:
        reply = json.loads(r.stdout)
        checks, projects, load = reply["checks"], reply["projects"], reply["load"]
        if not checks or not isinstance(projects, list) or any(not isinstance(p, str) for p in projects) \
                or type(load) is not int or load < 0:
            raise ValueError("invalid host facts")
        for c in checks:
            if c["status"] not in ("ok", "warn", "fail", "human", "unverified"):
                raise ValueError("unknown check status")
        required = {"tools", "logins", "project mirror"}
        ready = required <= {c["check"] for c in checks} and project in projects \
            and all(c["status"] in ("ok", "warn") for c in checks) \
            and all(c["status"] == "ok" for c in checks if c["check"] in required)
        report = "".join("%s %s: %s%s\n" % (c["status"], c["check"], c["detail"],
                         "; " + c["hint"] if c.get("hint") else "") for c in checks)
        return dict(reachable=True, ready=ready, report=report, projects=projects, load=load)
    except (ValueError, KeyError, TypeError):
        return dict(reachable=True, ready=False, report="fail remote check: invalid runner response\n",
                    projects=[], load="?")


def register(sub):
    p = sub.add_parser("host", help="check an inventory host's project readiness")
    actions = p.add_subparsers(dest="action", required=True)
    p = actions.add_parser("check")
    p.add_argument("host")
    options(p)
    p.add_argument("--fix", action="store_true")


def run(args):
    values, session, state = profile(args)
    if args.host not in inventory(values):
        print("crew host: unknown inventory host " + args.host)
        return 1
    facts = inspect_host(args, values, session, state, args.host)
    print(facts["report"], end="")
    print("%s: %s" % (args.host, "ready" if facts["ready"] else "not ready"))
    return 0 if facts["ready"] else 1
