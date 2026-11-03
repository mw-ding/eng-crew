# Solo session brief: <owner>/<repo> (tmux)

Flavor: <flavor-name>; review=<flavor-review>; validation=<flavor-validation>; evidence=<flavor-evidence>; caps=<flavor-caps>; merge=<flavor-merge>; builder=<flavor-builder>.
One owner-driven session builds and fixes this item. Fill in the issue number,
worktree, acceptance criteria and actual engine/model/effort before starting.
Read the live issue and PR, the repo's `AGENTS.md`, and
`<eng-crew>/docs/protocol.md`. Adopt any open PR closing the issue.

Mark the issue and PR `crew:solo`. This skips builder dispatch, B2 watches,
merge-up and fix delivery to builder windows. Findings and red CI are posted
on the PR for this session to pick up. No builder claim or inbox is required.
The reviewer uses a different engine from this session; the synthesizer alone
squashes under §7. Keep the floor F1–F7, holds, CI, inline mutation evidence
and the existing merge permission rules.

Before work and each push or post, run
`<eng-crew>/scripts/crew ownership --project "$CREW_PROJECT"` (add `--action write`
for pushes and posts). Set `CREW_PROJECT` to the installed project's absolute profile path.
On refusal, read/report only. Pin `PATH` with `<toolchain-bin>` and work only
in the supplied worktree on `builder/<n>-` plus a short slug.
Add `-R <owner>/<repo>` to every `gh` command except `gh api`.
Use local `.crew/` files for drafts and logs. Run the repo's CI checks before
pushing; never download tools, bypass quarantine or use a mirror registry.
Report unavailable checks in PR evidence and leave those checks to CI.

Open a non-draft PR with the contract below and label it `crew:in-review`.
Handle findings, red CI and merge conflicts in this same session. Use a merge
commit for updates from `<default-branch>`; never force-push a shared branch.
After each fix, post its head-pinned fix note. Never merge or self-approve.

<include:docs/roles.md#pr-conventions>
