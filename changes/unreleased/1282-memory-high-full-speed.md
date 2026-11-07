---
type: changed
issue: 1282
pr: TBD
date: 2026-11-07
box-skill: none
---

At full speed (every pool's effective cap equal to its full cap), the
scheduler now counts memory as high only at `critical`: macOS `warn` counts
as low, so the target T can grow again, and the Linux `some avg10` high
threshold moves from 10.0 to 40.0. Light mode keeps `warn` as high. The new
`runtime.options.memory_high` option (`warn` or `critical`) overrides the
mode rule, and the snapshot (`memory_high`) and summary line
(`mem warn (high at critical)`) show the effective threshold.
