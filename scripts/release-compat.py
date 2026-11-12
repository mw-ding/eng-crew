#!/usr/bin/env python3
"""Refuse a minor or patch release that breaks a manifest the last release accepted.

Usage: release-compat.py <version> [--baseline TAG] [--tags TAG ...] [--repo DIR]

The baseline is --baseline, else the greatest stable `vX.Y.Z` in --tags below
<version>: the published predecessor, pinned once per cut by its commit. The
corpus is CORPUS below, read from the baseline tree. Each manifest must pass
the baseline's own `core/crew-config.py validate`; the candidate validator in
--repo (default: this checkout) then checks the same file. A manifest that
newly fails refuses a same-major <version>, naming the baseline, manifest,
failing requirement and the major to cut instead. A major <version> allows the
break and lists it. An unreadable baseline, or a corpus manifest its own
release rejects, fails with a repair step. Exit 0 ok, 1 refused or failed.
Used by `.github/workflows/release.yml` (docs/release.md, Steps, 4).
Standard library only.
"""
import argparse
import importlib.util
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("changelog_cut", os.path.join(ROOT, "scripts", "changelog-cut.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

VALIDATOR = "core/crew-config.py"
# (label, path in the baseline tree, derive an external pack from it).
CORPUS = [
    ("connectors/github/manifest.toml", "connectors/github/manifest.toml", False),
    ("external pack (from connectors/github/manifest.toml)", "connectors/github/manifest.toml", True),
]
EXTERNAL_NAME = "compat-external"


class Failed(Exception):
    pass


def external_pack(text, baseline):
    """The shipped declaration renamed to a backend mdstack does not ship, pinned to the baseline."""
    out, n = re.subn(r'(?m)^name = "github"$', 'name = "%s"\nmdstack_version = "%s"' % (EXTERNAL_NAME, baseline), text)
    if n != 1:
        raise Failed("cannot derive the external pack: no single `name = \"github\"` line at %s" % baseline)
    return out


def pick_baseline(version, tags):
    stable = [t for t in tags if t.startswith("v") and cc.SEMVER.match(t[1:]) and "-" not in t and "+" not in t
              and cc.precedence(t[1:]) < cc.precedence(version)]
    if not stable:
        raise Failed("no published stable tag below %s in --tags; fetch tags (git fetch --tags) or pass --baseline" % version)
    return max(stable, key=lambda t: cc.precedence(t[1:]))


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if p.returncode:
        raise Failed("git %s: %s" % (" ".join(args), p.stderr.decode(errors="replace").strip()))
    return p.stdout


def run_validator(validator, path):
    p = subprocess.run([sys.executable, validator, "validate", path], capture_output=True, text=True,
                       env=dict(os.environ, CREW_PROJECT=os.devnull))
    return p.returncode, [ln for ln in p.stdout.splitlines() if not ln.startswith("crew-config: OK")]


def check(version, baseline, repo):
    if not cc.SEMVER.match(version):
        raise Failed("not a SemVer version (MAJOR.MINOR.PATCH): %r" % version)
    if not (baseline.startswith("v") and cc.SEMVER.match(baseline[1:])):
        raise Failed("baseline %r is not a vX.Y.Z tag" % baseline)
    try:
        commit = git(repo, "rev-parse", "--verify", baseline + "^{commit}").decode().strip()
        archive = git(repo, "archive", "--format=tar", commit)
    except Failed as e:
        raise Failed("cannot read baseline %s (%s); fetch tags (git fetch --tags) or pass the published "
                     "predecessor with --baseline" % (baseline, e))
    major = int(cc.SEMVER.match(version).group(1))
    same_major = major == int(cc.SEMVER.match(baseline[1:]).group(1))
    broken = []
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        for label, rel, derive in CORPUS:
            path = os.path.join(tmp, rel)
            if not os.path.isfile(path):
                raise Failed("baseline %s has no %s; repair CORPUS in scripts/release-compat.py" % (baseline, rel))
            if derive:
                with open(path, encoding="utf-8") as f:
                    text = external_pack(f.read(), baseline)
                path = os.path.join(tmp, ".compat", EXTERNAL_NAME, "manifest.toml")
                os.makedirs(os.path.dirname(path))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            code, out = run_validator(os.path.join(tmp, VALIDATOR), path)
            if code:
                raise Failed("baseline %s rejects its own %s (%s); repair CORPUS in scripts/release-compat.py"
                             % (baseline, label, "; ".join(o.replace(path, "") for o in out) or "exit %d" % code))
            code, out = run_validator(os.path.join(repo, VALIDATOR), path)
            if code:
                broken.append((label, "; ".join(o.replace(path + ":", "") for o in out) or "exit %d" % code))
    return commit, same_major, broken, "%d.0.0" % (major + 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--baseline", help="published predecessor tag (default: greatest stable tag below version)")
    ap.add_argument("--tags", nargs="*", default=[])
    ap.add_argument("--repo", default=ROOT, help="checkout holding the candidate validator and the tags")
    args = ap.parse_args(argv)
    try:
        baseline = args.baseline or pick_baseline(args.version, args.tags)
        commit, same_major, broken, major = check(args.version, baseline, args.repo)
    except Failed as e:
        print("release-compat: failed: %s" % e, file=sys.stderr)
        return 1
    where = "baseline %s (%s)" % (baseline, commit[:12])
    for label, reason in broken:
        if same_major:
            print("release-compat: refused: %s passes %s's validator and fails the candidate's: %s. "
                  "%s is not a major bump; cut %s with a **Breaking:** entry, or restore compatibility"
                  % (label, where, reason, args.version, major), file=sys.stderr)
        else:
            print("release-compat: breaking (allowed by major %s): %s: %s" % (args.version, label, reason),
                  file=sys.stderr)
    if broken and same_major:
        return 1
    print("release-compat: %d manifest(s) against %s ok for v%s" % (len(CORPUS), where, args.version),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
