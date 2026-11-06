#!/usr/bin/env python3
"""Drift check between the reviewed docs and the box skill copies (spec R4).

Not a byte comparison: the skill copies carry frontmatter and box-specific
wording. Each section is normalized (links, backticks, whitespace) and reported
as OK (identical), WORDING (text differs but the key facts are the same: code
spans such as labels, markers, event names and flags, plus numbers, also
inside code spans) or DRIFT
(key facts differ; a code-span fact still counts as present when the other
side has the same word unformatted, e.g. in bold). Only DRIFT, MISSING and EXTRA fail the check.

  docs/protocol.md  <->  eng-pr-pipeline SKILL.md   (per section)
  docs/roles.md     <->  eng-crew-roles SKILL.md    (key facts, whole file
                                                      incl. preamble, since
                                                      headings differ)

Python 3 standard library only, no network. Run by the coordinator on
`crew:needs-mirror` and after any PR that touches docs/protocol.md or
templates/ (see scripts/README.md). Not run in CI: CI has no box skills.

Usage: check-skill-drift.py --pipeline-skill PATH --roles-skill PATH
           [--root DIR] [--only pipeline|roles] [--ignore-heading TEXT]...
           [--verbose]
       check-skill-drift.py --project CREW_TOML [--org-profile PATH]
           [--live-dir DIR] [--verbose]

The skill paths may also come from ECREW_PIPELINE_SKILL / ECREW_ROLES_SKILL.
Render-vs-live mode (--project, #128): render the profile with crew-render.py
and compare every rendered file with the same path under the live copy dir
(--live-dir, ECREW_LIVE_DIR, else the profile's paths.live_dir), per section.
A rendered file missing from the live copy is exit 2; a live file the render
does not produce is EXTRA (drift). This mode has no WORDING tolerance: the
deploy must equal the render, so any section text difference (a code span,
a comment, appended text) is DRIFT, shown with its first differing words.
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
# The quota example holds historical percentages (38 %, 99 %), not thresholds.
DEFAULT_IGNORED = {"worked example / pilot notes",
                   "example: a quota steer on the reviewer side"}


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


def fact_text(lines):
    """Text that can vouch for a code-span fact in missing_facts(): the
    normalized body without reference definitions, inline link destinations or
    reference labels, so a changed fact cannot hide in a URL or #fragment."""
    text = LINK_DEF.sub("", COMMENT.sub("", "\n".join(lines)))
    text = REF_LABEL.sub("]", LINK_DEST.sub("]", text))
    return norm_body(text.split("\n"))


def strip_frontmatter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1:]
    return lines


