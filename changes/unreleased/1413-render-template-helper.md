---
type: added
issue: 1413
pr: 1674
date: 2026-11-11
box-skill: none
---

Template tests now have one shared helper, `render_template` in `dev/tests/crew_testlib.py`, that renders a file through `core/crew-render.py`'s production `render()`: includes are expanded and control, backend and strategy lines are filtered before placeholders are filled. The grok-bot ownership guard test now uses it instead of calling `Renderer.line` on hand-expanded template text. A new render test shows a template with a shared policy include rendering cleanly through the helper. Token-level `Renderer.line` unit tests are unchanged.
