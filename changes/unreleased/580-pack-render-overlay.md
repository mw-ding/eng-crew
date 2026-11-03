---
type: added
issue: 580
pr: TBD
date: 2026-11-03
box-skill: none
---

Packs can extend the rendered briefs without copying `templates/`. A pack's `render/` directory overlays the render inputs per file (`crew-render.py`, `crew bootstrap`, `crew up`, `crew upgrade` and `check-skill-drift.py`). Every `gh` call in the tmux briefs now goes through a backend operation, with new `change`, `state-tags` and `markers` operations; the GitHub render is byte-identical. A backend map can declare extra run-time placeholders with `[placeholders] kept`. `runtime.options.notes.render` appends notes for any role, leads included, at render time, where `size_budget` and the drift check see them.
