"""`crew poll` turns GitHub state changes into one-consumer wake records in `wake/queue.jsonl` (`new-head` and the
evidence-only `fix-at-head` carry the round `k`; approved default-branch merges emit `merge-up` with the previous
head and approval round). Queued ci-failed records for a superseded head are dropped. Failed Actions jobs with zero
steps emit ci-infra to the coordinator, never ci-passed. Non-active ownership emits one coordinator ownership wake per
mode change and no work events; `lost` (another runtime owns, after the ack) is the prompt-stop wake. A transient `gh` failure (5xx, timeout, connection reset) is retried with bounded
backoff; if it persists, `--once` exits 75 (EX_TEMPFAIL) so `crew watch` records an incident instead of waking (#702).
A change that resolves express (express-lane.md, routing) emits no reviewer event; `ci-passed` needs a selfgate pass at
head (or carried by an express merge-up atop a selfgate-passed head) and a new selfgate pass with CI green emits
`selfgate-passed`, all to the synthesizer. When the lane falls back, the head emits `new-head` for normal review.
With `triage.enabled`, each poll also runs the zero-model triage scan (triage.md, #747): unplaced issues and owner
replies to triage records in each `triage.repos` tracker go to `triage/queue.json` with exact-key duplicate hints,
intake-card fields and P0 signals; a newly seen P0 candidate queues one `triage-p0` wake for the coordinator.

Usage: crew poll [--once] --project FILE
"""
import json
import os
import re
import subprocess
import time
import tomllib
from crew_shared import commands, ownership_module, profile, queue_lock, ROLES


# crew poll (tmux.md Q1, C2): one wake source. Read-only gh JSON for open crew PRs and crew:ready items is diffed
# against poll-state.json; each change becomes one wake record in wake/queue.jsonl naming one consuming role
# (protocol §8). The coordinator drains the queue and routes each record by crew send or crew spawn.
CONSUMER = {event: role for role, data in ROLES.items() for event in data["events"]["tmux"]}
PR_FIELDS = "number,state,headRefOid,labels,statusCheckRollup,reviews"
CREW_LINE = re.compile(r"<!-- crew:v1 ([^>]*?) -->")
CI_OK, CI_BAD = {"SUCCESS", "NEUTRAL", "SKIPPED"}, {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED",
                                                    "STARTUP_FAILURE"}
TRANSIENT_GH = re.compile(r"HTTP 5\d\d|time(d ?)?out|connection reset|unexpected EOF|TLS handshake", re.IGNORECASE)
RETRY_DELAYS = (1, 2, 4)  # seconds between poll's attempts; well inside crew watch's default --source-timeout


class Transient(RuntimeError):
    """A gh failure that persisted through every retry but looks like a GitHub hiccup, not a crew bug."""


def landing_steers(reviews):
    """Read recorded coordinator urgency and outstanding project stops in review order."""
    urgent, stops = [], set()
    for review in reviews:
        for line in CREW_LINE.findall(review["body"]):
            marker = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if (marker.get("role"), marker.get("pass")) != ("coordinator", "steer"):
                continue
            cmd, cmd_id = marker.get("cmd"), marker.get("cmd-id")
            if cmd == "urgent":
                urgent.append(marker)
            elif cmd == "stop-landing" and cmd_id:
                stops.add(cmd_id)
            elif cmd == "resume-landing":
                stops.discard(marker.get("stop-id"))
    return {"urgent": urgent, "stops": sorted(stops)}


