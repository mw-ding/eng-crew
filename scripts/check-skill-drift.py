#!/usr/bin/env python3
"""Drift check between the reviewed docs and the box skill copies (spec R4).

Not a byte comparison: the skill copies carry frontmatter and box-specific
wording. Each section is normalized (links, backticks, whitespace) and reported
as OK (identical), WORDING (text differs but the key facts are the same: code
spans such as labels, markers, event names and flags, plus numbers) or DRIFT
(key facts differ). Only DRIFT, MISSING and EXTRA fail the check.

  docs/protocol.md  <->  eng-pr-pipeline SKILL.md   (per section)
  docs/roles.md     <->  eng-crew-roles SKILL.md    (key facts, whole file,
                                                      since headings differ)

Python 3 standard library only, no network. Run by the coordinator on
`crew:needs-mirror` and after any PR that touches docs/protocol.md or
templates/ (see scripts/README.md). Not run in CI: CI has no box skills.

Usage: check-skill-drift.py --pipeline-skill PATH --roles-skill PATH
           [--root DIR] [--only pipeline|roles] [--ignore-heading TEXT]...
           [--verbose]

The skill paths may also come from ECREW_PIPELINE_SKILL / ECREW_ROLES_SKILL.
Exit 0: every compared section matches. Exit 1: drift. Exit 2: usage error or
a missing/unreadable file (never a silent pass).
"""
import argparse
import difflib
import hashlib
import os
import re
import sys

