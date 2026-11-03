# Owner return brief

Owner: `<CoordinatorBot>`. Fill from live records for the away entry's interval;
copy full URLs, include every section, and use `None` when empty. Post once
on the tracking issue and send the same standalone brief in the owner channel.

```markdown
## Return brief

<Outcome, next decision or ask, and recommended action first.>

Away interval: <entry time> → <return time>.

### Landed

- <Result and full merged-change URL.>

### Defaults applied

- <Decision, applied default, time, and full decision-record URL.>

### Auto-approvals

- <Each line of `crew-permit.py log --entry <entry>` (docs/permit.md).>

### Waiting

- <Question or blocker, recommended default, deadline with timezone,
  and full issue or PR URL.>

### Next

<Next action or owner ask; state when no action is needed.>

— <CoordinatorEmoji> <CoordinatorBot> (<CoordinatorTitle>) · <harness> · <model>
```
