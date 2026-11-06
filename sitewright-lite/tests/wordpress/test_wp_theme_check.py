"""Regression tests for scripts/sw_wp_theme_check.py: the fixture theme passes and each mutation fails its check."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_records  # noqa: E402
CHECK = ROOT / "scripts" / "sw_wp_theme_check.py"
RECORDS = ROOT / "scripts" / "sw_records.py"
BASE = ROOT / "tests" / "fixtures" / "wordpress" / "harbour-lane-block-theme"
TOKENS = ROOT / "tests" / "fixtures" / "sites" / "harbour-lane-static" / "site" / "assets" / "site.css"
RUNTIME = ("wp.runtime-theme", "wp.runtime-templates", "wp.runtime-content")
PROBE = {
    "probe": "sitewright-wp-probe 2", "php_version": "8.5.10", "wp_version": "7.1.2",
    "theme": {"stylesheet": "harbour-lane", "template": "harbour-lane", "name": "Harbour Lane", "version": "0.1.0",
              "is_block_theme": True, "errors": []},
    "templates": [{"slug": s, "source": "theme", "has_theme_file": True} for s in ("404", "index", "page-no-title", "page")],
    "parts": [{"slug": "footer", "area": "footer", "source": "theme"}, {"slug": "header", "area": "header", "source": "theme"}],
    "patterns": [{"slug": "harbour-lane/not-found", "title": "Page not found"}],
    "pages": [{"slug": s, "path": f"/{s}/", "template": t, "has_blocks": True, "block_counts": {"core/paragraph": 2},
               "freeform": [], "unregistered": []}
              for s, t in (("home", "page-no-title"), ("menu", ""), ("order", ""), ("contact", ""))],
}


def run(*args, script=CHECK):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, timeout=60)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


def failed(report):
    return {(c["check_id"], c["target"]) for c in report["checks"] if c["result"] == "failed"}


class Copy:
    """A copy of the fixture in a temp dir whose path contains spaces."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw wp ")
        self.root = Path(self.tmp.name, "my project")
        shutil.copytree(BASE, self.root, ignore=lambda d, names: {"docs", "capture"} if Path(d) == BASE else set())
        self.theme = self.root / "theme" / "harbour-lane"
        self.content = self.root / "content"
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def edit(self, rel, old, new, base=None):
        path = (base or self.theme) / rel
        text = path.read_text()
        assert old in text, (rel, old)
        path.write_text(text.replace(old, new, 1))

    def snapshot(self, data):
        """What probe v2 reports about this copy: theme file hashes and each page's stored content hash."""
        files = {p.relative_to(self.theme).as_posix(): sw_records.fingerprint(p)
                 for p in sorted(self.theme.rglob("*")) if p.is_file()}
        data["theme"] = {**data["theme"], "files": files, "files_truncated": False}
        index = {p["slug"]: p["file"] for p in json.loads((self.content / "pages.json").read_text())["pages"]}
        data["pages"] = [dict(p, content_sha256=sw_records.fingerprint(self.content / index[p["slug"]]))
                         for p in data["pages"]]

    def probe(self, mutate=None, raw=False):
        """Write a probe of this copy as it is now (raw: without the v2 snapshot); `mutate` edits it afterwards."""
        data = json.loads(json.dumps(PROBE))
        if not raw:
            self.snapshot(data)
        if mutate:
            mutate(data)
        path = self.root / "probe.json"
        path.write_text(json.dumps(data))
        return path


