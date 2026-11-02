# Triage flavor record

At install/intake, the owner confirms `flavor.name` in the project profile.
At triage, resolve the item's default from explicitly named paths' classes,
or the project flavor when none are named. An unset project flavor is
`thorough`; flag the gap. Until class resolution is available, retain
`thorough` for named paths whose class default cannot be verified.

Post this signed comment on every triaged issue. Replace all placeholders;
omit `Reason:` only when no rigor knob is lowered. Owner-selected flavors
carry the owner's words as the reason. Tier measures difficulty separately.

```text
[<CoordinatorBot>/flavor] #<n>: <flavor> (default <default>)
Reason: <reason>
<!-- crew:v1 role=coordinator pass=flavor issue=<n> flavor=<flavor> default=<default> -->
— <CoordinatorEmoji> <CoordinatorBot> (<CoordinatorTitle>) · <harness> · <model>
```

Check the proposed record with `scripts/item-flavor.py --project crew.toml
--issue N` (add `--default NAME` for a verified class default), passing JSON
comment bodies oldest first, including the proposal last. Exit 1 refuses a
lowered record without a nonempty whole-line `Reason:`. Never post that
proposal; retain the default and request a reason through the coordinator.
On each wake roles read the newest coordinator record; missing records use
`thorough` and report `flavor-missing`, refused records use the default and
report `flavor-refused`. Tightening applies immediately. Flavor records
supply no new merge authority; F1–F7 still apply.
