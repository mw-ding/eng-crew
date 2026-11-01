"""Tests for crew send, moved from test-crew.py; fixtures in crew_testlib.py (stdlib only)."""
import importlib.machinery
import importlib.util
import json
import os
import textwrap
import unittest
from crew_testlib import CREW, SendBase


class Send(SendBase):
    def test_append_format_and_nudge(self):
        sha = "a" * 40
        r = self.send("ben-7", "fix", "#171", sha, "https://github.com/acme/widgets/pull/171", "docs/x.md")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r2 = self.send("ben-7", "ci-red", "#171")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        first, second = self.inbox()
        self.assertEqual(sorted(first), ["from", "id", "kind", "refs", "ts"])
        self.assertEqual(first["kind"], "fix")
        self.assertEqual(first["refs"], ["#171", sha, "https://github.com/acme/widgets/pull/171", "docs/x.md"])
        self.assertEqual(first["from"], "coordinator")
        self.assertRegex(first["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertNotEqual(first["id"], second["id"])
        self.assertIn("sent %s to ben-7" % first["id"], r.stdout)
        keys = [c for c in self.calls() if c[0] == "send-keys"]
        self.assertEqual(keys[:2], [["send-keys", "-t", "=crew-acme-widgets:10", "-l", "inbox: " + first["id"]],
                                    ["send-keys", "-t", "=crew-acme-widgets:10", "Enter"]])
        self.assertEqual(len(keys), 4)

    def test_oversized_or_payload_rejected(self):
        diff = "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-old\n+new\n"
        for refs in [["p" * 201], ["d/" + "y" * 198] * 5, [diff], ["---a/x"], ["@@"],
                     ["Traceback"], ["two words"], ["#171", "line\nbreak"]]:
            r = self.crew("send", "--project", self.project, "ben-7", "fix", "--", *refs)  # --: refs may start with -
            self.assertEqual(r.returncode, 2, (refs, r.stdout, r.stderr))
            self.assertIn("refusing send", r.stdout)
        self.assertIn("over 1024", self.send("ben-7", "fix", *["d/" + "y" * 198] * 5).stdout)  # each ref legal
        self.assertEqual(self.send("ben-7", "Fix it", "#1").returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-7.jsonl")))
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])

    def test_unknown_window_refused(self):
        r = self.send("ben-8", "fix", "#1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no window ben-8", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.state, "inbox", "ben-8.jsonl")))
        self.assertEqual([c for c in self.calls() if c[0] == "send-keys"], [])


# Real screens (#308), bottom rows of `tmux capture-pane -p` with the cursor from `#{cursor_x} #{cursor_y}`; the
# workdir and status line are redacted. Codex 0.164.0 after three `crew send` nudges whose Enter each added a newline:
CODEX_STACKED = ("", "• Explored", "  └ List probe", "    + Show details", "",
                 "■ Conversation interrupted - use /feedback if something went wrong", "", "",
                 "› inbox: 20261031T081746Z-30673c", "  inbox: 20261031T085326Z-c9db18",
                 "  inbox: 20261031T092356Z-55f592", "", "", "  GPT-5.5 xhigh · <workdir>",
                 " " * 64 + "⚠ 1 warning · f2 to view", "")
# The same stack once submitted: it is now a user message in the transcript and the composer is empty.
CODEX_SUBMITTED = ("■ Conversation interrupted - use /feedback if something went wrong", "", "",
                   "› inbox: 20261031T081746Z-30673c", "  inbox: 20261031T085326Z-c9db18",
                   "  inbox: 20261031T092356Z-55f592", "", "", "", "• Working (1s • esc to interrupt)", "", "",
                   "› Ask Codex to do anything", "", "  GPT-5.5 xhigh · <workdir>", "  ? for shortcuts", "")
# Claude Code 2.1.310 with a two-line draft: the glyph row has a no-break space after `❯`.
CLAUDE_STACKED = ("", "─" * 80, "❯\xa0inbox: 20261031T100200Z-111111", "  inbox: 20261031T100300Z-222222", "",
                  "─" * 80, "  ⏸ plan mode on (shift+tab to cycle)", "")


