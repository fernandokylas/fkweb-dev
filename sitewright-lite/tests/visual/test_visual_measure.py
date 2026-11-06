"""Regression tests for skills/website-verify/scripts/visual-measure.js (visual.measure).

Run from the dev root: python3 -m unittest discover tests/visual
Each scenario is a scratch HTML page with one known composition defect (a heading whose top margin a later
rule resets, a generated ::before box taking a grid cell, a column whose edge drifts, gaps off the spacing
scale) plus a clean control. The page loads the script with data-output="dom" and headless Chrome dumps the
DOM, so the measurements come from a real layout. Chrome runs with a throwaway profile, local files only.
Without a Chrome binary every test is skipped with the reason; that is `unavailable`, never a pass.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "website-verify" / "scripts" / "visual-measure.js"
# The Playwright headless shell is preferred: the full Chrome app can stall waking its updater.
SHELLS = [Path.home() / "Library" / "Caches" / "ms-playwright", Path.home() / ".cache" / "ms-playwright"]
APPS = ("/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
SCALE = "0,4,8,16,24,32,48,64"


def last(element):
    """The last step of a measured path, without its :nth-of-type()."""
    return re.sub(r":nth-of-type\(\d+\)", "", element.split(" > ")[-1])


def find_chrome():
    env = os.environ.get("SW_CHROME")
    if env:
        return env if Path(env).is_file() else None
    for cache in SHELLS:
        found = sorted(cache.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"),
                       key=lambda p: p.parts[-3])
        if found:
            return str(found[-1])
    for path in APPS:
        if Path(path).is_file():
            return path
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


CHROME = find_chrome()
IMG = "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27200%27 height=%27100%27/%3E"
BASE = "html,body{margin:0;padding:0} body{font:16px/1.5 sans-serif;width:960px;padding:32px} p{margin:0 0 16px}"

PAGES = {
    "clean": """
<main>
  <section class="intro"><h2>Menu</h2><p>One.</p><p>Two.</p><p>Three.</p></section>
  <ul class="cards"><li>A</li><li>B</li><li>C</li></ul>
</main>""",
    "heading-reset": """
<main>
  <section class="card"><p>Lead paragraph.</p><h2>Ingredients</h2><p>Flour, water, salt.</p></section>
</main>""",
    "grid-before": """
<main>
  <ol class="path"><li>Apprentice</li><li>Baker</li><li>Head baker</li></ol>
</main>""",
    "misaligned": """
<main>
  <section class="column"><p>One.</p><p class="drift">Two.</p><p>Three.</p><p>Four.</p></section>
</main>""",
    "tracking": """
<main>
  <p class="intro">An introduction long enough to read as running text, set with very wide tracking.</p>
  <span class="kicker">New season</span><p class="plain">Ordinary text.</p>
</main>""",
    "overflow": """
<main>
  <div class="wide">A banner set wider than the page.</div>
  <div class="track"><div class="belt">A belt inside a clipping track.</div></div>
</main>""",
    "clipped": """
<main>
  <p class="title">A product title far too long for the narrow box it was given</p>
  <div class="box"><p>First line of a card.</p><p>Second line.</p><p>Third line, cut off.</p></div>
  <div class="round"><p>Fits.</p></div>
  <span class="sr-only">Skip to content, for screen readers</span>
</main>""",
    "edge": """
<main>
  <p class="edge">Text pulled out to the screen edge.</p>
  <p class="ok">Text on the page margin.</p>
</main>""",
    "edge-phone": """
<main>
  <p>Text on a 14px phone margin.</p>
  <p class="edge">Text pressed to the edge.</p>
</main>""",
    "framed": f"""
<main>
  <figure class="frame inline"><img src="{IMG}" width="200" height="100" alt=""></figure>
  <figure class="frame block"><img src="{IMG}" width="200" height="100" alt=""></figure>
</main>""",
    "reveal": """
