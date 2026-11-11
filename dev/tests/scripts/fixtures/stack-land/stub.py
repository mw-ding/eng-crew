#!/usr/bin/env python3
"""Stub forge and stack-land backend for the stack-land lab (#1614).

`stub.py --serve SOCKET` reads the scenario state as JSON on stdin and serves it from memory on a Unix socket, so no
state or log file exists while a session runs; a `{"dump": true}` request returns the final state and the call log,
then exits. Installed as `gh` and `exstack` on the session's PATH, the same file is a client: it sends its argv and
cwd to $STACK_LAB_SOCKET and prints the reply. Every call is logged verbatim (tool, argv, exit). The server answers
the reads a session synthesizer makes (PR, reviews and markers, item comments, checks, default-branch runs) and
never reaches a network.

exstack land-stack <stack>: the declared change.land-stack; logs the request, exits state["land_stack_exit"]
(nonzero plays a lost acknowledgement) and advances nothing else. exstack stack-status <stack>: plays
state["stack_status"] in order, keeping the last. `gh pr merge` is a per-PR land request: logged, refused.
Anything else exits 1 with `stub: unsupported`, so an unexpected call shows in the log rather than passing.
"""
import contextlib
import io
import json
import os
import re
import socket
import socketserver
import subprocess
import sys

STATE, LOG, CWD, ARGV, SLURP = {}, [], [os.getcwd()], [[]], [False]


def opt(args, *names, flag=False):
    """Pop an option (and its value unless flag) from args; returns the value, True, or None."""
    for i, a in enumerate(args):
        for n in names:
            if a == n:
                del args[i]
                return True if flag else args.pop(i)
            if a.startswith(n + "="):
                del args[i]
                return a.split("=", 1)[1]
    return None


def emit(data, jq):
    text = json.dumps(data, indent=1)
    if jq:
        r = subprocess.run(["jq", "-r", jq], input=text, capture_output=True, text=True)
        sys.stdout.write(r.stdout)
        sys.stderr.write(r.stderr)
        return r.returncode
    print(text)
    return 0


def body_of(args):
    path = opt(args, "--body-file", "-F")
    if isinstance(path, str):
        path = path[len("body=@"):] if path.startswith("body=@") else path
        with open(os.path.join(CWD[0], path)) as f:
            return f.read()
    return opt(args, "--body", "-b", "-f") or ""


def pr_json(state, n):
    pr = state["prs"][str(n)]
    return dict(pr, number=n, reviews=[dict(r, state="COMMENTED") for r in pr["reviews"]],
                labels=[{"name": x} for x in pr["labels"]], statusCheckRollup=pr["checks"],
                commits=[{"oid": pr["headRefOid"]}], files=[{"path": p} for p in pr["files"]],
                closingIssuesReferences=[{"number": pr["issue"]}])


def rest_review(r, i):
    return {"id": 1000 + i, "user": {"login": r["author"]["login"]}, "body": r["body"], "state": "COMMENTED",
            "commit_id": r["commit"]["oid"], "submitted_at": r["submittedAt"]}


