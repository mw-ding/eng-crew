#!/usr/bin/env python3
"""Run scripts/test-*.py files in parallel and report per-file results (#613).

Usage:
  run-tests.py [-j N] [--slowest K] [FILE ...]

With no FILE, runs every `scripts/test-*.py`. Each file runs once, as
`python3 <file>` from the repo root, in its own process with its output
captured. -j sets the worker count (default: CPU count, at most 8). Files in
SERIAL run one at a time after the parallel batch. The runner prints one line
per file as it finishes (status and duration), then the K slowest files, then
the full output of every failing file. Exit code: 1 if any file fails, else 0.
CI runs the full suite this way in the `repo-guard` job of
`.github/workflows/ci.yml`. Python 3 standard library only.
"""
import argparse
import concurrent.futures
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAX_DEFAULT_JOBS = 8
# Files that cannot share a machine with other tests (ports, cwd or global
# state). None found so far: every test uses temp dirs and ephemeral ports.
SERIAL = set()


def run_one(path):
    start = time.monotonic()
    proc = subprocess.run([sys.executable, path], cwd=ROOT, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return path, proc.returncode, time.monotonic() - start, proc.stdout.decode(errors="replace")


def rel(path):
    return os.path.relpath(path, ROOT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-j", "--jobs", type=int, default=min(os.cpu_count() or 1, MAX_DEFAULT_JOBS))
    ap.add_argument("--slowest", type=int, default=10, metavar="K")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args(argv)
    if args.jobs < 1:
        ap.error("-j must be at least 1")
    files = [os.path.abspath(f) for f in args.files] or sorted(glob.glob(os.path.join(HERE, "test-*.py")))
    files = list(dict.fromkeys(files))
    for f in files:
        if not os.path.isfile(f):
            ap.error("no such test file: %s" % f)
    parallel = [f for f in files if os.path.basename(f) not in SERIAL]
    serial = [f for f in files if os.path.basename(f) in SERIAL]

    results = []

    def report(result):
        path, code, secs, _ = result
        results.append(result)
        print("%-4s %7.1fs  %s" % ("ok" if code == 0 else "FAIL", secs, rel(path)), flush=True)

    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run_one, f) for f in parallel]):
            report(future.result())
    for f in serial:
        report(run_one(f))
    wall = time.monotonic() - start

    print("\nslowest:")
    for path, _, secs, _ in sorted(results, key=lambda r: -r[2])[:args.slowest]:
        print("  %7.1fs  %s" % (secs, rel(path)))
    failed = sorted((r for r in results if r[1] != 0), key=lambda r: r[0])
    for path, code, _, output in failed:
        print("\n===== FAIL %s (exit %d) =====\n%s" % (rel(path), code, output.rstrip()))
    print("\n%d files, %d failed, %.1fs wall, -j %d" % (len(results), len(failed), wall, args.jobs))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
