#!/usr/bin/env python3
"""Capture a CLI command/output pair for inline PR evidence (#652).

Usage:
  evidence-cli.py [--label R1] [--setup FILE] [--scrub-env VAR]...
      [--volatile NOTE]... -- <argv...>

Runs <argv> in the current directory and prints the pair from
templates/evidence/cli-exit-stdout.md: a header line with the proof label,
capture SHA and working directory (relative to the repo root), a copyable `sh`
block, then a `text` block with `# scrubbed:` / `# volatile:` notes,
`exit: <code>`, `--- stdout` and `--- stderr`. Paste the output verbatim.

--setup FILE prepends the file's shell text to the `sh` block; the block then
runs as one `sh -c` script, so setup output lands in stdout (keep it quiet).
Scrubbing: each --scrub-env VAR value becomes `$VAR`, the absolute working
directory becomes `<cwd>`, $HOME becomes `~`, and obvious token shapes become
`<redacted>` (step-summary.py's patterns). The helper exits 0 after a capture;
the command's own exit code is in the `exit:` line. Python 3 standard library
only.
"""
import argparse
import importlib.util
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "step_summary", os.path.join(HERE, "step-summary.py"))
step_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step_summary)


def git(*args):
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def scrubbers(env_vars):
    pairs = []
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            pairs.append((value, "$" + var, f"${var} = value of env var {var}"))
    cwd = os.getcwd()
    for path in sorted({cwd, os.path.realpath(cwd)}, key=len, reverse=True):
        pairs.append((path, "<cwd>", "<cwd> = capture working directory"))
    home = os.path.expanduser("~")
    if home not in ("", "/", "~"):
        pairs.append((home, "~", "~ = home directory"))
    return pairs


def scrub(text, pairs, notes):
    for value, placeholder, note in pairs:
        if value in text:
            text = text.replace(value, placeholder)
            notes.setdefault(note, None)
    redacted = step_summary.redact(text)
    if redacted != text:
        notes.setdefault("<redacted> = token-shaped value", None)
    return redacted


def section(text):
    return text if not text or text.endswith("\n") else text + "\n"


def fence_for(*texts):
    longest = max([len(m) for t in texts for m in re.findall(r"`+", t)] or [0])
    return "`" * max(3, longest + 1)


def header(label):
    sha = git("rev-parse", "HEAD") or "unknown (not a git checkout)"
    if git("status", "--porcelain"):
        sha += " (dirty)"
    top = git("rev-parse", "--show-toplevel")
    cwd = os.path.relpath(os.getcwd(), top) if top else "<cwd>"
    return f"Proof {label} · `scripts/evidence-cli.py` · sha `{sha}` · cwd `{cwd}`"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Capture a CLI command/output evidence pair.")
    ap.add_argument("--label", default="R1", help="proof label, default R1")
    ap.add_argument("--setup", help="shell file prepended to the sh block")
    ap.add_argument("--scrub-env", action="append", default=[], metavar="VAR",
                    help="replace this env var's value with $VAR")
    ap.add_argument("--volatile", action="append", default=[], metavar="NOTE",
                    help="name a field the verifier may ignore")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        ap.error("missing command after --")

    script = shlex.join(command)
    if args.setup:
        with open(args.setup) as fh:
            script = section(fh.read()) + script
        run_argv = ["sh", "-c", script]
    else:
        run_argv = command
    try:
        result = subprocess.run(run_argv, capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, errors="replace")
    except OSError as exc:
        print(f"evidence-cli: cannot run {command[0]}: {exc}", file=sys.stderr)
        return 2

    pairs, notes = scrubbers(args.scrub_env), {}
    shown = scrub(script, pairs, notes)
    stdout = scrub(result.stdout, pairs, notes)
    stderr = scrub(result.stderr, pairs, notes)
    body = "".join(f"# scrubbed: {n}\n" for n in notes)
    body += "".join(f"# volatile: {v}\n" for v in args.volatile)
    body += (f"exit: {result.returncode}\n--- stdout\n{section(stdout)}"
             f"--- stderr\n{section(stderr)}")
    sh_fence, text_fence = fence_for(shown), fence_for(body)
    print(header(args.label) + "\n")
    print(f"{sh_fence}sh\n{section(shown)}{sh_fence}\n")
    print(f"{text_fence}text\n{body}{text_fence}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
