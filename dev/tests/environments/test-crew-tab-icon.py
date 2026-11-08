"""Role emoji on tmux tabs (#1157): display-only through @crew_icon, window names stay the targeting identity.

Run with python3 dev/tests/environments/test-crew-tab-icon.py. The fake tmux records every call; the width check
starts a real tmux only on a private socket under a temp TMUX_TMPDIR, never the owner's server (#1156).
"""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # dev/tests/: crew_testlib
from crew_testlib import SCRIPTS, SpawnBase

ADAPTER = os.path.join(os.path.dirname(SCRIPTS), "environments", "terminal", "sessions", "tmux", "adapter.py")
ICON = "#{?@crew_icon,#{@crew_icon} ,}"


class FakeTmux(SpawnBase):
    def icons(self):
        return {c[3]: c[5] for c in self.calls() if c[:2] == ["set-option", "-w"] and c[4] == "@crew_icon"}

    def test_icon_is_display_only_and_window_scoped(self):
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.assertEqual(self.windows()[-1][self.windows()[-1].index("-n") + 1], "ben-7")
        with open(self.state_file) as f:
            self.assertEqual(json.load(f)["crew-acme-widgets"], {"0": "ash", "10": "ben-7"})
        # coordinator 🔥; Ben's default 🛠️ (U+1F6E0 U+FE0F) shows without its variation selector
        self.assertEqual(self.icons(), {"=crew-acme-widgets:0": "🔥", "=crew-acme-widgets:10": "\U0001f6e0"})
        formats = [c for c in self.calls() if c[:2] == ["set-option", "-w"] and "format" in c[4]]
        self.assertEqual({(c[3], c[4]) for c in formats}, {(t, o) for t in self.icons()
                                                            for o in ("window-status-format",
                                                                      "window-status-current-format")})
        self.assertTrue(all(c[5] == ICON + "#I:#W#{?window_flags,#{window_flags}, }" for c in formats), formats)
        self.assertFalse([c for c in self.calls() if c[0] == "set-option" and "-g" in c])
        self.assertFalse([c for c in self.calls() if c[0] == "rename-window"])
        r = self.crew("kill", "ben-7", "--project", self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(["kill-window", "-t", "=crew-acme-widgets:10"], self.calls())

    def test_role_without_single_codepoint_emoji_shows_name_only(self):
        with open(self.project) as f:
            text = f.read()
        text = text.replace('name = "Ben" }', 'name = "Ben", emoji = "" }').replace(
            'name = "Vera" }', 'name = "Vera", emoji = "\U0001f469\u200d\U0001f4bb" }')
        with open(self.project, "w") as f:
            f.write(text)
        self.assertEqual(self.spawn("builder", "--issue", "7").returncode, 0)
        self.pr(7, "codex gpt-6.1-sol medium")
        r = self.spawn("reviewer", "--pr", "7")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([t for t in self.icons() if t != "=crew-acme-widgets:0"], [])
        self.assertEqual([w[w.index("-n") + 1] for w in self.windows()], ["ben-7", "vera-7-r1-review"])


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class RealTmuxWidth(unittest.TestCase):
    """AC 4: a single-codepoint emoji widens the tab by exactly its two cells plus one space."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tt")  # short: the socket path has a length limit
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = patch.dict(os.environ, {"TMUX_TMPDIR": self.tmp, "HOME": self.tmp})
        env.start()
        self.addCleanup(env.stop)
        spec = importlib.util.spec_from_file_location("tab_icon_tmux", ADAPTER)
        self.tmux = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tmux)
        self.tmux.bind("icon-test")
        self.assertTrue(self.tmux.default_socket().startswith(self.tmp))
        self.tmux.new_session("icon-test", "ash", self.tmp, {}, "sleep 30")
        self.addCleanup(self.tmux.tmux, "kill-server")

    def width(self):
        return int(self.tmux.tmux("display-message", "-p", "-t", "=icon-test:0",
                                  "#{w:#{E:window-status-format}}").stdout)

    def test_single_codepoint_emoji_keeps_tab_width(self):
        bare = self.width()
        self.tmux.icon("icon-test", 0, "🔥")
        self.assertEqual(self.width(), bare + 3)
        self.tmux.icon("icon-test", 0, "🔥")  # a second icon call never stacks the prefix
        self.assertEqual(self.width(), bare + 3)
        self.assertEqual(self.tmux.list_windows("icon-test"), [(0, "ash")])
        self.assertTrue(self.tmux.has_session("icon-test"))


if __name__ == "__main__":
    unittest.main()
