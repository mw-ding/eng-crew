#!/usr/bin/env python3
"""Export pinned personnel content and a mechanical host binding (#1180).

Usage: personnel-bundle.py --ref FULL_SHA --binding FILE --role eng/ROLE
       [--role eng/ROLE ...] --out DIR [--root PRODUCER_CHECKOUT]

Reads only committed producer files. Validates the complete composition before
publishing a content directory; identical reruns verify hashes and do no writes.
An existing different destination is refused. No consumer executable is shipped.
Python 3.11+ standard library only; run in the full producer checkout.
"""
import argparse
import fnmatch
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from posixpath import dirname, join, normpath
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parent.parent
CAPABILITIES = (
    "wake-delivery", "durable-queues", "run-identity", "claims-status",
    "connector-access", "head-bound-land", "reviewer-independence",
    "synthesizer-only-land",
)
ACTIONS = (
    "read", "resolve-policy", "check-ownership", "claim", "release",
    "heartbeat", "ack", "report", "notify", "wait", "spawn-worker", "supervise", "workspace",
    "artifact", "post-marker", "tracker", "run-check", "publish-change",
    "update-base", "compare-content", "land", "owner-channel",
    "knowledge-read", "knowledge-propose-edit",
)
OP = re.compile(r"<op:([a-z][a-z0-9.-]*(?:\|[a-z][a-z0-9.-]*)*)>")
AUTHORITY = {"class", "escalation", "marker_role", "passes", "head",
             "engine_independent_of", "identity_independent_of"}


class Refused(ValueError):
    pass


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def read(root, ref, path):
    return git(root, "show", f"{ref}:{path}").decode()


def closed(data, allowed, where):
    extra = set(data) - set(allowed)
    if extra:
        raise Refused(f"{where}: unsupported fields: {', '.join(sorted(extra))}")


def strings(data, where):
    if not isinstance(data, dict) or any(not isinstance(v, str) or not v.strip()
                                         for v in data.values()):
        raise Refused(f"{where}: expected nonempty string mappings")


