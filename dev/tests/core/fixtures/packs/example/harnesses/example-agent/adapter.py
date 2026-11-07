"""Fake harness adapter for the fixture pack: the same module interface as harnesses/<engine>/adapter.py."""
EXECUTABLE = "example-agent"
TITLE = "Example Agent"
LOGIN_STATUS = ["whoami"]
PROMPTS = [(r"Allow this action\?$", r"Enter to allow")]
BUSY = r"working…"


def role_argv(model, effort, wt, state, flags):
    return [EXECUTABLE, "--model", model, "--effort", effort, "--dir", state, *flags]


def coordinator_argv(project_dir, state, flags):
    return [EXECUTABLE]
