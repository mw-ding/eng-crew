"""Path glob matching shared by the repo guard (`scripts/check-repo.py`,
deliverables manifest) and `core/crew-config.py` (sensitive, class, spec
path and precheck rules), so both read a glob the same way (#281).
Python 3 stdlib only.
"""
import re


def glob_regex(glob):
    """`**` matches across `/`; `*` and `?` stay inside one path segment."""
    parts = re.split(r"(\*\*|\*|\?)", glob)
    tr = {"**": ".*", "*": "[^/]*", "?": "[^/]"}
    return re.compile("".join(tr.get(p, re.escape(p)) for p in parts) + r"\Z")
