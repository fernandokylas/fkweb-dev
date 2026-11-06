#!/usr/bin/env python3
"""Sitewright static site checker (stdlib only, read-only unless --record is given).

Usage:
  sw_site_check.py SITE_DIR [--page REL ...] [--checks ID,ID] [--release | --mode mockup|production]
                   [--mockup-class NAME ...] [--routes ROUTES_JSON] [--records DIR]
                   [--record VERIFICATION_JSON --root PROJECT --evidence-out PATH [--require]
                    [--input PATH ...] [--exclude PATH ...]
                    [--allow-website-exclusion]]

SITE_DIR is the built output (static files, or DOM captures of a client-rendered app with
--routes listing its routes). Each HTML page is checked against the page-contract acceptance
checks below; results are reported per (check_id, target) so they can be recorded as evidence.

  a11y.landmarks          lang, one main, header/nav/footer, one h1, no skipped heading levels
  meta.basics             title, meta description, viewport (canonical missing is a warning; a 404 page
                          needs neither description nor canonical)
  nav.internal-links      local links and assets resolve; fragments exist; no "#" or example links
                          (an Elementor "#elementor-action:" link is a review warning)
  nav.active              navigation marks the current page with aria-current="page" (absolute links to
                          the origin the pages' canonicals name count as the site's own)
  form.labels             every form control has an accessible name (placeholder is not one)
  form.states             forms have a live status region; a form with no endpoint is labelled simulated
  media.images            images have alt; width and height (warning) to avoid layout shift; a local image
                          file over 400 KB (warning)
  motion.reduced          motion in CSS or JS comes with a prefers-reduced-motion path
  content.placeholders    no lorem ipsum, TODO/TBD or template business names in visible text; warning
                          when a page (not the 404) has under 30 words outside header, nav and footer
                          and no form, table, address, image or embedded media
  content.tells           warning (review) when visible copy leans on a stock contrast cadence three or more
                          times: "Not a X. Y.", "X, not Y." and short "No …" / "Just …" rebuttals. Counted per
                          block (paragraph, heading, list item, quote, caption, cell); never a defect
  content.fixture-markers data-fixture / [fixture] content (defect with --release, otherwise convention)
  content.mockup-notes    visible mock-up notes and placeholder labels (defect with --release, otherwise
                          convention): data-mockup, data-mockup-note, data-placeholder(="" or "true"), any
                          --mockup-class, and elements whose visible text is only a label such as
                          "Placeholder" or "Mock-up image", or starts with "Placeholder:" / "Mock-up:".
                          Hidden elements, template/script/style/noscript, code/pre/kbd/samp, comments,
                          attribute values (input placeholder="") and prose that mentions placeholders are
                          not flagged.
  integration.form-endpoint  per page with a form: a simulated, undisclosed-endpoint or example-host form
                          fails with --release; a declared endpoint is recorded unavailable, because only
                          a browser or manual submission test can show it works. Without --release a
                          simulated (disclosed) or declared form passes for the mock-up only.
  meta.indexing           robots meta (robots/googlebot noindex or none) against the page contract's
                          metadata_and_indexing_intent, read from --records DIR (default: the folder
                          of --record; its Markdown files are recorded as inputs). A mismatch either
                          way is a defect with --release and a warning without it; a noindex at release
                          with no stated intent is a warning (404 pages exempt).
  site.404                a custom 404 page exists

Criteria and modes: --release (or --mode production) judges release criteria; without it (or --mode
mockup) mock-up criteria. Only release-sensitive checks (content.fixture-markers, content.mockup-notes,
integration.form-endpoint, meta.indexing) are recorded with that mode; the others are recorded without one and count
for both gates. The payload's modes_written lists what each check was tagged with.

With --record, an --evidence-out file that records already cite is refused: each run writes a new file.

Containment: nothing outside SITE_DIR is read. A page or a linked stylesheet or script
that resolves outside it (through "..", an absolute path or a symlink) is not opened: a
discovered page is an error, a linked file is a nav.internal-links defect.

Recorded evidence binds each check to what it read: motion.reduced records the page's
linked CSS and JS as inputs, nav.internal-links the local files its links reach, and
--input adds further sources (for a capture, the theme or app it was rendered from).

What it does not establish: rendering, contrast, keyboard behaviour, responsive layout or
anything a browser has to observe. Those are browser or manual checks (website-verify).

Output: one JSON object on stdout (website-verify/references/evidence-contract.md).
Exit: 0 passed or skipped, 1 failed, 2 error or unavailable.
"""
import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_records  # noqa: E402  (same directory; shared report, fingerprint and record logic)

TOOL = "sw_site_check"
TOOL_VERSION = "6"
PAGE_CHECKS = ("a11y.landmarks", "meta.basics", "meta.indexing", "nav.internal-links", "nav.active", "form.labels",
               "form.states", "media.images", "motion.reduced", "content.placeholders", "content.tells",
               "content.fixture-markers", "content.mockup-notes")
FORM_CHECKS = ("integration.form-endpoint",)   # only for pages that have a form
SITE_CHECKS = ("site.404",)
ALL_CHECKS = PAGE_CHECKS + FORM_CHECKS + SITE_CHECKS
# Checks whose criteria differ between mock-up and production: recorded with the run's mode.
RELEASE_SENSITIVE = ("content.fixture-markers", "content.mockup-notes", "integration.form-endpoint",
                     "meta.indexing")
NOINDEX = re.compile(r"\b(?:no-?index|none)\b", re.IGNORECASE)
INDEX_INTENT = re.compile(r"\bindex(?:ed|able|ing)?\b", re.IGNORECASE)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source",
        "track", "wbr"}
