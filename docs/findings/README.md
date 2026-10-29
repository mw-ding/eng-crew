# Findings buffer

One buffer for repeated small smells, instead of one lesson (and one PR) per
incident. A smell is written down once, its count goes up each time it recurs,
and the repeats are batched into a single issue on the next open milestone (the
M5 batch). The buffer itself is [buffer.md](buffer.md).

## Ownership

The coordinator (Ash) owns the buffer: it keeps entries accurate, decides when
to batch, and files the batch issue. The stuck-PR sweeper appends the smells it
sees while sweeping. Builders and reviewer-validators report a smell to the
coordinator instead of opening a lesson PR for it; the coordinator or sweeper
records it.

## How to append a smell

1. Look in [buffer.md](buffer.md) for an entry with the same smell.
2. If one exists, add 1 to its count, add the PR or repo reference and the
   date, and leave the rest alone.
3. If none exists, add a new entry at the end using the template below, with
   count 1.

Template:

```markdown
### <short smell title>

- **Date:** YYYY-MM-DD (first seen; update to the latest sighting)
- **PR / repo:** <owner>/<repo>#N, <owner>/<repo>#M
- **Smell:** <what keeps going wrong, in one or two sentences>
- **Count:** N
- **Proposed fix layer:** architecture | types/schemas | lint | CI check | prose
- **Status:** buffered | batched -> #N | fixed by #N
```

Fix layer: prefer the highest structural layer that would make the smell
impossible, in this order: architecture, types/schemas, lint, CI check, prose.
Prose is last, because a written rule is the easiest for the next run to miss.

## When to batch

Batch when either happens first:

- a smell reaches count 3 or more; or
- the coordinator's triage window (see [protocol](../protocol.md)) or the
  milestone batch comes round.

The coordinator then files ONE issue on the next open milestone covering all
the smells that are ready, and sets each one's status to `batched -> #N` with
the issue number. A smell with count 1 or 2 stays `buffered` until one of the
triggers above. Closed milestones are frozen, so the issue never goes there.

## Relationship to docs/lessons

[docs/lessons](../lessons/README.md) keeps incidents that have a written
analysis. The buffer is for repeated small smells that do not each deserve
one. When a batch is worked, the resulting PR may add or update a lesson; the
entry then links to it and its status becomes `fixed by #N`.

## Sanitization

Same rules as the lessons log (spec R1): no tokens, keys, email addresses,
private chat quotes or real box paths. Use placeholders such as `<state-dir>`
and `<owner>/<repo>`, and bot role names (coordinator, builder,
reviewer-validator, synthesizer).
