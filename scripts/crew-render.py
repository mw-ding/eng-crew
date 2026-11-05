#!/usr/bin/env python3
"""Renderer for eng-crew: resolved profile + inputs to role briefs and runtime artifacts. Python 3.11+ stdlib only.

Usage: crew-render.py --project FILE [--org-profile FILE] [--inputs DIR] [--diff-paths FILE] --out DIR
Inputs (default: the repo's templates/): core/<role>.md for each role, if core/ exists -> briefs/<role>.md;
runtimes/<runtime>/** of the profile's runtime -> runtime/**; backends/<backend>.toml maps each
<op:concern.operation> to a command, and its [placeholders] kept list declares extra run-time placeholders.
Pack overlay: a render/ directory in the org profile's directory (else paths.pack) is searched per file
before the inputs. runtime.options.notes.render files are appended verbatim to that role's rendered brief.
Fails closed: every problem (an unknown placeholder, a missing mapping, an unsupported capability) prints as
`file:line: reason`; exit 1 and write nothing if any, else 0.
Placeholder map: scripts/README.md (Renderer).
Enabled builder.precheck appends ordered steps and profile commands to builder briefs.
Flavor placeholders use the project preset/custom knobs; --diff-paths supplies newline-separated
repo-relative paths (both rename paths) for class rigor. Without paths, classes wait for live resolution.
Unset flavor resolves standard and renders its baseline line like an explicit name.
This render baseline supplies no item record or merge authority; explicit precheck settings stay in force.
Grok Bot SKILL.md inputs include the reviewed docs with <include:docs/protocol.md>
or <include:docs/roles.md>. Included docs keep their illustrative placeholders;
relative Markdown links point into the installed bundle, not the skill directory.
Builder and solo session briefs include the PR conventions section from docs/roles.md;
its illustrative placeholders stay literal and its link labels render as plain text.
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

ROLES = crew_config.ROLE_REGISTRY
# Install-time placeholder -> resolved profile keys (docs/profile.md "Replaces"); several keys must agree.
MAPPED = {
    "control-item": ["repo.control_item"], "runtime-id": ["runtime.name", "runtime.instance"],
    "owner": ["repo.owner"], "repo": ["repo.name"], "default-branch": ["repo.default_branch"],
    "author-login": [r["identity_key"] + ".gh_user" for r in ROLES.values() if "identity_independent_of" not in r],
    "reviewer-login": [r["identity_key"] + ".gh_user" for r in ROLES.values() if "identity_independent_of" in r],
    "user-logins": ["identities.owners"],
    "state-dir": ["paths.state_dir"], "worktree-root": ["paths.worktree_root"], "toolchain-bin": ["paths.toolchain_bin"],
    "mirror-deferral": ["runtime.options.mirror_deferral"], "mirror-gate": ["runtime.options.mirror"],
    "max-active-milestones": ["runtime.options.max_active_milestones"],
    "lone-pr-land": ["runtime.options.lone_pr_land"],
    "train-min": ["runtime.options.train_min"], "train-window": ["runtime.options.train_window"],
    "eng-crew": ["paths.eng_crew"], "merge-grant": ["runtime.options.merge_grant"],
    "hold-label-blocks": ["runtime.options.hold_label_blocks"], "timezone": ["runtime.timezone"], "fallback-engine": ["engines.fallback_engine"],
}
for role, metadata in ROLES.items():
    MAPPED[role.title() + "Bot"] = [metadata["identity_key"] + ".name"]
    for field in ("title", "emoji"):
        MAPPED[role.title() + field.title()] = [metadata["identity_key"] + "." + field]
for knob in ("name", "review", "validation", "evidence", "caps", "merge", "builder"):
    MAPPED["flavor-" + knob] = ["flavor." + knob]
MAPPED["flavor-validation-scope"] = ["flavor.validation_scope"]
MAPPED["flavor-selfgate-engine"] = ["flavor.selfgate_engine"]
# <mirror-gate>: the tmux synthesizer's mirror-gate paragraph by runtime.options.mirror (#877, docs/runtimes/tmux.md).
MIRROR_GATE = {
    "live-copy": "Mirror deferral: read the recorded owner decision named by `mirror_deferral`\n"
                 "   unless `none`; verify scope and ensure covered PRs\n"
                 "   do not change live Grok Bot behaviour. These satisfy the mirror gate even with\n"
                 "   `crew:needs-mirror` and no per-PR comment. Record\n"
                 "   `Mirror deferral used: <mirror-deferral>` in the merge post.\n"
                 "   Uncovered PRs, unreadable decisions or live behaviour changes need a real\n"
                 "   mirror. No merge permission is supplied; gate changes need per-PR owner merge-ok.",
    "none": "Mirror: `mirror = \"none\"` declares no live copy outside the render, so the\n"
            "   mirror gate is `n/a` by profile. Record `Mirror: n/a (profile)` on direct lands\n"
            "   and list no mirror item in gate-status. Never wait on or ask for a mirror or\n"
            "   deferral, and ignore `crew:needs-mirror`. This supplies no approval or merge\n"
            "   permission; every other gate still applies at head.",
}
# Configured check commands named in the reviewer brief; unset renders n/a (#648).
OPTIONAL = {"precheck-lint": "builder.precheck.lint", "precheck-test": "builder.precheck.test"}
MAPPED.update({name: [key] for name, key in OPTIONAL.items()})

# Run-time placeholders (templates/README.md, docs/roles.md): filled per task, kept verbatim.
KEPT = {"n", "sha7", "head-sha", "reviewed-base-sha", "k", "pass", "role", "pass|changes", "cmd", "comment id", "note", "parent",
        "planned | applied | live", "date", "reason", "issue#", "pr", "tier", "engine", "model", "effort",
        "UTC timestamp", "file", "full-40-char-head-sha", "new-head-sha", "gate", "run-id", "worktree",
        "run-url", "harness", "branch", "t", "M", "login", "project", "url", "id", "item", "status-field", "option", "tag",
        "version", "APPROVE|REQUEST_CHANGES", "sweep-id", "outcome", "band", "shadow|apply"}
TOKEN = re.compile(r"<([^<>\s!/=-][^<>\n]*)>")
OP = re.compile(r"op:(.*)\.(.*)")
PLACEHOLDER = re.compile(r"[a-z][a-z0-9-]*")


def pack_overlay(project, org, values):
    """The pack's render/ overlay: beside the org profile, else under paths.pack; None when absent."""
    if org:
        base = os.path.dirname(os.path.abspath(org))
    elif values.get("paths.pack"):
        base = os.path.join(os.path.dirname(os.path.abspath(project)), os.path.expanduser(values["paths.pack"]))
    else:
        return None
    overlay = os.path.join(base, "render")
    return overlay if os.path.isdir(overlay) else None