def pr_snapshot(pr):
    """Head, CI rollup, the latest verdict at head, round k (protocol §5) and whether a builder fix note sits at head
    after a changes verdict there (an evidence-only fix), and the latest builder selfgate verdict at head, from the
    hidden crew:v1 lines only (protocol §4)."""
    head = pr["headRefOid"]
    results = [c.get("state") if c.get("__typename") == "StatusContext" else
               "INFRA" if c.get("status") == "COMPLETED" and c.get("conclusion") in CI_BAD and
               (c.get("steps") == [] or c.get("_ci_infra")) else c.get("conclusion") if c.get("status") == "COMPLETED" else "PENDING"
               for c in pr["statusCheckRollup"]]
    ci = "failed" if CI_BAD & set(results) else "infra" if "INFRA" in results else \
         "passed" if results and set(results) <= CI_OK else "pending"
    verdict, fixed, changes, selfgate = None, False, 0, None
    for review in pr["reviews"]:
        for line in CREW_LINE.findall(review["body"]):
            m = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if m.get("pass") in ("cutover", "resume"):
                changes = 0
            elif m.get("role") == "reviewer-validator" and m.get("pass") == "verdict":
                changes += m.get("verdict") == "changes"
                if m.get("sha") == head:
                    verdict, fixed = m.get("verdict"), False
            elif m.get("role") == "builder" and m.get("pass") == "fix" and m.get("sha") == head:
                fixed = True
            elif m.get("role") == "builder" and m.get("pass") == "selfgate" and m.get("sha") == head:
                selfgate = m.get("verdict")
    return {"head": head, "ci": ci, "verdict": verdict, "round": 1 + changes, "fixed": fixed and verdict == "changes",
            "selfgate": selfgate}


def decide(prev, prs, issues, merge_ups=None, express=()):
    """Pure: previous poll state plus gh JSON (open PRs, tracked PRs now merged or closed, open issues) and the PR
    numbers that resolve express -> (events, new state). A change emits one event; no change emits nothing."""
    events, state = [], {"prs": {}, "issues": []}

    def emit(event, *refs, **extra):
        events.append({"event": event, "consumer": CONSUMER[event], "refs": list(refs), **extra})

    for pr in prs:
        n, cur = str(pr["number"]), pr_snapshot(pr)
        if pr["state"] != "OPEN":
            emit("pr-merged" if pr["state"] == "MERGED" else "pr-closed", "#" + n, cur["head"])
            continue
        if not any(label["name"].startswith("crew:") for label in pr["labels"]):
            continue
        old, lane, approved = prev.get("prs", {}).get(n, {}), n in express, (merge_ups or {}).get(n)
        carried = lane and bool(approved or old.get("head") == cur["head"] and old.get("carried"))  # merge-up portability
        gate = cur["selfgate"] == "pass" or carried
        state["prs"][n] = dict(cur, express=True, gate=gate, carried=carried) if lane else cur
        if cur["head"] != old.get("head"):
            if approved:
                emit("merge-up", "#" + n, cur["head"], previous_head=approved["head"], round=approved["round"])
            elif not lane:
                emit("new-head", "#" + n, cur["head"], round=cur["round"])
        elif old.get("express") and not lane:  # lane fallback: the suppressed head now needs normal review
            emit("new-head", "#" + n, cur["head"], round=cur["round"])
        if cur["ci"] in ("passed", "failed", "infra") and (cur["head"], cur["ci"]) != (old.get("head"), old.get("ci")) \
                and not (lane and cur["ci"] == "passed" and not gate):
            emit("ci-" + cur["ci"], "#" + n, cur["head"])
        elif lane and gate and cur["ci"] == "passed" and (cur["head"], True) != (old.get("head"), old.get("gate")):
            emit("selfgate-passed", "#" + n, cur["head"])
        if cur["verdict"] and (cur["head"], cur["verdict"]) != (old.get("head"), old.get("verdict")):
            emit("review-approved" if cur["verdict"] == "pass" else "review-changes-requested", "#" + n, cur["head"])
        if cur["fixed"] and not lane and (cur["head"], True) != (old.get("head"), old.get("fixed")):  # no new-head (B2)
            emit("fix-at-head", "#" + n, cur["head"], round=cur["round"])
    state["issues"] = sorted(i["number"] for i in issues if i["assignees"] and
                             any(label["name"] == "crew:ready" for label in i["labels"]))
    for n in state["issues"]:
        if n not in prev.get("issues", []):
            emit("issue-assigned", "#%d" % n)
    return events, state


