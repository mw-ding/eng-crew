---
type: added
issue: 793
pr: 1115
date: 2026-11-06
box-skill: none (internal campaign fixture and doc; no template or box-skill changes)
---

The M25 campaign gains the A14 (train, overlap and serial land) scenario spec in `scripts/fixtures/campaign/` (25.11). It runs at level a on sandbox tmux, with a fake forge that squashes for real. Two PRs editing one shared file stay in one train, and a third on the same line drops as a conflict. A red train lands nothing, and no successor builds on it. A successor built on its predecessor's tip waits for it, then lands on the final squash. Under one land lock, each member lands in order at its exact tested head, with the train step's tree. A head that moves mid-land is refused at the forge. A default branch that moves mid-land stops the train and rebuilds the successor on the new main. Every draft train PR is closed.