def sections(path, preamble=False):
    """Return ordered {key: (heading, normalized body)} for ## and ### sections.
    With preamble=True the text before the first heading is its own section."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = strip_frontmatter(fh.read().splitlines())
    except (OSError, UnicodeDecodeError) as e:
        die("cannot read %s: %s" % (path, e))
    out, order = {}, []
    cur, body, fence = (("(preamble)",) * 2 if preamble else None), [], None

    def flush():
        if cur is not None:
            key, head = cur
            n, k = 1, key
            while k in out:
                n += 1
                k = "%s #%d" % (key, n)
            out[k] = (head, norm_body(body), key_tokens(body), fact_text(body),
                      "\n".join(ln.rstrip() for ln in body).strip())
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


SPAN = re.compile(r"`([^`\n]+)`")
SPAN_MAX = 40
PLACEHOLDER = re.compile(r"<[^<>\n]*>")
LINK_DEST = re.compile(r"\]\([^)\n]*\)")
LINK_DEF = re.compile(r"^[ ]{0,3}\[[^\]\n]+\]:[ ]*\S+.*$", re.M)
REF_LABEL = re.compile(r"\]\[[^\]\n]*\]")
IDENT = re.compile(r"^-{0,2}[a-z][a-z0-9_.:=/-]{2,}$")
QUANT = re.compile(r"(?<![\w.<-])(\d+(?:\.\d+)?)[ -]?"
                   r"(min(?:ute)?s?|h|hours?|rounds?|char(?:acter)?s?|s|%)(?![a-z])")
UNIT_STEMS = (("min", "min"), ("hour", "h"), ("round", "round"), ("char", "char"))


def unit_name(unit):
    for stem, name in UNIT_STEMS:
        if unit.startswith(stem):
            return name
    return unit  # h, s, %


def key_tokens(raw_lines):
    """Facts that must survive mirroring: single-word code spans (labels,
    markers like pass=watch, event names, flags, commands) and quantities
    (thresholds such as 3 rounds, 40-char, 30 min; min/minute and
    char/character spellings count as the same unit). Link destinations are
    dropped first so a #5-rounds-and-escalation fragment is not a quantity.
    Spans are extracted before placeholders such as <sha7> are stripped from
    inside them, so a placeholder-only span cannot unpair later spans."""
    text = COMMENT.sub("", "\n".join(raw_lines))
    text = LINK_DEF.sub("", LINK_DEST.sub("]", text))
    toks = set()
    for s in SPAN.findall(text):
        s = PLACEHOLDER.sub("", s).strip().lower()
        if len(s) <= SPAN_MAX and IDENT.match(s):
            toks.add("`" + s + "`")
    text = PLACEHOLDER.sub(" ", text)
    for n, unit in QUANT.findall(text.lower()):
        toks.add(n + " " + unit_name(unit))
    return toks


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def first_diff(a, b, names=("repo", "skill")):
    wa, wb = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            lo = max(i1 - 4, 0)
            ctx = " ".join(wa[lo:i1])
            return ("%s: ...%s [%s]" % (names[0], ctx, " ".join(wa[i1:i2][:12])),
                    "%s: ...%s [%s]" % (names[1], ctx, " ".join(wb[j1:j2][:12])))
    return "", ""


def missing_facts(toks, other_toks, other_body):
    """Facts in toks that the other side lacks. A code-span fact still counts as
    present when the other side has the same word unformatted (bold, plain
    text), so only text that is really absent is reported. other_body is the
    fact_text() of the other side: link destinations and reference definitions
    are gone, so a URL or #fragment cannot stand in for a changed fact."""
    out = set()
    for t in toks - other_toks:
        word = t.strip("`")
        if t.startswith("`") and re.search(
                r"(?<![\w:=./-])%s(?![\w=/-])(?!\.\w)" % re.escape(word), other_body.lower()):
            continue
        out.add(t)
    return out


def fmt(toks):
    return ", ".join(sorted(toks)[:12]) + (" ..." if len(toks) > 12 else "")


def compare(label, repo_path, skill_path, ignored, verbose, whole, preamble=None, exact=False):
    """exact (render-vs-live): any raw section text difference is DRIFT."""
    preamble = whole if preamble is None else preamble
    repo, repo_order = sections(repo_path, preamble)
    skill, skill_order = sections(skill_path, preamble)
    print("== %s: %s <-> %s (%s)" % (label, os.path.basename(repo_path),
          os.path.basename(os.path.dirname(skill_path)) or "skill",
          "whole-file key facts" if whole else "per section"))
    if whole:
        rt = set().union(*(repo[k][2] for k in repo_order if k not in ignored))
        st = set().union(*(skill[k][2] for k in skill_order if k not in ignored))
        rbody = " ".join(repo[k][3] for k in repo_order if k not in ignored)
        sbody = " ".join(skill[k][3] for k in skill_order if k not in ignored)
        drift = 0
        for name, only, where in (
                ("MISSING", missing_facts(rt, st, sbody), "in repo, not found in skill text"),
                ("EXTRA", missing_facts(st, rt, rbody), "in skill, not found in repo text")):
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
        elif repo[key][1] == skill[key][1] and (not exact or repo[key][4] == skill[key][4]):
            print("  OK       %s [%s]" % (head, digest(repo[key][1])))
        elif not exact and not (missing_facts(repo[key][2], skill[key][2], skill[key][3])
                  or missing_facts(skill[key][2], repo[key][2], repo[key][3])):
            print("  WORDING  %s (same key facts, text differs)" % head)
            if verbose:
                for line in first_diff(repo[key][1], skill[key][1]):
                    print("             " + line)
        else:
            drift += 1
            print("  DRIFT    %s" % head)
            for name, only in (
                    ("not found in skill",
                     missing_facts(repo[key][2], skill[key][2], skill[key][3])),
                    ("not found in repo",
                     missing_facts(skill[key][2], repo[key][2], repo[key][3]))):
                if only:
                    print("             %s: %s" % (name, fmt(only)))
            if exact:
                for line in first_diff(repo[key][4], skill[key][4], ("render", "live")):
                    print("             " + line)
    for key in skill_order:
        if key not in repo and key not in ignored:
            drift += 1
            print("  EXTRA    %s (in skill, not in repo)" % skill[key][0])
    print("  %s: %s" % (label, "no drift" if not drift else "%d section(s) drifted" % drift))
    return 1 if drift else 0


