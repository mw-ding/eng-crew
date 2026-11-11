---
type: fixed
issue: 1493
pr: TBD
date: 2026-11-11
box-skill: none
---

The lab `status-pull` scenario's stub role run now reads typed input from fd 0 with `os.read` and splits it into complete newline-delimited lines, as the placed-run host stub does since #1492. Before, `select` on `sys.stdin` followed by a buffered `readline()` left a second inbox line typed in the same write in Python's buffer, so its ack was never written until more input arrived. A partial line is now kept and completes on the next write. Lab test fixture only; no runtime or gate behaviour changes.
