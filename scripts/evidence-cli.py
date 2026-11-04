#!/usr/bin/env python3
"""Capture a CLI command/output pair for inline PR evidence (#652).

Usage:
  evidence-cli.py [--label R1] [--setup FILE] [--scrub-env VAR]...
      [--volatile NOTE]... [--runner-fallback LINE] -- <argv...>
  evidence-cli.py [--label R1] --runner REF

Runs <argv> in the current directory and prints the pair from
templates/evidence/cli-exit-stdout.md: a header line with the proof label,
capture SHA and working directory (relative to the repo root), a copyable `sh`
block, then a `text` block with `# scrubbed:` / `# volatile:` notes,
`exit: <code>`, `--- stdout` and `--- stderr`. Paste the output verbatim.

--setup FILE prepends the file's shell text to the `sh` block; the block then
runs as one `sh -c` script, so setup output lands in stdout (keep it quiet).
Scrubbing: each --scrub-env VAR value becomes `$VAR`, the absolute working
directory becomes `<cwd>`, $HOME becomes `~`, and obvious token shapes become
`<redacted>` (step-summary.py's token patterns, without its generic
`key=value` rule, which would rewrite ordinary output and the `sh` block). The helper exits 0 after a capture;
the command's own exit code is in the `exit:` line. Python 3 standard library
only.

--runner REF renders a stored `crew runner` result (REF: a job id under
$CREW_STATE/runner/, or a result.json path) as a capture whose header names
`runner:<host>/<job_id>` and the head sha, with each command's exit code and
log tail. It refuses (exit 2) a result whose head is not the checkout's HEAD.
--runner-fallback LINE adds the runner's `runner: ...; ran locally` line to a
local capture.
"""
import argparse
import importlib.util
import json
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
            pairs.append((value, "$" + var, f"${var} (value of env var {var})"))
    cwd = os.getcwd()
    for path in sorted({cwd, os.path.realpath(cwd)}, key=len, reverse=True):
        pairs.append((path, "<cwd>", "<cwd> (capture working directory)"))
    home = os.path.expanduser("~")
    if home not in ("", "/", "~"):
        pairs.append((home, "~", "~ (home directory)"))
    return pairs


def redact_tokens(text):
    for rx in step_summary.REDACTIONS:
        text = rx.sub(step_summary.REDACTED, text)
    text = step_summary.BEARER.sub(r"\1" + step_summary.REDACTED, text)
    return step_summary.URL_CRED.sub(
        r"\1" + step_summary.REDACTED + r"\2", text)


def scrub(text, pairs, notes):
    for value, placeholder, note in pairs:
        if value in text:
            text = text.replace(value, placeholder)
            notes.setdefault(note, None)
    redacted = redact_tokens(text)
    if redacted != text:
        notes.setdefault("<redacted> (token-shaped value)", None)
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


FALLBACK = re.compile(r"runner: \S.*; ran locally")


def runner_capture(label, ref):
    path = ref if ref.endswith(".json") else os.path.join(
        os.environ.get("CREW_STATE", ""), "runner", os.path.basename(ref), "result.json")
    try:
        with open(path) as fh:
            done = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"evidence-cli: cannot read runner result {ref}: {exc}", file=sys.stderr)
        return 2
    head = git("rev-parse", "HEAD")
    if done.get("head") != head:
        print(f"evidence-cli: runner result is at {done.get('head')}, not the "
              f"checkout head {head}; it does not count", file=sys.stderr)
        return 2
    pairs, notes = scrubbers([]), {}
    checks = [f for c in done.get("spec", []) for f in c.get("files", [c["command"]])]
    shown = shlex.join(["crew", "runner", "run", "--head", head, "--", *checks])
    red = any(c["exit"] for c in done["commands"])
    body = f"runner:{done['host']}/{done['job_id']} head={head}\n"
    body += f"result: {'red' if red else 'pass'}\n"
    for c in done["commands"]:
        body += f"--- {c['command']} exit {c['exit']}\n{section(scrub(c.get('tail', ''), pairs, notes))}"
    body = "".join(f"# scrubbed: {n}\n" for n in notes) + body
    sh_fence, text_fence = fence_for(shown), fence_for(body)
    print(f"Proof {label} · `runner:{done['host']}/{done['job_id']}` · head `{head}`"
          " · `scripts/evidence-cli.py --runner`\n")
    print(f"{sh_fence}sh\n{section(shown)}{sh_fence}\n")
    print(f"{text_fence}text\n{body}{text_fence}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="R1", help="proof label, default R1")
    ap.add_argument("--setup", help="shell file prepended to the sh block")
    ap.add_argument("--scrub-env", action="append", default=[], metavar="VAR",
                    help="replace this env var's value with $VAR")
    ap.add_argument("--volatile", action="append", default=[], metavar="NOTE",
                    help="name a field the verifier may ignore")
    ap.add_argument("--runner", metavar="REF",
                    help="render a stored crew runner result instead of running")
    ap.add_argument("--runner-fallback", metavar="LINE",
                    help="the runner's `runner: ...; ran locally` line")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.runner:
        return runner_capture(args.label, args.runner)
    if args.runner_fallback and not FALLBACK.fullmatch(args.runner_fallback):
        ap.error("--runner-fallback must be a `runner: ...; ran locally` line")
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
    body += f"# {args.runner_fallback}\n" if args.runner_fallback else ""
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
