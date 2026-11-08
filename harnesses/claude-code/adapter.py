"""Claude Code harness adapter (docs/runtimes/harness-adapters.md#claude-code-claude-code)."""
import json
import os
import re
import shlex

CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "cli", "mdstack")
EXECUTABLE = "claude"
TITLE = "Claude Code"
ENGINE_RANK, LAUNCH_RANK = 0, 0
LOGIN_STATUS = ["auth", "status"]
# runtime.options.permission_mode (tmux.md mdstack spawn): bypass runs any command in the worktree without asking (#293).
PERMISSION = {"bypass": ["--permission-mode", "bypassPermissions",  # no warning screen, set per process only
                         "--settings", '{"skipDangerousModePermissionPrompt":true}'],
              "auto": ["--permission-mode", "auto"], "safe": ["--permission-mode", "acceptEdits"]}
RESUME = ["--resume"]
# Blocking prompts (#289): permission (proceed, make this edit, create) and folder trust, old and current.
PROMPTS = [(r"Do you want to .+\?", r"Esc to cancel"),
           (r"Do you trust the files in this folder\?$", r"Enter to confirm · Esc to cancel"),
           (r"Accessing workspace:$", r"Enter to confirm · Esc to cancel")]
FATAL = r'⎿\s+API Error: [45]\d\d\b.*"type": ?"error"'  # ⎿  API Error: 400 {"type":"error",...}
TRANSIENT = re.compile(r"⎿\s+API Error\b.*\b(?:429|5\d\d)\b|⎿\s+.*\brate.?limit", re.I)  # API Error (529 …) · Retrying
COMPOSER = "❯"
BUSY = re.compile(r"esc to interrupt|^[✽✻✶✢·*] .+… \([^\n]+\)", re.M)  # a lowercased screen mid-turn
INSTALL_ROLES = ("coordinator", "builder", "reviewer", "synthesizer")
INSTALL_TARGETS = [".claude/agents/crew-%s.md" % r for r in ("builder", "reviewer", "synthesizer")] + [
    ".claude/skills/crew-coordinator/SKILL.md", ".claude/settings.local.json"]


def role_argv(model, effort, wt, state, flags):
    """--add-dir state: every pass reads its brief and writes $CREW_STATUS, verdicts/ (#234 F15). Claude's --add-dir
    takes several values, so a flag must end it before the prompt."""
    return ["claude", "--model", model, "--effort", effort, "--add-dir", state, *flags]


def coordinator_argv(project_dir, state, flags):
    """No model or effort flags; the folder-trust dialog is accepted once by the owner (tmux.md)."""
    return ["claude"]


def is_guard(hook, state):
    """Whether a Stop hook is a crew turn-end guard for this state, from any bundle, link or checkout path."""
    try:
        argv = shlex.split(hook.get("command") or "")
    except ValueError:
        return False
    return len(argv) == 5 and argv[0] == "python3" and os.path.basename(argv[1]) in ("mdstack", "crew") and \
        argv[2:] == ["guard", "--state", state]


def stop_hook_settings(settings, state):
    """Add the turn-end guard to a settings object, preserving every other key. The command names the resolved
    bundle, so a run through the mdstack link matches; a guard for this state from another path, or naming the old
    crew CLI (#1233), is re-pointed (#1088)."""
    command = shlex.join(["python3", os.path.realpath(CLI), "guard", "--state", state])
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


def coordinator_setup(project_dir, state):
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


def coordinator_checks(values, project_dir):
    """A Claude Code coordinator opens at the folder-trust dialog until it is accepted once for the project directory
    or a parent (docs/runtimes/harness-adapters.md)."""
    path = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~"), ".claude.json")
    try:
        with open(path, "rb") as f:
            projects = json.load(f).get("projects", {})
    except FileNotFoundError:
        projects = {}
    d = os.path.realpath(project_dir)
    while not projects.get(d, {}).get("hasTrustDialogAccepted"):
        if d == os.path.dirname(d):
            window = values.get("identities.coordinator.name", "ash").lower()
            return [("human", "claude trust", "not accepted for " + project_dir, "after mdstack up, accept the folder-"
                     "trust dialog once with mdstack attach %s --rw (never a blind Enter: it picks No, exit)" % window)]
        d = os.path.dirname(d)
    return [("ok", "claude trust", d, "")]


def install_targets(project, state, pointer, check):
    """Agent and skill files with a one-line brief pointer, and the Stop hook in the local settings (bootstrap Q4)."""
    targets = {}
    for role in INSTALL_ROLES:
        if role == "coordinator":
            path = project.parent / ".claude/skills/crew-coordinator/SKILL.md"
        else:
            path = project.parent / (".claude/agents/crew-" + role + ".md")
        targets[path] = ('---\nname: crew-%s\ndescription: mdstack %s role\n---\n\n%s\n' %
                         (role, role, pointer(role)))
    path = project.parent / ".claude/settings.local.json"
    check(path)
    settings = json.loads(path.read_text()) if path.exists() else {}
    targets[path] = json.dumps(stop_hook_settings(settings, str(state)), indent=2) + "\n"
    return targets
