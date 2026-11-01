#!/bin/sh
# Prints the Codex and Claude Code role-window argv for a linked worktree. Run from the repo root.
set -e
scratch=$(mktemp -d); cd "$scratch"
git init -q repo && git -C repo -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
git -C repo worktree add -q -b b "$scratch/wt"
cd - >/dev/null
PYTHONPATH=scripts/crew.d python3 - "$scratch" <<'P'
import os, sys
import _shared
s = os.path.realpath(sys.argv[1])
for engine in ("codex", "claude-code"):
    argv = _shared.harness(engine, "m", "low", s + "/wt", "<state>", "safe")
    print(engine, " ".join("projects=<trust>" if a.startswith("projects=") else a.replace(s, "<scratch>") for a in argv))
P
