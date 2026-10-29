# Evidence adapter: CLI exit code and stdout

Shape: CLI. Also usable for a service (the start or probe command) and an API
(a `curl` call) until they get their own adapter. Protocol:
[verification](../../docs/verification.md).

## Builder: capture

1. Build or install the PR head. Work from a clean checkout of the head commit.
2. Run the command once and record it. For example, with `<cmd>` standing for
   the command under test:

   ```sh
   mkdir -p evidence/<pr>
   {
     echo '$ <cmd>'
     <cmd> >/tmp/out.txt 2>/tmp/err.txt; code=$?
     echo "exit: $code"
     echo '--- stdout'
     cat /tmp/out.txt
     echo '--- stderr'
     cat /tmp/err.txt
   } > evidence/<pr>/<name>.txt
   ```

3. Review the file and scrub anything volatile or private: timestamps, absolute
   box paths, hostnames, tokens, emails. Replace with placeholders, and note
   the replacement at the top of the file.
4. Commit it **on the PR branch** and push. The head moves; CI re-runs.
5. In the PR body, `## Acceptance Evidence`, add the shape and the path:
   `shape: CLI, evidence/<pr>/<name>.txt`.

## Fixture contents

The file must contain, in this order:

- The exact command line, prefixed with a dollar sign and a space.
- `exit: <code>`.
- A `--- stdout` section and a `--- stderr` section (empty is fine, but the
  heading stays).
- Any scrub note as a first line starting with `# scrubbed:`.

Capture one fixture per claimed behaviour, such as a success case and a failure
case with its non-zero exit code.

## Verifier: re-run and diff

1. Check out the PR head. Open the fixture from the head commit.
2. Re-run the recorded command exactly and write the result to a temporary file
   in the same format.
3. Diff it against the committed fixture, ignoring only the volatile fields the
   `# scrubbed:` note names:

   ```sh
   diff evidence/<pr>/<name>.txt /tmp/rerun.txt
   ```

4. Record in the validation section: the command, `agrees` if the diff is empty
   and the output shows the claimed behaviour, `disagrees` if it differs or
   does not show the claim, `unverified` if the command cannot run in the
   validator's environment (say why).
