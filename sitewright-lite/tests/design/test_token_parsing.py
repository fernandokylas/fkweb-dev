"""T18 (Lite 0.4.1, ported from Full 0.5.4): parse_tokens keeps the first value of a repeated name, reads a value given on a nested
bullet, and stops a value at the next bullet or label. The fixtures are the real design record of the
case-study site from the 0.5.3 Mac mini test (a fictional sample), before and after its workaround.

Run from the dev root: python3 -m unittest discover tests/design
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_design_check as dc  # noqa: E402
import sw_records  # noqa: E402

CASE = Path(__file__).resolve().parent / "fixtures_case_study"


def design_of(name):
    return sw_records.parse_records([("design.md", (CASE / name / "design.md").read_text())])["design"]


def parse(spec):
    dup = []
    return dc.parse_tokens(spec, dup), dup


class RepeatedNameTest(unittest.TestCase):
    def test_first_value_kept_and_duplicate_reported(self):
        tokens, dup = parse("- `--bg-main: #fff`; `--ink: #111` - `--bg-main: #000`")
        self.assertEqual(tokens["--bg-main"], "#fff")
        self.assertEqual([(n, a, b) for n, a, b in dup], [("--bg-main", "#fff", "#000")])

    def test_same_value_twice_is_not_a_duplicate(self):
        tokens, dup = parse("`--bg-main: #fff`; `--bg-main: #fff`")
        self.assertEqual((tokens["--bg-main"], dup), ("#fff", []))

    def test_a_bare_mention_does_not_replace_or_report(self):
        tokens, dup = parse("`--bg-main: #fff`; text on `--bg-main`")
        self.assertEqual((tokens["--bg-main"], dup), ("#fff", []))
        tokens, dup = parse("`--bg-main` named first; later `--bg-main: #fff`")
        self.assertEqual((tokens["--bg-main"], dup), ("#fff", []))


class NestedAndBoundaryTest(unittest.TestCase):
    def test_value_on_a_nested_bullet(self):
        # sw_records flattens nested bullets with " - "
        tokens, _ = parse("- `--bg-main` - #fff - `--ink`: - #111 - `--gap` - clamp(1rem, 2vw, 3rem)")
        self.assertEqual(tokens["--bg-main"], "#fff")
        self.assertEqual(tokens["--ink"], "#111")
        self.assertEqual(tokens["--gap"], "clamp(1rem, 2vw, 3rem)")

    def test_a_following_label_is_not_a_value(self):
        tokens, _ = parse("- `--bg-main` - notes: see palette - `--ink`: #111")
        self.assertIsNone(tokens["--bg-main"])
        self.assertEqual(tokens["--ink"], "#111")

    def test_value_stops_at_the_next_bullet_label(self):
        tokens, _ = parse("- --gap-section: clamp(4rem, 9vw, 8rem) - rules: `--rule-hair: 1px`")
        self.assertEqual(tokens["--gap-section"], "clamp(4rem, 9vw, 8rem)")
        tokens, _ = parse("- `--gap-section: clamp(4rem, 9vw, 8rem)` - rules: `--rule-hair: 1px`")
        self.assertEqual(tokens["--gap-section"], "clamp(4rem, 9vw, 8rem)")

    def test_value_stops_at_the_closing_backtick_and_semicolon(self):
        tokens, _ = parse("`--u: 0.5rem` (the panel module); steps `--s1: calc(var(--u) * 1)`; `--s2: 1rem`")
        self.assertEqual(tokens["--u"], "0.5rem")
        self.assertEqual(tokens["--s1"], "calc(var(--u) * 1)")
        self.assertEqual(tokens["--s2"], "1rem")

    def test_plain_values_keep_working(self):
        tokens, _ = parse("--a: #123456 (7:1), --b: 1px; --space-1..3")
        self.assertEqual((tokens["--a"], tokens["--b"]), ("#123456", "1px"))
        self.assertEqual({"--space-1", "--space-2", "--space-3"} - set(tokens), set())


class FieldLineLeadInTest(unittest.TestCase):
    def test_nested_token_bullets_after_a_lead_in_are_read(self):
        """Lite 0.4.1 (T18b): `- semantic_tokens: <lead-in>` followed by nested bullets keeps the bullets."""
        md = "# Design\n\n- semantic_tokens: paper ground\n    - `--bg-main: #f2f3f1`\n    - `--ink: #111`\n"
        spec = sw_records.parse_records([("design.md", md)])["design"]["semantic_tokens"]
        tokens, dup = parse(spec)
        self.assertEqual((tokens.get("--bg-main"), tokens.get("--ink"), dup), ("#f2f3f1", "#111", []))


class CaseStudyRecordTest(unittest.TestCase):
    """The real record, before the workaround (obsidian set under the same names) and after it."""

    def test_before_first_value_is_the_paper_ground(self):
        design = design_of("before")
        tokens, dup = parse(design["semantic_tokens"])
        self.assertEqual(tokens["--bg-main"], "#f2f3f1")           # paper, not obsidian #111a24
        self.assertEqual(tokens["--accent-text"], "#8f2614")
        self.assertEqual(tokens["--gap-section"], "clamp(4rem, 9vw, 8rem)")
        self.assertEqual(tokens["--u"], "0.5rem")
        self.assertEqual(tokens["--radius"], "0")
        names = {n for n, _, _ in dup}
        self.assertLessEqual({"--bg-main", "--text-main", "--accent-text", "--focus"}, names)
        self.assertIn(("--bg-main", "#f2f3f1", "#111a24"), dup)
        for name, value in tokens.items():
            self.assertTrue(value is None or "`" not in value, (name, value))

    def test_after_has_no_duplicates(self):
        design = design_of("after")
        tokens, dup = parse(design["semantic_tokens"])
        self.assertEqual(dup, [])
        self.assertEqual((tokens["--bg-main"], tokens["--gap-section"]), ("#f2f3f1", "clamp(4rem, 9vw, 8rem)"))
        self.assertIn("ground_inverted_tokens", design)

    def test_check_warns_on_the_before_record_and_is_quiet_after(self):
        for which, expect_warning in (("before", True), ("after", False)):
            with self.subTest(which):
                design = design_of(which)
                tokens, _ = parse(design["semantic_tokens"])
                with tempfile.TemporaryDirectory(prefix="sw tokens ") as tmp:
                    base = Path(tmp)
                    (base / "records").mkdir()
                    (base / "site").mkdir()
                    (base / "records" / "design.md").write_text((CASE / which / "design.md").read_text())
                    decls = "".join(f"  {n}: {v};\n" for n, v in tokens.items() if v is not None)
                    decls += "".join(f"  {n}: 0;\n" for n, v in tokens.items() if v is None)
                    (base / "site" / "style.css").write_text(f":root {{\n{decls}}}\nbody {{ margin: 0; }}\n")
                    (base / "site" / "index.html").write_text(
                        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>t</title>'
                        '<link rel="stylesheet" href="style.css"></head><body><p>x</p></body></html>')
                    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "sw_design_check.py"),
                                           "--site", str(base / "site"), "--records", str(base / "records"),
                                           "--root", str(base), "--checks", "design.token-drift"],
                                          capture_output=True, text=True, timeout=60)
                    report = json.loads(proc.stdout)
                drift = [f for f in report["findings"] if f["check_id"] == "design.token-drift"]
                defects = [f["evidence"] for f in drift if f["severity"] == "defect"]
                warns = [f["evidence"] for f in drift if f["severity"] == "warning" and "more than once" in f["evidence"]]
                self.assertEqual(defects, [], (proc.stderr, defects))
                if expect_warning:
                    self.assertTrue(any("--bg-main" in w and "#f2f3f1" in w and "#111a24" in w for w in warns), warns)
                    self.assertTrue(any("ground_inverted_tokens" in f["action"] for f in drift))
                else:
                    self.assertEqual(warns, [])


if __name__ == "__main__":
    unittest.main()
