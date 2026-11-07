#!/usr/bin/env python3
"""Slack contracts against a local fake webhook: every event, replay, away return,
digest timer, backoff, failed authority reads and secret-free stdout/state/argv.
Run with the CI test glob; no Slack credentials or network service required.
"""
import contextlib
import datetime
import http.server
import io
import json
import os
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import Base, CREW
import importlib.machinery
import importlib.util

loader = importlib.machinery.SourceFileLoader("crew_notify_tests", CREW)
cli = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_notify_tests", loader))
loader.exec_module(cli)
notify = cli._shared.commands()["notify"]
NOW = 2_000_000_000
START = datetime.datetime.fromtimestamp(NOW - 3600, datetime.timezone.utc).isoformat()


class Endpoint(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.attempts.append(payload)
        code = self.server.code
        if code == 200:
            self.server.messages.append(payload)
        self.send_response(code)
        self.end_headers()
        self.wfile.write(b"ok" if code == 200 else self.server.secret.encode())

    def log_message(self, *args):
        pass


def comment(record, cmd, source, login="acme-bot"):
    return {"user": {"login": login}, "body": '```json\n%s\n```\n'
            '<!-- crew:v1 role=coordinator pass=steer cmd=%s cmd-id=%s sha=%s round=n/a verdict=n/a -->\n'
            '— Ash (CTO) · codex · model' % (json.dumps(record), cmd, source, "a" * 40)}


class Notify(Base):
    def setUp(self):
        super().setUp()
        with open(self.project, "a") as f:
            f.write('\n[backends.owner-channel]\nname = "slack"\n[runtime.options]\n'
                    'slack_webhook_env = "CREW_TEST_WEBHOOK"\nslack_digest_interval = 60\n')
        self.values, problems = cli._shared.crew_render.resolve(self.project, None)
        self.assertFalse(problems, problems)
        with patch.object(socket, "getfqdn", return_value="localhost"):
            self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
        self.server.code, self.server.messages, self.server.attempts = 200, [], []
        self.server.secret = "runtime-webhook-secret"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.webhook = "http://127.0.0.1:%d/%s" % (self.server.server_port, self.server.secret)
        self.env["CREW_TEST_WEBHOOK"] = self.webhook
        self.put("away-control.json", '{"issue": 7}')
        self.away = {"state": "away", "entry": "entry1", "started": START, "until": START, "words": ""}
        self.comments = [comment(self.away, "away", "entry1")]
        self.gh = Path(self.tmp) / "bin/gh"
        self.update_comments()
        self.output = io.StringIO()
        self.event_file = Path(self.tmp) / "event.json"

    def update_comments(self):
        self.gh.write_text("#!/usr/bin/env python3\nprint(%r)\n" % json.dumps([self.comments]))
        self.gh.chmod(0o755)

    def event(self, kind, id=None):
        event = {"kind": kind, "id": id or kind, "url": "https://example.test/record/" + kind}
        event.update({field: field + " https://example.test/item" for field in notify.KINDS[kind][1]})
        return event

    def send(self, event, now=NOW):
        self.event_file.write_text(json.dumps(event))
        with patch.dict(os.environ, self.env), patch.object(notify.time, "time", return_value=now), contextlib.redirect_stdout(self.output):
            self.assertEqual(cli._shared.main(["notify", "--project", self.project, "--event-file", str(self.event_file)]), 0)

    def tick(self, now=NOW, force=False):
        with patch.dict(os.environ, self.env), contextlib.redirect_stdout(self.output):
            return notify.tick(self.values, self.state, now, force=force)

    def assert_no_secret(self):
        text = self.output.getvalue() + "".join(p.read_text() for p in Path(self.state).rglob("*") if p.is_file())
        self.assertNotIn(self.webhook, text)
        self.assertNotIn(self.server.secret, text)

    def test_all_messages_and_restart_dedupe(self):
        for i, kind in enumerate(notify.KINDS):
            self.send(self.event(kind), NOW + 120 * i)
            self.send(self.event(kind), NOW + 120 * i + 1)
        self.assertEqual(len(self.server.messages), len(notify.KINDS))
        for payload, kind in zip(self.server.messages, notify.KINDS):
            self.assertIn(notify.KINDS[kind][0], payload["text"])
            self.assertIn("https://example.test/record/" + kind, payload["text"])
        self.tick(NOW + 2000)
        self.assertEqual(len(self.server.messages), len(notify.KINDS))
        self.assert_no_secret()
        print("fake webhook: all 10 event kinds delivered once; replay suppressed")

    def test_return_cancels_future_retry_and_no_new_posts(self):
        self.server.code = 503
        self.send(self.event("land"))
        self.comments.append(comment({"state": "returned", "entry": "entry1", "returned": START}, "away-return", "return1"))
        self.comments[-1]["body"] = self.comments[-1]["body"].replace("```json\n", "`").replace("\n```", "`")
        self.update_comments()
        self.tick(NOW + 1, force=True)
        self.send(self.event("ask"))
        self.tick(NOW + 100)
        self.assertEqual(len(self.server.attempts), 1)
        self.assertEqual(json.loads(notify.files(self.state)[0].read_text())["status"], "cancelled")
        self.assert_no_secret()

    def test_backoff_and_recovered_failure_in_return_status(self):
        self.server.code = 503
        self.send(self.event("stop"))
        self.tick(NOW + 29)
        self.assertEqual(len(self.server.attempts), 1)
        self.tick(NOW + 30)
        self.assertEqual(len(self.server.attempts), 2)
        self.tick(NOW + 89)
        self.server.code = 200
        self.tick(NOW + 90)
        self.assertEqual(len(self.server.messages), 1)
        with patch.dict(os.environ, self.env), contextlib.redirect_stdout(self.output):
            cli._shared.main(["notify", "--project", self.project, "--status"])
        self.assertIn("failures=2; status=sent", self.output.getvalue())
        self.assert_no_secret()
        print("fake webhook: rejection retries at +30/+90s; recovered failures retained")

    def test_digest_without_lands_and_urgent_suppression(self):
        wakes = self.tick()
        self.assertEqual(wakes[0]["reason"], "notify-digest")
        self.send(self.event("land"))
        self.send(self.event("digest"), NOW + 1)
        self.assertEqual(len(self.server.messages), 1)
        self.assertFalse(self.tick(NOW + 59))
        self.assertEqual(self.tick(NOW + 60)[0]["reason"], "notify-digest")
        self.send(self.event("digest"), NOW + 60)
        self.assertFalse(self.tick(NOW + 61))

    def test_unavailable_and_untrusted_away_fail_closed(self):
        self.comments = [comment(self.away, "away", "entry1", login="stranger")]
        self.update_comments()
        self.send(self.event("land"))
        self.assertFalse(self.server.attempts)
        self.gh.write_text("#!/bin/sh\necho private-error >&2\nexit 1\n")
        self.send(self.event("land"))
        self.assertNotIn("private-error", self.output.getvalue())
        self.assert_no_secret()

    def test_new_away_entry_gets_its_own_dedupe_and_replay_ignored(self):
        event = self.event("land")
        self.send(event)
        newer = dict(self.away, entry="entry2")
        self.comments += [comment(newer, "away", "entry2"), self.comments[0]]
        self.update_comments()
        self.send(event, NOW + 1)
        self.assertEqual(len(self.server.messages), 2)
        edited = comment(dict(newer, entry="entry3"), "away", "entry3")
        edited.update(created_at="first", updated_at="edited")
        self.assertEqual(notify.away_record(self.comments + [edited], "acme-bot")["entry"], "entry2")

    def test_unavailable_record_defers_pending_delivery(self):
        self.server.code = 503
        self.send(self.event("land"))
        self.gh.write_text("#!/bin/sh\necho private-error >&2\nexit 1\n")
        self.server.code = 200
        self.tick(NOW + 30)
        self.assertEqual(len(self.server.attempts), 1)
        self.assertIn("away record unavailable", self.output.getvalue())
        self.assert_no_secret()

    def test_watcher_delivers_digest_wake_once_across_rearm(self):
        Path(self.state_file).write_text(json.dumps({"crew-acme-widgets": {"0": "ash"}}))
        self.away["started"] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=70)).isoformat()
        self.comments = [comment(self.away, "away", "entry1")]
        self.update_comments()
        args = ("watch", "--project", self.project, "--no-nudge", "--interval", "0.01", "--backstop", "0.01")
        first = self.crew(*args)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("notify-digest: away digest due", first.stdout)
        second = self.crew(*args)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        queue = (Path(self.state) / "wake/queue.jsonl").read_text().splitlines()
        self.assertEqual(sum(json.loads(line)["reason"] == "notify-digest" for line in queue), 1)
        print("watcher: digest due delivered once across rearm; fake endpoint ready")

    def test_slack_render_keeps_recorded_ask(self):
        out = Path(self.tmp) / "render"
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output):
            self.assertEqual(cli._shared.crew_render.main(["--project", self.project, "--out", str(out)]), 0)
        brief = (out / "runtime/coordinator.md").read_text()
        self.assertIn("gh issue edit <n> --add-label crew:needs-md", brief)
        self.assertIn("binding's Slack section", brief)
        self.assertNotIn(self.webhook, brief)

    def test_ambiguous_timeout_never_resends(self):
        with patch.object(notify.urllib.request.OpenerDirector, "open", side_effect=socket.timeout(self.webhook)):
            self.send(self.event("land"))
        self.tick(NOW + 500)
        self.assertFalse(self.server.attempts)
        self.assertIn("acceptance uncertain", self.output.getvalue())
        self.assertEqual(json.loads(notify.files(self.state)[0].read_text())["status"], "uncertain")
        self.assert_no_secret()

    def test_crash_after_acceptance_never_resends_on_restart(self):
        original = notify.urllib.request.OpenerDirector.open

        def crash(opener, *args, **kwargs):
            original(opener, *args, **kwargs).close()
            raise SystemExit("simulated crash after acceptance")

        with patch.object(notify.urllib.request.OpenerDirector, "open", new=crash):
            with self.assertRaises(SystemExit):
                self.send(self.event("land"))
        self.tick(NOW + 500)
        self.assertEqual(len(self.server.messages), 1)
        self.assertEqual(json.loads(notify.files(self.state)[0].read_text())["status"], "uncertain")
        self.assert_no_secret()

    def test_secret_event_rejected_and_non_slack_quiet(self):
        self.send(dict(self.event("land"), title=self.webhook))
        self.assertFalse(notify.files(self.state))
        self.values["backends.owner-channel.name"] = "github"
        self.assertFalse(self.tick())
        self.assert_no_secret()

    def test_missing_secret_refuses_up_without_session(self):
        self.env.pop("CREW_TEST_WEBHOOK")
        r = self.up()
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing Slack webhook environment variable CREW_TEST_WEBHOOK", r.stdout)
        self.assertFalse(self.calls())

    def test_private_launch_uses_stdin_and_sanitizes_errors(self):
        from subprocess import CompletedProcess
        with patch.object(cli._shared.tmux.backends["tmux"], "tmux", return_value=CompletedProcess([], 0, "", "")), \
                patch.object(cli._shared.tmux.subprocess, "run", return_value=CompletedProcess([], 1, "", self.webhook)) as run:
            with self.assertRaisesRegex(RuntimeError, "private environment launch refused"):
                cli._shared.tmux.new_session("s", "w", self.tmp, {}, "sleep 20", {"CREW_TEST_WEBHOOK": self.webhook})
        self.assertNotIn(self.webhook, str(run.call_args.args))
        self.assertIn(self.webhook, run.call_args.kwargs["input"])


if __name__ == "__main__":
    unittest.main()
