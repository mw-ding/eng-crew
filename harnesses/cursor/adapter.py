"""Cursor harness adapter (docs/runtimes/harness-adapters.md#cursor-cursor)."""
import os
import re
import shutil
import subprocess

EXECUTABLE = "cursor-agent"
TITLE = "Cursor"
ENGINE_RANK, LAUNCH_RANK = 5, 3
LOGIN_STATUS = ["auth", "status"]
PERMISSION = {"bypass": ["--force"]}
PERMISSION_REFUSAL = "crew: Cursor supports only permission_mode=bypass in this adapter"
QUOTA = re.compile(r"^\s*Error: (?:\w+ )?usage limit reached\b")  # Error: Weekly usage limit reached. It resets in 1 day. (#631)


def role_argv(model, effort, wt, state, flags):
    """Cursor has no CLI effort flag: effort stays in attribution only."""
    return ["cursor-agent", *flags] + (["--model", model] if model else [])


def coordinator_argv(project_dir, state, flags):
    """Cursor's configured model."""
    return role_argv("", "", project_dir, state, flags)


def foreground_tty(tty):
    """Cursor's shell launcher execs its bundled Node with the adjacent index.js; generic Node is not proof."""
    binary = shutil.which("cursor-agent")
    if not binary:
        return False
    directory = os.path.dirname(os.path.realpath(binary))
    out = subprocess.run(["ps", "-o", "stat=", "-o", "args=", "-t", tty], capture_output=True, text=True).stdout
    for line in out.splitlines():
        stat, _, command = line.strip().partition(" ")
        argv = command.split()
        if "+" in stat and argv[:2] == [os.path.join(directory, "node"), os.path.join(directory, "index.js")]:
            return True
    return False
