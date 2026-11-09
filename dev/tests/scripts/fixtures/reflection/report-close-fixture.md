[Riley/reflection] close-fixture

Window: 2026-11-08T21:00:00Z to 2026-11-09T13:00:00Z. Input SHA: <fixture-sha>. Index: forge 11, lessons 2, findings 1, decisions 1, observations 1.

## Digest

1. rp-deferred-handoff-renudge-environments-terminal-crew-d-lead-py: `environments/terminal/crew.d/lead.py`, accept, via https://github.com/mw-ding/mdstack/issues/1502
2. rp-conflicting-pr-gets-no-ci-environments-terminal-crew-d-poll-py: `environments/terminal/crew.d/poll.py`, accept, via https://github.com/mw-ding/mdstack/issues/1398
3. rp-stale-changes-label-environments-terminal-crew-d-route-py: `environments/terminal/crew.d/route.py`, accept, via https://github.com/mw-ding/mdstack/issues/1483

## Proposals

### 1. rp-deferred-handoff-renudge-environments-terminal-crew-d-lead-py (existing #1502)

- Targets: `environments/terminal/crew.d/lead.py`
- Layer: architecture
- Incidents (1): ri-mw-ding-mdstack-1053 reported https://github.com/mw-ding/mdstack/issues/1502
- Impact: 1 observed nudge at 2026-11-09T09:00:00Z (index observations, ref #1502); the card's "about 10 nudges in 15 minutes" is the reporter's estimate, not measured
- Rank: no confirmed incident in the window; the only proposal with a measured impact
- Existing work: #1502 (open card, triaged P1); no fix found for the class
- Recommended default: accept, routed through #1502

### 2. rp-conflicting-pr-gets-no-ci-environments-terminal-crew-d-poll-py (existing #1398)

- Targets: `environments/terminal/crew.d/poll.py`
- Layer: architecture
- Incidents (3): ri-mw-ding-mdstack-1341 reported https://github.com/mw-ding/mdstack/issues/1398, ri-mw-ding-mdstack-1373 reported https://github.com/mw-ding/mdstack/issues/1398, ri-mw-ding-mdstack-1392 reported https://github.com/mw-ding/mdstack/issues/1398
- Impact: unknown (no measured stall in the index; missing checks count as neither green nor zero delay)
- Rank: no confirmed incident and no measure; 3 reported incidents. A threshold crossing (3 distinct incidents of one class): the pending card is #1403 R6, so none is filed
- Existing work: #1398 (open card, triaged P1); the 2026-11-01 lesson "A conflicting PR shows no checks" is superseded context
- Recommended default: accept, routed through #1398

### 3. rp-stale-changes-label-environments-terminal-crew-d-route-py (existing #1483)

- Targets: `environments/terminal/crew.d/route.py`
- Layer: architecture
- Incidents (2): ri-mw-ding-mdstack-1467 reported https://github.com/mw-ding/mdstack/issues/1483, ri-mw-ding-mdstack-1472 reported https://github.com/mw-ding/mdstack/issues/1483
- Impact: unknown (the coordinator cleared both labels by hand; no duration recorded)
- Rank: no confirmed incident and no measure; 2 reported incidents; findings row "A passing verdict leaves the changes label" at count 2, below the batch threshold
- Existing work: #1483 (open card); findings buffer row, status buffered
- Recommended default: accept, routed through #1483; reflection clears no gate label

## Skipped

- rp-session-loss-environments-terminal-sessions-tmux-adapter-py: fixed without recurrence. ri-mw-ding-mdstack-1474 confirmed https://github.com/mw-ding/mdstack/issues/1474 (the card's first suspect is superseded by the research finding and the correction); fix #1475 merged in #1482, lesson 2026-11-09 applied, owner decision "no private socket for the crew server" followed. One incident, not two; live only after the next release install, per the coordinator's correction.

## Gaps

- Unresolved refs absent from the snapshot: #1053, #1472.
- Missing inputs: none. Selected item without a card: #1514.
- Not read: private runtime logs; impact unknown for proposals 2 and 3.

<!-- crew:v1 role=researcher pass=reflection window=close-fixture sha=<fixture-sha> proposals=3 new=0 incidents=7 -->
— 🔬 Riley (Researcher) · claude-code · claude-opus-5-5
