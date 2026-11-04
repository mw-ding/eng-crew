# Profile install

Onboarding module for installing the crew from a profile with
`crew bootstrap`, split out of the [onboarding runbook](../runbook-new-repo.md)
under the M26 modular organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It is the
recommended path of the runbook's
[Step 0: write, validate and render the profile](../runbook-new-repo.md#step-0-write-validate-and-render-the-profile),
after the [Prerequisites](../runbook-new-repo.md#prerequisites). The
[manual fallback](../runbook-new-repo.md#manual-fallback) and the onboarding
Steps 1–8 stay in the runbook.

## Bootstrap (recommended)

Start with an extracted, checksum-verified release bundle from
[README: Install](../../README.md#install), or a checkout at an exact stable
release tag. Use a release that includes `crew bootstrap`; check
`<eng-crew>/scripts/crew bootstrap --help`. An untagged development checkout
requires `--dev`, records its commit SHA and satisfies no version pin.

Write `<project>/crew.toml` using item 1 of the
[manual fallback](../runbook-new-repo.md#manual-fallback). For tmux, use
[Set up the target repo](../runbook-new-repo.md#set-up-the-target-repo) for the runtime-specific
profile values. Set every path used by the install to a real path; for tmux,
`paths.eng_crew` must be `<state-dir>/<owner>__<repo>/eng-crew`, the link
bootstrap creates to the bundle. Use an absolute project-file path:

```bash
<eng-crew>/scripts/crew bootstrap --project <project>/crew.toml --dry-run
<eng-crew>/scripts/crew bootstrap --project <project>/crew.toml
```

Pass `--org-profile <pack>/profile.toml` to both commands if a pack applies.
Review the render diff, target paths and human steps before confirming apply.
In a non-interactive shell, use `--yes` only after reviewing the dry run.
A failed preflight stops the install; follow its hints, use
`<eng-crew>/scripts/crew doctor --project <project>/crew.toml --fix` for
missing state directories, then retry. Never overwrite a tracked, edited or
unowned target to get past a refusal.

Capture the dry-run and apply output. Expect `crew bootstrap: dry-run; no
install written`, then `crew bootstrap: installed <path-to-install.json>`.
Apply records `VERSION`, `install.json`, a profile copy and the `eng-crew`
link in the shared state directory. Grok Bot receives the deployed render at
`paths.live_dir`; tmux receives a render preview, with deployment and hooks
left to `crew up`. See [bootstrap](../bootstrap.md) for the design and build slices.

Complete Steps 1–5 and the remaining wiring in [Step 6](../runbook-new-repo.md#step-6-state-dir-and-wiring-doc).
The current core does not automate labels, collaborator acceptance, Milestones,
Project setup, protection choices or the end-to-end smoke test. Record every
pending human step from the install manifest. Bootstrap does not start roles:
create Grok Bot routines in [Step 7](../runbook-new-repo.md#step-7-listener-wiring-per-bot), or run
`crew up` for [tmux](../runbook-new-repo.md#run-the-crew), then complete Step 8 and the checklist.