def resolve(project, org, paths=None):
    """Resolve the layered profile with crew_config.resolve_profile; return ({dotted key: value}, problems)."""
    merged, _, problems, _ = crew_config.resolve_profile(project, org)
    if problems:
        return None, problems
    flavor = merged["flavor"]
    named = dict(crew_config.FLAVOR_PRESETS)
    for name, knobs in flavor.get("custom", {}).items():
        named[name] = dict(named[knobs["base"]], **{k: v for k, v in knobs.items() if k != "base"})
    name = flavor["name"]
    knobs = dict(named[name])
    if paths is not None:
        try:
            knobs.update(crew_config.class_flavor(merged, paths)["rigor"])
        except ValueError as e:
            return None, ["diff-paths:1: " + str(e)]
        keys = set(crew_config.FLAVOR_ORDER) | {"caps"}
        if any(knobs[k] != named[name][k] for k in keys):
            name = next((n for n, candidate in named.items() if all(knobs[k] == candidate[k] for k in keys)), "mixed")
    values = dict(crew_config.leaves(merged))
    values.update({"flavor." + k: v for k, v in knobs.items()})
    values["flavor.name"] = name
    values["flavor.selfgate_engine"] = flavor.get("selfgate_engine", "different")  # read only for express changes
    return values, []


