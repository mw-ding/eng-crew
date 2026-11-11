# Spec template

Seed for a spec in a project's `docs/specs/`, the home of its source of
truth in the [essential doc set](../docs/project-doc-set.md#essential-doc-set).
Copy the block below to `docs/specs/<topic>.md`, replace every placeholder,
and delete these instructions. Keep requirement IDs stable: never renumber or
reuse one; mark a dropped requirement `withdrawn` and keep its row. No
secrets, tokens, personal data or box paths.

````markdown
# Spec: <title>

> - **Status:** design | partly built | built | superseded
> - **Applies to:** <scope>
> - **Current rules:** <links to the docs that own the live rules>
> - **Built:** <issues or PRs, or "nothing">
> - **Last checked:** <YYYY-MM-DD> at `<sha7>`

## Goal

<What this spec makes true, for whom, and why now. Two to four sentences.
Link the decision that started it in `docs/decisions.md`.>

## Non-goals

- <What this spec deliberately leaves out, with the issue that tracks it if
  any.>

## Requirements

### REQ-<AREA>-1: <short name>

- **Applies when:** <the condition or scope under which it holds>
- **Obligation:** <what must, must not or may happen, one statement>
- **Acceptance criteria:**
  1. <an observable outcome a reviewer can check>
- **Verification:** <the test, check or evidence shape that proves it>

## Target environment (verified on <YYYY-MM-DD>)

<Platform or device specs only; otherwise write "N/A: <reason>". Each fact
was observed, not recalled, and names the command that showed it. An
unknown or incompatible fact blocks `crew:ready`.>

- **Host:** <model, OS version, architecture> (`<command>`)
- **Toolchain:** <tool and version available on the host> (`<command>`)
- **Target device:** <model and OS version> (`<command>`)

## Owner prerequisites

<Every step only the owner can do (accounts, admin password, device trust,
developer mode, signing team, media capture), asked for in one batch before
the build. Write "None" if there are none.>

- [ ] <step> — owner: <who> — by: <YYYY-MM-DD>

## Design

<Components, boundaries and data flow that meet the requirements. Cite other
specs and docs by link instead of restating them.>

## Open questions

- <A question still open, who decides it, and the issue it lives on.>

## Changes

| Date | Version | Change | Issue or PR |
|---|---|---|---|
| <YYYY-MM-DD> | v0.1 | First draft | <#n> |
````
