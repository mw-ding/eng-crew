"""`crew up` starts a repo's tmux crew, or a team's (one session for every repo in a team file), with the coordinator
in window 0. When the profile can use Codex, refuse before rendering if a host hooks.json or inline config.toml hook lacks stored trust. Never write Codex config.

Usage: crew up (--project FILE[#REPO] | --team FILE) [--org-profile FILE] [--inputs DIR]
"""
import argparse
import contextlib
import io
import json
import os
import re
import shlex
from crew_shared import (
    brief_src, codex_hooks, codex_trust, commands, CREW_BIN, crew_render, ENGINE_CMD, HERE, LAUNCH, POINTER, profile,
    harness, role_notes, runs, sandbox_env, tmux)


TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")


def stop_hook_settings(settings, state):
    """Add the turn-end guard to a settings object, preserving every other key."""
    command = shlex.join(["python3", os.path.join(HERE, "crew"), "guard", "--state", state])
    stop = settings.setdefault("hooks", {}).setdefault("Stop", [])
    if not any(h.get("command") == command for entry in stop for h in entry.get("hooks", [])):
        stop.append({"hooks": [{"type": "command", "command": command}]})
    return settings


def install_stop_hook(project_dir, state):
    """Add the turn-end guard to the project's local Claude settings, once, keeping every other key."""
    path = os.path.join(project_dir, ".claude", "settings.local.json")
    settings = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            settings = json.load(f)
    settings = stop_hook_settings(settings, state)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def reconcile(state):
    """After crew up rebuilt the session from disk: report recorded runs; never respawn them (tmux.md Q7)."""
    names = [n for n, _ in runs(state)]
    if names:
        print("crew: rebuilt from %s; recorded runs now probe missing: %s (crew status; crew restart <window>)" % (
            state, ", ".join(names)))


def register(sub):
    p = sub.add_parser("up")
    which = p.add_mutually_exclusive_group(required=True)
    which.add_argument("--project")
    which.add_argument("--team", help="team file: one instance for every [repos.<name>] (docs/profile.md)")
    p.add_argument("--org-profile")
    p.add_argument("--inputs", default=TEMPLATES, help="render inputs dir (default: templates/)")


def slack_ok(values):
    if values["backends.owner-channel.name"] == "slack" and not os.environ.get(values["runtime.options.slack_webhook_env"]):
        print("crew: refusing to start: missing Slack webhook environment variable %s" % values["runtime.options.slack_webhook_env"])
        return False
    return True


def codex_ok(values):
    """Refuse before any write when the profile can use Codex and a host hook lacks stored trust."""
    uses_codex = values["engines.coordinator"] == "codex" or values.get("engines.fallback_engine") == "codex" or any(
        e.split("/")[0] == "codex" for k, order in values.items()
        if re.fullmatch(r"engines\.(roles\.)?\w+\.order", k) for e in order)
    if uses_codex:
        for status, check, detail, hint in codex_hooks():
            if status != "ok":
                print("crew: refusing to start: %s: %s; %s" % (check, detail, hint))
                return False
    return True


def render_briefs(args, project, state):
    """Render the role briefs into state/render; print the renderer's chatter only on failure."""
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(out):
        code = crew_render.main(["--project", project, "--inputs", args.inputs, "--out", os.path.join(state, "render")] +
                                (["--org-profile", args.org_profile] if args.org_profile else []))
    if code:
        print(out.getvalue(), end="")
    return not code


def coordinator_cmd(values, project_dir, state):
    """The coordinator's harness command; RuntimeError when the harness refuses the profile."""
    engine = values["engines.coordinator"]
    if engine in ("pi", "cursor", "muse"):  # coordinator uses the harness's configured model and thinking level
        return shlex.join(harness(engine, "", "", project_dir, state, values["runtime.options.permission_mode"], values))
    return ENGINE_CMD[engine] if engine == "claude-code" else shlex.join(  # Claude Code: trust dialog (tmux.md)
        ["codex", "-c", codex_trust(project_dir)])


