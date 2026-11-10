Milestone admission: profile `max_active_milestones = <max-active-milestones>`.
Dispatch new builds from at most <max-active-milestones> open milestones, in
milestone order. The earliest active milestone keeps priority. A later
milestone only fills builder capacity the earlier one cannot use because its
remaining items are blocked by dependencies or already in flight. In-flight
PRs in any milestone still finish.
Write no rigor floor into a brief beyond the effective flavor; to raise it,
post a newer item pass=flavor record with a Reason: line first.
