---
type: fixed
issue: 1682
pr: TBD
date: 2026-11-12
box-skill: none
---

A builder's published merge-up note now starts the delta re-review it asks for. Merge-up delta detection in `mdstack route` accepted only `[<Builder>/fix]` or `[<Builder>/ci-fix]` notes with a `pass=fix` or `pass=ci-fix` marker and "resolved ... conflict" wording, so the signed, head-pinned `[Ben/merge-up]` note on #1656 ("two text conflicts and one semantic conflict, and all three are resolved") sent its conflict-resolved merge-up to the synthesizer and the reviewer lead got nothing until a manual handoff. Detection now also accepts the `[<Builder>/merge-up]` header with a `pass=merge-up` marker and "conflicts ... resolved" wording; the round carries from the approved head, and a replayed event starts no second review. Clean merge-ups, moved heads, unsigned or foreign notes, holds and express keep their current handling, and no marker or gate changes.
