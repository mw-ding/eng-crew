"""Shared release verifier and transport record for bootstrap, upgrade and host prepare (#943).

docs/bootstrap.md Release sources: `fetch` stages a release from the [install] source and verifies it into place.
`stage` copies the archive and SHA256SUMS (gh for github, an HTTP GET for url, a file copy for mirror; only github
calls gh). `verify` runs verifier steps 2 to 5 over an archive and SHA256SUMS already staged by a source, and moves
the bundle into place only after every check passes; nothing is extracted before the SHA256SUMS pin and entry
checks. `build_git` is the git source (#945): it fetches the tag into a temporary bare repository with no checkout
and no hooks, refuses unless the tag peels to the pinned commit, and only then runs that commit's own
scripts/release-bundle.py; `unpack` applies the member, VERSION and entry point checks to the built archive.
`transport` builds install.json's `transport` field for a non-GitHub source, and `transport_kind` reads a record,
where a record without the field is `github`. Stdlib only; runs nothing from a bundle or commit before its checks.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def verify(stage, tag, destination, sha256sums_digest=None):
    """Check the staged eng-crew-<v>.tar.gz and SHA256SUMS in stage, then move the bundle to destination.

    Returns (bundle sha256, SHA256SUMS sha256). Raises ValueError, leaving destination absent, on any failure.
    """
    stage, name = Path(stage), "eng-crew-" + tag[1:]
    archive, sums = stage / (name + ".tar.gz"), stage / "SHA256SUMS"
    sums_sha = digest(sums)
    if sha256sums_digest is not None and sums_sha != sha256sums_digest:
        raise ValueError("SHA256SUMS digest %s does not match the pinned sha256sums_digest" % sums_sha)
    sha = digest(archive)
    entries = [line.split() for line in sums.read_text().splitlines()]
    checksums = [parts[0] for parts in entries if len(parts) == 2 and parts[1] == archive.name]
    if checksums != [sha]:
        raise ValueError("SHA256SUMS mismatch or missing entry for " + archive.name)
    unpack(archive, tag, destination)
    return sha, sums_sha


def unpack(archive, tag, destination):
    """Verifier steps 4 and 5: member checks, extract beside the archive, VERSION and entry point, then move."""
    archive, name = Path(archive), "eng-crew-" + tag[1:]
    extracted = archive.parent / "extract"
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if (not parts or parts[0] != name or ".." in parts or
                    not (member.isfile() or member.isdir())):
                raise ValueError("unsafe release archive member: " + member.name)
        tar.extractall(extracted, filter="data")
    bundle = extracted / name
    version = bundle / "VERSION"
    if not version.is_file() or version.read_text().strip() != tag or not (bundle / "scripts/crew").is_file():
        raise ValueError("release bundle VERSION or bootstrap entry point does not match " + tag)
    bundle.rename(destination)


def stage(install, tag, where):
    """Copy eng-crew-<v>.tar.gz and SHA256SUMS for tag into where. A url or mirror location holds them under
    <location>/<tag>/; only github calls gh."""
    kind, names = install.get("source", "github"), ["eng-crew-%s.tar.gz" % tag[1:], "SHA256SUMS"]
    if kind == "github":
        result = subprocess.run(["gh", "release", "download", tag, "-R", "mw-ding/eng-crew", "--pattern", names[0],
                                 "--pattern", names[1], "--dir", str(where)], capture_output=True, text=True)
        if result.returncode:
            raise ValueError("release download failed for " + tag)
        return
    for name in names:
        source = install["location"].rstrip("/") + "/" + tag + "/" + name
        try:
            if kind == "url":
                with urllib.request.urlopen(source, timeout=60) as response, open(Path(where) / name, "wb") as f:
                    shutil.copyfileobj(response, f)
            else:
                shutil.copyfile(source, Path(where) / name)
        except (OSError, ValueError) as e:
            raise ValueError("release fetch failed for %s from %s %s: %s" % (tag, kind, source, e))


def build_git(location, tag, commit, where):
    """The git source: fetch refs/tags/<tag> into a bare repository under where, refuse unless it peels to commit,
    then build the archive with that commit's scripts/release-bundle.py. Returns the archive path."""
    where = Path(where)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def run(step, *argv):
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, env=env)
        if r.returncode:
            raise ValueError("git source %s failed for %s from %s: %s" % (
                step, tag, location, r.stderr.decode(errors="replace").strip()[-300:]))
        return r.stdout

    repo = where / "repo.git"
    git = ["git", "-c", "core.hooksPath=" + os.devnull, "-C", str(repo)]
    run("init", "git", "init", "--quiet", "--bare", "--object-format=" + ("sha256" if len(commit) == 64 else "sha1"),
        str(repo))
    run("fetch", *git, "fetch", "--quiet", "--no-tags", "--", location, "+refs/tags/%s:refs/tags/%s" % (tag, tag))
    peeled = run("tag", *git, "rev-parse", "--verify", "refs/tags/%s^{commit}" % tag).decode().strip()
    if peeled != commit:
        raise ValueError("git tag %s resolves to %s, not the pinned git_commit %s" % (tag, peeled, commit))
    tools = where / "tools"
    archive = where / "scripts.tar"
    archive.write_bytes(run("archive", *git, "archive", "--format=tar", commit, "scripts"))
    with tarfile.open(archive) as tar:
        tar.extractall(tools, filter="data")
    run("build", sys.executable, str(tools / "scripts/release-bundle.py"), tag[1:], "--out", str(where), "--ref",
        commit, "--repo", "mw-ding/eng-crew", "--root", str(repo))
    return where / ("eng-crew-%s.tar.gz" % tag[1:])


def fetch(install, tag, destination):
    """Fetch tag from the [install] source in a staging directory beside destination and verify it into place.

    Returns (bundle sha256, SHA256SUMS sha256 or None, commit or None). A failure removes the staging directory
    and leaves destination absent."""
    destination = Path(destination)
    with tempfile.TemporaryDirectory(prefix=".crew-fetch-", dir=destination.parent) as tmp:
        if install.get("source") == "git":
            archive = build_git(install["location"], tag, install["git_commit"], tmp)
            unpack(archive, tag, destination)
            return digest(archive), None, install["git_commit"]
        stage(install, tag, tmp)
        return (*verify(tmp, tag, destination, install.get("sha256sums_digest")), None)


def transport(install, sha256sums_sha256=None, commit=None):
    """install.json's `transport` for the profile's [install] table; None (no field) for github."""
    kind = (install or {}).get("source", "github")
    if kind == "github":
        return None
    record = {"kind": kind, "location": install["location"]}
    if kind == "git":
        record["commit"] = commit
    else:
        record["sha256sums_sha256"] = sha256sums_sha256
        record["pinned"] = "sha256sums_digest" in install
    return record


def transport_kind(record):
    """The source kind an install.json record names; a record without `transport` reads as github."""
    return (record.get("transport") or {}).get("kind", "github")
