# Worked example: the agentconnect pilot

> **This is a worked example, not a template.** It records how the crew was
> wired on one real repo, `mw-ding/agentconnect`, in a pilot that ran from
> Oct 18, 2026. Values here are specific to that repo. To wire a new repo, use
> the placeholder files in [../../templates/](../../templates/README.md).

The files were sanitized: no tokens or credentials, no chat transcripts, no
account identifiers beyond public GitHub logins, no routine or automation IDs.
Dates are kept so the example reads as a timeline.

| File | Contents |
|---|---|
| [wiring-summary.md](wiring-summary.md) | Identities, enforcement, state flow, steering, pilot findings |
| [routines.md](routines.md) | The routine list with the actual trigger JSON |
| [engine-steer.md](engine-steer.md) | The reviewer engine choice as of Oct 19, 2026 |

Mapping to the templates: Ash is `<CoordinatorBot>`, Ben `<BuilderBot>`, Vera
`<ReviewerBot>`, Sam `<SynthesizerBot>`; `mw-ding` is `<author-login>`, `md-mt`
is `<reviewer-login>`, and the user allowlist is both logins. The repo's default
branch is `main`, and the shared state directory held `claims/` and
`locks/merge.lock`.