class FixtureTest(unittest.TestCase):
    def test_fixture_passes_with_only_warnings(self):
        code, report, err = run(BASE / "theme" / "harbour-lane", "--content", BASE / "content", "--tokens", TOKENS)
        self.assertEqual(code, 0, (err, report))
        self.assertEqual(report["result"], "passed")
        self.assertTrue(all(f["severity"] == "warning" for f in report["findings"]))
        html = [f for f in report["findings"] if f["check_id"] == "wp.content-editable"]
        self.assertEqual([f["location"] for f in html], ["content/order.html:5"])
        ids = {c["check_id"] for c in report["checks"]}
        self.assertEqual(ids, {"wp.theme-header", "wp.theme-json", "wp.tokens", "wp.block-markup", "wp.template-structure",
                               "wp.patterns", "wp.content-editable", "wp.assets", "wp.php-safety"})

    def test_matching_probe_passes_runtime_checks(self):
        with Copy() as c:
            code, report, err = run(c.theme, "--content", c.content, "--probe", c.probe())
            self.assertEqual(code, 0, (err, report))
            self.assertTrue({"wp.runtime-theme", "wp.runtime-templates", "wp.runtime-content"}
                            <= {x["check_id"] for x in report["checks"]})
            self.assertEqual(report["wp_version"], "7.1.2")


class MutationTest(unittest.TestCase):
    def assertFails(self, mutate, expected, *extra):
        with Copy() as c:
            mutate(c)
            code, report, err = run(c.theme, "--content", c.content, *[a(c) if callable(a) else a for a in extra])
            self.assertEqual(code, 1, (err, report))
            self.assertIn(expected, failed(report), report["findings"])

    def test_unclosed_block(self):
        self.assertFails(lambda c: c.edit("parts/footer.html", "<!-- /wp:group -->", ""),
                         ("wp.block-markup", "parts/footer.html"))

    def test_attributes_not_json(self):
        self.assertFails(lambda c: c.edit("parts/footer.html", '{"textColor":"muted",', '{textColor:"muted",'),
                         ("wp.block-markup", "parts/footer.html"))

    def test_missing_template_part(self):
        self.assertFails(lambda c: (c.theme / "parts" / "footer.html").unlink(),
                         ("wp.template-structure", "templates/page.html"))

    def test_page_template_without_post_content(self):
        def mutate(c):
            path = c.theme / "templates" / "page.html"
            text = path.read_text()
            start = text.index("<!-- wp:post-content")
            end = text.index("/-->", start) + 4
            path.write_text(text[:start] + text[end:])
        self.assertFails(mutate, ("wp.template-structure", "templates/page.html"))

    def test_two_main_landmarks(self):
        self.assertFails(lambda c: c.edit("templates/page.html", "<!-- wp:post-content",
                                          '<!-- wp:group {"tagName":"main"} --><main class="wp-block-group"></main>'
                                          '<!-- /wp:group -->\n<!-- wp:post-content'),
                         ("wp.template-structure", "templates/page.html"))

    def test_undefined_preset(self):
        self.assertFails(lambda c: c.edit("parts/footer.html", '"textColor":"muted"', '"textColor":"teal"'),
                         ("wp.tokens", "parts/footer.html"))

    def test_token_value_drift(self):
        self.assertFails(lambda c: c.edit("theme.json", '"#8a3b12"', '"#8a3b13"'), ("wp.tokens", "theme.json"),
                         "--tokens", TOKENS)

    def test_pattern_outside_namespace(self):
        self.assertFails(lambda c: c.edit("patterns/not-found.php", "Slug: harbour-lane/not-found", "Slug: other/not-found"),
                         ("wp.patterns", "patterns/not-found.php"))

    def test_classic_content(self):
        self.assertFails(lambda c: (c.content / "menu.html").write_text("<p>Old classic page</p>\n"),
                         ("wp.content-editable", "content/menu.html"))

    def test_page_index_names_missing_template(self):
        self.assertFails(lambda c: c.edit("pages.json", '"page-no-title"', '"page-wide"', base=c.content),
                         ("wp.content-editable", "content/pages.json"))

    def test_missing_asset(self):
        self.assertFails(lambda c: (c.theme / "assets" / "order.js").unlink(), ("wp.assets", "functions.php"))

    def test_unsanitised_request_input(self):
        self.assertFails(lambda c: c.edit("functions.php", "<?php", "<?php\necho $_GET['q'];", ),
                         ("wp.php-safety", "functions.php"))

    def test_embedded_credential(self):
        self.assertFails(lambda c: c.edit("functions.php", "<?php", "<?php\n$api_key = 'sk-live-abcdef123';"),
                         ("wp.php-safety", "functions.php"))

    def test_eval(self):
        self.assertFails(lambda c: c.edit("functions.php", "<?php", "<?php\neval( $code );"),
                         ("wp.php-safety", "functions.php"))

    def test_broken_theme_json_is_a_failure_not_a_crash(self):
        self.assertFails(lambda c: (c.theme / "theme.json").write_text("{ not json"), ("wp.theme-json", "theme.json"))

    def test_header_field_missing(self):
        self.assertFails(lambda c: c.edit("style.css", "Text Domain:", "Text-Domain-Removed:"), ("wp.theme-header", "style.css"))

    def test_runtime_wrong_theme(self):
        self.assertFails(lambda c: None, ("wp.runtime-theme", "probe"),
                         "--probe", lambda c: c.probe(lambda d: d["theme"].update(stylesheet="twentytwentyfive")))

    def test_runtime_database_override(self):
        def custom(d):
            d["templates"] = [dict(t, source="custom") if t["slug"] == "page" else t for t in d["templates"]]
        self.assertFails(lambda c: None, ("wp.runtime-templates", "probe"), "--probe", lambda c: c.probe(custom))

    def test_runtime_classic_chunk(self):
        def chunk(d):
            d["pages"] = [dict(p, freeform=[{"line": 1}]) if p["slug"] == "menu" else p for p in d["pages"]]
        self.assertFails(lambda c: None, ("wp.runtime-content", "probe"), "--probe", lambda c: c.probe(chunk))

    def test_runtime_missing_page(self):
        self.assertFails(lambda c: None, ("wp.runtime-content", "probe"), "--probe",
                         lambda c: c.probe(lambda d: d.update(pages=d["pages"][:3])))


