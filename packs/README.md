# packs

Bundled packs: the extension point for org specifics. Part of the
[module layout](../docs/specs/team.md#4-target-module-layout).

## Contents

None: this repo bundles no pack. The GitHub connector lives in
[`connectors/github/`](../connectors/github/).

## How it plugs in

A pack lives outside this repo and references mdstack, never the other way
round ([direction rule](../docs/packs.md#direction-rule)). It supplies
connectors, harnesses, environment defaults, skills and a profile layer,
pinned to an mdstack version range, and may tighten but never loosen a core
floor. Format, discovery and the conformance kit: [packs](../docs/packs.md).