class Renderer:
    def __init__(self, values, inputs, normalize_paths=False, overlay=None):
        self.values, self.inputs, self.tables = values, inputs, {}
        self.normalize_paths, self.overlay, self.kept = normalize_paths, overlay, set()

    def find(self, *parts):
        """An input file: the pack overlay's copy when present, else the inputs' copy."""
        if self.overlay and os.path.isfile(os.path.join(self.overlay, *parts)):
            return os.path.join(self.overlay, *parts)
        return os.path.join(self.inputs, *parts)

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
        mapping = self.table(self.find("backends", backend + ".toml"))
        cmd = mapping.get(concern, {}).get(op)
        if not isinstance(cmd, str):
            raise ValueError("missing mapping: no command for %s.%s in backends/%s.toml" % (concern, op, backend))
        kept = mapping.get("placeholders", {}).get("kept", [])
        if not isinstance(kept, list) or not all(isinstance(k, str) and PLACEHOLDER.fullmatch(k) for k in kept):
            raise ValueError("invalid placeholders.kept in backends/%s.toml: expected a list of names "
                             "([a-z][a-z0-9-]*)" % backend)
        clash = sorted(set(kept) & set(MAPPED))
        if clash:
            raise ValueError("invalid placeholders.kept in backends/%s.toml: <%s> is an install-time placeholder"
                             % (backend, clash[0]))
        return cmd, set(kept)

    def fill(self, m):
        name = m.group(1)
        if name in ("include:docs/protocol.md", "include:docs/roles.md", "include:docs/roles.md#pr-conventions"):
            source = os.path.join(os.path.dirname(HERE), name[len("include:"):].split("#", 1)[0])
            try:
                with open(source, encoding="utf-8") as f:
                    text = f.read()
                if name.endswith("#pr-conventions"):
                    text = text.split("## PR conventions\n", 1)[1].split("## Parallelism\n", 1)[0]
                    text = ("## PR conventions\n" + text).rstrip()
                    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
            except (OSError, UnicodeDecodeError) as e:
                raise ValueError("cannot read included doc %s (%s)" % (source, e)) from e
            bundle = "<path>" if self.normalize_paths else self.values["paths.eng_crew"].rstrip("/")

            def link(match):
                target = match.group(1)
                if target.startswith(("#", "/")) or re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    return match.group(0)
                return "](" + bundle + "/" + os.path.normpath("docs/" + target) + ")"

            return re.sub(r"\]\(([^)\s]+)\)", link, text)
        if OP.fullmatch(name):
            cmd, kept = self.op(*OP.fullmatch(name).groups())
            outer, self.kept = self.kept, kept
            try:
                return self.line(cmd)
            finally:
                self.kept = outer
        if name in KEPT or name in self.kept:
            return m.group(0)
        if name in OPTIONAL:
            command = str(self.values.get(OPTIONAL[name], "")).strip()
            return "`%s`" % (command or "n/a")
        if name not in MAPPED:
            raise ValueError("unknown placeholder <%s>" % name)
        if name == "control-item":
            return str(self.values.get("repo.control_item", "none"))
        if name == "mirror-gate":
            return self.line(MIRROR_GATE[self.values.get("runtime.options.mirror", "live-copy")])
        if name == "runtime-id":
            return self.values["runtime.name"] + "@" + self.values.get("runtime.instance", "unconfigured")
        keys = MAPPED[name]
        missing = [k for k in keys if k not in self.values]
        if missing:
            raise ValueError("missing mapping: <%s> needs %s, not set in the resolved profile" % (name, missing[0]))
        if len({json.dumps(self.values[k]) for k in keys}) > 1:
            raise ValueError("missing mapping: <%s> is ambiguous (%s differ)" % (name, ", ".join(keys)))
        if self.normalize_paths and all(k.startswith("paths.") for k in keys):
            return "<path>"
        value = self.values[keys[0]]
        if name == "flavor-caps":
            return json.dumps(value)
        if isinstance(value, bool):
            return json.dumps(value)
        return '", "'.join(value) if isinstance(value, list) else str(value)

    def line(self, text):
        return TOKEN.sub(self.fill, text)

    def precheck(self):
        if not self.values.get("builder.precheck.enabled", False):
            return ""
        attempts = self.values.get("builder.precheck.max_fix_attempts", 2)
        commands = {step: self.values.get("builder.precheck." + step, "").strip()
                    for step in ("lint", "test", "docs")}
        lines = ["\n## Builder pre-review check\n\n",
                 "Before handoff, follow protocol.md's builder pre-review check in order:\n\n",
                 "1. Fresh base: fetch and rebase the unpublished branch; use merge-up for an existing PR.\n",
                 "2. Lint / format.\n"]
        for number, step, label in ((2, "lint", "Lint / format"), (3, "test", "Tests / build")):
            if number == 3:
                lines.append("3. Tests / build: gather typed runtime evidence.\n")
                if self.values.get("builder.precheck.owners", "").strip():
                    lines.append("   Pipe the changed paths, one per line, to `scripts/crew-config.py precheck-scope "
                                 "--project <file>` and append its `targets` to the test command. Exit 3 (unowned "
                                 "code) or 4 (owners query failed) stops the check; `tests=n/a` only when every "
                                 "path is no-owner-ok, and list the `no_owner_ok` paths beside the marker.\n")
            lines.append("\n```sh\n%s\n```\n\n" % commands[step] if commands[step] else
                         "\n%s: `n/a` (no configured command).\n\n" % label)
        lines += ["4. Self-review against the acceptance criteria and repo rules.\n",
                  "5. Docs / changelog: update required docs and the changelog.\n",
                  "\n```sh\n%s\n```\n\n" % commands["docs"] if commands["docs"] else
                  "\nDocs command: `n/a` (no configured command).\n\n",
                  "6. Confirm required evidence and inline excerpts.\n",
                  "7. Open the non-draft PR with per-step results and `pass=precheck` at the final full head SHA.\n\n",
                  "Allow at most %d fix attempts per failing command, rerunning after each.\n" % attempts,
                  "Stop and report a base conflict or remaining failure; never loosen tests, lint or checks.\n",
                  "Rerun affected checks if self-review or docs changes the diff. Missing commands are `n/a`,\n",
                  "never `pass`; report build separately as `n/a` if no build command applies.\n",
                  "Publish step results and command output, never self-review reasoning.\n"]
        return "".join(lines)


