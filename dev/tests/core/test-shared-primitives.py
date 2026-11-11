#!/usr/bin/env python3
"""Tests for the shipped shared modules core/secret-patterns.py,
core/path-glob.py and core/markdown-scan.py (#281).

Covers: the repo guard, crew-config.py and docs-scan.py use the very same
definitions (no second copy to drift); secret detection and placeholder
exceptions; glob semantics (`**` crosses `/`, `*` and `?` do not); fenced
blocks, code spans, HTML comments and link destinations. Run in CI.
"""
import importlib.util
import os
import unittest

TESTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # dev/tests/
ROOT = os.path.dirname(os.path.dirname(TESTS))


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = load("secret_patterns", "core/secret-patterns.py")
pg = load("path_glob", "core/path-glob.py")
ms = load("markdown_scan", "core/markdown-scan.py")
check_repo = load("check_repo", "scripts/check-repo.py")
crew_config = load("crew_config", "core/crew-config.py")
docs_scan = load("docs_scan", "scripts/docs-scan.py")


def same(a, b):
    """Two loads of one module give distinct objects; equal source and patterns mean one definition."""
    if hasattr(a, "pattern"):
        return a.pattern == b.pattern and a.flags == b.flags
    if callable(a):
        return (a.__code__.co_code == b.__code__.co_code
                and os.path.realpath(a.__code__.co_filename) == os.path.realpath(b.__code__.co_filename))
    return a == b


class ConsumersShareDefinitions(unittest.TestCase):
    def test_guard_and_config_use_the_shared_secret_patterns(self):
        for mod in (check_repo, crew_config.secret_patterns):
            with self.subTest(mod=mod.__name__):
                self.assertEqual([(r, rx.pattern, why) for r, rx, why in mod.PATTERNS],
                                 [(r, rx.pattern, why) for r, rx, why in sp.PATTERNS])
                for name in ("PLACEHOLDER", "BEARER", "URL_CRED", "is_placeholder"):
                    self.assertTrue(same(getattr(mod, name), getattr(sp, name)), name)

    def test_guard_and_config_use_the_shared_glob(self):
        for fn in (check_repo.glob_regex, crew_config.path_glob.glob_regex):
            self.assertTrue(same(fn, pg.glob_regex))

    def test_guard_and_docs_scan_use_the_shared_markdown_scan(self):
        for mod in (check_repo, docs_scan.markdown_scan):
            for name in ("LINK_OPEN", "REFDEF", "unfenced", "strip_code_spans", "strip_html_comments",
                         "link_destinations"):
                self.assertTrue(same(getattr(mod, name), getattr(ms, name)), name)

    def test_config_no_longer_loads_the_guard(self):
        self.assertFalse(hasattr(crew_config, "check_repo"))
        self.assertFalse(hasattr(docs_scan, "repo_check"))


class SecretPatterns(unittest.TestCase):
    def test_tokens_found_and_placeholders_pass(self):
        self.assertEqual(crew_config.token_reasons("x ghp_" + "a" * 36),
                         ["GitHub token (ghp_/gho_/ghu_/ghs_/ghr_)"])
        self.assertEqual(crew_config.token_reasons("ghp_<token>"), [])
        self.assertEqual(crew_config.token_reasons("Authorization: Bear" + "er abc123"),
                         ["bearer auth header with a literal value"])
        self.assertEqual(crew_config.token_reasons("Authorization: Bearer <token>"), [])
        self.assertEqual(crew_config.token_reasons("https://u:" + "pw@host/x"), ["URL with embedded credentials"])
        self.assertEqual(crew_config.token_reasons("https://<user>:<pass>@host/x"), [])

    def test_is_placeholder(self):
        self.assertTrue(sp.is_placeholder("<token>"))
        self.assertTrue(sp.is_placeholder("<token>`."))
        self.assertFalse(sp.is_placeholder("<token>x"))
        self.assertFalse(sp.is_placeholder("token"))


class PathGlob(unittest.TestCase):
    def test_segments(self):
        rx = pg.glob_regex
        self.assertTrue(rx("docs/**").fullmatch("docs/a/b.md"))
        self.assertTrue(rx("docs/*.md").fullmatch("docs/a.md"))
        self.assertFalse(rx("docs/*.md").fullmatch("docs/a/b.md"))
        self.assertTrue(rx("a?.py").fullmatch("ab.py"))
        self.assertFalse(rx("a?.py").fullmatch("a/.py"))
        self.assertFalse(rx("a.py").fullmatch("aXpy"))


class MarkdownScan(unittest.TestCase):
    def test_fences_comments_spans_links(self):
        lines = ["[a](x.md)", "```", "[b](y.md)", "```", "<!-- [c](z.md) -->", "`[d](w.md)` [e](<v w.md>)"]
        visible = list(ms.strip_html_comments(ms.unfenced(lines)))
        self.assertEqual([n for n, _ in visible], [1, 6])
        self.assertEqual(ms.link_destinations(ms.strip_code_spans(visible[1][1])), ["v w.md"])
        self.assertEqual(ms.link_destinations("[p](other(v1).md)"), ["other(v1).md"])
        self.assertEqual(ms.scan_fences(["```", "x"], False), ([], 1))


if __name__ == "__main__":
    unittest.main()