<main>
  <div class="spacer">Top of the page.</div>
  <section class="reveal"><p>Revealed on scroll.</p></section>
  <p class="never">Never revealed.</p>
  <div class="acc"><button aria-expanded="false" aria-controls="panel">More</button>
    <div id="panel" class="panel"><p>Collapsed answer.</p></div></div>
  <div class="squash"><p>Squashed by a zero-height box.</p></div>
  <details><summary>Question</summary><p>Answer inside closed details.</p></details>
  <span class="sr-only">Screen reader text</span><span class="off-left">Old helper text</span>
  <p class="away">Waiting to slide in.</p>
</main>
<script>
  // Reveal once the viewport has reached the section. A scroll-position timer stands in for an
  // IntersectionObserver: under --dump-dom virtual time the headless shell runs timers but hardly any
  // rendering frames, so observers never fire there (they do in a real browser session).
  var reveal = document.querySelector(".reveal");
  setInterval(function () {
    if (window.scrollY + window.innerHeight > reveal.offsetTop) reveal.classList.add("in");
  }, 30);
</script>""",
    "dark": """
<main><p class="theme-note">Shown only in the light scheme.</p><p>Always shown.</p></main>""",
    "tells": """
<main>
  <section class="card"><p class="eyebrow">Our approach</p><span class="num">01</span><h2>Plan</h2>
    <a href="#a">Read more →</a></section>
  <section class="card"><p class="eyebrow">Our process</p><span class="num">02</span><h2>Build</h2>
    <a href="#b">Read more →</a></section>
  <section class="card"><p class="eyebrow">Our results</p><span class="num">03</span><h2>Launch</h2>
    <a href="#c">Read more →</a></section>
  <section class="card"><p class="label">Contact</p><h2>Talk</h2><a href="#d">Write to us</a></section>
</main>""",
    "components": """
<header class="site"><nav><a href="/">Home</a> <a href="/about/">About</a></nav></header>
<main>
  <p>Intro.</p>
  <a class="button" href="#a">Book</a> <a class="button" href="#b">Call</a> <button class="ghost">Menu</button>
  <section class="cta"><h2>Ready?</h2><a class="button" href="#c">Start</a></section>