def gh(args):
    state = STATE
    jq = opt(args, "--jq", "-q")
    opt(args, "-R", "--repo")
    fields = opt(args, "--json")
    for f in ("--paginate", "--slurp", "--required", "--name-only", "--comment", "-i", "--include"):
        opt(args, f, flag=True)
    cmd = args[:2]
    if cmd in (["pr", "view"], ["pr", "checks"], ["pr", "diff"], ["pr", "review"], ["pr", "edit"],
               ["pr", "merge"]) and len(args) > 2:
        n = args[2].lstrip("#")
        if n not in state["prs"]:
            print("stub: no PR %s" % n, file=sys.stderr)
            return 1
        pr = state["prs"][n]
        if cmd == ["pr", "view"]:
            data = pr_json(state, int(n))
            if fields:
                data = {k: data.get(k) for k in fields.split(",")}
            return emit(data, jq)
        if cmd == ["pr", "checks"]:
            rows = [{"name": c["name"], "state": c["conclusion"] if c["status"] == "COMPLETED" else "PENDING",
                     "bucket": {"SUCCESS": "pass", "FAILURE": "fail"}.get(c["conclusion"], "pending"),
                     "link": "https://ci.example/run/%s" % c["name"]} for c in pr["checks"]]
            code = emit(rows, jq) if fields or jq else print("\n".join("%s\t%s" % (r["name"], r["bucket"])
                                                                       for r in rows)) or 0
            return code or (1 if any(r["bucket"] == "fail" for r in rows) else
                            8 if any(r["bucket"] == "pending" for r in rows) else 0)
        if cmd == ["pr", "diff"]:
            print("\n".join(pr["files"]))
            return 0
        if cmd == ["pr", "review"]:
            body = body_of(args)
            pr["reviews"].append({"author": {"login": state["self"]}, "body": body,
                                  "commit": {"oid": pr["headRefOid"]}, "submittedAt": "2026-11-11T12:00:00Z"})
            return 0
        if cmd == ["pr", "edit"]:
            while True:
                add, rm = opt(args, "--add-label"), opt(args, "--remove-label")
                if not add and not rm:
                    break
                pr["labels"] = [x for x in pr["labels"] if x != rm] + ([add] if add and add not in pr["labels"] else [])
            return 0
        print("stub: per-PR merge refused in the stack lab; stack members land through change.land-stack",
              file=sys.stderr)
        return 1
    if cmd == ["pr", "list"]:
        rows = [pr_json(state, int(n)) for n in sorted(state["prs"], key=int)]
        if fields:
            rows = [{k: r.get(k) for k in fields.split(",")} for r in rows]
        return emit(rows, jq)
    if cmd == ["issue", "view"] and len(args) > 2:
        n = args[2].lstrip("#")
        issue = state["issues"].get(n, {"comments": [], "labels": []})
        data = {"number": int(n), "state": "OPEN", "title": "item %s" % n, "body": "",
                "labels": [{"name": x} for x in issue["labels"]], "comments": issue["comments"]}
        if fields:
            data = {k: data.get(k) for k in fields.split(",")}
        return emit(data, jq)
    if cmd == ["repo", "view"]:
        return emit({"defaultBranchRef": {"name": "main"}, "nameWithOwner": "acme/widgets"}, jq)
    if cmd in (["run", "list"], ["run", "view"]):
        runs = [{"databaseId": 900 + i, "headSha": sha, "headBranch": "main", "event": "push", "status": "completed",
                 "conclusion": "success", "name": "repo-guard", "workflowName": "repo-guard"}
                for i, sha in enumerate(state["main_runs"])]
        if cmd == ["run", "view"]:
            runs = [r for r in runs if str(r["databaseId"]) == (args[2] if len(args) > 2 else "")][:1]
            return emit(runs[0] if runs else {}, jq) if runs else 1
        return emit(runs, jq)
    if args[:1] == ["api"]:
        method = (opt(args, "-X", "--method") or "GET").upper()
        rest = [a for a in args[1:] if not a.startswith("-")]
        path = rest[0].lstrip("/").split("?")[0] if rest else ""
        m = re.fullmatch(r"repos/acme/widgets/(pulls|issues)/(\d+)(/reviews|/comments)?(?:/(\d+))?", path)
        if m and m.group(1) == "pulls" and m.group(3) == "/reviews" and m.group(2) in state["prs"]:
            pr = state["prs"][m.group(2)]
            if method == "GET":
                return emit([rest_review(r, i) for i, r in enumerate(pr["reviews"])], jq)
            body = body_of(args)
            if method == "PUT" and m.group(4):
                pr["reviews"][int(m.group(4)) - 1000]["body"] = body
            else:
                pr["reviews"].append({"author": {"login": state["self"]}, "body": body,
                                      "commit": {"oid": pr["headRefOid"]}, "submittedAt": "2026-11-11T12:00:00Z"})
            return 0
        if m and m.group(1) == "pulls" and not m.group(3) and m.group(2) in state["prs"]:
            pr = state["prs"][m.group(2)]
            return emit({"number": int(m.group(2)), "state": "open", "merged": False, "draft": False,
                         "mergeable": True, "mergeable_state": "clean", "body": pr["body"],
                         "head": {"sha": pr["headRefOid"], "ref": pr["headRefName"]},
                         "base": {"ref": pr["baseRefName"]}, "labels": [{"name": x} for x in pr["labels"]]}, jq)
        if m and m.group(1) == "issues" and m.group(3) == "/comments":
            if m.group(2) in state["prs"]:
                return emit([], jq)
            comments = state["issues"].get(m.group(2), {"comments": []})["comments"]
            rows = [{"id": 2000 + i, "user": {"login": c["author"]["login"]}, "body": c["body"],
                     "created_at": c["createdAt"]} for i, c in enumerate(comments)]
            return emit([rows] if SLURP[0] else rows, jq)
        if m and m.group(1) == "issues" and not m.group(3):
            src = state["prs"].get(m.group(2)) or state["issues"].get(m.group(2), {"labels": []})
            return emit({"number": int(m.group(2)), "state": "open",
                         "labels": [{"name": x} for x in src["labels"]]}, jq)
        if re.fullmatch(r"repos/acme/widgets/(branches|git/ref/heads|git/refs/heads)/main", path):
            return emit({"name": "main", "commit": {"sha": state["main"]}, "object": {"sha": state["main"]}}, jq)
        m = re.fullmatch(r"repos/acme/widgets/compare/([^.]+)\.\.\.(.+)", path)
        if m:
            return emit({"status": "ahead", "behind_by": 0, "ahead_by": 1,
                         "merge_base_commit": {"sha": state["main"]}}, jq)
        if re.fullmatch(r"repos/acme/widgets/(issues/\d+/(events|timeline)|issues/events)", path):
            return emit([], jq)
        if re.fullmatch(r"repos/acme/widgets/actions/runs", path):
            return emit({"workflow_runs": [{"id": 900 + i, "head_sha": s, "head_branch": "main", "event": "push",
                                            "status": "completed", "conclusion": "success", "name": "repo-guard"}
                                           for i, s in enumerate(state["main_runs"])]}, jq)
        m = re.fullmatch(r"repos/acme/widgets/commits/([0-9a-f]+)/(check-runs|status)", path)
        if m:
            ok = m.group(1) in state["main_runs"]
            if m.group(2) == "status":
                return emit({"state": "success" if ok else "pending", "statuses": []}, jq)
            return emit({"check_runs": [{"name": "repo-guard", "status": "completed", "conclusion": "success"}]
                         if ok else []}, jq)
    print("stub: unsupported: gh %s" % " ".join(ARGV[0]), file=sys.stderr)
    return 1