UNLABELLED_INPUTS = {"hidden", "submit", "button", "reset", "image"}
# Stock contrast cadence (concept after Impeccable's aphoristic-cadence detector, Apache-2.0; original patterns)
TELL_PATTERNS = (
    re.compile(r"(?:^|(?<=[.!?]\s))Not (?:an?|the|just|only) [^.!?]{1,40}[.!]\s+[A-Z][^.!?]{1,60}[.!]"),
    re.compile(r"\b[\w'-]+(?: [\w'-]+){0,5}, not (?:an? |the |just |only )?[a-z][\w'-]*(?: [a-z][\w'-]*){0,4}[.!]"),
    re.compile(r"(?:^|(?<=[.!?]\s))(?:No|Just) [a-z][\w'-]*(?: [a-z][\w'-]*){0,3}[.!]"),   # "No shortcuts."
)
TELL_BLOCKS = ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "figcaption", "td", "dd", "dt")
PLACEHOLDER_TEXT = re.compile(sw_records.PLACEHOLDER_MARKERS + r"|\bAcme (Inc|Corp)\b|\bYour (Company|Business) Name\b",
                              re.IGNORECASE)
EXAMPLE_HOSTS = re.compile(r"(^|\.)example\.(com|org|net)$|^your-?(site|domain)\.", re.IGNORECASE)
CSS_MOTION = re.compile(r"(?<![-\w])(animation(-name)?|transition(-property)?)\s*:\s*(?!none\b)[^;}]+|"
                        r"@keyframes\b|scroll-behavior\s*:\s*smooth|animation-timeline\s*:", re.IGNORECASE)
JS_MOTION = re.compile(r"\.animate\s*\(|behavior\s*:\s*['\"]smooth['\"]|gsap\.|ScrollTrigger", re.IGNORECASE)
REDUCED = re.compile(r"prefers-reduced-motion", re.IGNORECASE)
SIMULATED_TEXT = re.compile(r"simulat|not (yet )?(connected|sent|delivered)|isn['’]t (sent|delivered|connected)",
                            re.IGNORECASE)
MAX_PAGE_BYTES = 5_000_000
MOCKUP_ATTRS = ("data-mockup", "data-mockup-note")
MOCKUP_WORD = r"(placeholder|mock-?up)"
MOCKUP_LABEL = re.compile(rf"^{MOCKUP_WORD}(\s+(image|photo|picture|portrait|text|copy|content|note|logo|video))?"
                          r"\s*[.:\u2013\u2014-]?$", re.IGNORECASE)
MOCKUP_PREFIX = re.compile(rf"^{MOCKUP_WORD}(\s+(image|photo|text|copy|content|note))?\s*:", re.IGNORECASE)
NOT_VISIBLE_TAGS = {"script", "style", "template", "noscript", "code", "pre", "kbd", "samp", "textarea", "head"}
HEAVY_IMAGE_BYTES = 400 * 1024   # media.images warns above this file size for a local <img src>
THIN_WORDS = 30          # content.placeholders warns below this many words of page content
CARRIER_TAGS = {"form", "iframe", "video", "audio", "canvas", "object", "embed", "address", "table", "img", "picture"}


def is_not_found(rel):
    return Path(rel).stem == "404" or rel == "404/index.html"
HIDDEN_STYLE = re.compile(r"(^|;)\s*(display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE)


class SiteReport(sw_records.Report):
    def emit(self, result, extra=None, code=None):
        return super().emit(result, {"tool": TOOL, "tool_version": TOOL_VERSION, **(extra or {})}, code)


class Node:
    __slots__ = ("tag", "attrs", "children", "parent", "line", "text")

    def __init__(self, tag, attrs, parent, line):
        self.tag, self.attrs, self.parent, self.line = tag, attrs, parent, line
        self.children, self.text = [], []

    def iter(self):
        yield self
        for c in self.children:
            yield from c.iter()

    def find_all(self, *tags):
        return [n for n in self.iter() if n.tag in tags]

    def find_rendered(self, *tags):
        """Like find_all, but skips <noscript> fallbacks, which never render alongside the scripted page."""
        return [n for n in self.find_all(*tags) if not any(a.tag == "noscript" for a in n.ancestors())]

    def ancestors(self):
        n = self.parent
        while n is not None:
            yield n
            n = n.parent

    def all_text(self):
        parts = list(self.text)
        for c in self.children:
            if c.tag not in ("script", "style", "template"):
                parts.append(c.all_text())
        return " ".join(p for p in parts if p).strip()


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, None, 1)
        self.cur = self.root
        self.inline_styles, self.inline_scripts = [], []

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v if v is not None else "") for k, v in attrs}, self.cur, self.getpos()[0])
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.cur.tag == tag:
            self.cur = self.cur.parent

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if self.cur.tag == "style":
            self.inline_styles.append(data)
        elif self.cur.tag == "script":
            if self.cur.attrs.get("type", "") in ("", "module", "text/javascript"):
                self.inline_scripts.append(data)
        elif data.strip():
            self.cur.text.append(data.strip())


def visible_text(node, checker):
    """Text of `node` that a visitor sees: hidden descendants and non-rendered elements are left out."""
    parts = list(node.text)
    for c in node.children:
        if checker.visible(c):
            parts.append(visible_text(c, checker))
    return " ".join(p for p in parts if p).strip()


class Page:
    def __init__(self, path, rel, tree, styles, scripts, deps, escapes):
        self.path, self.rel, self.tree = path, rel, tree
        self.styles, self.scripts = styles, scripts
        self.deps = deps                # linked CSS/JS files inside the site that were read
        self.escapes = escapes          # linked refs that resolve outside the site (never read)
        self.link_deps = set()          # local files the page's links reach (nav.internal-links)
        self.ids = {n.attrs["id"] for n in tree.root.iter() if n.attrs.get("id")}


