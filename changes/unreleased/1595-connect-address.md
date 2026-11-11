---
type: fixed
issue: 1595
pr: TBD
date: 2026-11-11
box-skill: none
---

`mdstack connect` now uses the inventory host's `address` (#1034) as the `ssh`, `mosh` or `et` destination when set, falling back to the host label as `host check` and `host prepare` already do, so a host whose label does not resolve no longer needs an SSH config alias. Hosts without `address` keep today's argv, and `connect.alias` stays a lookup name only.
