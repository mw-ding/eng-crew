# Evidence adapter: CLI exit code and stdout

Shape: CLI. Also usable for a service (start, readiness probe and logs) and
an API (`curl` request with status/body). Protocol:
[verification](../../docs/verification.md).

## Builder: capture inline

1. Build the change head and work from its clean checkout. Pick a proof label
   such as `R1`. Never hand-write, paraphrase or re-split a capture.
2. Run the command with the capture helper and paste its output verbatim:

   ```sh
   python3 <mdstack>/scripts/evidence-cli.py --label R1 [--setup setup.sh] \
     [--scrub-env VAR] [--volatile NOTE] -- <argv...>
   ```

   It prints the header line (`Proof R1 · scripts/evidence-cli.py · sha
   <sha> · cwd <dir>`), the copyable `sh` block and the output block below.
   Put any temp repo, fake `gh` or fake tmux in the `--setup` file so the
   `sh` block recreates it. In a working copy git does not serve, pass
   `--sha <full head> --root <repo root>` so the header carries the real head
   and a root-relative cwd; a `--sha` that differs from git's HEAD is refused.
   Without the helper, run this script instead, replacing the example argv; it
   prints the same three parts:

   ```sh
   python3 - <<'PY'
   import os, shlex, subprocess
   command = ["python3", "scripts/check-repo.py", "--only", "shapes"]
   git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True).stdout.strip()
   cwd = os.path.relpath(os.getcwd(), git("rev-parse", "--show-toplevel"))
   print(f"Proof R1 · cli-exit-stdout.md · sha `{git('rev-parse', 'HEAD')}` · cwd `{cwd}`\n")
   result = subprocess.run(command, capture_output=True, text=True)
   print("```sh\n" + shlex.join(command) + "\n```")
   print("\n```text\nexit:", result.returncode)
   print("--- stdout\n" + result.stdout, end="")
   print("\n--- stderr\n" + result.stderr, end="")
   print("\n```")
   PY
   ```

3. Scrub private or volatile values before posting (the helper scrubs
   `--scrub-env` values, the working directory, `$HOME` and token shapes and
   writes the notes). The output block begins
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
   For a changed fail-closed tool, run the shipped entry point (script,
   wrapper or CLI command) with an accepted and a rejected input; the
   rejected pair shows a nonzero `exit:`
   ([claim scope](../../docs/verification.md#claim-scope)).
   Apply the [size limits](../../docs/verification.md#q3-size-limits): truncate
   long output with an omission note and CI-log link or a re-run label.

## Negative control

A new or changed guard (a test, sweep, pattern or check meant to fail on a
bad state) gets a fail-then-pass pair
([protocol §3](../../docs/protocol.md#3-evidence-requirements)):

1. **N1, mutated.** In a throwaway copy of the head, undo or mutate the line
   the guard protects, or feed it the nearest wrong input, then run the guard.
   Put the copy and the mutation in a `--setup` file so the `sh` block
   recreates them, and make the mutation fail loudly if it changes nothing:

   ```sh
   # n1-setup.sh
   tmp=$(mktemp -d) && git archive HEAD | tar -x -C "$tmp" && cd "$tmp" &&
   python3 -c 'import pathlib; p = pathlib.Path("scripts/x.py"); s = p.read_text(); assert s.count("GOOD") == 1; p.write_text(s.replace("GOOD", "BAD"))'
   ```

   ```sh
   python3 <mdstack>/scripts/evidence-cli.py --label N1 --setup n1-setup.sh -- <guard argv...>
   ```

   The `text` block shows the guard failing: a nonzero `exit:` and the
   failure line naming the bad state.
2. **N2, restored.** Run the same guard argv at the clean head with
   `--label N2`; it exits 0.

Label the pair `shape: negative control, N1/N2` and name the guard and the
mutation in one line above it. The verifier replays both blocks. A mutated
run that passes, or a mutation that misses the guarded line, is `disagrees`.

## Verifier: re-run and compare

1. Check out the current head. Read the pair in the body or signed builder
   review; a review's marker SHA must be head or an earlier change commit.
2. A CLI, service or API capture with no `Proof R1 · ... · sha ... ·
   cwd ...` header line is one finding. Copy and run the `sh` block, using its
   setup and working directory; prefer re-running it with
   `scripts/evidence-cli.py` so your output is in the same shape. Compare
   exit code, stdout and stderr to the expected `text` block, ignoring only
   named scrubbed or volatile fields. For truncated proof, compare retained
   lines (excluding the omission note) and verify the claim from the full run.
3. Record your own command/output excerpt inline: `agrees` if it shows the
   claim at head, `disagrees` if it differs without justification or fails the
   claim, `unverified` if it cannot run (say why). Missing required proof is
   `disagrees`; earlier proof is accepted only when it still holds at head.
