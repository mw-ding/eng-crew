# Coordinator-session brief: <owner>/<repo> (session)

Paste-ready brief for a hand-started coordinator session (Claude Code or
Codex) that has no runtime binding yet ([session binding](../../../docs/runtimes/session.md),
design only). It carries the ownership guard and the handoff steps of
`<eng-crew>/docs/handoff.md` until that binding exists. Fill in every
placeholder before starting. This brief adds no rule, gate, cap or label.

This session's runtime id is `session@` plus the profile's `runtime.instance`. Set `CREW_PROJECT`
to the installed project's absolute profile path, with `repo.control_item`
and `runtime.instance` set.

## Guard

Run `<eng-crew>/scripts/crew ownership --project "$CREW_PROJECT" --runtime session`
at each owner turn and worker completion, and again before each dispatch.
Add `--action write` before each push, post or label, and `--action land`
before dispatching the synthesizer to land. Exit 1 means read-only: dispatch
nothing, report the owning runtime to the owner and post only this session's handoff-side state (protocol §4). An unreadable
record is read-only for this turn; retry on the next. No merge-ok or standing
grant overrides the guard. With a control item and no marker, post `claimed`
(`from=none`, `to=` this session's runtime id) per §4, then re-read before
dispatching.

Every handoff post uses the signed header and hidden line of
`<eng-crew>/docs/protocol.md` §4 [Ownership record](../../../docs/protocol.md#ownership-record),
with the full default-branch head as `sha=`. Re-read the record before each
post; never post a state that is already there for this handoff id.

## Quota

While this session owns the repo, check its own engine's meter at each owner
turn. Under a [quota routing](../../../docs/roles.md#quota-routing) skip
threshold, suggest a handoff once per meter window per
`<eng-crew>/docs/roles.md`, Quota handoff suggestion. Never start one
without the owner's `/crew handoff to` command.

## Outgoing: `/crew handoff to <runtime-id> [drain | stop] [deadline N]` (N minutes)

1. Post `draining` with the owner's command (`cmd-id=chat`), mode and
   deadline (default 30 minutes).
2. `drain`: dispatch nothing new, lands included; let each subagent or CLI
   worker finish its round and post its note or verdict. At the deadline,
   or for `stop`: end every worker now, keep worktrees with unlanded work,
   and let a land past its final gate re-check finish. Release this
   session's claims.
3. Build the manifest from live state and the run records, per
   [Manifest template](../../../docs/handoff.md#manifest-template)
   (references only; no diff, log, token or real path). For a runtime whose
   guard predates #210, add `crew:hold` to each open crew item without one
   and list exactly those in `holds_added`. Post it with `offered`. From here
   this session is read-only.
4. Wait for the ack on each owner turn. With none after two awake hours,
   remind the owner how to start the incoming runtime. Re-post the same
   `offered` only if it is missing on re-read.
5. On `acked`: dispatch nothing more, end any remaining workers, post
   `stopped`, and tell the owner this session may close.

`/crew handoff abort` before the ack: post `aborted`; this session owns again.

## Incoming: an `offered` to this session, or `/crew takeover from <runtime-id>`

1. `crew doctor --project "$CREW_PROJECT"`; it passes with
   `runtime.instance` set.
2. Find the open handoff whose `to` is this session's runtime id, in state
   `offered`. On a takeover command, post `takeover` instead, reusing the
   open handoff's id, `from` and `to` when one is open.
3. Reconcile each manifest set against live state, reading only, per the
   [reconcile table](../../../docs/handoff.md#resume-and-reconcile): live
   state wins; a pass marker posted after `offered` or `takeover` satisfies
   nothing and is re-run at head; a diverged set is only planned as held.
4. Compare the manifest's `rules` with this profile's resolved values. Any
   difference is an owner ask before the ack; never adopt or drop a rule
   silently.
5. Re-read the record. If an `acked` with this id exists, stop; otherwise
   post `acked`, naming any missed open crew item, and retry until posted.
   Before any dispatch, hold each diverged set (`crew:hold` with a note)
   and ask the owner.
6. Lift `crew:hold` from the `holds_added` items only after the outgoing
   side posts `stopped`, the owner confirms its wake sources are gone, or
   its `eng_crew_version` includes #210.
7. Continue with the protocol §6 sweep. Owner-ask deadlines carry over
   unchanged; rounds keep counting. Take new claims; never trust a foreign
   claim file.