def binding_file(path):
    data = tomllib.loads(path.read_text())
    closed(data, {"id", "version", "capabilities", "gaps", "actions", "operations", "settings"}, "binding")
    for key in ("id", "version"):
        if not isinstance(data.get(key), str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", data[key]):
            raise Refused(f"binding: invalid {key}")
    caps = data.get("capabilities", {})
    closed(caps, CAPABILITIES, "capabilities")
    if any(caps.get(c) is not True for c in CAPABILITIES) or data.get("gaps", []):
        raise Refused("binding: missing capability or unsupported invariant (declared gaps)")
    actions = data.get("actions", {})
    strings(actions, "actions")
    closed(actions, ACTIONS, "actions")
    if set(actions) != set(ACTIONS):
        raise Refused("binding: missing required action")
    if any("<op:" in value or "$CREW_BIN" in value for value in actions.values()):
        raise Refused("binding: unbound required action")
    strings(data.get("operations", {}), "operations")
    for role, settings in data.get("settings", {}).items():
        closed(settings, {"presentation", "engine", "extra_skills"}, f"settings.{role}")
        strings({k: v for k, v in settings.items() if k != "extra_skills"}, "settings")
        if not isinstance(settings.get("extra_skills", []), list):
            raise Refused("extra_skills: expected producer paths")
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def compose(root, ref, roles, binding):
    if not re.fullmatch(r"[0-9a-f]{40}", ref) or git(root, "rev-parse", f"{ref}^{{commit}}").decode().strip() != ref:
        raise Refused("source pin must be a full commit SHA")
    if not roles or len(set(roles)) != len(roles):
        raise Refused("missing or colliding role ID")
    tree = git(root, "ls-tree", "-r", "--name-only", ref).decode().splitlines()
    patterns = [l for l in read(root, ref, "scripts/personnel-files.txt").splitlines()
                if l and not l.startswith("#")]
    selected = {p for p in tree if any(fnmatch.fnmatchcase(p, g) for g in patterns)}
    if any(not p.endswith((".md", ".toml")) for p in selected):
        raise Refused("content manifest selected a non-content file")
    with tarfile.open(fileobj=io.BytesIO(git(root, "archive", ref)), mode="r:") as archive:
        files = {p: archive.extractfile(p).read() for p in sorted(selected)}
    closed(binding.get("settings", {}), roles, "settings role IDs")
    descriptors = {}
    for role in sorted(roles):
        if not re.fullmatch(r"eng/[a-z][a-z0-9-]*", role):
            raise Refused(f"unknown role ID: {role}")
        path = f"roles/{role}.toml"
        if path not in files or f"templates/policy/{role.split('/')[1]}/SKILL.md" not in files:
            raise Refused(f"missing role: {role}")
        descriptors[role] = tomllib.loads(files[path].decode())
        for extra in binding.get("settings", {}).get(role, {}).get("extra_skills", []):
            if not isinstance(extra, str) or extra not in tree or not extra.endswith("/SKILL.md"):
                raise Refused(f"missing additive skill: {extra}")
            # Only canonical producer skills are accepted, never overlay prose.
            if not extra.startswith(("templates/policy/", "roles/seats/")):
                raise Refused(f"extra skill outside personnel content: {extra}")
            files[extra] = read(root, ref, extra).encode()

    operations = binding.get("operations", {})

    def operation(match):
        for name in match[1].split("|"):
            if name in operations:
                value = operations[name]
                if "<op:" in value or "$CREW_BIN" in value:
                    raise Refused(f"unbound operation mapping: {name}")
                return value
        raise Refused(f"unbound required operation: {match[1]}")

    for path, data in list(files.items()):
        if path.startswith("templates/policy/") and path.endswith(".md"):
            text = data.decode()
            text = OP.sub(operation, text)
            text = text.replace("<include:docs/roles.md#pr-conventions>",
                                "Read docs/roles.md, PR conventions, in the personnel root.")
            # Canonical fragments retain run parameters and illustrative examples.
            # The personnel entry binds mechanics through the host table.
            text = text.replace("<mdstack>", "{personnel-root}")
            files[path] = text.encode()

    template = read(root, ref, "templates/personnel/brief.md")
    for role, descriptor in descriptors.items():
        name = role.split("/")[1]
        settings = binding.get("settings", {}).get(role, {})
        actions = "\n".join(f"- `{k}`: `{v}`" for k, v in sorted(binding["actions"].items()))
        authority = json.dumps({k: descriptor[k] for k in sorted(AUTHORITY) if k in descriptor}, sort_keys=True)
        text = template.replace("{{role}}", role).replace("{{binding}}", f"{binding['id']}@{binding['version']}")
        text = text.replace("{{policy-entry}}", f"[canonical role and procedures](../../templates/policy/{name}/SKILL.md)")
        text = text.replace("{{authority}}", authority).replace("{{actions}}", actions)
        text = text.replace("{{settings}}", json.dumps(settings, sort_keys=True))
        files[f"briefs/eng/{name}.md"] = text.encode()

    # Close every Markdown reference to producer content. Execution adapters and
    # historical references stay pinned producer links, never installed machinery.
    source_url = "https://github.com/" + git(root, "remote", "get-url", "origin").decode().strip().split("github.com")[-1].lstrip(":/").removesuffix(".git")
    spec = importlib.util.spec_from_file_location("release_bundle", ROOT / "scripts/release-bundle.py")
    links = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(links)
    for path, data in list(files.items()):
        if not path.endswith(".md"):
            continue

        lines = data.decode().split("\n")
        for number, line in links.cr.unfenced(lines):
            for start, end, _ in sorted(links.link_spans(line), reverse=True):
                target = line[start:end]
                if not target or links.EXTERNAL.match(target) or links.cr.PLACEHOLDER.search(target):
                    continue
                dest, sep, fragment = target.partition("#")
                resolved = normpath(join(dirname(path), dest))
                if resolved in files:
                    continue
                if resolved not in tree and not any(p.startswith(resolved.rstrip("/") + "/") for p in tree):
                    raise Refused(f"unresolved reference: {path}: {target}")
                url = f"{source_url}/blob/{ref}/{resolved}" + (sep + fragment if sep else "")
                line = line[:start] + url + line[end:]
            lines[number - 1] = line
        files[path] = "\n".join(lines).encode()

    version = read(root, ref, "VERSION").strip() if "VERSION" in tree else "v" + re.search(
        r"^## \[([0-9][^\]]*)\]", read(root, ref, "CHANGELOG.md"), re.M)[1]
    manifest = {
        "schema_version": 1, "source": {"commit": ref, "version": version},
        "roles": sorted(roles), "binding": binding,
        "binding_sha256": digest(json.dumps(binding, sort_keys=True).encode()),
        "provenance": {r: {k: f"binding:{binding['id']}@{binding['version']}" for k in binding.get("settings", {}).get(r, {})} for r in roles},
        "files": {p: digest(d) for p, d in sorted(files.items())},
    }
    files["personnel.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    return files


def install(files, out):
    if out.exists():
        actual = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        if actual != files or any(p.is_symlink() for p in out.rglob("*")):
            raise Refused("destination differs; select a new version directory")
        return "unchanged"
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".personnel-", dir=out.parent))
    try:
        for path, data in files.items():
            dest = stage / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        stage.rename(out)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return "installed"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--role", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        files = compose(args.root, args.ref, args.role, binding_file(args.binding))
        result = install(files, args.out)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"personnel-bundle: refused: {exc}", file=sys.stderr)
        return 1
    print(f"personnel-bundle: {result}; {len(args.role)} roles, {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
