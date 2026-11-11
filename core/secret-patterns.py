"""Secret-scan patterns shared by the repo guard (`scripts/check-repo.py`,
`secrets` check) and profile validation (`core/crew-config.py`), so the
installed bundle detects the same secrets without shipping the guard (#281).

PATTERNS lists (rule id, regex, reason); BEARER and URL_CRED match credential
forms whose captured value fails only when it is not a documented
`<placeholder>` (is_placeholder). Python 3 stdlib only.
"""
import re

PLACEHOLDER = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*>")  # documented allowlist form

# (rule id, regex, reason). A match is a failure unless the rule has a
# placeholder check below. Placeholders such as `ghp_<token>` never match the
# token regexes because `<` is outside their character classes.
# Boundaries are alnum-only lookarounds, not `\b`: `\b` treats `_` as a word
# character, so Markdown emphasis like `_ghp_<token>_` would slip through.
PATTERNS = [
    ("github-token", re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}"),
     "GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)"),
    ("github-pat", re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
     "GitHub fine-grained token (github_pat_)"),
    ("sk-key", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
     "sk- style API key"),
    ("aws-access-key", re.compile(r"(?<![A-Za-z0-9])(?:AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA)[A-Z0-9]{16}(?![A-Za-z0-9])"),
     "AWS access key id"),
    ("private-key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
     "private key block"),
]
BEARER = re.compile(r"""authorization["']?\s*[:=]\s*["']?bearer\s+([^\s"']+)""", re.I)
URL_CRED = re.compile(r"""(?<![A-Za-z0-9])[a-z][a-z0-9+.-]*://([^/\s:@"'<>]+|<[^>\s]+>):([^/\s@"']+)@""", re.I)


def is_placeholder(value):
    return PLACEHOLDER.match(value) is not None and PLACEHOLDER.sub("", value, 1).strip(".,;:)`\"'") == ""