def main(argv=None, normalize_paths=False):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--org-profile")
    ap.add_argument("--inputs", default=os.path.join(os.path.dirname(HERE), "templates"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--diff-paths", help="file of repo-relative diff paths, including both rename paths")
    args = ap.parse_args(argv)
    paths = None
    if args.diff_paths:
        try:
            with open(args.diff_paths, encoding="utf-8") as f:
                paths = f.read().splitlines()
        except (OSError, UnicodeDecodeError) as e:
            print("%s:1: cannot read diff paths (%s)" % (args.diff_paths, e))
            return 1
    values, problems = resolve(args.project, args.org_profile, paths)
    jobs, overlay = [], None
    if values is not None:
        overlay = pack_overlay(args.project, args.org_profile, values)
        roots = [args.inputs] + ([overlay] if overlay else [])
        if any(os.path.isdir(os.path.join(root, "core")) for root in roots):
            jobs = [("core/%s.md" % r, os.path.join("briefs", r + ".md"), r) for r in ROLES]
        rt = os.path.join("runtimes", values["runtime.name"])
        if not any(os.path.isdir(os.path.join(root, rt)) for root in roots):
            problems.append("%s:1: missing mapping: no runtime binding for %s"
                            % (os.path.join(args.inputs, rt), values["runtime.name"]))
        found = set()
        for root in roots:
            for parent, dirs, names in os.walk(os.path.join(root, rt)):
                found |= {os.path.relpath(os.path.join(parent, n), os.path.join(root, rt)) for n in names}
        jobs += [(os.path.join(rt, rel), os.path.join("runtime", rel), None)
                 for rel in sorted(found, key=lambda rel: [(1, d) for d in rel.split(os.sep)[:-1]] + [(0, rel)])]
    renderer, rendered = Renderer(values, args.inputs, normalize_paths, overlay), {}
    for rel, dst, role in jobs:
        src = renderer.find(rel)
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
        if role == "builder" or dst in ("runtime/builder.md", "runtime/builder-b1.md", "runtime/solo.md"):
            precheck = renderer.precheck()
            if dst == "runtime/builder-b1.md" and precheck:
                prompt, closing = "".join(out).rsplit("\n```", 1)
                out = [prompt, precheck.replace("```", "~~~"), "\n```", closing]
            else:
                out.append(precheck)
        note_role = os.path.splitext(os.path.basename(dst))[0]
        if dst in ("briefs/%s.md" % note_role, "runtime/%s.md" % note_role):
            for path in values.get("runtime.options.notes.render." + note_role, []):
                note = os.path.join(os.path.dirname(os.path.abspath(args.project)), os.path.expanduser(path))
                try:
                    with open(note, encoding="utf-8") as f:
                        out.append("\n## Render note: %s\n\n%s" % (path, f.read()))
                except (OSError, UnicodeDecodeError) as e:
                    problems.append("%s:1: cannot read runtime.options.notes.render.%s file (%s)" % (note, note_role, e))
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
