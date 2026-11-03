"""`crew up` starts a repo's tmux crew with the coordinator in window 0. When the profile can use Codex,
refuse before rendering if a host hooks.json or inline config.toml hook lacks stored trust. Never write Codex config.

`runtime.options.launch` picks the topology: coordinator tmux|none, roles tmux|hosted|none, resume fresh|ask|<id>.

Usage: crew up --project FILE [--org-profile FILE] [--inputs DIR] [--coordinator-only]
"""
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
LAUNCH_DEFAULTS = {"coordinator": "tmux", "roles": "tmux", "resume": "fresh", "reconcile": "backend"}


def launch(values, key):
    return values.get("runtime.options.launch." + key, LAUNCH_DEFAULTS[key])


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
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--inputs", default=TEMPLATES, help="render inputs dir (default: templates/)")
    p.add_argument("--coordinator-only", action="store_true", help="start no role windows (as launch.roles = none)")


def run(args):
    values, session, state = profile(args)
    if values["backends.owner-channel.name"] == "slack" and not os.environ.get(values["runtime.options.slack_webhook_env"]):
        print("crew: refusing to start: missing Slack webhook environment variable %s" % values["runtime.options.slack_webhook_env"])
        return 1
    if tmux.has_session(session):
        print("crew: %s already running; attach with: tmux attach -t %s" % (session, session))
        return 0
    try:
        notes = role_notes(values, state, "coordinator")
    except RuntimeError as e:
        print(e)
        return 1
    uses_codex = values["engines.coordinator"] == "codex" or values.get("engines.fallback_engine") == "codex" or any(
        e.split("/")[0] == "codex" for k, order in values.items()
        if re.fullmatch(r"engines\.(roles\.)?\w+\.order", k) for e in order)
    if uses_codex:
        for status, check, detail, hint in codex_hooks():
            if status != "ok":
                print("crew: refusing to start: %s: %s; %s" % (check, detail, hint))
                return 1
    engine, resume = values["engines.coordinator"], launch(values, "resume")
    if resume != "fresh" and engine not in ("claude-code", "codex"):
        print("crew: refusing to start: launch.resume needs a claude-code or codex coordinator, not %s" % engine)
        return 1
    render = os.path.join(state, "render")
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(out):  # chatter only on failure
        code = crew_render.main(["--project", args.project, "--inputs", args.inputs, "--out", render] +
                                (["--org-profile", args.org_profile] if args.org_profile else []))
    if code:
        print(out.getvalue(), end="")
        return 1
    if notes:
        with open(brief_src(state, "coordinator"), "a", encoding="utf-8") as f:
            f.write(notes)
    if launch(values, "coordinator") == "none":
        print("crew: preflight ok; launch.coordinator = none, so no session started (render: %s)" % render)
        return 0
    project_dir = os.path.dirname(os.path.abspath(args.project))
    if engine == "claude-code":
        install_stop_hook(project_dir, state)
    env = {"CREW_ROLE": "coordinator", "CREW_STATE": state, "CREW_IDENTITY": values["identities.coordinator.gh_user"],
           "CREW_BRIEF": brief_src(state, "coordinator"), "CREW_BIN": CREW_BIN,
           "CREW_PROJECT": os.path.abspath(args.project), **sandbox_env(values)}
    window = values.get("identities.coordinator.name", "ash").lower()
    if engine in ("pi", "cursor", "muse"):
        try:
            argv = harness(engine, "", "", project_dir, state, values["runtime.options.permission_mode"], values)
        except RuntimeError as e:
            print(e)
            return 1
        cmd = shlex.join(argv)  # coordinator uses the harness's configured model and thinking level
    else:
        cmd = ENGINE_CMD[engine] if engine == "claude-code" else shlex.join(  # Claude Code: trust dialog (tmux.md)
            ["codex", "-c", codex_trust(project_dir)])
        if resume != "fresh":  # ask opens the harness picker, which would take the pointer as a search term or id
            cmd += " --resume" if engine == "claude-code" else " resume"
            cmd += "" if resume == "ask" else " " + shlex.quote(resume)
    private = {values["runtime.options.slack_webhook_env"]: os.environ[values["runtime.options.slack_webhook_env"]]} \
        if values["backends.owner-channel.name"] == "slack" else None
    line = LAUNCH.removesuffix(' "%s"') % cmd if resume == "ask" else LAUNCH % (cmd, POINTER)
    tmux.new_session(session, window, project_dir, env, line, private_env=private)
    print("crew: started %s (window 0 %s, %s); attach with: tmux attach -t %s" % (session, window, engine, session))
    reconcile(state)
    roles = "none" if args.coordinator_only else launch(values, "roles")
    if roles != "tmux":
        print("crew: launch.roles = %s; started no role windows" % roles)
        return 0
    for role in commands()["lead"].POOLS:
        if commands()["lead"].enabled(state, role) and commands()["lead"].ensure(args, role):
            return 1
    return 0
