"""`crew up` starts a repo's tmux crew with the coordinator in window 0. When the profile can use Codex,
refuse before rendering if a host hooks.json or inline config.toml hook lacks stored trust. Never write Codex config.

Usage: crew up --project FILE [--org-profile FILE] [--inputs DIR]
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


def run(args):
    values, session, state = profile(args)
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
        if re.fullmatch(r"engines\.\w+\.order", k) for e in order)
    if uses_codex:
        for status, check, detail, hint in codex_hooks():
            if status != "ok":
                print("crew: refusing to start: %s: %s; %s" % (check, detail, hint))
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
    project_dir = os.path.dirname(os.path.abspath(args.project))
    engine = values["engines.coordinator"]
    if engine == "claude-code":
        install_stop_hook(project_dir, state)
    env = {"CREW_ROLE": "coordinator", "CREW_STATE": state, "CREW_IDENTITY": values["identities.coordinator.gh_user"],
           "CREW_BRIEF": brief_src(state, "coordinator"), "CREW_BIN": CREW_BIN,
           "CREW_PROJECT": os.path.abspath(args.project), **sandbox_env(values)}
    window = values.get("identities.coordinator.name", "ash").lower()
    if engine == "pi":
        try:
            argv = harness(engine, "", "", project_dir, state, values["runtime.options.permission_mode"])
        except RuntimeError as e:
            print(e)
            return 1
        cmd = shlex.join(argv)  # coordinator uses the harness's configured model and thinking level
    else:
        cmd = ENGINE_CMD[engine] if engine == "claude-code" else shlex.join(  # Claude Code: trust dialog (tmux.md)
            ["codex", "-c", codex_trust(project_dir)])
    tmux.new_session(session, window, project_dir, env, LAUNCH % (cmd, POINTER))
    print("crew: started %s (window 0 %s, %s); attach with: tmux attach -t %s" % (session, window, engine, session))
    reconcile(state)
    for role in commands()["lead"].POOLS:
        if commands()["lead"].enabled(state, role) and commands()["lead"].ensure(args, role):
            return 1
    return 0
