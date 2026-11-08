#!/usr/bin/env python3
"""Build the release bundle `mdstack-<version>.tar.gz` and `SHA256SUMS`.

Usage: release-bundle.py <version> [--out DIR] [--ref REF] [--repo OWNER/REPO] [--root DIR]

Bundles every path tracked at REF (default HEAD) that scripts/deliverables.txt
classifies `deliverable`, at its repo path under `mdstack-<version>/`, plus
`VERSION` (`v<version>`).
In bundled Markdown, a relative link to a repo path outside the bundle is
rewritten to `https://github.com/<owner>/<repo>/blob/v<version>/<path>`
(`raw/` for an image, an `![...]` link or a png, jpg, jpeg, gif, svg or webp
file, so it renders inline);
owner and repo come from --repo or the `origin` remote. An offline link check
then needs every relative link to resolve inside the bundle (exit 1, nothing
written, if not). Deterministic: sorted entries, mtime from SOURCE_DATE_EPOCH
or the commit time, uid/gid 0, no user names. Standard library only.
Refuses (exit 1, nothing written) a non-SemVer version, a path the manifest
does not classify exactly once, and a dangling link. Not run in CI.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import os
import posixpath
import re
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import quote, unquote

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cr = load("check_repo", "check-repo.py")
SEMVER = load("changelog_cut", "changelog-cut.py").SEMVER
REMOTE = re.compile(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$")
EXTERNAL = re.compile(r"^([a-z][a-z0-9+.-]*:|//|#)", re.I)
IMAGE_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp)$", re.I)


class Refused(Exception):
    pass


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", root, *args], capture_output=True, env=env, check=True).stdout


def tracked(root, ref):
    """({path: (mode, blob sha)} for every path at ref, {path: class})."""
    rows = []
    for raw in git(root, "show", "%s:%s" % (ref, cr.MANIFEST)).decode().splitlines():
        if raw.strip() and not raw.startswith("#"):
            glob, cls = raw.split("\t")[:2]
            rows.append((cr.glob_regex(glob), cls))
    tree, classes = {}, {}
    for entry in git(root, "ls-tree", "-r", "-z", ref).decode().split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            mode, _, sha = meta.split()
            hits = [cls for rx, cls in rows if rx.match(path)]
            if len(hits) != 1:
                raise Refused("%s matches %d manifest rows; run check-repo.py" % (path, len(hits)))
            tree[path] = (0o755 if mode == "100755" else 0o644, sha)
            classes[path] = hits[0]
    return tree, classes


def code_spans(line):
    """Index ranges of inline code spans (same rules as check-repo.py)."""
    tokens, spans, i = list(re.finditer(r"\\.|`+", line)), [], 0
    while i < len(tokens):
        run = tokens[i].group()
        close = None if run.startswith("\\") else next(
            (j for j in range(i + 1, len(tokens)) if tokens[j].group() == run), None)
        if close is not None:
            spans.append((tokens[i].start(), tokens[close].end()))
            i = close
        i += 1
    return spans


def link_spans(line):
    """(start, end, is image) of each inline link destination or reference
    definition outside code spans."""
    code, spans = code_spans(line), []
    for m in cr.LINK_OPEN.finditer(line):
        i = j = m.end()
        if any(a <= m.start() < b for a, b in code):
            continue
        if line.startswith("<", i):
            j = line.find(">", i)
            if j > 0:
                spans.append((i + 1, j, m.group().startswith("!")))
            continue
        depth = 0
        while j < len(line) and not line[j].isspace() and not (line[j] == ")" and depth == 0):
            depth += {"(": 1, ")": -1}.get(line[j], 0)
            j += 1
        spans.append((i, j, m.group().startswith("!")))
    ref = cr.REFDEF.match(line)
    if ref:
        spans.append((*ref.span(1 if ref.group(1) is not None else 2), False))
    return spans


def rewrite(rel, text, tree, bundle, repo_url, tag):
    """Point relative links to repo paths outside the bundle at the tag."""
    lines = text.split("\n")
    for n, line in cr.unfenced(lines):
        for start, end, image in sorted(link_spans(line), reverse=True):
            dest = line[start:end]
            if not dest or EXTERNAL.match(dest) or cr.PLACEHOLDER.search(dest):
                continue
            path, frag = re.match(r"([^#?]*)(.*)", dest).groups()
            folder = "" if path.startswith("/") else posixpath.dirname(rel)
            target = posixpath.normpath(posixpath.join(folder, unquote(path).lstrip("/")))
            if target in bundle or target not in tree:
                continue  # in the bundle, or not a tracked file: the link check decides
            kind = "raw" if image or IMAGE_EXT.search(target) else "blob"
            url = "%s/%s/%s/%s%s" % (repo_url, kind, tag, quote(target), frag)
            line = line[:start] + url + line[end:]
        lines[n - 1] = line
    return "\n".join(lines)


def build(root, version, ref, repo, out):
    if not SEMVER.match(version):
        raise Refused("not a SemVer version (no leading v): %r" % version)
    if not repo:
        m = REMOTE.search(git(root, "remote", "get-url", "origin").decode().strip())
        if not m:
            raise Refused("cannot read owner/repo from the origin remote; pass --repo")
        repo = "%s/%s" % m.groups()
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or git(root, "log", "-1", "--format=%ct", ref))
    tree, classes = tracked(root, ref)
    bundle = {p: tree[p] for p in tree if classes[p] == "deliverable"}
    files = {"VERSION": (0o644, ("v%s\n" % version).encode())}
    for path, (mode, sha) in bundle.items():
        data = git(root, "cat-file", "blob", sha)
        if path.endswith(".md"):
            text = rewrite(path, data.decode("utf-8"), tree, bundle, "https://github.com/" + repo, "v" + version)
            data = text.encode("utf-8")
        files[path] = (mode, data)
    with tempfile.TemporaryDirectory() as stage:
        for path, (_, data) in files.items():
            os.makedirs(os.path.dirname(os.path.join(stage, path)), exist_ok=True)
            with open(os.path.join(stage, path), "wb") as f:
                f.write(data)
        problems = []
        cr.check_links(stage, lambda p, n, r, why: problems.append("%s:%d: [%s] %s" % (p, n, r, why)))
    if problems:
        raise Refused("offline link check failed:\n" + "\n".join(problems))
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(files):
                mode, data = files[path]
                info = tarfile.TarInfo("mdstack-%s/%s" % (version, path))
                info.size, info.mtime, info.mode = len(data), epoch, mode
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
    name = "mdstack-%s.tar.gz" % version
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, name), "wb") as f:
        f.write(raw.getvalue())
    with open(os.path.join(out, "SHA256SUMS"), "w") as f:
        f.write("%s  %s\n" % (hashlib.sha256(raw.getvalue()).hexdigest(), name))
    return os.path.join(out, name), len(files)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--out", default=".")
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--repo", help="OWNER/REPO for rewritten links (default: the origin remote)")
    ap.add_argument("--root", default=os.path.dirname(HERE))
    args = ap.parse_args(argv)
    try:
        path, count = build(os.path.abspath(args.root), args.version, args.ref, args.repo, args.out)
    except (Refused, subprocess.CalledProcessError, UnicodeDecodeError) as e:
        print("release-bundle: refused: %s" % e, file=sys.stderr)
        return 1
    print("release-bundle: %s (%d files) and SHA256SUMS" % (path, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
