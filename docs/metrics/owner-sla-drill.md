# Owner-SLA drill (P7)

## Purpose

Prove the owner-SLA path once, end to end: a synthetic `crew:hold` that needs a
user decision becomes `crew:needs-md`, the coordinator pings the user with a
recommended default and an auto-apply time, and the resolution is recorded. The
2h SLA itself is out of scope and is not changed here.

## Rule drilled

- [Owner decisions: one channel and a 2h SLA](../protocol.md#6-duties-on-wake-all-roles):
  after more than 2h of the user's awake hours in Pacific Time (PT), the
  coordinator adds `crew:needs-md` and pings the user with the link, a one-line
  question, a **recommended default** and an **auto-apply time** (date and time
  in PT). At that time it applies the default if the user has not answered and
  records it. It then clears `crew:needs-md`; other holds stay.
- Allowed defaults: **merge** (only for 🟢/🟡 doc-only changes that qualify
  for the [standing doc-only merge-ok](../protocol.md#6-duties-on-wake-all-roles)
  grant — no code, no `.github/`, no `templates/`, no `docs/protocol.md`, green
  CI; the synthesizer re-checks every §7 gate before merging), **defer**,
  **keep hold**. The drill uses **keep hold**, which has no merge or code side
  effect.
- The sweeper backstop: [coordinator-stuck-pr-sweeper](../../templates/coordinator-stuck-pr-sweeper.md)
  adds `crew:needs-md` for held items whose latest hold asks the user for a
  decision, and counts only awake hours PT.

## Synthetic hold scenario

A throwaway issue `[drill] owner-SLA, safe to close` on `<owner>/<repo>`
(or a doc-only throwaway PR), labelled `crew:hold`. Its latest comment asks the
user one question: "Keep this drill item on hold, or close it as not planned?"
It is a decision ask, not a lane/dependency hold, so it is eligible for
promotion. Recommended default: **keep hold**, then close the item as part of
cleanup after the drill. No product code or protocol file is touched.

## Steps and expected timestamps

T0 is the time the hold is raised, inside awake hours PT. All times are awake
hours PT; the clock pauses outside them.

| # | Step | Actor | Expected time |
|---|---|---|---|
| 1 | Raise the hold: add `crew:hold`, post the decision ask on GitHub and in the coordinator chat | Coordinator | T0 = Thursday 2026-10-29 10:00 AM PT |
| 2 | Wait; no promotion before 2h of awake time has passed | Coordinator | T0 to T0+2h |
| 3 | After more than 2h awake: add `crew:needs-md`; ping the user with link, question, recommended default (keep hold) and auto-apply time | Coordinator (or sweeper adds the label, coordinator pings) | T0+2h, shortly after |
| 4 | Owner answers, or does nothing | Owner | before the auto-apply time |
| 5 | At the auto-apply time with no answer, apply the default and record it on the item | Coordinator | auto-apply time stated in step 3 |
| 6 | Clear `crew:needs-md`; leave `crew:hold` unless the answer or default says otherwise | Coordinator | right after step 4 or 5 |
| 7 | Record resolution (answer or default, who, when) and clean up the throwaway item | Coordinator | right after step 6 |

If T0+2h falls outside the user's awake hours, the 2h clock is paused outside
those hours, as in the sweeper's notes. Count the remaining time from the next
awake window, and write the adjusted expected time in the Results table. If the
awake schedule is unknown, report that to the coordinator; do not invent one.

## Pass/fail checks

The coordinator marks each as pass or fail in the Results table:

1. `crew:needs-md` was added only after more than 2h of awake hours PT, not early.
2. The ping used the single owner channel (GitHub and coordinator chat) and
   named the link, one-line question, recommended default and auto-apply time in PT.
3. The default was applied only at the auto-apply time, and only if unanswered.
4. `crew:needs-md` was cleared after resolution; `crew:hold` was not cleared
   merely because the SLA expired.
5. The resolution is recorded on the item and in the Results table.

## Execution

- Status: **scheduled**.
- The coordinator (Ash) owns the clock and runs the drill; the builder does not.
- Planned T0: **Thursday 2026-10-29 10:00 AM PT**.
- Expected promotion (`crew:needs-md` + ping): **Thursday 2026-10-29 12:00 PM
  PT** (T0 + 2h awake).
- Expected auto-apply time stated in the ping: **Thursday 2026-10-29 12:30 PM
  PT**.
- Ash may shift these if the awake window differs; Ash still owns the clock.
- Results are recorded in the table below in this same file.

## Results

| Field | Value |
|---|---|
| Drill item | `<link>` |
| T0 hold raised | `<timestamp PT>` |
| `crew:needs-md` added | `<timestamp PT>` |
| Ping posted (default, auto-apply time) | `<timestamp PT>` / `<default>` / `<timestamp PT>` |
| Owner answer or default applied | `<timestamp PT>` / `<answer or default>` |
| `crew:needs-md` cleared, resolution recorded | `<timestamp PT>` |
| Checks 1-5 | `<pass/fail each>` |
| Gaps found | `<none or issue link>` |

## Gaps

Gaps found by the drill become a follow-up issue on the next open milestone.
They are not fixed as a drive-by protocol edit outside the M4 batch.
