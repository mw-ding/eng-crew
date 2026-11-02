# Evidence adapter: CLI exit code and stdout

Shape: CLI. Also usable for a service (start, readiness probe and logs) and
an API (`curl` request with status/body). Protocol:
[verification](../../docs/verification.md).

## Builder: capture inline

1. Build the change head and work from its clean checkout. Name the capture
   SHA, working directory, setup and a proof label such as `R1`.
2. Run the command and emit a copyable command/output pair to stdout. Replace
   the example argv with the exact command under test:

   ```sh
   python3 - <<'PY'
   import shlex, subprocess
   command = ["python3", "scripts/check-repo.py", "--only", "shapes"]
   result = subprocess.run(command, capture_output=True, text=True)
   print("```sh\n" + shlex.join(command) + "\n```")
   print("\n```text\nexit:", result.returncode)
   print("--- stdout\n" + result.stdout, end="")
   print("\n--- stderr\n" + result.stderr, end="")
   print("\n```")
   PY
   ```

3. Scrub private or volatile values before posting. The output block begins
   with optional `# scrubbed:` / `# volatile:` notes, then `exit: <code>`,
   `--- stdout`, `--- stderr` (empty sections keep their headings). A service
   adds `--- log`; API output includes status/body and names ignored fields.
   Keep secrets as variable names in commands, never values.
4. Paste the pair into `## Test Output` or below the `## Acceptance Evidence`
   table at creation; proof cells name `shape: CLI, R1` and key output. Later
   pairs go in a signed fix / ci-fix review with its capture SHA. Never edit
   the body or commit evidence. Without a code push, late evidence needs the
   coordinator's rereview steer.
5. One pair per claimed behaviour, including success and failure cases.
   Apply the [size limits](../../docs/verification.md#q3-size-limits): truncate
   long output with an omission note and CI-log link or a re-run label.

## Verifier: re-run and compare

1. Check out the current head. Read the pair in the body or signed builder
   review; a review's marker SHA must be head or an earlier change commit.
2. Copy and run the `sh` block, using its setup and working directory. Compare
   exit code, stdout and stderr to the expected `text` block, ignoring only
   named scrubbed or volatile fields. For truncated proof, compare retained
   lines (excluding the omission note) and verify the claim from the full run.
3. Record your own command/output excerpt inline: `agrees` if it shows the
   claim at head, `disagrees` if it differs without justification or fails the
   claim, `unverified` if it cannot run (say why). Missing required proof is
   `disagrees`; earlier proof is accepted only when it still holds at head.
