"""`mdstack spawn` creates a role window with its own worktree, engine, identity and brief, and queues beyond the profile
band cap for `mdstack dequeue`.
Refuses solo-labelled builder items before creating a claim, queue entry or window. `researcher --sweep` starts
a triage sweep window, riley-sweep, with no item (docs/triage.md#host, #748); its Item names the queued closed
milestones it takes for a milestone-close sweep (#374). `researcher --docs-pass` starts a docs pass window, riley-docs,
with no item (docs/project-docs.md#docs-pass, #1026); its Item names each repo's scan.json, and it is refused unless
`[docs] enabled` is true. `researcher --reflection WINDOW` starts a reflection run, riley-reflection, with no item
(docs/self-improve.md#reflection, #1520): its run ID, reflection log issue, input SHA and window are fixed at the request,
so a queued, dequeued or restarted run carries them intact; the worktree is at the input SHA. `builder --train N` starts
a train worker, ben-trainN, for the synthesizer's delegated merge train N (#1391); its Item names the delegation record.
With the synthesizer lead installed, `spawn synthesizer` refuses: the lead is the lander (#1569).

With a [hosts] inventory, placement (_placement.py, docs/runtimes/multi-device.md#placement, #207) picks the host and
engine from the profile and live host facts, queues with one reason per host, or refuses; the run record keeps host,
placement and rejections. --host H --reason TEXT overrides the host and posts the reason on the item first; a failed
post spawns nothing. On a role host (#345, _remote.py) the host fetches the head into its mirror, adds the worktree and
starts the harness in its runner's session; the brief (its Worktree line names the host's path) and the PR's review
files travel in the call, and the run record (`remote`), claim and brief copy stay on the primary.
Every worktree is claimed host-wide before it is added (copy-claim.py, docs/runtimes/multi-device.md#working-copy-claims,
#391): another crew's claim refuses the spawn before any worktree or window, and mdstack kill releases it.

Usage: mdstack spawn ROLE --issue N | --pr N | --sweep | --docs-pass | --reflection WINDOW [--log N] [--input-sha SHA]
       [--run-id ID] | --train N [--pass PASS] [--round K] [--tier T] [--host H --reason TEXT] --project FILE [--org-profile FILE]
"""
import collections
import json
import os
import re
import shlex
import time
from crew_shared import (
    BANDS, brief_src, checkout, commands, copy_claim, ENGINE_CMD, fetch, git, harness, identity, kill_run, LAUNCH, NAMES, over_cap, PASSES, POINTER,
    load, profile, queue_lock, remote_run, role_notes, ROLES, runs, show_icon, tmux, wait_harness, window_env, open_trains,
    synthesizer_work)

placement = load("crew_placement", "environments/terminal/crew.d/_placement.py")
# A reflection window ID (docs/self-improve.md#reflection); coalesced windows join with +.
WINDOW = re.compile(r"(?:week-\d{4}-W\d{2}|close-\d+)(?:\+(?:week-\d{4}-W\d{2}|close-\d+))*")


def reflection_of(args):
    """The reflection request's fields, or None: run ID, log issue, input SHA and window (#1520)."""
    window = getattr(args, "reflection", None)
    return window and {"window": window, "run": getattr(args, "run_id", None), "log": getattr(args, "log", None),
                       "sha": getattr(args, "input_sha", None)}


def engine_order(values, tier, avoid=None, role=None):
    """Interactive engines in the role's override order, else the tier's (#597); a reviewer avoids every actual
    builder engine of the PR (roles.md Reviewer engine selection)."""
    key = "engines.roles.%s.order" % role if "engines.roles.%s.order" % role in values else "engines.%s.order" % tier
    order = [e.split("/", 1) for e in values[key]]
    order = [e for e in order if e[0] in ENGINE_CMD and e[0] not in (avoid or ())]
    if not order:
        raise RuntimeError("crew: no %s engine in %s differs from the builder's %s" %
                           ("/".join(ENGINE_CMD), key, sorted(avoid or ())))
    return order


def pick_engine(values, tier, avoid=None, role=None):
    order = engine_order(values, tier, avoid, role)
    return order[0][0], order[0][1], values["engines.%s.effort" % tier]


