"""Shared release verifier and transport record for bootstrap, upgrade and host prepare (#943).

docs/bootstrap.md Release sources: `verify` runs verifier steps 2 to 5 over an archive and SHA256SUMS already
staged by a source, and moves the bundle into place only after every check passes; nothing is extracted before
the SHA256SUMS pin and entry checks. `transport` builds install.json's `transport` field for a non-GitHub source,
and `transport_kind` reads a record, where a record without the field is `github`. Stdlib only; makes no network
call and runs nothing from the bundle.
"""
import hashlib
import tarfile
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
    extracted = stage / "extract"
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
    return sha, sums_sha


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
