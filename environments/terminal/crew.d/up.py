"""`mdstack up` starts a repo's tmux crew, or a team's (one session for every repo in a team file), with the coordinator
in window 0, launched by its harness adapter (docs/runtimes/harness-adapters.md). When the profile can use an engine
whose adapter declares a host check, refuse before rendering on a failed one: for Codex, a host hooks.json or inline
config.toml hook that lacks stored trust. Never write Codex config.

`runtime.options.launch` picks the topology: coordinator tmux|none, roles tmux|hosted|none, resume fresh|ask|<id>.
`mdstack up ROLE` starts one instance of a running crew's role whose `lifecycle` has the `manual` wake, up to its `max`;
`mdstack up` starts each lifecycle role's `min`, and the watcher scales idle instances down to it (#1231,
docs/roles-registry.md#lifecycle). Each watcher scan also runs routine_tick: a due routine of a lifecycle role whose
`wake` has `routine` starts an instance when none runs and messages one instance the routine file (#1247,
docs/routines.md#terminal).

Usage: mdstack up [ROLE] (--project FILE[#REPO] | --team FILE) [--org-profile FILE] [--inputs DIR] [--coordinator-only]
"""
import argparse
import contextlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
from crew_shared import (
    brief_src, commands, coordinator_harness, CREW_BIN, crew_render, HERE, harnesses, kill_run, LAUNCH, load, NAMES,
    POINTER, profile, ownership_module, proc, require_ownership, role_notes, ROLES, ROOT, runs, sandbox_env, stop_pid,
    tmux)


TEMPLATES = os.path.join(os.path.dirname(HERE), "templates")
LAUNCH_DEFAULTS = {"coordinator": "tmux", "roles": "tmux", "resume": "fresh", "reconcile": "backend"}
crew_routines = load("crew_routines", "core/crew-routines.py")
ROUTINES = crew_routines.load(os.path.join(ROOT, "roles"))[0]  # (role, routine) -> table; check-repo rejects bad ones


def launch(values, key):
    return values.get("runtime.options.launch." + key, LAUNCH_DEFAULTS[key])


