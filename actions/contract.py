#!/usr/bin/env python3
"""Actions contract conformance kit (actions/cli.md): the public contract tests a pack runs in its own CI.

Usage: contract.py PACK_DIR      (or: mdstack pack test PACK_DIR)

Loads the pack with core/crew-pack.py, then runs each check against its adapters with fakes, printing one
`ok|FAIL <kind> <name>: <check>` line per check. Exit 0 when every check passes, 1 otherwise.

Connector: the manifest passes the built-in validator; an [actions] table names an `entry` (pack-relative; a .py runs
with this Python) and declares actions/README.md capabilities per action (undeclared is unsupported). The entry runs
under a fake project and state dir (CREW_ACTIONS_FAKE) and must keep the CLI contract: --capabilities equals the
declaration; every result is one JSON envelope whose outcome agrees with the exit code; an unknown action is refused
as usage (exit 2); an unsupported action is refused as unsupported (exit 6); a short --head is refused; without --json
stdout is one `<outcome>: <action>` line. Harness: the adapter keeps the module interface every built-in adapter has
(harnesses/crew-harness.py), and its launch, coordinator and login argv run a fake executable placed first on PATH.
Python 3.11+ stdlib only.
"""
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT = "eng-crew.actions/0.1"
# actions/cli.md Commands: command name -> operations (empty: the action takes none).
ACTIONS = {
    "read": [], "resolve-policy": [], "check-ownership": [], "claim": ["acquire", "release"], "heartbeat": [],
    "notify": [], "ack": [], "wait": [], "report": [], "spawn-worker": [], "supervise": ["probe", "stop", "restart"],
    "workspace": ["create", "remove"], "artifact": ["write", "append", "update", "remove"], "post-marker": [],
    "tracker": ["create", "edit", "assign", "place", "label", "close"], "run-check": [],
    "publish-change": ["open", "upload", "publish", "prune"], "update-base": [], "compare-content": [],
    "land": ["acquire", "request", "status", "finish", "release"], "owner-channel": ["ask", "update", "close"],
    "knowledge-read": [], "knowledge-propose-edit": [],
}
EXITS = {0: "completed", 2: "refused", 3: "pending", 4: "unknown", 5: "stale", 6: "refused", 7: "failed"}
FIELDS = ["contract", "action", "op", "outcome", "reason", "refs", "result", "capability", "key", "observed_at"]
KEBAB = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
HEAD = "0123456789abcdef0123456789abcdef01234567"
FAKE_MODEL = "fake-model"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def envelope(stdout, code, action, op):
    """Problems with one --json result: one object, every field, outcome agreeing with the exit code."""
    try:
        result = json.loads(stdout)
    except ValueError:
        return None, ["stdout is not exactly one JSON object"]
    if not isinstance(result, dict):
        return None, ["stdout is not exactly one JSON object"]
    out = ["missing field %r" % f for f in FIELDS if f not in result]
    if out:
        return result, out
    if result["contract"] != CONTRACT:
        out.append("contract %r, expected %r" % (result["contract"], CONTRACT))
    if (result["action"], result["op"]) != (action, op):
        out.append("names %s %s, expected %s %s" % (result["action"], result["op"], action, op))
    if code not in EXITS:
        out.append("exit %d is no defined outcome" % code)
    elif result["outcome"] != EXITS[code]:
        out.append("outcome %r disagrees with exit %d (%s)" % (result["outcome"], code, EXITS[code]))
    reason = result["reason"]
    if result["outcome"] == "completed" and reason is not None:
        out.append("completed with a reason")
    if result["outcome"] != "completed" and not (isinstance(reason, dict) and isinstance(reason.get("text"), str)
                                                 and KEBAB.fullmatch(str(reason.get("code")))):
        out.append("reason must be {code: kebab-case, text}")
    if not isinstance(result["refs"], dict) or not isinstance(result["result"], dict):
        out.append("refs and result must be objects")
    if not isinstance(result["key"], str) or not UTC.fullmatch(str(result["observed_at"])):
        out.append("key must be a string and observed_at a UTC time YYYY-MM-DDTHH:MM:SSZ")
    return result, out


