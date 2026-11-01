---
type: fixed
issue: 308
pr: 310
date: 2026-10-31
box-skill: none
---

`crew send` nudges no longer pile up unsent in a Codex composer: an
`Enter` sent right behind the typed `inbox: <msg-id>` landed in Codex's
paste burst and added a newline, so each nudge stacked under the last and
none was submitted. The adapter's `send_keys` now waits 0.3 s before
`Enter` (the watcher's `wake: watcher` line too), and `crew send` follows
firstmate's verified-submit pattern: it reads the composer at the cursor,
clears earlier `inbox:` lines with `C-u` when they are all it holds (other
text is never cleared), types the nudge once, retries `Enter` up to 3
times while the nudge is still in the composer, and exits 4 with
`crew: nudge not submitted: ...; treat <window> as ambiguous` if it never
submits. `scripts/test-crew-send.py` adds the composer check on captured
Codex and Claude Code screens and a fake-composer test; `docs/runtimes/tmux.md`
and `scripts/README.md` describe it.