def host_facts(args, values, session, state):
    """facts(host) for placement: the primary is where spawn runs; another host answers its readiness check. Load is
    this crew's live runs there from the run records; a record without a host ran on the primary."""
    hosts = placement.inventory(values)
    primary = next((h for h in hosts if placement.setting(values, h, "primary", False)), None)
    load = collections.Counter(rec.get("host") or primary for _, rec in runs(state))
    seen = {}

    def facts(h):
        if h not in seen:
            f = dict(reachable=True, ready=True) if h == primary else commands()["host"].inspect_host(
                args, values, session, state, h)
            seen[h] = dict(reachable=f["reachable"], ready=f["ready"], load=load[h])
        return seen[h]
    return facts


def post_override(values, args, name, host, reason):
    """Post the override reason on the PR (narrative post) or issue before the spawn; False if it was not posted."""
    body = "[%s/placement] %s placed on %s by override\n\nReason: %s" % (
        values.get("identities.coordinator.name", "Ash"), name, host, reason)
    cmd = ["pr", "review", str(args.pr), "--comment"] if args.pr else ["issue", "comment", str(args.issue)] \
        if args.issue else None
    try:
        return cmd is not None and commands()["route"].gh(
            *cmd, "-R", "%s/%s" % (values["repo.owner"], values["repo.name"]), "--body", body) is None
    except RuntimeError:
        return False


def builder_engines(values, state, repo, base, sha, pr):
    """The PR's actual builder engines: every `Engine:` line in its commit messages, trailer block or not (#442);
    else the PR-body builder marker and the builder run records for the PR or its closing issues. Unknown refuses."""
    found = {e for e in re.findall(r"^Engine:[ \t]*(\S+)", git(repo, "log", "--format=%B", "%s..%s" % (base, sha)), re.M)
             if e != "none"}
    if found:
        return found
    change = commands()["route"].gh("pr", "view", str(pr), "-R", "%s/%s" % (values["repo.owner"], values["repo.name"]),
                                    "--json", "body,closingIssuesReferences")
    found = set(re.findall(r"<!-- crew:v1 role=builder [^>]*?\bengine=([^\s>]+)", change.get("body") or ""))
    issues = {"issue #%d" % i["number"] for i in change["closingIssuesReferences"]}
    found |= {rec["engine"] for _, rec in runs(state) if rec["role"] == "builder" and (
        rec.get("args", {}).get("pr") == pr or rec["item"].split(",")[0] in issues)}
    if not found:
        raise RuntimeError("crew: refusing spawn: PR #%d's builder engine is unknown (no Engine: line, builder marker "
                           "or builder run record); an unknown engine is never assumed non-Claude" % pr)
    return found


