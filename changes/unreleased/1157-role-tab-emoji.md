---
type: added
issue: 1157
pr: 1341
date: 2026-11-07
box-skill: none
---

Each role's tab now shows its configured `[identities]` emoji beside its name, display-only: on tmux through a per-window `@crew_icon` option prefixed to the window status formats of crew windows only (never `-g`), and on herdr as an emoji-and-space label prefix (`<emoji> <label>`) that every lookup strips. Window names and labels stay the targeting identity. A variation selector (`U+FE0F`, as in the default builder 🛠️) is dropped, and an empty or multi-codepoint emoji (a ZWJ sequence) shows the name only, so the tmux status bar keeps its width. Session adapters gain an optional `icon` capability.
