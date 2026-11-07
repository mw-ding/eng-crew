"""A12 validator reproduction (docs/verification.md Q2): repro.py CAPTURE DIR.

Refuses a capture whose header SHA is not DIR's HEAD (stale capture or changed head), then runs the capture's `sh`
block in DIR and compares exit, stdout and stderr with its `text` block, ignoring `# scrubbed:` / `# volatile:` notes.
Prints `agrees` (exit 0), or `stale: ...` / `disagrees` with a diff (exit 1).
"""
import difflib
import os
import re
import subprocess
import sys

capture, cwd = open(sys.argv[1]).read(), sys.argv[2]
sha = re.search(r"· sha `([^`]*)`", capture).group(1)
head = subprocess.run(["git", "-C", cwd, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
if sha != head:
    print("stale: capture %s, head %s" % (sha, head))
    sys.exit(1)
script = re.search(r"^(`{3,})sh\n(.*?)^\1$", capture, re.S | re.M).group(2)
want = re.search(r"^(`{3,})text\n(.*?)^\1$", capture, re.S | re.M).group(2)
run = subprocess.run(["sh", "-c", script], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL)
section = lambda t: t if not t or t.endswith("\n") else t + "\n"
got = "exit: %d\n--- stdout\n%s--- stderr\n%s" % (run.returncode, section(run.stdout), section(run.stderr))
for path in sorted({os.path.abspath(cwd), os.path.realpath(cwd)}, key=len, reverse=True):
    got = got.replace(path, "<cwd>")
want = "".join(line for line in want.splitlines(True) if not line.startswith(("# scrubbed:", "# volatile:")))
if got != want:
    sys.exit("disagrees\n" + "".join(difflib.unified_diff(want.splitlines(True), got.splitlines(True), "capture", "head")))
print("agrees")