def start(values, session, state, project_dir, env):
    """Open window 0 with the coordinator; 1 on a harness refusal."""
    try:
        cmd = coordinator_cmd(values, project_dir, state)
    except RuntimeError as e:
        print(e)
        return 1
    env = {"CREW_ROLE": "coordinator", "CREW_STATE": state, "CREW_IDENTITY": values["identities.coordinator.gh_user"],
           "CREW_BIN": CREW_BIN, **env, **sandbox_env(values)}
    window = values.get("identities.coordinator.name", "ash").lower()
    private = {values["runtime.options.slack_webhook_env"]: os.environ[values["runtime.options.slack_webhook_env"]]} \
        if values["backends.owner-channel.name"] == "slack" else None
    tmux.new_session(session, window, project_dir, env, LAUNCH % (cmd, POINTER), private_env=private)
    print("crew: started %s (window 0 %s, %s); attach with: tmux attach -t %s" % (
        session, window, values["engines.coordinator"], session))
    return 0


def run(args):
    if args.team:
        return team(args)
    values, session, state = profile(args)
    if not slack_ok(values):
        return 1
    if tmux.has_session(session):
        print("crew: %s already running; attach with: tmux attach -t %s" % (session, session))
        return 0
    try:
        notes = role_notes(values, state, "coordinator")
    except RuntimeError as e:
        print(e)
        return 1
    if not codex_ok(values):
        return 1
    if not render_briefs(args, args.project, state):
        return 1
    if notes:
        with open(brief_src(state, "coordinator"), "a", encoding="utf-8") as f:
            f.write(notes)
    project_dir = os.path.dirname(os.path.abspath(args.project))
    if values["engines.coordinator"] == "claude-code":
        install_stop_hook(project_dir, state)
    if start(values, session, state, project_dir, {"CREW_BRIEF": brief_src(state, "coordinator"),
                                                   "CREW_PROJECT": os.path.abspath(args.project)}):
        return 1
    reconcile(state)
    for role in commands()["lead"].POOLS:
        if commands()["lead"].enabled(state, role) and commands()["lead"].ensure(args, role):
            return 1
    return 0


def team(args):
    """One instance for a team file: one session and coordinator, state root <state_dir>/<team>/ with a subfolder
    and render per repo. The coordinator's brief lists each repo's --project reference, state and rendered brief."""
    try:
        names = crew_render.crew_config.team_repos(args.team)
    except (OSError, ValueError) as e:
        print("crew: cannot read team file %s: %s" % (args.team, e))
        return 1
    if not names:
        print("crew: %s is not a team file (needs [team] and [repos.<name>])" % args.team)
        return 1
    repos = []
    for name in names:
        ref = "%s#%s" % (args.team, name)
        values, session, state = profile(argparse.Namespace(project=ref, org_profile=args.org_profile))
        repos.append((ref, values, state))
    values, root = repos[0][1], os.path.dirname(repos[0][2])
    if not slack_ok(values):
        return 1
    if tmux.has_session(session):
        print("crew: %s already running; attach with: tmux attach -t %s" % (session, session))
        return 0
    try:
        notes = role_notes(values, root, "coordinator")
    except RuntimeError as e:
        print(e)
        return 1
    if not codex_ok(values):
        return 1
    for ref, _, state in repos:
        if not render_briefs(args, ref, state):
            return 1
    team_name = os.path.basename(root)
    rows = "".join("| %s/%s | `%s` | `%s` | `%s` |\n" % (v["repo.owner"], v["repo.name"], os.path.abspath(ref), state,
                                                     brief_src(state, "coordinator")) for ref, v, state in repos)
    brief = os.path.join(root, "coordinator.md")
    with open(brief, "w", encoding="utf-8") as f:
        f.write("# Team coordinator: %s\n\nYou coordinate every repo of team `%s` from this window: one session, one "
                "coordinator, one state root (`%s`) with a subfolder per repo. For each repo, follow its rendered "
                "coordinator brief, pass its reference as `--project` to every crew command, and use its state "
                "directory as `CREW_STATE`. `$CREW_PROJECT` names the first repo; `$CREW_TEAM` is the team file.\n\n"
                "| Repo | --project | State | Brief |\n|---|---|---|---|\n%s%s" % (team_name, team_name, root, rows, notes))
    project_dir = os.path.dirname(os.path.abspath(args.team))
    if values["engines.coordinator"] == "claude-code":
        for _, _, state in repos:
            install_stop_hook(project_dir, state)
    if start(values, session, root, project_dir, {"CREW_BRIEF": brief, "CREW_PROJECT": os.path.abspath(repos[0][0]),
                                                  "CREW_TEAM": os.path.abspath(args.team)}):
        return 1
    for _, _, state in repos:
        reconcile(state)
    return 0
