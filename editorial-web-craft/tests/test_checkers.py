#!/usr/bin/env python3
"""Unit tests for WARN behaviour that run_fixtures.py (which counts FAILs only) cannot pin.

Covers check_semantics.py (named scrollable regions, named sections) and check_zindex.py (the
stacking-context warning on elements that have no children).

Run from the plugin folder: python3 tests/test_checkers.py
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMANTICS = ROOT / "skills" / "html5-native-fallback" / "scripts" / "check_semantics.py"
ZINDEX = ROOT / "skills" / "z-index-coordinate-matrix" / "scripts" / "check_zindex.py"


def run(script, *files):
    r = subprocess.run([sys.executable, str(script), *map(str, files)], capture_output=True, text=True, timeout=30)
    lines = [l.strip() for l in r.stdout.splitlines()]
    return (r.returncode, [l[4:].strip() for l in lines if l.startswith("WARN")],
            [l[4:].strip() for l in lines if l.startswith("FAIL")])


class Temp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ewc checkers ")
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path


def page(body, style=""):
    style_tag = f"<style>\n{style}\n</style>" if style else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>t</title>{style_tag}</head>'
            f"<body><main><h1>Title</h1>{body}</main></body></html>")


class SemanticsTest(Temp):
    def check(self, body):
        return run(SEMANTICS, self.write("p.html", page(body)))

    def test_section_named_by_aria_is_not_warned(self):
        for attr in ('aria-label="Notes"', 'aria-labelledby="t"', "aria-label='Notes'"):
            with self.subTest(attr):
                code, warns, fails = self.check(f"<section {attr}><p>x</p></section>")
                self.assertEqual((code, warns, fails), (0, [], []))

    def test_section_without_heading_or_name_still_warns(self):
        for opening in ("<section>", '<section aria-label="">', '<section aria-label="  ">', '<section class="a">'):
            with self.subTest(opening):
                code, warns, fails = self.check(f"{opening}<p>x</p></section>")
                self.assertEqual(code, 0)
                self.assertEqual([w for w in warns if "<section> without a heading" in w], warns)
                self.assertEqual(len(warns), 1, warns)

    def test_section_with_heading_is_quiet(self):
        self.assertEqual(self.check("<section><h2>Part</h2></section>"), (0, [], []))

    def test_named_scrollable_region_is_allowed(self):
        for attrs in ('role="region" aria-label="Data" tabindex="0"',
                      'tabindex="0" aria-labelledby="t" role="region"',
                      "role='region' aria-label='Data' tabindex='0'"):
            with self.subTest(attrs):
                code, warns, fails = self.check(f"<div {attrs}><p>x</p></div>")
                self.assertEqual((code, fails), (0, []))

    def test_unnamed_or_non_region_focusables_still_fail(self):
        for tag in ('<div role="region" tabindex="0">', '<div role="region" aria-label="" tabindex="0">',
                    '<span aria-label="X" tabindex="0">', '<div tabindex="0">',
                    '<div role="group" aria-label="X" tabindex="0">'):
            with self.subTest(tag):
                code, warns, fails = self.check(f"{tag}<p>x</p></{tag[1:4] if tag[1:4] == 'div' else 'span'}>")
                self.assertEqual(code, 1)
                self.assertTrue(any("tabindex on" in f for f in fails), fails)


class ZindexTest(Temp):
    CSS = ":root { --z-base: 0; --z-raised: 10; }\n.card-bar { transform: translateZ(0); height: 4px; }\n"

    def check(self, css, html=None, inline=False):
        files = []
        if inline:
            files.append(self.write("p.html", page(html, css)))
        else:
            files.append(self.write("s.css", css))
            if html is not None:
                files.append(self.write("p.html", page(html)))
        return run(ZINDEX, *files)

    def stacking(self, warns):
        return [w for w in warns if "creates a stacking context" in w]

    def test_css_only_still_warns(self):
        code, warns, _ = self.check(self.CSS)
        self.assertEqual((code, len(self.stacking(warns))), (0, 1), warns)

    def test_html_with_only_empty_elements_skips_the_warning(self):
        for html in ('<div class="card-bar"></div>', '<div class="card-bar">\n  </div><div class="card-bar"></div>',
                     '<div class="x card-bar y"></div>'):
            with self.subTest(html):
                code, warns, _ = self.check(self.CSS, html)
                self.assertEqual((code, self.stacking(warns)), (0, []), warns)

    def test_inline_style_in_the_same_html_is_used(self):
        code, warns, _ = self.check(self.CSS, '<div class="card-bar"></div>', inline=True)
        self.assertEqual((code, self.stacking(warns)), (0, []), warns)

    def test_an_element_with_children_keeps_the_warning(self):
        for html in ('<div class="card-bar"><span>tip</span></div>', '<div class="card-bar">text</div>',
                     '<div class="card-bar"></div><div class="card-bar"><i></i></div>'):
            with self.subTest(html):
                code, warns, _ = self.check(self.CSS, html)
                self.assertEqual(len(self.stacking(warns)), 1, warns)

    def test_no_matching_element_keeps_the_warning(self):
        code, warns, _ = self.check(self.CSS, '<div class="other"></div>')
        self.assertEqual(len(self.stacking(warns)), 1, warns)

    def test_void_element_counts_as_empty_and_id_selectors_work(self):
        css = "#card-photo { filter: blur(2px); }\n"
        code, warns, _ = self.check(css, '<img id="card-photo" src="a.png" alt="">')
        self.assertEqual(self.stacking(warns), [], warns)
        code, warns, _ = self.check(css, '<div id="card-photo"><p>x</p></div>')
        self.assertEqual(len(self.stacking(warns)), 1, warns)

    def test_descendant_selector_checks_the_last_compound(self):
        css = ".list .card-bar { transform: scale(1); }\n"
        _, warns, _ = self.check(css, '<ul class="list"><li><div class="card-bar"></div></li></ul>')
        self.assertEqual(self.stacking(warns), [], warns)
        _, warns, _ = self.check(css, '<div class="list"><div class="card-bar"><b></b></div></div>')
        self.assertEqual(len(self.stacking(warns)), 1, warns)

    def test_message_names_the_children_condition(self):
        _, warns, _ = self.check(self.CSS)
        self.assertTrue(any("if this element has children" in w for w in warns), warns)


if __name__ == "__main__":
    unittest.main()