def by_id(report):
    return {c["check_id"]: c["result"] for c in report["checks"]}


class SnapshotBindingTest(unittest.TestCase):
    """Runtime results count only for the theme files and page content the probe actually observed."""

    def runtime(self, c, probe, *extra):
        return run(c.theme, "--content", c.content, "--probe", probe, "--checks", ",".join(RUNTIME), *extra)

    def test_version_1_probe_is_stale_never_passed(self):
        with Copy() as c:
            code, report, err = self.runtime(c, c.probe(lambda d: d.update(probe="sitewright-wp-probe 1"), raw=True))
            self.assertEqual((code, report["result"]), (2, "stale"), err)
            self.assertEqual(set(by_id(report).values()), {"stale"})
            self.assertTrue(any("does not identify the theme files" in x for x in report["diagnostics"]))

    def test_truncated_file_list_is_stale(self):
        with Copy() as c:
            code, report, _ = self.runtime(c, c.probe(lambda d: d["theme"].update(files_truncated=True)))
            self.assertEqual((code, report["result"]), (2, "stale"))

    def test_theme_edit_after_the_probe_makes_runtime_stale(self):
        with Copy() as c:
            probe = c.probe()
            code, report, _ = self.runtime(c, probe)
            self.assertEqual((code, report["result"]), (0, "passed"), report)
            c.edit("parts/footer.html", "sample hours", "sample opening hours")
            code, report, _ = self.runtime(c, probe)
            self.assertEqual((code, report["result"]), (2, "stale"))
            self.assertEqual(set(by_id(report).values()), {"stale"})
            self.assertTrue(any("parts/footer.html" in x for x in report["diagnostics"]), report["diagnostics"])

    def test_added_theme_file_makes_runtime_stale(self):
        with Copy() as c:
            probe = c.probe()
            (c.theme / "patterns" / "extra.php").write_text("<?php\n")
            code, report, _ = self.runtime(c, probe)
            self.assertEqual(report["result"], "stale")

    def test_content_edit_after_the_probe_makes_only_content_stale(self):
        with Copy() as c:
            probe = c.probe()
            c.edit("menu.html", "</p>", " Fresh today.</p>", base=c.content)
            code, report, _ = self.runtime(c, probe)
            self.assertEqual((code, report["result"]), (2, "stale"))
            self.assertEqual(by_id(report), {"wp.runtime-theme": "passed", "wp.runtime-templates": "passed",
                                             "wp.runtime-content": "stale"})

    def test_content_check_without_content_dir_is_stale(self):
        with Copy() as c:
            code, report, _ = run(c.theme, "--probe", c.probe(), "--checks", "wp.runtime-content")
            self.assertEqual((code, report["result"]), (2, "stale"))

    def test_rechecking_an_old_probe_does_not_refresh_recorded_evidence(self):
        with Copy() as c:
            verification = c.root / "docs" / "website" / "verification.json"
            evidence = c.root / "docs" / "website" / "evidence" / "wp-theme-check.json"
            probe = c.probe()
            record = ("--record", verification, "--root", c.root, "--evidence-out", evidence, "--require")
            code, report, err = self.runtime(c, probe, *record)
            self.assertEqual(code, 0, (err, report))
            records = {r["check_id"]: r for r in json.loads(verification.read_text())["records"]}
            for cid in RUNTIME:
                self.assertEqual(records[cid]["target"], "theme/harbour-lane")
                self.assertNotIn("probe.json", json.dumps(records[cid].get("inputs", {})))
            self.assertEqual(list(records["wp.runtime-content"]["inputs"]), ["content"])
            c.edit("templates/page.html", "<!-- wp:post-content", "<!-- wp:post-content ")
            gcode, gate, _ = run("gate", verification, "--root", c.root, script=RECORDS)
            self.assertEqual(gate["result"], "stale")
            # Running the checker again against the same, now old, probe must not make the records current.
            # A second run to the same evidence file is refused: the first records cite it.
            code, report, _ = self.runtime(c, probe, *record)
            self.assertEqual((code, report["result"]), (2, "error"))
            self.assertIn("already holds evidence", " ".join(report["diagnostics"]))
            again = record[:5] + (evidence.with_name("wp-theme-check-2.json"), "--require")
            code, report, _ = self.runtime(c, probe, *again)
            self.assertEqual((code, report["result"]), (2, "stale"))
            gcode, gate, _ = run("gate", verification, "--root", c.root, script=RECORDS)
            self.assertNotEqual(gate["result"], "passed", gate)
            self.assertEqual({x["result"] for x in gate["checks"]}, {"stale"})


