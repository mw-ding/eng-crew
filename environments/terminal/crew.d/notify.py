"""Away-only Slack notifications, durable event dedupe and bounded webhook retries.

Usage: mdstack notify --project FILE --event-file FILE
       mdstack notify --project FILE --flush
       mdstack notify --project FILE --status
The coordinator supplies JSON events after recording them on GitHub. --status
prints delivery failures for the return brief; watch retries one due event per scan.
Only the environment holds the webhook; errors never print response bodies or URLs.
"""
import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from crew_shared import profile, queue_lock, require_ownership

KINDS = {
    "land": ("PR landed", ("title", "train", "milestone")),
    "milestone": ("Milestone completed", ("title",)),
    "release-cut": ("Release cut", ("title",)),
    "release-published": ("Release published", ("title",)),
    "ask": ("Owner decision needed", ("title", "deadline", "default")),
    "sensitive": ("Sensitive merge permission needed", ("title", "deadline", "default")),
    "mirror": ("Mirror decision needed", ("title", "deadline", "default")),
    "main-red": ("Default branch red after land", ("title",)),
    "stop": ("Stop the line", ("title",)),
    "digest": ("Away progress", ("landed", "in_flight", "blocked")),
}


def away_record(comments, login):
    current, seen = None, set()
    for comment in comments:
        body = comment.get("body") or ""
        if comment.get("user", {}).get("login") != login or not re.search(r"^— .+ · .+ · .+$", body, re.M):
            continue
        if comment.get("updated_at") != comment.get("created_at"):
            continue
        for line in re.findall(r"<!-- crew:v1 ([^>]*?) -->", body):
            marker = dict(kv.split("=", 1) for kv in line.split() if "=" in kv)
            if (marker.get("role"), marker.get("pass"), marker.get("round"), marker.get("verdict")) != (
                    "coordinator", "steer", "n/a", "n/a") or not re.fullmatch(r"[0-9a-f]{40}", marker.get("sha", "")):
                continue
            source = marker.get("cmd-id")
            if not source or source in seen:
                continue
            for text in re.findall(r"```json\s*\n(.*?)\n```", body, re.S) + re.findall(r"`(\{[^`\n]+\})`", body):
                record = json.loads(text)
                if marker.get("cmd") == "away" and record.get("state") == "away" and record.get("entry") == source:
                    datetime.datetime.fromisoformat(record["started"])
                    current = record
                    seen.add(source)
                elif marker.get("cmd") == "away-return" and record.get("state") == "returned" and current and record.get("entry") == current["entry"]:
                    current = None
                    seen.add(source)
    return current


def live_away(values, state):
    control = Path(state) / "away-control.json"
    if not control.exists():
        return None
    issue = json.loads(control.read_text())["issue"]
    result = subprocess.run(["gh", "api", "--paginate", "--slurp", "repos/%s/%s/issues/%s/comments" % (
        values["repo.owner"], values["repo.name"], issue)], capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise ValueError("away record unavailable")
    return away_record([c for page in json.loads(result.stdout) for c in page], values["identities.coordinator.gh_user"])


def message(event):
    label, fields = KINDS[event["kind"]]
    if not isinstance(event["id"], str) or not event["id"]:
        raise ValueError("event id required")
    url = event["url"]
    if not isinstance(url, str) or not url.startswith("https://") or any(c in url for c in "\r\n"):
        raise ValueError("recorded HTTPS URL required")
    lines = [label]
    for field in fields:
        value = event[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("event field required")
        lines.append("%s: %s" % (field.replace("_", " "), value))
    return "\n".join(lines + [url, "Decisions and approvals stay on the recorded tool of record."])


def save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record) + "\n")
    tmp.replace(path)


def files(state):
    return sorted((Path(state) / "notifications").glob("*.json"))


