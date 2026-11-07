"""Muse harness adapter (docs/runtimes/harness-adapters.md#muse-muse). A contributor-tier harness: the crew core
refuses its launch unless the repository is verified public (roles.md Hard rules)."""
import re

EXECUTABLE = "muse"
TITLE = "Muse"
ENGINE_RANK, LAUNCH_RANK = 2, 4
LOGIN_STATUS = ["auth", "status"]
PERMISSION = {"bypass": ["--yolo"]}  # trusts the workspace, no approvals or sandbox for this process
PERMISSION_REFUSAL = "crew: Muse supports only permission_mode=bypass; auto and safe are unverified"
CONTRIBUTOR_TIER = True
PROCESS = re.compile(r"muse-bin-[A-Za-z0-9][A-Za-z0-9._-]*")  # a versioned foreground name
PROMPTS = [(r"Do you trust this workspace\?$", r"Use Up/Down or 1/2, then Enter\. Esc quits\.$"),
           (r"Sign in at this page:$", r"Esc cancel$")]


def role_argv(model, effort, wt, state, flags):
    return ["muse", *flags] + (["--model", model, "--reasoning-effort", effort] if model else [])


def coordinator_argv(project_dir, state, flags):
    """Muse's configured model and effort."""
    return role_argv("", "", project_dir, state, flags)
