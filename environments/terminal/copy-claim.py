"""Host-wide working-copy claims across crews (docs/runtimes/multi-device.md#working-copy-claims, #391).

Stdlib only, so the primary and a role host load the same file. A claim is keyed by the copy's canonical host-local
identity: the real path with every symlink and `..` resolved, so two aliases of one copy are one claim. The store is
one directory per host user, shared by every crew and state root there: MDSTACK_COPY_CLAIMS when set (tests; sshd
never forwards it to the remote entrypoint), else ~/.mdstack/copy-claims. A claim records host, path, crew (the
holder's state root), run, item and since; it is published complete with an atomic hard link, so a competing acquire
either wins or reads the whole holder. Only the holder (same crew and run) releases it. No age, liveness guess or
other crew ever reclaims one: a stale claim is released by its holder's cleanup, or removed by hand on the owner's
decision.
"""
import hashlib
import json
import os
import socket
import time
import uuid


def store():
    return os.environ.get("MDSTACK_COPY_CLAIMS") or os.path.expanduser(os.path.join("~", ".mdstack", "copy-claims"))


def identity(path):
    """The copy's canonical path on this host; aliases (symlinks, `..`, a trailing slash) resolve to one."""
    return os.path.realpath(os.path.expanduser(path))


def claim_path(path):
    return os.path.join(store(), hashlib.sha256(identity(path).encode()).hexdigest()[:32] + ".json")


def holder(path):
    """The claim record on the copy, or None."""
    try:
        with open(claim_path(path)) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def describe(rec):
    return "%s claimed by crew %s run %s (%s) since %s" % (rec["path"], rec["crew"], rec["run"], rec["item"],
                                                          rec["since"])


def acquire(path, crew, run, item):
    """Claim the copy for (crew, run), or raise RuntimeError naming the live holder. Re-acquiring one's own claim is
    a no-op, so a relaunch in the same copy keeps it."""
    rec = dict(host=socket.gethostname(), path=identity(path), crew=crew, run=run, item=item,
               since=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    target = claim_path(path)
    os.makedirs(store(), exist_ok=True)
    tmp = "%s.%s.tmp" % (target, uuid.uuid4().hex)
    with open(tmp, "w") as f:
        json.dump(rec, f)
    try:
        os.link(tmp, target)  # atomic: fails if any holder exists
        return rec
    except FileExistsError:
        held = holder(path)
        if held and (held["crew"], held["run"]) == (crew, run):
            return held
        raise RuntimeError("crew: refusing: working copy " + (describe(held) if held else identity(path)))
    finally:
        os.remove(tmp)


def release(path, crew, run):
    """Drop the claim when (crew, run) holds it. No claim is a no-op; another holder raises."""
    held = holder(path)
    if held is None:
        return
    if (held["crew"], held["run"]) != (crew, run):
        raise RuntimeError("crew: refusing release: working copy " + describe(held))
    os.remove(claim_path(path))
