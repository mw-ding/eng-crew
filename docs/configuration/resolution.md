# Configuration resolution

Configuration module for checking and resolving a profile, split out of the
[profile reference](../profile.md) under the M26 modular organization
principle ([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds
the profile's former [Validate](../profile.md#validate) section: both command
variants, the problem format and exit codes, the rejection list and the
install-time placeholder check. The key schema, host inventory and pack
manifest stay in the profile's [Keys](../profile.md#keys) section.
[Layers and precedence](../profile.md#layers-and-precedence), which builds
the effective profile that `resolve` checks, stays in the profile.

## Validate

```sh
python3 scripts/crew-config.py validate crew.toml
python3 scripts/crew-config.py validate crew.toml --install
```

Each problem prints as `file:key: reason`, where `key` is the dotted path
(`backends.change.name`, `engines.default.order[0]`); exit 1 on any problem,
0 otherwise. It fails on: invalid TOML, a missing required key, an unknown
key, concern, runtime, backend, engine or effort, a wrong type, a malformed
capability, a host inventory problem (`[hosts.<name>]` and `[placement]`
in the profile's
[Keys](../profile.md#hostsname-and-placement)), and a token-shaped value
anywhere in the file.

`--install` rejects remaining install-time placeholders, including embedded
placeholders and entries in lists. The renderer's run-time placeholders
(such as `<n>` and `<head-sha>`) stay allowed. Ordinary validation keeps
allowing template profiles. `resolve --project crew.toml --install` applies
the same check to the effective profile after all layers and overrides
(see the profile's
[Layers and precedence](../profile.md#layers-and-precedence)),
so defaults replaced with concrete project/org values do not fail.
