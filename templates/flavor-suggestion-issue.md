# Issue template: flavor suggestion

Owner: `<CoordinatorBot>`. Filed in the control-plane repo with plain label
`flavor-suggestion`; never a gate or a `crew:*` state tag. Protocol:
[flavors](../docs/flavors.md#feedback-loop). This body template creates nothing.
Run `scripts/flavor-suggest.py --help` for input formats. Copy its Title and
Label separately and its body below; validate the proposed complete profile
before filing, replacing the pending validator line with actual output.

At most one open issue per project and scope: comment with later signals on
that issue. Keep the current flavor unless the owner explicitly accepts.
A decline closes as not planned; record its date and signal strengths for the
28 day same-signal cooldown, unless the numbers get worse. Missing dated
escaped-defect evidence blocks relaxation.

## Body

```markdown
## Signal

<T1–T3 or R1–R3> as of <date> (UTC). Scope: project | class `<paths>`. Goal: <goal>.
Signal strengths: <paste the report's JSON; retain for decline comparison>.

## Evidence

| Change | Flavor | Changes verdicts | Escaped defects | Cycle time (min) | Engine runs |
|---|---|---|---|---|---|
| <owner>/<repo>#<n> | <flavor> | <k> | <link or 0> | <m> | <r> |

<paste dated defect links and owner feedback card links; name missing inputs>

## Proposed change

<from> → <to>. Knobs: <knob> <old> → <new>, ...

~~~toml
<paste the proposed flavor tables; class scope updates its class record,
not the project's flavor.name; preserve all unrelated profile settings>
~~~

Validator: `crew-config.py validate` → <actual output for the complete profile>.

## Decision

Owner: `accept flavor: <to>` or `decline flavor: <reason>`.
Default if unanswered: keep <from>. A flavor change is never applied by default.
```

On accept, follow the [owner accept path](../docs/flavors.md#owner-accept-path):
record the owner's words, open the tracked profile PR with validator output
and obtain per-change owner merge-ok, or post the untracked profile diff before
applying it. Standing grants never cover this change. Away words may accept a
tighten, never a relax. Close with the applied-change link; after tightening,
re-record open items that have not merged. F7 and spec permissions stay intact.