def tick(values, state, now, force=False):
    if values["backends.owner-channel.name"] != "slack":
        return []
    with queue_lock(state):
        records = [(p, json.loads(p.read_text())) for p in files(state)]
        pending = [(p, r) for p, r in records if r["status"] == "pending" and r["next"] <= now]
        clock_path = Path(state) / "notifications-clock.json"
        clock = json.loads(clock_path.read_text()) if clock_path.exists() else {"checked": 0, "away": None}
        cached = clock["away"]
        interval = values["runtime.options.slack_digest_interval"]
        latest = max([datetime.datetime.fromisoformat(cached["started"]).timestamp()] +
                     [r["activity"] for _, r in records if r["entry"] == cached["entry"]]) if cached else now
        if not force and not pending and now < latest + interval and now < clock["checked"] + 60:
            return []
        try:
            away = live_away(values, state)
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            print("crew: Slack notification deferred: away record unavailable")
            return []
        save(clock_path, {"checked": now, "away": {k: away[k] for k in ("entry", "started")} if away else None})
        for p, r in records:
            if r["status"] == "pending" and (not away or r["entry"] != away["entry"]):
                r["status"] = "cancelled"
                save(p, r)
        if not away:
            return []
        active = [(p, r) for p, r in records if r["entry"] == away["entry"]]
        pending = [(p, r) for p, r in pending if r["entry"] == away["entry"]]
        if pending and require_ownership(values, "write"):
            p, r = pending[0]
            webhook = os.environ.get(values["runtime.options.slack_webhook_env"], "")
            r["status"] = "uncertain"
            save(p, r)  # A crash after acceptance must not resend on restart.
            try:
                request = urllib.request.Request(webhook, data=json.dumps({"text": r["text"], "mrkdwn": False}).encode(),
                                                 headers={"Content-Type": "application/json"})
                # A redirect could expose the webhook or send the same event elsewhere.
                opener = urllib.request.build_opener(NoRedirect)
                with opener.open(request, timeout=2) as response:
                    if response.status != 200 or response.read(64).strip() != b"ok":
                        raise ValueError("webhook rejected")
                r["status"] = "sent"
            except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException) as error:
                r["failures"] += 1
                if isinstance(error, urllib.error.HTTPError):
                    error.close()
                rejected = isinstance(error, (urllib.error.HTTPError, ValueError)) or (
                    isinstance(error, urllib.error.URLError) and isinstance(error.reason, (ConnectionRefusedError, socket.gaierror)))
                if rejected:
                    r["status"] = "pending"
                    r["next"] = now + min(3600, 30 * 2 ** min(r["failures"] - 1, 7))
                else:
                    r["status"] = "uncertain"
                print("crew: Slack delivery failed; %s (attempt %d)" % (
                    "retry scheduled" if rejected else "acceptance uncertain; reconcile on return", r["failures"]))
            save(p, r)
        latest = max([datetime.datetime.fromisoformat(away["started"]).timestamp()] + [r["activity"] for _, r in active])
        if now >= latest + interval:
            return [{"reason": "notify-digest", "event": "away digest due", "entry": away["entry"], "slot": int(latest + interval)}]
    return []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def register(sub):
    p = sub.add_parser("notify")
    p.add_argument("--project")
    p.add_argument("--org-profile")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--event-file")
    group.add_argument("--flush", action="store_true")
    group.add_argument("--status", action="store_true")


def run(args):
    values, _, state = profile(args)
    if args.status:
        for path in files(state):
            r = json.loads(path.read_text())
            if r["failures"] or r["status"] == "uncertain":
                print("Slack delivery: %s; failures=%d; status=%s; %s" % (r["kind"], r["failures"], r["status"], r["url"]))
        return 0
    if values["backends.owner-channel.name"] != "slack":
        return 0
    now = time.time()
    if args.event_file:
        try:
            event = json.loads(Path(args.event_file).read_text())
            text = message(event)
            webhook = os.environ.get(values["runtime.options.slack_webhook_env"], "")
            if webhook and webhook in json.dumps(event):
                raise ValueError("secret in event")
            away = live_away(values, state)
            if not away:
                return 0
            if event["kind"] == "digest":
                latest = max([datetime.datetime.fromisoformat(away["started"]).timestamp()] +
                             [r["activity"] for r in (json.loads(p.read_text()) for p in files(state))
                              if r["entry"] == away["entry"]])
                if now < latest + values["runtime.options.slack_digest_interval"]:
                    return 0
            key = hashlib.sha256(json.dumps([away["entry"], event["kind"], event["id"]]).encode()).hexdigest()
            path = Path(state) / "notifications" / (key + ".json")
            with queue_lock(state):
                if path.exists():
                    return 0
                save(path, dict(entry=away["entry"], kind=event["kind"], url=event["url"], text=text,
                                status="pending", failures=0, next=now, activity=now))
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            print("crew: Slack notification not queued: invalid event or unavailable away record")
            return 0
    tick(values, state, now, force=args.flush)
    return 0
