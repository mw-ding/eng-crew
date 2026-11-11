---
type: fixed
issue: 1536
pr: 1658
date: 2026-11-10
box-skill: none
---

A missing expected CI check no longer reads as green. The new optional `[ci] required_checks` profile list names the checks that must each be present at head: `mdstack poll`, `ready_sample`, the gate-status CI item (which now names the missing checks) and `mdstack train` build and wait keep CI pending while one is absent (a train times out rather than passing), even when every observed check passed. Failed and infrastructure-failed checks still read as failed or infra, unlisted checks such as `lab` stay optional, and a profile without the table keeps today's behaviour.
