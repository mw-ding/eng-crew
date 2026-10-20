# Scripts

Repo guard for the spec's hard requirements (R1 no secrets, R6 CI green).
Python 3 standard library only; no network, no dependencies.

| File | Purpose |
|---|---|
| `check-repo.py` | The guard: secret scan, required docs/sections, relative links |
| `required-docs.txt` | Single config of required files and sections |
| `test-check-repo.py` | Tests: one bad fixture per pattern, a good fixture, structural cases |
| `fixtures/bad/`, `fixtures/good/` | Synthetic scan samples (see below) |

## Run it

From the repo root:

```sh
python3 scripts/check-repo.py            # all checks
python3 scripts/check-repo.py --only secrets   # or docs / links (repeatable)
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
| `broken-link` | a relative markdown link (or image) whose target file does not exist, or that points outside the repo |

All files under the repo root are scanned for secrets (except `.git/` and
`node_modules/`; binary files are skipped). Links are checked in `*.md` files,
skipping code fences and inline code; `http(s):`, `mailto:` and
fragment-only links are ignored. Fragment (`#anchor`) checks stay with the
`links` CI job (lychee). Git history is not scanned.

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
`path :: ## Heading` requires that exact heading line (outside code fences).
Blank lines and lines starting with `#` are ignored. Add entries in the same PR
that lands the doc.

## Fixtures

`fixtures/bad/*.txt` holds one fake sample per rule, always on line 3, with the
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
