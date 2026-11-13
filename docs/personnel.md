# Personnel content and host import

The personnel producer exports pinned role content for a host that brings
its own coordination machinery. It runs in the full producer checkout;
the installed directory contains Markdown, descriptors and a JSON manifest,
with no terminal CLI, resolver, renderer or executable adapters. This is
the #1180 delivery of [team §9.6](specs/team.md#96-pinned-personnel-import-and-host-binding).
It starts no routine and supplies no gate or merge permission.

## File and execution boundary

| Source path | Category / consumer treatment |
|---|---|
| `roles/eng/*.toml` | Stable `eng/role` descriptors; authority is pinned, not overlaid |
| `roles/seats/` | Seat descriptors and additive skill content; placeholders remain placeholders |
| `templates/policy/` | Canonical role skills, procedure entry skills and policy fragments |
| `docs/specs/`, `docs/protocol.md`, `docs/flavors.md`, `docs/verification.md` | Governing requirements, gates, markers, rigor and evidence contracts |
| `actions/*.md` | Generic action semantics and binding contracts |
| `templates/personnel/brief.md` | Producer composition input; output is `briefs/eng/<role>.md` |
| `scripts/personnel-files.txt` | Explicit content selection; governing doc references stay available |
| `scripts/personnel-bundle.py` | Producer only: validates, composes and locally installs content |
| `core/crew-config.py`, `core/crew-render.py` | Full producer resolver/renderer; transitively import terminal session adapters; not portable consumer modules |
| `environments/terminal/` | Owned execution machinery: scheduler, leads, trains, reap/runner, wake and sweepers; excluded |
| `cli/mdstack` | Terminal-backed execution CLI; excluded |
| `harnesses/`, `connectors/` | Execution adapters chosen and supplied by the host; excluded |

The normal release bundle remains a full producer/runtime distribution.
The personnel exporter is separate and uses no consumer resolver. Its content
allowlist includes supporting docs to keep required policy references local.
References to execution code, historical artifacts or runtime templates point
to the pinned producer source; they do not install or require that machinery.
Terminal window/lifetime/discovery fields in copied descriptors are inert
binding metadata. A host must not turn them into authority or start jobs from
them. The target `protocols/` and `install/` module moves remain design only.

## Produce and install

In a reviewed producer checkout, select an exact full commit SHA and a
reviewed host binding. No tag, branch, network role lookup or second source
is accepted as a role pin. Example (replace the source pin and binding):

```sh
python3 scripts/personnel-bundle.py \
  --ref FULL_40_CHARACTER_COMMIT_SHA \
  --binding host-binding.toml \
  --role eng/builder --role eng/reviewer --role eng/synthesizer \
  --out personnel/selected-version
```

`--root` can name another full producer checkout. All selected content and
composition templates are read at the source commit, ignoring uncommitted
producer edits. `--out` is the local install destination, not a running host.
Validation finishes before publication. A missing role, duplicate ID,
incomplete binding, unresolved policy reference or unsupported invariant
returns nonzero without publishing an install. Identical input at an existing
destination verifies its bytes and does no writes; different input or edited
content requires a new destination and is refused rather than overwritten.

`personnel.json` records source commit/version, selected IDs, binding
ID/version and declaration, setting provenance and every content file's
SHA-256. The binding digest covers its normalized declaration. It is an
integrity record, not a signature or permission grant; the host verifies it
against the reviewed producer and rejects local authority edits.
Source version is `VERSION` when present, otherwise the latest release
heading at the source pin; the full commit distinguishes unreleased content.

## Thin binding and consumer loading

Grok Bot and a generic host are consumers of these role packs plus a thin
mechanical binding, rather than a second full mdstack control plane.
A binding TOML declares `id`, `version`, `gaps`, `[capabilities]`,
`[actions]`, `[operations]` and optional `[settings."eng/role"]`.
The offline example is `dev/tests/fixtures/personnel/fake-host.toml`.
It maps generic actions and canonical `<op:concern.operation>` tokens to
fake host commands; the exporter never executes those mappings.

Required capabilities are wake/delivery, durable queues, run identity,
claims/status, connector access, head-bound land, reviewer independence
and synthesizer-only land. Each must be explicitly true. Nonempty gaps
are refused by this producer: an unsupported invariant cannot silently
become supported by import. A real binding's capability declarations and
composed prose need review; schema validation alone cannot prove its runtime
guarantees. The existing [Grok Bot gaps and watches](runtimes/grok-bot.md#runtime-contract)
remain binding responsibilities; fake-host proof is not live adoption.

The host loads `personnel.json`, verifies its source and file hashes, then
loads `briefs/eng/<role>.md`, the linked canonical role `SKILL.md`, and its
procedure entry skills. Canonical fragments are reference material, with
run parameters supplied at dispatch. Terminal examples do not execute at
the consumer: the personnel entry's action table is the mechanical binding.
The host supplies the repository/item/head/pass/round, actual harness/model,
worktree and claim. It owns wake/delivery/recovery, connector credentials,
durable reports and the live head-bound stage 7 checks before any land.
Importing a synthesizer descriptor never authorizes another role to land.

Run the isolated import/refusal test from the producer:

```sh
python3 scripts/run-tests.py test-personnel-bundle.py
```

The fake host loads all five engineering briefs and every procedure with
`environments/`, `core/`, `cli/`, `harnesses/` and `connectors/` absent in the
installed tree. It checks required policy links and operation mappings,
hashes, idempotency and refusal before publication. It makes no real claims,
posts, routines, launches or land requests.

## Import settings and authority

The only settings are `presentation`, `engine` and `extra_skills` per selected
role ID. Presentation corresponds to deployment identity display settings;
engine requests still pass the host's existing routing/independence checks
before launch. Additive skills must be pinned canonical producer `SKILL.md`
paths under `templates/policy/` or `roles/seats/`; no arbitrary prose overlay
or external skill discovery is accepted. Setting provenance names the
reviewed binding ID/version in the manifest.

Unknown settings, including role class/escalation, marker role/pass semantics,
reviewer identity/engine independence or land authority, are refused.
Descriptors are copied unchanged. Missing roles and colliding selections
fail; there is no last-writer replacement. This import mechanism adds no
registry layering, external role-definition discovery or generic inheritance.
Those remain separate future work.