def gh_json(*args, retry=()):
    """gh JSON output; with retry (poll_once's reads, #702), a transient failure is retried after each delay in turn.
    Other callers keep one attempt: train_view records each failed read itself, and route runs inside the watcher."""
    for delay in (*retry, None):
        r = subprocess.run(["gh", *args], capture_output=True, text=True)
        if not r.returncode:
            return json.loads(r.stdout)
        transient = bool(TRANSIENT_GH.search(r.stderr))
        if delay is None or not transient:
            break
        time.sleep(delay)
    raise (Transient if transient else RuntimeError)("crew: gh %s failed: %s" % (" ".join(args[:2]), r.stderr.strip()))


def observe_ci(pr, repo):
    """A failed Actions run with no started job steps is infrastructure, never green CI.
    Unavailable job observations keep the original failure classification."""
    ci_state(pr, repo)
    for check in pr["statusCheckRollup"]:
        if check.get("status") != "COMPLETED" or check.get("conclusion") not in CI_BAD:
            continue
        match = re.search(r"/actions/runs/(\d+)", check.get("detailsUrl", ""))
        if not match:
            continue
        try:
            jobs = gh_json("api", "repos/%s/actions/runs/%s/jobs?per_page=100" % (repo, match[1]))["jobs"]
        except (RuntimeError, KeyError):
            continue
        check["_ci_infra"] = bool(jobs) and all(j.get("steps") == [] for j in jobs) and len(jobs) < 100


def ci_state(pr, repo):
    """Read failed Actions jobs' steps; unknown jobs remain code failures, never a green CI signal."""
    checks = []
    for check in pr["statusCheckRollup"]:
        job = re.search(r"/actions/runs/\d+/job/(\d+)", check.get("detailsUrl") or "")
        if job and check.get("status") == "COMPLETED" and check.get("conclusion") in CI_BAD:
            try:
                data = gh_json("api", "repos/%s/actions/jobs/%s" % (repo, job[1]))
            except RuntimeError:
                data = {}
            if data.get("status") == "completed" and data.get("conclusion", "").upper() in CI_BAD and \
                    isinstance(data.get("steps"), list):
                check = dict(check, steps=data["steps"])
        checks.append(check)
    pr["statusCheckRollup"] = checks
    return pr_snapshot(pr)["ci"]


def merge_up(pr, old, repo, default_branch, express=False):
    """Recognize one merge atop the previously observed, still-approved head (for express, its selfgate pass); its
    second parent must belong to the default branch. Read the verdict live, so a later changes verdict cannot inherit
    a cached approval."""
    if not old.get("head") or old["head"] == pr["headRefOid"]:
        return None
    approved = pr_snapshot({**pr, "headRefOid": old["head"]})
    if approved["selfgate" if express else "verdict"] != "pass":
        return None
    for review in pr["reviews"]:
        for line in CREW_LINE.findall(review["body"]):
            marker = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if (marker.get("role"), marker.get("pass"), marker.get("sha")) == (
                    "reviewer-validator", "verdict", old["head"]):
                approved["round"] = int(marker["round"])
    commit = gh_json("api", "repos/%s/commits/%s" % (repo, pr["headRefOid"]))
    parents = [p["sha"] for p in commit["parents"]]
    if len(parents) != 2 or parents[0] != old["head"]:
        return None
    comparison = gh_json("api", "repos/%s/compare/%s...%s" % (repo, parents[1], default_branch))
    return approved if comparison["status"] in ("ahead", "identical") else None


def express_lane(args, values, view):
    """Express resolution for a crew:express change (crew train's train_express); unreadable runs the crew lane."""
    try:
        return commands()["train"].train_express(args, values, "%s/%s" % (values["repo.owner"], values["repo.name"]),
                                                 view)[0]
    except RuntimeError as e:
        print("crew: poll: #%d crew lane: %s" % (view["number"], e))
        return False


