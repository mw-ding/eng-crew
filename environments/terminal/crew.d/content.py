"""Compare a verified patch with its tool-updated patch without editing either tree.

Usage: crew content VERIFIED_BASE VERIFIED_HEAD UPDATED_BASE UPDATED_HEAD --repo DIR [--project FILE]
Exit 0 prints content=identical carried-from=<full SHA>; exit 1 prints content=different route=builder.
Only blob-index hashes and hunk positions are ignored; whitespace, paths, modes and binary changes count.
This is content evidence, never approval, merge permission or a CI result.
"""
import re
import subprocess


def identical(repo, verified_base, verified_head, updated_base, updated_head):
    patches = []
    for base, head in ((verified_base, verified_head), (updated_base, updated_head)):
        r = subprocess.run([
            "git", "-C", repo, "diff", "--binary", "--full-index", "--no-ext-diff", "--no-textconv",
            "--no-renames", "--no-color", "--no-relative", "--src-prefix=a/", "--dst-prefix=b/",
            "--diff-algorithm=myers", "--unified=0", "--submodule=short", base, head, "--",
        ], capture_output=True)
        if r.returncode:
            raise RuntimeError(r.stderr.decode().strip())
        patch = re.sub(rb"^index [0-9a-f]+\.\.[0-9a-f]+(?: [0-7]+)?\n", b"", r.stdout, flags=re.M)
        patches.append(re.sub(rb"^@@ -[0-9,]+ \+[0-9,]+ @@[^\n]*\n", b"@@\n", patch, flags=re.M))
    return patches[0] == patches[1]


def register(sub):
    p = sub.add_parser("content", help="compare verified and updated patches (read only)")
    for name in ("verified_base", "verified_head", "updated_base", "updated_head"):
        p.add_argument(name)
    p.add_argument("--repo", required=True)
    p.add_argument("--project")


def run(args):
    try:
        refs = []
        for name in ("verified_base", "verified_head", "updated_base", "updated_head"):
            r = subprocess.run(["git", "-C", args.repo, "rev-parse", "--verify", "--end-of-options",
                                getattr(args, name) + "^{commit}"], capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError(r.stderr.strip())
            refs.append(r.stdout.strip())
        if identical(args.repo, *refs):
            print("content=identical carried-from=" + refs[1])
            return 0
        print("content=different route=builder")
    except RuntimeError as e:
        print("content=unverified route=builder: " + str(e))
    return 1
