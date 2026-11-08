"""GitHub repository prerequisite checks and fixers for doctor and bootstrap (docs/bootstrap.md Q6).

Read-only unless fix=True; dry_run prints shell-quoted operations without executing them. Uses the profile's builder
identity without switching gh accounts. Only the ten runbook crew labels are managed; mismatches need this repo's
install.json and extra crew labels always block. Milestone names are explicit; closed milestones stay frozen.
Project Status options are replaced only on an empty board. The board is recommended, not required: an identity that
cannot create one under the repo owner gets a human step naming the owner's commands. Invitations are sent, never accepted. CI and branch
protection remain human steps. No product labels, workflows, webhooks or repository settings are changed.
"""
import json
import os
import re
import shlex
import subprocess

LABELS = [
    ("crew:ready", "0E8A16", "Released to the builder; issue may be assigned and built"),
    ("crew:in-review", "1D76DB", "PR open, awaiting CI + review/validation"),
    ("crew:changes", "D93F0B", "Reviewer requested changes; builder fix round due"),
    ("crew:approved", "5319E7", "Reviewer approved at head; synthesizer may merge"),
    ("crew:escalated", "B60205", "Round/CI-fix cap hit or escalated; bots no-op until /crew resume"),
    ("crew:hold", "FBCA04", "Paused: every bot no-ops on this item"),
    ("crew:external", "C5DEF5", "External/fork PR: sandboxed validation, no tokens"),
    ("crew:spec", "0052CC", "Spec PR: review pass only, merges on /crew merge-ok"),
    ("crew:needs-md", "F9D0C4", "Blocked on an owner decision (recommended default + deadline)"),
    ("crew:needs-mirror", "E99695", "Protocol/template change: merge blocked until the box skill is mirrored"),
]
STATUS = ["Todo", "In Progress", "In Review", "Done"]
LINKED = "query($owner:String!,$repo:String!){repository(owner:$owner,name:$repo){projectsV2(first:100){nodes{id} pageInfo{hasNextPage}}}}"
OPTIONS = 'mutation($field:ID!){updateProjectV2Field(input:{fieldId:$field,singleSelectOptions:[%s]}){projectV2Field{... on ProjectV2SingleSelectField{id}}}}' % ",".join(
    '{name:"%s",color:%s,description:""}' % (name, color)
    for name, color in zip(STATUS, ["GRAY", "YELLOW", "ORANGE", "GREEN"]))


