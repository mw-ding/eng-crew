# tmux onboarding

Operator module for onboarding a repo onto a local tmux crew, split out of the
[onboarding runbook](../runbook-new-repo.md) under the M26 modular
organization principle ([#676](https://github.com/mw-ding/eng-crew/issues/676)).
It holds the tmux prerequisites and the target-repo setup. The runbook
keeps the parent
[tmux runtime](../runbook-new-repo.md#tmux-runtime) introduction, with the
runtime choice and the `crew` and `CREW_PROJECT` conventions used here, and
the steps not yet moved:
[Run the crew](../runbook-new-repo.md#run-the-crew) and
[tmux troubleshooting](../runbook-new-repo.md#tmux-troubleshooting).

## tmux prerequisites

- tmux, Python 3.11+, `git`, and `gh` logged in as every login the profile
  names ([Q5](../runtimes/tmux.md#q5-identities)). One identity for every role
  is the default: verdicts are COMMENT reviews and each merge needs an owner
  merge-ok or a standing grant ([single-identity profile](../interfaces.md#single-identity-profile)).
- Claude Code and Codex installed, so the reviewer engine can differ from the
  builder engine ([roles.md](../roles.md#reviewer-engine-selection)).
- **Permission mode.** Role windows launch with
  `runtime.options.permission_mode`, default `bypass`: agents run any command
  in their worktree without asking, with no approval prompt and, for Codex,
  no sandbox ([crew spawn](../runtimes/tmux.md#crew-spawn)). Run the crew only
  on a machine, and with GitHub logins, where you accept that. `auto` and
  `safe` keep the harness's approval checks, but a window then waits on any
  prompt the host does not auto-approve; crew roles never answer one.
- **Codex hook trust on the host.** Every hook in the host's own Codex
  config must be trusted before `crew up`. One untrusted host hook shows
  `Hooks need review` in every Codex window; the crew then escalates to the
  owner and never types into the window ([Troubleshooting](../runbook-new-repo.md#tmux-troubleshooting)).
- An extracted release bundle ([README: Install](../../README.md#install)) or
  an eng-crew checkout at `<eng-crew>`, and a clone of the target repo at
  `<project>`.
- In a nested sandbox (an agent session that is itself sandboxed), the org
  pack's sandbox variable, passed as `CREW_SANDBOX_ENV=<NAME>=<value>` in the
  shell that runs `crew up` ([Troubleshooting](../runbook-new-repo.md#tmux-troubleshooting)).

Next: [Set up the target repo](#set-up-the-target-repo).

## Set up the target repo

1. **Profile.** Write `<project>/crew.toml` from
   [profiles/tmux.toml](../../profiles/tmux.toml) plus `[repo]` and `[paths]`.
   `paths.state_dir`, `paths.worktree_root`, `paths.toolchain_bin` and
   `paths.live_dir` default to placeholders: set each to a real local path.
   `crew` refuses (exit 1) while a path it uses still resolves to a
   `<placeholder>`, including one inherited from the default profile because
   the key is missing (#265), so a stray copy such as the `crew.toml` inside
   a worktree can never put state or the land lock under the worktree.
   Set `paths.eng_crew` to `<state-dir>/<owner>__<repo>/eng-crew` for bootstrap,
   or directly to `<eng-crew>` for the manual fallback, so the briefs cite
   its docs in a repo that has none. Set `runtime.options.merge_grant` (default `none`: a
   merge-ok per PR), `hold_label_blocks` and `permission_mode` (default
   `bypass`) only if the owner chose otherwise
   ([profile.md: Keys](../profile.md#keys)). Preview and apply with
   [bootstrap](../runbook-new-repo.md#bootstrap-recommended). For the [manual fallback](../runbook-new-repo.md#manual-fallback),
   validate and resolve the profile; `crew up` renders in either path.
2. **Labels.** Create the ten `crew:*` labels as in
   [Step 1](../runbook-new-repo.md#step-1-create-the-crew-labels).
3. **CI.** At least one check must run on every PR: review starts on each new
   head whatever its CI, but `sam` lands only when the CI rollup at head is
   green ([CI and review handoff](../runtimes/tmux.md#crew-poll)). Branch protection is
   unavailable on a private Free-plan repo, so the check cannot be made
   required there; the §7 re-check of CI at head is then the only guard
   ([Step 4](../runbook-new-repo.md#step-4-check-ci-and-branch-protection)).

Next: [Run the crew](../runbook-new-repo.md#run-the-crew).
