#!/usr/bin/env python3
"""A non-git version control stand-in for the pack commit pin tests (#1326), run in the working copy.

fake-vcs.py commit    records every file's hash in .fakevcs/ and a new revision id
fake-vcs.py status    prints each file changed since the last commit; nothing when clean
fake-vcs.py rev       prints the current revision id
"""
import hashlib
import json
import os
import sys

STORE = ".fakevcs"


def snapshot():
    out = {}
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d != STORE]
        for name in files:
            path = os.path.relpath(os.path.join(root, name))
            with open(path, "rb") as f:
                out[path] = hashlib.sha256(f.read()).hexdigest()
    return out


def main(cmd):
    if cmd == "commit":
        os.makedirs(STORE, exist_ok=True)
        files = snapshot()
        with open(os.path.join(STORE, "state.json"), "w") as f:
            json.dump({"rev": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:12],
                       "files": files}, f)
        return 0
    try:
        with open(os.path.join(STORE, "state.json")) as f:
            state = json.load(f)
    except OSError:
        print("fake-vcs: not a working copy", file=sys.stderr)
        return 255
    if cmd == "rev":
        print(state["rev"])
    else:
        files = snapshot()
        for path in sorted(set(files) | set(state["files"])):
            if files.get(path) != state["files"].get(path):
                print("M " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