class Repo:
    def __init__(self, values, fix=False, dry_run=False, milestone=None):
        self.owner, self.name = values["repo.owner"], values["repo.name"]
        self.repo = self.owner + "/" + self.name
        self.base = "repos/" + self.repo
        self.reviewer = values["identities.reviewer.gh_user"]
        self.state = os.path.join(os.path.abspath(values["paths.state_dir"]), self.owner + "__" + self.name)
        self.fix, self.dry_run, self.milestone = fix, dry_run, milestone
        self.runtime = values["runtime.name"]
        self.env = dict(os.environ)
        token = self.call("auth", "token", "--user", values["identities.builder.gh_user"], decode=False)
        self.env["GH_TOKEN"] = token.strip()

    def call(self, *args, decode=True):
        r = subprocess.run(["gh", *args], env=self.env, capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=30)
        if r.returncode:
            raise RuntimeError("gh operation failed: " + shlex.join(args))  # never echo stderr or credentials
        return json.loads(r.stdout) if decode and r.stdout.strip() else r.stdout

    def api(self, path):
        return self.call("api", path)

    def pages(self, path):
        return self.call("api", path + ("&" if "?" in path else "?") + "per_page=100", "--paginate", "--slurp")

    def items(self, path):
        return [item for page in self.pages(path) for item in page]

    def operation(self, *args):
        print("plan: " + shlex.join(["gh", *args]))
        if self.fix and not self.dry_run:
            self.call(*args, decode=False)
            return True
        return False

    def labels(self):
        want = {n: (c.lower(), d) for n, c, d in LABELS}
        record = os.path.join(self.state, "install.json")
        owned = False
        if os.path.isfile(record):
            with open(record) as f:
                install = json.load(f)
            owned = isinstance(install, dict) and install.get("runtime") == self.runtime and bool(install.get("tag"))
        # Re-read the entire namespace before each operation, so a late collision stops further writes.
        changed = False
        for name, color, desc in LABELS:
            have = {x["name"]: (x["color"].lower(), x.get("description") or "")
                    for x in self.items(self.base + "/labels") if x["name"].startswith("crew:")}
            if set(have) - set(want) or (not owned and any(have[n] != want[n] for n in have)):
                return "fail", "crew namespace collision", "human: decide who owns crew:*; no labels changed after detection"
            if have.get(name) == want[name]:
                continue
            args = ["label", "create", name, "-R", self.repo, "--color", color, "--description", desc]
            changed = True
            if name in have:
                args.append("--force")
            self.operation(*args)
        return ("ok" if not changed or self.fix and not self.dry_run else "fail", "crew labels ready" if not changed else "crew labels planned/repaired", "mdstack doctor --fix")

    def reviewer_access(self):
        permission = self.api(self.base + "/collaborators/" + self.reviewer + "/permission")["permission"]
        if permission in ("write", "admin", "maintain"):
            return "ok", "reviewer has write access", ""
        pending = self.items(self.base + "/invitations")
        if any(x["invitee"]["login"] == self.reviewer for x in pending):
            return "human", "reviewer invitation pending", "reviewer accepts the repository invitation"
        sent = self.operation("api", "-X", "PUT", self.base + "/collaborators/" + self.reviewer, "-f", "permission=push")
        if sent:
            return self.reviewer_access()
        return "fail", "reviewer invitation planned", "mdstack doctor --fix; reviewer accepts the invitation"

    def milestones(self):
        milestones = self.items(self.base + "/milestones?state=all")
        if any(x["state"] == "open" and re.match(r"M\d+(?:\s|$)", x["title"]) for x in milestones):
            return "ok", "open M* milestone exists", ""
        if not self.milestone:
            return "human", "no open M* milestone", "confirm the current name with mdstack doctor --fix --milestone M1 (or the current M number)"
        if any(x["title"] == self.milestone for x in milestones):
            return "fail", "milestone is closed: " + self.milestone, "choose the next M number; closed milestones are frozen"
        applied = self.operation("api", "-X", "POST", self.base + "/milestones", "-f", "title=" + self.milestone)
        return "ok" if applied else "fail", "milestone planned/created: " + self.milestone, "mdstack doctor --fix"

    def linked(self):
        data = self.call("api", "graphql", "-f", "query=" + LINKED, "-f", "owner=" + self.owner, "-f", "repo=" + self.name)
        projects = data["data"]["repository"]["projectsV2"]
        if projects["pageInfo"]["hasNextPage"]:
            raise RuntimeError("too many linked Projects to check safely")
        return {x["id"] for x in projects["nodes"]}

    def can_create_project(self):
        """A login other than a user owner cannot create that user's Project; a classic token needs the project scope."""
        text = self.call("api", "-i", "user", decode=False).replace("\r\n", "\n")
        head, _, body = text.partition("\n\n")
        login = json.loads(body)["login"]
        if self.api("users/" + self.owner)["type"] == "User" and login.lower() != self.owner.lower():
            return False
        scopes = re.search(r"^x-oauth-scopes:(.*)$", head, re.I | re.M)
        return not scopes or "project" in [x.strip() for x in scopes.group(1).split(",")]

    def board_steps(self):
        title = shlex.quote(self.name + " crew board")
        return "human", "no crew board (recommended, not required); this identity cannot create one under " + self.owner, (
            "optional: the owner runs gh project create --owner %s --title %s, then gh project link <number> --owner %s --repo %s"
            % (self.owner, title, self.owner, self.name))

    def project(self):
        try:
            listing = self.call("project", "list", "--owner", self.owner, "--limit", "100", "--format", "json")
            linked = self.linked()
        except RuntimeError:
            if self.can_create_project():
                raise
            return self.board_steps()  # without Project read access the board cannot be seen or created
        projects = listing["projects"]
        if listing["totalCount"] > len(projects):
            return "human", "Project listing truncated", "choose and link one crew board; automatic setup needs the complete owner listing"
        candidates = [p for p in projects if not p["closed"] and (p["id"] in linked or p["title"] == self.name + " crew board")]
        if len(candidates) > 1:
            return "human", "multiple candidate Projects", "choose and link one crew board before retrying"
        if not candidates:
            if not self.can_create_project():
                return self.board_steps()
            if self.operation("project", "create", "--owner", self.owner, "--title", self.name + " crew board", "--format", "json"):
                return self.project()
            return "fail", "Project create, link and Status setup planned", "mdstack doctor --fix creates a board, links it and sets " + ", ".join(STATUS)
        p = candidates[0]
        number = str(p["number"])
        if p["id"] not in self.linked():
            self.operation("project", "link", number, "--owner", self.owner, "--repo", self.name)
        fields = self.call("project", "field-list", number, "--owner", self.owner, "--limit", "100", "--format", "json")["fields"]
        field = next((f for f in fields if f["name"] == "Status"), None)
        if not field or "options" not in field:
            return "human", "Project has no Status field", "add a single-select Status field with " + ", ".join(STATUS)
        if [o["name"] for o in field["options"]] != STATUS:
            items = self.call("project", "item-list", number, "--owner", self.owner, "--limit", "1", "--format", "json")
            if items["totalCount"]:
                return "human", "Project Status differs on a populated board", "add missing Status options in Project settings; replacing options may clear existing statuses"
            self.operation("api", "graphql", "-f", "query=" + OPTIONS, "-f", "field=" + field["id"])
        elif p["id"] in linked:
            return "ok", "linked Project with four Status options", ""
        return "ok" if self.fix and not self.dry_run else "fail", "Project link/Status planned/repaired", "mdstack doctor --fix"


def checks(values, fix=False, dry_run=False, milestone=None):
    try:
        repo = Repo(values, fix, dry_run, milestone)
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError):
        return [("human", "repo identity", "builder credential unavailable", "gh auth login as the profile's builder account")]
    rows = []
    for name, check in [("crew labels", repo.labels), ("reviewer access", repo.reviewer_access),
                        ("milestone", repo.milestones), ("Project", repo.project)]:
        try:
            status, detail, hint = check()
        except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError):
            status, detail, hint = "human" if name == "Project" else "fail", "repository check unavailable", "check repo admin access" + (" and the project token scope" if name == "Project" else "")
        rows.append((status, name, detail, hint))
        if name == "crew labels" and status == "fail":
            repo.fix = False  # namespace collision blocks subsequent remote writes
    rows.append(("human", "CI / protection", "owner policy", "runbook Step 4: verify PR CI and choose branch protection and squash-only merges; never applied by doctor"))
    return rows
