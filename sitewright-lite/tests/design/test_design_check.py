"""Regression tests for scripts/sw_design_check.py (item 10).

Run from the dev root: python3 -m unittest discover tests/design
The fixtures in tests/fixtures/design/ are original. Negative cases either use the deliberately broken
`fail/` set or copy `pass/` (or `theme/`) into a temporary directory with a space in its path and apply
one mutation.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts" / "sw_design_check.py"
RECORDS = ROOT / "scripts" / "sw_records.py"
FIXTURES = ROOT / "tests" / "fixtures" / "design"
PASS, FAIL, THEME = FIXTURES / "pass", FIXTURES / "fail", FIXTURES / "theme"


def run(*args, script=CHECK):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, timeout=60)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


def site(base, *extra):
    return run("--site", base / "site", "--records", base / "records", "--root", base, *extra)


def theme(base, *extra):
    return run("--theme", base / "saltmarsh", "--records", base / "records", "--root", base, *extra)


def results(report, value):
    return {c["check_id"] for c in report["checks"] if c["result"] == value}


def findings(report, check_id, severity="defect"):
    return [f["evidence"] for f in report["findings"] if f["check_id"] == check_id and f["severity"] == severity]


class Scratch:
    """A copy of one fixture under a temporary path containing a space."""

    def __init__(self, source):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw design ")
        self.base = Path(self.tmp.name, "café project")
        shutil.copytree(source, self.base)

    def edit(self, rel, old, new):
        path = self.base / rel
        text = path.read_text()
        assert old in text, (rel, old)
        path.write_text(text.replace(old, new, 1))

    def close(self):
        self.tmp.cleanup()


class ScratchCase(unittest.TestCase):
    source = PASS

    def setUp(self):
        self.copy = Scratch(self.source)
        self.base = self.copy.base

    def tearDown(self):
        self.copy.close()


class PassFixtureTest(unittest.TestCase):
    def test_agreeing_records_and_build_pass(self):
        code, report, err = site(PASS)
        self.assertEqual((code, report["result"]), (0, "passed"), (err, report))
        self.assertEqual(results(report, "failed"), set())
        self.assertEqual(report["tokens"], {"recorded": 13, "found": 13, "values_compared": 10})
        self.assertEqual(report["contrast_pairs"]["unresolved"], 0)
        self.assertGreaterEqual(report["contrast_pairs"]["checked"], 6)
        self.assertEqual(results(report, "skipped"), {"assets.final"})     # release-only check

    def test_release_mode_passes_when_assets_are_final(self):
        code, report, _ = site(PASS, "--release")
        self.assertEqual((code, report["result"]), (0, "passed"), report)
        self.assertIn("assets.final", results(report, "passed"))


class FailFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.report, cls.err = site(FAIL)

    def test_overall_failure(self):
        self.assertEqual((self.code, self.report["result"]), (1, "failed"), self.err)
        self.assertEqual(results(self.report, "failed"),
                         {"design.token-drift", "style.contrast", "style.leading", "style.tracking",
                          "assets.rights", "assets.local-path"})

    def test_token_drift(self):
        drift = findings(self.report, "design.token-drift")
        self.assertTrue(any("--color-brand" in d and "never defines" in d for d in drift), drift)
        self.assertTrue(any("'#222222'" in d and "'#333333'" in d for d in drift), drift)
        self.assertEqual(self.report["tokens"]["found"], 4)

    def test_contrast_in_both_schemes(self):
        contrast = findings(self.report, "style.contrast")
        self.assertTrue(any(d.startswith(".notice") and "2.99:1" in d and "scheme" not in d for d in contrast))
        self.assertTrue(any(d.startswith(".btn") for d in contrast))
        self.assertTrue(any(d.startswith("body") and "prefers-color-scheme: dark" in d for d in contrast))
        inferred = findings(self.report, "style.contrast", "warning")
        self.assertTrue(any(d.startswith(".caption") and "static inference" in d for d in inferred))

    def test_type_rules(self):
        self.assertTrue(any("line height 1.10" in d for d in findings(self.report, "style.leading")))
        self.assertTrue(any("0.150em" in d for d in findings(self.report, "style.tracking")))
        self.assertTrue(findings(self.report, "style.justify", "warning"))
        self.assertTrue(any(d.startswith(".btn") for d in findings(self.report, "style.padding", "warning")))
        self.assertTrue(any("#ffffff" in d for d in findings(self.report, "design.raw-literals", "warning")))

    def test_asset_rights_and_paths(self):
        rights = findings(self.report, "assets.rights")
        self.assertTrue(any("photo-hero" in d and "unknown permitted use" in d for d in rights), rights)
        self.assertTrue(any("team-photo" in d and "attribution" in d for d in rights), rights)
        paths = " | ".join(findings(self.report, "assets.local-path"))
        for needle in ("remote address", "is absolute", "outside the project", "does not exist"):
            self.assertIn(needle, paths)
        unrecorded = findings(self.report, "assets.rights", "warning")
        self.assertTrue(any("unrecorded.svg" in d for d in unrecorded))
        self.assertTrue(any("cdn.example.net" in d for d in unrecorded))

    def test_release_turns_warnings_into_defects(self):
        code, report, _ = site(FAIL, "--release", "--checks", "assets.final,assets.rights")
        self.assertEqual((code, report["result"]), (1, "failed"))
        final = findings(report, "assets.final")
        self.assertTrue(any("gallery-1 is still placeholder" in d for d in final), final)
        self.assertTrue(any("shared-drive is still needed" in d for d in final), final)
        self.assertTrue(any("unrecorded.svg" in d for d in findings(report, "assets.rights")))


class SiteMutationTest(ScratchCase):
    def test_accent_drift_also_breaks_button_contrast(self):
        self.copy.edit("site/assets/style.css", "--color-accent: #0f5c6e;", "--color-accent: #5fb0c0;")
        code, report, _ = site(self.base)
        self.assertEqual(code, 1)
        self.assertEqual(results(report, "failed"), {"design.token-drift", "style.contrast"})
        self.assertTrue(any(d.startswith(".button") for d in findings(report, "style.contrast")))

    def test_dark_scheme_only_contrast_failure(self):
        self.copy.edit("site/assets/style.css", "--color-ink: #e8eef0;", "--color-ink: #3a454b;")
        code, report, _ = site(self.base, "--checks", "style.contrast")
        self.assertEqual(code, 1)
        self.assertTrue(all("prefers-color-scheme: dark" in d for d in findings(report, "style.contrast")))

    def test_tight_body_leading(self):
        self.copy.edit("site/assets/style.css", "font: 1rem/1.6 var(--font-body);", "font: 1rem/1.1 var(--font-body);")
        code, report, _ = site(self.base, "--checks", "style.leading")
        self.assertEqual((code, results(report, "failed")), (1, {"style.leading"}))

    def test_approved_asset_with_unknown_rights(self):
        self.copy.edit("records/website.md", "- permitted_use: CC BY 4.0", "- permitted_use: unknown (OPEN-4)")
        code, report, _ = site(self.base, "--checks", "assets.rights")
        self.assertEqual(code, 1)
        self.assertTrue(any("marsh-drawing" in d for d in findings(report, "assets.rights")))

    def test_unknown_rights_on_unapproved_asset_warns_until_release(self):
        self.copy.edit("records/website.md", "- permitted_use: CC BY 4.0", "- permitted_use: unknown (OPEN-4)")
        self.copy.edit("records/website.md", "- alt_text: Reeds along the edge of a salt marsh\n- status: approved",
                       "- alt_text: Reeds along the edge of a salt marsh\n- status: supplied")
        code, report, _ = site(self.base, "--checks", "assets.rights")
        self.assertEqual(code, 0, report)
        self.assertTrue(any("marsh-drawing" in d for d in findings(report, "assets.rights", "warning")))
        code, report, _ = site(self.base, "--checks", "assets.rights", "--release")
        self.assertEqual(code, 1)

    def test_text_led_site_skips_asset_checks(self):
        records = self.base / "records" / "website.md"
        text = records.read_text()
        records.write_text(text[:text.index("### Asset: hero-ferry")] + "- assets: none (text-only)\n")
        for img in (self.base / "site" / "assets").glob("*.svg"):
            img.unlink()
        page = self.base / "site" / "index.html"
        page.write_text("\n".join(l for l in page.read_text().splitlines() if "<img" not in l and "figcaption" not in l))
        code, report, _ = site(self.base, "--checks", "assets.rights,assets.local-path")
        self.assertEqual((code, report["result"]), (0, "skipped"), report)


class MissingInputTest(ScratchCase):
    def test_missing_design_record_is_unavailable(self):
        (self.base / "records" / "website.md").unlink()
        code, report, _ = site(self.base)
        self.assertEqual((code, report["result"]), (2, "unavailable"), report)

    def test_missing_assets_record_is_unavailable(self):
        records = self.base / "records" / "website.md"
        text = records.read_text()
        records.write_text(text[:text.index("# Assets")])
        code, report, _ = site(self.base, "--checks", "assets.rights")
        self.assertEqual((code, report["result"]), (2, "unavailable"), report)
        code, report, _ = site(self.base, "--checks", "design.token-drift")   # independent checks still run
        self.assertEqual((code, report["result"]), (0, "passed"), report)

    def test_empty_semantic_tokens_fail(self):
        self.copy.edit("records/website.md", "- semantic_tokens: --color-ground", "- semantic_tokens: \n- old_tokens: --color-ground")
        code, report, _ = site(self.base, "--checks", "design.token-drift")
        self.assertEqual(code, 1, report)

    def test_site_without_stylesheets(self):
        shutil.rmtree(self.base / "site" / "assets")
        code, report, _ = site(self.base, "--checks", "style.contrast,style.leading")
        self.assertNotEqual(report["result"], "passed", report)
        self.assertIn(report["result"], ("skipped", "unavailable", "error"))


class ThemeTest(ScratchCase):
    source = THEME

    def test_presets_carry_the_recorded_tokens(self):
        code, report, err = theme(THEME)
        self.assertEqual((code, report["result"]), (0, "passed"), (err, report))
        self.assertEqual(report["tokens"]["recorded"], report["tokens"]["found"])
        alias = findings(report, "design.token-drift", "warning")
        self.assertEqual(len(alias), 1)
        self.assertIn("--wp--custom--radius", alias[0])

    def test_palette_drift(self):
        self.copy.edit("saltmarsh/theme.json", '"color": "#0f5c6e"', '"color": "#3d8ea0"')
        code, report, _ = theme(self.base)
        self.assertEqual(code, 1)
        self.assertTrue(any("--color-teal" in d for d in findings(report, "design.token-drift")))

    def test_missing_preset(self):
        self.copy.edit("saltmarsh/theme.json", '"custom": { "radius": "3px" },', "")
        code, report, _ = theme(self.base, "--checks", "design.token-drift")
        self.assertEqual(code, 1)
        self.assertTrue(any("--radius-1" in d for d in findings(report, "design.token-drift")))

    def test_style_contrast_from_theme_json(self):
        self.copy.edit("saltmarsh/theme.json", '"slug": "on-teal", "name": "On teal", "color": "#ffffff"',
                       '"slug": "on-teal", "name": "On teal", "color": "#5a8f9a"')
        self.copy.edit("records/website.md", "--color-on-teal: #ffffff",
                       "--color-on-teal: #5a8f9a")
        code, report, _ = theme(self.base, "--checks", "style.contrast")
        self.assertEqual(code, 1, report)

    def test_malformed_theme_json_is_an_error(self):
        (self.base / "saltmarsh" / "theme.json").write_text('{"version": 3, "settings": ')
        code, report, _ = theme(self.base)
        self.assertEqual((code, report["result"]), (2, "error"))
        self.assertTrue(report["diagnostics"])

    def test_missing_theme_json_is_an_error(self):
        (self.base / "saltmarsh" / "theme.json").unlink()
        code, report, _ = theme(self.base)
        self.assertEqual((code, report["result"]), (2, "error"))


class ErrorTest(ScratchCase):
    def assert_error(self, *args):
        code, report, _ = run(*args)
        self.assertEqual((code, report["result"]), (2, "error"), args)
        self.assertTrue(report["diagnostics"], args)

    def test_bad_arguments(self):
        self.assert_error("--bogus")
        self.assert_error()
        self.assert_error("--site", PASS / "site", "--theme", THEME / "saltmarsh", "--records", PASS / "records")
        self.assert_error("--site", PASS / "site", "--records", PASS / "records", "--checks", "style.kerning")
        self.assert_error("--site", PASS / "site", "--records", PASS / "records", "--record", "v.json")

    def test_oversized_stylesheet(self):
        (self.base / "site" / "assets" / "huge.css").write_text("/*" + "x" * 5_100_000 + "*/")
        code, report, _ = site(self.base)
        self.assertEqual((code, report["result"]), (2, "error"))

    def test_undecodable_stylesheet(self):
        (self.base / "site" / "assets" / "bad.css").write_bytes(b"body { color: \xff\xfe; }")
        code, report, _ = site(self.base)
        self.assertEqual((code, report["result"]), (2, "error"))


class RecordTest(ScratchCase):
    def test_records_every_check_and_gate_tracks_staleness(self):
        verification = self.base / "docs" / "website" / "verification.json"
        evidence = self.base / "docs" / "website" / "evidence" / "design-check.json"
        code, report, err = site(self.base, "--record", verification, "--evidence-out", evidence, "--require")
        self.assertEqual(code, 0, (err, report))
        self.assertEqual(json.loads(evidence.read_text())["result"], "passed")
        records = json.loads(verification.read_text())["records"]
        self.assertEqual(len(records), len(report["checks"]))
        self.assertTrue(all(r["method"] == "automated" and r["tool_and_version"] == "sw_design_check 4"
                            for r in records))
        skipped = [r for r in records if r["result"] == "skipped"]
        self.assertTrue(skipped and all(r.get("skip_reason_when_applicable") for r in skipped))
        self.assertTrue(all(r["required_or_optional"] == "optional" for r in skipped))
        self.assertIn("--release", skipped[0]["skip_reason_when_applicable"])
        # without --release the asset checks judge mock-up criteria; the rest judge the same in both modes
        modes = {r["check_id"]: r.get("mode") for r in records}
        self.assertEqual({c for c, m in modes.items() if m}, {"assets.rights", "assets.local-path", "assets.final"})
        self.assertEqual({m for m in modes.values() if m}, {"mockup"})
        gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
        self.assertEqual((gcode, gate["result"]), (0, "passed"), gate)
        gcode, gate, _ = run("gate", verification, "--root", self.base, script=RECORDS)
        self.assertEqual((gcode, gate["result"]), (1, "unavailable"), gate)
        self.assertEqual({c["check_id"] for c in gate["checks"] if c["result"] == "unavailable"},
                         {"assets.rights", "assets.local-path"})
        self.copy.edit("site/assets/style.css", "letter-spacing: 0.08em;", "letter-spacing: 0.06em;")
        gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
        self.assertEqual((gcode, gate["result"]), (1, "stale"), gate)

    def test_records_bind_the_other_files_each_check_read(self):
        """Token drift targets the design record but reads the build; raw literals target a sheet but read
        the design record's token names. A change to either dependency makes that record stale."""
        verification = self.base / "docs" / "website" / "verification.json"
        evidence = self.base / "docs" / "website" / "evidence" / "design-check.json"
        code, report, err = site(self.base, "--record", verification, "--evidence-out", evidence, "--require")
        self.assertEqual(code, 0, (err, report))

        records = {r["check_id"]: r for r in json.loads(verification.read_text())["records"]}
        self.assertEqual(records["design.token-drift"]["target"], "records/website.md")
        self.assertEqual(set(records["design.token-drift"]["inputs"]), {"site"})
        # stylesheet checks target the build's CSS set and read the token names, never the whole build
        self.assertEqual(records["design.raw-literals"]["target"], "site/**/*.css")
        self.assertEqual(set(records["design.raw-literals"]["inputs"]), {"records/website.md"})
        self.assertNotIn("docs/website/evidence/design-check.json",
                         {k for r in records.values() for k in r["inputs"]})

        def stale_checks():
            gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
            self.assertEqual(gate["result"], "stale", gate)
            return {c["check_id"] for c in gate["checks"] if c["result"] == "stale"}

        self.copy.edit("site/assets/ferry.svg", "<svg", "<svg data-edited=\"1\"")
        self.assertIn("design.token-drift", stale_checks())
        self.copy.edit("site/assets/ferry.svg", "<svg data-edited=\"1\"", "<svg")
        gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
        self.assertEqual(gate["result"], "passed", gate)
        with open(self.base / "records" / "website.md", "a") as fh:
            fh.write("\n")
        self.assertIn("design.raw-literals", stale_checks())

    def test_hashed_rebuild_keeps_the_stylesheet_pairs_current(self):
        """A framework build that renames a stylesheet (style.css -> style.4f1c2a.css) without changing it
        leaves every stylesheet check current under the same pair; changed CSS makes them stale."""
        verification = self.base / "docs" / "website" / "verification.json"
        evidence = self.base / "docs" / "website" / "evidence" / "design-check.json"
        code, report, err = site(self.base, "--record", verification, "--evidence-out", evidence, "--require")
        self.assertEqual(code, 0, (err, report))
        pairs = {(r["check_id"], r["target"]) for r in json.loads(verification.read_text())["records"]}
        self.assertFalse(any(t.endswith("style.css") for _, t in pairs))
        sheet = self.base / "site" / "assets" / "style.css"
        renamed = sheet.with_name("style.4f1c2a.css")
        sheet.rename(renamed)
        index = self.base / "site" / "index.html"
        index.write_text(index.read_text().replace("style.css", "style.4f1c2a.css"))
        gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
        css = {c["check_id"]: c["result"] for c in gate["checks"] if c["target"] == "site/**/*.css"}
        self.assertTrue(css and set(css.values()) == {"passed"}, gate)
        self.assertFalse(any("missing" in str(c.get("reason", "")) for c in gate["checks"]), gate)
        renamed.write_text(renamed.read_text().replace("--color-accent: #0f5c6e;", "--color-accent: #0e5b6d;"))
        gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
        css = {c["check_id"]: c["result"] for c in gate["checks"] if c["target"] == "site/**/*.css"}
        self.assertEqual(set(css.values()), {"stale"}, gate)

    def test_a_missing_design_record_is_filed_against_the_record_file_not_the_folder(self):
        """Recording `unavailable` against docs/website itself would make that folder a target containing
        verification.json, which blocks `compact` and later records."""
        md = self.base / "records" / "website.md"
        text = md.read_text()
        start = text.index("# Design")
        end = text.find("\n# ", start + 1)
        md.write_text(text[:start] + (text[end + 1:] if end != -1 else ""))
        verification = self.base / "records" / "verification.json"
        evidence = self.base / "records" / "evidence" / "design-check.json"
        code, report, err = site(self.base, "--record", verification, "--evidence-out", evidence,
                                 "--checks", "design.token-drift")
        self.assertEqual((code, report["result"]), (2, "unavailable"), err)
        records = json.loads(verification.read_text())["records"]
        self.assertEqual([(r["check_id"], r["target"], r["result"]) for r in records],
                         [("design.token-drift", "records/website.md", "unavailable")])

    def test_failed_run_is_recorded_as_failed(self):
        self.copy.edit("site/assets/style.css", "--color-accent: #0f5c6e;", "--color-accent: #5fb0c0;")
        verification = self.base / "docs" / "website" / "verification.json"
        evidence = self.base / "docs" / "website" / "evidence" / "design-check.json"
        code, report, _ = site(self.base, "--record", verification, "--evidence-out", evidence, "--require")
        self.assertEqual(code, 1)
        failed = {r["check_id"] for r in json.loads(verification.read_text())["records"] if r["result"] == "failed"}
        self.assertEqual(failed, {"design.token-drift", "style.contrast"})
        gcode, gate, _ = run("gate", verification, "--root", self.base, script=RECORDS)
        self.assertEqual((gcode, gate["result"]), (1, "failed"), gate)



