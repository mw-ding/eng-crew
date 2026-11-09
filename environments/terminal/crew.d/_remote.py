"""Remote runs on the primary (docs/runtimes/multi-device.md#remote-call-and-runner): spawn, probe and kill a role
run on its placed host through the hardened call (crew-remote.py, #345), and attach, capture and logs (#348). A run
record with `remote` set ran on its `host`; every call carries the project, the host's root and this primary's name,
and retries with the same request id while the transport fails, at most 3 calls in a row, so a retried spawn never
opens a second window.
"""
import importlib.util
import os
import re

spec = importlib.util.spec_from_file_location("crew_remote", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "remote", "crew-remote.py"))
REMOTE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(REMOTE)


def host_of(rec):
    """The run's host when it ran on a role host, else None."""
    return rec.get("host") if rec.get("remote") else None


def scope(values, host):
    """The fields every call carries: the project, this primary's name and the host's root."""
    primary = next((k.split(".")[1] for k, v in values.items() if k.startswith("hosts.") and k.endswith(".primary")
                    and v), None)
    return dict(project=values["repo.owner"] + "__" + values["repo.name"], primary=primary,
                root=values.get("hosts.%s.root" % host, "~/.mdstack"))


def call(values, host, verb, **fields):
    fields.update(scope(values, host))
    for _ in range(3):
        reply = REMOTE.call(host, verb, **fields)
        if reply["result"] != "unreachable":
            return reply
        fields["request_id"] = reply.get("request_id")
    return reply


def spawn(values, state, name, rec, brief, worktree=None, ref=None):
    """Start the run on its host in wt/<worktree> at rec's head fetched from ref, carrying the brief and the PR's
    review files; with no worktree, relaunch the kept run in its own worktree with this brief."""
    with open(brief, encoding="utf-8") as f:
        fields = dict(window=name, role=rec["role"], engine=rec["engine"], model=rec["model"], effort=rec["effort"],
                      permission_mode=values["runtime.options.permission_mode"], brief=f.read(),
                      identity=values["identities.%s.gh_user" % rec["role"]])
    if worktree is None:
        return call(values, rec["host"], "spawn", relaunch=True, **fields)
    pr, verdicts, folder = re.search(r"PR #(\d+)", rec["item"]), {}, os.path.join(state, "verdicts")
    for n in sorted(os.listdir(folder)) if pr and os.path.isdir(folder) else []:
        if n.startswith("pr%s-%s-" % (pr.group(1), rec["head"][:7])) and n.endswith("-review.md"):
            with open(os.path.join(folder, n), encoding="utf-8") as f:
                verdicts[n] = f.read()
    return call(values, rec["host"], "spawn", worktree_path="wt/" + worktree, sha=rec["head"], ref=ref,
                verdicts=verdicts, **fields)


def probe(values, name, rec):
    """C5 liveness from the host, or `unreachable` when the transport fails."""
    reply = call(values, rec["host"], "probe", window=name)
    return reply["liveness"] if reply["result"] == "ok" else "unreachable" if reply["result"] == "unreachable" \
        else "ambiguous"


def kill(values, name, rec, discard=False, keep=False):
    """Stop the run on its host and remove its worktree there unless it holds unlanded work against the default
    branch, the worktree's own branch and the run's PR heads."""
    prs = set(re.findall(r"PR #(\d+)", rec["item"])) | {str(n) for n in (rec.get("pr"), rec.get("args", {}).get("pr")) if n}
    refs = ["refs/heads/" + values["repo.default_branch"]] + ["refs/pull/%s/head" % n for n in sorted(prs)]
    return call(values, rec["host"], "kill", window=name, refs=refs, discard=discard, keep=keep)


def attach(values, name, rec, rw=False):
    """This terminal on the run's pane on its host (`ssh -t` to the attach verb); the ssh exit code, 255 unreachable."""
    return REMOTE.attach(rec["host"], window=name, rw=rw, **scope(values, rec["host"]))


def capture(values, name, rec):
    return call(values, rec["host"], "capture", window=name)


def logs(values, name, rec, lines):
    return call(values, rec["host"], "logs", window=name, lines=lines)
