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
| Read diff (`read-diff`) | Returns the unified diff at head against its merge base, without rename folding, for a role with no checkout to run [content rules](profile.md#content-rules-879) on | I3 |
| Update from base | Merges the base into the change (never a rebase), making a new head | I3 |
| Land (squash, head-pinned) | One squash commit on the default branch; refused if the head moved from the given revision | I3, I4 |
| Close | Ends the change without landing; the record stays readable | I5 |
| List open (`list-open`) | Lists the open changes with their branches and linked items, so a build adopts an existing change | none |
| Read state (`read-state`) | Returns a change's state, head branch, head repository, cross-repository flag and base branch | none |
| Read default branch (`read-default-branch`) | Returns the repository's default branch | none |
| Delete branch (`delete-branch`) | Deletes a landed change's head branch | none |
| CLI conventions (`cli-name`, `cli-repo-flag`, `cli-unscoped`) | Brief text: the backend's command-line tool, its per-repository scope flag and the call that takes no scope flag | none |

`read-diff` is conditional (#879): `resolve` requires it only when the
resolved profile declares content rules; a manifest without it stays valid
otherwise.

Designed, not active: a backend whose VCS forbids merge commits would
declare a rebase update, with every earlier head kept readable in place of
the no-rewrite guarantee
([rebase update from base](#rebase-update-from-base-design), #874).

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
| List items (`list-items`) | Lists open and closed items with title, body, labels, milestone, state, close reason, creation time and comments, for a [triage](triage.md) lookup | I5 |
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
A backend-neutral `read-item` output, the `write-item` retry rule and the
`<control-item>` placeholder for a tracker-native control item id are
proposed in [handoff](handoff.md#tracker-native-control-item) (#875);
they apply once its build issues land.

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
- **Release pairing.** With an external pack, `[release]` and a pack-bound
  `[backends.release]` bind together
  ([#910](https://github.com/mw-ding/eng-crew/issues/910)). `resolve`
  fails closed on a `[release]` table whose `[backends.release]` still comes
  from the bundled default while the pack's manifest declares release
  capabilities, and on a `[backends.release]` that a layer above the
  default binds to the pack with no `[release]` table. The error names the missing half and the file it
  belongs in. There is no opt-out; a binding set by any layer other than
  the default, such as an explicit `name = "github"`, is kept.
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
  exclusions). A spec change is in a grant's scope only when
  `merge_grant_scope` lists `spec` and the recorded grant authorizes spec
  coverage ([§7 spec change](protocol.md#spec-change-definition-and-spec-grant-scope)).
  A grant gives permission only, never the approval
  ([§7](protocol.md#7-merge-gate-synthesizer)). Without either, the
  compensation is absent and the profile is unsupported. Today it applies to
  #110 roadmap changes only.

## Asynchronous land (design)

**Status: design only** ([#873](https://github.com/mw-ding/eng-crew/issues/873)
slice D). Nothing here is active yet. Until the slices below land, every
backend is `sync`, the land is the one head-pinned call in
[change](#change), and [protocol §7](protocol.md#7-merge-gate-synthesizer)
applies as written. The gate changes proposed here take effect only through
protocol §7 edits that ship with their code. Owner decisions:
[#649](https://github.com/mw-ding/eng-crew/issues/649) (2026-11-05): the
final gate check runs before queue admission, a head change triggers
re-verification, and a land that was never requested is told apart from a
failed one.

On some backends, changes open as drafts, and a land is a request into a
queue that rebases, tests and lands minutes later, or fails. A backend like
that declares an asynchronous land instead of the pack carrying its own
publish step, polling loop and written waiver.

### Declaration

The pack manifest gets an optional `[land]` table. Without it, the backend
is `sync`, and an unchanged manifest stays valid. That keeps the change
within a minor release.

| Key | Values (default) | Meaning |
|---|---|---|
| `mode` | `sync` \| `async` (`sync`) | `async`: `change.land` is a request; the final state comes from `change.land-status` |
| `opens_draft` | bool (`false`) | Changes open as drafts that cannot land until `change.publish` runs |
| `serializes` | bool (`false`) | The backend lands at most one change per repo at a time, each on the tip the previous land left |
| `tests_against_tip` | bool (`false`) | The backend tests the exact patch it lands on the current tip, and refuses the land on red |

`resolve` fails before dispatch when `async` is declared with
`change.land-status` unsupported, when `opens_draft = true` is declared with
`change.publish` unsupported, or when `serializes`, `tests_against_tip` or
`opens_draft` is true under `sync`. A runtime without an async binding
(Grok Bot today) refuses `async` the same way. The new operations are
conditional: a `sync` manifest never needs them.

### Operations

| Operation | Guarantee | Protects |
|---|---|---|
| Publish (`publish`) | Makes a draft change reviewable and landable; running it again is harmless; supplies no approval, verdict or gate | I5 |
| Land, async (`land`) | A request pinned to the given head that returns at once. It is refused if the head moved. A repeated request for the same change and head never lands twice | I3, I4 |
| Land status (`land-status`) | For a change and head, returns `none` (never requested at this head), `queued`, `landing`, `landed <full revision>` or `failed <reason>`; a head change while queued ends in `failed` | I3, I4 |

An unreadable or malformed status is unknown, never `none`, and is never
taken as permission to request again.

### Synthesizer loop

1. **Final gate check before admission.** Re-check every §7 gate at the
   pinned head right before the request, as for a sync land. Publication
   satisfies "not draft" and nothing else.
2. **Intent first.** Record a land intent keyed by change and head in
   runtime state, read `land-status`, and request only on `none`. A lost
   acknowledgement is resolved by reading the status again, never by a
   blind resend. On `none` after a lost acknowledgement, the gate check
   reruns before the next request.
3. **Poll.** Read `land-status` every `land_poll_interval` seconds (profile
   option, default 60) until `landed` or `failed`, or until `land_timeout`
   (default 3600, at least the interval). Both options are optional and
   validated as positive integers.
4. **Record.** Only `landed` posts `merge`, with `sha=` the checked head and
   the landed revision named, which may differ from the head after a backend
   rebase. Default-branch CI is then checked at the landed revision, as after
   a direct land. `failed`, a timeout and an unknown status report
   `blocked:` and post no `merge`. A timeout keeps the intent, so a later
   `landed` still gets its record.
5. **Restart.** On every wake, read `land-status` for each recorded intent
   before anything else. `queued` or `landing` resumes polling, and `landed`
   posts a missing record. Neither requests the land again.
6. **Head change.** A new head ends the old request (`failed`). The new head
   needs every §7 gate again, a fresh verdict or verdict portability
   included, before a new intent.

### Gate alternatives

A bare `async` changes no gate: the synthesizer holds the land lock from the
final gate check until the terminal status and the `merge` post, and
tested-with-`<default-branch>` must hold at the request as today.

- **C7.** With `serializes = true`, the backend meets
  [C7](runtimes/README.md#c7-serial-land) itself and no local land lock is
  taken. The runtime contract table declares this in the gap format.
- **Tested with `<default-branch>`.** With `tests_against_tip = true`, the
  backend's land check meets the gate for the exact patch it lands. The
  synthesizer runs no update-from-base and builds no train. `crew train`
  refuses with a reason that names `land.tests_against_tip`. The merge record
  names the backend check and the landed revision. A backend rebase that
  changes the patch must fail the land, not change it.

The gate registry rows for C7 and tested with `<default-branch>` name these
backend alternatives when they become active. No merge-ok or standing grant
substitutes for either flag, and CI is never waived.

### GitHub

GitHub stays `sync`: its manifest gets no `[land]` table, and every GitHub
render stays byte-identical.

### Slices

| Slice | Paths | Adds |
|---|---|---|
| B1 | `scripts/crew-config.py`, `docs/profile.md` | `[land]` schema, conditional operations, `land_poll_interval` and `land_timeout`, the `resolve` refusals |
| B2 | `scripts/crew.d/land.py` (new), `scripts/test-crew-land.py` | Request and status handling: queued to landed, failed, timeout, stale head, lost acknowledgement |
| B3 | `scripts/crew.d/land.py`, protocol §7 | Persisted intent, restart read-back, the merge record's landed revision |
| B4 | `scripts/crew-render.py`, tmux builder and synthesizer templates, `scripts/crew.d/train.py`, protocol §7 and the gate registry | Rendered `<op:change.publish>`, `<op:change.land>` and `<op:change.land-status>` steps when async (the sync render stays byte-identical), no-lock and train refusal under the flags |

## Bindable sensitivity (design)

**Status: design only** ([#880](https://github.com/mw-ding/eng-crew/issues/880)
slice D). Nothing here is active yet. Until the slices below land, roles run
`scripts/crew-config.py sensitive` as written in the
[protocol](protocol.md#sensitive-class), and a pack cannot add to it. Owner
decision ([#649](https://github.com/mw-ding/eng-crew/issues/649),
2026-11-05): a pack binding can add matches but never remove built-in ones.

An org that keeps its sensitivity policy in its own source (ownership files,
a policy registry) binds that check as an extension. The built-in classifier
always runs, and the extension can only add to its result.

### Declaration

`classify` is an optional concern with one operation, `sensitive`, like
[release](#release). Without a `[backends.classify]` table there is no
extension, every existing manifest and profile stays valid, and
classification is today's.

| Operation | Guarantee | Protects |
|---|---|---|
| Classify sensitive (`sensitive`) | An extension command that reads the classifier's input on stdin and prints the [shared JSON result](profile.md#content-rules-879); core adds its matches to the built-in ones and never lets it remove one | I4 |

I4 because the land reads the sensitive label.

A pack binds it in three places:

```toml
# pack profile.toml
[backends.classify]
name = "<pack>"
# pack manifest.toml
[capabilities.classify]
sensitive = "supported"
# pack render/backends/<pack>.toml
[classify]
sensitive = "<cli> policy classify --stdin --json"
```

`resolve` fails when `[backends.classify]` names a backend whose
`classify.sensitive` is not `supported` (the bundled `github` declares no
extension), when the backend map has no `[classify] sensitive` command, or
when that command holds a placeholder. `emulated` is refused: an extension
either runs or does not. `resolve` prints the bound command with its
`pack:<name>` provenance.

### One entry point

`<op:classify.sensitive>` always renders the core entry
`scripts/crew-config.py sensitive`, whatever the backend. The renderer never
substitutes a backend map's `[classify] sensitive` value into a brief, so no
pack can replace the core run. The four call sites
(`templates/runtimes/tmux/builder.md`, `templates/runtimes/tmux/coordinator.md`,
`templates/triage-flavor.md`, `templates/runtimes/grok-bot/builder-b1.md`)
use the token and keep their own arguments around it, so the default render
is byte-identical to today's.

### Union, fail-closed

`scripts/crew-config.py sensitive` (its runner may move to a
`scripts/crew-sensitive.py` helper with #879):

1. Validates the resolved profile. Invalid configuration exits 1 before any
   classifier runs, as today. Missing or incomplete diff input under
   [content rules](profile.md#content-rules-879) exits 3 and runs no
   extension.
2. Runs the built-in path rules (mandatory defaults plus profile `paths`)
   and any content rules.
3. With an extension bound, runs its command through `sh -c` in the current
   directory, with the same stdin bytes (the path list, or the diff under
   `--diff`), the inherited environment and a 120-second limit. The
   extension never sees the built-in result.
4. Adds each extension path match to `matches`, its rule names prefixed
   `<pack>:` so the record shows the source, and each extension `content`
   record to `content`, with the same prefix on `rule`. Results are sorted
   as in the shared contract.
5. Counts the extension as failed on a nonzero exit, a timeout, stdout that
   is not one JSON object, `label` other than `null` or `crew:sensitive`, a
   `matches` that is not an object of path to rule-name lists, a malformed
   `content` record, or `label = "crew:sensitive"` with no match to record.
   Unknown fields are ignored. A failure adds one line to `errors` naming
   the pack and the cause, with no extension matches.
6. Sets `label` to `crew:sensitive` when `matches`, `content` or `errors`
   is nonempty. Exit is 0 for every result from a valid configuration,
   including a failed extension.

So an extension negative never clears a built-in positive, and a broken
extension reads as sensitive, never as clean. `errors` is present only when
an extension is bound: `[]` after a clean run. Without an extension the
output and exit codes are byte-identical to today's.

### Slices

| Slice | Paths | Adds |
|---|---|---|
| B1 ([#961](https://github.com/mw-ding/eng-crew/issues/961)) | `scripts/crew-config.py`, `docs/profile.md` | Optional `classify` concern, the backend-map command lookup and fold, the `resolve` refusals |
| B2 ([#962](https://github.com/mw-ding/eng-crew/issues/962)) | `scripts/crew-config.py` or `scripts/crew-sensitive.py`, their tests | The union runner: built-in positive with extension negative, extension-only positive, failure, malformed JSON, no extension, shared content records |
| B3 ([#963](https://github.com/mw-ding/eng-crew/issues/963)) | `scripts/crew-render.py`, the four call sites, protocol Sensitive class | The fixed token value, the call sites on the token, the operative protocol wording; default render byte-identical |

## Rebase update from base (design)

**Status: design only** ([#874](https://github.com/mw-ding/eng-crew/issues/874)
slice D). Nothing here is active yet. Until the slices below land, every
backend updates by merge, [change](#change) and the
[protocol](protocol.md) apply as written, and protocol wording changes only
with the code that enforces it. Owner decision 3 on
[#649](https://github.com/mw-ding/eng-crew/issues/649) (2026-11-05): rebase
is allowed only with the guarantee that every earlier head stays readable,
merge stays the default, rebase disables trains, and there is no weaker
emulated mode.

On a VCS that forbids merge commits, where the review backend keeps every
uploaded version of a change, the only update is to rebase and upload. Such a
backend declares that strategy instead of the pack declaring
`change.update-from-base` `unsupported`, or `emulated` with a guarantee the
[capability rule](#capability-declaration) forbids weakening.

### Declaration

The pack manifest gets an optional `[strategy]` table. Without it, the
backend updates by merge, and an unchanged manifest stays valid. That keeps
the change within a minor release.

| Key | Values (default) | Meaning |
|---|---|---|
| `update_from_base` | `merge` \| `rebase` (`merge`) | How `change.update-from-base` makes the new head |
| `retains_prior_heads` | bool (`false`) | The review backend keeps every earlier head of a change readable, by full revision, for as long as the change record exists |

`validate` and `resolve` refuse `rebase` without `retains_prior_heads = true`,
and `retains_prior_heads` under `merge`. The table is the only way to
declare a rebase: an `emulated` note on `change.update-from-base` that
describes a rebase is `unsupported`. The backend map binds the commands as
today, for example
`update-from-base = "<cli> rebase --onto <default-branch> && <cli> upload <change-id>"`.
`resolve` exposes the resolved strategy to the renderer, the precheck and
`crew train`.

### Guarantees under `rebase`

| Operation | Guarantee | Protects |
|---|---|---|
| Push | Uploads a new head as a new version of the same change; every earlier head stays readable on the review backend | I3 |
| Update from base | Rebases the change onto the given base and uploads the result as a new head; earlier heads stay readable; stacked children are restacked onto the new head and uploaded with it | I3 |

"Never rewrites shared history" protects I3: every verdict, marker and proof
stays checkable against the head it names. Under `rebase`, retained heads
give that protection instead, so a new version replaces the tip only through
the bound `push` or `update-from-base` upload, never a raw force-push to a
ref that does not retain. Under `merge` the no-force-push and
no-shared-branch-rewrite rules apply unchanged. A GitHub repo that requires
linear history needs no rebase: that rule governs the default branch, and
the squash land already keeps it linear.

### Protocol under `rebase`

- **Hard rules.** "Merge-up uses a merge commit or the backend's
  update-branch" reads "update from base by the declared strategy"; the
  no-force-push rule names `merge` backends.
- **Precheck step 1.** An unpublished change still rebases. A published
  change uses the declared update, "rebase onto `<default-branch>` and
  upload" under `rebase`, and merge-up under `merge`. The precheck marker's
  `rebase=` field is unchanged.
- **Verdict portability.** Unchanged. The synthesizer compares B→H with the
  updated base→updated head by `crew content` with all four SHAs. H stays
  fetchable because the backend retains it; an unfetchable H blocks the
  carry. A conflict or a differing patch goes to the builder, whose signed
  conflict note records both pairs, then to delta review and validation.
  Each restacked child is its own base-update push.
- **Markers.** `pass=merge-up`, the merge-up ack and every other marker
  name stay. Only the rendered instruction text changes.

### Briefs

The renderer picks the update wording from the resolved strategy: "rebase
onto `<default-branch>` and upload" under `rebase`, and merge-up under
`merge`. That covers the generated precheck step, the builder's and solo
briefs' merge-up and no-rebase lines, the synthesizer's behind and conflict
routing, the Grok Bot briefs and the PR conventions included from
[roles](roles.md). Every GitHub render stays byte-identical.

### Trains

`crew train build` and `crew train bisect` stack merge commits, so they
refuse on a `rebase` backend before creating any worktree, branch or change,
with a reason that names `strategy.update_from_base = "rebase"`. The
synthesizer lands ready changes one at a time: the declared update,
required CI green at the new head, verdict portability, then the
head-pinned land. A backend that declares
[`tests_against_tip`](#asynchronous-land-design) meets
tested-with-`<default-branch>` itself. No local train is offered as a
fallback.

### GitHub

GitHub stays `merge`: its manifest gets no `[strategy]` table, and every
GitHub render stays byte-identical.

### Slices

| Slice | Paths | Adds |
|---|---|---|
| B1 [#951](https://github.com/mw-ding/eng-crew/issues/951) | `scripts/crew-config.py`, `docs/profile.md` | `[strategy]` schema, the `validate` and `resolve` refusals, the resolved strategy in metadata |
| B2 [#952](https://github.com/mw-ding/eng-crew/issues/952) | `scripts/crew-render.py`, tmux builder, solo and synthesizer templates, Grok Bot briefs, `docs/roles.md`, protocol hard rules, precheck and portability | Strategy wording in renders, a rebase-backend render fixture, the operative protocol text |
| B3 [#953](https://github.com/mw-ding/eng-crew/issues/953) | `scripts/crew.d/train.py`, `docs/runtimes/tmux.md` | The early `train build` and `train bisect` refusal |

Tests: `scripts/test-crew-config.py` (default, refusals, metadata),
render tests (rebase fixture, unchanged GitHub bytes), `scripts/test-crew-train.py`
(refusal before any side effect) and `scripts/test-crew-content.py`
(identical and differing patch pairs across a rebase).