</main>
<footer class="site">Footer</footer>""",
}
PAGES["reveal-nosweep"] = PAGES["reveal"]
PAGES["components-b"] = PAGES["components"].replace("<p>Intro.</p>", "<p>A longer intro.</p><p>Second.</p>")
SIZE = {"edge-phone": "390,844"}
SWEEP = {"reveal"}
FLAGS = {"dark": ["--blink-settings=preferredColorScheme=0"]}
CSS = {
    "clean": ".intro h2{margin:32px 0 16px} .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;"
             "list-style:none;margin:0;padding:0}",
    "heading-reset": "h2{margin:40px 0 24px} .card h2{margin:0 0 24px}",
    "grid-before": ".path{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;list-style:none;margin:0;"
                   "padding:0} .path::before{content:'';border-top:1px solid #333}",
    "misaligned": ".column .drift{margin-left:12px} .column p{margin-bottom:20px}",
    "tracking": ".intro{letter-spacing:.3em} .kicker{text-transform:uppercase;font-size:12px;letter-spacing:.16em}",
    "overflow": ".wide{width:1400px} .track{overflow-x:hidden} .belt{width:2000px}",
    "clipped": ".title{width:200px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
               " .box{height:40px;overflow:hidden} .round{overflow:hidden;border-radius:8px}"
               " .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}",
    "edge": ".edge{margin-left:-24px}",
    "edge-phone": "body{width:auto;padding:0 14px} .edge{margin-left:-8px}",
    "framed": ".frame{margin:0 0 16px;padding:12px;border:1px solid #333;width:200px} .block img{display:block}",
    "reveal": ".spacer{height:2400px} .reveal{opacity:0} .reveal.in{opacity:1} .never{opacity:0}"
              " .panel{height:0;overflow:hidden} .squash{height:0;overflow:hidden}"
              " .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}"
              " .off-left{position:absolute;left:-9999px} .away{transform:translateX(-200vw)}",
    "dark": "@media (prefers-color-scheme: dark){.theme-note{opacity:0}}",
    "tells": ".card{border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,.1);padding:16px;margin:0 0 16px}"
             " .eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:12px}"
             " .label{text-transform:uppercase;font-size:12px}",
    "components": "header.site{background:#111;color:#fff;padding:12px 24px} footer.site{background:#eee;padding:24px}"
                  " .button{display:inline-block;background:#c30;color:#fff;padding:8px 16px;border-radius:4px}"
                  " .ghost{background:none;border:1px solid #333;padding:8px 16px}"
                  " .cta{background:#f4efe6;padding:24px}",
}
CSS["reveal-nosweep"] = CSS["reveal"]
CSS["components-b"] = CSS["components"].replace(".button{display:inline-block;background:#c30",
                                                ".button{display:inline-block;background:#036")


@unittest.skipUnless(CHROME, "no Chrome or Chromium binary found (set SW_CHROME); visual.measure is unavailable")
class VisualMeasureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="sw visual ")
        cls.dir = Path(cls.tmp.name)
        shutil.copy(SCRIPT, cls.dir / "visual-measure.js")
        cls.results = {}
        for name, body in PAGES.items():
            page = cls.dir / f"{name}.html"
            page.write_text(f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{name}</title>"
                            f"<style>{BASE} {CSS[name]}</style></head><body>{body}\n"
                            f"<script src=\"visual-measure.js\" data-output=\"dom\" data-scale=\"{SCALE}\" "
                            f"data-root=\"main\"{' data-sweep=\"true\"' if name in SWEEP else ''}></script>"
                            f"</body></html>")
            cls.results[name] = cls.measure(page, SIZE.get(name, "1280,900"), FLAGS.get(name, []))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def measure(cls, page, size="1280,900", flags=()):
        profile = cls.dir / f"profile-{page.stem}"
        mode = [] if CHROME.endswith("chrome-headless-shell") else ["--headless=new"]
        try:
            done = subprocess.run([CHROME, *mode, "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                                   "--disable-extensions", f"--user-data-dir={profile}", f"--window-size={size}",
                                   # timers and frames run before the DOM is dumped (the reveal sweep waits)
                                   "--virtual-time-budget=10000", *flags, "--dump-dom", page.as_uri()],
                                  capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            raise unittest.SkipTest(f"{CHROME} did not finish rendering {page.name} in 60 s; visual.measure is "
                                    "unavailable on this machine (set SW_CHROME to a headless shell)")
        m = re.search(r'<script type="application/json" id="sw-visual-measure">(.*?)</script>', done.stdout, re.DOTALL)
        if not m:
            raise AssertionError(f"no measurement in the dumped DOM for {page.name}: {done.stderr[-400:]}")
        return json.loads(m.group(1))

    def test_clean_control_has_nothing_to_review(self):
        r = self.results["clean"]
        self.assertNotIn("error", r)
        self.assertEqual(r["off_scale"], [], r["gaps"])
        self.assertEqual([h for h in r["heading_rhythm"] if h["tighter_above"]], [])
        self.assertEqual([a for a in r["alignment"] if a["outliers"]], [])
        grid = [g for g in r["grid_items"] if "ul.cards" in g["container"]]
        self.assertEqual(len(grid), 1, r["grid_items"])
        self.assertEqual((grid[0]["column_tracks"], grid[0]["generated_items"], grid[0]["rows_used"]), (3, [], 1))
        self.assertEqual((r["overflow"]["amount"], r["overflow"]["culprits"]), (0, []))
        self.assertEqual((r["clipped"], r["edge_text"], r["framed_media"], r["edge_margin"]), ([], [], [], 16))

    def test_heading_whose_top_margin_was_reset_sits_closer_to_the_block_above(self):
        rhythm = [h for h in self.results["heading-reset"]["heading_rhythm"] if h["heading"].endswith("h2")]
        self.assertEqual(len(rhythm), 1, rhythm)
        self.assertEqual((rhythm[0]["above"], rhythm[0]["below"], rhythm[0]["tighter_above"]), (16, 24, True))

    def test_generated_box_takes_a_grid_cell_and_pushes_items_to_a_new_row(self):
        grid = [g for g in self.results["grid-before"]["grid_items"] if "ol.path" in g["container"]]
        self.assertEqual(len(grid), 1, self.results["grid-before"]["grid_items"])
        g = grid[0]
        self.assertEqual(g["generated_items"], ["::before"])
        self.assertEqual((g["column_tracks"], g["children"], g["cells_used"], g["rows_used"]), (3, 3, 4, 2))
        self.assertGreater(g["first_child_offset"], 0)     # the first real item no longer starts the row

    def test_drifting_column_edge_and_off_scale_gaps_are_measured(self):
        r = self.results["misaligned"]
        outliers = [o for a in r["alignment"] for o in a["outliers"]]
        self.assertEqual([(o["child"], o["offset_from_common"]) for o in outliers], [("p.drift:nth-of-type(2)", 12)])
        self.assertEqual(len(r["off_scale"]), 3, r["gaps"])       # the three 20px gaps between the paragraphs
        self.assertTrue(all(o["gap"] == 20 and o["nearest"] in (16, 24) for o in r["off_scale"]), r["off_scale"])

    def test_tracking_lists_wide_text_with_what_settles_its_role(self):
        """Finding 6: class-only rules the static check could not classify are measured in the browser."""
        rows = {r["element"].split(".")[-1].split(":")[0]: r for r in self.results["tracking"]["tracking"]}
        self.assertEqual(set(rows), {"intro", "kicker"}, rows)
        self.assertEqual((rows["intro"]["tag"], rows["intro"]["letter_spacing_em"], rows["intro"]["text_transform"]),
                         ("p", 0.3, "none"))
        self.assertGreater(rows["intro"]["text_length"], 60)
        self.assertEqual((rows["kicker"]["text_transform"], rows["kicker"]["font_size_px"]), ("uppercase", 12))
        self.assertEqual(self.results["clean"]["tracking"], [])

    def test_overflow_names_the_element_past_the_edge_but_not_one_its_ancestor_clips(self):
        o = self.results["overflow"]["overflow"]
        self.assertGreater(o["amount"], 100, o)
        self.assertEqual([last(c["element"]) for c in o["culprits"]], ["div.wide"], o)

    def test_clipped_text_is_measured_with_its_axis_and_ellipsis(self):
        rows = {last(r["element"]): r for r in self.results["clipped"]["clipped"]}
        self.assertEqual(set(rows), {"p.title", "div.box"}, rows)     # the fitting box and sr-only helper are not
        self.assertEqual((rows["p.title"]["axis"], rows["p.title"]["ellipsis"]), ("x", True))
        self.assertEqual((rows["div.box"]["axis"], rows["div.box"]["ellipsis"]), ("y", False))
        self.assertTrue(rows["div.box"]["text"].startswith("Second") or rows["div.box"]["text"].startswith("Third"))

    def test_edge_text_uses_16px_on_desktop_and_12px_on_a_phone(self):
        desk = self.results["edge"]
        self.assertEqual(desk["edge_margin"], 16)
        self.assertEqual([(last(r["element"]), r["side"], r["px"]) for r in desk["edge_text"]],
                         [("p.edge", "left", 8)])
        phone = self.results["edge-phone"]
        self.assertEqual(phone["edge_margin"], 12)
        self.assertEqual([(last(r["element"]), r["px"]) for r in phone["edge_text"]], [("p.edge", 6)])

    def test_framed_inline_image_has_unequal_insets_and_a_block_image_does_not(self):
        rows = {last(r["frame"]).split(".")[-1]: r for r in self.results["framed"]["framed_media"]}
        self.assertEqual(set(rows), {"inline", "block"}, rows)
        self.assertTrue(rows["inline"]["unequal"], rows["inline"])
        self.assertGreater(rows["inline"]["insets"]["bottom"], rows["inline"]["insets"]["top"])
        self.assertFalse(rows["block"]["unequal"], rows["block"])
        self.assertEqual(rows["block"]["insets"], {"top": 12, "right": 12, "bottom": 12, "left": 12})

    def test_reveal_sweep_shows_scroll_reveals_and_invisible_text_lists_what_stays_hidden(self):
        swept, before = self.results["reveal"], self.results["reveal-nosweep"]
        self.assertTrue(swept["swept"])
        self.assertFalse(before["swept"])
        rows = {r["text"]: r["reason"] for r in swept["invisible_text"]}
        self.assertEqual(rows, {"Never revealed.": "opacity", "Squashed by a zero-height box.": "clipped",
                                "Waiting to slide in.": "offscreen"}, swept["invisible_text"])
        texts = " ".join(r["text"] for r in swept["invisible_text"])
        for kept_out in ("Revealed on scroll", "Collapsed answer", "closed details", "Screen reader", "Old helper"):
            self.assertNotIn(kept_out, texts)
        before_texts = {r["text"]: r["reason"] for r in before["invisible_text"]}
        self.assertEqual(before_texts.get("Revealed on scroll."), "opacity")    # what a print from the top shows

    def test_media_state_is_reported_and_dark_only_hiding_is_found(self):
        light, dark = self.results["clean"]["media"], self.results["dark"]["media"]
        self.assertEqual((light["print"], light["color_scheme"]), (False, "light"))
        self.assertEqual(dark["color_scheme"], "dark")
        self.assertEqual([r["text"] for r in self.results["dark"]["invisible_text"]], ["Shown only in the light sch"
                                                                                     "eme."])
        self.assertEqual(self.results["clean"]["invisible_text"], [])

    def test_tells_count_repeated_template_devices(self):
        tells = self.results["tells"]["tells"]
        self.assertEqual((tells["eyebrows"]["count"], tells["eyebrows"]["repeated"]), (3, True), tells)
        self.assertEqual(tells["eyebrows"]["samples"][0], "Our approach")   # the untracked label is not one
        self.assertEqual((tells["numbering"]["count"], tells["numbering"]["samples"]), (3, ["01", "02", "03"]))
        self.assertEqual((tells["trailing_arrows"]["count"], tells["trailing_arrows"]["repeated"]), (3, True))
        self.assertEqual((tells["card_kit"]["count"], tells["card_kit"]["repeated"]), (4, True))
        self.assertEqual(tells["card_kit"]["radius"], "12px")
        clean = self.results["clean"]["tells"]
        self.assertEqual([clean[k]["count"] for k in ("eyebrows", "numbering", "trailing_arrows", "card_kit")],
                         [0, 0, 0, 0])

    def test_components_digest_shared_parts_so_pages_can_be_compared(self):
        a, b = self.results["components"]["components"], self.results["components-b"]["components"]
        self.assertEqual(last(a["header"]["element"]), "header.site")
        self.assertEqual(a["header"]["style"]["background_color"], "rgb(17, 17, 17)")
        self.assertEqual(last(a["footer"]["element"]), "footer.site")
        self.assertIsNotNone(a["nav"])
        for name in ("header", "nav", "footer"):
            self.assertEqual(a[name]["digest"], b[name]["digest"], name)       # same CSS, same look
        self.assertEqual([g["count"] for g in a["buttons"]], [3, 1], a["buttons"])   # 2 links + panel link; ghost
        self.assertNotEqual(a["buttons"][0]["digest"], b["buttons"][0]["digest"])   # the primary colour changed
        self.assertEqual(len(a["cta_panels"]), 1, a["cta_panels"])
        self.assertEqual(last(a["cta_panels"][0]["element"]), "section.cta")
        clean = self.results["clean"]["components"]
        self.assertEqual((clean["header"], clean["buttons"], clean["cta_panels"]), (None, [], []))

    def test_measurements_make_no_judgement(self):
        for name, r in self.results.items():
            text = json.dumps(r)
            for word in ("passed", "failed", "defect", "result"):
                self.assertNotIn(f'"{word}"', text, name)


if __name__ == "__main__":
    unittest.main()
