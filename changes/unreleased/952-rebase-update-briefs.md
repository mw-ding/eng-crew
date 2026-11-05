---
type: added
issue: 952
pr: TBD
date: 2026-11-04
box-skill: deferred to #140
---

A backend that declares `[strategy] update_from_base = "rebase"` now gets
rebase wording and no merge trains (#874 slices B2 and B3). The renderer
reads the resolved strategy: template lines prefixed `<strategy:merge>` or
`<strategy:rebase>` render only under that strategy, the new
`<tested-update>` placeholder fills the synthesizer's
tested-with-default-branch row, and the builder precheck's fresh-base step
says "rebase onto the default branch and upload" for an existing PR. The
tmux builder, solo and synthesizer briefs and the Grok Bot builder and
synthesizer briefs carry the rebase lines. Protocol hard rules, precheck step
1 and verdict portability now read the declared strategy, and `crew train
build` and `crew train bisect` refuse on a rebase backend before creating any
clone, branch or PR. GitHub and every manifest without `[strategy]` stay
`merge`, and their renders are byte-identical.
