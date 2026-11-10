---
type: fixed
issue: 1541
pr: 1572
date: 2026-11-09
box-skill: none
---

`mdstack upgrade` now runs on a session-runtime profile: it previews and applies the re-render to `paths.live_dir` (and fetches with `--version` or `--latest`) without the tmux in-flight wait or window reload, then says to restart the coordinator with `mdstack up`. `mdstack bootstrap` on a session profile no longer fails its `briefs` self-test, which looked for the Grok Bot brief names instead of the session runtime's tmux-named briefs. tmux upgrades are unchanged.
