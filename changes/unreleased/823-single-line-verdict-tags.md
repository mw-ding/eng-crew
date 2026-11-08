---
type: fixed
issue: 823
pr: TBD
date: 2026-11-08
box-skill: none
---

A passing review no longer leaves `crew:changes` beside `crew:approved`. The GitHub backend wrote the `set-approved` and `set-changes` state-tag commands across two lines, so the rendered reviewer brief split each command. The first line of `set-approved` is a valid command by itself, so a reviewer that ran only that line added `crew:approved` and kept the round-1 `crew:changes`, and the merge gate refused the land until someone removed the tag by hand. Both commands now render on one line, and the reviewer brief says to run the command whole, read the PR's tags back and run it again if `crew:in-review` or the other verdict tag is still set.