def exclude_crew(wt):
    """Exclude step summaries (.crew/) in the worktree's info/exclude, so they never count as unlanded (#234 N7)."""
    path = os.path.join(wt, git(wt, "rev-parse", "--git-path", "info/exclude"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+", encoding="utf-8") as f:
        f.seek(0)
        if ".crew/" not in f.read().split():
            f.write("\n.crew/\n")


def enqueue(state, args, pass_, reason=None):
    """Append a capped or unplaced spawn request to spawn-queue.jsonl for the coordinator; no window is created."""
    entry = {"role": args.role, "issue": args.issue, "pr": args.pr, "pass": pass_, "round": args.round,
             "tier": args.tier, "head": getattr(args, "head", None), "queued": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if getattr(args, "messages", None):
        entry["messages"] = args.messages
    if getattr(args, "sweep", False):
        entry["sweep"] = True
    if getattr(args, "docs_pass", False):
        entry["docs_pass"] = True
    if getattr(args, "train", None):
        entry["train"] = args.train
    if getattr(args, "rereview_id", None):  # the steer this pass answers, bound to its PR/head/pass/round (#1477)
        entry["rereview_id"] = args.rereview_id
    if reflection_of(args):
        entry["reflection"] = reflection_of(args)
    if reason:
        entry["reason"] = reason
    if getattr(args, "host", None):  # an override survives the queue; dequeue posts its reason at the spawn
        entry["host"], entry["override_reason"] = args.host, args.reason
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "spawn-queue.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")
    if args.role == "builder" and getattr(args, "wake", True):
        with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a") as f:
            f.write(json.dumps(dict(event="builder-queued", reason="spawn")) + "\n")
    print("queued: %s %s %s (%s; run mdstack dequeue when a window closes)" % (
        args.role, pass_, "train %d" % entry["train"] if entry.get("train") else "reflection " + args.reflection if entry.get("reflection") else "sweep" if entry.get("sweep") else "docs pass" if entry.get("docs_pass") else "issue #%s" % args.issue if args.issue else "PR #%s" % args.pr,
        "no host: " + reason if reason else args.role + " cap reached"))
    return 0


def register(sub):
    p = sub.add_parser("spawn")
    p.add_argument("role", choices=sorted(BANDS))
    p.add_argument("--issue", type=int)
    p.add_argument("--pr", type=int)
    p.add_argument("--sweep", action="store_true", help="researcher only: a triage sweep, no item (docs/triage.md)")
    p.add_argument("--docs-pass", action="store_true", help="researcher only: a docs pass, no item (docs/project-docs.md)")
    p.add_argument("--reflection", metavar="WINDOW", help="researcher only: a reflection run, no item (docs/self-improve.md#reflection)")
    p.add_argument("--log", type=int, help="reflection only: the reflection log issue, if one is open")
    p.add_argument("--input-sha", help="reflection only: the input SHA (default: the default branch head at the request)")
    p.add_argument("--run-id", help="reflection only: the run ID (default: minted at the request)")
    p.add_argument("--train", type=int, help="builder only: build the delegated merge train N, no item (#1391)")
    p.add_argument("--pass", dest="pass_", choices=sorted({p for v in PASSES.values() for p in v}))
    p.add_argument("--head", help="expected PR head; refuse a changed head, including a queued spawn")
    p.add_argument("--rereview-id", help="reviewer only, with --pr and --head: the rereview steer this pass answers")
    p.add_argument("--round", type=int, default=1, help="verdict round k, for reviewer window names")
    p.add_argument("--tier", choices=["trivial", "default", "deep"], help="default: the role's default_tier, else default")
    p.add_argument("--timeout", type=float, default=15.0, help="seconds to see the harness in the foreground")
    p.add_argument("--host", help="placement override: run on this inventory host; needs --reason")
    p.add_argument("--reason", help="why the host is overridden; posted on the item before the spawn")
    p.add_argument("--project")
    p.add_argument("--org-profile")


def run(args):
    role = args.role
    data = ROLES[role]
    args.tier = args.tier or data.get("default_tier", "default")  # the researcher's research row: high effort (#584)
    tool = ("toolchain_bin",) if data["lifetime"] == "issue" else ()
    values, session, state = profile(args, "worktree_root", *tool)
    if role == "synthesizer" and commands()["lead"].enabled(state, role):  # its lead lands in window 1 (#1569)
        print("crew: refusing spawn: the synthesizer lead owns lands; run mdstack lead handoff synthesizer land '#N' HEAD")
        return 1
    train = getattr(args, "train", None)
    pass_ = "train" if train else args.pass_ or (data.get("change_pass", PASSES[role][0]) if args.pr else PASSES[role][0])
    inputs = data["inputs"].get(pass_, [])
    sweep, docs_pass = getattr(args, "sweep", False), getattr(args, "docs_pass", False)
    if train and (role != "builder" or args.issue or args.pr or args.pass_ or sweep or docs_pass):
        print("crew: --train is builder-only and takes no --issue, --pr or --pass")
        return 2
    if sweep and (role != "researcher" or args.issue or args.pr or docs_pass):
        print("crew: --sweep is researcher-only and takes no --issue, --pr or --docs-pass")
        return 2
    if docs_pass and (role != "researcher" or args.issue or args.pr):
        print("crew: --docs-pass is researcher-only and takes no --issue or --pr")
        return 2
    reflection = reflection_of(args)
    if not reflection and any(getattr(args, k, None) for k in ("log", "input_sha", "run_id")):
        print("crew: --log, --input-sha and --run-id go with --reflection")
        return 2
    if reflection and (role != "researcher" or args.issue or args.pr or sweep or docs_pass):
        print("crew: --reflection is researcher-only and takes no --issue, --pr, --sweep or --docs-pass")
        return 2
    if getattr(args, "rereview_id", None) and (role != "reviewer" or not args.pr or not getattr(args, "head", None)):
        print("crew: --rereview-id is reviewer-only and needs --pr and --head")
        return 2
    if docs_pass and not values.get("docs.enabled"):
        print("crew: refusing spawn: --docs-pass needs [docs] enabled = true (docs/profile.md#docs)")
        return 1
    if reflection and not (WINDOW.fullmatch(reflection["window"]) and re.fullmatch(r"[0-9a-f]{40}", reflection["sha"] or "0" * 40)
                           and re.fullmatch(r"[\w.+-]+", reflection["run"] or "-")):
        print("crew: --reflection takes a window ID (week-YYYY-Www or close-N, joined by +), --input-sha a full SHA "
              "and --run-id letters, digits and ._+-")
        return 2
    if reflection and not (reflection["sha"] and reflection["run"]):  # fixed now, so a queued run keeps them (#1520)
        try:
            args.input_sha = args.input_sha or fetch(git(checkout(values, args.project), "rev-parse", "--show-toplevel"),
                                                     values["repo.default_branch"])
        except RuntimeError as e:
            print(e)
            return 1
        args.run_id = args.run_id or "%s-%s" % (args.reflection, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
        reflection = reflection_of(args)
    if sweep or docs_pass or reflection:
        inputs = []
    override, reason = getattr(args, "host", None), getattr(args, "reason", None)
    if bool(override) != bool(reason):
        print("crew: --host and --reason go together (the override reason is posted on the item)")
        return 2
    if (pass_ not in PASSES[role] and not train) or bool(args.issue) != ("issue" in inputs) or \
            bool(args.pr) != ("change" in inputs):
        error_inputs = next((v["inputs"][pass_] for v in ROLES.values() if v.get("change_pass") == pass_),
                            data["inputs"][PASSES[role][0]])
        expected = " ".join("--%s N" % ("pr" if i == "change" else i) for i in error_inputs)
        print("crew: %s %s takes %s" % (role, pass_, expected))
        return 2
    if role == "builder":
        try:
            if commands()["lead"].solo(values, args.issue, args.pr):
                print("crew: refusing spawn: solo item belongs to the owner's session")
                return 1
        except RuntimeError as e:
            print(e)
            return 1
    nm = values.get(data["identity_key"] + ".name", NAMES[role]).lower()
    instance = getattr(args, "instance", None)  # mdstack up <role>: an on-demand instance, named by mdstack up (#1231)
    name = instance or data["window_name"].format(name=nm, issue="sweep" if sweep else "docs" if docs_pass else "reflection" if reflection else "train%d" % train if train else args.issue, change=args.pr, round=args.round, **{"pass": pass_})
    if not tmux.has_session(session):
        print("crew: session %s not reachable (tmux socket, or run mdstack up first)" % session)
        return 1
    tmux.pin_layout(session)
    windows = dict((n, i) for i, n in tmux.list_windows(session))
    free = [i for i in range(BANDS[role][0], BANDS[role][1] + 1) if i not in windows.values()]
    if name not in windows and over_cap(values, role, windows, state):
        return enqueue(state, args, pass_)
    if role == "synthesizer" and name not in windows and os.path.exists(os.path.join(state, "runs", name + ".json")):
        if kill_run(values, session, state, name):
            return 1
    src = brief_src(state, role)
    problem = ("%s already running" % name if name in windows else "band %d-%d full" % BANDS[role] if not free
               else "no rendered brief %s (run mdstack up)" % src if not os.path.exists(src) else None)
    if problem:
        print("crew: refusing spawn: " + problem)
        return 1
    try:
        notes = role_notes(values, state, role)
        repo = git(checkout(values, args.project), "rev-parse", "--show-toplevel")
        sha = fetch(repo, "pull/%d/head" % args.pr if args.pr else values["repo.default_branch"])
        if reflection:  # the request's input SHA, never a newer head
            sha = git(repo, "rev-parse", "--verify", reflection["sha"] + "^{commit}")
        if getattr(args, "head", None) and args.head != sha:
            raise RuntimeError("crew: stale spawn: expected %s, live head %s" % (args.head, sha))
        base = fetch(repo, values["repo.default_branch"]) if args.pr else None
        order = engine_order(values, args.tier, role=role) if "engine_independent_of" not in data else engine_order(
            values, args.tier, builder_engines(values, state, repo, base, sha, args.pr), role)
        paths = git(repo, "diff", "--name-only", "%s...%s" % (base, sha)).split() if args.pr and \
            placement.inventory(values) else []
        placed = placement.place(dict(role=role, paths=paths, order=order, host=override, **{"pass": pass_}), values,
                                 host_facts(args, values, session, state))
    except RuntimeError as e:
        print(e)
        return 1
    if placed["result"] == "queue":
        return enqueue(state, args, pass_, placed["reason"])
    primary = next((h for h in placement.inventory(values) if placement.setting(values, h, "primary", False)), None)
    if placed["result"] == "refuse":
        print("crew: refusing spawn: placement: " + placed["reason"])
        return 1
    remote = placed["host"] if placed["host"] != primary else None
    engine, model, effort = placed["engine"], placed["model"], values["engines.%s.effort" % args.tier]
    if override and not post_override(values, args, name, placed["host"], reason):
        print("crew: refusing spawn: override reason not posted on the item")
        return 1
    run = "%s-pr%d-%s" % (role, args.pr, sha[:7]) if args.pr else ""
    run += "-r%d-%s" % (args.round, pass_) if data["lifetime"] == "pass" else ""  # review and validate coexist (#139 F3)
    claim = os.path.join(state, "claims", "%s-train%d" % (role, train) if train else "%s-sweep" % role if sweep else "%s-docs" % role if docs_pass else
                         "%s-reflection" % role if reflection else
                         "%s-%s" % (role, instance) if instance else "%s-issue%s" % (role, args.issue) if not args.pr else run)
    for d in ["claims", "runs", "inbox", "status"]:
        os.makedirs(os.path.join(state, d), exist_ok=True)
    try:
        os.close(os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY))  # atomic claim (protocol §6 step 2)
    except FileExistsError:
        print("crew: refusing spawn: claim %s exists" % claim)
        return 1
    item = ", ".join("issue #%s" % args.issue if i == "issue" else "PR #%d" % args.pr for i in inputs) or \
        ("on demand (mdstack up %s)" % role if instance else "triage sweep (docs/triage.md)")
    if train:
        item = "merge train %d (%s)" % (train, commands()["train"].delegation_path(state, train))
    if docs_pass:  # each repo's scan, docs-scan.py's output path
        item = "docs pass (docs/project-docs.md); scans: " + ", ".join(os.path.join(
            os.path.dirname(state), r.replace("/", "__"), "docs", "scan.json") for r in values["docs.repos"])
    if reflection:
        item = "reflection %s (run %s, input sha %s, log %s)" % (reflection["window"], reflection["run"], sha, "#%d" % reflection[
            "log"] if reflection["log"] else "none given: find or open it")
    milestones = commands()["poll"].triage_untaken(state) if sweep else []  # taken only once the window starts (#374)
    if milestones:
        item += "; milestone close: " + ", ".join("%s milestone %d (%s)" % (m["repo"], m["number"], m["title"])
                                                  for m in milestones)
    wt_name = "%s-%s-%s-%s%s" % (
        args.pr or args.issue or ("train%d" % train if train else "docs" if docs_pass else "reflection" if reflection else instance or "sweep"), sha[:7], role, "r%d-" % args.round if data["lifetime"] == "pass" else "", pass_)
    wt = os.path.join(placement.setting(values, remote, "root", "~/.mdstack"), "wt", wt_name) if remote else \
        os.path.join(os.path.abspath(values["paths.worktree_root"]), wt_name)
    rec = {"index": None if remote else free[0], "role": role, "item": item, "pass": pass_, "repo": repo, "worktree": None, "claim": claim,
           "engine": engine, "model": model, "effort": effort, "harness": ENGINE_CMD[engine], "head": sha,
           "host": placed["host"], "placement": placed["placement"], "rejections": placed["rejections"]}
    if override:
        rec["override_reason"] = reason
    if remote:  # its window and worktree are on the host; the run record, claim and brief copy stay here
        rec["remote"] = True
    if getattr(args, "rereview_id", None):  # on the record before the worker can complete (#1477)
        rec["rereview_id"] = args.rereview_id
    if role == "reviewer":  # the brief's verdict file, removed by mdstack kill
        rec["verdict"] = os.path.join(state, "verdicts", "pr%d-%s-r%d-%s.md" % (args.pr, sha[:7], args.round, pass_))

    def save():
        with open(os.path.join(state, "runs", name + ".json"), "w") as f:
            json.dump(rec, f, indent=2)

    save()
    try:
        real, top = os.path.realpath(wt), os.path.realpath(repo)
        if not remote and (real == top or real.startswith(top + os.sep)):
            raise RuntimeError("crew: refusing spawn: %s is inside the primary checkout %s" % (wt, repo))
        if not remote:  # host-wide, so another crew's run never shares the copy (#391); kill_run releases it
            copy_claim.acquire(wt, state, name, item)
            rec["copy_claim"] = wt
            save()
        if not remote and os.path.lexists(wt):
            raise RuntimeError("crew: refusing spawn: %s exists" % wt)
        if not remote:
            os.makedirs(os.path.dirname(wt), exist_ok=True)
            git(repo, "worktree", "add", "-q", "--detach", wt, sha)
            rec["worktree"] = wt
            save()
            exclude_crew(wt)
        brief = os.path.join(state, "runs", name + ".brief.md")
        with open(src, encoding="utf-8") as f, open(brief, "w", encoding="utf-8") as out:
            out.write(f.read() + commands()["brief"].run_block([
                ("Window", name), ("Item", item), ("Pass", pass_), ("Worktree", wt), ("Base", sha),
                ("Engine", "%s %s %s" % (engine, model, effort)), ("Claim", claim)]))
        prompt = POINTER
        if role == "synthesizer":
            pending = os.path.join(state, "inbox", "synthesizer-pending.jsonl")
            inbox = os.path.join(state, "inbox", name + ".jsonl")
            if os.path.exists(pending):
                os.replace(pending, inbox)
            messages = synthesizer_work(state, name)
            rec["pending_lands"] = [m for m in messages if m["kind"] == "land"]
            trains = open_trains(state)
            if trains or messages:
                prompt += " Resume open trains: %s. Pending inbox IDs: %s." % (
                    ", ".join(trains) or "none", ", ".join(m["id"] for m in messages) or "none")
            with open(brief, "a", encoding="utf-8") as out:
                out.write("\n## Recovered work\n\nResume open trains before choosing a new land rule:\n" +
                          "".join("- " + p + "\n" for p in trains) +
                          "\nProcess every pending inbox message, acknowledging its ID again:\n" +
                          "".join("- inbox: " + m["id"] + "\n" for m in messages))
        with open(brief, "a", encoding="utf-8") as out:
            out.write(notes)
        argv = harness(engine, model, effort, wt, state, values["runtime.options.permission_mode"], values, not remote)
        if remote:  # the launch policy above still refuses here; the host builds the argv and checks its own uid
            rec["worktree"] = wt
            save()
            reply = remote_run.spawn(values, state, name, rec, brief, wt_name, "refs/pull/%d/head" % args.pr
                                    if args.pr else "refs/heads/" + values["repo.default_branch"])
            if reply["result"] != "ok":
                raise RuntimeError("crew: refusing spawn on %s: %s: %s" % (remote, reply["result"], reply.get(
                    "reason") or reply.get("error")))
            rec.update({k: reply[k] for k in ("worktree", "pane_id", "pane_pid", "pane_start")})
        else:
            tmux.new_window(session, free[0], name, wt, window_env(values, state, role, name, brief, args.project),
                            LAUNCH % (shlex.join(argv), prompt))
            show_icon(values, session, free[0], role)
            wait_harness(session, free[0], name, ENGINE_CMD[engine], args.timeout)
    except (RuntimeError, OSError) as e:
        kill_run(values, session, state, name)
        print(e)
        return 1
    rec["start"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rec.update({} if remote else identity(session, free[0]), args=dict({"issue": args.issue, "pr": args.pr, "pass": pass_,
                                                      "round": args.round, "tier": args.tier}, **({"sweep": True} if sweep else {"docs_pass": True} if docs_pass else
                                                                               {"reflection": reflection} if reflection else
                                                                               {"train": train} if train else {})))
    save()
    if role in ("builder", "reviewer"):  # its run record has appeared: the grant ends here, not at the next decide (#1050)
        commands()["schedule"].release(state, role, ["#%d" % n for n in (args.issue, args.pr) if n])
    if milestones:
        commands()["poll"].triage_take(state, milestones)
    print("crew: started %s (%s, %s %s %s) in %s" % (name, "on " + remote if remote else "window %d" % free[0], engine,
                                                    model, effort, rec["worktree"]))
    return 0
