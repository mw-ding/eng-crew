#!/usr/bin/env python3
"""Campaign scenario lint (#1412): steps fail closed and required cases stay recorded.

A `run` step's result is its shell's last exit, so an assertion whose exit is dropped can fail without
failing the step (A03, A05). This lint parses each step and refuses an unhandled assertion: a `test`, `[`,
`false`, `grep -q` (or `--quiet`/`--silent`) or `!` pipeline whose exit is neither the step's result, nor captured
by a following `VAR=$?`, nor handled by a `||` after it, nor guarded by a trailing `|| exit`. A
non-final list item, any item in a loop body and an item in a group whose own exit is dropped all drop
their exit. A `COND && break` (or continue, return, exit, or an assignment) is control flow, not an
assertion. A call to a function defined in the step is an assertion when that function's return can carry
a failure (a nonzero `return`, `false`, or an unguarded assertion at its tail); a helper that runs `exit 1`
itself ends the step. A step that does not parse is refused too. campaign-run.py refuses such a step at run time.

Allowlist (#1677, fail closed): a step may use simple commands, pipelines and `&&`/`||` chains of them; a
simple `|| exit N`/`|| return N` handler or a `|| { ...; exit N; }` group whose last item is an unconditional,
explicitly nonzero `exit N` (or `return N`); `if`/`case` with allowed branches; `for`/`while`/`until` loops
(each body assertion carries `|| exit N`); `name() { ...; }` functions under the return analysis above; and
subshells holding no assertion, `false`, `exit` or `return`. Everything else is refused by name: other brace
groups, a subshell that can fail, a backgrounded (`&`) assertion or compound command, `eval`, `trap`, `return`
outside a function, a non-brace function body, an assertion before `|` and an `exit`/`return` (or handler
group) inside a multi-command pipeline, which runs in a child. In an `if`/`while`/`until` condition only the
final item is the predicate; an earlier assertion there is dropped and refused. `|| false` and `|| exit 0` are
not failure handlers. Nested interpreters (`sh -c`, `python3 -c`) are opaque commands.

A step may carry `"disposition": {"state": "expected-fail" | "accepted", "reason": TEXT}`: a required
case that fails today and is either waiting for a fix (expected-fail) or accepted as is. The reason is
required. The runner reports it as EXPECTED FAIL or ACCEPTED, never PASS.

Every step of a committed scenario is a required case, `<scenario>/<step name>`. With `--base REF`, each
case at the merge base of REF and HEAD must still be a step at head or be listed, with a reason, in
`retired-cases.json` (`{"<case>": "reason"}`) beside the scenarios. Deleting a case together with its
disposition, renaming a step or deleting a whole scenario is caught. check-repo.py runs this (rule
`campaign`) against `origin/main`. Python 3 stdlib only.

Usage: campaign-lint.py DIR [--base REF] [--root REPO]
"""
import argparse
import json
import os
import re
import subprocess
import sys

STATES = ("expected-fail", "accepted")
RETIRED = "retired-cases.json"
SCENARIO = re.compile(r"A\d+\.json")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _sq(s, i):
    return s.index("'", i + 1) + 1


def _bt(s, i):
    j = i + 1
    while s[j] != "`":
        j += 2 if s[j] == "\\" else 1
    return j + 1


def _dq(s, i):
    j = i + 1
    while s[j] != '"':
        if s[j] == "\\":
            j += 2
        elif s.startswith("$(", j):
            j = _sub(s, j)
        elif s[j] == "`":
            j = _bt(s, j)
        else:
            j += 1
    return j + 1


def _sub(s, i):
    j, depth = i + 2, 1
    while True:
        c = s[j]
        if c == "'":
            j = _sq(s, j)
        elif c == '"':
            j = _dq(s, j)
        elif c == "`":
            j = _bt(s, j)
        elif c == "\\":
            j += 2
        elif c == "(":
            depth, j = depth + 1, j + 1
        elif c == ")":
            depth, j = depth - 1, j + 1
            if not depth:
                return j
        else:
            j += 1


