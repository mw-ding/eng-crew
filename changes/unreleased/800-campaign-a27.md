---
type: added
issue: 800
pr: 1097
date: 2026-11-06
box-skill: none (internal campaign fixture, sandbox stub and doc; no template or box-skill changes)
---

The M25 campaign gains the A27 scenario spec (intake, milestone close and refusal recovery) in `scripts/fixtures/campaign/` (25.18). It runs on real sandbox tmux at level a. `crew feedback` files one redacted runtime-blocker card per failure class, comments on an open card of the same class, and files nothing when the card list is unreadable. A closed milestone stays queued, and is not taken, while the researchers cap holds its sweep back; it is taken once when that sweep starts. The played milestone-close sweep files `crew:` and `repo:` cards, adds evidence to a matching card and links a matching lesson. A provider safety refusal is parked once as `needs-owner` and never retried, and a worker's refusal status wakes the coordinator once with the window kept. The sandbox `gh` stub now keeps each `--body-file -` body in `bodies.log`.
