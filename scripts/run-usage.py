#!/usr/bin/env python3
"""Print one usage line for a role run: wall-clock time, tokens and model (#1557).

Usage:
  run-usage.py --run <state>/runs/<window>.json
  run-usage.py --engine <engine> --dir <worktree> --start <UTC ISO time> [--model M] [--effort E]

A run record gives the engine, worktree, start time, model and effort; flags
override it, and a run without a record (the coordinator) passes them alone.
Wall-clock time runs from the start to now. Tokens come from the engine's
harness adapter `usage(directory, start)` reader of its local session log
(docs/runtimes/harness-adapters.md); an adapter without a reader, or no log
entry since the start, prints `tokens n/a`, never an estimate. The model is
the one the log names, else the record's. For example:

  Run: 23m 10s · 1.24M in (1.1M cached) / 38.2k out · claude-opus-5-5 (high)

Informational only: no gate, verdict, flavor or scheduler reads it. It never
prints a path or credential, and errors name no path. Python 3 standard
library only.
"""
import argparse
import datetime
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def harness():
    spec = importlib.util.spec_from_file_location("crew_harness", os.path.join(ROOT, "harnesses", "crew-harness.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def count(n):
    if n >= 999_500:
        return "%.3gM" % (n / 1e6)
    if n >= 1000:
        return "%.3gk" % (n / 1e3)
    return str(n)


def duration(seconds):
    s = max(0, int(seconds))
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return "%dh %02dm" % (h, m) if h else "%dm %02ds" % (m, s) if m else "%ds" % s


def line(engine, directory, start, model, effort, now, adapters):
    reader = getattr(adapters.get(engine), "usage", None)
    totals = reader(directory, start.timestamp()) if reader and directory else None
    tokens = "tokens n/a"
    if totals:
        tokens = "%s in (%s cached) / %s out" % (count(totals["input"]), count(totals["cached"]),
                                                 count(totals["output"]))
        model = totals.get("model") or model
    parts = ["Run: " + duration((now - start).total_seconds()), tokens]
    if model:
        parts.append(model + (" (%s)" % effort if effort else ""))
    return " · ".join(parts)


def parse_time(text):
    when = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    return when if when.tzinfo else when.replace(tzinfo=datetime.timezone.utc)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Print a role run's usage line.")
    ap.add_argument("--run", help="run record JSON")
    ap.add_argument("--engine")
    ap.add_argument("--dir", help="the run's worktree or working directory")
    ap.add_argument("--start", help="run start, UTC ISO 8601")
    ap.add_argument("--model")
    ap.add_argument("--effort")
    ap.add_argument("--now", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    record = {}
    if args.run:
        try:
            with open(args.run, encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, ValueError):
            print("run-usage: run record unreadable", file=sys.stderr)
            return 2
    engine = args.engine or record.get("engine")
    start = args.start or record.get("start")
    if not engine or not start:
        print("run-usage: need an engine and a start time (--run or --engine and --start)", file=sys.stderr)
        return 2
    try:
        start, now = parse_time(start), parse_time(args.now) if args.now else datetime.datetime.now(datetime.timezone.utc)
    except ValueError:
        print("run-usage: start is not an ISO 8601 time", file=sys.stderr)
        return 2
    print(line(engine, args.dir or record.get("worktree"), start, args.model or record.get("model"),
               args.effort or record.get("effort"), now, harness().ADAPTERS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
