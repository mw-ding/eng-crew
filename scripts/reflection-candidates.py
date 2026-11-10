#!/usr/bin/env python3
"""Reflection threshold candidates: which recurring patterns need a pending intake card (M39 R6, #1522; #1403).

Reads, offline: the evidence index of `reflection-scan.py` (`--index`), the forge snapshots that index was built from
(`--forge`, repeatable; the same `gh issue list` / `gh pr list` JSON) and the findings buffer at the index's SHA
(`--buffer`, for example `git show <sha>:docs/findings/buffer.md`). Python 3 standard library only; no network, no
gh, no writes but stdout. It selects and matches; the researcher's protocol-reflection procedure files or appends.

Selection: a findings row whose Count is 3 or more, or 3 or more distinct incidents of one `class:` key in the
index's window. A row with Status `fixed`, `applied` or `encoded` is skipped unless a fresh occurrence came after its
fix closed: a later row Date or a linked incident first reported after it. A fix not in the snapshots is skipped as
unknown, never assumed fresh.

Matching: an existing issue or PR is a candidate's work when its body names the candidate's proposal prefix
(`rp-<class>-`), its Failure class is the candidate's class, or it is the row's `batched -> #n` issue. An open match
is preferred, then the latest closed; a closed item of one counted incident fixed that incident, not the pattern,
and is not a match. Actions: `file` (no match, or a closed match with a fresh occurrence after it closed:
`regression_of`), `append` (an open match missing some of the evidence, listed in `new`), `none` (the open match
already cites everything, as after an interrupted run that posted its card) and `skip`. A fixed row with a fresh
occurrence then checks its matching cards too, open or closed, so a retry finds the regression card it already
filed and a closed one needs an occurrence after it closed.

Usage: reflection-candidates.py --index FILE [--forge FILE]... [--buffer FILE]
Exit codes: 0 candidates printed, 2 usage or malformed input.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rs = module("reflection_scan", "reflection-scan.py")
tc = rs.tc
THRESHOLD = 3
FIXED = ("fixed", "applied", "encoded")


def rows(text, repo):
    """Findings buffer rows: heading, Date, refs, Count, Status word and the refs its Status names."""
    out, cur = [], None
    for line in text.splitlines() + ["### end"]:
        if line.startswith("### "):
            if cur and "count" in cur:
                out.append(cur)
            cur = {"title": line[4:].strip()}
        elif cur is not None and rs.FIELD.match(line):
            name, value = rs.FIELD.match(line)[1].strip().lower(), rs.FIELD.match(line)[2]
            if name == "count":
                cur["count"] = int(value.split()[0])
            elif name == "date":
                cur["date"] = value[:10]
            elif name == "pr / repo":
                cur["refs"] = rs.refs(value, repo)
            elif name == "status":
                cur["status"] = (value.split() or [""])[0].strip("`*:,.").lower()
                cur["status_refs"] = rs.refs(value, repo)
    return out


def first(incident):
    return min(e["at"] for e in incident["evidence"] if e["at"])


def cited(item, repo):
    text = "\n".join([item.get("body") or ""] + [c.get("body") or "" for c in item.get("comments") or []])
    return set(rs.refs(text, repo)) | {tc.ref(item).lower()}, set(re.findall(r"ri-[\w.-]+-\d+", text))


def ri(incident):
    head, tail = incident["id"].split(":", 1)[1].split("~")[0].split("#")
    return "ri-%s-%s" % (head.replace("/", "-"), tail)


def candidate(c, matches, incidents, repo, fresh_after, own=()):
    """Pick the action for one candidate from its matching items; `own` items closed one incident, not the pattern."""
    live = [m for m in matches if (m.get("state") or "").upper() == "OPEN"]
    if live:
        m = min(live, key=lambda m: m["number"])
        refs_, ids = cited(m, repo)
        new = [ri(i) for i in incidents
               if ri(i) not in ids and not set(i["refs"] + i["sites"] + i["reported_by"]) & refs_]
        new += [r for r in c.get("refs", []) if r not in refs_]
        return dict(c, action="append" if new else "none", match=m.get("url"), new=new)
    done = sorted((m for m in matches if m.get("closedAt") and tc.ref(m).lower() not in own),
                  key=lambda m: m["closedAt"])
    if not done:
        return dict(c, action="file")
    m = done[-1]
    fresh = fresh_after(rs.when(m["closedAt"]))
    if fresh:
        return dict(c, action="file", regression_of=m.get("url"), fresh=fresh)
    return dict(c, action="skip", match=m.get("url"), reason="closed %s, no occurrence after" % tc.ref(m).lower())


def run(a):
    with open(a.index, encoding="utf-8") as f:
        index = json.load(f)
    items, missing = [], []
    for path in a.forge or []:
        items += rs.load(path)
    if not a.forge:
        missing.append("forge: not provided")
    repos = {tc.repo_of(i).lower() for i in items}
    repo = repos.pop() if len(repos) == 1 else ""
    by_ref = {tc.ref(i).lower(): i for i in items}

    def matching(cls, extra=()):
        return [i for r, i in by_ref.items() if r in extra or "rp-%s-" % cls in (i.get("body") or "")
                or tc.slug(tc.card(i, "Failure class").split()[0] if tc.card(i, "Failure class") else "") == cls]

    out = []
    by_class = {}
    for i in index["incidents"]:
        for k in i["keys"]:
            if k.startswith("class:"):
                by_class.setdefault(k[6:], []).append(i)
    for cls, group in sorted(by_class.items()):
        if len(group) < THRESHOLD:
            continue
        c = {"basis": "class", "class": cls, "proposal_prefix": "rp-%s-" % tc.slug(cls), "count": len(group),
             "incidents": [ri(i) for i in group]}
        out.append(candidate(c, matching(tc.slug(cls)), group, repo,
                             lambda t, g=group: [ri(i) for i in g if rs.when(first(i)) > t],
                             {r for i in group for r in i["refs"] + i["reported_by"]}))

    if a.buffer is None:
        missing.append("findings: no --buffer")
    else:
        with open(a.buffer, encoding="utf-8") as f:
            buffer = rows(f.read(), repo)
        for row in buffer:
            if row["count"] < THRESHOLD:
                continue
            cls = tc.slug(row["title"])
            linked = [i for i in index["incidents"]
                      if set(i["refs"] + i["sites"] + i["reported_by"]) & set(row.get("refs", []))]
            c = {"basis": "findings", "class": cls, "proposal_prefix": "rp-%s-" % cls, "count": row["count"],
                 "title": row["title"], "refs": row.get("refs", []), "incidents": [ri(i) for i in linked]}

            def fresh(t, row=row, linked=linked):
                late = [ri(i) for i in linked if rs.when(first(i)) > t]
                if row.get("date") and rs.when(row["date"]).date() > t.date():
                    late.append("row-date-%s" % row["date"])
                return late

            if row.get("status") in FIXED:
                fix = [by_ref[r] for r in row["status_refs"] if r in by_ref and by_ref[r].get("closedAt")]
                if not fix:
                    out.append(dict(c, action="skip", reason="fixed by %s, fix date unknown" % (
                        ", ".join(row["status_refs"]) or "an unnamed fix")))
                    continue
                got = candidate(c, fix, linked, repo, fresh)
                if got["action"] != "skip":
                    got = candidate(got, fix + matching(cls), linked, repo, fresh)
                out.append(got)
                continue
            batched = row["status_refs"] if row.get("status") == "batched" else []
            out.append(candidate(c, matching(cls, batched), linked, repo, fresh))
    return {"window": index.get("window"), "sha": index.get("sha"), "missing": missing, "candidates": out}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--index", required=True)
    p.add_argument("--forge", action="append")
    p.add_argument("--buffer")
    a = p.parse_args(argv)
    try:
        result = run(a)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print("reflection-candidates: unreadable input: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
