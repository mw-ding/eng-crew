#!/usr/bin/env python3
"""Renderer for eng-crew: resolved profile + inputs to role briefs and runtime artifacts. Python 3.11+ stdlib only.

Usage: crew-render.py --project FILE [--org-profile FILE] [--inputs DIR] --out DIR
Inputs (default: the repo's templates/): core/<role>.md for each role, if core/ exists -> briefs/<role>.md;
runtimes/<runtime>/** of the profile's runtime -> runtime/**; backends/<backend>.toml maps each
<op:concern.operation> to a command.
Fails closed: every problem (an unknown placeholder, a missing mapping, an unsupported capability) prints as
`file:line: reason`; exit 1 and write nothing if any, else 0.
Placeholder map: scripts/README.md (Renderer).
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("crew_config", os.path.join(HERE, "crew-config.py"))
crew_config = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crew_config)

ROLES = ["coordinator", "builder", "reviewer", "synthesizer"]
# Install-time placeholder -> resolved profile keys (docs/profile.md "Replaces"); several keys must agree.
MAPPED = {
    "owner": ["repo.owner"], "repo": ["repo.name"], "default-branch": ["repo.default_branch"],
    "author-login": ["identities.%s.gh_user" % r for r in ["coordinator", "builder", "synthesizer"]],
    "reviewer-login": ["identities.reviewer.gh_user"], "user-logins": ["identities.owners"],
    "state-dir": ["paths.state_dir"], "worktree-root": ["paths.worktree_root"], "toolchain-bin": ["paths.toolchain_bin"],
    "train-min": ["runtime.options.train_min"], "train-window": ["runtime.options.train_window"],
    "eng-crew": ["paths.eng_crew"], "merge-grant": ["runtime.options.merge_grant"],
    "hold-label-blocks": ["runtime.options.hold_label_blocks"], "timezone": ["runtime.timezone"], "fallback-engine": ["engines.fallback_engine"],
    "CoordinatorBot": ["identities.coordinator.name"], "BuilderBot": ["identities.builder.name"],
    "ReviewerBot": ["identities.reviewer.name"], "SynthesizerBot": ["identities.synthesizer.name"],
}
# Run-time placeholders (templates/README.md, docs/roles.md): filled per task, kept verbatim.
KEPT = {"n", "sha7", "head-sha", "k", "pass", "role", "pass|changes", "cmd", "comment id", "note", "parent",
        "planned | applied | live", "date", "reason", "issue#", "pr", "tier", "engine", "model", "effort",
        "UTC timestamp", "file", "full-40-char-head-sha", "new-head-sha", "gate", "run-id", "worktree",
        "branch", "t", "M", "login", "project", "url", "id", "item", "status-field", "option", "tag",
        "APPROVE|REQUEST_CHANGES"}
TOKEN = re.compile(r"<([^<>\s!/=-][^<>\n]*)>")
OP = re.compile(r"op:(.*)\.(.*)")


def resolve(project, org):
    """Resolve the layered profile with crew_config.resolve_profile; return ({dotted key: value}, problems)."""
    merged, _, problems, _ = crew_config.resolve_profile(project, org)
    if problems:
        return None, problems
    return dict(crew_config.leaves(merged)), []


class Renderer:
    def __init__(self, values, inputs):
        self.values, self.inputs, self.tables = values, inputs, {}

    def table(self, path):
        if path not in self.tables:
            try:
                with open(path, "rb") as f:
                    self.tables[path] = tomllib.load(f)
            except (OSError, tomllib.TOMLDecodeError):
                self.tables[path] = {}
        return self.tables[path]

    def op(self, concern, op):
        if op not in crew_config.OPERATIONS.get(concern, []):
            raise ValueError("unknown operation %s.%s" % (concern, op))
        backend = self.values["backends.%s.name" % concern]
        manifest = self.table(os.path.join(os.path.dirname(HERE), "packs", backend, "manifest.toml"))
        cap = self.values.get("backends.%s.capabilities.%s" % (concern, op),
                              manifest.get("capabilities", {}).get(concern, {}).get(op, "unsupported"))
        if cap == "unsupported":
            raise ValueError("unsupported capability %s.%s (backend %s)" % (concern, op, backend))
        cmd = self.table(os.path.join(self.inputs, "backends", backend + ".toml")).get(concern, {}).get(op)
        if not isinstance(cmd, str):
            raise ValueError("missing mapping: no command for %s.%s in backends/%s.toml" % (concern, op, backend))
        return cmd

    def fill(self, m):
        name = m.group(1)
        if OP.fullmatch(name):
            return self.line(self.op(*OP.fullmatch(name).groups()))
        if name in KEPT:
            return m.group(0)
        if name not in MAPPED:
            raise ValueError("unknown placeholder <%s>" % name)
        keys = MAPPED[name]
        missing = [k for k in keys if k not in self.values]
        if missing:
            raise ValueError("missing mapping: <%s> needs %s, not set in the resolved profile" % (name, missing[0]))
        if len({json.dumps(self.values[k]) for k in keys}) > 1:
            raise ValueError("missing mapping: <%s> is ambiguous (%s differ)" % (name, ", ".join(keys)))
        value = self.values[keys[0]]
        if isinstance(value, bool):
            return json.dumps(value)
        return '", "'.join(value) if isinstance(value, list) else str(value)

    def line(self, text):
        return TOKEN.sub(self.fill, text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--org-profile")
    ap.add_argument("--inputs", default=os.path.join(os.path.dirname(HERE), "templates"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    values, problems = resolve(args.project, args.org_profile)
    jobs = []
    if values is not None:
        if os.path.isdir(os.path.join(args.inputs, "core")):
            jobs = [(os.path.join(args.inputs, "core", r + ".md"), os.path.join("briefs", r + ".md"), r) for r in ROLES]
        rt_dir = os.path.join(args.inputs, "runtimes", values["runtime.name"])
        if not os.path.isdir(rt_dir):
            problems.append("%s:1: missing mapping: no runtime binding for %s" % (rt_dir, values["runtime.name"]))
        for root, dirs, names in os.walk(rt_dir):
            dirs.sort()
            jobs += [(os.path.join(root, n), os.path.join("runtime", os.path.relpath(os.path.join(root, n), rt_dir)), None)
                     for n in sorted(names)]
    renderer, rendered = Renderer(values, args.inputs), {}
    for src, dst, role in jobs:
        try:
            with open(src, encoding="utf-8") as f:
                lines = f.read().splitlines(keepends=True)
        except (OSError, UnicodeDecodeError) as e:
            problems.append("%s:1: missing mapping: no brief for role %s (%s)" % (src, role, e) if role else
                            "%s:1: cannot read (%s)" % (src, e))
            continue
        out = []
        for i, text in enumerate(lines, 1):
            try:
                out.append(renderer.line(text))
            except ValueError as e:
                problems.append("%s:%d: %s" % (src, i, e))
        rendered[dst] = "".join(out)
    for p in problems:
        print(p)
    if problems:
        print("crew-render: FAILED (%d problem%s)" % (len(problems), "" if len(problems) == 1 else "s"), file=sys.stderr)
        return 1
    for dst, text in rendered.items():
        path = os.path.join(args.out, dst)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(path)
    print("crew-render: OK (%d files)" % len(rendered), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
