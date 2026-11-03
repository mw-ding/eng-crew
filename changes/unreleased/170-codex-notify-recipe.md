---
type: fixed
issue: 170
pr: 605
date: 2026-11-02
box-skill: none
---

Verify the Codex coordinator wake path on codex-cli 0.164.0 and fix its turn-end notify recipe: the recipe now pipes Codex's turn payload to `crew guard`, types the wake line with a 0.3 s settle before Enter (a single send-keys left it unsent in the composer), and `crew guard` treats a turn started by its own wake line as already continuing, so it blocks once per stop cycle instead of looping every few seconds. `crew up` still does not install the recipe.
