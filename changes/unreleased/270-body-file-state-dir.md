---
type: fixed
issue: 270
pr: 356
date: 2026-11-01
box-skill: deferred to #140
---

The tmux role briefs now say where a `gh` `--body-file` scratch file goes
(#270, from the #139 final live run L1; part of #110). Builder, reviewer and
synthesizer write it to `$CREW_STATE/runs/$CREW_ID.body.md`, which `crew kill`
and `crew down` delete with the run's other `runs/<window>.*` files; before,
roles wrote bodies to `/tmp` and to the parent of the state dir, where they
outlived the run. The coordinator, whose window is never killed, writes
`runs/coordinator.body.md` and deletes it after the post. The brief lint in
`test-tmux-briefs.py` fails a brief that uses `--body-file` without that
location or names a `/tmp` scratch file, and `test-crew-kill.py` pins that kill
removes `runs/<window>.body.md`. `templates/backends/github.toml` is unchanged,
and the Grok Bot runtime templates do not use it, so their rendered text is
unchanged.