def tokens(src):
    """(kind, text) pairs: "w" words (quotes, $() and backticks kept opaque) and "op" operators.
    Comments and here-document bodies are dropped."""
    out, word, heredocs, i, n = [], None, [], 0, len(src)

    def flush():
        nonlocal word
        if word is not None:
            out.append(("w", word))
            word = None

    while i < n:
        c = src[i]
        if c == "\\":
            j = i + 2
        elif c == "'":
            j = _sq(src, i)
        elif c == '"':
            j = _dq(src, i)
        elif c == "`":
            j = _bt(src, i)
        elif src.startswith("$(", i):
            j = _sub(src, i)
        elif src.startswith("<<<", i):
            j = i + 3
        elif c == "#" and word is None:
            while i < n and src[i] != "\n":
                i += 1
            continue
        elif src.startswith("<<", i):
            flush()
            m = re.match(r"<<-?[ \t]*(['\"]?)([\w.-]+)\1", src[i:])
            heredocs.append(m.group(2))
            out.append(("w", m.group(0)))
            i += m.end()
            continue
        elif c in " \t":
            flush()
            i += 1
            continue
        elif c == "\n":
            flush()
            out.append(("op", "\n"))
            i += 1
            for tag in heredocs:
                m = re.compile(r"^\t*%s$" % re.escape(tag), re.M).search(src, i)
                i = m.end() + 1 if m else n
            heredocs = []
            continue
        else:
            op = next((o for o in ("&&", "||", ";;") if src.startswith(o, i)), c if c in ";&|()" else None)
            if op and not (op in "&|" and word is not None and word.endswith((">", "<"))):
                flush()
                out.append(("op", op))
                i += len(op)
                continue
            j = i + 1
        word = (word or "") + src[i:j]
        i = j
    flush()
    return out


