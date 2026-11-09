"""Remote run lifecycle on the primary (docs/runtimes/multi-device.md#remote-call-and-runner, #345): spawn, probe and
kill a role run on its placed host through the hardened call (crew-remote.py). A run record with `remote` set ran
on its `host`; every call carries the project, the host's root and this primary's name, and retries with the same
request id while the transport fails, at most 3 calls in a row, so a retried spawn never opens a second window.
Remote wakes and messages (#346): `pull` copies new status lines into the primary's status/<window>.status mirror and
`send` delivers an `mdstack send` message through the host.
"""
import base64
import contextlib
import fcntl
import hashlib
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


def call(values, host, verb, attempts=3, **fields):
    primary = next((k.split(".")[1] for k, v in values.items() if k.startswith("hosts.") and k.endswith(".primary")
                    and v), None)
    fields.update(project=values["repo.owner"] + "__" + values["repo.name"], primary=primary,
                  root=values.get("hosts.%s.root" % host, "~/.mdstack"))
    for _ in range(attempts):
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


@contextlib.contextmanager
def pull_lock(state):
    """status/.pull.lock: one pull at a time per crew, so the watcher and `mdstack acked` never append a line twice."""
    os.makedirs(os.path.join(state, "status"), exist_ok=True)
    with open(os.path.join(state, "status", ".pull.lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def pull(values, state, host, names):
    """One `pull` call for the runs `names` on host: append each run's new complete status lines to its primary
    mirror. The mirror's own size is the offset and its SHA-256 proves the prefix, so an interrupted, repeated or
    concurrent pull and a primary restart neither lose nor double a line; a host answering from 0 (its file was
    rewritten, or the mirror is gone or torn) rebuilds the mirror. One attempt: the next scan is the retry."""
    with pull_lock(state):
        mirrors, windows = {}, {}
        for n in names:
            mirrors[n] = os.path.join(state, "status", n + ".status")
            try:
                with open(mirrors[n], "rb") as f:
                    data = f.read()
            except FileNotFoundError:
                data = b""
            windows[n] = dict(offset=len(data), digest=hashlib.sha256(data).hexdigest())
        reply = call(values, host, "pull", attempts=1, windows=windows)
        for n, got in (reply.get("windows") or {}).items() if reply["result"] == "ok" else ():
            if n not in mirrors or not got["size"]:
                continue  # an empty or missing host file never wipes the lines already mirrored
            chunk = base64.b64decode(got["data"])
            if got["offset"] != windows[n]["offset"]:
                with open(mirrors[n] + ".tmp", "wb") as f:
                    f.write(chunk)
                os.replace(mirrors[n] + ".tmp", mirrors[n])
            elif chunk:
                with open(mirrors[n], "ab") as f:
                    f.write(chunk)
        return reply


def send(values, name, rec, message):
    """Deliver an `mdstack send` message through the run's host: its inbox line and nudge are the host's."""
    return call(values, rec["host"], "send", window=name, message=message)


def refresh(values, state, name, rec):
    """A wait_ack refresh for a remote run: pull its status lines into the mirror."""
    return lambda: pull(values, state, rec["host"], [name])
