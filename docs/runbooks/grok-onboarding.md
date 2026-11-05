# Grok Bot onboarding

Onboarding module for the Grok Bot install state and wiring, split out of the
[onboarding runbook](../runbook-new-repo.md) under the M26 modular
organization principle
([#676](https://github.com/mw-ding/eng-crew/issues/676)). It holds the
runbook's
[Step 6: state dir and wiring doc](#step-6-state-dir-and-wiring-doc): the
install-state verification and the four wiring setup items, after
[Step 5: product-safety checks](../runbook-new-repo.md#step-5-product-safety-checks).
The worked
[Filled-in wiring.md](../runbook-new-repo.md#filled-in-wiringmd-derived-from-the-template)
example and
[Step 7: listener wiring per bot](../runbook-new-repo.md#step-7-listener-wiring-per-bot)
remain in the runbook.

## Step 6: state dir and wiring doc

After bootstrap, verify its recorded install before filling the wiring doc:

```bash
cat <state-dir>/<owner>__<repo>/VERSION
cat <state-dir>/<owner>__<repo>/install.json
ls -la <state-dir>/<owner>__<repo>/ <state-dir>/<owner>__<repo>/claims
```

Confirm the source, runtime, profile copy and pending human steps match the
reviewed plan. Keep bootstrap-owned files intact; rerun bootstrap for profile
changes. For Grok Bot, copy the deployed `paths.live_dir/runtime/wiring.md` to
the state directory's `wiring.md` if it is missing. Continue with items 2–4
below, copying `reviewer-engines.md` only if it is missing. Record bootstrap
output and the installed version in the wiring doc.

1. **Manual fallback:** create the state dir and files if bootstrap was not used:

   ```bash
   mkdir -p <state-dir>/<owner>__<repo>/claims <state-dir>/<owner>__<repo>/locks
   : > <state-dir>/<owner>__<repo>/locks/merge.lock
   cp crew.toml <state-dir>/<owner>__<repo>/crew.toml
   cp <path-to-this-repo>/templates/runtimes/grok-bot/wiring.md <state-dir>/<owner>__<repo>/wiring.md
   cp <path-to-this-repo>/templates/runtimes/grok-bot/reviewer-engines.md <state-dir>/<owner>__<repo>/reviewer-engines.md
   ls -la <state-dir>/<owner>__<repo>/ <state-dir>/<owner>__<repo>/claims
   ```

2. Fill in `wiring.md` from [../templates/runtimes/grok-bot/wiring.md](../../templates/runtimes/grok-bot/wiring.md):
   section 0 from steps 1 to 5 above, section 1 from the identities, section 2
   from [Step 7](../runbook-new-repo.md#step-7-listener-wiring-per-bot), section 4 from the choices in
   step 4. Start from the deployed or manually rendered `runtime/wiring.md`,
   with the profile values already in. Mark every item `planned`, then `applied` or `live` with a date as
   you go. Keep it the one place that lists what is installed.

3. Copy the template, `reviewer-engines.md`, and fill `Updated` plus the
   allowed engine set (private repos: Claude Code or Codex only). Only the
   reviewer bot's main chat edits it afterwards
   ([reviewer-engines.md](../../templates/runtimes/grok-bot/reviewer-engines.md)).

4. Install the README seed. Copy [../templates/product-readme.md](../../templates/product-readme.md)
   into the repo root `README.md` and fill every section, or verify the
   existing README already has problem, what it is, how to run / use, how the
   crew works and status. Record which in the wiring doc. A product repo
   without such a README fails [protocol safety](../protocol.md#8-safety).