class Parser:
    """Just enough POSIX sh grammar to know whose exit status reaches whom. A list is a list of items;
    an item is [(pipeline, "&&" | "||" | None)]; a pipeline is {"bang", "cmds"}."""

    def __init__(self, src):
        self.t, self.i, self.bg = tokens(src), 0, set()

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def skip(self, *ops):
        while self.peek()[0] == "op" and self.peek()[1] in ops:
            self.i += 1

    def word(self, *ws):
        return self.peek()[0] == "w" and self.peek()[1] in ws

    def expect(self, w):
        if self.peek()[1] != w:
            raise ValueError("expected %r at token %d, got %r" % (w, self.i, self.peek()[1]))
        self.i += 1

    def parse(self):
        items = self.items()
        if self.peek()[0] is not None:
            raise ValueError("unexpected %r at token %d" % (self.peek()[1], self.i))
        return items

    def items(self, stops=(), stop_op=None):
        out = []
        while True:
            self.skip("\n", ";", "&")
            k, v = self.peek()
            if k is None or (k == "w" and v in stops) or (k == "op" and v in (")", stop_op)):
                return out
            item = []
            while True:
                item.append([self.pipeline(stops), None])
                if self.peek()[1] not in ("&&", "||") or self.peek()[0] != "op":
                    break
                item[-1][1] = self.peek()[1]
                self.i += 1
                self.skip("\n")
            out.append([tuple(x) for x in item])
            if self.peek() == ("op", "&"):
                self.bg.add(id(out[-1]))

    def pipeline(self, stops):
        bang = self.word("!")
        self.i += bang
        cmds = [self.command(stops)]
        while self.peek() == ("op", "|"):
            self.i += 1
            self.skip("\n")
            cmds.append(self.command(stops))
        return {"bang": bang, "cmds": cmds}

    def body(self, end):
        b = self.items(stops=(end,))
        self.expect(end)
        return b

    def command(self, stops):
        k, v = self.peek()
        if (k, v) == ("op", "("):
            self.i += 1
            c = {"type": "group", "body": self.items(), "subshell": True}
            self.expect(")")
        elif k != "w":
            raise ValueError("unexpected %r at token %d" % (v, self.i))
        elif v == "{":
            self.i += 1
            c = {"type": "group", "body": self.body("}")}
        elif v == "if":
            self.i += 1
            bodies, conds = [], []
            while True:
                conds.append(self.items(stops=("then",)))
                self.expect("then")
                bodies.append(self.items(stops=("elif", "else", "fi")))
                if self.word("else"):
                    self.i += 1
                    bodies.append(self.items(stops=("fi",)))
                kw = self.peek()[1]
                self.i += 1
                if kw == "fi":
                    break
                if kw != "elif":
                    raise ValueError("unterminated if at token %d" % self.i)
            c = {"type": "branch", "bodies": bodies, "conds": conds}
        elif v in ("while", "until", "for"):
            self.i += 1
            conds = []
            if v == "for":
                while not self.word("do"):
                    if self.peek()[0] is None:
                        raise ValueError("unterminated for")
                    self.i += 1
            else:
                conds.append(self.items(stops=("do",)))
            self.expect("do")
            c = {"type": "loop", "body": self.body("done"), "conds": conds}
        elif v == "case":
            while not self.word("in"):
                self.i += 1
            self.i += 1
            bodies = []
            while True:
                self.skip("\n")
                if self.word("esac"):
                    self.i += 1
                    break
                while self.peek() != ("op", ")"):
                    self.i += 1
                self.i += 1
                bodies.append(self.items(stops=("esac",), stop_op=";;"))
                self.skip(";;")
            c = {"type": "branch", "bodies": bodies}
        else:
            words = []
            while self.peek()[0] == "w" and not (not words and self.peek()[1] in stops):
                words.append(self.peek()[1])
                self.i += 1
            if len(words) == 1 and self.t[self.i:self.i + 2] == [("op", "("), ("op", ")")]:
                self.i += 2
                self.skip("\n")
                return {"type": "func", "name": words[0], "body": self.command(stops)}
            return {"type": "simple", "words": words}
        while self.peek()[0] == "w" and self.peek()[1] not in stops:
            self.i += 1
        return c


def _words(pipe):
    c = pipe["cmds"][-1]
    return [w for w in c.get("words", []) if not ASSIGN.match(w)] if c["type"] == "simple" else None


def is_assertion(pipe, fns=()):
    w = _words(pipe)
    if pipe["bang"] or (w and (w[0] in ("test", "[", "false") or w[0] in fns)):
        return True
    return bool(w) and w[0] in ("grep", "egrep", "fgrep") and any(
        a in ("--quiet", "--silent") or re.match(r"-[A-Za-z]*q", a) for a in w[1:])


def _wrap(cmd):
    """A function body (any compound command) as a one-item list whose result is the function's."""
    return [[({"bang": False, "cmds": [cmd]}, None)]]


def _pipes(items):
    """Every pipeline in ITEMS, nested bodies included, with the functions defined there."""
    for item in items:
        for p, _ in item:
            yield p
            for c in p["cmds"]:
                if c["type"] == "func":
                    yield from _pipes(_wrap(c["body"]))
                for b in [c.get("body")] if c["type"] in ("group", "loop") else c.get("bodies", []):
                    yield from _pipes(b)


def _tail_fails(items, fns):
    """Whether the exit of ITEMS (a body whose result is kept) can be an assertion's failure."""
    if not items:
        return False
    item = items[-1]
    if len(item) > 1 and item[-2][1] == "||" and _exits(item[-1][0]):
        return False
    c = item[-1][0]["cmds"][-1]
    if c.get("subshell"):
        return any(_fails(q, fns) for q in _pipes(c["body"]))
    bodies = [c["body"]] if c["type"] == "group" else c["bodies"] if c["type"] == "branch" else []
    return any(op != "||" and is_assertion(p, fns) for p, op in item) or any(_tail_fails(b, fns) for b in bodies)


