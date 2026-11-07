---
type: added
issue: 1231
pr: 1275
date: 2026-11-07
box-skill: none
---

Any role can now run in the terminal on demand. A role definition may declare a `lifecycle` table: `policy` (`always-on`, `elastic` for a lead plus elastic workers, or `ephemeral`), `min` and `max` instances, `idle_ttl` in seconds and `wake` triggers (`manual` or tmux event IDs). `crew-roles.py` validates it: a tier-sourced role without `cap_key`, `max` within its window band, the policy's bounds, and a first pass with no inputs. `crew up` starts each lifecycle role's `min` instances after the pool leads. `crew up <role> --project <file>` starts one more instance of a role with the `manual` wake and refuses at `max`. On every scan the watcher kills instances that have had no pane output, no inbox message and no unacknowledged message for `idle_ttl` seconds, down to `min`, so ephemeral roles scale to zero. Event wakes are declared only for now. Roles without a `lifecycle`, all the engineering roles among them, behave as before.
