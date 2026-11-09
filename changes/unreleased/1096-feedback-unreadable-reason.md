---
type: fixed
issue: 1096
pr: TBD
date: 2026-11-08
box-skill: none
---

`mdstack feedback` now says why it could not list the open intake cards when `gh issue list` exits 0 with an answer that is not JSON, such as a proxy's `HTTP 502: Bad Gateway` page. Before, the refusal ended in `gh`'s empty stderr, so the line gave no reason. Now it prints `unreadable answer:` and the answer's first line, redacted and cut at 120 characters (`empty` for no output). A non-zero `gh` exit still prints `gh`'s stderr, and nothing is filed in either case.