def _returns_failure(items):
    """A `false`, or a `return` that is nonzero or bare right after `||`, anywhere in a function body."""
    for item in items:
        for n, (p, _) in enumerate(item):
            w = _words(p) or [""]
            if w[0] == "false" or (w[0] == "return" and (w[1:2] not in ([], ["0"]) or (
                    not w[1:] and n and item[n - 1][1] == "||"))):
                return True
            for c in p["cmds"]:
                if c["type"] == "func":
                    continue
                for b in [c["body"]] if c["type"] in ("group", "loop") else c.get("bodies", []):
                    if _returns_failure(b):
                        return True
    return False


def fallible(items):
    """Names of the functions defined in ITEMS whose return status can carry a failure: a nonzero or bare
    `return` (a bare one keeps the last failed status) or `false` in the body, or an unguarded assertion (or
    call to another such function, or a subshell that can fail) at its tail. A function that exits on failure
    ends the step itself, so it does not count; an `exit` inside a subshell does not end the step."""
    fns = {c["name"]: c["body"] for p in _pipes(items) for c in p["cmds"] if c["type"] == "func"}
    out = set()
    while True:
        more = set()
        for name, body in fns.items():
            if name not in out and (_returns_failure(_wrap(body)) or _tail_fails(_wrap(body), out)):
                more.add(name)
        if not more:
            return out
        out |= more


def _exits(pipe):
    """Whether PIPE ends the step (or, for `return`, the function) with a failure: a bare or nonzero `exit`
    or `return`, or a handler group (`_handler`), alone in its pipeline. `false`, `exit 0`, a subshell's
    `exit` and an `exit` inside a multi-command pipeline (a child) do not."""
    if len(pipe["cmds"]) != 1:
        return False
    c = pipe["cmds"][-1]
    if c["type"] == "group":
        return _handler(c)
    return c["type"] == "simple" and c["words"][:1] in (["exit"], ["return"]) and c["words"][1:2] != ["0"]


def _handler(c):
    """A `{ ...; exit N; }` brace group whose last item is an unconditional, explicitly nonzero `exit N` or
    `return N` (a bare one would keep the status of the command before it)."""
    if c["type"] != "group" or c.get("subshell") or not c["body"] or len(c["body"][-1]) != 1:
        return False
    last = c["body"][-1][0][0]["cmds"]
    w = last[0].get("words") or [] if len(last) == 1 else []
    return w[:1] in (["exit"], ["return"]) and len(w) == 2 and w[1] != "0"


def _control(item):
    c = item[-1][0]["cmds"][-1]
    w = c.get("words") or []
    return len(item) > 1 and c["type"] == "simple" and bool(w) and (
        w[0] in ("break", "continue", "return", "exit") or all(ASSIGN.match(x) for x in w))


def _captures(item):
    c = item[0][0]["cmds"][0]
    return len(item) == 1 and c["type"] == "simple" and bool(c["words"]) and all(
        ASSIGN.match(w) and "$?" in w for w in c["words"])


def _show(item):
    text = " ".join(("! " if p["bang"] else "") + " | ".join(
        " ".join(c["words"]) if c["type"] == "simple" else "<%s>" % c["type"] for c in p["cmds"])
        + (" " + op if op else "") for p, op in item)
    return text if len(text) <= 160 else text[:157] + "..."


