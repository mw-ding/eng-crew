#!/usr/bin/env python3
"""Zero-model project docs scan: stage 1 of the docs pass (docs/project-docs.md Docs pass, #1025).

For each `[docs] repos` entry of the resolved profile, reads the repo's git tree at its default-branch head
from a local clone and writes `<state-dir>/<owner>__<repo>/docs/scan.json` with:

- inventory: every Markdown file, its line count, its docs index row (and kind) and its status banner;
- missing: essential docs (docs/project-doc-set.md) absent at their `[docs] homes` path or anchor, and a missing
  `docs/README.md` index when more than five docs sit under `docs/`;
- unbannered: docs the index marks as `design` with no banner under the H1;
- stale: banners whose **Last checked** date is missing or older than `stale_days`;
- broken_links: relative links whose file or Markdown heading anchor does not exist at that ref;
- oversize: docs over `size_budget` lines.

The head is `--ref OWNER/NAME=REF` when given, else `origin/<repo.default_branch>` for the project's own repo,
else `origin/HEAD`, else `HEAD`. Read-only: it reads git objects (`ls-tree`, `cat-file`), never fetches or
touches a work tree, and writes nothing but each repo's scan.json. No profile `[docs]` table: nothing runs.
Python 3 standard library only, no network.

Usage: docs-scan.py --project FILE [--org-profile FILE] --checkout OWNER/NAME=PATH... [--ref OWNER/NAME=REF]...
           [--today YYYY-MM-DD]
Prints one summary line per repo; exit 0 after a scan (findings included), 2 on a usage, profile or git error.
"""
import argparse
import datetime
import importlib.util
import json
import os
import posixpath
import re
import subprocess
import sys
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crew_config = load("crew_config", "crew-config.py")
repo_check = load("check_repo", "check-repo.py")  # fence, code-span, comment and link parsing shared with `links`

DEFAULT_HOMES = {"overview": "README.md", "agent_guide": "AGENTS.md", "architecture": "docs/architecture.md",
                 "runbook": "docs/runbook.md", "decisions": "docs/decisions.md"}  # docs/project-doc-set.md
INDEX = "docs/README.md"
ATX = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
HTML_ID = re.compile(r"<a\s[^>]*(?:id|name)=\"([^\"]+)\"", re.I)
BANNER_ITEM = re.compile(r"^>\s*[-*]\s+\*\*([^*]+?):\*\*\s*(.*)$")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
DELIM = re.compile(r"^ *\|? *:?-+:? *\|")


def git(path, *args, data=None):
    r = subprocess.run(["git", "-C", path, *args], input=data, capture_output=True)
    if r.returncode:
        raise RuntimeError("git %s in %s: %s" % (args[0], path, r.stderr.decode(errors="replace").strip()))
    return r.stdout


def read_tree(path, ref):
    """(head sha, every path in the tree, {Markdown path: lines}) at ref, from git objects only."""
    sha = git(path, "rev-parse", "--verify", ref + "^{commit}").decode().strip()
    entries = [e.split("\t", 1) for e in git(path, "ls-tree", "-r", "-z", "--full-tree", sha).decode().split("\0") if e]
    files = [name for _, name in entries]
    blobs = [(meta.split()[2], name) for meta, name in entries if meta.split()[1] == "blob" and name.endswith(".md")]
    out = git(path, "cat-file", "--batch", data="".join(b + "\n" for b, _ in blobs).encode())
    docs, pos = {}, 0
    for _, name in blobs:
        end = out.index(b"\n", pos)
        size = int(out[pos:end].split()[2])
        docs[name] = out[end + 1:end + 1 + size].decode("utf-8", "replace").splitlines()
        pos = end + 2 + size
    return sha, files, docs


def default_head(path, candidates):
    """The first candidate ref that names a commit in the clone, else the last (whose read then fails loudly)."""
    for ref in candidates:
        if subprocess.run(["git", "-C", path, "rev-parse", "--verify", "-q", ref + "^{commit}"],
                          capture_output=True).returncode == 0:
            return ref
    return candidates[-1]


