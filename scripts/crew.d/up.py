"""`crew up` starts a repo's tmux crew, or a team's (one session for every repo in a team file), with the coordinator
in window 0. When the profile can use Codex, refuse before rendering if a host hooks.json or inline config.toml hook lacks stored trust. Never write Codex config.

`runtime.options.launch` picks the topology: coordinator tmux|none, roles tmux|hosted|none, resume fresh|ask|<id>.

Usage: crew up (--project FILE[#REPO] | --team FILE) [--org-profile FILE] [--inputs DIR] [--coordinator-only]
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
    harness, ownership_module, role_notes, runs, sandbox_env, stop_pid, tmux)


TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")
LAUNCH_DEFAULTS = {"coordinator": "tmux", "roles": "tmux", "resume": "fresh", "reconcile": "backend"}


def launch(values, key):
    return values.get("runtime.options.launch." + key, LAUNCH_DEFAULTS[key])


def is_guard(hook, state):
    """Whether a Stop hook is a crew turn-end guard for this state, from any bundle, link or checkout path."""
    try:
        argv = shlex.split(hook.get("command") or "")
    except ValueError:
        return False
    return len(argv) == 5 and argv[0] == "python3" and os.path.basename(argv[1]) == "crew" and \
        argv[2:] == ["guard", "--state", state]


def stop_hook_settings(settings, state):
    """Add the turn-end guard to a settings object, preserving every other key. The command names the resolved
    bundle, so a run through the eng-crew link matches; a guard for this state from another path is re-pointed (#1088)."""
    command = shlex.join(["python3", os.path.realpath(os.path.join(HERE, "crew")), "guard", "--state", state])
    stop = settings.setdefault("hooks", {}).setdefault("Stop", [])
    placed = False
    for entry in list(stop):
        hooks = []
        for h in entry.get("hooks", []):
            if is_guard(h, state):
                if placed:
                    continue
                h, placed = dict(h, command=command), True
            hooks.append(h)
        if entry.get("hooks") and not hooks:
            stop.remove(entry)
        elif "hooks" in entry:
            entry["hooks"] = hooks
    if not placed:
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


def record_binding(values, project, args):
    """Record a non-GitHub markers backend's `markers.read-item` and `markers.write-item` commands for the ownership
    guard and crew handoff, and a non-GitHub tracker or change backend's live reads (#606, docs/handoff.md Bindings).

    An unmapped or unsupported operation is not recorded, so its read fails closed (read-only) and its post refuses."""
    path = ownership_module.binding_path(values)
    with contextlib.suppress(FileNotFoundError):
        os.remove(path)
    ops = [] if values["backends.markers.name"] == "github" else [("markers", "read-item"), ("markers", "write-item")]
    ops += list(ownership_module.LIVE_OPS) if ownership_module.native(values) else []
    if not ops or not values.get("repo.control_item"):
        return
    overlay = crew_render.pack_overlay(project, args.org_profile, values)  # a pack's render/ map wins (#580)
    renderer = crew_render.Renderer(values, args.inputs, overlay=overlay)
    bindings = {}
    for concern, op in ops:
        try:
            bindings["%s.%s" % (concern, op)], _ = renderer.op(concern, op)
        except ValueError as e:
            print("crew: ownership %s unbound (%s); %s" % (
                "read" if op == "read-item" else "%s.%s" % (concern, op), e,
                "the control item reads as read-only" if op == "read-item" else "crew handoff refuses it"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bindings, f)


def reap_orphans(state):
    """Before a new session: stop each recorded lead whose pane process outlived its tmux server (Codex ignores SIGHUP,
    #818). Only the recorded pid with its recorded start time, reparented to init, counts; any other process is
    left alone."""
    for name, rec in commands()["lead"].records(state):
        pid, start = rec.get("pane_pid"), rec.get("pane_start")
        if not pid or not start or tmux.proc_start(pid) != start or tmux.proc_parent(pid) != 1:
            continue
        survivor = stop_pid(int(pid))
        print("crew: %s orphaned lead %s (pid %s, started %s) from a lost tmux server" % (
            "could not stop" if survivor else "stopped", name, pid, start))


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
    p.add_argument("--coordinator-only", action="store_true", help="start no role windows (as launch.roles = none)")


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


def resume_ok(values):
    engine = values["engines.coordinator"]
    if launch(values, "resume") != "fresh" and engine not in ("claude-code", "codex"):
        print("crew: refusing to start: launch.resume needs a claude-code or codex coordinator, not %s" % engine)
        return False
    return True


def coordinator_cmd(values, project_dir, state):
    """The coordinator's harness command; RuntimeError when the harness refuses the profile."""
    engine, resume = values["engines.coordinator"], launch(values, "resume")
    if engine in ("pi", "cursor", "muse"):  # coordinator uses the harness's configured model and thinking level
        return shlex.join(harness(engine, "", "", project_dir, state, values["runtime.options.permission_mode"], values))
    cmd = ENGINE_CMD[engine] if engine == "claude-code" else shlex.join(  # Claude Code: trust dialog (tmux.md)
        ["codex", "-c", codex_trust(project_dir)])
    if resume != "fresh":  # ask opens the harness picker, which would take the pointer as a search term or id
        cmd += " --resume" if engine == "claude-code" else " resume"
        cmd += "" if resume == "ask" else " " + shlex.quote(resume)
    return cmd


def attach_hint(session):
    """The owner's attach line on the crew's own server (#818)."""
    own = tmux.backends["tmux"].server() if tmux.name == "tmux" else []
    return shlex.join(["tmux", *own, "attach", "-t", session])


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
    line = LAUNCH.removesuffix(' "%s"') % cmd if launch(values, "resume") == "ask" else LAUNCH % (cmd, POINTER)
    tmux.new_session(session, window, project_dir, env, line, private_env=private)
    print("crew: started %s (window 0 %s, %s); attach with: %s" % (
        session, window, values["engines.coordinator"], attach_hint(session)))
    return 0


def run(args):
    if args.team:
        return team(args)
    values, session, state = profile(args)
    if not slack_ok(values):
        return 1
    if tmux.has_session(session):
        print("crew: %s already running; attach with: %s" % (session, attach_hint(session)))
        return 0
    try:
        notes = role_notes(values, state, "coordinator")
    except RuntimeError as e:
        print(e)
        return 1
    if not codex_ok(values) or not resume_ok(values):
        return 1
    if not render_briefs(args, args.project, state):
        return 1
    record_binding(values, args.project, args)
    if notes:
        with open(brief_src(state, "coordinator"), "a", encoding="utf-8") as f:
            f.write(notes)
    if launch(values, "coordinator") == "none":
        print("crew: preflight ok; launch.coordinator = none, so no session started (render: %s)" %
              os.path.join(state, "render"))
        return 0
    project_dir = os.path.dirname(os.path.abspath(args.project))
    if values["engines.coordinator"] == "claude-code":
        install_stop_hook(project_dir, state)
    reap_orphans(state)
    if start(values, session, state, project_dir, {"CREW_BRIEF": brief_src(state, "coordinator"),
                                                   "CREW_PROJECT": os.path.abspath(args.project)}):
        return 1
    reconcile(state)
    roles = "none" if args.coordinator_only else launch(values, "roles")
    if roles != "tmux":
        print("crew: launch.roles = %s; started no role windows" % roles)
        return 0
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
        print("crew: %s already running; attach with: %s" % (session, attach_hint(session)))
        return 0
    try:
        notes = role_notes(values, root, "coordinator")
    except RuntimeError as e:
        print(e)
        return 1
    if not codex_ok(values) or not resume_ok(values):
        return 1
    for ref, v, state in repos:
        if not render_briefs(args, ref, state):
            return 1
        record_binding(v, ref, args)
    if launch(values, "coordinator") == "none":
        print("crew: preflight ok; launch.coordinator = none, so no session started (render: %s)" % root)
        return 0
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