def tree_files(root):
    return sorted(os.path.relpath(os.path.join(d, n), root) for d, _, ns in os.walk(root) for n in ns)


def render_live(args, ignored):
    """Render-vs-live mode (#128): render the profile with crew-render.py into
    a temp dir and compare each rendered file with the live copy per section
    (text before the first heading counts as a section). Returns the drift count."""
    import contextlib
    import importlib.util
    import io
    import shutil
    import tempfile
    spec = importlib.util.spec_from_file_location(
        "crew_render", os.path.join(os.path.dirname(os.path.abspath(__file__)), "crew-render.py"))
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    values, problems = cr.resolve(args.project, args.org_profile)
    if problems:
        print("\n".join(problems))
        die("cannot resolve profile %s" % args.project)
    live = args.live_dir or values.get("paths.live_dir")
    if not live or PLACEHOLDER.fullmatch(live):
        die("no live copy path (set paths.live_dir in the profile, pass --live-dir or set ECREW_LIVE_DIR)")
    if not os.path.isdir(live):
        die("live copy dir not found: %s" % live)
    tmp = tempfile.mkdtemp(prefix="drift-render-")
    try:
        argv = ["--project", args.project, "--out", tmp]
        argv += ["--org-profile", args.org_profile] if args.org_profile else []
        argv += ["--inputs", args.inputs] if args.inputs else []
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cr.main(argv)
        if code:
            print(out.getvalue(), end="")
            die("render failed for %s" % args.project)
        rendered, lived = tree_files(tmp), tree_files(live)
        missing = [rel for rel in rendered if rel not in lived]
        for rel in missing:
            print("  MISSING  %s (rendered, not in live copy)" % rel)
        if missing:
            die("%d rendered file(s) missing from the live copy %s" % (len(missing), live))
        drift = sum(compare(rel, os.path.join(tmp, rel), os.path.join(live, rel), ignored,
                            args.verbose, False, preamble=True, exact=True) for rel in rendered)
        for rel in lived:
            if rel not in rendered:
                drift += 1
                print("  EXTRA    %s (in live copy, not rendered)" % rel)
        return drift
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def die(msg):
    print("error: " + msg, file=sys.stderr)
    sys.exit(2)


def need_file(path, what):
    if not path:
        die("no path for %s (pass the flag or set the env var)" % what)
    if not os.path.isfile(path):
        die("%s not found: %s" % (what, path))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
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
    ap.add_argument("--project", help="render-vs-live mode: crew.toml to render (#128)")
    ap.add_argument("--org-profile", help="render-vs-live mode: org profile layer")
    ap.add_argument("--live-dir", default=os.environ.get("ECREW_LIVE_DIR"),
                    help="render-vs-live mode: live copy dir (default: profile paths.live_dir)")
    ap.add_argument("--inputs", help="render-vs-live mode: override the render inputs (tests)")
    args = ap.parse_args()

    ignored = DEFAULT_IGNORED | {norm_heading(h) for h in args.ignore_heading}
    if args.project:
        drift = render_live(args, ignored)
        print("DRIFT: %d comparison(s) drifted" % drift if drift else "OK: no drift")
        return 1 if drift else 0
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
