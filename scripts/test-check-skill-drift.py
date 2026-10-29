#!/usr/bin/env python3
"""Tests for check-skill-drift.py. Python 3 stdlib only; uses synthetic
fixtures under fixtures/drift/, so it runs in CI without any box skill files."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "check-skill-drift.py")
FIX = os.path.join(HERE, "fixtures", "drift")
DOC = os.path.join(FIX, "doc.txt")
failed = []


def run(*args, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("ECREW_")}
    e.update(env or {})
    p = subprocess.run([sys.executable, CHECK, "--protocol", DOC, *args],
                       capture_output=True, text=True, env=e)
    return p.returncode, p.stdout + p.stderr


def case(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        failed.append(name)


m = os.path.join(FIX, "skill-match.txt")
d = os.path.join(FIX, "skill-drift.txt")

rc, out = run("--only", "pipeline", "--pipeline-skill", m)
case("matching copy passes (wording and frontmatter differences allowed)",
     rc == 0 and "WORDING  2. Labels" in out and "no drift" in out)
case("repo-only section is skipped, not failed", "SKIP     Worked example" in out)

rc, out = run("--only", "pipeline", "--pipeline-skill", d)
case("drifted copy exits 1", rc == 1)
case("changed key facts are named",
     "DRIFT    1. Gate" in out and "40 char" in out and "3 round" in out)
case("section missing from the skill is reported", "MISSING  2. Labels" in out)
case("section only in the skill is reported", "EXTRA    3. Extra" in out)

rc, out = run("--only", "pipeline", "--pipeline-skill", os.path.join(FIX, "nope.txt"))
case("missing skill file is an error (exit 2), not a pass",
     rc == 2 and "not found" in out)

rc, out = run("--only", "pipeline")
case("no skill path is an error (exit 2)", rc == 2 and "no path" in out)

rc, out = run("--only", "pipeline", env={"ECREW_PIPELINE_SKILL": m})
case("skill path from the environment", rc == 0)

rc, out = run("--only", "roles", "--roles", DOC, "--roles-skill", m)
case("roles pair compares key facts file-wide", rc == 0 and "whole-file" in out)
rc, out = run("--only", "roles", "--roles", DOC, "--roles-skill", d)
case("roles drift exits 1", rc == 1 and "MISSING" in out)

tmp = tempfile.mkdtemp(prefix="drift-test-")


def write(name, text, mode="w", **kw):
    path = os.path.join(tmp, name)
    with open(path, mode, **kw) as fh:
        fh.write(text)
    return path


# Regression: a code span over 40 chars must not break pairing of later spans.
long_span = "`" + "round=n/a verdict=n/a watch=b2 status=attached" + "`"
doc_l = write("long-doc.txt", "## A\n\n%s then `ci-fix` and `merge-up`.\n" % long_span)
sk_l = write("long-skill.txt", "## A\n\n%s then `ci-fix` and `merge-up`.\n" % long_span)
rc, out = run("--only", "pipeline", "--protocol", doc_l, "--pipeline-skill", sk_l)
case("long span ahead of short spans: no false drift", rc == 0 and "DRIFT" not in out)
sk_l2 = write("long-skill2.txt", "## A\n\n%s then `ci-fix`.\n" % long_span)
rc, out = run("--only", "pipeline", "--protocol", doc_l, "--pipeline-skill", sk_l2)
case("long span ahead of short spans: missing later span still reported",
     rc == 1 and "`merge-up`" in out)

# Regression: preamble (before the first heading) is compared for roles.
pre_a = write("pre-a.txt", "Intro uses `crew:needs-md`.\n\n## S\n\ntext `crew:x`\n")
pre_b = write("pre-b.txt", "Intro uses `crew:wrong`.\n\n## S\n\ntext `crew:x`\n")
rc, out = run("--only", "roles", "--roles", pre_a, "--roles-skill", pre_b)
case("changed fact in the preamble is drift", rc == 1 and "crew:needs-md" in out)
nh_a = write("nh-a.txt", "only `crew:alpha` here\n")
nh_b = write("nh-b.txt", "only `crew:beta` here\n")
rc, out = run("--only", "roles", "--roles", nh_a, "--roles-skill", nh_b)
case("heading-free files with different facts do not pass", rc == 1)
rc, out = run("--only", "roles", "--roles", nh_a, "--roles-skill", nh_a)
case("identical heading-free files pass", rc == 0)

# Quantities inside code spans count.
q3 = write("q3.txt", "## A\n\nReviews take ``3 rounds`` at most.\n")
q5 = write("q5.txt", "## A\n\nReviews take ``5 rounds`` at most.\n")
rc, out = run("--only", "pipeline", "--protocol", q3, "--pipeline-skill", q5)
case("quantity inside a code span is drift", rc == 1 and "3 round" in out)

def pair(a, b, only="pipeline"):
    """Run one section pair through the check; returns (rc, output)."""
    da = write("pa-%d.txt" % len(os.listdir(tmp)), "## A\n\n%s\n" % a)
    db = write("pb-%d.txt" % len(os.listdir(tmp)), "## A\n\n%s\n" % b)
    return run("--only", "pipeline", "--protocol", da, "--pipeline-skill", db)


# Regression: a placeholder-only span (<sha7>) must not unpair later spans.
line = "`<sha7>` then `pass=watch` and `ci-fix`"
rc, out = pair(line, "`<sha7>` then `ci-fix`")
case("placeholder span keeps later spans paired", rc == 1 and "`pass=watch`" in out
     and "`then`" not in out and "`and`" not in out)
rc, out = pair(line, line)
case("placeholder span identical sides pass", rc == 0)
rc, out = pair("run `x <sha7> y` now", "run `x y` now")
case("placeholder inside a longer span is stripped", rc == 0)

# Regression: link destinations are not quantities.
rc, out = pair("See [rounds](#5-rounds-and-escalation); max 3 rounds.",
               "See rounds; max 3 rounds.")
case("link fragment is not a quantity", rc == 0 and "5 round" not in out)
rc, out = pair("See [rounds][r]; max 3 rounds.\n\n[r]: #5-rounds-and-escalation",
               "See rounds; max 3 rounds.")
case("reference-style link definition is not a quantity", rc == 0)

# Unit variants compare equal; a changed value is drift.
rc, out = pair("a 40-character title", "a 40-char title")
case("40-character equals 40-char", rc == 0)
rc, out = pair("a 40-char title", "a 50 chars title")
case("changed char count is drift", rc == 1 and "40 char" in out and "50 char" in out)
rc, out = pair("wait 5 minutes", "wait 5 min")
case("5 minutes equals 5 min", rc == 0)
rc, out = pair("wait 5 minutes", "wait 10 minutes")
case("changed minutes is drift", rc == 1 and "5 min" in out and "10 min" in out)

# A code-span fact present unformatted on the other side is not reported.
rc, out = pair("Roles: `eng-backend` and `ci-fix`.", "Roles: **eng-backend** and `ci-fix`.")
case("code span vs bold of the same word is not drift", rc == 0)
rc, out = pair("Roles: `eng-backend` and `ci-fix`.", "Roles: `ci-fix`.")
case("really absent fact is reported as not found", rc == 1 and "not found in skill" in out
     and "`eng-backend`" in out)

# Historical percentages in the default-ignored quota example are not facts.
ex_a = write("ex-a.txt", "## Q\n\nskip under 15%.\n\n### Example: a quota steer on the reviewer side\n\nwas at 38% and 99%.\n")
ex_b = write("ex-b.txt", "## Q\n\nskip under 15%.\n")
rc, out = run("--only", "roles", "--roles", ex_a, "--roles-skill", ex_b)
case("quota example percentages are not thresholds", rc == 0)

# Unreadable input is exit 2 with a message, never a traceback.
bad = write("bad-utf8.txt", b"## A\n\xff\xfe\x80 bytes\n", mode="wb")
rc, out = run("--only", "pipeline", "--pipeline-skill", bad)
case("non-UTF-8 file is exit 2", rc == 2 and "cannot read" in out and "Traceback" not in out)
rc, out = run("--only", "pipeline", "--protocol", bad, "--pipeline-skill", m)
case("non-UTF-8 repo doc is exit 2", rc == 2 and "cannot read" in out)
noperm = write("noperm.txt", "## A\n")
os.chmod(noperm, 0)
if os.access(noperm, os.R_OK):
    print("skip unreadable-file test (running as a user that bypasses permissions)")
else:
    rc, out = run("--only", "pipeline", "--pipeline-skill", noperm)
    case("unreadable file is exit 2", rc == 2 and "cannot read" in out and "Traceback" not in out)
shutil.rmtree(tmp, ignore_errors=True)

if failed:
    print("\n%d failed: %s" % (len(failed), ", ".join(failed)))
    sys.exit(1)
print("\nall passed")