class Composer(unittest.TestCase):
    """The composer check on the real screens: only a composer of nothing but earlier nudges is cleared."""

    @classmethod
    def setUpClass(cls):
        loader = importlib.machinery.SourceFileLoader("crew_cli", CREW)
        cls.mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("crew_cli", loader))
        loader.exec_module(cls.mod)

    def test_real_screens(self):
        stack = ["inbox: 20261031T081746Z-30673c", "inbox: 20261031T085326Z-c9db18", "inbox: 20261031T092356Z-55f592"]
        screen = "\n".join(CODEX_STACKED)
        self.assertEqual(self.mod.composer_draft(screen, (2, 11)), stack + [""])
        self.assertEqual(self.mod.stale_nudges(screen, (2, 11)), stack + [""])
        screen = "\n".join(CODEX_SUBMITTED)  # the transcript's copy is above the cursor's composer, never read
        self.assertEqual(self.mod.composer_draft(screen, (2, 12)), ["Ask Codex to do anything"])
        self.assertEqual(self.mod.stale_nudges(screen, (2, 12)), [])
        screen = "\n".join(CLAUDE_STACKED)
        self.assertEqual(self.mod.stale_nudges(screen, (2, 4)),
                         ["inbox: 20261031T100200Z-111111", "inbox: 20261031T100300Z-222222", ""])

    def test_other_text_never_cleared(self):
        screen = "\n".join(CODEX_STACKED).replace("› inbox: 20261031T081746Z-30673c", "› fix the flaky test")
        self.assertEqual(self.mod.composer_draft(screen, (2, 11))[0], "fix the flaky test")
        self.assertEqual(self.mod.stale_nudges(screen, (2, 11)), [])
        screen = "\n".join(CODEX_STACKED)
        self.assertEqual(self.mod.stale_nudges(screen, (9, 10)), [])  # cursor inside the last line
        self.assertEqual(self.mod.stale_nudges(screen, (32, 9)), [])  # a draft line below the cursor
        self.assertEqual(self.mod.stale_nudges(screen, None), [])  # tmux could not answer
        self.assertIsNone(self.mod.composer_draft(screen, (0, 3)))  # no composer at the cursor
        self.assertEqual(self.mod.stale_nudges("\n".join(CODEX_STACKED[:8]), (0, 7)), [])


