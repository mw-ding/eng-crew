#!/usr/bin/env python3
"""Tests for check-skill-drift.py. Python 3 stdlib only; uses synthetic
fixtures under fixtures/drift/, so it runs in CI without any box skill files.

Covers the drift check on synthetic fixtures (`fixtures/drift/`), and the
render-vs-live mode on `fixtures/render/` (match, wording, drift, missing and
extra live file, live-dir sources). Run in CI without any box files.
"""
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
# Wording differs so the pair reaches fact extraction (identical bodies never do).
rc, out = pair("See [rounds](#5-rounds-and-escalation); max 3 rounds.",
               "Read the rounds section; at most 3 rounds.")
case("link fragment is not a quantity", rc == 0 and "WORDING" in out
     and "5 round" not in out)
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
# Wording differs so the pair reaches fact extraction (identical bodies never do).
rc, out = pair("Roles: `eng-backend` and `ci-fix`.",
               "The roles are **eng-backend** plus `ci-fix`.")
case("code span vs bold of the same word is not drift", rc == 0 and "WORDING" in out)
rc, out = pair("Roles: `eng-backend` and `ci-fix`.", "Roles: `ci-fix`.")
case("really absent fact is reported as not found", rc == 1 and "not found in skill" in out
     and "`eng-backend`" in out)

# A changed fact cannot hide in a link destination or reference definition.
rc, out = pair("Use `ci-fix` here.", "Use **ci-break** here.\n\n[r]: #ci-fix")
case("fact only in a reference definition is still drift", rc == 1
     and "`ci-fix`" in out)
rc, out = pair("Use `ci-fix` here.", "Use **ci-break** [here](#ci-fix).")
case("fact only in an inline link destination is still drift", rc == 1
     and "`ci-fix`" in out)
rc, out = pair("Use `ci-fix` here.", "Use **ci-break** [here][ci-fix].\n\n[ci-fix]: #x")
case("fact only in a reference label is still drift", rc == 1 and "`ci-fix`" in out)
rc, out = pair("Use `ci-fix` here.", "Use **ci-fix** [here](#y).\n\n[r]: #z")
case("fact present in text next to links is not drift", rc == 0)

# Historical percentages in the default-ignored quota example are not facts.
ex_a = write("ex-a.txt", "## Q\n\nskip under 15%.\n\n### Example: a quota steer on the reviewer side\n\nwas at 38% and 99%.\n")
ex_b = write("ex-b.txt", "## Q\n\nskip under 15%.\n")
rc, out = run("--only", "roles", "--roles", ex_a, "--roles-skill", ex_b)
case("quota example percentages are not thresholds", rc == 0)

# Self-compare: ignore-heading strip applies on both sides (whole-file).
ex_same = write("ex-same.txt", "## Q\n\nskip under 15%.\n\n### Example: a quota steer on the reviewer side\n\nwas at 38% and 99% and `xhigh`.\n")
rc, out = run("--only", "roles", "--roles", ex_same, "--roles-skill", ex_same)
case("identical files with ignored quota example pass", rc == 0 and "EXTRA" not in out)

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

# Render-vs-live mode (#128): the render fixture's expected tree is a matching live copy.
RFIX = os.path.join(HERE, "fixtures", "render")
RPROJ = os.path.join(RFIX, "crew.toml")
RIN = ["--inputs", os.path.join(RFIX, "inputs")]


def live_copy(name, edit=None, drop=None, add=None):
    """Copy the expected render tree to tmp/name, then apply one change."""
    root = os.path.join(tmp, name)
    shutil.copytree(os.path.join(RFIX, "expected"), root)
    intake = os.path.join(root, "runtime", "builder-intake.md")
    if edit:
        with open(intake, encoding="utf-8") as fh:
            text = fh.read()
        with open(intake, "w", encoding="utf-8") as fh:
            fh.write(text.replace(*edit))
    if drop:
        os.remove(os.path.join(root, drop))
    if add:
        write(os.path.join(name, add), "## Old\n\nleft over\n")
    return root


rc, out = run("--project", RPROJ, *RIN, "--live-dir", live_copy("live-match"))
case("render vs live: matching live copy passes", rc == 0 and "OK: no drift" in out
     and "OK       (preamble)" in out and "runtime/builder-intake.md" in out)
rc, out = run("--project", RPROJ, *RIN, "--live-dir", live_copy("live-wording", edit=("Owner: Bo.", "Owned by Bo.")))
case("render vs live: wording-only change is WORDING, not drift", rc == 0 and "WORDING  (preamble)" in out)
rc, out = run("--project", RPROJ, *RIN, "--live-dir", live_copy("live-drift", edit=("`claude-code`", "`codex`")))
case("render vs live: changed key fact is drift", rc == 1 and "DRIFT    (preamble)" in out
     and "`claude-code`" in out and "`codex`" in out)
