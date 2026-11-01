#!/usr/bin/env python3
"""Append one structured step line to a run's summary.md (M8 observe protocol).

Usage:
  step-summary.py --ref issue-85 --run-id r1 --step build --status ok \\
      --duration 42 --outcome "built 3 targets" [--log steps/build.log]
  step-summary.py --dir <run-dir> --step test --status fail --duration 3m04s \\
      --outcome-from-log steps/test.log --log steps/test.log

The run dir is `<root>/.crew/runs/<ref>/<run-id>/` (or --dir). summary.md is
created with a header on the first call; every call appends one step block.
The outcome is cut to 3 lines of 200 characters and obvious token patterns are
redacted. Raw logs are never copied or echoed: --outcome-from-log reads only
the last 3 non-empty lines. Python 3 standard library only. See docs/observe.md.
"""
import argparse
import datetime
import os
import re
import sys

STATUSES = ("ok", "fail", "skip", "warn")
MAX_LINES, MAX_LINE_CHARS = 3, 200
TAIL_BLOCK = 8192
# Total bytes tail_of() may read, far above MAX_LINES * MAX_LINE_CHARS.
TAIL_MAX_BYTES = 4 * TAIL_BLOCK
NAME = re.compile(r"[A-Za-z0-9._-]+")
REDACTED = "<redacted>"
# Order matters: the specific token shapes run before the generic key=value one.
REDACTIONS = [
    re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Za-z0-9])"),
]
BEARER = re.compile(r"(bearer\s+)[^\s\"']+", re.I)
URL_CRED = re.compile(r"(://[^/\s:@]+:)[^/\s@]+(@)")
KEY_VALUE = re.compile(
    r"((?:token|secret|password|passwd|api[_-]?key)\s*[=:]\s*)[^\s\"']+", re.I)


def redact(text):
    for rx in REDACTIONS:
        text = rx.sub(REDACTED, text)
    text = BEARER.sub(r"\1" + REDACTED, text)
    text = URL_CRED.sub(r"\1" + REDACTED + r"\2", text)
    return KEY_VALUE.sub(r"\1" + REDACTED, text)


def clean_outcome(text):
    lines = [" ".join(l.split()) for l in text.splitlines()]
    lines = [l for l in lines if l][:MAX_LINES]
    out = []
    for line in lines:
        line = redact(line)
        if len(line) > MAX_LINE_CHARS:
            line = line[:MAX_LINE_CHARS - 3] + "..."
        out.append(line)
    return out


def tail_of(path, n=MAX_LINES):
    """Last n non-empty lines, reading at most TAIL_MAX_BYTES from the end.

    Blocks are read backwards and joined once. Reading stops once n + 1
    non-empty lines are buffered, at the start of the file, or at the byte
    cap, whichever comes first. When the cap cuts the data, the first line may
    be partial: it is dropped if n other lines exist, else kept (clean_outcome
    truncates it anyway), so a log ending in one huge line yields its tail.
    """
    with open(path, "rb") as fh:
        pos = fh.seek(0, os.SEEK_END)
        blocks, got = [], 0
        while pos > 0 and got < TAIL_MAX_BYTES:
            step = min(TAIL_BLOCK, pos, TAIL_MAX_BYTES - got)
            pos -= step
            fh.seek(pos)
            blocks.append(fh.read(step))
            got += step
            data = b"".join(reversed(blocks))
            if sum(1 for l in data.splitlines() if l.strip()) > n:
                break
    data = b"".join(reversed(blocks))
    lines = [l for l in data.decode("utf-8", errors="replace").splitlines()
             if l.strip()]
    if pos > 0 and len(lines) > n:
        lines = lines[1:]  # first line was cut by the cap
    return "\n".join(lines[-n:])


def fmt_duration(value):
    value = value.strip()
    try:
        secs = float(value)
    except ValueError:
        return " ".join(value.split())[:20] or "n/a"
    if secs < 60:
        return "%gs" % round(secs, 1)
    return "%dm%02ds" % (secs // 60, secs % 60)


def run_dir(args):
    if args.dir:
        return args.dir
    if not (args.ref and args.run_id):
        sys.exit("step-summary: give --dir, or both --ref and --run-id")
    for label, value in (("--ref", args.ref), ("--run-id", args.run_id)):
        if not NAME.fullmatch(value) or not value.strip("."):
            sys.exit("step-summary: %s must match [A-Za-z0-9._-]+ and not be "
                     "only dots" % label)
    return os.path.join(args.root, ".crew", "runs", args.ref, args.run_id)


def resolve_log(rdir, path):
    """Absolute paths are the caller's choice; relative ones must stay in rdir."""
    if os.path.isabs(path):
        return path
    base = os.path.realpath(rdir)
    full = os.path.realpath(os.path.join(base, path))
    if os.path.commonpath([base, full]) != base:
        sys.exit("step-summary: relative --outcome-from-log escapes the run dir")
    return full


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def header(args):
    ref = args.ref or "n/a"
    run = args.run_id or os.path.basename(os.path.normpath(run_dir(args)))
    return ("# Step summary\n\n- Ref: `%s`\n- Run: `%s`\n- Started: %s\n\n"
            "## Steps\n\n" % (ref, run, now()))


def step_block(args, outcome):
    name = " ".join(args.step.split())
    parts = ["- **%s** · %s · %s" % (name, args.status, fmt_duration(args.duration))]
    parts += ["  > " + l for l in outcome]
    if args.log:
        parts.append("  log: `%s`" % " ".join(args.log.split()))
    return "\n".join(parts) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", help="run directory (overrides --root/--ref/--run-id)")
    ap.add_argument("--root", default=".", help="worktree root (default: cwd)")
    ap.add_argument("--ref", help="issue-<n> or pr-<n>")
    ap.add_argument("--run-id", help="run id, for example r1 or a UTC timestamp")
    ap.add_argument("--step", required=True)
    ap.add_argument("--status", required=True, choices=STATUSES)
    ap.add_argument("--duration", default="n/a", help="seconds or a text like 3m04s")
    ap.add_argument("--outcome", default="", help="1-3 line outcome or error tail")
    ap.add_argument("--outcome-from-log", help="use the last 3 lines of this log (relative: to the run dir)")
    ap.add_argument("--log", help="path to the full log (recorded, never read)")
    args = ap.parse_args(argv)

    text = args.outcome
    if args.outcome_from_log:
        log_path = resolve_log(run_dir(args), args.outcome_from_log)
        text = (text + "\n" if text else "") + tail_of(log_path)
    outcome = clean_outcome(text)
    d = run_dir(args)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "summary.md")
    try:  # create with the header exactly once
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as fh:
            fh.write(header(args))
    except FileExistsError:
        pass
    with open(path, "a") as fh:
        fh.write(step_block(args, outcome))
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