def _lint(items, kept, found, fns):
    for n, item in enumerate(items):
        ok = (kept and n == len(items) - 1) or (n + 1 < len(items) and _captures(items[n + 1])) or (
            len(item) > 1 and item[-2][1] == "||" and _exits(item[-1][0]))
        if not ok and not _control(item) and any(op != "||" and is_assertion(p, fns) for p, op in item):
            found.append(_show(item))
        for p, _ in item:
            for k, c in enumerate(p["cmds"]):
                kept_here = ok and k == len(p["cmds"]) - 1
                if c.get("subshell") and not kept_here and any(_fails(q, fns) for q in _pipes(c["body"])):
                    found.append("unsupported: a subshell with an assertion, `false`, `exit` or `return` whose "
                                 "exit is dropped (its failure stays local); use `{ ...; }`: " + _show(item))
                elif c["type"] == "group":
                    _lint(c["body"], kept_here, found, fns)
                elif c["type"] in ("branch", "loop"):
                    for cond in c.get("conds", []):
                        _lint(cond, True, found, fns)  # the final item is the predicate; earlier ones drop
                    for b in c["bodies"] if c["type"] == "branch" else []:
                        _lint(b, kept_here, found, fns)
                    if c["type"] == "loop":
                        _lint(c["body"], False, found, fns)
                elif c["type"] == "func":
                    _lint(_wrap(c["body"]), True, found, fns)


def _unsupported(items, fns, bg, found, in_func=False):
    """The allowlist (#1677, fail closed): simple commands, pipelines and `&&`/`||` chains of them; a simple
    `|| exit N`/`|| return N` or `|| { ...; exit N; }` handler; `if`/`case`; `for`/`while`/`until` loops;
    `name() { ...; }` functions; subshells that cannot fail. Every other construct is refused by name."""
    def refuse(what, item):
        found.append("unsupported: %s: %s" % (what, _show(item)))

    for item in items:
        if id(item) in bg and any(is_assertion(p, fns) or any(c["type"] != "simple" for c in p["cmds"])
                                  for p, _ in item):
            refuse("a backgrounded (`&`) assertion or compound command", item)
        for n, (p, _) in enumerate(item):
            for k, c in enumerate(p["cmds"]):
                cmd = [x for x in c.get("words") or [] if not ASSIGN.match(x)]
                if k < len(p["cmds"]) - 1 and is_assertion({"bang": False, "cmds": [c]}, fns):
                    refuse("an assertion before `|` loses its exit", item)
                if len(p["cmds"]) > 1 and cmd[:1] in (["exit"], ["return"]):
                    refuse("`%s` in a pipeline runs in a child and does not end the step" % cmd[0], item)
                if cmd[:1] in (["eval"], ["trap"]) or (cmd[:1] == ["return"] and not in_func):
                    refuse("`%s`%s" % (cmd[0], " outside a function" if cmd[0] == "return" else ""), item)
                if c["type"] == "func":
                    if c["body"]["type"] != "group" or c["body"].get("subshell"):
                        refuse("function %s: only a `%s() { ...; }` body is supported" % (c["name"], c["name"]),
                               item)
                    for b in [c["body"].get("body")] if c["body"]["type"] == "group" else []:
                        _unsupported(b, fns, bg, found, True)
                    continue
                if c.get("subshell") and any(_fails(q, fns) for q in _pipes(c["body"])):
                    refuse("a subshell with an assertion, `false`, `exit` or `return` (its failure stays local; "
                           "use `git -C`, `cd -` or a plain command)", item)
                elif c["type"] == "group" and not c.get("subshell") and not (
                        n and item[n - 1][1] == "||" and len(p["cmds"]) == 1 and _handler(c)):
                    refuse("a brace group other than a `|| { ...; exit N; }` handler", item)
                for b in ([c["body"]] if c["type"] in ("group", "loop") else c.get("bodies", [])) + c.get("conds", []):
                    _unsupported(b, fns, bg, found, in_func)


def _fails(pipe, fns):
    w = _words(pipe) or [""]
    return is_assertion(pipe, fns) or w[0] in ("false", "exit", "return")


def lint_step(src):
    """Unhandled assertions and unsupported constructs in one step's shell, as short text; raises ValueError
    if it does not parse."""
    found = []
    try:
        parser = Parser(src)
        tree = parser.parse()
        fns = fallible(tree)
        _unsupported(tree, fns, parser.bg, found)
        _lint(tree, True, found, fns)
    except (IndexError, AttributeError) as e:
        raise ValueError("unterminated quote, substitution or here-document (%s)" % type(e).__name__)
    return found


