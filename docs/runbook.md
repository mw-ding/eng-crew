# Runbook

eng-crew's runbook entry point in the
[essential doc set](project-doc-set.md#essential-doc-set)
([#1219](https://github.com/mw-ding/eng-crew/issues/1219)): how to install,
run, release, operate and recover a crew. Navigation only. Each link goes to
the doc that owns those steps, and this page adds no rule, step or default of
its own.

## Install and onboard

| Task | Owner doc |
|---|---|
| Put the crew on a new repo, end to end | [runbook-new-repo.md](runbook-new-repo.md) |
| Check prerequisites and identities first | [runbooks/prerequisites.md](runbooks/prerequisites.md) |
| Install from a profile with `mdstack bootstrap` | [runbooks/profile-install.md](runbooks/profile-install.md) |
| Onboard a local tmux crew | [runbooks/tmux-onboarding.md](runbooks/tmux-onboarding.md) |
| Onboard a Grok Bot crew | [runbooks/grok-onboarding.md](runbooks/grok-onboarding.md) |
| Preflight checks with `mdstack doctor` | [bootstrap.md, Q5](bootstrap.md#q5-preflight-checks) |

## Run and operate

| Task | Owner doc |
|---|---|
| Start, watch and stop a tmux crew | [runbooks/tmux-onboarding.md, Run the crew](runbooks/tmux-onboarding.md#run-the-crew) |
| Every `mdstack` command | [runtimes/tmux.md, Usage](runtimes/tmux.md#usage) |
| Land changes and run merge trains | [runtimes/tmux.md, mdstack train](runtimes/tmux.md#mdstack-train) |
| Steer the crew (`/crew` commands) | [protocol.md §9](protocol.md#9-steering-crew-commands) |

## Release and upgrade

| Task | Owner doc |
|---|---|
| Cut and publish a release | [release.md, Steps](release.md#steps) |
| Upgrade an install to a new release | [release.md, Update path](release.md#update-path) and [bootstrap.md, Q8](bootstrap.md#q8-idempotency-upgrade-and-uninstall) |

## Recover

| Task | Owner doc |
|---|---|
| Fix a tmux crew that misbehaves | [runbooks/tmux-onboarding.md, tmux troubleshooting](runbooks/tmux-onboarding.md#tmux-troubleshooting) |
| Recover duplicate or lost runs | [runtimes/tmux.md, Deduplication and recovery](runtimes/tmux.md#deduplication-and-recovery) |
| Roll back a release | [release.md, Rollback](release.md#rollback) |
| Take the crew off a repo | [runbooks/offboarding.md](runbooks/offboarding.md) |
