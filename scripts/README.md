# Scripts

Repo guard for the spec's hard requirements (R1 no secrets, R6 CI green).
Python 3 standard library only; no dependencies. The guard needs no network;
`metrics-refresh.py` calls the `gh` CLI (read-only).

| File | Purpose |
|---|---|
| `check-repo.py` | The guard: secret scan, required docs/sections, relative links, crew marker SHAs |
| `required-docs.txt` | Single config of required files and sections |
| `test-check-repo.py` | Tests: bad fixtures per pattern, a good fixture, fence/link/section/file-selection cases |
| `metrics-refresh.py` | Refreshes the crew PR metrics artifact in `docs/metrics/` via the `gh` CLI (see [../docs/metrics/README.md](../docs/metrics/README.md)); not run in CI |
| `test-metrics-refresh.py` | Offline self-test for the metrics parsing logic |
| `fixtures/bad/`, `fixtures/good/` | Synthetic scan samples (see below) |

## Run it

From the repo root:

```sh
python3 scripts/check-repo.py            # all checks
python3 scripts/check-repo.py --only secrets   # or docs / links / markers (repeatable)
python3 scripts/test-check-repo.py       # fixture and structural tests
```

Every problem prints as `file:line: [rule] reason`; the exit code is 1 if there
is any problem, 0 otherwise. CI runs both commands in the `repo-guard` job
(`.github/workflows/ci.yml`) on every pull request and push to `main`.

## What it checks

| Rule | Fails on |
|---|---|
| `github-token` | GitHub tokens with the `ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_` prefixes |
| `github-pat` | fine-grained tokens with the `github_pat_` prefix |
| `sk-key` | `sk-` style API keys (20+ key characters) |
| `aws-access-key` | AWS access key ids (`AKIA`, `ASIA`, and related prefixes) |
| `private-key` | `-----BEGIN ... PRIVATE KEY-----` blocks |
| `bearer-header` | an `Authorization` header with a literal bearer value |
| `url-credentials` | URLs with a literal `user:password@` part |
| `missing-file`, `missing-section` | an entry in `required-docs.txt` that is absent |
| `marker-sha` | a `crew:v1` marker (also wrapped over lines, also inside fences) in `*.md` whose `sha=` is a literal that is not 40 hex characters, or a placeholder naming a short SHA (`sha7`, `short`). Placeholders like `<head-sha>` and `<40-char head sha>` pass. Encodes the lesson in `docs/lessons/2026-10-23-watch-handoff-first-run.md` (issue #69) |
| `broken-link` | a relative markdown link (or image) whose target file does not exist, or that points outside the repo |

Every file is scanned for secrets (binary files are skipped). In a git work
tree (the repo root is the top level) the file list is `git ls-files`, so
everything tracked is scanned, including a tracked `node_modules/`, and an
untracked or ignored directory such as a local `node_modules/` is not; `git add`
a new file for local runs to see it (CI only has tracked files anyway). Outside
a git work tree (or if `git` fails) every file except `.git/` is scanned.

Token patterns use alnum-only boundaries, not `\b`, so a token wrapped in `_`
(Markdown emphasis, such as `_ghp_<36 chars>_`) is still caught. Git history is
not scanned.

Links are checked in `*.md` files; `http(s):`, `mailto:` and fragment-only
links are ignored. Fragment (`#anchor`) checks stay with the `links` CI job
(lychee). Destinations are URL-decoded (`other%20file.md`) and may contain
balanced parentheses (`other(v1).md`) or be written as `<other file.md>`.

Code fences follow CommonMark. A fence opens with 3+ backticks or tildes (up to
3 spaces of indent), also after list markers (`-`, `*`, `+`, `1.`, `1)`, nested
to any depth) and block-quote `>` prefixes, and closes only on a fence of the
same character, at least as long as the opener, with nothing but whitespace
after it (inside a list item or quote the closer may be indented as far as the
content). Fenced lines are skipped by the link check, and a heading inside a
fence never satisfies a required section.

Safety rule for stray fences: CommonMark runs an unclosed fence to the end of
the file, which would let one unrecognised opener (or a lone closer of a fence
the scanner did not see) hide every later link. So for the link check an
unclosed opener is treated as plain text: nothing after it is skipped. The
section check stays strict and fails closed instead: a heading after an
unclosed fence does not count, and the `missing-section` message names the
line of the unclosed fence. The only way a fence hides lines is therefore a
recognised opener with a matching closer, and a fence the scanner opens that
CommonMark would not (for example inside an indented code block) can hide only
the lines up to its closer.

Inline code spans are skipped: a backtick run closes at the next run of the
same length, a backslash-escaped backtick is literal, and an unmatched run is
literal (the text after it is still checked). HTML comments (`<!-- ... -->`,
also across lines; an unclosed one runs to the end of the file) never satisfy a
required heading; links inside comments are still checked.

Known limits:

- A link split across lines (`[x](` then the destination on the next line) and
  a reference definition whose destination is on the next line are not checked.
- Code spans are matched within one line; a span that wraps lines is not
  skipped, so a link inside it is checked (this can only add findings).
- A fence or comment marker inside an HTML comment is not understood: a lone
  fence line in a comment is read as a fence opener (an unclosed one is
  harmless for links but makes the section check fail closed).

## Allowlist: placeholder form only

There is no ignore comment and no path exclusion. A secret-looking value is
accepted only when written as a placeholder, a name in angle brackets:

- `ghp_<token>`, `sk-<key>` (the `<` stops the token pattern from matching)
- `Authorization: Bearer <token>`
- `https://<user>:<password>@host/path`

Anything else, including well-known documentation example keys, fails. Refer to
credentials by mechanism instead (see spec R1).

## Required docs

Edit `required-docs.txt`. One entry per line: `path` requires the file;
`path :: ## Heading` requires that exact heading line (outside code fences
and HTML comments, as defined above).
Blank lines and lines starting with `#` are ignored. Add entries in the same PR
that lands the doc.

## Fixtures

`fixtures/bad/*.txt` holds fake samples per rule (including `_`-wrapped
variants named `*-underscore.txt`), always on line 3, with the
rule id on the `# expect:` line. Each token is stored **defanged**: a `~~`
marker splits the string, so the repo never contains a matching (or
push-protection-triggering) value. `test-check-repo.py` strips the marker into a
temp directory and requires `check-repo.py` to fail with `<file>:3: [<rule>]`.
`fixtures/good/` holds the placeholder forms and must pass.

Because the fixtures are inert, the real scan does not exclude them, and
verifies it by scanning them as ordinary files. Fixtures are `.txt` so
markdownlint and lychee ignore them. Structural cases (missing file or section,
broken link) are built in temp directories by the test, not stored as `.md`.

To add a pattern: add it to `PATTERNS` in `check-repo.py`, add
`fixtures/bad/<name>.txt` with a defanged sample, and extend the table above.