class ErrorTest(unittest.TestCase):
    def test_errors_are_exit_2_never_pass(self):
        theme = BASE / "theme" / "harbour-lane"
        with tempfile.TemporaryDirectory(prefix="sw wp ") as d:
            not_probe = Path(d, "other.json")
            not_probe.write_text('{"hello": 1}')
            bad = Path(d, "bad.json")
            bad.write_text("{")
            cases = [
                (Path(d, "nope"),),
                (theme, "--checks", "wp.nonsense"),
                (theme, "--checks", "wp.runtime-theme"),  # runtime without --probe
                (theme, "--probe", not_probe),
                (theme, "--probe", bad),
                (theme, "--content", Path(d, "missing")),
                (theme, "--tokens", Path(d, "missing.css")),
                (theme, "--record", Path(d, "v.json")),  # --record needs --evidence-out
                (theme, "--bogus-flag"),
            ]
            for args in cases:
                code, report, err = run(*args)
                self.assertEqual(code, 2, (args, report, err))
                if report:
                    self.assertEqual(report["result"], "error", args)

    def test_check_selection(self):
        code, report, _ = run(BASE / "theme" / "harbour-lane", "--checks", "wp.patterns")
        self.assertEqual(code, 0)
        self.assertEqual({c["check_id"] for c in report["checks"]}, {"wp.patterns"})


