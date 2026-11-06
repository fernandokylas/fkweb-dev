"""Regression tests for scripts/sw_site_check.py against the Harbour Lane static fixture (item 06).

Run from the dev root: python3 -m unittest discover tests/site
Each negative case copies the fixture into a temporary directory (with a space in its path),
applies one mutation and expects exactly the matching check to fail.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "scripts" / "sw_site_check.py"
RECORDS = ROOT / "scripts" / "sw_records.py"
FIXTURE = ROOT / "tests" / "fixtures" / "sites" / "harbour-lane-static" / "site"


def run(*args, script=CHECK):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, timeout=60)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


def failed_checks(report):
    return {(c["check_id"], c["target"]) for c in report["checks"] if c["result"] == "failed"}


class FixtureTest(unittest.TestCase):
    def test_fixture_passes_with_only_conventions(self):
        code, report, err = run(FIXTURE)
        self.assertEqual((code, report["result"]), (0, "passed"), (err, report["findings"]))
        self.assertTrue(all(f["severity"] == "warning" for f in report["findings"]))
        targets = {c["target"] for c in report["checks"]}
        self.assertEqual(targets, {".", "index.html", "menu/index.html", "order/index.html",
                                   "contact/index.html", "404.html"})
        self.assertEqual(report["tool"], "sw_site_check")

    def test_release_mode_rejects_fixture_content(self):
        code, report, _ = run(FIXTURE, "--release")
        self.assertEqual((code, report["result"]), (1, "failed"))
        # the order form is data-handler="simulated": fine for the mock-up, a release defect
        self.assertEqual({c for c, _ in failed_checks(report)},
                         {"content.fixture-markers", "integration.form-endpoint"})

    def test_single_page_and_check_selection(self):
        code, report, _ = run(FIXTURE, "--page", "order/index.html", "--checks", "form.labels,form.states")
        self.assertEqual(code, 0)
        self.assertEqual({(c["check_id"], c["target"]) for c in report["checks"]},
                         {("form.labels", "order/index.html"), ("form.states", "order/index.html")})

    def test_a_check_selection_leaves_out_site_level_checks(self):
        """0.3.0 rerun hints narrow with --checks/--page; neither may record site.404 it was not asked for."""
        code, report, _ = run(FIXTURE, "--checks", "meta.basics")
        self.assertEqual(code, 0, report)
        self.assertEqual({c["check_id"] for c in report["checks"]}, {"meta.basics"})
        self.assertIn(("site.404", "."), {(c["check_id"], c["target"]) for c in run(FIXTURE)[1]["checks"]})
        code, report, _ = run(FIXTURE, "--page", "menu/index.html")       # a page run without --checks: no site.404
        self.assertNotIn("site.404", {c["check_id"] for c in report["checks"]})
        code, report, _ = run(FIXTURE, "--page", "menu/index.html", "--checks", "meta.basics,site.404")
        self.assertEqual({(c["check_id"], c["target"]) for c in report["checks"]},
                         {("meta.basics", "menu/index.html"), ("site.404", ".")})


MUTATIONS = {
    # name: (file, old, new, expected failing check)
    "no-lang": ("index.html", '<html lang="en-GB">', "<html>", "a11y.landmarks"),
    "two-h1": ("menu/index.html", "<h2 id=\"bread\">Bread</h2>", "<h1 id=\"bread\">Bread</h1>", "a11y.landmarks"),
    "skipped-heading": ("menu/index.html", '<h2 id="bread">Bread</h2>', '<h3 id="bread">Bread</h3>', "a11y.landmarks"),
    "no-footer": ("contact/index.html", '<footer class="site-footer">', '<div class="site-footer">', "a11y.landmarks"),
    "no-description": ("menu/index.html", '<meta name="description"', '<meta name="x-description"', "meta.basics"),
    "no-viewport": ("index.html", '<meta name="viewport"', '<meta name="x-viewport"', "meta.basics"),
    "broken-link": ("index.html", 'href="/menu/">See the full menu', 'href="/menus/">See the full menu', "nav.internal-links"),
    "hash-link": ("contact/index.html", 'href="tel:+15550123">555-0123</a></li>', 'href="#">555-0123</a></li>', "nav.internal-links"),
    "example-link": ("index.html", 'href="/contact/">Address', 'href="https://example.com/">Address', "nav.internal-links"),
    "missing-fragment": ("order/index.html", 'href="/menu/#cakes"', 'href="/menu/#cupcakes"', "nav.internal-links"),
    "missing-asset": ("menu/index.html", 'href="/assets/site.css"', 'href="/assets/missing.css"', "nav.internal-links"),
    "no-aria-current": ("menu/index.html", '<a href="/menu/" aria-current="page">', '<a href="/menu/">', "nav.active"),
    "wrong-aria-current": ("menu/index.html", '<a href="/order/">Order', '<a href="/order/" aria-current="page">Order', "nav.active"),
    "unlabelled-input": ("order/index.html", '<label for="name">Your name</label>', '', "form.labels"),
    "no-live-region": ("order/index.html", ' role="status" aria-live="polite"', '', "form.states"),
    "undisclosed-simulation": ("order/index.html", "<strong>This form is not connected yet.</strong> Orders are simulated in this test build and nothing is sent.", "<strong>Order online.</strong>", "form.states"),
    "unmarked-handler": ("order/index.html", ' data-handler="simulated"', '', "form.states"),
    "img-no-alt": ("index.html", "<h2 id=\"specials\">", '<img src="/assets/site.css" width="1" height="1"><h2 id="specials">', "media.images"),
    "motion-without-reduced": ("assets/site.css", "@media (prefers-reduced-motion: reduce)", "@media (max-width: 1px)", "motion.reduced"),
    "lorem": ("contact/index.html", "<h1>Contact</h1>", "<h1>Contact</h1><p>Lorem ipsum dolor sit amet.</p>", "content.placeholders"),
    "todo": ("menu/index.html", "Prices for this week.", "Prices TBD.", "content.placeholders"),
    "tbc": ("menu/index.html", "Prices for this week.", "Prices TBC.", "content.placeholders"),
    "verify-note": ("contact/index.html", "<h1>Contact</h1>", "<h1>Contact</h1><p>Open daily (verify hours).</p>", "content.placeholders"),
    "confirm-note": ("contact/index.html", "<h1>Contact</h1>", "<h1>Contact</h1><p>[Confirm parking details]</p>", "content.placeholders"),
    "need-note": ("contact/index.html", "<h1>Contact</h1>", "<h1>Contact</h1><p>[NEED: photo of shop front]</p>", "content.placeholders"),
    "french-note": ("contact/index.html", "<h1>Contact</h1>", "<h1>Contact</h1><p>Horaires à vérifier.</p>", "content.placeholders"),
}


class MutationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw site ")
        self.site = Path(self.tmp.name, "my site")
        shutil.copytree(FIXTURE, self.site)

    def tearDown(self):
        self.tmp.cleanup()

    def mutate(self, rel, old, new):
        path = self.site / rel
        text = path.read_text()
        self.assertIn(old, text, (rel, old))
        path.write_text(text.replace(old, new, 1))

    def test_each_mutation_fails_its_check(self):
        for name, (rel, old, new, check) in MUTATIONS.items():
            with self.subTest(name):
                shutil.rmtree(self.site)
                shutil.copytree(FIXTURE, self.site)
                self.mutate(rel, old, new)
                code, report, err = run(self.site)
                self.assertEqual((code, report["result"]), (1, "failed"), (name, err))
                self.assertEqual({c for c, _ in failed_checks(report)}, {check}, (name, report["findings"]))

    def test_ordinary_verify_and_confirm_copy_passes(self):
        # Only note forms count: real copy that says "verify" or "confirm" is not a draft marker.
        self.mutate("contact/index.html", "<h1>Contact</h1>",
                    "<h1>Contact</h1><p>Please verify your email. We confirm (within 24 hours) every order.</p>")
        code, report, err = run(self.site)
        self.assertEqual((code, report["result"]), (0, "passed"), (err, report["findings"]))

    def test_stock_contrast_cadence_is_a_review_warning_from_three_lines(self):
        cadence = ("<h1>Contact</h1><p>Not a bakery. A neighbourhood kitchen.</p>"
                   "<p>We bake for people, not for photos. No shortcuts.</p>")
        self.mutate("contact/index.html", "<h1>Contact</h1>", cadence)
        code, report, err = run(self.site)
        self.assertEqual((code, report["result"]), (0, "passed"), (err, report["findings"]))
        tells = [f for f in report["findings"] if f["check_id"] == "content.tells"]
        self.assertEqual(len(tells), 1, report["findings"])
        self.assertEqual((tells[0]["severity"], tells[0]["kind"]), ("warning", "review"))
        self.assertIn("3 stock contrast lines", tells[0]["evidence"])
        self.assertIn("Not a bakery", tells[0]["evidence"])

    def test_two_contrast_lines_or_ordinary_negation_are_not_tells(self):
        self.mutate("contact/index.html", "<h1>Contact</h1>",
                    "<h1>Contact</h1><p>Not a bakery. A kitchen.</p><p>Fresh, not frozen.</p>"
                    "<p>We do not deliver on Sundays. No parking is available on site, sorry.</p>")
        code, report, err = run(self.site)
        self.assertEqual([f for f in report["findings"] if f["check_id"] == "content.tells"], [],
                         report["findings"])

    def test_missing_404(self):
        (self.site / "404.html").unlink()
        code, report, _ = run(self.site)
        self.assertEqual(code, 1)
        self.assertEqual(failed_checks(report), {("site.404", ".")})


class ErrorAndSkipTest(unittest.TestCase):
    def test_missing_directory_is_error(self):
        code, report, _ = run("/nonexistent/site dir")
        self.assertEqual((code, report["result"]), (2, "error"))
        self.assertTrue(report["diagnostics"])

    def test_directory_without_html_is_skipped(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            Path(d, "notes.txt").write_text("not a site")
            code, report, _ = run(d)
            self.assertEqual((code, report["result"]), (0, "skipped"))
            self.assertTrue(report["skip_reason"])

    def test_unknown_check_and_page_are_errors(self):
        self.assertEqual(run(FIXTURE, "--checks", "nav.bogus")[0], 2)
        self.assertEqual(run(FIXTURE, "--page", "nope.html")[0], 2)

    def test_undecodable_page_is_error_not_pass(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            Path(d, "index.html").write_bytes(b"<html>\xff\xfe\xfa</html>")
            code, report, _ = run(d)
            self.assertEqual((code, report["result"]), (2, "error"))

    def test_bad_arguments_are_errors(self):
        code = subprocess.run([sys.executable, str(CHECK)], capture_output=True, timeout=30).returncode
        self.assertEqual(code, 2)
        self.assertEqual(run(FIXTURE, "--record", "x.json")[0], 2)  # --record needs --evidence-out


SPA_PAGE = """<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">
<title>Story</title><meta name="description" content="A story."><script src="/app.js"></script></head>
<body><noscript><main><h1>Needs JavaScript</h1></main></noscript>
<header><nav><a href="/" aria-current="page">Story</a><a href="/about">About</a></nav></header>
<main><h1>Story</h1></main><footer>Footer</footer></body></html>"""


class AbsoluteNavLinkTest(unittest.TestCase):
    """CMS menus (WordPress) link pages by absolute URL; the canonicals name the site's own origin."""

    PAGE = ('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">'
            '<title>{t}</title><meta name="description" content="The {t} page.">'
            '<link rel="canonical" href="https://example.org{route}"></head><body><header><nav>'
            '<a href="https://example.org/"{home}>Home</a><a href="https://example.org/about/"{about}>About</a>'
            '<a href="https://other.example.net/about/">Partner</a></nav></header>'
            '<main><h1>{t}</h1></main><footer>Footer</footer></body></html>')

    def write(self, d, about_current, home_on_about=False):
        cur = ' aria-current="page"'
        Path(d, "index.html").write_text(self.PAGE.format(t="Home", route="/", home=cur, about=""))
        Path(d, "about").mkdir()
        Path(d, "about", "index.html").write_text(self.PAGE.format(
            t="About", route="/about/", home=cur if home_on_about else "", about=cur if about_current else ""))
        Path(d, "404.html").write_text(self.PAGE.format(t="Not found", route="/", home="", about=""))

    def test_aria_current_on_the_pages_own_absolute_url_passes(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            self.write(d, about_current=True)
            code, report, err = run(d, "--checks", "nav.active")
            self.assertEqual((code, report["result"]), (0, "passed"), (err, report["findings"]))

    def test_404_page_needs_no_description_or_canonical(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            self.write(d, about_current=True)
            bare = (self.PAGE.format(t="Not found", route="/", home="", about="")
                    .replace('<meta name="description" content="The Not found page.">', "")
                    .replace('<link rel="canonical" href="https://example.org/">', ""))
            Path(d, "404.html").write_text(bare)
            code, report, err = run(d, "--checks", "meta.basics")
            self.assertEqual((code, report["result"]), (0, "passed"), (err, report["findings"]))
            self.assertEqual([f for f in report["findings"] if f["location"].startswith("404")], [])
            Path(d, "about", "index.html").write_text(bare)          # an ordinary page still needs both
            code, report, _ = run(d, "--checks", "meta.basics")
            self.assertIn(("meta.basics", "about/index.html"), failed_checks(report))

    def test_absolute_links_still_catch_a_missing_or_stray_current_marker(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            self.write(d, about_current=False, home_on_about=True)
            code, report, _ = run(d, "--checks", "nav.active")
            self.assertEqual(code, 1)
            evidence = [f["evidence"] for f in report["findings"] if f["location"].startswith("about/")]
            self.assertTrue(any("without aria-current" in e for e in evidence), evidence)
            self.assertTrue(any('aria-current="page" on a link to https://example.org/' in e for e in evidence),
                            evidence)


class ThinPageTest(unittest.TestCase):
    """A page that is only a heading (a CMS page published empty) is flagged for review, not failed."""

    PAGE = ('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">'
            '<title>Privacy policy</title><meta name="description" content="How we handle your data.">'
            '</head><body><header><nav><a href="/">Home</a> <a href="/privacy/">Privacy policy</a> '
            '<a href="/contact/">Contact us today for a free quote on your next project</a></nav></header>'
            '{main}<footer><p>Footer text with plenty of words that must not count towards the page '
            'content, such as the address, the opening hours and the newsletter sign-up line.</p></footer>'
            '</body></html>')

    def warnings(self, d, main):
        Path(d, "index.html").write_text(self.PAGE.format(main=main))
        code, report, err = run(d, "--checks", "content.placeholders")
        thin = [f for f in report["findings"] if "words of content" in f["evidence"]]
        return code, report, thin

    def test_heading_only_page_warns_without_failing(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            code, report, thin = self.warnings(d, "<main><h1>Privacy policy</h1></main>")
            self.assertEqual((code, report["result"]), (0, "passed"))
            self.assertEqual([(f["severity"], f["evidence"]) for f in thin],
                             [("warning", "only 2 words of content outside the header, navigation and footer")])

    def test_without_main_the_body_outside_header_nav_and_footer_is_counted(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            _, _, thin = self.warnings(d, "<div><h1>Privacy policy</h1></div>")
            self.assertEqual(len(thin), 1)

    def test_real_content_a_form_or_a_table_carries_the_page(self):
        prose = "<p>" + " ".join(["word"] * 30) + "</p>"
        for main in (f"<main><h1>Privacy</h1>{prose}</main>",
                     '<main><h1>Contact</h1><form action="/send"><label>Email <input name="e"></label></form></main>',
                     "<main><h1>Hours</h1><table><tr><th>Mon</th><td>Closed</td></tr></table></main>"):
            with self.subTest(main=main[:30]), tempfile.TemporaryDirectory(prefix="sw site ") as d:
                self.assertEqual(self.warnings(d, main)[2], [])

    def test_404_page_is_not_flagged(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            Path(d, "index.html").write_text(self.PAGE.format(main="<main><h1>Home</h1>" + "<p>" +
                                                              " ".join(["word"] * 30) + "</p></main>"))
            Path(d, "404.html").write_text(self.PAGE.format(main="<main><h1>Not found</h1></main>"))
            _, report, _ = run(d, "--checks", "content.placeholders")
            self.assertEqual([f for f in report["findings"] if "words of content" in f["evidence"]], [])


class HeavyImageTest(unittest.TestCase):
    """A multi-megabyte hero image is the usual cause of a slow largest paint on phones."""

    PAGE = ('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">'
            '<title>Home</title><meta name="description" content="Home page."></head><body><main><h1>Home</h1>'
            '<img src="{src}" alt="Harbour at dawn" width="1600" height="900"></main></body></html>')

    def heavy(self, d, src, size):
        Path(d, "img").mkdir(exist_ok=True)
        Path(d, "img", "hero.png").write_bytes(b"\0" * size)
        Path(d, "index.html").write_text(self.PAGE.format(src=src))
        code, report, _ = run(d, "--checks", "media.images")
        return code, report, [f for f in report["findings"] if " KB" in f["evidence"]]

    def test_image_over_the_limit_warns_without_failing(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            code, report, heavy = self.heavy(d, "/img/hero.png", 1700 * 1024)
            self.assertEqual((code, report["result"]), (0, "passed"))
            self.assertEqual([(f["severity"], f["evidence"]) for f in heavy], [("warning", "/img/hero.png is 1700 KB")])

    def test_small_relative_or_missing_images_do_not_warn(self):
        for src, size in (("img/hero.png", 200 * 1024), ("img/missing.png", 1700 * 1024),
                          ("https://cdn.example.net/hero.png", 1700 * 1024)):
            with self.subTest(src=src), tempfile.TemporaryDirectory(prefix="sw site ") as d:
                self.assertEqual(self.heavy(d, src, size)[2], [])


class ElementorActionLinkTest(unittest.TestCase):
    """Elementor opens popups from "#elementor-action:..." links: not a missing fragment, but JS-only."""

    def test_action_link_is_a_review_warning_and_a_real_missing_fragment_still_fails(self):
        link = '<a href="#elementor-action%3Aaction%3Dpopup%3Aopen%26settings%3DeyJpZCI6MTE3OX0%3D">Get a quote</a>'
        page = ('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width">'
                '<title>Home</title></head><body><main><h1>Home</h1>{}</main></body></html>')
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            Path(d, "index.html").write_text(page.format(link))
            code, report, _ = run(d, "--checks", "nav.internal-links")
            self.assertEqual((code, report["result"]), (0, "passed"), report["findings"])
            self.assertEqual([(f["severity"], f["evidence"]) for f in report["findings"]],
                             [("warning", "Elementor action link (elementor-action:action=popup:open)")])
            Path(d, "index.html").write_text(page.format('<a href="#pricing">Pricing</a>'))
            code, report, _ = run(d, "--checks", "nav.internal-links")
            self.assertEqual(code, 1)


class CapturedAppTest(unittest.TestCase):
    """Client-rendered apps are checked from DOM captures, with --routes mapping capture files to routes."""

    def write(self, d, routes):
        Path(d, "index.html").write_text(SPA_PAGE)
        Path(d, "404.html").write_text(SPA_PAGE.replace('aria-current="page"', ""))
        Path(d, "app.js").write_text("document.querySelector('h1').animate([{opacity: 0}, {opacity: 1}], 200);\n"
                                     "matchMedia('(prefers-reduced-motion: reduce)');\n")
        Path(d, "routes.json").write_text(json.dumps(routes))

    def test_noscript_fallback_is_not_a_second_landmark_and_routes_resolve(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            self.write(d, {"index.html": "/", "404.html": "/404", "about.html": "/about"})
            Path(d, "about.html").write_text(SPA_PAGE.replace('href="/" aria-current="page"', 'href="/"')
                                             .replace('href="/about"', 'href="/about" aria-current="page"'))
            code, report, err = run(d, "--routes", Path(d, "routes.json"))
            self.assertEqual((code, report["result"]), (0, "passed"), (err, report["findings"]))

    def test_unknown_route_fails_and_bad_routes_file_errors(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            self.write(d, {"index.html": "/", "404.html": "/404"})
            code, report, _ = run(d, "--routes", Path(d, "routes.json"))
            self.assertEqual(code, 1)
            self.assertIn(("nav.internal-links", "index.html"), failed_checks(report))
            Path(d, "routes.json").write_text('["index.html"]')
            self.assertEqual(run(d, "--routes", Path(d, "routes.json"))[0], 2)

    def test_js_motion_without_reduced_motion_fails(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            self.write(d, {"index.html": "/", "404.html": "/404", "about.html": "/about"})
            Path(d, "about.html").write_text(SPA_PAGE)
            Path(d, "app.js").write_text("document.querySelector('h1').animate([{opacity: 0}, {opacity: 1}], 200);\n")
            code, report, _ = run(d, "--routes", Path(d, "routes.json"))
            self.assertIn(("motion.reduced", "index.html"), failed_checks(report))


CONTRACTS = """# Site map

- routes: /, /menu, /order, /contact

### Page: /menu

- metadata_and_indexing_intent: index; canonical /menu/

### Page: `/contact/`

- metadata_and_indexing_intent: noindex until the opening hours are confirmed
"""


class IndexingTest(unittest.TestCase):
    """meta.indexing: robots meta against the page contracts (every fixture page carries noindex)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw site ")
        self.project = Path(self.tmp.name, "my project")
        shutil.copytree(FIXTURE, self.project / "site")
        self.records = self.project / "docs" / "website"
        self.records.mkdir(parents=True)
        (self.records / "website.md").write_text(CONTRACTS)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, *extra):
        code, report, err = run(self.project / "site", "--checks", "meta.indexing", *extra)
        self.assertIn(code, (0, 1), (err, report))
        return report

    def findings(self, report):
        return {(f["location"].split(":")[0], f["severity"]) for f in report["findings"]}

    def test_mismatch_is_a_warning_for_a_review_build(self):
        report = self.check("--records", self.records)
        self.assertEqual(report["result"], "passed")
        self.assertEqual(self.findings(report), {("menu/index.html", "warning")})

    def test_mismatch_is_a_defect_at_release(self):
        report = self.check("--records", self.records, "--release")
        self.assertEqual(failed_checks(report), {("meta.indexing", "menu/index.html")})
        # pages without a stated intent only warn; the 404 page is exempt
        self.assertIn(("index.html", "warning"), self.findings(report))
        self.assertNotIn("404.html", {loc for loc, _ in self.findings(report)})

    def test_missing_noindex_is_a_defect_at_release(self):
        page = self.project / "site" / "contact" / "index.html"
        page.write_text(page.read_text().replace('<meta name="robots" content="noindex">', ""))
        report = self.check("--records", self.records, "--release")
        self.assertIn(("meta.indexing", "contact/index.html"), failed_checks(report))

    def test_without_records_release_only_warns(self):
        report = self.check("--release")
        self.assertEqual(report["result"], "passed")
        self.assertTrue(report["findings"])
        self.assertTrue(all(f["severity"] == "warning" for f in report["findings"]))

    def test_missing_records_folder_is_an_error(self):
        code, report, _ = run(self.project / "site", "--records", self.project / "nope")
        self.assertEqual((code, report["result"]), (2, "error"))

    def test_records_are_inputs_so_a_contract_change_is_stale(self):
        verification = self.records / "verification.json"
        code, report, err = run(self.project / "site", "--checks", "meta.indexing", "--record", verification,
                                "--root", self.project, "--evidence-out", self.records / "evidence" / "idx.json",
                                "--require")
        self.assertEqual(code, 0, (err, report))
        gcode, gate, _ = run("gate", verification, "--root", self.project, "--mode", "mockup", script=RECORDS)
        self.assertEqual(gcode, 0, gate)
        contracts = self.records / "website.md"
        contracts.write_text(contracts.read_text().replace("index; canonical", "noindex; canonical"))
        gcode, gate, _ = run("gate", verification, "--root", self.project, "--mode", "mockup", script=RECORDS)
        self.assertEqual((gcode, gate["result"]), (1, "stale"), gate)


class RecordTest(unittest.TestCase):
    def test_records_every_check_and_gate_reflects_them(self):
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            project = Path(d, "bakery project")
            shutil.copytree(FIXTURE, project / "site")
            verification = project / "docs" / "website" / "verification.json"
            evidence = project / "docs" / "website" / "evidence" / "site-check.json"
            code, report, err = run(project / "site", "--record", verification, "--root", project,
                                    "--evidence-out", evidence, "--require")
            self.assertEqual(code, 0, (err, report))
            saved = json.loads(evidence.read_text())
            self.assertEqual(saved["result"], "passed")
            records = json.loads(verification.read_text())["records"]
            self.assertEqual(len(records), len(report["checks"]))
            self.assertTrue(all(r["method"] == "automated" and r["evidence_path"] == "docs/website/evidence/site-check.json"
                                for r in records))
            # without --release only the release-sensitive checks judge mock-up criteria; the rest count for both
            self.assertEqual({r["check_id"] for r in records if r.get("mode")},
                             {"content.fixture-markers", "content.mockup-notes", "integration.form-endpoint",
                              "meta.indexing"})
            self.assertEqual({r["mode"] for r in records if r.get("mode")}, {"mockup"})
            gcode, gate, _ = run("gate", verification, "--root", project, "--mode", "mockup", script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (0, "passed"), gate)
            gcode, gate, _ = run("gate", verification, "--root", project, script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (1, "unavailable"), gate)
            self.assertEqual({c["check_id"] for c in gate["checks"] if c["result"] != "passed"},
                             {"content.fixture-markers", "content.mockup-notes", "integration.form-endpoint",
                              "meta.indexing"})
            # editing a checked page makes its record stale
            page = project / "site" / "menu" / "index.html"
            page.write_text(page.read_text().replace("Prices for this week.", "Prices for this fortnight."))
            gcode, gate, _ = run("gate", verification, "--root", project, "--mode", "mockup", script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (1, "stale"), gate)
            stale = {(c["check_id"], c["target"]) for c in gate["checks"] if c["result"] == "stale"}
            self.assertIn(("site.404", "site"), stale)
            self.assertIn(("a11y.landmarks", "site/menu/index.html"), stale)
            # pages linking to the menu page depend on it for nav.internal-links only
            others = {t for c, t in stale if t not in ("site", "site/menu/index.html")}
            self.assertTrue(others)
            self.assertEqual({c for c, t in stale if t in others}, {"nav.internal-links"})
            self.assertNotIn(("a11y.landmarks", "site/index.html"), stale)

    def test_a_missing_page_retires_only_when_its_removal_is_recorded_as_intended(self):
        """Refinement 3 of the 0.2.2 plan: a page that disappears is a potential regression and stays
        required; only a route listed in state.json removed_routes (with a decision or source) retires."""
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            project = Path(d, "bakery project")
            shutil.copytree(FIXTURE, project / "site")
            verification = project / "docs" / "website" / "verification.json"
            runs = iter(range(10))

            def check():
                evidence = project / "docs" / "website" / "evidence" / f"site-check-{next(runs)}.json"
                return run(project / "site", "--record", verification, "--root", project, "--evidence-out",
                           evidence, "--checks", "a11y.landmarks", "--require")
            self.assertEqual(check()[0], 0)
            shutil.rmtree(project / "site" / "order")
            code, report, err = check()
            self.assertEqual(code, 0, (err, report))
            self.assertEqual(report["route_changes"]["retired"], [])
            self.assertEqual([i["target"] for i in report["route_changes"]["potential_regressions"]],
                             ["site/order/index.html"])
            self.assertTrue(any(f["check_id"] == "site.missing-page" and "potential regression" in f["evidence"]
                                for f in report["findings"]))
            gcode, gate, _ = run("gate", verification, "--root", project, "--mode", "mockup", script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (1, "error"), gate)
            # a removal without a decision or source is not a recorded intention
            state = project / "docs" / "website" / "state.json"
            state.write_text(json.dumps({"removed_routes": [{"route": "/order", "reason": "orders by phone"}]}))
            code, report, _ = check()
            self.assertEqual(len(report["route_changes"]["potential_regressions"]), 1)
            state.write_text(json.dumps({"removed_routes": [{"route": "/order/", "reason": "orders by phone",
                                                             "source": "owner's message, 27 Oct"}]}))
            code, report, err = check()
            self.assertEqual(code, 0, (err, report))
            self.assertEqual([i["route"] for i in report["route_changes"]["retired"]], ["/order"])
            gcode, gate, _ = run("gate", verification, "--root", project, "--mode", "mockup", script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (0, "passed"), gate)
            history = [h for h in json.loads(verification.read_text())["requirement_history"] if h["action"] == "retire"]
            self.assertTrue(history and all("removed_routes" in h["basis"] and h["decided_by"] == "" for h in history))

    def test_linked_css_change_makes_motion_record_stale(self):
        """Finding 7: a page's motion.reduced record binds the CSS it read; editing only the CSS makes it stale."""
        with tempfile.TemporaryDirectory(prefix="sw site ") as d:
            project = Path(d, "bakery project")
            shutil.copytree(FIXTURE, project / "site")
            verification = project / "docs" / "website" / "verification.json"
            evidence = project / "docs" / "website" / "evidence" / "site-check.json"
            code, report, err = run(project / "site", "--record", verification, "--root", project,
                                    "--evidence-out", evidence, "--checks", "motion.reduced,a11y.landmarks", "--require")
            self.assertEqual(code, 0, (err, report))
            records = json.loads(verification.read_text())["records"]
            motion = [r for r in records if r["check_id"] == "motion.reduced" and r["target"] == "site/index.html"]
            self.assertEqual(list(motion[0]["inputs"]), ["site/assets/site.css"])
            css = project / "site" / "assets" / "site.css"
            css.write_text(css.read_text() + "\n.x{color:red}\n")
            gcode, gate, _ = run("gate", verification, "--root", project, script=RECORDS)
            self.assertEqual((gcode, gate["result"]), (1, "stale"), gate)
            stale = {c["check_id"] for c in gate["checks"] if c["result"] == "stale"}
            self.assertEqual(stale, {"motion.reduced"})


class ModeAndNoiseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw site ")
        self.project = Path(self.tmp.name, "bakery project")
        shutil.copytree(FIXTURE, self.project / "site")

    def tearDown(self):
        self.tmp.cleanup()

    def test_identical_findings_are_reported_once(self):
        page = self.project / "site" / "index.html"
        twin = '<img src="assets/favicon.svg" alt="Mark"><img src="assets/favicon.svg" alt="Mark">'
        page.write_text(page.read_text().replace("  </main>", f"  {twin}\n  </main>", 1))
        code, report, err = run(self.project / "site", "--checks", "media.images")
        self.assertEqual(code, 0, (err, report))
        sizes = [f for f in report["findings"] if f["evidence"] == "image without width and height"]
        self.assertEqual(len(sizes), 1, report["findings"])

    def test_release_run_tags_only_release_sensitive_checks(self):
        verification = self.project / "docs" / "website" / "verification.json"
        evidence = self.project / "docs" / "website" / "evidence"
        code, report, err = run(self.project / "site", "--record", verification, "--root", self.project,
                                "--evidence-out", evidence / "site-1.json",
                                "--checks", "content.fixture-markers,meta.basics", "--release", "--require")
        self.assertEqual(report["mode"], "production")
        self.assertEqual(report["modes_written"], {"content.fixture-markers": "production", "meta.basics": None})
        records = json.loads(verification.read_text())["records"]
        self.assertEqual({r.get("mode") for r in records if r["check_id"] == "content.fixture-markers"},
                         {"production"})
        self.assertEqual({r.get("mode") for r in records if r["check_id"] == "meta.basics"}, {None})
        # a later non-release run cannot hide the production failure
        code, _, err = run(self.project / "site", "--record", verification, "--root", self.project,
                           "--evidence-out", evidence / "site-2.json", "--checks", "content.fixture-markers")
        self.assertEqual(code, 0, err)
        gcode, gate, _ = run("gate", verification, "--root", self.project, script=RECORDS)
        fixture = {c["result"] for c in gate["checks"] if c["check_id"] == "content.fixture-markers"}
        self.assertEqual(fixture, {"failed"}, gate)
        gcode, gate, _ = run("gate", verification, "--root", self.project, "--mode", "mockup", script=RECORDS)
        self.assertEqual(gate["result"], "passed", gate)

    def test_mode_selects_criteria_and_never_tags_mode_neutral_checks(self):
        """Finding 4: --mode production judges release criteria; meta.basics stays unmoded either way."""
        verification = self.project / "docs" / "website" / "verification.json"
        evidence = self.project / "docs" / "website" / "evidence"
        code, report, _ = run(self.project / "site", "--record", verification, "--root", self.project,
                              "--evidence-out", evidence / "a.json", "--checks",
                              "content.fixture-markers,meta.basics", "--mode", "production")
        self.assertEqual((code, report["release_mode"]), (1, True))
        run(self.project / "site", "--record", verification, "--root", self.project,
            "--evidence-out", evidence / "b.json", "--checks", "meta.basics", "--mode", "mockup")
        modes = {(r["check_id"], r.get("mode")) for r in json.loads(verification.read_text())["records"]}
        self.assertEqual(modes, {("content.fixture-markers", "production"), ("meta.basics", None)})
        code, report, _ = run(self.project / "site", "--mode", "mockup", "--release")
        self.assertEqual((code, report["result"]), (2, "error"))

    def test_cited_evidence_file_is_not_overwritten(self):
        """Finding 5: a second run to the same --evidence-out is refused; the first records keep their file."""
        verification = self.project / "docs" / "website" / "verification.json"
        evidence = self.project / "docs" / "website" / "evidence" / "site-check.json"
        run(self.project / "site", "--record", verification, "--root", self.project, "--evidence-out", evidence,
            "--checks", "meta.basics")
        before = evidence.read_bytes()
        code, report, _ = run(self.project / "site", "--record", verification, "--root", self.project,
                              "--evidence-out", evidence, "--checks", "meta.basics")
        self.assertEqual((code, report["result"]), (2, "error"))
        self.assertIn("docs/website/evidence/site-check-", " ".join(report["diagnostics"]))
        self.assertEqual(evidence.read_bytes(), before)
        gcode, gate, _ = run("gate", verification, "--root", self.project, "--mode", "mockup", script=RECORDS)
        self.assertNotIn("stale", {c["result"] for c in gate["checks"]})


class ContainmentTest(unittest.TestCase):
    """Finding 4: nothing outside the site directory is read, and an escaping reference is never a silent pass."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw site ")
        self.base = Path(self.tmp.name)
        self.site = self.base / "site"
        shutil.copytree(FIXTURE, self.site)
        # outside the site: CSS full of motion with no reduced-motion path, and JS that animates
        (self.base / "outside.css").write_text("@keyframes spin{to{transform:rotate(1turn)}} .a{animation:spin 1s}")
        (self.base / "outside.js").write_text("el.animate([{opacity:0}],{duration:300});")
        (self.base / "secret.html").write_text("<p>lorem ipsum TODO outside</p>")

    def tearDown(self):
        self.tmp.cleanup()

    def edit_home(self, old, new):
        home = self.site / "index.html"
        home.write_text(home.read_text().replace(old, new, 1))

    def assert_escape_defect(self, report):
        found = [f for f in report["findings"] if f["check_id"] == "nav.internal-links"
                 and "outside the site directory" in f["evidence"]]
        self.assertTrue(found, report["findings"])
        self.assertIn(("nav.internal-links", "index.html"), failed_checks(report))
        # the outside file was never read: its motion would otherwise fail motion.reduced
        self.assertNotIn(("motion.reduced", "index.html"), failed_checks(report))

    def test_dotdot_stylesheet_is_a_defect_and_not_read(self):
        self.edit_home('href="/assets/site.css"', 'href="../outside.css"')
        code, report, _ = run(self.site)
        self.assertEqual((code, report["result"]), (1, "failed"))
        self.assert_escape_defect(report)

    def test_encoded_and_absolute_style_escapes(self):
        for ref in ("%2e%2e/outside.css", "/../outside.css", "assets/%2e%2e/%2e%2e/outside.css"):
            with self.subTest(ref=ref):
                shutil.rmtree(self.site)
                shutil.copytree(FIXTURE, self.site)
                self.edit_home('href="/assets/site.css"', f'href="{ref}"')
                code, report, _ = run(self.site)
                self.assertEqual(code, 1, report)
                self.assert_escape_defect(report)

    def test_script_through_symlink_is_a_defect_and_not_read(self):
        (self.site / "assets" / "linked.js").symlink_to(self.base / "outside.js")
        self.edit_home("</body>", '<script src="/assets/linked.js"></script></body>')
        code, report, _ = run(self.site)
        self.assertEqual(code, 1, report)
        self.assert_escape_defect(report)

    def test_symlinked_directory_escape(self):
        (self.base / "ext").mkdir()
        shutil.copy(self.base / "outside.css", self.base / "ext" / "o.css")
        (self.site / "assets" / "ext").symlink_to(self.base / "ext", target_is_directory=True)
        self.edit_home('href="/assets/site.css"', 'href="/assets/ext/o.css"')
        code, report, _ = run(self.site)
        self.assertEqual(code, 1, report)
        self.assert_escape_defect(report)

    def test_symlinked_page_outside_the_site_is_an_error(self):
        (self.site / "leak.html").symlink_to(self.base / "secret.html")
        code, report, _ = run(self.site)
        self.assertEqual((code, report["result"]), (2, "error"), report)
        self.assertIn("outside the site directory", " ".join(report["diagnostics"]))
        self.assertNotIn("lorem", json.dumps(report))

    def test_links_inside_the_site_still_pass(self):
        # a symlink that stays inside the site, and relative links within it, are legitimate
        (self.site / "assets" / "alias.css").symlink_to(self.site / "assets" / "site.css")
        self.edit_home('href="/assets/site.css"', 'href="assets/alias.css"')
        code, report, err = run(self.site)
        self.assertEqual((code, report["result"]), (0, "passed"), (err, report["findings"]))



class CommittedEvidenceTest(unittest.TestCase):
    """The committed fixture evidence must stay fresh: editing a fixture without re-recording fails here."""

    def test_fixture_verification_gates_pass(self):
        for name in ("harbour-lane-static", "harbour-lane-react"):
            base = ROOT / "tests" / "fixtures" / "sites" / name
            proc = subprocess.run([sys.executable, str(RECORDS), "gate",
                                   str(base / "docs" / "website" / "verification.json"), "--root", str(base)],
                                  capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, (name, proc.stdout[-800:], proc.stderr[-400:]))

    def test_browser_evidence_goes_stale_when_a_dependency_changes(self):
        """Browser records bind the whole build (static) or the sources plus build inputs (React), so a
        stylesheet or entry-page edit outside the record's target still makes the evidence stale."""
        cases = (("harbour-lane-static", "site/assets/site.css"), ("harbour-lane-react", "index.html"))
        for name, dependency in cases:
            with self.subTest(name), tempfile.TemporaryDirectory(prefix="sw dep ") as tmp:
                base = Path(tmp) / name
                shutil.copytree(ROOT / "tests" / "fixtures" / "sites" / name, base,
                                ignore=shutil.ignore_patterns("node_modules", "dist"))
                records = json.loads((base / "docs" / "website" / "verification.json").read_text())
                browser = [r for r in records["records"] if r["check_id"].startswith("browser.")]
                self.assertTrue(browser and all("inputs" in r for r in browser), name)
                with open(base / dependency, "a", encoding="utf-8") as fh:
                    fh.write("\n/* later edit */\n" if dependency.endswith(".css") else "\n<!-- later edit -->\n")
                proc = subprocess.run([sys.executable, str(RECORDS), "gate",
                                       str(base / "docs" / "website" / "verification.json"), "--root", str(base)],
                                      capture_output=True, text=True, timeout=60)
                gate = json.loads(proc.stdout)
                stale = {c["check_id"] for c in gate["checks"] if c["result"] == "stale"}
                self.assertEqual(gate["result"], "stale")
                self.assertTrue({r["check_id"] for r in browser} <= stale, (name, stale))


if __name__ == "__main__":
    unittest.main()
