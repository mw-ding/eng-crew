# packs

Bundled packs: the extension point for org specifics. Part of the
[module layout](../docs/specs/team.md#4-target-module-layout).

## Contents

| Path | Holds |
|---|---|
| `github/manifest.toml` | Compatibility copy of the GitHub connector manifest, kept for one release (#1223); the source is `connectors/github/manifest.toml` |

## How it plugs in

A pack lives outside this repo and references eng-crew, never the other way
round ([direction rule](../docs/packs.md#direction-rule)). It supplies
connectors, harnesses, environment defaults, skills and a profile layer,
pinned to an eng-crew version range, and may tighten but never loosen a core
floor. Format, discovery and the conformance kit: [packs](../docs/packs.md).