def connector(name, manifest_path, cfg):
    """[(check, problems)] for one connector's manifest and actions/ binding."""
    with open(manifest_path, "rb") as f:
        manifest = tomllib.load(f)
    problems = []
    cfg.validate_manifest(manifest, lambda k, r: problems.append("%s: %s" % (k, r)), os.path.dirname(manifest_path),
                          external_pin=False)
    checks = [("manifest validates", problems)]
    actions = manifest.get("actions")
    if actions is None:
        return checks
    declared, bad = {}, []
    for key, value in actions.items():
        if key == "entry":
            continue
        if key not in ACTIONS:
            bad.append("unknown action %r (actions/cli.md Commands)" % key)
        elif not isinstance(value, str) or not cfg.CAPABILITY.fullmatch(value):
            bad.append("%s: expected supported, unsupported or emulated (<how>)" % key)
        else:
            declared[key] = value
    entry = os.path.realpath(os.path.join(os.path.dirname(manifest_path), str(actions.get("entry", ""))))
    if not isinstance(actions.get("entry"), str) or not entry.startswith(os.path.realpath(os.path.dirname(
            manifest_path)) + os.sep) or not os.path.isfile(entry):
        bad.append("actions.entry must name a file in the connector directory")
    checks.append(("actions declaration", bad))
    if bad:
        return checks
    with tempfile.TemporaryDirectory(prefix="crew-contract-") as fake:
        project = os.path.join(fake, "crew.toml")
        with open(project, "w") as f:
            f.write("# fake project for the actions conformance kit\n")
        env = dict(os.environ, CREW_ACTIONS_FAKE=fake)
        base = [sys.executable, entry] if entry.endswith(".py") else [entry]

        def call(*argv):
            try:
                proc = subprocess.run(base + list(argv), capture_output=True, text=True, env=env, timeout=60)
            except subprocess.TimeoutExpired:
                return 4, ""
            return proc.returncode, proc.stdout

        code, stdout = call("--capabilities", "--json")
        try:
            caps = json.loads(stdout).get("capabilities")
        except (ValueError, AttributeError):
            caps = None
        want = {a: declared.get(a, "unsupported").split(" ")[0] for a in ACTIONS}
        checks.append(("--capabilities equals the declaration", [] if code == 0 and isinstance(caps, dict) and {
            a: caps.get(a, "unsupported") for a in ACTIONS} == want else ["exit %d, capabilities %r" % (code, caps)]))
        code, stdout = call("crew-conformance-unknown", "--json")
        result, out = envelope(stdout, code, "crew-conformance-unknown", None)
        if result and not out and (code, (result["reason"] or {}).get("code")) != (2, "usage"):
            out.append("exit %d reason %r, expected exit 2 usage" % (code, result["reason"]))
        checks.append(("unknown action is refused as usage", out))
        common = ["--project", project, "--role", "builder", "--item", "1", "--head", HEAD, "--json"]
        for action, ops in ACTIONS.items():
            op = ops[0] if ops else None
            code, stdout = call(*([action] + ([op] if op else []) + common))
            result, out = envelope(stdout, code, action, op)
            word = declared.get(action, "unsupported").split(" ")[0]
            if result and not out and word == "unsupported" and (code, (result["reason"] or {}).get("code")) != (
                    6, "unsupported"):
                out.append("declared unsupported: exit %d reason %r, expected exit 6 unsupported" % (code, result["reason"]))
            if result and not out and word != "unsupported" and result["capability"] != word:
                out.append("capability %r, declared %r" % (result["capability"], word))
            checks.append(("%s%s keeps the envelope" % (action, " " + op if op else ""), out))
        supported = [a for a in declared if not declared[a].startswith("unsupported")]
        for action in supported[:1]:
            op = ACTIONS[action][0] if ACTIONS[action] else None
            code, stdout = call(*([action] + ([op] if op else []) + common[:-3] + ["--head", HEAD[:7], "--json"]))
            result, out = envelope(stdout, code, action, op)
            if result and not out and result["outcome"] != "refused":
                out.append("a 7-character --head gave %r, expected refused" % result["outcome"])
            checks.append(("%s refuses a short --head" % action, out))
            code, stdout = call(*([action] + ([op] if op else []) + common[:-1]))
            line = stdout.splitlines()
            ok = len(line) == 1 and re.fullmatch(r"(completed|pending|stale|refused|failed|unknown): %s%s\b.*" % (
                re.escape(action), " " + op if op else ""), line[0])
            checks.append(("%s without --json prints one outcome line" % action, [] if ok else ["stdout %r" % stdout]))
    return checks