def slug(text):
    """GitHub's heading anchor: link and tag markup dropped, lowercased, punctuation removed, spaces to hyphens."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    parts = re.split(r"(`+)(.+?)\1", text)  # [text, ticks, code, text, ...]: tags drop outside code spans only
    text = "".join(p if i % 3 == 2 else "" if i % 3 else re.sub(r"<[^>]+>", "", p) for i, p in enumerate(parts))
    text = text.strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(lines):
    seen, out = {}, set()
    visible = list(repo_check.strip_html_comments(repo_check.unfenced(lines)))
    for k, (n, line) in enumerate(visible):
        out.update(HTML_ID.findall(line))
        m = ATX.match(line)
        prev = visible[k - 1] if k else None
        if not m and SETEXT.match(line) and prev and prev[0] == n - 1 and prev[1].strip() and not ATX.match(prev[1]):
            m = re.match(r"\s*(.*?)\s*$", prev[1])
        if m:
            base = slug(m.group(1))
            count = seen.get(base, 0)
            seen[base] = count + 1
            out.add(base if not count else "%s-%d" % (base, count))
    return out


def banner(lines):
    """The `> - **Key:** value` list right under the H1 (docs/project-doc-set.md Status banners), or None."""
    h1 = next((n for n, line in repo_check.unfenced(lines) if re.match(r"^# \S", line)), None)
    if h1 is None:
        return None
    items, key, j = {}, None, h1
    while j < len(lines) and not lines[j].strip():
        j += 1
    while j < len(lines) and lines[j].startswith(">"):
        m = BANNER_ITEM.match(lines[j])
        if m:
            key = m.group(1).strip()
            items[key] = m.group(2).strip()
        elif key and lines[j].strip(" >"):
            items[key] += " " + lines[j].strip(" >")
        j += 1
    return items or None


def index_rows(lines):
    """{doc path: (index line, kind)} for each table row of the docs index whose first link names a doc."""
    rows, kind_col = {}, None
    for n, line in enumerate(lines, 1):
        if not line.lstrip().startswith("|"):
            kind_col = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if n < len(lines) and DELIM.match(lines[n]):  # header row: find the Kind column
            kind_col = next((i for i, c in enumerate(cells) if c.lower() == "kind"), None)
            continue
        links = repo_check.link_destinations(line)
        if links and not re.match(r"^[a-z][a-z0-9+.-]*:", links[0], re.I):
            path = posixpath.normpath(posixpath.join(posixpath.dirname(INDEX), unquote(links[0].split("#")[0])))
            kind = cells[kind_col] if kind_col is not None and kind_col < len(cells) else None
            rows.setdefault(path, ("%s:%d" % (INDEX, n), kind))
    return rows


def broken_links(files, docs, anchor_sets):
    known = set(files) | {posixpath.dirname(p) for p in files}
    for f in list(known):
        while f:
            f = posixpath.dirname(f)
            known.add(f)
    out = []
    for path, lines in sorted(docs.items()):
        for n, line in repo_check.strip_html_comments(repo_check.unfenced(lines)):
            text = repo_check.strip_code_spans(line)
            targets = repo_check.link_destinations(text)
            ref = repo_check.REFDEF.match(text)
            if ref:
                targets.append(ref.group(1) if ref.group(1) is not None else ref.group(2))
            for t in targets:
                if re.match(r"^([a-z][a-z0-9+.-]*:|//)", t, re.I) or repo_check.PLACEHOLDER.search(t):
                    continue
                dest, _, anchor = t.partition("#")
                dest = unquote(dest.split("?")[0])
                target = posixpath.normpath(posixpath.join("" if dest.startswith("/") else posixpath.dirname(path),
                                                           dest.lstrip("/"))) if dest else path
                if target == ".." or target.startswith("../"):
                    out.append({"path": path, "line": n, "target": t, "reason": "escapes the repo"})
                elif target not in known and target != ".":
                    out.append({"path": path, "line": n, "target": t, "reason": "no such file"})
                elif anchor and target in docs and not re.fullmatch(r"L\d+(-L\d+)?", anchor) \
                        and unquote(anchor).lower() not in anchor_sets[target]:
                    out.append({"path": path, "line": n, "target": t, "reason": "no such anchor"})
    return out


def scan(repo, sha, files, docs, settings, today):
    anchor_sets = {p: anchors(lines) for p, lines in docs.items()}
    rows = index_rows(docs.get(INDEX, []))
    inventory, unbannered, stale, oversize = [], [], [], []
    for path, lines in sorted(docs.items()):
        row, kind = rows.get(path, (None, None))
        mark = banner(lines)
        inventory.append({"path": path, "lines": len(lines), "index": row, "kind": kind, "banner": mark})
        if kind and "design" in re.split(r"[\s,]+", kind.lower()) and not mark:
            unbannered.append({"path": path, "index": row})
        if mark:
            found = DATE.search(mark.get("Last checked", ""))
            day = datetime.date.fromisoformat(found.group()) if found else None
            if day is None or (today - day).days > settings["stale_days"]:
                stale.append({"path": path, "last_checked": day and day.isoformat(),
                              "age_days": day and (today - day).days})
        if len(lines) > settings["size_budget"]:
            oversize.append({"path": path, "lines": len(lines)})
    missing = []
    for name, home in settings["homes"].items():
        path, _, anchor = home.partition("#")
        if path not in files:
            missing.append({"essential": name, "home": home, "reason": "no such file"})
        elif anchor and anchor.lower() not in anchor_sets.get(path, set()):
            missing.append({"essential": name, "home": home, "reason": "no such anchor"})
    if INDEX not in files and sum(p.startswith("docs/") for p in docs) > 5:
        missing.append({"essential": "docs_index", "home": INDEX, "reason": "more than five docs under docs/"})
    return {"repo": repo, "head": sha, "scanned": today.isoformat(), "settings": settings,
            "inventory": inventory, "missing": missing, "unbannered": unbannered, "stale": stale,
            "broken_links": broken_links(files, docs, anchor_sets), "oversize": oversize}


def pairs(items, flag):
    out = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not crew_config.TRACKER_REPO.fullmatch(key) or not value:
            raise ValueError("%s %r: expected OWNER/NAME=VALUE" % (flag, item))
        out[key] = value
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="project profile (crew.toml)")
    ap.add_argument("--org-profile", help="org profile layered under the project")
    ap.add_argument("--checkout", action="append", default=[], metavar="OWNER/NAME=PATH",
                    help="local clone of a [docs] repo (one per repo)")
    ap.add_argument("--ref", action="append", default=[], metavar="OWNER/NAME=REF", help="scan this ref instead")
    ap.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.datetime.now(datetime.timezone.utc).date(),
                    metavar="YYYY-MM-DD", help="date staleness is measured from (default: today, UTC)")
    args = ap.parse_args(argv)
    try:
        checkouts, refs = pairs(args.checkout, "--checkout"), pairs(args.ref, "--ref")
        merged, _, problems, _ = crew_config.resolve_profile(args.project, args.org_profile)
        if problems:
            raise ValueError("\n".join(problems))
        docs = merged.get("docs")
        if not isinstance(docs, dict):
            print("docs-scan: no [docs] table in the profile; nothing to scan", file=sys.stderr)
            return 0
        lost = [r for r in docs["repos"] if r not in checkouts]
        if lost:
            raise ValueError("no --checkout for %s" % ", ".join(lost))
        own = "%s/%s" % (merged["repo"]["owner"], merged["repo"]["name"])
        settings = {"stale_days": docs["stale_days"], "size_budget": docs["size_budget"],
                    "homes": dict(DEFAULT_HOMES, **docs.get("homes", {}))}
        results = []
        for repo in docs["repos"]:
            path = checkouts[repo]
            heads = [refs[repo]] if repo in refs else \
                (["origin/" + merged["repo"]["default_branch"]] if repo == own else []) + ["origin/HEAD", "HEAD"]
            results.append(scan(repo, *read_tree(path, default_head(path, heads)), settings, args.today))
    except (OSError, ValueError, RuntimeError) as exc:
        print("docs-scan: %s" % exc, file=sys.stderr)
        return 2
    for result in results:
        owner, name = result["repo"].split("/")
        out = os.path.join(os.path.abspath(merged["paths"]["state_dir"]), "%s__%s" % (owner, name), "docs", "scan.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
            f.write("\n")
        print("%s @ %s: %d docs, %s -> %s" % (result["repo"], result["head"][:7], len(result["inventory"]), ", ".join(
            "%d %s" % (len(result[k]), k) for k in ("missing", "unbannered", "stale", "broken_links", "oversize")), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