# A tmux wrapper with a composer model in $FAKE_COMPOSER: `-l` text joins the draft's last line, C-u clears a line
# and then joins it to the one above (as in Codex and Claude Code), Enter takes the next of `enters` (the last one
# repeats): `submit` moves the draft into the transcript, `newline` adds a line. Every other call goes to the base fake.
FAKE_COMPOSER = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    c = json.load(open(os.environ["FAKE_COMPOSER"]))
    def rows(draft):
        return ["› " + draft[0]] + ["  " + line for line in draft[1:]]
    if args[0] in ("capture-pane", "display-message") and (args[0] == "capture-pane" or "#{cursor_x}" in args[-1]):
        with open(os.environ["FAKE_TMUX_LOG"], "a") as f:
            f.write(json.dumps(args) + "\\n")
        screen = c["history"] + [""] + (rows(c["draft"]) if c["draft"] else ["› Ask Codex to do anything"])
        x = 2 + len(c["draft"][-1]) if c["draft"] else 2
        print("\\n".join([r.rstrip() for r in screen] + ["", "  ? for shortcuts"]) if args[0] == "capture-pane"
              else "%d %d" % (x, len(screen) - 1))
        sys.exit(0)
    if args[0] == "send-keys":
        draft = c["draft"]
        if "-l" in args:
            c["draft"] = draft[:-1] + [(draft[-1] if draft else "") + args[-1]]
        for key in args[args.index("-t") + 2:] if "-l" not in args else []:
            if key == "C-u" and c.get("clears", True) and draft:
                draft[-1:] = [""] if draft[-1] else []
            elif key == "Enter":
                mode = c["enters"].pop(0) if len(c["enters"]) > 1 else c["enters"][0]
                if mode == "submit" and draft:
                    c["history"], c["draft"] = c["history"] + rows(draft), []
                elif mode == "newline":
                    c["draft"] = (draft or [""]) + [""]
            draft = c["draft"]
        json.dump(c, open(os.environ["FAKE_COMPOSER"], "w"))
    os.execv(os.path.join(os.path.dirname(sys.argv[0]), "tmux-base"), ["tmux"] + args)
    """)


class VerifiedNudge(SendBase):
    """crew send on a fake composer: clear earlier nudges, type once, retry Enter only, exit 4 if never submitted."""

    def setUp(self):
        super().setUp()
        bindir = os.path.join(self.tmp, "bin")
        os.rename(os.path.join(bindir, "tmux"), os.path.join(bindir, "tmux-base"))
        with open(os.path.join(bindir, "tmux"), "w") as f:
            f.write(FAKE_COMPOSER)
        os.chmod(os.path.join(bindir, "tmux"), 0o755)
        self.composer = os.path.join(self.tmp, "composer.json")
        self.env["FAKE_COMPOSER"] = self.composer

    def model(self, draft=(), enters=("submit",), **kv):
        with open(self.composer, "w") as f:
            json.dump(dict({"history": ["› inbox: 20261031T070000Z-000000"], "draft": list(draft),
                            "enters": list(enters)}, **kv), f)

    def current(self):
        with open(self.composer) as f:
            return json.load(f)

    def keys(self):
        return [c[3:] for c in self.calls() if c[0] == "send-keys"]

    def test_stacked_composer_cleared_then_submitted(self):
        self.model(draft=["inbox: 20261031T081746Z-30673c", "inbox: 20261031T085326Z-c9db18", ""])
        r = self.send("ben-7", "land", "#12")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        nudge = "inbox: " + self.inbox()[0]["id"]
        self.assertEqual(self.keys(), [["C-u"] * 6, ["-l", nudge], ["Enter"]])
        self.assertIn("cleared 2 earlier inbox line(s)", r.stdout)
        self.assertEqual(self.current()["draft"], [])
        self.assertEqual(self.current()["history"][-1], "› " + nudge)  # submitted alone, not after the old lines

    def test_swallowed_enter_retried_never_retyped(self):
        self.model(enters=["newline", "submit"])
        r = self.send("ben-7", "fix", "#12")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        nudge = "inbox: " + self.inbox()[0]["id"]
        self.assertEqual(self.keys(), [["-l", nudge], ["Enter"], ["Enter"]])
        self.assertEqual(self.current()["history"][-2:], ["› " + nudge, "  "])
        self.assertIn("sent ", r.stdout)

    def test_never_submitted_exits_4(self):
        self.model(enters=["newline"])
        r = self.send("ben-7", "land", "#12", "--wait-ack", "5")
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        msg_id = self.inbox()[0]["id"]  # the inbox line stays: the message is not lost
        self.assertEqual(self.keys(), [["-l", "inbox: " + msg_id]] + [["Enter"]] * 4)
        self.assertIn("nudge not submitted: %s to ben-7" % msg_id, r.stdout)
        self.assertIn("after 3 Enter retries", r.stdout)
        self.assertIn("treat ben-7 as ambiguous", r.stdout)
        self.assertNotIn("no ack", r.stdout)
        r = self.send("ben-7", "land", "#12")  # the next send clears the leftover nudge and its newlines first
        self.assertEqual(self.keys()[5], ["C-u"] * 10)

    def test_other_text_kept(self):
        self.model(draft=["fix the flaky test"])
        r = self.send("ben-7", "fix", "#12")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(["C-u"], [k[:1] for k in self.keys()])
        self.assertEqual(self.current()["history"][-1], "› fix the flaky testinbox: " + self.inbox()[0]["id"])

    def test_clear_that_fails_types_nothing(self):
        self.model(draft=["inbox: 20261031T081746Z-30673c"], clears=False)
        r = self.send("ben-7", "land", "#12")
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertEqual(self.keys(), [["C-u"] * 2])
        self.assertIn("still holds earlier inbox lines after the clear; nothing typed", r.stdout)
        self.assertEqual(self.current()["draft"], ["inbox: 20261031T081746Z-30673c"])


if __name__ == "__main__":
    unittest.main()