def drop_superseded(queue, heads):
    """Drop queued ci-failed records for a PR whose live head has moved past theirs (#578); caller holds the lock."""
    if not os.path.exists(queue):
        return
    with open(queue, encoding="utf-8") as f:
        lines = f.read().splitlines(keepends=True)
    kept = []
    for line in lines:
        try:
            w = json.loads(line)
        except ValueError:
            kept.append(line)
            continue
        refs = w.get("refs") or []
        if not (w.get("event") == "ci-failed" and len(refs) > 1 and heads.get(refs[0], refs[1]) != refs[1]):
            kept.append(line)
    if len(kept) < len(lines):
        with open(queue, "w", encoding="utf-8") as f:
            f.writelines(kept)


def poll_once(values, state, args):
    mode = ownership_module.status(values)
    ownership_path = os.path.join(state, "ownership.json")
    previous = json.load(open(ownership_path)) if os.path.exists(ownership_path) else "active"
    if mode != "active":
        if previous != mode:
            with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a") as f:
                f.write(json.dumps({"id": "ownership-" + os.urandom(6).hex(), "source": "poll",
                                   "reason": "ownership:", "event": "ownership", "consumer": "coordinator",
                                   "refs": [mode]}) + "\n")
        with open(ownership_path, "w") as f:
            json.dump(mode, f)
        print("crew: ownership: %s; poll emits no work" % mode)
        return
    if previous != "active":
        with open(ownership_path, "w") as f:
            json.dump(mode, f)
    repo, path = "%s/%s" % (values["repo.owner"], values["repo.name"]), os.path.join(state, "poll-state.json")
    prev = None
    if os.path.exists(path):
        with open(path) as f:
            prev = json.load(f)
    prs = gh_json("pr", "list", "-R", repo, "--state", "open", "--limit", "200", "--json", PR_FIELDS,
                  retry=RETRY_DELAYS)
    gone = set((prev or {}).get("prs", {})) - {str(pr["number"]) for pr in prs}
    prs += [gh_json("pr", "view", n, "-R", repo, "--json", PR_FIELDS, retry=RETRY_DELAYS) for n in sorted(gone)]
    issues = gh_json("issue", "list", "-R", repo, "--state", "open", "--label", "crew:ready", "--limit", "200",
                     "--json", "number,labels,assignees", retry=RETRY_DELAYS)
    express = {str(pr["number"]) for pr in prs if pr["state"] == "OPEN" and express_lane(args, values, pr)}
    merge_ups = {}
    for pr in prs:
        if pr["state"] == "OPEN" and any(l["name"].startswith("crew:") for l in pr["labels"]):
            approved = merge_up(pr, (prev or {}).get("prs", {}).get(str(pr["number"]), {}),
                                repo, values["repo.default_branch"], str(pr["number"]) in express)
            if approved:
                merge_ups[str(pr["number"])] = approved
    for pr in prs:
        observe_ci(pr, repo)
    events, new = decide(prev or {}, prs, issues, merge_ups, express)
    if prev is None:  # first run: record a baseline only; the §6 step 3 sweep covers what happened before it
        events = []
        print("crew: poll: baseline of %d PRs, %d issues" % (len(new["prs"]), len(new["issues"])))
    heads = {"#%d" % pr["number"]: pr["headRefOid"] for pr in prs}
    with queue_lock(state):
        drop_superseded(os.path.join(state, "wake", "queue.jsonl"), heads)
    with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a", encoding="utf-8") as f:  # at-least-once
        for e in events:
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            f.write(json.dumps({"id": "poll-%s-%s" % (ts, os.urandom(3).hex()), "source": "poll", "reason": "poll", **e, "ts": ts}) + "\n")
            print("crew: poll: %s -> %s %s" % (e["event"], e["consumer"], " ".join(e["refs"])))
    with open(path + ".tmp", "w") as f:
        json.dump(new, f, indent=2)
    os.replace(path + ".tmp", path)
    if values.get("triage.enabled"):
        triage_poll(values, state, args.project)