class RawScaleLiteralTest(ScratchCase):
    """0.3.0 (D6): spacing lengths and durations written as literals are summarised per stylesheet and kind."""

    def test_spacing_and_duration_literals_warn_once_per_sheet_and_kind(self):
        css = self.base / "site" / "assets" / "style.css"
        css.write_text(css.read_text() + "\n.card { margin: 1rem 0 24px; padding: 1px 0.5rem; gap: var(--space-2, 8px); }"
                       "\n.note { inset: -12px; border: 1px solid; transition: opacity 300ms ease 0s; }"
                       "\n.fade { animation-duration: .12s; }\n")
        code, report, err = site(self.base)
        self.assertIsNotNone(report, err)
        rows = [f for f in report["findings"] if f["check_id"] == "design.raw-literals"]
        kinds = {f["kind"]: f for f in rows if "kind" in f}
        self.assertEqual(set(kinds), {"spacing", "duration"}, rows)
        self.assertEqual(kinds["spacing"]["count"], 4, kinds["spacing"])    # 1rem, 24px, 0.5rem, -12px; not 1px, 0, 8px fallback
        self.assertIn("= var(--space-3)", kinds["spacing"]["evidence"])     # 1rem equals --space-3
        self.assertEqual(kinds["duration"]["count"], 2, kinds["duration"])  # 300ms, .12s; not 0s
        self.assertIn("= var(--duration-short)", kinds["duration"]["evidence"])
        self.assertTrue(all(f["severity"] == "warning" for f in rows))

if __name__ == "__main__":
    unittest.main()
