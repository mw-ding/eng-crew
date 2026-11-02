---
type: fixed
issue: 572
pr: TBD
date: 2026-11-02
box-skill: none (tmux only)
---

Count only busy builders for admission, reclaim the longest-idle pushed builder with output retained when windows are full, and expire idle builders after a configurable 30 minutes. Stop descendant process groups during cleanup and exclude closed or merged items from lead suite probes, so finished work cannot block new builds.
