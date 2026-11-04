# Backend interfaces

The minimum operations a backend must support for each concern, the guarantee
each operation gives, and the invariant it protects (portable eng-crew, roadmap
13.9, [#121](https://github.com/mw-ding/eng-crew/issues/121)). Terms are in
[concepts.md](concepts.md). Invariants are numbered as in
[portable spec §3](specs/portable.md#3-invariants): I1 author ≠ reviewer, I2
reviewer engine ≠ writing engine, I3 evidence on the change record, validated at head, I4 only the
synthesizer lands, I5 the tool of record holds the audit trail. R is the
release gate ([release](#release)).

This page adds no rule, gate, cap, marker field or label. The
[protocol](protocol.md) owns them; the merge gates are in
[§7](protocol.md#7-merge-gate-synthesizer) and the
[gate registry](protocol.md#gate-registry). Today's GitHub commands for every
operation are in [GitHub backend: Interface mapping](backends/github.md#interface-mapping).
The runtime side (wake, one consumer, liveness, serial land) is the
[runtime contract](runtimes/README.md).

## Concerns

### change

| Operation | Guarantee | Protects |
|---|---|---|
| Open, linked to an item | The new change names its tracker item; landing closes it unless it is an umbrella | I5 |
| Push | Adds commits to the change branch; never rewrites shared history | I3 |
| Read head | Returns the full 40-character head revision | I3 |
| Read diff paths | Lists the paths changed at head, for path-derived gates | I3 |
| Update from base | Merges the base into the change (never a rebase), making a new head | I3 |
| Land (squash, head-pinned) | One squash commit on the default branch; refused if the head moved from the given revision | I3, I4 |
| Close | Ends the change without landing; the record stays readable | I5 |
| List open (`list-open`) | Lists the open changes with their branches and linked items, so a build adopts an existing change | none |
| Read state (`read-state`) | Returns a change's state, head branch, head repository, cross-repository flag and base branch | none |
| Read default branch (`read-default-branch`) | Returns the repository's default branch | none |
| Delete branch (`delete-branch`) | Deletes a landed change's head branch | none |
| CLI conventions (`cli-name`, `cli-repo-flag`, `cli-unscoped`) | Brief text: the backend's command-line tool, its per-repository scope flag and the call that takes no scope flag | none |

### review

| Operation | Guarantee | Protects |
|---|---|---|
| Post verdict (pass / changes) pinned to head | Bound to one head; posted by an identity other than the change author; the body holds the markers | I1, I2, I3 |
| Post narrative | Non-binding; never counts as a verdict; wakes no work role | I5 |
| List verdicts | Every verdict with its author identity, head, state, body and order | I1, I3, I4 |
| Request re-review | Wakes the reviewer for a fresh verdict at the current head | I2, I3 |

### tracker

| Operation | Guarantee | Protects |
|---|---|---|
| Create item | Durable item with goal and acceptance criteria | I5 |
| Assign | Records who builds the item; the runtime may wake on it | I5 |
| Link change ↔ item | Readable from both sides | I5 |
| Milestone | Set and read an item's milestone; a closed milestone takes no new items | I5 |
| Board status | Set and read Todo / In Progress / In Review / Done | I5 |
| List items (`list-items`) | Lists open and closed items with title, body, labels, milestone and comments, for a [triage](triage.md) lookup | I5 |
| Label (`label`) | Sets, clears and reads a non-state label on an item (the triage and priority labels of [protocol §4](protocol.md#4-marker-conventions)) | I5 |
| Comment (`comment`) | Appends a signed post with its marker line to any item (a triage record, a log entry, an extracted card); never edited | I5 |
| Close item (`close-item`) | Closes an item with a reason; it stays readable | I5 |

### state tags

| Operation | Guarantee | Protects |
|---|---|---|
| Set / clear / read | Durable on an item or change; setting or clearing wakes no role (or the runtime ignores the tag event) | I4, I5 |
| Set approved / set changes (`set-approved`, `set-changes`) | The reviewer's state-tag change right after its verdict: one tag set, the other review tags cleared | none |

I4 because the land reads hold and escalation tags.

### markers

| Operation | Guarantee | Protects |
|---|---|---|
| Write | A signed header plus the `crew:v1` line inside a post on the change, carrying the full head SHA ([protocol §4](protocol.md#4-marker-conventions)); append-only, never edited or deleted | I1, I3, I5 |
| Read | Every marker on the change in post order, with the posting identity | I1, I3, I5 |
| Write item (`write-item`) | Append-only coordinator ownership post on the control item | I4, I5 |
| Read item (`read-item`) | All control-item markers in backend post order with posting identity | I4, I5 |
| Edit status (`edit-status`) | Updates the synthesizer's diagnostic `pass=gate-status` post in place; the only edited marker post, never a verdict or permission | none |

The signed marker is the role identity when several roles share an account.
Item-level ownership markers use the same append-only guarantees on the
repo control item, read in post order with the posting identity
([ownership record](protocol.md#ownership-record)); change markers keep
using the existing `write` and `read` operations.

### CI

| Operation | Guarantee | Protects |
|---|---|---|
| Required-check status at head | Pass / fail / pending of every required check for that exact head, never an older one | I3 |
| Failing job names | Names and log links of the failing jobs at head | I3 |

### events

| Operation | Guarantee | Protects |
|---|---|---|
| Subscribe or poll | Delivers the state-transition events of [protocol §8](protocol.md#8-safety) and the steering comment events, each naming the item or change, the head and the actor | I1, I4 |

The actor lets steering accept commands only from the owner's accounts
([§9](protocol.md#9-steering-crew-commands)). One consumer per event and
re-delivery are runtime duties ([C1, C2](runtimes/README.md#contract)).

### owner channel

| Operation | Guarantee | Protects |
|---|---|---|
| Ask with default and deadline | Reaches the owner with a recommended default and auto-apply time; the ask and the answer are recorded on the tool of record | I5 |
| Notify | One-way message to the owner, also recorded | I5 |

### release

Optional: a backend may leave the whole concern undeclared, and only a
profile with a [`[release]` table](profile.md#release) needs it
([release operations](release.md#release-operations),
[#585](https://github.com/mw-ding/eng-crew/issues/585)). R is the
[release gate](protocol.md#gate-registry): no release is published without
the owner's per-change merge-ok at the landed cut's head.

| Operation | Guarantee | Protects |
|---|---|---|
| Cut | Produces the cut change (the CHANGELOG version section plus the consumed fragments) as a normal change for review and the [§7 merge gate](protocol.md#7-merge-gate-synthesizer); never writes the default branch directly | I4, R |
| Approve check | After the cut lands and before any release id is written, verifies the owner's per-change merge-ok at the landed cut change's head, release validation green and required CI green at the landed revision; refuses otherwise | R |
| Record release | Writes the release id once, on the landed cut revision: a tag, or the full 40-character commit hash ([`release_id`](profile.md#release)); never moves or rewrites it | R, I5 |
| Notify | Posts the release link or id on the release item and closes it | I5 |

## Capability declaration

A backend declares every operation above, one line each:

```text
<concern>.<operation>: supported
<concern>.<operation>: emulated (<how>)
<concern>.<operation>: unsupported
```

Rules:

- An operation not declared counts as `unsupported`.
- `emulated` names the mechanism and must give the same guarantee. An
  emulation that weakens the guarantee is `unsupported`.
- **Unsupported-invariant rule.** If an `unsupported` operation leaves an
  invariant it protects with no other operation in the profile that keeps
  it, the profile is **unsupported**. It is never silently weakened (portable
  spec §3). The only documented substitute is the single-identity rule below.
- **Release rule.** A profile with a `[release]` table must keep
  `release.approve-check` and `release.record-release`; if either is
  `unsupported` or undeclared, `resolve` fails closed: the profile is
  unsupported for release. Without the table the concern is not checked.
- A declaration changes no protocol rule. The profile file that carries it is
  13.10 ([#122](https://github.com/mw-ding/eng-crew/issues/122)).

## Single-identity profile

One account acts for every role (the roadmap setup decided in
[#111](https://github.com/mw-ding/eng-crew/issues/111),
[portable spec §6](specs/portable.md#6-decisions)).

- **What breaks: I1.** Author and reviewer are the same account, so
  `review.post verdict` cannot hold literally. A backend that refuses formal
  verdicts from the change author (GitHub does) cannot post one at all, and
  `review.list verdicts` cannot tell the parties apart by account.
- **Allowed compensation.** `review.post verdict` is declared
  `emulated (COMMENT-review verdict + recorded owner merge-ok)`:
  - the verdict is a narrative post headed `[<ReviewerBot>/verdict] round <k> @ <sha7>`,
    with review and validate markers and a final `pass=verdict` marker; the
    signed marker, not the account, identifies the reviewer;
  - the owner OKs each change, and the coordinator records it on the change as
    a `steer` post with `pass=steer cmd=merge-ok cmd-id=chat` at head, or an
    owner standing merge grant covers it (see Scope);
  - the synthesizer re-checks every §7 gate and lands head-pinned.
- **What still holds.** This replaces only the formal-approval gate in the
  [gate registry](protocol.md#gate-registry). Every other gate is unchanged; CI
  is never waived. I2 still holds through the engine in the markers and commit
  trailers. I4 stays a convention backed by the synthesizer's `merge` marker,
  as in [§7](protocol.md#7-merge-gate-synthesizer).
- **Events.** No verdict event fires, so the runtime wakes on its own
  re-check rather than on a verdict event.
- **Scope.** Merge permission comes from a recorded owner merge-ok per
  change, or from an owner standing merge grant recorded on the tracker for
  changes in its scope (for #110 roadmap changes, the grant on
  [#111](https://github.com/mw-ding/eng-crew/issues/111), with its listed
  exclusions). A grant gives permission only, never the approval
  ([§7](protocol.md#7-merge-gate-synthesizer)). Without either, the
  compensation is absent and the profile is unsupported. Today it applies to
  #110 roadmap changes only.