# Always-on triage scan (triage.md T1, #747): deterministic, no model call. Skip rules per triage.md "Skip rules".
TRIAGE_FIELDS = "number,title,body,labels,milestone,url,comments"
TRIAGE_RULES = {"p0": {"labels": ["P0", "security"],  # built-in defaults when triage.rules is unset or unreadable
                       "keywords": ["pipeline blocked", "gate bypass", "secret leak", "token leak", "data loss"]}}
TRIAGE_CARD = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "templates", "intake-candidate.md")
TRIAGE_PATH = re.compile(r"(?<![\w/.])(?:[\w.-]+/)+[\w-]+\.\w+\b")
TRIAGE_SOURCE = re.compile(r"[\w.-]+/[\w.-]+#\d+")


def triage_card_fields(template=TRIAGE_CARD):
    """Card field names from the intake-candidate template's markdown block, e.g. Source, Failure class."""
    with open(template, encoding="utf-8") as f:
        block = f.read().split("```markdown", 1)[1].split("```", 1)[0]
    return re.findall(r"^(?:\*\*)?([A-Z][\w ]*?):", block, re.M)


def triage_keys(item, fields):
    """Card fields and the exact duplicate keys of one issue: failure class, Source, named paths, normalized title."""
    body = item.get("body") or ""
    card = {}
    for name in fields:
        m = re.search(r"^(?:\*\*)?%s:(?:\*\*)?[ \t]*(.+?)[ \t]*$" % re.escape(name), body, re.M)
        if m:
            card[name] = m[1]
    source = TRIAGE_SOURCE.search(card.get("Source", ""))
    title = re.sub(r"^(\[[^]]*\]\s*)+", "", item["title"].lower())
    keys = {"title:" + " ".join(re.findall(r"[a-z0-9]+", title))}
    keys |= {"path:" + p for p in TRIAGE_PATH.findall(body)}
    if card.get("Failure class"):
        keys.add("class:" + card["Failure class"].split()[0].lower())
    if source:
        keys.add("source:" + source[0].lower())
    return card, keys


def triage_rules(path):
    """(rules, note): the rules file's P0 signals, or the built-in defaults when unset or unreadable."""
    if not path:
        return TRIAGE_RULES, "default"
    try:
        with open(path, "rb") as f:
            p0 = tomllib.load(f)["p0"]
        return {"p0": {k: [str(v) for v in p0.get(k, [])] for k in ("labels", "keywords")}}, path
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        return TRIAGE_RULES, "default (unreadable %s: %s)" % (path, e)