def step_problems(step):
    """Problems with one step: unhandled assertions, a parse failure or a malformed disposition."""
    out = []
    if "run" in step:
        try:
            out += [f if f.startswith("unsupported: ") else
                    "unhandled assertion (chain it into the step's result or add `|| exit 1`): " + f
                    for f in lint_step(step["run"])]
        except ValueError as e:
            out.append("step does not parse: %s" % e)
    d = step.get("disposition")
    if d is not None and not (isinstance(d, dict) and d.get("state") in STATES
                              and isinstance(d.get("reason"), str) and d["reason"].strip()):
        out.append("disposition needs a state (%s) and a reason" % " or ".join(STATES))
    return out


def cases(docs):
    """{case id: step} from {scenario id: parsed scenario}."""
    return {"%s/%s" % (sid, st["name"]): st for sid, sc in docs.items() for st in sc.get("steps", [])}


def load_dir(d):
    """Scenarios and retired cases in D; a missing D has none (deleting every scenario is still checked)."""
    docs = {}
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if SCENARIO.fullmatch(name):
            with open(os.path.join(d, name)) as fh:
                docs[name[:-5]] = json.load(fh)
    retired = {}
    if os.path.isfile(os.path.join(d, RETIRED)):
        with open(os.path.join(d, RETIRED)) as fh:
            retired = json.load(fh)
    return docs, retired


def load_base(root, rel, base):
    """Scenarios at the merge base of BASE and HEAD under repo-relative dir REL."""
    git = ["git", "-C", root]
    mb = subprocess.run(git + ["merge-base", base, "HEAD"], capture_output=True, text=True)
    if mb.returncode:
        raise ValueError("cannot find the merge base of %s and HEAD: %s" % (base, mb.stderr.strip()))
    sha = mb.stdout.strip()
    ls = subprocess.run(git + ["ls-tree", "--name-only", sha, rel + "/"], capture_output=True, text=True, check=True)
    docs = {}
    for path in ls.stdout.split():
        if SCENARIO.fullmatch(os.path.basename(path)):
            show = subprocess.run(git + ["show", "%s:%s" % (sha, path)], capture_output=True, text=True, check=True)
            docs[os.path.basename(path)[:-5]] = json.loads(show.stdout)
    return sha, docs


def check(d, base=None, root=None):
    """All problems for scenario dir D, as "where: what" lines; with BASE, also the retention check."""
    docs, retired = load_dir(d)
    probs = ["%s: %s" % (cid, p) for cid, st in cases(docs).items() for p in step_problems(st)]
    for cid, why in sorted(retired.items()):
        if not (isinstance(why, str) and why.strip()):
            probs.append("%s: %s needs a non-empty reason" % (RETIRED, cid))
            del retired[cid]
    if base:
        root = root or subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True,
                                      text=True, check=True).stdout.strip()
        rel = os.path.relpath(os.path.realpath(d), os.path.realpath(root))
        sha, old = load_base(root, rel, base)
        now = cases(docs)
        probs += ["%s: required case at %s is gone; keep the step, give it a disposition, or retire it with a "
                  "reason in %s" % (cid, sha[:12], RETIRED)
                  for cid in sorted(cases(old)) if cid not in now and cid not in retired]
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir")
    ap.add_argument("--base", help="compare required cases against the merge base of this ref and HEAD")
    ap.add_argument("--root", help="repository root (default: the dir's git top level)")
    args = ap.parse_args(argv)
    try:
        probs = check(args.dir, args.base, args.root)
    except (ValueError, subprocess.CalledProcessError) as e:
        print("campaign-lint: %s" % e, file=sys.stderr)
        return 2
    for p in probs:
        print(p)
    print("campaign-lint: %s (%d problem%s)" % ("FAILED" if probs else "OK", len(probs), "" if len(probs) == 1 else "s"),
          file=sys.stderr)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
