---
type: fixed
issue: 1616
pr: 1626
date: 2026-11-10
box-skill: none
---

`mdstack upgrade` now adopts a running user-level install that has no `install.json`, such as one set up by `mdstack install`, `layout --write` and `up`. It first checks the `paths.mdstack` link, the release `VERSION` beside a `releases/current` link and the state's `config.toml` copy, then writes the record and upgrades. Before this, it refused with "run mdstack bootstrap first", and bootstrap then refused the same install. An install that does not verify is refused, and the refusal names the mismatch. `mdstack doctor --fix` now resets a `crew:*` runbook label's color and description instead of failing the labels check when no install record owns it. Only an extra `crew:*` name still collides.
