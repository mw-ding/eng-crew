#!/usr/bin/env python3
"""Core memory (#1230, docs/memory.md): the owner profile and per-role core memory curated in git under memory/.

Usage: crew-memory.py [--root DIR]
Lints DIR/memory/ (default: the current directory's): only memory/owner.md and memory/roles/<role>.md for a
registered role; each file within its size limit; no personal data, which belongs in the knowledge connector.
Prints `file:line: [rule] reason` per problem; exit 1 if any, else 0. Python 3.11+ stdlib only.
The renderer appends section() to each role's rendered brief, from one snapshot() per render: both files at the
tip of the checkout's remote default branch (#1537). It fails closed on the same problems and on a snapshot failure.
"""
import argparse
import importlib.util
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("crew_config", os.path.join(HERE, "crew-config.py"))
crew_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crew_config)

OWNER = "memory/owner.md"
ROLE = "memory/roles/%s.md"
GIT_TIMEOUT = 120  # seconds per git call; ls-remote and fetch reach the remote
LIMITS = {"owner": 3000, "role": 2000}  # bytes: a small curated core, read at every start
ROUTE = "keep it in the knowledge connector, not core memory (docs/memory.md#personal-data)"
# (kind, regex). Placeholders such as <user>@<domain> never match: `<` is outside every class.
PERSONAL = [
    ("email address", re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")),
    ("phone number", re.compile(r"(?<![\w-])(?:\+\d{1,3}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?![\w-])")),
    ("street address", re.compile(r"\b\d+ (?:[A-Z][a-z]+ )+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln"
                                  r"|Drive|Dr|Way|Court|Ct|Place|Pl)\b")),
    ("personal detail", re.compile(r"\b(?:birthday|date of birth|home address|phone number|social security"
                                   r"|passport|salary|medical|diagnosis|spouse|wife|husband)\b", re.I)),
]


def files(root):
    """Every file under root/memory/, as repo-relative paths, sorted."""
    found = []
    for parent, _, names in os.walk(os.path.join(root, "memory")):
        found += [os.path.relpath(os.path.join(parent, n), root).replace(os.sep, "/") for n in names]
    return sorted(found)


def check(root, rel):
    """(text or None, problems) for one memory file: its size limit and personal data. A problem is
    (path, line, rule, reason); a missing file is (None, [])."""
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return None, []
    except (OSError, UnicodeError) as e:
        return None, [(rel, 1, "memory-read", "cannot read (%s)" % e)]
    return text, check_text(rel, text)


def check_text(rel, text):
    """Problems in one memory file's text: its size limit and personal data."""
    limit = LIMITS["owner" if rel == OWNER else "role"]
    size = len(text.encode("utf-8"))
    problems = [(rel, 1, "memory-size", "%d bytes, over the %d-byte limit; curate it down" % (size, limit))] \
        if size > limit else []
    for n, line in enumerate(text.splitlines(), 1):
        problems += [(rel, n, "memory-personal", "%s: %s" % (kind, ROUTE)) for kind, rx in PERSONAL if rx.search(line)]
    return problems


def lint(root):
    """Problems across root/memory/: layout, then each file's checks."""
    allowed = {OWNER} | {ROLE % r for r in crew_config.ROLE_REGISTRY}
    problems = []
    for rel in files(root):
        if rel not in allowed:
            problems.append((rel, 1, "memory-layout", "core memory is memory/owner.md and memory/roles/<role>.md for a "
                             "registered role (%s)" % ", ".join(crew_config.ROLE_REGISTRY)))
            continue
        problems += check(root, rel)[1]
    return problems


def git(root, *args):
    """One git command in root, never prompting for credentials; raises OSError or TimeoutExpired."""
    return subprocess.run(["git", "-C", root, *args], capture_output=True, timeout=GIT_TIMEOUT,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})


def snapshot(root, branch, remote="origin"):
    """(texts, source, problems): the core memory a render injects (#1537), read at the tip of the checkout's
    remote default branch, never from the local tree. texts maps OWNER and each registered role file present at
    that revision to its text; source is "<remote>/<branch>@<sha>", None without a revision. A root outside git or
    without the remote yields nothing when it has no memory/; every other failure is a problem, so the render
    refuses."""
    try:
        where = git(root, "rev-parse", "--show-prefix")
        if where.returncode or git(root, "config", "--get", "remote.%s.url" % remote).returncode:
            return {}, None, [("memory", 1, "memory-source", "no %s remote: core memory is read at the remote "
                               "default branch, never from local files" % remote)] \
                if os.path.isdir(os.path.join(root, "memory")) else []
        prefix, ref = where.stdout.decode().strip(), "refs/heads/" + branch
        tip = git(root, "ls-remote", "--exit-code", remote, ref)
        if tip.returncode:
            return {}, None, [("memory", 1, "memory-source", "cannot resolve %s/%s: %s; refusing stale or local "
                               "memory" % (remote, branch, tip.stderr.decode().strip() or "no such branch"))]
        sha = tip.stdout.split()[0].decode()
        if git(root, "cat-file", "-e", sha + "^{commit}").returncode:
            fetched = git(root, "fetch", "--quiet", "--no-tags", "--no-write-fetch-head", remote, ref)
            if fetched.returncode or git(root, "cat-file", "-e", sha + "^{commit}").returncode:
                return {}, None, [("memory", 1, "memory-source", "cannot fetch %s/%s at %s: %s" % (
                    remote, branch, sha, fetched.stderr.decode().strip() or "commit missing after fetch"))]
        listing = git(root, "ls-tree", "-r", "--full-tree", "--name-only", sha, "--", prefix + "memory/")
        if listing.returncode:
            return {}, None, [("memory", 1, "memory-source", "cannot list memory/ at %s" % sha)]
        present, texts, problems = set(listing.stdout.decode().splitlines()), {}, []
        for rel in [OWNER] + [ROLE % r for r in crew_config.ROLE_REGISTRY]:
            if prefix + rel in present:
                blob = git(root, "cat-file", "blob", "%s:%s%s" % (sha, prefix, rel))
                try:
                    if blob.returncode:
                        raise ValueError(blob.stderr.decode().strip())
                    texts[rel] = blob.stdout.decode("utf-8")
                except ValueError as e:  # UnicodeDecodeError included
                    problems.append((rel, 1, "memory-read", "cannot read at %s (%s)" % (sha, e)))
        return texts, "%s/%s@%s" % (remote, branch, sha), problems
    except (OSError, subprocess.TimeoutExpired) as e:
        return {}, None, [("memory", 1, "memory-source", "git failed (%s); refusing stale or local memory" % e)]


def section(texts, role):
    """(markdown, problems): the owner profile and the role's core memory from texts (snapshot()'s), as one brief
    section, or "" when neither file exists. Problems in either file make the caller fail closed."""
    parts, problems = [], []
    for rel in (OWNER, ROLE % role):
        text = texts.get(rel)
        if text is not None:
            problems += check_text(rel, text)
            parts.append("\n### %s\n\n%s" % (rel, text))
    if not parts:
        return "", problems
    return ("\n## Core memory\n\nThe owner profile and this role's core memory, curated in git under `memory/`. "
            "Change them only through a reviewed memory PR.\n" + "".join(parts)), problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repo root holding memory/ (default: .)")
    args = ap.parse_args(argv)
    problems = lint(os.path.abspath(args.root))
    for p in problems:
        print("%s:%d: [%s] %s" % p)
    if problems:
        print("crew-memory: FAILED (%d problem%s)" % (len(problems), "" if len(problems) == 1 else "s"),
              file=sys.stderr)
        return 1
    print("crew-memory: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
