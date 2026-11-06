---
type: added
issue: 796
pr: TBD
date: 2026-11-06
box-skill: none (internal campaign fixtures and doc; no template or box-skill changes)
---

The M25 campaign gains the A20 (install, doctor, upgrade, rollback and uninstall) scenario spec in `scripts/fixtures/campaign/` (25.14). It runs on real sandbox tmux at level a. It installs from a checksum-verified local bundle with a `mirror` source and an org pack pin. The steps cover doctor's fail, fix, ownership and tool-drift rows. They check that dry-run writes nothing, and that the self-test and install record are complete. They refuse a drifted render, an edited or tracked target, a pin mismatch and a bad checksum, each leaving the install untouched. An upgrade waits for a busy pass, applies from the verified bundle and rolls back to the previous one. Uninstall pauses items and keeps unlanded work, then archives the state and keeps an edited target. A reinstall and an upgrade with a running crew then check that each role reloads, coordinator last.