rc, out = run("--project", RPROJ, *RIN, "--live-dir", live_copy("live-missing", drop="briefs/reviewer.md"))
case("render vs live: missing live file is exit 2, never a pass", rc == 2
     and "MISSING  briefs/reviewer.md" in out and "missing from the live copy" in out)
rc, out = run("--project", RPROJ, *RIN, "--live-dir", live_copy("live-extra", add="runtime/old.md"))
case("render vs live: extra live file is drift", rc == 1 and "EXTRA    runtime/old.md" in out)

with open(RPROJ, encoding="utf-8") as fh:
    proj = fh.read()
assert 'toolchain_bin = "/opt/node/bin"' in proj
proj_live = write("crew-live.toml", proj.replace('toolchain_bin = "/opt/node/bin"', 'toolchain_bin = "/opt/node/bin"\n'
                                                 'live_dir = "%s"' % os.path.join(tmp, "live-match")))
rc, out = run("--project", proj_live, *RIN)
case("render vs live: live dir from the profile's paths.live_dir", rc == 0 and "OK: no drift" in out)
rc, out = run("--project", proj_live, *RIN, "--live-dir", os.path.join(tmp, "live-drift"))
case("render vs live: --live-dir overrides the profile", rc == 1)
rc, out = run("--project", RPROJ, *RIN, env={"ECREW_LIVE_DIR": os.path.join(tmp, "live-match")})
case("render vs live: live dir from ECREW_LIVE_DIR", rc == 0)
rc, out = run("--project", os.path.join(HERE, "..", "profiles", "default.toml"))
case("render vs live: placeholder live dir (default profile) is exit 2", rc == 2 and "no live copy path" in out)
rc, out = run("--project", RPROJ, *RIN, "--live-dir", os.path.join(tmp, "nope"))
case("render vs live: absent live dir is exit 2", rc == 2 and "not found" in out)
rc, out = run("--project", os.path.join(tmp, "nope.toml"), *RIN, "--live-dir", os.path.join(tmp, "live-match"))
case("render vs live: unreadable profile is exit 2", rc == 2 and "cannot resolve" in out)
# Render-time notes (#580) are part of the render, so drift covers them.
note = write("note.md", "Use `alpha`.\n")
proj_notes = write("crew-notes.toml", proj.replace('timezone = "America/Los_Angeles"',
                                                  'timezone = "America/Los_Angeles"\nname = "tmux"')
                   .replace('capabilities = { board-status = "unsupported" }\n', '')
                   + '\n[runtime.options.notes.render]\ncoordinator = ["note.md"]\n')
live = os.path.join(tmp, "notes-live")
render = subprocess.run([sys.executable, os.path.join(HERE, "crew-render.py"), "--project", proj_notes, *RIN,
                         "--out", live], capture_output=True, text=True)
with open(os.path.join(live, "briefs", "coordinator.md"), encoding="utf-8") as fh:
    rendered = fh.read()
case("render note lands in the rendered brief", render.returncode == 0
     and rendered.endswith("\n## Render note: note.md\n\nUse `alpha`.\n"))
rc, out = run("--project", proj_notes, *RIN, "--live-dir", live)
case("render vs live: render note matches", rc == 0 and "OK: no drift" in out)
write("note.md", "Use `beta`.\n")
rc, out = run("--project", proj_notes, *RIN, "--live-dir", live)
case("render vs live: changed render note is drift", rc == 1 and "DRIFT" in out and "`beta`" in out)
# The real bundle input includes both box skills in the existing drift tree.
project = os.path.join(HERE, "..", "profiles", "default.toml")
live = os.path.join(tmp, "box-live")
render = subprocess.run([sys.executable, os.path.join(HERE, "crew-render.py"),
                         "--project", project, "--out", live], capture_output=True, text=True)
case("box skills render alongside routines", render.returncode == 0)
rc, out = run("--project", project, "--live-dir", live)
case("rendered box skills match live", rc == 0 and "skills/eng-pr-pipeline/SKILL.md" in out
     and "skills/eng-crew-roles/SKILL.md" in out)
for skill in ("eng-pr-pipeline", "eng-crew-roles"):
    path = os.path.join(live, "runtime", "skills", skill, "SKILL.md")
    with open(path) as f:
        original = f.read()
    with open(path, "w") as f:
        f.write(original.replace("`crew:ready`", "`crew:wrong`"))
    rc, out = run("--project", project, "--live-dir", live)
    case(skill + " changed gate fact is drift", rc == 1 and "DRIFT" in out)
    os.remove(path)
    rc, out = run("--project", project, "--live-dir", live)
    case(skill + " missing live skill fails closed", rc == 2 and "MISSING" in out)
    with open(path, "w") as f:
        f.write(original)
shutil.rmtree(tmp, ignore_errors=True)

if failed:
    print("\n%d failed: %s" % (len(failed), ", ".join(failed)))
    sys.exit(1)
print("\nall passed")
