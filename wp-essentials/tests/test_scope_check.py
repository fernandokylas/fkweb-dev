"""Tests for skills/wp-page-update/scripts/scope_check.py."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "wp-page-update" / "scripts"))
import scope_check  # noqa: E402

PAGE = """<!doctype html>
<html><head><title>Shop</title><meta charset="utf-8"></head>
<body>
<header id="top"><nav><a href="/">Home</a></nav></header>
<main>
<section id="s1" class="hero wide"><h1>Welcome</h1><p>Fresh fish daily.</p></section>
<section id="pricing"><h2>Pricing</h2><p>From 10 euros.</p></section>
<footer id="foot"><p>Contact us</p></footer>
</main>
</body></html>
"""


class ScopeCheckTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_check(self, after_html, *args, before_html=PAGE):
        b, a = self.dir / "before.html", self.dir / "after.html"
        b.write_text(before_html, encoding="utf-8")
        a.write_text(after_html, encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scope_check.main([str(b), str(a), "--json", *args])
        return code, json.loads(out.getvalue()) if out.getvalue() else None

    def test_identical_pages_pass(self):
        code, res = self.run_check(PAGE, "--allow", "hero")
        self.assertEqual(code, 0)
        self.assertEqual(res["findings"], [])

    def test_in_scope_change_passes(self):
        code, res = self.run_check(PAGE.replace("Fresh fish daily.", "Fresh crab daily."), "--allow", "s1")
        self.assertEqual(code, 0)
        self.assertEqual([(f["region"], f["change"]) for f in res["findings"]], [("s1", "changed")])

    def test_whitespace_only_change_is_not_a_change(self):
        code, res = self.run_check(PAGE.replace("<p>Fresh fish daily.</p>", "<p>Fresh   fish\n daily.</p>"), "--allow", "x")
        self.assertEqual(code, 0)
        self.assertEqual(res["findings"], [])

    def test_out_of_scope_change_fails(self):
        code, res = self.run_check(PAGE.replace("From 10 euros.", "From 12 euros."), "--allow", "s1")
        self.assertEqual(code, 1)
        self.assertEqual(res["out_of_scope"][0]["region"], "pricing")

    def test_head_change_fails_unless_global_allowed(self):
        after = PAGE.replace("<title>Shop</title>", "<title>New shop</title>")
        code, res = self.run_check(after, "--allow", "s1")
        self.assertEqual(code, 1)
        self.assertEqual(res["global_changes"], ["head"])
        code, _ = self.run_check(after, "--allow", "s1", "--allow-global")
        self.assertEqual(code, 0)
        code, _ = self.run_check(after, "--allow", "s1,global")
        self.assertEqual(code, 0)

    def test_global_style_outside_regions_fails_unless_global_allowed(self):
        before = PAGE.replace("<main>", "<style>a{color:red}</style><main>")
        after = before.replace("red", "blue")
        code, res = self.run_check(after, "--allow", "s1", before_html=before)
        self.assertEqual(code, 1)
        self.assertEqual(res["global_changes"], ["style"])
        code, _ = self.run_check(after, "--allow", "s1", "--allow-global", before_html=before)
        self.assertEqual(code, 0)

    def test_exact_match_vs_loose(self):
        after = PAGE.replace("From 10 euros.", "From 12 euros.")
        code, _ = self.run_check(after, "--allow", "pri")
        self.assertEqual(code, 1)
        code, _ = self.run_check(after, "--allow", "pri", "--loose")
        self.assertEqual(code, 0)
        code, _ = self.run_check(after, "--allow", "pricing")
        self.assertEqual(code, 0)

    def test_loose_flag_does_not_leak_between_runs(self):
        after = PAGE.replace("From 10 euros.", "From 12 euros.")
        self.run_check(after, "--allow", "pri", "--loose")
        code, _ = self.run_check(after, "--allow", "pri")
        self.assertEqual(code, 1)

    def test_class_token_match(self):
        after = PAGE.replace("Fresh fish daily.", "Fresh crab daily.")
        for token in ("hero", "wide"):
            code, _ = self.run_check(after, "--allow", token)
            self.assertEqual(code, 0, token)
        code, _ = self.run_check(after, "--allow", "her")
        self.assertEqual(code, 1)

    def test_heading_and_tag_match(self):
        after = PAGE.replace("Contact us", "Call us")
        code, _ = self.run_check(after, "--allow", "footer")
        self.assertEqual(code, 0)
        code, _ = self.run_check(PAGE.replace("Fresh fish daily.", "x"), "--allow", "welcome")
        self.assertEqual(code, 0)

    def test_removed_region_flagged(self):
        start = PAGE.index('<section id="pricing">')
        end = PAGE.index("</section>", start) + len("</section>")
        after = PAGE[:start] + PAGE[end:]
        code, res = self.run_check(after, "--allow", "s1")
        self.assertEqual(code, 1)
        self.assertIn(("pricing", "removed"), [(f["region"], f["change"]) for f in res["findings"]])
        code, _ = self.run_check(after, "--allow", "pricing")
        self.assertEqual(code, 0)

    def test_added_region_flagged(self):
        after = PAGE.replace("</main>", '<section id="faq"><h2>FAQ</h2></section></main>')
        code, res = self.run_check(after, "--allow", "s1")
        self.assertEqual(code, 1)
        self.assertIn(("faq", "added"), [(f["region"], f["change"]) for f in res["findings"]])

    def test_unsectioned_body_content_is_not_ignored(self):
        before = PAGE.replace("</main>", "</main><p>Loose text</p>")
        code, res = self.run_check(before.replace("Loose text", "Other"), "--allow", "s1", before_html=before)
        self.assertEqual(code, 1)
        self.assertEqual(res["out_of_scope"][0]["region"], "(unsectioned)")

    def test_missing_file_exit_2(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = scope_check.main([str(self.dir / "a.html"), str(self.dir / "b.html")])
        self.assertEqual(code, 2)
        self.assertIn("existing HTML files", err.getvalue())

    def test_text_report_mentions_verdict(self):
        b, a = self.dir / "b.html", self.dir / "a.html"
        b.write_text(PAGE, encoding="utf-8")
        a.write_text(PAGE.replace("10", "11"), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = scope_check.main([str(b), str(a), "--allow", "s1"])
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out.getvalue())


if __name__ == "__main__":
    unittest.main()
