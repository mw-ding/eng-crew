---
type: added
issue: 1439
pr: TBD
date: 2026-11-08
box-skill: none
---

Campaign scenario A19 gains an installed-adapter smoke and a live evidence ledger (#797). `dev/tests/scripts/fixtures/campaign/a19/smoke.py` runs once per installed harness and session backend binding, from an operator shell. On one disposable run it drives launch, the `mdstack send` doorbell, the inbox `ack:`, the C5 probe and the pane stop through the runtime's own code. tmux runs on a dedicated server; herdr closes only its own workspace. Each result pins the source SHA, the adapter file hashes and the harness and backend versions. A binding that is not installed, has no interactive launch or is skipped by policy is reported as blocked. The `live` section of `a19/ledger.json` names every binding and the Grok Bot mirror and watch. Each entry links to its evidence, links to a block that states the installation, version, account and sandbox facts, or quotes why the binding is unsupported. `replay.py` fails a missing binding, an entry without a link or a block that leaves out one of those facts.
