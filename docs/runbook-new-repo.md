# Runbook: put the crew on a new repo

This runbook takes a repo from "no automation" to "one issue went through every
stage, merged, and closed out, with evidence". It ends with a verification
checklist. Do the steps in order and capture the evidence named in each step;
the [checklist](#verification-checklist) collects it.

The install path starts with `mdstack bootstrap`: write one `crew.toml`, preview
the install, then apply it ([Step 0](#step-0-write-validate-and-render-the-profile)).
The profile ([profile.md](profile.md)) replaces hand-filled placeholders.
The manual validate, resolve, render and state setup remain below as a fallback.
Then complete the GitHub install mechanics (Steps 1 to 4: labels, reviewer collaborator,
milestones and board, CI and protection;
[GitHub backend: Tracking](backends/github.md#tracking)), the product-safety
checks (Step 5), the state dir and routines from the rendered output (Steps 6
and 7), and a first test issue (Step 8).
For a local tmux crew instead of Grok Bot, see [tmux runtime](#tmux-runtime).

Read first: the [architecture overview](architecture.md), the
[stage protocol](protocol.md), and [roles, tiers and engines](roles.md). A
finished onboarding, with real values, is the
[agentconnect worked example](../examples/agentconnect/README.md).
This runbook onboards one repo. It does not change the protocol or the
templates; gaps found along the way go into [Known gaps](#known-gaps).

The `<name>` placeholder values used in every command are defined in
[Prerequisites: Command values](runbooks/prerequisites.md#command-values).

## Prerequisites

Moved to [Prerequisites](runbooks/prerequisites.md#prerequisites).

### Identities

Moved to [Prerequisites: Identities](runbooks/prerequisites.md#identities).

### Per-identity `gh` usage

Moved to
[Prerequisites: Per-identity `gh` usage](runbooks/prerequisites.md#per-identity-gh-usage).

### Token scopes

Moved to [Prerequisites: Token scopes](runbooks/prerequisites.md#token-scopes).

### Shared state dir

Moved to
[Prerequisites: Shared state dir](runbooks/prerequisites.md#shared-state-dir).

### Other prerequisites

Moved to
[Prerequisites: Other prerequisites](runbooks/prerequisites.md#other-prerequisites).

## Step 0: write, validate and render the profile

Both install paths live in [Profile install](runbooks/profile-install.md):

1. [Bootstrap (recommended)](runbooks/profile-install.md#bootstrap-recommended).
2. [Manual fallback](runbooks/profile-install.md#manual-fallback), when
   bootstrap is unavailable.

### Bootstrap (recommended)

Moved to
[Profile install: Bootstrap (recommended)](runbooks/profile-install.md#bootstrap-recommended).

### Manual fallback

Moved to
[Profile install: Manual fallback](runbooks/profile-install.md#manual-fallback).

## Step 1: create the `crew:*` labels

Moved to
[GitHub tracking: Step 1](runbooks/github-tracking.md#step-1-create-the-crew-labels).

## Step 2: add the reviewer as a collaborator

Moved to
[GitHub reviewer access: Step 2](runbooks/github-reviewer-access.md#step-2-add-the-reviewer-as-a-collaborator).

## Step 3: create Milestones and link a GitHub Project (v2)

Moved to
[GitHub tracking: Step 3](runbooks/github-tracking.md#step-3-create-milestones-and-link-a-github-project-v2).

## Step 4: check CI and branch protection

Moved to [GitHub CI and branch protection](runbooks/github-ci-protection.md):

1. [Step 4: CI discovery and current protection](runbooks/github-ci-protection.md#step-4-check-ci-and-branch-protection),
   items 1 to 4.
2. [Protection choice](runbooks/github-ci-protection.md#protection-choice),
   item 5.
3. [Merge settings and enforcement limits](runbooks/github-ci-protection.md#merge-settings-and-enforcement-limits),
   items 6 and 7.

## Step 5: product-safety checks

Moved to [Product preflight](runbooks/product-preflight.md#step-5-product-safety-checks):

1. [Automation, namespace and fork preflight](runbooks/product-preflight.md#automation-namespace-and-fork-preflight),
   items 1 to 3.
2. [Workflow, repo-contract, toolchain and cutover checks](runbooks/product-preflight.md#workflow-repo-contract-toolchain-and-cutover-checks),
   items 4 to 8.

## Step 6: state dir and wiring doc

Moved to
[Grok Bot onboarding: Step 6](runbooks/grok-onboarding.md#step-6-state-dir-and-wiring-doc).

### Filled-in wiring.md (derived from the template)

Moved to
[Grok Bot onboarding: Filled-in wiring.md](runbooks/grok-onboarding.md#filled-in-wiringmd-derived-from-the-template).

## Step 7: listener wiring per bot

Moved to
[Grok Bot onboarding: Step 7](runbooks/grok-onboarding.md#step-7-listener-wiring-per-bot).

### Steering wiring

Moved to
[Grok Bot onboarding: Steering wiring](runbooks/grok-onboarding.md#steering-wiring).

### Cutover for existing open PRs

Moved to
[Grok Bot onboarding: Cutover for existing open PRs](runbooks/grok-onboarding.md#cutover-for-existing-open-prs).

## Step 8: first test issue

Moved to
[Onboarding proof: Step 8](runbooks/onboarding-proof.md#step-8-first-test-issue).

### Template issue

Moved to
[Onboarding proof: Template issue](runbooks/onboarding-proof.md#template-issue).

### Expected event and marker sequence

Moved to
[Onboarding proof: Expected event and marker sequence](runbooks/onboarding-proof.md#expected-event-and-marker-sequence).

### Optional steering smoke test

Moved to
[Onboarding proof: Optional steering smoke test](runbooks/onboarding-proof.md#optional-steering-smoke-test).

## Verification checklist

Moved to
[Onboarding proof: Verification checklist](runbooks/onboarding-proof.md#verification-checklist).

### Evidence timeline

Moved to
[Onboarding proof: Evidence timeline](runbooks/onboarding-proof.md#evidence-timeline).

## tmux runtime

This section is now navigation: each heading below keeps its anchor and
links to its module. The current steps are in the
[tmux onboarding module](runbooks/tmux-onboarding.md), with the `mdstack` and
`CREW_PROJECT` conventions in its
[Command conventions](runbooks/tmux-onboarding.md#command-conventions); the
dated 2026-10-30 run is in the
[tmux onboarding history](runbooks/tmux-onboarding-history.md).

### tmux prerequisites

Moved to
[tmux onboarding: tmux prerequisites](runbooks/tmux-onboarding.md#tmux-prerequisites).

### Set up the target repo

Moved to
[tmux onboarding: Set up the target repo](runbooks/tmux-onboarding.md#set-up-the-target-repo).

### Run the crew

Moved to [tmux onboarding: Run the crew](runbooks/tmux-onboarding.md#run-the-crew).

### tmux troubleshooting

Moved to
[tmux onboarding: tmux troubleshooting](runbooks/tmux-onboarding.md#tmux-troubleshooting).

### End-to-end run (2026-10-30)

Moved to
[tmux onboarding history: End-to-end run (2026-10-30)](runbooks/tmux-onboarding-history.md#end-to-end-run-2026-10-30)
(history, not current instructions).

## Rollback and offboarding

Moved to
[Offboarding: Rollback and offboarding](runbooks/offboarding.md#rollback-and-offboarding).

## Known gaps

Moved to [Onboarding proof: Known gaps](runbooks/onboarding-proof.md#known-gaps).
