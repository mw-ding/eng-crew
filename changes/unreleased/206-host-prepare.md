---
type: added
issue: 206
pr: TBD
date: 2026-11-03
box-skill: none (tmux CLI and host entrypoint only; no template changes)
---

`crew host prepare <host>` sets a project up on an inventory host and then runs `crew host check`. On a role host the hardened `prepare` call creates the project mirror under `mirrors/<owner>__<repo>.git` with the host's own `gh` login, or fetches it, and makes the `wt/` and `state/<owner>__<repo>/` directories. On a forge-less host the primary fetches its checkout and seeds the mirror with a full bundle of the default branch through the new `seed` verb, so the host never reaches the forge. On the primary it fetches the project checkout. A failed step prints `fail prepare <step>` and leaves the host not ready.