def exstack(args):
    state = STATE
    if args[:1] == ["land-stack"]:
        return state["land_stack_exit"]
    if args[:1] == ["stack-status"]:
        seq = state["stack_status"]
        state["stack_status"] = seq[1:] or seq
        print(seq[0])
        return 0
    print("stub: unsupported: exstack %s" % " ".join(args), file=sys.stderr)
    return 1


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        req = json.loads(self.rfile.readline())
        if req.get("dump"):
            self.wfile.write((json.dumps({"state": STATE, "log": LOG}) + "\n").encode())
            self.server.done = True
            return
        tool, argv = req["tool"], req["argv"]
        CWD[0], ARGV[0], SLURP[0] = req["cwd"], argv, "--slurp" in argv
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = (exstack if tool == "exstack" else gh)(list(argv))
            except Exception as e:  # a malformed call is the session's problem, never the server's
                print("stub: error: %r" % e, file=sys.stderr)
                code = 1
        LOG.append({"tool": tool, "argv": argv, "exit": code})
        self.wfile.write((json.dumps({"code": code, "out": out.getvalue(), "err": err.getvalue()}) + "\n").encode())



def serve(path):
    STATE.update(json.load(sys.stdin))
    server = socketserver.UnixStreamServer(path, Handler)
    server.done = False
    print("ready", flush=True)
    while not server.done:
        server.handle_request()
    server.server_close()
    os.remove(path)


def client():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(os.environ["STACK_LAB_SOCKET"])
    s.sendall((json.dumps({"tool": os.path.basename(sys.argv[0]), "argv": sys.argv[1:], "cwd": os.getcwd()})
               + "\n").encode())
    reply = json.loads(s.makefile().readline())
    sys.stdout.write(reply["out"])
    sys.stderr.write(reply["err"])
    return reply["code"]


if __name__ == "__main__":
    if sys.argv[1:2] == ["--serve"]:
        serve(sys.argv[2])
    else:
        sys.exit(client())
