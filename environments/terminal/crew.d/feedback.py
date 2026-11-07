"""`mdstack feedback` files a `runtime-blocker` intake card upstream when a crew defect blocks or slows a run, or comments
on the open card with the same failure class instead (#299, docs/triage.md T7). Source and run fields come from the
run record of --window; every line is redacted per spec R1 (credentials, emails, box paths) before it is posted.

Usage: mdstack feedback --project FILE [--org-profile FILE] --class SLUG --summary TEXT [--window NAME]
                     [--repo OWNER/REPO] [--sign TEXT] [--dry-run]
--repo defaults to `<repo.owner>/eng-crew`. Prints `filed: <url>`, `commented: <repo>#<n>` or, with --dry-run, the
action and body without posting. Exit 1 on a bad slug, an unreadable card list or refused write ownership.
"""
import json
import os
import re
import subprocess
from crew_shared import crew_render, load, require_ownership

step_summary = load("step_summary", "scripts/step-summary.py")  # its credential redactor: tokens, bearer, URL creds, key=value

SECRET = re.compile(r"\bxox[abprs]-[\w-]{10,}")
ABS_PATH = re.compile(r"(?<![\w<>.:/~-])/[\w.@+-]+(?:/[\w.@+-]*)*")  # left after the known places
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def register(sub):
    p = sub.add_parser("feedback")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")
    p.add_argument("--class", dest="cls", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--window")
    p.add_argument("--repo")
    p.add_argument("--sign", default="")
    p.add_argument("--dry-run", action="store_true")


def redact(text, places):
    """Spec R1: known box paths become placeholders (longest first), then the home dir, any other absolute path,
    credentials and emails."""
    for path, name in sorted(places.items(), key=lambda kv: -len(kv[0])):
        if path:
            text = text.replace(path, name)
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if os.environ.get(name):
            text = text.replace(os.environ[name], "<redacted>")
    text = ABS_PATH.sub("<path>", text.replace(os.path.expanduser("~"), "<home>"))
    return EMAIL.sub("<email>", SECRET.sub("<redacted>", step_summary.redact(text)))


def gh(*argv, body=None):
    return subprocess.run(["gh", *argv], input=body, capture_output=True, text=True)


def run(args):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.cls):
        print("crew: feedback: --class must be a lowercase slug, e.g. spawn-failure")
        return 1
    values, problems = crew_render.resolve(args.project, args.org_profile)
    if problems:
        print("\n".join(problems))
        return 1
    owner, name = values["repo.owner"], values["repo.name"]
    intake = args.repo or "%s/eng-crew" % owner
    state = os.path.join(os.path.abspath(values["paths.state_dir"]), "%s__%s" % (owner, name))
    rec = {}
    if args.window and os.path.exists(os.path.join(state, "runs", args.window + ".json")):
        with open(os.path.join(state, "runs", args.window + ".json")) as f:
            rec = json.load(f)
    item = re.search(r"#(\d+)", rec.get("item") or "")
    source = "%s/%s#%s" % (owner, name, item[1]) if item else "%s/%s (run blocker, no item)" % (owner, name)
    run_lines = ["- Window: %s (%s)" % (args.window, "no run record" if not rec else "%s, %s" % (
        rec.get("role"), rec.get("item"))) if args.window else "- Window: none"]
    if rec:
        run_lines += ["- Engine: %s %s %s (harness %s)" % tuple(rec.get(k) for k in ("engine", "model", "effort", "harness")),
                      "- Launch args: `%s`" % json.dumps(rec.get("args") or {}, sort_keys=True)]
    run_lines.append("- Summary: " + args.summary)
    places = {os.path.abspath(values["paths.state_dir"]): "<state-dir>",
              os.path.abspath(values.get("paths.worktree_root") or ""): "<worktree>",
              rec.get("worktree") or "": "<worktree>", rec.get("repo") or "": "<repo>"}
    sign = ["", args.sign] if args.sign else []
    listed = gh("issue", "list", "-R", intake, "--state", "open", "--limit", "1000", "--json", "number,body")
    try:
        cards = json.loads(listed.stdout) if not listed.returncode else None
    except ValueError:
        cards = None
    if cards is None:  # fail closed: a blind file would duplicate a card
        print("crew: feedback: cannot list open cards in %s: %s" % (intake, listed.stderr.strip()))
        return 1
    hit = min((c["number"] for c in cards if re.search(
        r"^\*\*Failure class:\*\*[ \t]*%s[ \t]*$" % re.escape(args.cls), c.get("body") or "", re.M)), default=None)
    if hit:
        body = redact("\n".join(["Seen again on %s (trigger `runtime-blocker`)." % source, ""] + run_lines + sign), places)
        argv = ["issue", "comment", str(hit), "-R", intake, "--body-file", "-"]
        done = "commented: %s#%d" % (intake, hit)
    else:
        title = "intake: %s on %s" % (args.cls, source.split(" ")[0])
        body = redact("\n".join([
            "**Source:** " + source, "**Trigger:** runtime-blocker", "**Failure class:** " + args.cls,
            "**Proposed fix:** for triage",
            "**Scope:** crew: - a crew or runtime defect seen during a run (triage: confirm or promote)",
            "**Lesson:** none yet", "**Findings entry:** none yet", "**Decision:** pending", "", "## Run", ""]
            + run_lines + sign), places)
        argv = ["issue", "create", "-R", intake, "--title", title, "--body-file", "-"]
        done = "filed: "
    if args.dry_run:
        print("dry-run: gh %s\n%s" % (" ".join(argv), body))
        return 0
    if not require_ownership(values, "write"):
        return 1
    posted = gh(*argv, body=body + "\n")
    if posted.returncode:
        print("crew: feedback: gh %s failed: %s" % (argv[1], posted.stderr.strip()))
        return 1
    print(done + (posted.stdout.strip() if done == "filed: " else ""))
    return 0
