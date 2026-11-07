"""Pi harness adapter (docs/runtimes/harness-adapters.md#pi-pi)."""

EXECUTABLE = "pi"
TITLE = "Pi"
ENGINE_RANK, LAUNCH_RANK = 4, 2
LOGIN_STATUS = ["auth", "status"]
PERMISSION = {"bypass": ["--approve"]}  # trusts project-local resources for this process
PERMISSION_REFUSAL = "crew: Pi supports only permission_mode=bypass; no built-in approvals or sandbox"


def role_argv(model, effort, wt, state, flags):
    return ["pi", *flags] + (["--model", model, "--thinking", effort] if model else [])


def coordinator_argv(project_dir, state, flags):
    """Pi's configured model and thinking level."""
    return role_argv("", "", project_dir, state, flags)