class RecordTest(unittest.TestCase):
    def test_records_every_check_and_edits_make_them_stale(self):
        with Copy() as c:
            verification = c.root / "docs" / "website" / "verification.json"
            evidence = c.root / "docs" / "website" / "evidence" / "wp-theme-check.json"
            code, report, err = run(c.theme, "--content", c.content, "--probe", c.probe(), "--record", verification,
                                    "--root", c.root, "--evidence-out", evidence, "--require")
            self.assertEqual(code, 0, (err, report))
            records = json.loads(verification.read_text())["records"]
            self.assertEqual(len(records), len(report["checks"]))
            self.assertEqual(json.loads(evidence.read_text())["result"], "passed")
            gcode, gate, _ = run("gate", verification, "--root", c.root, script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (0, "passed"), gate)
            c.edit("parts/footer.html", "sample hours", "sample opening hours")
            gcode, gate, _ = run("gate", verification, "--root", c.root, script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (1, "stale"), gate)
            self.assertIn("theme/harbour-lane/parts/footer.html",
                          {x["target"] for x in gate["checks"] if x["result"] == "stale"})


class CommittedEvidenceTest(unittest.TestCase):
    """The committed fixture evidence must stay fresh: editing the theme or content without re-recording fails here."""

    def test_fixture_verification_gate_passes(self):
        code, gate, err = run("gate", BASE / "docs" / "website" / "verification.json", "--root", BASE, script=RECORDS)
        self.assertEqual(code, 0, (gate and [c for c in gate["checks"] if c["result"] != "passed"], err[-400:]))
        ids = {c["check_id"] for c in gate["checks"]}
        self.assertIn("browser.wp-editor-valid", ids)
        self.assertIn("wp.runtime-content", ids)

    def test_committed_runtime_and_browser_evidence_bind_the_observed_snapshot(self):
        """The probe saw the committed theme and content (probe v2), and the browser records list the
        content and blueprint as inputs, so a content edit makes both kinds stale, not just the target."""
        probe = json.loads((BASE / "docs" / "website" / "evidence" / "probe.json").read_text())
        self.assertEqual(probe["probe"], "sitewright-wp-probe 2")
        self.assertFalse(probe["theme"]["files_truncated"])
        with tempfile.TemporaryDirectory(prefix="sw wp dep ") as tmp:
            base = Path(tmp) / "fixture"
            shutil.copytree(BASE, base)
            records = json.loads((base / "docs" / "website" / "verification.json").read_text())["records"]
            browser = [r for r in records if r["check_id"].startswith("browser.")]
            self.assertTrue(browser)
            for r in browser:
                self.assertEqual((r["target"], sorted(r["inputs"])), ("theme/harbour-lane", ["blueprint.json", "content"]))
            with open(base / "content" / "menu.html", "a", encoding="utf-8") as fh:
                fh.write("\n<!-- later edit -->\n")
            code, gate, _ = run("gate", base / "docs" / "website" / "verification.json", "--root", base, script=RECORDS)
            stale = {c["check_id"] for c in gate["checks"] if c["result"] == "stale"}
            self.assertEqual((code, gate["result"]), (1, "stale"))
            self.assertTrue({r["check_id"] for r in browser} | {"wp.runtime-content"} <= stale, stale)

    def test_capture_assets_match_the_theme(self):
        """The rendered capture is not fingerprinted against the theme, so compare the assets WordPress served."""
        captured = BASE / "capture" / "wp-content" / "themes" / "harbour-lane" / "assets"
        for name in ("theme.css", "order.js"):
            self.assertEqual((captured / name).read_bytes(), (BASE / "theme" / "harbour-lane" / "assets" / name).read_bytes(),
                             f"{name}: re-run sw_capture against Playground after theme changes")


if __name__ == "__main__":
    unittest.main()
