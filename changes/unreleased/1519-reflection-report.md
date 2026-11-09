---
type: added
issue: 1519
pr: 1529
date: 2026-11-09
box-skill: none
---

The researcher gains a `protocol-reflection` procedure (`templates/policy/researcher/skills/protocol-reflection/SKILL.md`) for #1403's reflection loop: it reads `reflection-scan.py`'s evidence index and the sources it cites as data, searches existing work and owner decisions first, applies the rejection cooldown and the 3-new-proposal cap inside triage's noise cap, and posts one signed report on the `reflection:log` issue with stable-ID proposals (exact targets, correction layer, incident count, measured impact or `unknown`, rank reason, recommended default), a top-three digest and gaps. It rechecks ownership and the `pass=reflection` completion marker before posting, and a signed coordinator request runs it by hand before any schedule exists. The tmux researcher brief points to it, and a sample report fixture for the scan test's window is checked against the index.