class Checker:
    def __init__(self, site, routes, release, wanted, mockup_classes=(), contracts=None):
        self.site = site
        self.contracts = contracts      # {route: page contract} from --records, or None
        self.mockup_classes = set(mockup_classes)
        self.routes = routes
        self.release = release
        self.seen = set()
        self.wanted = wanted
        self.report = None
        self.results = {}
        self.pages = {}
        self.origins = set()            # scheme://host of the site, from the pages' absolute canonical links

    def note_origins(self):
        for page in self.pages.values():
            for n in page.tree.root.find_all("link"):
                if "canonical" in n.attrs.get("rel", "").lower():
                    parts = urlsplit(n.attrs.get("href", "").strip())
                    if parts.scheme in ("http", "https") and parts.netloc:
                        self.origins.add(f"{parts.scheme}://{parts.netloc.lower()}")

    def site_ref(self, ref):
        """An absolute link to the site's own origin (as its canonicals name it), as a root-relative ref."""
        parts = urlsplit(ref)
        if parts.scheme in ("http", "https") and f"{parts.scheme}://{parts.netloc.lower()}" in self.origins:
            return (parts.path or "/") + (f"?{parts.query}" if parts.query else "") + \
                (f"#{parts.fragment}" if parts.fragment else "")
        return ref

    # ----- recording -----
    def add(self, check_id, target, line, severity, evidence, action, kind="defect"):
        if check_id not in self.wanted:
            return
        key = (check_id, target, line, evidence)
        if key in self.seen:                     # the same finding from a repeated element or rule, once
            return
        self.seen.add(key)
        self.report.add(check_id, f"{target}:{line}" if line else target, severity, evidence, action, kind)
        if severity == "defect":
            self.results[(check_id, target)] = "failed"

    def ran(self, check_id, target):
        if check_id in self.wanted:
            self.results.setdefault((check_id, target), "passed")

    # ----- loading -----
    def inside(self, path):
        """True when `path` (symlinks resolved) lies inside the site directory."""
        try:
            Path(path).resolve().relative_to(self.site.resolve())
            return True
        except (ValueError, OSError, RuntimeError):
            return False

    def load(self, rel):
        path = self.site / rel
        if not self.inside(path):
            raise ValueError(f"{rel}: resolves outside the site directory (symlink or '..'); not read")
        size = path.stat().st_size
        if size > MAX_PAGE_BYTES:
            raise ValueError(f"{rel}: {size} bytes exceeds the {MAX_PAGE_BYTES}-byte page limit")
        text = path.read_text(encoding="utf-8")
        builder = TreeBuilder()
        builder.feed(text)
        builder.close()
        styles, scripts = list(builder.inline_styles), list(builder.inline_scripts)
        deps, escapes = [], set()
        for n in builder.root.iter():
            ref = None
            if n.tag == "link" and "stylesheet" in n.attrs.get("rel", "").lower():
                ref, bucket = n.attrs.get("href"), styles
            elif n.tag == "script" and n.attrs.get("src"):
                ref, bucket = n.attrs.get("src"), scripts
            if ref:
                local = self.local_file(rel, ref)
                if local is None:
                    continue
                if not self.inside(local):
                    escapes.add(ref)                     # checked by nav.internal-links; never opened
                elif local.is_file() and "node_modules" not in local.parts:
                    bucket.append(local.read_text(encoding="utf-8", errors="replace"))
                    deps.append(local)
        return Page(path, rel, builder, styles, scripts, deps, escapes)

    def local_file(self, rel, ref):
        """Resolve a local reference to a path inside the site, or None for external/special refs."""
        parts = urlsplit(ref)
        if parts.scheme or parts.netloc or ref.startswith(("//", "data:", "mailto:", "tel:", "javascript:")):
            return None
        path = unquote(parts.path)
        if not path:
            return None
        base = self.site if path.startswith("/") else (self.site / rel).parent
        return (base / path.lstrip("/")).resolve()

    def route_of(self, rel):
        p = Path(rel)
        if self.routes is not None:
            return self.routes.get(rel)
        if p.name == "index.html":
            return "/" + (p.parent.as_posix() + "/" if p.parent.as_posix() != "." else "")
        return "/" + p.with_suffix("").as_posix()

    def resolve_page(self, rel, ref):
        """Map an internal href to the page file it reaches; returns (page_rel or None, exists)."""
        parts = urlsplit(ref)
        path = unquote(parts.path)
        if not path:
            return rel, True
        if self.routes is not None and path.startswith("/") and not Path(path).suffix:
            norm = path.rstrip("/") or "/"
            for page_rel, route in self.routes.items():
                if (route.rstrip("/") or "/") == norm:
                    return page_rel, True
            return None, False
        target = self.local_file(rel, ref)
        if target is None:
            return None, True
        try:
            inside = target.relative_to(self.site.resolve())
        except ValueError:
            return None, False
        candidates = [target] if target.suffix else [target / "index.html", target.with_suffix(".html")]
        if path.endswith("/"):
            candidates = [target / "index.html"]
        for c in candidates:
            if c.is_file():
                return c.relative_to(self.site.resolve()).as_posix(), True
        return inside.as_posix(), False

    def check_indexing(self, rel, root):
        robots = [n for n in root.find_all("meta")
                  if n.attrs.get("name", "").lower() in ("robots", "googlebot")]
        noindex = next((n for n in robots if NOINDEX.search(n.attrs.get("content", ""))), None)
        route = self.route_of(rel)
        contract = (self.contracts or {}).get(sw_records.norm_route(route)) if route else None
        intent = (contract or {}).get("metadata_and_indexing_intent", "")
        want = False if NOINDEX.search(intent) else True if INDEX_INTENT.search(intent) else None
        sev = "defect" if self.release else "warning"
        later = "" if self.release else " (a defect with --release)"
        line = noindex.line if noindex else 0
        if want is True and noindex is not None:
            self.add("meta.indexing", rel, line, sev, f"robots noindex, but the page contract for {route} says index"
                     + later, "remove the noindex for release; keep review hosts private by access control")
        elif want is False and noindex is None:
            self.add("meta.indexing", rel, 0, sev, f"no robots noindex, but the page contract for {route} says noindex"
                     + later, 'add <meta name="robots" content="noindex"> to this page')
        elif want is None and noindex is not None and self.release and Path(rel).stem != "404":
            self.add("meta.indexing", rel, line, "warning",
                     "robots noindex at release and no indexing intent in a page contract"
                     + ("" if self.contracts is not None else " (run with --records to compare)"),
                     "state index or noindex in metadata_and_indexing_intent, or remove the noindex")

    # ----- page checks -----
    def content_tells(self, rel, root):
        hits = []
        for block in root.find_rendered(*TELL_BLOCKS):
            if any(a.tag in TELL_BLOCKS for a in block.ancestors()):
                continue                                   # counted once, in the outermost block
            text = re.sub(r"\s+", " ", block.all_text()).strip()
            for pattern in TELL_PATTERNS:
                hits += [(block.line, m.group(0)) for m in pattern.finditer(text)]
        if len(hits) >= 3:
            sample = "; ".join(f'line {line}: "{t[:60]}"' for line, t in hits[:3])
            self.add("content.tells", rel, hits[0][0], "warning",
                     f"{len(hits)} stock contrast lines ({sample}" + ("; …)" if len(hits) > 3 else ")"),
                     "keep them only if the content direction asks for this voice; otherwise rewrite the "
                     "sentences (swapping punctuation is not a rewrite), or ask the user once whether to accept it",
                     kind="review")

    def content_words(self, root):
        """Visible words in <main> (when there is exactly one), else in the body outside header, nav,
        footer and aside; None when the region holds a form or embedded media, which carry the page."""
        mains = root.find_rendered("main")
        region = mains[0] if len(mains) == 1 else next(iter(root.find_all("body")), root)
        skip = set() if len(mains) == 1 else {"header", "nav", "footer", "aside"}
        words = 0

        def walk(node):
            nonlocal words
            if node.tag in CARRIER_TAGS:
                return False
            words += sum(len(t.split()) for t in node.text)
            return all(walk(c) for c in node.children if c.tag not in skip and self.visible(c))
        return words if walk(region) else None

    def check_page(self, page):
        rel, root = page.rel, page.tree.root
        for cid in PAGE_CHECKS:
            self.ran(cid, rel)

        # a11y.landmarks
        html = next(iter(root.find_all("html")), None)
        if html is None or not html.attrs.get("lang", "").strip():
            self.add("a11y.landmarks", rel, html.line if html else 0, "defect", "<html> has no lang attribute",
                     "set lang to the page language")
        mains = root.find_rendered("main")
        if len(mains) != 1:
            self.add("a11y.landmarks", rel, 0, "defect", f"{len(mains)} <main> elements (expected 1)",
                     "wrap the page's main content in exactly one <main>")
        for tag in ("header", "nav", "footer"):
            if not root.find_rendered(tag):
                self.add("a11y.landmarks", rel, 0, "defect", f"no <{tag}> landmark",
                         f"add the shared {tag} from the site's global components")
        headings = root.find_rendered("h1", "h2", "h3", "h4", "h5", "h6")
        h1 = [h for h in headings if h.tag == "h1"]
        if len(h1) != 1:
            self.add("a11y.landmarks", rel, h1[1].line if len(h1) > 1 else 0, "defect",
                     f"{len(h1)} <h1> elements (expected 1)", "give the page one h1 that names it")
        prev = 0
        for h in headings:
            level = int(h.tag[1])
            if prev and level > prev + 1:
                self.add("a11y.landmarks", rel, h.line, "defect", f"heading jumps from h{prev} to h{level}",
                         "use the next heading level down, styled as needed")
            prev = level

        # meta.basics
        title = next(iter(root.find_all("title")), None)
        if title is None or not title.all_text():
            self.add("meta.basics", rel, 0, "defect", "missing or empty <title>", "add a page-specific title")
        metas = {n.attrs.get("name", "").lower(): n for n in root.find_all("meta") if n.attrs.get("name")}
        not_found = is_not_found(rel)   # never indexed: no description or canonical
        if not not_found and (not metas.get("description")
                              or not metas["description"].attrs.get("content", "").strip()):
            self.add("meta.basics", rel, 0, "defect", "missing or empty meta description",
                     "describe the page in one sentence")
        if "viewport" not in metas:
            self.add("meta.basics", rel, 0, "defect", "missing viewport meta",
                     'add <meta name="viewport" content="width=device-width, initial-scale=1">')
        if not not_found and not any("canonical" in n.attrs.get("rel", "").lower() for n in root.find_all("link")):
            self.add("meta.basics", rel, 0, "warning", "no canonical link",
                     "add one once the production URL is known", kind="convention")

        # meta.indexing: robots meta against the page contract's metadata_and_indexing_intent
        self.check_indexing(rel, root)

        # nav.internal-links (links, assets, fragments)
        for n in root.iter():
            attr = {"a": "href", "link": "href", "img": "src", "script": "src", "source": "src"}.get(n.tag)
            if not attr or attr not in n.attrs:
                continue
            ref = n.attrs[attr].strip()
            if n.tag == "a" and ref in ("", "#"):
                self.add("nav.internal-links", rel, n.line, "defect", f'placeholder link href="{ref}"',
                         "point the link at a real destination or use a <button>")
                continue
            if n.tag == "a" and unquote(urlsplit(ref).fragment).startswith("elementor-action:"):
                self.add("nav.internal-links", rel, n.line, "warning",
                         f"Elementor action link ({unquote(urlsplit(ref).fragment).split('&')[0]})",
                         "it works only with JavaScript: check in a browser that the popup or action opens; "
                         "for content visitors must reach, link to a page instead", kind="review")
                continue
            host = urlsplit(ref).hostname or ""
            if host and EXAMPLE_HOSTS.search(host):
                self.add("nav.internal-links", rel, n.line, "defect", f"example or template link: {ref}",
                         "replace with the real destination")
                continue
            local = self.local_file(rel, ref)
            if local is None and not urlsplit(ref).fragment:
                continue
            if ref in page.escapes or (local is not None and not self.inside(local)):
                self.add("nav.internal-links", rel, n.line, "defect",
                         f"{n.tag} {attr}={ref} resolves outside the site directory (not read)",
                         "keep links and assets inside the built site; copy the file in or fix the path")
                continue
            target_rel, exists = self.resolve_page(rel, ref)
            if exists and target_rel and target_rel != rel and (self.site / target_rel).exists():
                page.link_deps.add(self.site / target_rel)
            if not exists:
                self.add("nav.internal-links", rel, n.line, "defect", f"{n.tag} {attr}={ref} does not resolve",
                         "create the route or asset, or fix the link")
                continue
            frag = urlsplit(ref).fragment
            if frag and n.tag == "a" and target_rel and target_rel.endswith(".html"):
                target_page = self.pages.get(target_rel)
                if target_page and unquote(frag) not in target_page.ids:
                    self.add("nav.internal-links", rel, n.line, "defect", f"fragment #{frag} not found in {target_rel}",
                             "add the id to the target section or fix the link")

        # nav.active
        own = self.route_of(rel)
        for nav in root.find_all("nav"):
            links = [a for a in nav.find_all("a") if a.attrs.get("href")]
            hits = [a for a in links if self.resolve_page(rel, self.site_ref(a.attrs["href"]))[0] == rel
                    and not urlsplit(a.attrs["href"]).fragment]
            if hits and not any(a.attrs.get("aria-current") == "page" for a in hits):
                self.add("nav.active", rel, hits[0].line, "defect",
                         f"navigation links to this page ({own}) without aria-current=\"page\"",
                         "mark the current page's link with aria-current=\"page\"")
            stray = [a for a in links if a.attrs.get("aria-current") == "page" and a not in hits]
            for a in stray:
                self.add("nav.active", rel, a.line, "defect", f"aria-current=\"page\" on a link to {a.attrs['href']}",
                         "mark only the link to the current page")

        # form.labels
        labels_for = {n.attrs.get("for") for n in root.find_all("label") if n.attrs.get("for")}
        for n in root.find_all("input", "select", "textarea"):
            if n.tag == "input" and n.attrs.get("type", "text").lower() in UNLABELLED_INPUTS:
                continue
            named = (n.attrs.get("id") in labels_for or n.attrs.get("aria-label", "").strip()
                     or n.attrs.get("aria-labelledby", "").strip() or n.attrs.get("title", "").strip()
                     or any(a.tag == "label" for a in n.ancestors()))
            if not named:
                hint = " (placeholder is not a label)" if n.attrs.get("placeholder") else ""
                self.add("form.labels", rel, n.line, "defect",
                         f"<{n.tag} name=\"{n.attrs.get('name', '')}\"> has no accessible name{hint}",
                         "add a visible <label for> tied to the control's id")

        # form.states
        page_text = root.all_text()
        live = [n for n in root.iter() if n.attrs.get("role") in ("status", "alert") or n.attrs.get("aria-live")]
        for form in root.find_all("form"):
            if not live:
                self.add("form.states", rel, form.line, "defect", "form has no live status region",
                         "add an element with role=\"status\" (or aria-live) for loading, error and success messages")
            action = form.attrs.get("action", "").strip()
            simulated = form.attrs.get("data-handler", "").lower() == "simulated"
            if not action or action == "#":
                if not simulated:
                    self.add("form.states", rel, form.line, "defect",
                             "form has no delivery endpoint and is not marked data-handler=\"simulated\"",
                             "connect a real endpoint or mark and label the handler as simulated")
                elif not SIMULATED_TEXT.search(form.all_text() + " " + page_text):
                    self.add("form.states", rel, form.line, "defect",
                             "simulated form handler is not disclosed in visible text",
                             "tell visitors the form is not connected yet")

        # media.images
        for img in root.find_all("img"):
            if "alt" not in img.attrs:
                self.add("media.images", rel, img.line, "defect", f"<img src=\"{img.attrs.get('src', '')}\"> has no alt",
                         "describe the image, or alt=\"\" if it is decorative")
            if not (img.attrs.get("width") and img.attrs.get("height")):
                self.add("media.images", rel, img.line, "warning", "image without width and height",
                         "set intrinsic width and height to prevent layout shift", kind="convention")
            src = self.site_ref(img.attrs.get("src", ""))
            path = self.local_file(rel, src) if src else None
            if path and path.is_file() and path.stat().st_size > HEAVY_IMAGE_BYTES:
                self.add("media.images", rel, img.line, "warning",
                         f"{src} is {path.stat().st_size // 1024} KB",
                         f"resize to the largest displayed width and compress (WebP or AVIF for photos) to stay "
                         f"under {HEAVY_IMAGE_BYTES // 1024} KB; a heavy hero image delays the largest paint on phones")

        # motion.reduced
        styles, scripts = "\n".join(page.styles), "\n".join(page.scripts)
        styled = [n.attrs.get("style", "") for n in root.iter() if n.attrs.get("style")]
        motion = CSS_MOTION.search(styles) or JS_MOTION.search(scripts) or any(CSS_MOTION.search(s) for s in styled)
        if motion and not (REDUCED.search(styles) or REDUCED.search(scripts)):
            self.add("motion.reduced", rel, 0, "defect", f"motion without a reduced-motion path: {motion.group(0)[:60]}",
                     "add a prefers-reduced-motion rule that removes or shortens it")

        # content.placeholders and content.fixture-markers
        m = PLACEHOLDER_TEXT.search(page_text)
        if m:
            self.add("content.placeholders", rel, 0, "defect", f"placeholder text: {m.group(0)}",
                     "replace with real content or record an open issue")
        words = None if is_not_found(rel) else self.content_words(root)
        if words is not None and words < THIN_WORDS:
            self.add("content.placeholders", rel, 0, "warning",
                     f"only {words} words of content outside the header, navigation and footer",
                     "add the page's content (or record an open issue); a page that is only a heading reads "
                     "as unfinished to visitors and search engines")
        self.content_tells(rel, root)
        marked = [n for n in root.iter() if "data-fixture" in n.attrs] or (["text"] if "[fixture]" in page_text else [])
        if marked:
            line = marked[0].line if isinstance(marked[0], Node) else 0
            if self.release:
                self.add("content.fixture-markers", rel, line, "defect", "fixture content in a release build",
                         "replace fixture content with supplied content before release")
            else:
                self.add("content.fixture-markers", rel, line, "warning", "page contains fixture content",
                         "fine for development; must be replaced before release", kind="convention")

        # content.mockup-notes
        notes = self.mockup_notes(root)
        if notes:
            first = "; ".join(f"line {n.line}: {why}" for n, why in notes[:3])
            evidence = f"{len(notes)} visible mock-up note(s) or placeholder label(s) ({first}" + \
                ("; …)" if len(notes) > 3 else ")")
            if self.release:
                self.add("content.mockup-notes", rel, notes[0][0].line, "defect", evidence,
                         "replace each with final content (or remove the note) before release")
            else:
                self.add("content.mockup-notes", rel, notes[0][0].line, "warning", evidence,
                         "fine for a mock-up; must be resolved before release", kind="convention")

        # integration.form-endpoint
        forms = root.find_rendered("form")
        if forms:
            self.ran("integration.form-endpoint", rel)
        for form in forms:
            self.form_endpoint(rel, root, form)

    def visible(self, node):
        if node.tag in NOT_VISIBLE_TAGS or "hidden" in node.attrs:
            return False
        if node.attrs.get("aria-hidden", "").strip().lower() == "true":
            return False
        return not HIDDEN_STYLE.search(node.attrs.get("style", ""))

    def mockup_notes(self, root):
        """[(node, why)] for visible mock-up notes: explicit markers first, then label-only text. Only the
        innermost matching element is reported, so a note is counted once."""
        hits = []

        def walk(node):
            if node.tag != "#document" and not self.visible(node):
                return False
            classes = set(node.attrs.get("class", "").split())
            marker = next((a for a in MOCKUP_ATTRS if a in node.attrs), None)
            if marker is None and node.attrs.get("data-placeholder", None) in ("", "true"):
                marker = "data-placeholder"
            if marker is None and classes & self.mockup_classes:
                marker = "class " + sorted(classes & self.mockup_classes)[0]
            if marker:
                hits.append((node, f"marked {marker}"))
                return True
            found = False
            for child in node.children:
                found = walk(child) or found
            if found or node.tag == "#document":
                return found
            text = " ".join(visible_text(node, self).split())
            if text and (MOCKUP_LABEL.match(text) or MOCKUP_PREFIX.match(text)):
                hits.append((node, f"<{node.tag}> \"{text[:50]}\""))
                return True
            return False

        walk(root)
        return sorted(hits, key=lambda h: h[0].line)

    def form_endpoint(self, rel, root, form):
        """Release criteria: a simulated form, a form with no endpoint or handler, or an example host fails;
        a declared endpoint stays unavailable until a browser or manual submission test is recorded."""
        cid = "integration.form-endpoint"
        action = form.attrs.get("action", "").strip()
        handler = form.attrs.get("data-handler", "").strip()
        described = " ".join(n.all_text() for n in root.iter()
                             if n.attrs.get("id") and n.attrs["id"] in form.attrs.get("aria-describedby", "").split())
        disclosed = SIMULATED_TEXT.search(form.all_text() + " " + described)
        host = urlsplit(action).hostname or ""
        where = f"<form{' id=' + chr(34) + form.attrs['id'] + chr(34) if form.attrs.get('id') else ''}>"
        if host and EXAMPLE_HOSTS.search(host):
            self.add(cid, rel, form.line, "defect", f"{where} submits to an example host ({host})",
                     "point the form at its real endpoint or handler")
        elif handler.lower() == "simulated" or disclosed:
            why = 'data-handler="simulated"' if handler.lower() == "simulated" else "visible text says it is not connected"
            if self.release:
                self.add(cid, rel, form.line, "defect", f"{where} is simulated ({why}); nothing is delivered",
                         "connect the agreed form integration, then record a submission test (browser or manual)")
        elif (not action or action == "#") and not handler:
            if self.release:
                self.add(cid, rel, form.line, "defect", f"{where} has no endpoint or handler",
                         "connect the agreed form integration, then record a submission test")
            else:
                self.add(cid, rel, form.line, "warning", f"{where} has no endpoint or handler",
                         'mark a mock-up form data-handler="simulated" and say so in visible text',
                         kind="convention")
        elif self.release:
            declared = f"action={action}" if action and action != "#" else f'data-handler="{handler}"'
            self.add(cid, rel, form.line, "warning", f"{where} declares {declared}; source alone does not show "
                     "that submissions arrive", "test a submission against a local stub or the provider's test "
                     "mode and record it with --method browser or manual", kind="evidence")
            if self.results.get((cid, rel)) != "failed":
                self.results[(cid, rel)] = "unavailable"

    def check_site(self, all_rels):
        self.ran("site.404", ".")
        names = set(all_rels) if self.routes is None else set(self.routes)
        if not ({"404.html", "404/index.html"} & names):
            self.add("site.404", ".", 0, "defect", "no custom 404 page", "add 404.html with links back into the site")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sw_site_check.py", description=__doc__.splitlines()[0])
    parser.add_argument("site")
    parser.add_argument("--page", action="append", default=[], help="check only this page (relative path)")
    parser.add_argument("--checks", help="comma-separated check IDs (default: all)")
    parser.add_argument("--release", action="store_true",
                        help="judge release criteria: fixture content, mock-up notes and simulated forms are defects")
    parser.add_argument("--mode", choices=sw_records.DELIVERY_MODES,
                        help="criteria to judge: production is the same as --release, mockup the default; only "
                             "release-sensitive checks are recorded with it, the others count for both gates")
    parser.add_argument("--mockup-class", action="append", default=[], metavar="NAME",
                        help="a class that marks mock-up notes or placeholders in this project (repeatable)")
    parser.add_argument("--exclude", action="append", default=[], metavar="PATH",
                        help="with --record: leave PATH (relative to --root) out of folder targets that contain it")
    parser.add_argument("--allow-website-exclusion", action="store_true",
                        help="with --exclude: allow excluding a folder that holds website files")
    parser.add_argument("--records", metavar="DIR", help="project records folder (page contracts) for "
                        "meta.indexing; default: the folder of --record")
    parser.add_argument("--routes", help="JSON object {page_file: route} for DOM captures of a client-rendered app")
    parser.add_argument("--record", help="append one evidence record per (check, target) to this verification file")
    parser.add_argument("--root", help="project root for recorded targets (with --record)")
    parser.add_argument("--evidence-out", help="also write this report to PATH (required with --record)")
    parser.add_argument("--require", action="store_true", help="with --record: add each check to required_checks")
    parser.add_argument("--input", action="append", default=[], metavar="PATH",
                        help="with --record: a further source every record depends on, e.g. the theme or app "
                             "a capture was rendered from (repeatable)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    started = time.monotonic()
    site = Path(args.site)
    report = SiteReport(args.site)
    try:
        wanted = set(ALL_CHECKS)
        if args.checks:
            wanted = {c.strip() for c in args.checks.split(",") if c.strip()}
            unknown = wanted - set(ALL_CHECKS)
            if unknown:
                report.diagnostics.append(f"unknown check IDs: {', '.join(sorted(unknown))}")
                return report.emit("error")
        if args.record and not args.evidence_out:
            report.diagnostics.append("--record needs --evidence-out (evidence_path must name the saved output)")
            return report.emit("error")
        if args.mode == "mockup" and args.release:
            report.diagnostics.append("--mode mockup contradicts --release (release criteria are production)")
            return report.emit("error")
        args.release = args.release or args.mode == "production"
        if args.record:
            root = Path(args.root) if args.root else sw_records.default_root(args.record)
            clash = sw_records.cited_evidence_problem(args.record, root, args.evidence_out, TOOL)
            if clash:
                report.diagnostics.append(clash)
                return report.emit("error")
        if not site.is_dir():
            report.diagnostics.append(f"site directory not found: {args.site}")
            return report.emit("error")
        routes = None
        if args.routes:
            routes = json.loads(Path(args.routes).read_text(encoding="utf-8"))
            if not isinstance(routes, dict) or not all(isinstance(v, str) for v in routes.values()):
                report.diagnostics.append("--routes must be a JSON object mapping page files to routes")
                return report.emit("error")
        all_rels = sorted(p.relative_to(site).as_posix() for p in site.rglob("*.html")
                          if "node_modules" not in p.parts and (p.is_file() or p.is_symlink()))
        targets = args.page or all_rels
        contracts = None
        if args.records and not Path(args.records).is_dir():
            report.diagnostics.append(f"records folder not found: {args.records}")
            return report.emit("error")
        records_dir = args.records or (str(Path(args.record).parent) if args.record else None)
        if records_dir and Path(records_dir).is_dir():
            contracts, args.records_files = sw_records.page_contracts(records_dir)
        checker = Checker(site, routes, args.release, wanted, args.mockup_class, contracts)
        checker.report = report
        for rel in all_rels:
            checker.pages[rel] = checker.load(rel)
        checker.note_origins()
        missing = [t for t in targets if t not in checker.pages]
        if missing:
            report.diagnostics.append(f"page not found or not HTML: {', '.join(missing)}")
            return report.emit("error")
        if not targets:
            return report.emit("skipped", {"checks": [], "skip_reason": "no HTML pages in the site directory"})
        for rel in targets:
            checker.check_page(checker.pages[rel])
        if not args.page or (args.checks and "site.404" in wanted):   # needs only the page list
            checker.check_site(all_rels)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        report.diagnostics.append(f"{type(exc).__name__}: {exc}")
        return report.emit("error")

    accepted = sw_records.accept_findings(report, lambda loc: site / loc, args.record, records_dir, args.root)
    checks = [{"check_id": c, "target": t, "result": r} for (c, t), r in sorted(checker.results.items())]
    result = "failed" if any(f["severity"] == "defect" for f in report.findings) else "passed"
    mode = "production" if args.release else "mockup"
    payload = {"checks": checks, "release_mode": args.release, "mode": mode,
               "mockup_classes": sorted(checker.mockup_classes),
               "modes_written": {cid: (mode if cid in RELEASE_SENSITIVE else None)
                                 for cid in sorted({c["check_id"] for c in checks})}}
    if accepted is not None:
        payload["accepted"] = accepted
    if args.evidence_out:
        out = {"tool": TOOL, "tool_version": TOOL_VERSION, "target": str(site), "result": result,
               "findings": report.findings, "diagnostics": report.diagnostics, "checks": checks,
               **({"accepted": accepted} if accepted is not None else {}),
               "mockup_classes": sorted(checker.mockup_classes),
               "timestamp": sw_records.now_iso(), "duration_ms": int((time.monotonic() - started) * 1000)}
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        sw_records.write_json_atomic(args.evidence_out, out)
    if args.record:
        code = record_all(args, site, checker, checks, report)
        if code:
            return code
        if getattr(checker, "route_changes", None):
            payload["route_changes"] = checker.route_changes
        payload["evidence_kept"] = getattr(args, "evidence_kept", True)
    return report.emit(result, payload)


def submission_tested(verification, target):
    """True when the newest production record for the page's form endpoint is a browser or manual test."""
    try:
        data = sw_records.load_verification(verification)
    except (OSError, ValueError, KeyError, TypeError):
        return False
    newest = None
    for rec in data.get("records", []):
        if isinstance(rec, dict) and rec.get("check_id") == "integration.form-endpoint" \
                and rec.get("target") == target and sw_records.applies(rec, "production"):
            newest = rec
    return newest is not None and newest.get("method") in ("browser", "manual")


def record_all(args, site, checker, checks, report):
    root = Path(args.root) if args.root else sw_records.default_root(args.record)
    evidence = Path(args.evidence_out)
    try:
        evidence_rel = evidence.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        evidence_rel = str(evidence)
    entries = []
    for c in checks:
        target_path = site / c["target"] if c["target"] != "." else site
        try:
            target_rel = target_path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            report.diagnostics.append(f"target {target_path} is outside the project root {root}")
            return report.emit("error")
        found = [f["evidence"] for f in report.findings
                 if f["check_id"] == c["check_id"] and f["severity"] == "defect"
                 and f["location"].split(":")[0] == c["target"]]
        argv = ["record", args.record, "--root", str(root), "--check-id", c["check_id"],
                "--target", target_rel, "--result", c["result"], "--method", "automated",
                "--tool-and-version", f"{TOOL} {TOOL_VERSION}", "--evidence-path", evidence_rel,
                "--finding", "; ".join(found)[:400] or "no defects found by the static rules",
                "--limitations", "static source check; does not render the page or test keyboard, contrast or layout"]
        if args.require:
            argv.append("--require")
        page = checker.pages.get(c["target"])
        deps = []
        if page is not None and c["check_id"] == "motion.reduced":
            deps = page.deps
        elif page is not None and c["check_id"] == "nav.internal-links":
            deps = sorted(page.link_deps)
        elif c["check_id"] == "meta.indexing":
            deps = getattr(args, "records_files", [])
        for dep in [*deps, *args.input]:
            argv += ["--input", str(dep)]
        if c["check_id"] in RELEASE_SENSITIVE:
            argv += ["--mode", "production" if args.release else "mockup"]
        if c["check_id"] == "integration.form-endpoint":
            argv[argv.index("--limitations") + 1] = (
                "static source reading; shows how the form is declared, not that a submission arrives" +
                ("" if args.release else "; mock-up criteria only: production needs a submission test"))
            if c["result"] == "unavailable":
                if submission_tested(args.record, target_rel):
                    continue    # a browser or manual submission record decides; the gate judges its freshness
                argv[argv.index("--finding") + 1] = ("endpoint declared in source; no submission test recorded "
                                                     "(record one with --method browser or manual)")
        for given in sw_records.exclusions_within(root, target_path, args.exclude):
            argv += ["--exclude", given]
        if args.allow_website_exclusion:
            argv.append("--allow-website-exclusion")
        entries.append(argv[4:])
    try:
        site_rel = site.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        site_rel = None
    routes = {}

    def removed_pages(data):
        if site_rel is not None:
            routes["retired"], routes["potential_regressions"] = \
                sw_records.retire_removed_routes(data, root, Path(args.record), site_rel)

    # one validated, atomic write for the whole run; a refused entry leaves the file untouched
    if entries and sw_records.record_many(args.record, root, entries, report, before_write=removed_pages,
                                                 resolve=lambda loc: site / loc) is None:
        report.diagnostics.append("recording failed: nothing was written")
        return report.emit("error")
    if entries:
        args.evidence_kept = sw_records.keep_cited_evidence(args.record, evidence_rel, evidence)
    for item in routes.get("retired", []):
        report.diagnostics.append(f"retired {len(item['check_ids'])} check(s) on {item['target']}: route "
                                  f"{item['route']} is recorded as intentionally removed in state.json removed_routes")
    for item in routes.get("potential_regressions", []):
        report.add("site.missing-page", item["target"], "warning",
                   f"{item['target']} (route {item['route'] or 'not a page'}) is gone but "
                   f"{len(item['check_ids'])} required check(s) still name it: a potential regression",
                   "restore the page; if the removal was intended, record it in state.json removed_routes "
                   "(route, reason and the accepted decision or source), then rerun", kind="convention")
    checker.route_changes = routes
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # report, never pass silently
        r = SiteReport("")
        r.diagnostics.append(f"{type(exc).__name__}: {exc}")
        sys.exit(r.emit("error"))