def harness(name, mod):
    """[(check, problems)] for one harness adapter: the module interface, and its argv run against a fake executable."""
    out = []
    exe = getattr(mod, "EXECUTABLE", None)
    if not isinstance(exe, str) or not exe or "/" in exe:
        out.append("EXECUTABLE must be a bare command name")
    if not isinstance(getattr(mod, "TITLE", None), str):
        out.append("TITLE must be a string")
    for attr in ("ENGINE_RANK", "LAUNCH_RANK"):
        if hasattr(mod, attr) and type(getattr(mod, attr)) is not int:
            out.append("%s must be an integer" % attr)
    for i, pair in enumerate(getattr(mod, "PROMPTS", [])):
        try:
            assert len(pair) == 2
            [re.compile(p) for p in pair]
        except (AssertionError, TypeError, re.error):
            out.append("PROMPTS[%d] must be a (question, footer) pair of regexes" % i)
    for attr in ("FATAL", "TRANSIENT", "BUSY"):
        value = getattr(mod, attr, None)
        try:
            if value is not None and not isinstance(value, re.Pattern):
                re.compile(value)
        except (TypeError, re.error):
            out.append("%s must be a regex" % attr)
    checks = [("module interface", out)]
    if out:
        return checks
    with tempfile.TemporaryDirectory(prefix="crew-contract-") as fake:
        bindir, log = os.path.join(fake, "bin"), os.path.join(fake, "argv.log")
        os.makedirs(bindir)
        with open(os.path.join(bindir, exe), "w") as f:
            f.write('#!/bin/sh\nfor a in "$@"; do printf "%%s\\n" "$a"; done > %s\n' % shlex.quote(log))
        os.chmod(os.path.join(bindir, exe), 0o755)
        env = dict(os.environ, PATH=bindir + os.pathsep + os.environ.get("PATH", ""))
        argvs = [("login status", [exe, *getattr(mod, "LOGIN_STATUS", ["auth", "status"])])]
        if hasattr(mod, "role_argv"):
            argvs.append(("role launch", mod.role_argv(FAKE_MODEL, "medium", fake, fake, [])))
        if hasattr(mod, "coordinator_argv"):
            argvs.append(("coordinator launch", mod.coordinator_argv(fake, fake, [])))
        for label, argv in argvs:
            out = []
            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv) or argv[0] != exe:
                out.append("argv must be a list of strings starting with %r: %r" % (exe, argv))
            elif label == "role launch" and not any(FAKE_MODEL in a for a in argv):
                out.append("role argv does not pass the chosen model")
            else:
                proc = subprocess.run(argv, env=env, capture_output=True, timeout=60)
                with open(log) as f:
                    seen = f.read().splitlines() if proc.returncode == 0 else None
                if seen != argv[1:]:
                    out.append("the fake %s did not receive the argv (exit %d)" % (exe, proc.returncode))
            checks.append(("%s runs the executable" % label, out))
    return checks


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    if len(argv) != 1 or argv[0].startswith("-"):
        print(__doc__.split("\n\n")[1])
        return 2
    cfg = load_module("crew_config", "core/crew-config.py")
    pack, problems = load_module("crew_pack", "core/crew-pack.py").load(argv[0], cfg, cfg.harnesses)
    for problem in problems:
        print("FAIL pack: " + problem)
    if not pack:
        return 1
    results = [("connector", n, c) for n, path in sorted(pack["items"]["connectors"].items())
               for c in connector(n, path, cfg)]
    results += [("harness", n, c) for n, mod in sorted(pack["harnesses"].items()) for c in harness(n, mod)]
    failed = 0
    for kind, name, (check, out) in results:
        print("%s %s %s: %s%s" % ("FAIL" if out else "ok", kind, name, check, "".join("\n  " + p for p in out)))
        failed += bool(out)
    print("mdstack pack test: %s (%d checks, %d failed)" % ("FAILED" if failed else "OK", len(results), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