def triage_scan(repo, open_items, closed_items, rules, owners, fields):
    """Pure: queue entries for one repo. Skips pull requests, triage:log issues, placed issues and issues with a
    flavor record; an issue with a pass=triage record queues only on a later owner comment without one."""
    entries, keyed, open_numbers = [], [], {i.get("number") for i in open_items}
    for item in open_items + closed_items:
        try:
            keyed.append((item, *triage_keys(item, fields)))
        except (KeyError, TypeError, AttributeError) as e:  # a closed item only loses its duplicate hints
            if item in open_items:
                entries.append({"ref": "%s#%s" % (repo, item.get("number")),
                                "unreadable": "%s: %s" % (type(e).__name__, e)})
    for item, card, keys in keyed:
        ref = "%s#%d" % (repo, item["number"])
        if item["number"] not in open_numbers:
            continue
        try:
            labels = {label["name"] for label in item["labels"]}
            markers = [(c, dict(kv.split("=", 1) for kv in line.split() if "=" in kv))
                       for c in item["comments"] for line in CREW_LINE.findall(c["body"])]
            if "/pull/" in item.get("url", "") or "triage:log" in labels or item.get("milestone"):
                continue
            triaged = [i for i, (_, m) in enumerate(markers) if m.get("pass") == "triage"]
            if triaged:
                last = markers[triaged[-1]][0]
                later = item["comments"][item["comments"].index(last) + 1:]
                if not any((c.get("author") or {}).get("login") in owners and "pass=triage" not in c["body"]
                           for c in later):
                    continue
                reason = "owner-reply"
            elif any(m.get("pass") == "flavor" for _, m in markers):
                continue
            else:
                reason = "new"
        except (KeyError, TypeError, AttributeError, ValueError) as e:
            entries.append({"ref": ref, "unreadable": "%s: %s" % (type(e).__name__, e)})
            continue
        text = " ".join((item["title"], card.get("Failure class", ""))).lower()
        p0 = sorted({"label:" + n for n in labels if n in rules["p0"]["labels"]} |
                    {"keyword:" + k for k in rules["p0"]["keywords"]
                     if re.search(r"\b%s\b" % re.escape(k.lower()), text)})
        dupes = [{"ref": "%s#%d" % (repo, other["number"]), "state": "open" if other["number"] in open_numbers
                  else "closed", "keys": sorted(keys & other_keys)}
                 for other, _, other_keys in keyed if other is not item and keys & other_keys]
        entries.append({"ref": ref, "reason": reason, "title": item["title"], "card": card, "duplicates": dupes,
                        "p0": p0})
    return entries


def triage_poll(values, state, project, read=gh_json):
    """Scan every triage.repos tracker into triage/queue.json; queue one triage-p0 wake per newly seen P0 candidate.
    An unreadable repo or item is recorded in the queue, never dropped."""
    rules_path = values.get("triage.rules")
    rules, note = triage_rules(rules_path and os.path.join(os.path.dirname(os.path.abspath(project)), rules_path))
    owners, fields = set(values.get("identities.owners") or []), triage_card_fields()
    path = os.path.join(state, "triage", "queue.json")
    try:
        with open(path) as f:
            seen = {e["ref"] for e in json.load(f)["items"] if e.get("p0")}
    except (OSError, ValueError, KeyError, TypeError):
        seen = set()
    queue = {"scanned": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rules": note, "repos": {}, "items": []}
    for repo in values.get("triage.repos") or ["%s/%s" % (values["repo.owner"], values["repo.name"])]:
        try:
            items = [read("issue", "list", "-R", repo, "--state", s, "--limit", "500", "--json",
                          TRIAGE_FIELDS if s == "open" else "number,title,body", retry=RETRY_DELAYS)
                     for s in ("open", "closed")]
        except RuntimeError as e:
            queue["repos"][repo] = "unreadable: %s" % e
            continue
        queue["repos"][repo] = "ok"
        queue["items"] += triage_scan(repo, *items, rules, owners, fields)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w") as f:
        json.dump(queue, f, indent=2)
    os.replace(path + ".tmp", path)
    for e in queue["items"]:
        if e.get("p0") and e["ref"] not in seen:
            ts = queue["scanned"]
            with queue_lock(state), open(os.path.join(state, "wake", "queue.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"id": "triage-p0-%s-%s" % (ts, os.urandom(3).hex()), "source": "poll",
                                    "reason": "triage-p0", "event": "triage-p0", "consumer": "coordinator",
                                    "refs": [e["ref"]], "p0": e["p0"], "ts": ts}) + "\n")
            print("crew: poll: triage-p0 -> coordinator %s" % e["ref"])


def register(sub):
    p = sub.add_parser("poll")
    p.add_argument("--once", action="store_true", help="one poll, then exit (default: every poll_interval seconds)")
    p.add_argument("--project", required=True)
    p.add_argument("--org-profile")


def run(args):
    values, _, state = profile(args)
    while True:
        try:
            poll_once(values, state, args)
        except RuntimeError as e:
            print(e)
            if args.once:
                return os.EX_TEMPFAIL if isinstance(e, Transient) else 1
        if args.once:
            return 0
        time.sleep(values["runtime.options.poll_interval"])