HEADING = re.compile(r"^(#{2,3})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
COMMENT = re.compile(r"<!--.*?-->", re.S)

# Repo-only sections never expected in the box copies.
DEFAULT_IGNORED = {"worked example / pilot notes"}


def norm_heading(text):
    text = re.sub(r"[`*_]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def norm_body(lines):
    text = "\n".join(lines)
    text = COMMENT.sub("", text)
    text = "\n".join(re.sub(r"^\s*>\s?", "", ln) for ln in text.split("\n"))
    text = LINK.sub(r"\1", text)
    text = re.sub(r"[`*]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_frontmatter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1:]
    return lines


def sections(path):
    """Return ordered {key: (heading, normalized body)} for ## and ### sections."""
    with open(path, encoding="utf-8") as fh:
        lines = strip_frontmatter(fh.read().splitlines())
    out, order = {}, []
    cur, body, fence = None, [], None

    def flush():
        if cur is not None:
            key, head = cur
            n, k = 1, key
            while k in out:
                n += 1
                k = "%s #%d" % (key, n)
            out[k] = (head, norm_body(body), key_tokens(body))
            order.append(k)

    for ln in lines:
        m = FENCE.match(ln)
        if m:
            tok = m.group(1)
            if fence is None:
                fence = tok[0]
            elif tok[0] == fence:
                fence = None
        h = None if fence or m else HEADING.match(ln)
        if h:
            flush()
            cur, body = (norm_heading(h.group(2)), h.group(2).strip()), []
            continue
        body.append(ln)
    flush()
    return out, order


SPAN = re.compile(r"`([^`\n]{1,40})`")
PLACEHOLDER = re.compile(r"<[^<>\n]*>")
IDENT = re.compile(r"^-{0,2}[a-z][a-z0-9_.:=/-]{2,}$")
QUANT = re.compile(r"(?<![\w.<-])(\d+(?:\.\d+)?)[ -]?(min|h|hours?|rounds?|chars?|s|%)(?![a-z])")


def key_tokens(raw_lines):
    """Facts that must survive mirroring: single-word code spans (labels,
    markers like pass=watch, event names, flags, commands) and quantities
    (thresholds such as 3 rounds, 40-char, 30 min)."""
    text = COMMENT.sub("", "\n".join(raw_lines))
    text = PLACEHOLDER.sub("", text)
    toks = set()
    for s in SPAN.findall(text):
        s = s.strip().lower()
        if IDENT.match(s):
            toks.add("`" + s + "`")
    for n, unit in QUANT.findall(SPAN.sub("", text).lower()):
        toks.add(n + " " + unit.rstrip("s") if unit != "s" else n + " s")
    return toks


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def first_diff(a, b):
    wa, wb = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            lo = max(i1 - 4, 0)
            ctx = " ".join(wa[lo:i1])
            return ("repo: ...%s [%s]" % (ctx, " ".join(wa[i1:i2][:12])),
                    "skill: ...%s [%s]" % (ctx, " ".join(wb[j1:j2][:12])))
    return "", ""


def fmt(toks):
    return ", ".join(sorted(toks)[:12]) + (" ..." if len(toks) > 12 else "")


def compare(label, repo_path, skill_path, ignored, verbose, whole):
    repo, repo_order = sections(repo_path)
    skill, skill_order = sections(skill_path)
    print("== %s: %s <-> %s (%s)" % (label, os.path.basename(repo_path),
          os.path.basename(os.path.dirname(skill_path)) or "skill",
          "whole-file key facts" if whole else "per section"))
    if whole:
        rt = set().union(*(repo[k][2] for k in repo_order if k not in ignored))
        st = set().union(*(skill[k][2] for k in skill_order))
        drift = 0
        for name, only, where in (("MISSING", rt - st, "in repo, not in skill"),
                                  ("EXTRA", st - rt, "in skill, not in repo")):
            if only:
                drift += len(only)
                print("  %-8s %d key fact(s) %s: %s" % (name, len(only), where, fmt(only)))
        print("  %s: %s" % (label, "no drift" if not drift else "%d key fact(s) differ" % drift))
        return 1 if drift else 0
    drift = 0
    for key in repo_order:
        head = repo[key][0]
        if key in ignored:
            print("  SKIP     %s (repo-only)" % head)
        elif key not in skill:
            drift += 1
            print("  MISSING  %s (in repo, not in skill)" % head)
        elif repo[key][1] == skill[key][1]:
            print("  OK       %s [%s]" % (head, digest(repo[key][1])))
        elif repo[key][2] == skill[key][2]:
            print("  WORDING  %s (same key facts, text differs)" % head)
            if verbose:
                for line in first_diff(repo[key][1], skill[key][1]):
                    print("             " + line)
        else:
            drift += 1
            print("  DRIFT    %s" % head)
            for name, only in (("repo only", repo[key][2] - skill[key][2]),
                               ("skill only", skill[key][2] - repo[key][2])):
                if only:
                    print("             %s: %s" % (name, fmt(only)))
    for key in skill_order:
        if key not in repo and key not in ignored:
            drift += 1
            print("  EXTRA    %s (in skill, not in repo)" % skill[key][0])
    print("  %s: %s" % (label, "no drift" if not drift else "%d section(s) drifted" % drift))
    return 1 if drift else 0


def die(msg):
    print("error: " + msg, file=sys.stderr)
    sys.exit(2)


def need_file(path, what):
    if not path:
        die("no path for %s (pass the flag or set the env var)" % what)
    if not os.path.isfile(path):
        die("%s not found: %s" % (what, path))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--pipeline-skill", default=os.environ.get("ECREW_PIPELINE_SKILL"),
                    help="<skill-dir>/eng-pr-pipeline/SKILL.md")
    ap.add_argument("--roles-skill", default=os.environ.get("ECREW_ROLES_SKILL"),
                    help="<skill-dir>/eng-crew-roles/SKILL.md")
    ap.add_argument("--protocol", help="override docs/protocol.md (tests)")
    ap.add_argument("--roles", help="override docs/roles.md (tests)")
    ap.add_argument("--only", choices=["pipeline", "roles"])
    ap.add_argument("--ignore-heading", action="append", default=[],
                    help="extra repo-only heading to skip (repeatable)")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="show the first differing words of each DIFF section")
    args = ap.parse_args()

    ignored = DEFAULT_IGNORED | {norm_heading(h) for h in args.ignore_heading}
    protocol = args.protocol or os.path.join(args.root, "docs", "protocol.md")
    roles = args.roles or os.path.join(args.root, "docs", "roles.md")
    # (label, repo doc, repo name, skill path, skill name, whole-file compare)
    pairs = []
    if args.only in (None, "pipeline"):
        pairs.append(("protocol", protocol, "protocol doc", args.pipeline_skill,
                      "eng-pr-pipeline skill", False))
    if args.only in (None, "roles"):
        # The roles skill is organised differently (lead playbook), so its
        # headings do not line up with roles.md; compare key facts file-wide.
        pairs.append(("roles", roles, "roles doc", args.roles_skill,
                      "eng-crew-roles skill", True))
    for _, repo_path, rname, skill_path, sname, _ in pairs:
        need_file(repo_path, rname)
        need_file(skill_path, sname)

    drift = sum(compare(label, r, s, ignored, args.verbose, whole)
                for label, r, _, s, _, whole in pairs)
    print("DRIFT: %d comparison(s) drifted" % drift if drift else "OK: no drift")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
