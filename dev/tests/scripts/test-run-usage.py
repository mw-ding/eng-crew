#!/usr/bin/env python3
"""Fixture test for scripts/run-usage.py and the Claude Code and Codex usage readers (#1557), temp dirs only.

Covers both readers on fixture session logs (dedupe, start cut-off, other cwd, pre-start totals), the `tokens n/a`
fallback for an adapter without a reader or without a log, number and duration formats, and that no path is printed.
Run in CI.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import tempfile
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(TESTS)), "scripts")
spec = importlib.util.spec_from_file_location("run_usage", os.path.join(SCRIPTS, "run-usage.py"))
ru = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ru)

START, NOW = "2026-11-10T07:00:00Z", "2026-11-10T07:23:10Z"


def claude_line(ts, msg_id, req, inp, write, read, out, model="claude-opus-5-5"):
    return {"type": "assistant", "timestamp": ts, "requestId": req, "uuid": msg_id + ts,
            "message": {"id": msg_id, "model": model, "usage": {
                "input_tokens": inp, "cache_creation_input_tokens": write, "cache_read_input_tokens": read,
                "output_tokens": out}}}


def codex_count(ts, inp, cached, out):
    return {"timestamp": ts, "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {
        "input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out, "total_tokens": inp + out}}}}


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write((rec if isinstance(rec, str) else json.dumps(rec)) + "\n")


class RunUsageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.realpath(self.tmp.name)
        self.wt = os.path.join(self.home, "runs", "1557-abc-builder-build")
        os.makedirs(self.wt)
        env = {"CLAUDE_CONFIG_DIR": os.path.join(self.home, "claude"), "CODEX_HOME": os.path.join(self.home, "codex")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_usage(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ru.main(list(argv) + ["--now", NOW])
        return code, out.getvalue().strip(), err.getvalue().strip()

    def record(self, **fields):
        path = os.path.join(self.home, "run.json")
        rec = {"engine": "claude-code", "worktree": self.wt, "start": START, "model": "opus", "effort": "high"}
        rec.update(fields)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f)
        return path

    def claude_logs(self):
        folder = os.path.join(self.home, "claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", self.wt))
        write_jsonl(os.path.join(folder, "s1.jsonl"), [
            claude_line("2026-11-10T06:59:00Z", "m0", "r0", 9, 9, 9, 9),  # before the start
            claude_line("2026-11-10T07:01:00Z", "m1", "r1", 2, 100_000, 0, 20_000),
            claude_line("2026-11-10T07:01:01Z", "m1", "r1", 2, 100_000, 0, 20_000),  # same message, streamed
            "not json",
            {"type": "user", "timestamp": "2026-11-10T07:02:00Z", "message": {"role": "user"}},
            claude_line("2026-11-10T07:03:00Z", "m2", "r2", 3, 40_000, 1_100_000, 18_200),
        ])
        write_jsonl(os.path.join(folder, "s1", "subagents", "a.jsonl"), [
            claude_line("2026-11-10T07:04:00Z", "m3", "r3", 0, 0, 0, 0, model="<synthetic>")])

    def test_claude_reader(self):
        self.claude_logs()
        self.assertEqual(self.run_usage("--run", self.record()),
                         (0, "Run: 23m 10s · 1.24M in (1.1M cached) / 38.2k out · claude-opus-5-5 (high)", ""))

    def test_codex_reader(self):
        sessions = os.path.join(self.home, "codex", "sessions", "2026", "11", "10")
        meta = {"timestamp": "2026-11-10T06:50:00Z", "type": "session_meta", "payload": {"cwd": self.wt}}
        ctx = {"timestamp": "2026-11-10T06:50:01Z", "type": "turn_context", "payload": {"model": "gpt-6.1-sol"}}
        write_jsonl(os.path.join(sessions, "rollout-a.jsonl"), [
            meta, ctx, codex_count("2026-11-10T06:55:00Z", 100_000, 90_000, 1_000),  # resumed: before the start
            codex_count("2026-11-10T07:10:00Z", 500_000, 400_000, 5_000),
            codex_count("2026-11-10T07:20:00Z", 1_340_000, 1_190_000, 39_200)])
        other = dict(meta, payload={"cwd": self.home})
        write_jsonl(os.path.join(sessions, "rollout-b.jsonl"), [other, codex_count(NOW, 7, 7, 7)])
        rec = self.record(engine="codex", model="gpt", effort="xhigh")
        self.assertEqual(self.run_usage("--run", rec),
                         (0, "Run: 23m 10s · 1.24M in (1.1M cached) / 38.2k out · gpt-6.1-sol (xhigh)", ""))

    def test_no_reader_or_no_log_is_na(self):
        self.assertEqual(self.run_usage("--engine", "pi", "--dir", self.wt, "--start", START, "--model", "m"),
                         (0, "Run: 23m 10s · tokens n/a · m", ""))
        self.assertEqual(self.run_usage("--run", self.record()), (0, "Run: 23m 10s · tokens n/a · opus (high)", ""))
        self.assertEqual(self.run_usage("--run", self.record(engine="codex")),
                         (0, "Run: 23m 10s · tokens n/a · opus (high)", ""))

    def test_unreadable_log_is_na_without_path(self):
        self.claude_logs()
        real_open = open

        def deny(path, *a, **k):
            if str(path).endswith(".jsonl"):
                raise PermissionError(13, "Permission denied", path)
            return real_open(path, *a, **k)
        with mock.patch("builtins.open", deny):
            code, out, err = self.run_usage("--run", self.record())
        self.assertEqual((code, out, err), (0, "Run: 23m 10s · tokens n/a · opus (high)", ""))

    def test_flags_override_record_and_coordinator_form(self):
        self.claude_logs()
        code, out, _ = self.run_usage("--engine", "claude-code", "--dir", self.wt, "--start", "2026-11-10T07:02:30Z")
        self.assertEqual((code, out), (0, "Run: 20m 40s · 1.14M in (1.1M cached) / 18.2k out · claude-opus-5-5"))

    def test_errors_name_no_path(self):
        missing = os.path.join(self.home, "nope.json")
        code, out, err = self.run_usage("--run", missing)
        self.assertEqual((code, out), (2, ""))
        self.assertNotIn(self.home, err)
        self.assertEqual(self.run_usage("--engine", "codex")[0], 2)
        self.assertEqual(self.run_usage("--engine", "codex", "--start", "yesterday")[0], 2)

    def test_formats(self):
        self.assertEqual([ru.count(n) for n in (0, 999, 1000, 38_249, 999_499, 999_500, 1_240_000)],
                         ["0", "999", "1k", "38.2k", "999k", "1M", "1.24M"])
        self.assertEqual([ru.duration(s) for s in (-5, 45, 65, 3725)], ["0s", "45s", "1m 05s", "1h 02m"])


if __name__ == "__main__":
    unittest.main()
