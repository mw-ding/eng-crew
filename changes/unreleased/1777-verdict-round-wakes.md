---
type: fixed
issue: 1777
pr: 1803
date: 2026-11-12
box-skill: none
---

Wake the builder or synthesizer once for a new signed verdict round at an unchanged head, using the posted round and coordinator reset epoch independently of the next review round. Duplicate verdict posts retain their canonical review provenance without another wake, and existing poll state seeds the new identity without replaying an unchanged verdict.
