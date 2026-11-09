---
type: fixed
issue: 1054
pr: 1508
date: 2026-11-09
box-skill: none
---

`crew-render.py` now fails when a `runtime.options.notes.render.<role>` entry names a role the selected runtime renders no brief for (for example `builder-lead` or `researcher` under `session`), naming the key and the runtime, instead of dropping the note silently. Notes for rendered roles behave as before.