def record_binding(values, project, args):
    """Record a non-GitHub markers backend's `markers.read-item` and `markers.write-item` commands for the ownership
    guard and mdstack handoff, and a non-GitHub tracker or change backend's live reads (#606, docs/handoff.md Bindings).

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
                "the control item reads as read-only" if op == "read-item" else "mdstack handoff refuses it"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bindings, f)


def reap_orphans(state):
    """Before a new session: stop each recorded lead whose pane process outlived its tmux server (Codex ignores SIGHUP,
    #818). Only the recorded pid with its recorded start time, reparented to init, counts; any other process is
    left alone."""
    for name, rec in commands()["lead"].records(state):
        pid, start = rec.get("pane_pid"), rec.get("pane_start")
        if not pid or not start or proc.proc_start(pid) != start or proc.proc_parent(pid) != 1:
            continue
        survivor = stop_pid(int(pid))
        print("crew: %s orphaned lead %s (pid %s, started %s) from a lost tmux server" % (
            "could not stop" if survivor else "stopped", name, pid, start))


def reconcile(state):
    """After mdstack up rebuilt the session from disk: report recorded runs; never respawn them (tmux.md Q7)."""
    names = [n for n, _ in runs(state)]
    if names:
        print("crew: rebuilt from %s; recorded runs now probe missing: %s (mdstack status; mdstack restart <window>)" % (
            state, ", ".join(names)))


def lifecycles():
    return {r: v["lifecycle"] for r, v in ROLES.items() if "lifecycle" in v}


def instances(state, role):
    return sorted(n for n, rec in runs(state) if rec["role"] == role)


def start_instance(args, values, state, role):
    """Spawn one instance of a lifecycle role: its first pass, named by window_name, then with 2, 3 up to max appended
    (no separator: mdstack kill's scratch glob takes <name>-* as the run's own files)."""
    if not require_ownership(values):  # the spawn ownership gate, which the CLI applies only to a typed mdstack spawn
        return 1
    data, taken = ROLES[role], set(instances(state, role))
    base = data["window_name"].format(name=values.get(data["identity_key"] + ".name", NAMES[role]).lower(),
                                      **{"pass": data["passes"][0]})
    name = next(n for n in [base] + ["%s%d" % (base, i) for i in range(2, data["lifecycle"]["max"] + 1)]
                if n not in taken)
    return commands()["spawn"].run(argparse.Namespace(
        role=role, instance=name, issue=None, pr=None, pass_=None, head=None, round=1, tier=None, timeout=15.0,
        project=args.project, org_profile=args.org_profile))


def up_role(args):
    """mdstack up ROLE: one more instance of a role whose lifecycle has the manual wake, refused at its max."""
    life = lifecycles().get(args.role)
    if args.team or not life or "manual" not in life["wake"]:
        print("crew: refusing up %s: %s" % (args.role, "a role takes --project, not --team" if args.team else
                                             "no lifecycle with the manual wake (docs/roles-registry.md#lifecycle)"))
        return 2
    values, _, state = profile(args)
    running = instances(state, args.role)
    if len(running) >= life["max"]:
        print("crew: refusing up %s: at its lifecycle max %d (%s)" % (args.role, life["max"], ", ".join(running)))
        return 1
    return start_instance(args, values, state, args.role)


def scale_down(values, session, state, now):
    """Kill lifecycle instances idle for idle_ttl seconds, longest idle first, down to the role's min. Idle means no
    pane output and no inbox message since then, and none unacknowledged; a backend that reports no pane activity
    never scales. Returns the killed names."""
    killed = []
    for role, life in lifecycles().items():
        recs = [(n, rec) for n, rec in runs(state) if rec["role"] == role]
        idle = []
        for name, rec in recs if life["idle_ttl"] else []:
            p = tmux.pane(session, rec["index"])
            if not p or p["id"] != rec.get("pane_id") or not p["activity"].isdigit() or not int(p["activity"]):
                continue
            since, inbox = int(p["activity"]), os.path.join(state, "inbox", name + ".jsonl")
            if os.path.exists(inbox):
                status = os.path.join(state, "status", name + ".status")
                with open(status) if os.path.exists(status) else io.StringIO() as f:
                    acks = {line[5:].strip() for line in f if line.startswith("ack: ")}
                with open(inbox) as f:
                    if any(json.loads(line)["id"] not in acks for line in f if line.strip()):
                        continue
                since = max(since, os.path.getmtime(inbox))
            if now - since >= life["idle_ttl"]:
                idle.append((since, name))
        for _, name in sorted(idle)[:max(0, len(recs) - life["min"])]:
            if not kill_run(values, session, state, name):
                killed.append(name)
    return killed


def routine_tick(args, values, state, now):
    """Due routines of lifecycle roles whose wake has `routine` (docs/routines.md#terminal). For each due one, start an
    instance when none runs (refused at max like mdstack up ROLE), then `mdstack send` the first instance a `routine` message
    naming the routine file. The slot record is routines/<role>.<routine>.json {"at", "outcome"}; a skipped miss
    records its slot unrun. A role with no due routine starts nothing, so an ephemeral role stays at zero. Returns the
    watcher wakes: one `routine-missed` per escalated miss."""
    wakes = []
    for (role, name), routine in sorted(ROUTINES.items()):
        life = lifecycles().get(role)
        if not life or "routine" not in life["wake"]:
            continue
        path = os.path.join(state, "routines", "%s.%s.json" % (role, name))
        try:
            with open(path) as f:
                last = json.load(f)
        except (OSError, ValueError):
            last = None
        action, slot = crew_routines.due(routine, values, last, now)
        if action is None:
            continue
        at, outcome = now, "skipped: missed"
        if action == "skip":
            at = slot
        else:
            if action == "escalate":
                wakes.append({"reason": "routine-missed", "event": "%s/%s missed its %s deadline" % (
                    role, name, routine["deadline"])})
            code = 0 if instances(state, role) else start_instance(args, values, state, role)
            running = instances(state, role)
            if code or not running:
                outcome = "failed: no %s instance started" % role
            else:
                r = subprocess.run([sys.executable, CREW_BIN, "send", running[0], "routine", routine["path"],
                                    "--project", args.project], capture_output=True, text=True, timeout=120)
                out = (r.stdout.strip().splitlines() or ["exit %d" % r.returncode])[-1]
                outcome = "sent: " + running[0] if r.returncode == 0 else "failed: " + out
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w") as f:
            json.dump({"at": at, "outcome": outcome}, f)
        os.replace(path + ".tmp", path)
    return wakes


def register(sub):
    p = sub.add_parser("up")
    p.add_argument("role", nargs="?", help="start one instance of this lifecycle role (docs/roles-registry.md)")
    which = p.add_mutually_exclusive_group()
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


def host_ok(values):
    """Refuse before any write when an engine the profile can use fails its adapter's host check (Codex: a host hook
    lacks stored trust)."""
    used = {values["engines.coordinator"], values.get("engines.fallback_engine")} | {
        e.split("/")[0] for k, order in values.items() if re.fullmatch(r"engines\.(roles\.)?\w+\.order", k) for e in order}
    for engine in harnesses.LAUNCHABLE:
        if engine in used and hasattr(harnesses.ADAPTERS[engine], "host_checks"):
            for status, check, detail, hint in harnesses.ADAPTERS[engine].host_checks():
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
    if launch(values, "resume") != "fresh" and engine not in harnesses.RESUMABLE:
        print("crew: refusing to start: launch.resume needs a %s coordinator, not %s" % (
            " or ".join(harnesses.RESUMABLE), engine))
        return False
    return True


def coordinator_cmd(values, project_dir, state):
    """The coordinator's harness command; RuntimeError when the harness refuses the profile."""
    # ask opens the harness picker, which would take the pointer as a search term or id
    return shlex.join(coordinator_harness(values["engines.coordinator"], project_dir, state,
                                          values["runtime.options.permission_mode"], values, launch(values, "resume")))


def attach_hint(session):
    """The owner's attach line (on the crew's own tmux server, #818)."""
    return tmux.attach_hint(session)


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
    if args.role:
        return up_role(args)
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
    if not host_ok(values) or not resume_ok(values):
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
    coordinator = harnesses.ADAPTERS[values["engines.coordinator"]]
    if hasattr(coordinator, "coordinator_setup"):  # Claude Code: the Stop-hook turn-end guard
        coordinator.coordinator_setup(project_dir, state)
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
    for role, life in lifecycles().items():  # always-on and elastic floors
        for _ in range(life["min"] - len(instances(state, role))):
            if start_instance(args, values, state, role):
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
    if not host_ok(values) or not resume_ok(values):
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
    coordinator = harnesses.ADAPTERS[values["engines.coordinator"]]
    if hasattr(coordinator, "coordinator_setup"):
        for _, _, state in repos:
            coordinator.coordinator_setup(project_dir, state)
    if start(values, session, root, project_dir, {"CREW_BRIEF": brief, "CREW_PROJECT": os.path.abspath(repos[0][0]),
                                                  "CREW_TEAM": os.path.abspath(args.team)}):
        return 1
    for _, _, state in repos:
        reconcile(state)
    return 0
