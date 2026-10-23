# agentconnect routine list (worked example)

Worked example, exported Oct 19, 2026. Placeholders in the templates map to the
values below; see [README.md](README.md).

| ID | Bot | Name | Scope |
|---|---|---|---|
| B1 | Ben | build intake and fix rounds | repo-wide, standing |
| B2 | Ben | per-PR watch | one PR, self-deletes |
| V1 | Vera | PR intake (anyone) | repo-wide, standing |
| V2 | Vera | per-PR watch | one PR, self-deletes |
| S1 | Sam | merge on approval | repo-wide, standing |
| A1 | Ash | after merge | repo-wide, standing |
| A2 | Ash | steering dispatcher | repo-wide, standing |
| A3 | Ash | stuck-PR sweeper (added Oct 19, 2026) | schedule |

## Trigger JSON as run in the pilot

B1 originally also carried `review-changes-requested`. The templates move that
event to B2 so each event has one consumer; the pilot's B1 relied on the
allowlist to admit only reviews by `md-mt` on `mw-ding` PRs.

```json
{ "type": "github", "repo": "mw-ding/agentconnect",
  "events": ["issue-assigned", "review-changes-requested"],
  "userAllowlist": ["mw-ding", "md-mt"] }
```

B2, created for PR `<n>`:

```json
{ "type": "github", "repo": "mw-ding/agentconnect", "pr": "<n>",
  "events": ["ci-failed", "review-changes-requested", "pr-merged", "pr-closed"] }
```

V1:

```json
{ "type": "github", "repo": "mw-ding/agentconnect", "events": ["pr-opened"] }
```

V2, created for PR `<n>`:

```json
{ "type": "github", "repo": "mw-ding/agentconnect", "pr": "<n>",
  "events": ["ci-passed", "review-requested", "pr-merged", "pr-closed"] }
```

S1:

```json
{ "type": "github", "repo": "mw-ding/agentconnect", "events": ["review-approved"] }
```

A1, after merge (the `ci-failed` listener on `main` was added Oct 19, 00:33 PT,
once `main` was found to run push CI):

```json
[ { "type": "github", "repo": "mw-ding/agentconnect", "events": ["pr-merged"] },
  { "type": "github", "repo": "mw-ding/agentconnect", "events": ["ci-failed"], "ciBranch": "main" } ]
```

A2, steering dispatcher:

```json
{ "type": "github", "repo": "mw-ding/agentconnect",
  "events": ["pr-comment", "inline-review-comment"],
  "userAllowlist": ["mw-ding", "md-mt"] }
```

## Other routines on the same platform

- Per-PR watches (B2, V1/V2) are created per PR and self-delete on merge or close.
- Repo-wide PR-review forwarding for the user's other active repos used 9
  routines across 4 repos each, because one watch covers at most 4 repos.
- A daily engineering summary on weekdays and a periodic coding-quota report
  ran as unrelated scheduled routines.

## A3: sweeper schedule

Hourly at minute 17, around the clock. Stuck conditions and thresholds were:
changes requested at head with no builder claim or push for over 30 minutes;
CI green with no reviewer ack or verdict over 30 minutes; approved and green
but not merged over 15 minutes; conflicting with no merge-up over 30 minutes;
CI failed with no ci-fix over 20 minutes; claimed or acked with no output over
3 hours; a `crew:ready` issue with no PR or claim over 60 minutes. Dedup was by
(item, condition, head SHA) with at most one nudge per 2 hours; the third nudge
without progress escalated to the user.
