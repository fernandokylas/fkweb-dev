#!/usr/bin/env python3
"""Sitewright WordPress block-theme checker (stdlib only, read-only unless --record is given).

Usage:
  sw_wp_theme_check.py THEME_DIR [--content DIR] [--tokens CSS_FILE] [--probe PROBE_JSON]
                       [--checks ID,ID]
                       [--record VERIFICATION_JSON --root PROJECT --evidence-out PATH [--require]]

THEME_DIR is a block theme (style.css, theme.json, templates/, parts/, patterns/). --content is a
directory of page content in block markup (*.html, optional pages.json listing slug and template).
--tokens is a CSS file whose custom properties are the design record's tokens
(--color-*, --space-N, --radius-1, --duration-short); theme.json must carry the same values.

  wp.theme-header        style.css header names the theme, version, requirements, licence and text domain
  wp.theme-json          theme.json parses, has a supported version, and its parts and custom templates exist
  wp.tokens              every preset a template, part, pattern or page uses exists; --tokens values match
  wp.block-markup        block comments are balanced, attributes are valid JSON, no stray markup between blocks
  wp.template-structure  index template exists; each template has one main; template parts and patterns resolve;
                         page templates render post content
  wp.patterns            pattern headers have a title and a slug in the theme's namespace; slugs are unique
  wp.content-editable    page content is blocks, not classic HTML; Custom HTML and shortcodes are reported
  wp.assets              files that functions.php and theme.json load exist
  wp.php-safety          request input, database queries, output escaping, remote calls and embedded secrets

With --probe (output of scripts/wp-probe from a disposable local WordPress):
  wp.runtime-theme       the theme is active as a block theme, without errors, at the checked version
  wp.runtime-templates   WordPress resolves every template, part and pattern from the theme's files
  wp.runtime-content     published pages are parsed as registered blocks with no classic chunks

Runtime results are bound to the snapshot the probe observed. The probe (version 2) lists a
SHA-256 for every file in the active theme and for each page's stored content. The runtime checks
are `stale`, not passed or failed, when the probe is version 1, when its theme files differ from
THEME_DIR, or (wp.runtime-content) when a page's stored content differs from its --content file
or no --content is given. Re-running this checker against an old probe therefore never refreshes
runtime evidence: probe the current theme and content again. Recorded runtime results target
THEME_DIR, with --content as an input of wp.runtime-content; the probe file is supporting
evidence, never an input.

What it does not establish: that PHP parses (only a running WordPress shows that; see --probe),
how blocks look, editor validation of saved markup (a browser check), or how a production site
with other plugins behaves. Severity follows context: a finding is a defect only when the rule
is broken in a way that matters for this file; otherwise it is a warning with the reason.

Output: one JSON object on stdout. Exit: 0 passed, 1 failed, 2 error or stale.
"""
import argparse
import contextlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_records  # noqa: E402

TOOL = "sw_wp_theme_check"
TOOL_VERSION = "2"
STATIC_CHECKS = ("wp.theme-header", "wp.theme-json", "wp.tokens", "wp.block-markup", "wp.template-structure",
                 "wp.patterns", "wp.content-editable", "wp.assets", "wp.php-safety")
RUNTIME_CHECKS = ("wp.runtime-theme", "wp.runtime-templates", "wp.runtime-content")
ALL_CHECKS = STATIC_CHECKS + RUNTIME_CHECKS
MAX_BYTES = 2_000_000

# Block delimiters: <!-- wp:name {json} /--> and <!-- /wp:name -->. Attribute JSON ends at the
# first "}" that is followed by whitespace and the end of the comment.
BLOCK = re.compile(r"<!--\s+(?P<close>/)?wp:(?P<name>[a-z][a-z0-9_-]*(?:/[a-z][a-z0-9_-]*)?)\s+"
                   r"(?:(?P<attrs>\{.*?\})\s+)?(?P<void>/)?-->", re.DOTALL)
PHP_TAG = re.compile(r"<\?(?:php|=).*?(?:\?>|$)", re.DOTALL)
HEADER_FIELDS = ("Theme Name", "Version", "Requires at least", "Requires PHP", "License", "Text Domain")
PRESET_KINDS = {"color": "palette", "font-size": "fontSizes", "spacing": "spacingSizes",
                "font-family": "fontFamilies", "gradient": "gradients"}
ATTR_PRESETS = {"backgroundColor": "color", "textColor": "color", "borderColor": "color",
                "overlayColor": "color", "fontSize": "font-size", "fontFamily": "font-family", "gradient": "gradient"}
VAR_PRESET = re.compile(r"var:preset\|([a-z-]+)\|([a-z0-9-]+)|var\(--wp--preset--([a-z-]+?)--([a-z0-9-]+)\)")
CLASS_PRESET = re.compile(r"\bhas-([a-z0-9-]+?)-(background-color|color|border-color|font-size|font-family)\b")
GENERIC_CLASS_WORDS = {"text", "link", "background", "border"}
DEFAULT_SLUGS = {  # slugs WordPress itself provides when the matching default* setting is left on
    "color": {"black", "cyan-bluish-gray", "white", "pale-pink", "vivid-red", "luminous-vivid-orange",
              "luminous-vivid-amber", "light-green-cyan", "vivid-green-cyan", "pale-cyan-blue",
              "vivid-cyan-blue", "vivid-purple"},
    "font-size": {"small", "medium", "large", "x-large", "xx-large"},
    "spacing": {"20", "30", "40", "50", "60", "70", "80"},
}
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
LIMITATIONS = {
    "static": "static read of theme and content files; PHP not executed, blocks not rendered or validated in the editor",
    "runtime": "read from a disposable local WordPress via the read-only probe, bound to the theme files and page "
               "content the probe observed; other plugins and production hosting not covered",
}


class ThemeReport(sw_records.Report):
    def emit(self, result, extra=None, code=None):
        return super().emit(result, {"tool": TOOL, "tool_version": TOOL_VERSION, **(extra or {})}, code)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def parse_blocks(text):
    """Return (blocks, problems). blocks: list of (name, attrs, line, depth); problems: (line, message)."""
    blocks, problems, stack = [], [], []
    last = 0
    for m in BLOCK.finditer(text):
        if not stack:
            stray = re.sub(r"<!--.*?-->", "", text[last:m.start()], flags=re.DOTALL).strip()
            if stray:
                problems.append((line_of(text, last + text[last:m.start()].find(stray[:20])),
                                 f"markup outside any block: {stray[:60]!r}"))
        name = m.group("name")
        if "/" not in name:
            name = "core/" + name
        line = line_of(text, m.start())
        attrs = {}
        if m.group("attrs"):
            try:
                attrs = json.loads(m.group("attrs"))
                if not isinstance(attrs, dict):
                    raise ValueError("not an object")
            except ValueError as exc:
                problems.append((line, f"{name}: attributes are not a JSON object ({exc})"))
        if m.group("close"):
            if not stack:
                problems.append((line, f"closing {name} without an opening block"))
            elif stack[-1][0] != name:
                problems.append((line, f"closing {name} but {stack[-1][0]} (line {stack[-1][1]}) is open"))
                if any(s[0] == name for s in stack):
                    while stack and stack[-1][0] != name:
                        stack.pop()
                    stack.pop()
            else:
                stack.pop()
        else:
            blocks.append((name, attrs, line, len(stack)))
            if not m.group("void"):
                stack.append((name, line))
        last = m.end()
    for name, line in stack:
        problems.append((line, f"{name} is never closed"))
    if not stack:
        stray = re.sub(r"<!--.*?-->", "", text[last:], flags=re.DOTALL).strip()
        if stray:
            problems.append((line_of(text, last), f"markup outside any block: {stray[:60]!r}"))
    return blocks, problems


def read_header(text):
    fields = {}
    m = re.search(r"/\*(.*?)\*/", text, re.DOTALL)
    for raw in (m.group(1) if m else "").splitlines():
        raw = raw.strip().lstrip("*").strip()
        if ":" in raw:
            key, value = raw.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


class Checker:
    def __init__(self, theme, content, tokens, probe, wanted, report):
        self.theme = theme
        self.content = content
        self.tokens = tokens
        self.probe = probe
        self.wanted = wanted
        self.report = report
        self.results = {}
        self.paths = {}  # target label -> Path
        self.files = {}  # label -> text
        self.header = {}
        self.theme_json = None
        self.slug = theme.resolve().name
        self.stale = {}  # runtime check_id -> why the probe cannot be bound to this theme/content

    # ----- recording -----
    def add(self, check_id, target, line, severity, evidence, action, kind="defect"):
        if check_id not in self.wanted:
            return
        self.report.add(check_id, f"{target}:{line}" if line else target, severity, evidence, action, kind)
        if severity == "defect":
            self.results[(check_id, target)] = "failed"

    def ran(self, check_id, target):
        if check_id in self.wanted:
            self.results.setdefault((check_id, target), "passed")

    def warn(self, check_id, target, line, evidence, action):
        self.add(check_id, target, line, "warning", evidence, action, kind="convention")

    # ----- loading -----
    def load(self, label, path):
        if path.stat().st_size > MAX_BYTES:
            raise ValueError(f"{path} is larger than {MAX_BYTES} bytes")
        self.paths[label] = path
        self.files[label] = path.read_text(encoding="utf-8")
        return self.files[label]

    def theme_files(self, sub, pattern):
        d = self.theme / sub
        return sorted(d.glob(pattern)) if d.is_dir() else []

    def markup_targets(self):
        """(label, markup text, kind) for every file holding block markup."""
        out = []
        for sub in ("templates", "parts"):
            for p in self.theme_files(sub, "*.html"):
                label = f"{sub}/{p.name}"
                out.append((label, self.load(label, p), sub))
        for p in self.theme_files("patterns", "*.php"):
            label = f"patterns/{p.name}"
            text = self.load(label, p)
            # PHP is blanked (newlines kept) so block parsing and line numbers still line up
            out.append((label, PHP_TAG.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text), "patterns"))
        if self.content:
            for p in sorted(self.content.glob("*.html")):
                label = f"content/{p.name}"
                out.append((label, self.load(label, p), "content"))
        return out

    # ----- checks -----
    def check_header(self):
        cid, label = "wp.theme-header", "style.css"
        path = self.theme / "style.css"
        if not path.is_file():
            self.add(cid, ".", None, "defect", "style.css is missing", "add style.css with the theme header")
            self.paths["."] = self.theme
            return
        self.header = read_header(self.load(label, path))
        for field in HEADER_FIELDS:
            if not self.header.get(field):
                self.add(cid, label, None, "defect", f"header field '{field}' is missing",
                         f"add '{field}:' to the style.css header")
        if not self.header.get("Tested up to"):
            self.warn(cid, label, None, "header field 'Tested up to' is missing", "add the WordPress version it was tested on")
        td = self.header.get("Text Domain")
        if td and td != self.slug:
            self.warn(cid, label, None, f"Text Domain '{td}' differs from the theme folder '{self.slug}'",
                      "use the folder name as the text domain")
        self.ran(cid, label)

    def check_theme_json(self):
        cid, label = "wp.theme-json", "theme.json"
        path = self.theme / "theme.json"
        if not path.is_file():
            self.add(cid, ".", None, "defect", "theme.json is missing", "a block theme needs theme.json")
            self.paths["."] = self.theme
            return
        try:
            self.theme_json = json.loads(self.load(label, path))
        except ValueError as exc:
            self.add(cid, label, None, "defect", f"theme.json does not parse: {exc}", "fix the JSON")
            return
        tj = self.theme_json
        version = tj.get("version")
        if version not in (2, 3):
            self.add(cid, label, None, "defect", f"version {version!r} is not 2 or 3", "set version 3 (WordPress 6.6+) or 2")
        if version == 3 and self.header.get("Requires at least") and version_tuple(self.header["Requires at least"]) < (6, 6):
            self.add(cid, label, None, "defect", "version 3 needs WordPress 6.6 but style.css requires less",
                     "raise 'Requires at least' to 6.6 or use version 2")
        if "$schema" not in tj:
            self.warn(cid, label, None, "no $schema", "add the schema URL for editor validation")
        for part in tj.get("templateParts", []):
            name = part.get("name", "")
            if not (self.theme / "parts" / f"{name}.html").is_file():
                self.add(cid, label, None, "defect", f"templateParts names '{name}' but parts/{name}.html is missing",
                         "add the part file or remove the entry")
            if part.get("area") not in ("header", "footer", "uncategorized", None):
                self.warn(cid, label, None, f"part '{name}' uses area {part.get('area')!r}",
                          "use header, footer or uncategorized unless a plugin registers the area")
        for tpl in tj.get("customTemplates", []):
            name = tpl.get("name", "")
            if not (self.theme / "templates" / f"{name}.html").is_file():
                self.add(cid, label, None, "defect", f"customTemplates names '{name}' but templates/{name}.html is missing",
                         "add the template or remove the entry")
        self.ran(cid, label)

    def presets(self):
        """kind -> set of slugs available (theme presets plus defaults left switched on)."""
        settings = (self.theme_json or {}).get("settings", {})
        found = {k: set() for k in PRESET_KINDS}
        section = {"color": "color", "gradient": "color", "font-size": "typography",
                   "font-family": "typography", "spacing": "spacing"}
        for kind, key in PRESET_KINDS.items():
            for item in settings.get(section[kind], {}).get(key, []) or []:
                if isinstance(item, dict) and item.get("slug"):
                    found[kind].add(str(item["slug"]))
        defaults = {"color": settings.get("color", {}).get("defaultPalette", True),
                    "font-size": settings.get("typography", {}).get("defaultFontSizes", True),
                    "spacing": settings.get("spacing", {}).get("defaultSpacingSizes", True)}
        for kind, on in defaults.items():
            if on is not False:
                found[kind] |= DEFAULT_SLUGS[kind]
        return found

    def check_tokens(self, markup):
        cid = "wp.tokens"
        if self.theme_json is None:
            return
        available = self.presets()
        palette = (self.theme_json.get("settings", {}).get("color", {}).get("palette") or [])
        seen = set()
        for item in palette:
            slug, color = item.get("slug"), str(item.get("color", ""))
            if slug in seen:
                self.add(cid, "theme.json", None, "defect", f"palette slug '{slug}' is defined twice", "keep one")
            seen.add(slug)
            if not HEX.match(color) and not color.startswith(("rgb", "hsl", "var(")):
                self.add(cid, "theme.json", None, "defect", f"palette '{slug}' has colour {color!r}", "use a valid CSS colour")
        sources = [(label, text) for label, text, _ in markup] + [("theme.json", json.dumps(self.theme_json))]
        for label, text in sources:
            used = set()
            for m in VAR_PRESET.finditer(text):
                kind, slug = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
                used.add((kind, slug, line_of(text, m.start())))
            for m in BLOCK.finditer(text):
                try:
                    attrs = json.loads(m.group("attrs")) if m.group("attrs") else {}
                except ValueError:
                    continue
                for key, kind in ATTR_PRESETS.items():
                    if isinstance(attrs.get(key), str):
                        used.add((kind, attrs[key], line_of(text, m.start())))
            for m in CLASS_PRESET.finditer(text):
                if m.group(1) in GENERIC_CLASS_WORDS:
                    continue  # has-text-color, has-link-color etc. mark that a colour is set, not which
                kind = {"background-color": "color", "color": "color", "border-color": "color"}.get(m.group(2), m.group(2))
                used.add((kind, m.group(1), line_of(text, m.start())))
            for kind, slug, line in sorted(used):
                if kind in available and slug not in available[kind]:
                    self.add(cid, label, line, "defect", f"{kind} preset '{slug}' is not defined",
                             f"add '{slug}' to theme.json settings or use an existing {kind} preset")
            self.ran(cid, label)
        if self.tokens:
            self.compare_tokens()

    def compare_tokens(self):
        cid, label = "wp.tokens", "theme.json"
        css = self.tokens.read_text(encoding="utf-8")
        props = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;}]+)", css, re.IGNORECASE))
        settings = self.theme_json.get("settings", {})
        palette = {p.get("slug"): str(p.get("color", "")).lower() for p in settings.get("color", {}).get("palette", [])}
        spacing = {s.get("slug"): str(s.get("size", "")) for s in settings.get("spacing", {}).get("spacingSizes", [])}
        custom = settings.get("custom", {})
        for prop, value in props.items():
            value = value.strip()
            m = re.match(r"--color-(.+)$", prop)
            if m:
                if m.group(1) not in palette:
                    self.add(cid, label, None, "defect", f"design token {prop} has no palette entry '{m.group(1)}'",
                             "add it to settings.color.palette")
                elif palette[m.group(1)] != value.lower():
                    self.add(cid, label, None, "defect",
                             f"palette '{m.group(1)}' is {palette[m.group(1)]} but the design token is {value}",
                             "use the design record's value")
                continue
            m = re.match(r"--space-(\d+)$", prop)
            if m:
                if spacing.get(m.group(1)) != value:
                    self.add(cid, label, None, "defect", f"spacing '{m.group(1)}' is {spacing.get(m.group(1))!r}, token is {value}",
                             "match settings.spacing.spacingSizes to the tokens")
                continue
            if prop == "--radius-1" and str(custom.get("radius")) != value:
                self.add(cid, label, None, "defect", f"custom.radius is {custom.get('radius')!r}, token is {value}",
                         "match settings.custom.radius")
            if prop == "--duration-short" and str(custom.get("duration", {}).get("short")) != value:
                self.add(cid, label, None, "defect",
                         f"custom.duration.short is {custom.get('duration', {}).get('short')!r}, token is {value}",
                         "match settings.custom.duration.short")
        self.ran(cid, label)

    def check_markup(self, markup):
        for label, text, kind in markup:
            blocks, problems = parse_blocks(text)
            for line, message in problems:
                stray = message.startswith("markup outside")
                if stray and kind == "content":
                    continue  # reported by wp.content-editable as classic content
                self.add("wp.block-markup", label, line, "defect", message,
                         "fix the block delimiters; the editor shows broken blocks as invalid")
            self.ran("wp.block-markup", label)
            if kind == "templates":
                self.check_template(label, text, blocks)
            if kind in ("templates", "parts", "patterns"):
                self.check_references(label, blocks)
            if kind == "content":
                self.check_content(label, text, blocks, problems)

    def check_template(self, label, text, blocks):
        cid = "wp.template-structure"
        mains = max(sum(1 for n, a, *_ in blocks if a.get("tagName") == "main"), len(re.findall(r"<main\b", text)))
        if mains != 1:
            self.add(cid, label, None, "defect", f"{mains} main landmarks", "wrap the page body in one group with tagName main")
        name = Path(label).stem
        custom = [t.get("name") for t in (self.theme_json or {}).get("customTemplates", [])
                  if "page" in t.get("postTypes", ["page"])]
        is_page = name in ("page", "singular") or name.startswith("page-") or name in custom
        if is_page and not any(n == "core/post-content" for n, *_ in blocks):
            self.add(cid, label, None, "defect", "page template does not render post content",
                     "add a post-content block so the page's own content shows and stays editable")
        self.ran(cid, label)

    def check_references(self, label, blocks):
        cid = "wp.template-structure"
        pattern_slugs = {self.pattern_slug(p) for p in self.theme_files("patterns", "*.php")}
        for name, attrs, line, _ in blocks:
            if name == "core/template-part":
                slug = attrs.get("slug", "")
                theme = attrs.get("theme")
                if theme and theme != self.slug:
                    self.warn(cid, label, line, f"template part '{slug}' names theme '{theme}'",
                              "drop the theme attribute so the part follows the active theme")
                if not (self.theme / "parts" / f"{slug}.html").is_file():
                    self.add(cid, label, line, "defect", f"template part '{slug}' has no parts/{slug}.html",
                             "add the part or fix the slug")
            elif name == "core/pattern":
                slug = attrs.get("slug", "")
                if slug.startswith(f"{self.slug}/") and slug not in pattern_slugs:
                    self.add(cid, label, line, "defect", f"pattern '{slug}' is not defined in patterns/",
                             "add the pattern file or fix the slug")
                elif not slug.startswith(f"{self.slug}/"):
                    self.warn(cid, label, line, f"pattern '{slug}' comes from outside the theme",
                              "confirm the plugin or core that registers it is part of the project")
        self.ran(cid, label)

    def pattern_slug(self, path):
        return read_header(path.read_text(encoding="utf-8")).get("Slug", "")

    def check_site_structure(self):
        cid = "wp.template-structure"
        if not (self.theme / "templates" / "index.html").is_file():
            self.add(cid, ".", None, "defect", "templates/index.html is missing", "a block theme needs an index template")
        if not (self.theme / "templates" / "404.html").is_file():
            self.warn(cid, ".", None, "no 404 template; WordPress falls back to index",
                      "add templates/404.html when the page contract has a not-found page")
        self.paths["."] = self.theme
        self.ran(cid, ".")

    def check_patterns(self):
        cid = "wp.patterns"
        seen = {}
        for p in self.theme_files("patterns", "*.php"):
            label = f"patterns/{p.name}"
            text = self.files.get(label) or self.load(label, p)
            fields = read_header(text)
            if not text.lstrip().startswith("<?php"):
                self.add(cid, label, 1, "defect", "pattern file does not start with <?php and a header comment",
                         "start with <?php and the /** Title: … Slug: … */ header")
            for field in ("Title", "Slug"):
                if not fields.get(field):
                    self.add(cid, label, None, "defect", f"pattern header has no {field}",
                             f"add '{field}:' to the header; WordPress skips patterns without it")
            slug = fields.get("Slug", "")
            if slug and not slug.startswith(f"{self.slug}/"):
                self.add(cid, label, None, "defect", f"slug '{slug}' is outside the '{self.slug}/' namespace",
                         f"prefix it with '{self.slug}/'")
            if slug in seen:
                self.add(cid, label, None, "defect", f"slug '{slug}' is also used by {seen[slug]}", "make slugs unique")
            seen.setdefault(slug, label)
            if not fields.get("Categories") and fields.get("Inserter", "").lower() not in ("no", "false"):
                self.warn(cid, label, None, "inserter pattern has no Categories", "add a category so editors can find it")
            self.ran(cid, label)

    def check_content(self, label, text, blocks, problems):
        cid = "wp.content-editable"
        for line, message in problems:
            if message.startswith("markup outside"):
                self.add(cid, label, line, "defect", message.replace("markup outside any block", "classic (non-block) markup"),
                         "convert it to blocks; classic chunks open as a single Classic block")
        for name, attrs, line, depth in blocks:
            if name == "core/freeform":
                self.add(cid, label, line, "defect", "Classic block", "convert it to blocks")
            elif name == "core/html":
                self.warn(cid, label, line, "Custom HTML block: editors can change it only as code",
                          "replace it with blocks, or a plugin block for forms, when one is chosen")
            elif name == "core/shortcode":
                self.warn(cid, label, line, "shortcode block: output depends on a plugin",
                          "confirm the plugin is part of the project")
        if not blocks:
            self.add(cid, label, None, "defect", "no blocks", "write the page content as blocks")
        self.ran(cid, label)

    def check_content_index(self):
        cid = "wp.content-editable"
        index = self.content / "pages.json"
        if not index.is_file():
            return
        data = json.loads(self.load("content/pages.json", index))
        templates = {p.stem for p in self.theme_files("templates", "*.html")}
        for page in data.get("pages", []):
            f = page.get("file", "")
            if f and not (self.content / f).is_file():
                self.add(cid, "content/pages.json", None, "defect", f"page '{page.get('slug')}' names missing {f}", "add the file")
            tpl = page.get("template") or ""
            if tpl and tpl not in templates:
                self.add(cid, "content/pages.json", None, "defect", f"page '{page.get('slug')}' uses missing template '{tpl}'",
                         "add the template or fix the name")
        self.ran(cid, "content/pages.json")

    def check_assets(self):
        cid = "wp.assets"
        refs = []
        fn = self.theme / "functions.php"
        if fn.is_file():
            text = self.files.get("functions.php") or self.load("functions.php", fn)
            for rx in (r"get_theme_file_(?:uri|path)\(\s*['\"]([^'\"]+)['\"]",
                       r"get_(?:template|stylesheet)_directory_(?:uri|path)?\(\)\s*\.\s*['\"]/?([^'\"]+)['\"]",
                       r"add_editor_style\(\s*['\"]([^'\"]+)['\"]"):
                for m in re.finditer(rx, text):
                    refs.append(("functions.php", line_of(text, m.start()), m.group(1)))
            for m in re.finditer(r"wp_(?:enqueue|register)_(?:script|style)\([^;]*?['\"](https?:)?//([^/'\"]+)", text):
                self.warn(cid, "functions.php", line_of(text, m.start()), f"loads a file from {m.group(2)}",
                          "bundle it with the theme or record the third-party dependency and its privacy impact")
        if self.theme_json:
            text = json.dumps(self.theme_json)
            for m in re.finditer(r'"file:\./([^"]+)"', text):
                refs.append(("theme.json", None, m.group(1)))
        for label, line, ref in refs:
            ref = ref.split("?")[0].lstrip("/")
            if not (self.theme / ref).is_file():
                self.add(cid, label, line, "defect", f"{ref} does not exist in the theme", "add the file or fix the path")
            self.ran(cid, label)
        if not (self.theme / "screenshot.png").is_file():
            self.warn(cid, ".", None, "no screenshot.png", "add a 1200×900 screenshot before distribution")
            self.paths["."] = self.theme
        self.ran(cid, ".")
        self.paths["."] = self.theme

    def check_php(self):
        cid = "wp.php-safety"
        for p in sorted(self.theme.rglob("*.php")):
            if "vendor" in p.parts or "node_modules" in p.parts:
                continue
            label = p.relative_to(self.theme).as_posix()
            text = self.files.get(label) or self.load(label, p)
            is_pattern = label.startswith("patterns/")
            for no, line in enumerate(text.splitlines(), 1):
                code = re.sub(r"//.*$|#.*$", "", line)
                if re.search(r"\beval\s*\(", code):
                    self.add(cid, label, no, "defect", "eval()", "remove it; eval runs arbitrary code")
                if re.search(r"\$_(GET|POST|REQUEST|COOKIE|SERVER|FILES)\b", code) and not re.search(
                        r"sanitize_|absint|intval|wp_unslash|esc_|isset|empty\(|wp_verify_nonce|check_admin_referer|filter_input|in_array", code):
                    self.add(cid, label, no, "defect", "request input used without sanitising or checking it",
                             "unslash and sanitise it for its type, and verify a nonce for state changes")
                if re.search(r"\$wpdb->(query|get_var|get_results|get_row|get_col)\s*\(", code) and "$" in code.split("(", 1)[1] \
                        and "prepare" not in code:
                    self.add(cid, label, no, "defect", "database query built from variables without $wpdb->prepare",
                             "use $wpdb->prepare with placeholders")
                if re.search(r"(echo|print|<\?=)\s*\$", code) and not re.search(r"esc_|wp_kses|absint|intval|wp_json_encode", code):
                    self.warn(cid, label, no, "variable printed without escaping",
                              "escape for the output context (esc_html, esc_attr, esc_url) unless it is trusted markup")
                if re.search(r"(?<![\w])_e\s*\(|echo\s+__\s*\(", code):
                    self.warn(cid, label, no, "translated string printed without escaping",
                              "use esc_html_e / esc_html__ (translations are external input)")
                if re.search(r"\bbase64_decode\s*\(", code):
                    self.warn(cid, label, no, "base64_decode()", "say why encoded content is needed; a theme rarely needs it")
                if re.search(r"wp_remote_(get|post|request)|curl_exec|file_get_contents\(\s*['\"]https?:", code):
                    self.warn(cid, label, no, "makes a network request",
                              "make it optional, cache it, and record the external service")
                if re.search(r"(password|passwd|api[_-]?key|secret|token)['\"]?\s*(=>|=)\s*['\"][^'\"\s]{4,}['\"]", code, re.IGNORECASE):
                    self.add(cid, label, no, "defect", "credential-like value in source",
                             "remove it; read secrets from configuration outside the theme")
            if not is_pattern and label != "index.php" and "ABSPATH" not in text and re.search(r"add_(action|filter)\s*\(", text) is None:
                self.warn(cid, label, None, "no ABSPATH guard and no hook registration",
                          "add `defined( 'ABSPATH' ) || exit;` if the file can run code when requested directly")
            self.ran(cid, label)

    # ----- runtime (probe) -----
    def snapshot_problems(self):
        """{runtime check_id: reason} for results that cannot be bound to the theme and content checked."""
        probe = self.probe
        theme = probe.get("theme") or {}
        observed = theme.get("files")
        version = str(probe.get("probe", ""))
        if version not in ("sitewright-wp-probe 2", "sitewright-wp-probe 3") or not isinstance(observed, dict):
            reason = (f"the probe ({version or 'unknown version'}) does not identify the theme files it observed; "
                      "probe again with the current scripts/wp-probe")
            return dict.fromkeys(RUNTIME_CHECKS, reason)
        if theme.get("files_truncated"):
            return dict.fromkeys(RUNTIME_CHECKS, "the probe listed only part of the theme's files, so the snapshot "
                                                 "it observed cannot be compared")
        local = {}
        for dirpath, dirnames, filenames in os.walk(self.theme, followlinks=False):
            dirnames[:] = sorted(d for d in dirnames if d not in (".git", "node_modules", "__pycache__"))
            for name in filenames:
                p = Path(dirpath, name)
                local[p.relative_to(self.theme).as_posix()] = "link" if p.is_symlink() else sw_records.fingerprint(p)
        differ = sorted(k for k in set(local) | set(observed) if local.get(k) != observed.get(k))
        if differ:
            return dict.fromkeys(RUNTIME_CHECKS, f"the probe observed a different theme snapshot ({len(differ)} file(s) "
                                                 f"differ, e.g. {', '.join(differ[:3])}); mount this theme, probe again "
                                                 "and re-run")
        if not self.content or not (self.content / "pages.json").is_file():
            return {"wp.runtime-content": "no --content with pages.json was given, so the pages the probe observed "
                                          "cannot be bound to project files"}
        expected = json.loads((self.content / "pages.json").read_text(encoding="utf-8")).get("pages", [])
        by_slug = {p.get("slug"): p for p in probe.get("pages", [])}
        differ = []
        for exp in expected:
            got, name = by_slug.get(exp.get("slug")), Path(str(exp.get("file") or "")).name
            source = self.content / name
            if got is None:
                continue  # an unpublished page is a wp.runtime-content defect, not a snapshot mismatch
            if not name or not source.is_file() or got.get("content_sha256") != sw_records.fingerprint(source):
                differ.append(str(exp.get("slug")))
        if differ:
            return {"wp.runtime-content": f"the probe observed different stored content for {', '.join(differ)} than "
                                          "the --content files; load the current content, probe again and re-run"}
        return {}

    def check_runtime(self):
        problems = self.snapshot_problems()
        label = "probe"
        self.paths[label] = self.theme
        self.stale = {cid: reason for cid, reason in problems.items() if cid in self.wanted}
        for cid, reason in self.stale.items():
            self.results[(cid, label)] = "stale"
            self.report.diagnostics.append(f"{cid} stale: {reason}")
        if set(RUNTIME_CHECKS) <= set(problems):
            return  # the probe saw another snapshot: its findings are not about this theme
        probe = self.probe
        theme = probe.get("theme") or {}
        cid = "wp.runtime-theme"
        if theme.get("stylesheet") != self.slug:
            self.add(cid, label, None, "defect", f"active theme is {theme.get('stylesheet')!r}, not {self.slug!r}",
                     "activate the theme in the test site")
        if theme.get("is_block_theme") is not True:
            self.add(cid, label, None, "defect", "WordPress does not treat the theme as a block theme",
                     "check templates/index.html and theme.json")
        if theme.get("errors"):
            self.add(cid, label, None, "defect", f"theme errors: {theme['errors']}", "fix the reported theme errors")
        if self.header.get("Version") and theme.get("version") != self.header.get("Version"):
            self.add(cid, label, None, "defect",
                     f"runtime theme version {theme.get('version')!r} differs from style.css {self.header.get('Version')!r}",
                     "the probe ran on a different copy; mount this theme and probe again")
        self.ran(cid, label)
        cid = "wp.runtime-templates"
        resolved = {t.get("slug"): t for t in probe.get("templates", [])}
        for p in self.theme_files("templates", "*.html"):
            t = resolved.get(p.stem)
            if not t:
                self.add(cid, label, None, "defect", f"template '{p.stem}' not registered", "check the file name and markup")
            elif t.get("source") != "theme":
                self.add(cid, label, None, "defect", f"template '{p.stem}' comes from {t.get('source')!r}, not the theme file",
                         "a saved database copy overrides the file; reset it in the Site Editor or note the override")
        parts = {t.get("slug"): t for t in probe.get("parts", [])}
        for p in self.theme_files("parts", "*.html"):
            t = parts.get(p.stem)
            if not t or t.get("source") != "theme":
                self.add(cid, label, None, "defect", f"part '{p.stem}' not resolved from the theme file",
                         "check the part file, or reset a database override")
        patterns = {t.get("slug") for t in probe.get("patterns", [])}
        for p in self.theme_files("patterns", "*.php"):
            slug = self.pattern_slug(p)
            if slug and slug not in patterns:
                self.add(cid, label, None, "defect", f"pattern '{slug}' not registered at runtime",
                         "check the header fields; WordPress skips invalid pattern files")
        self.ran(cid, label)
        cid = "wp.runtime-content"
        if cid in problems:
            return
        pages = probe.get("pages", [])
        if not pages:
            self.add(cid, label, None, "defect", "no published pages", "load the content into the test site")
        for page in pages:
            slug = page.get("slug")
            if not page.get("has_blocks"):
                self.add(cid, label, None, "defect", f"page '{slug}' has no blocks", "store the content as blocks")
            if page.get("freeform"):
                self.add(cid, label, None, "defect", f"page '{slug}' has classic chunks", "convert them to blocks")
            if page.get("unregistered"):
                self.add(cid, label, None, "defect", f"page '{slug}' uses unregistered blocks {page['unregistered']}",
                         "install the providing plugin or replace the blocks")
            if (page.get("block_counts") or {}).get("core/html"):
                self.warn(cid, label, None, f"page '{slug}' has {page['block_counts']['core/html']} Custom HTML block(s)",
                          "editable only as code; see wp.content-editable")
        if self.content and (self.content / "pages.json").is_file():
            expected = json.loads((self.content / "pages.json").read_text(encoding="utf-8")).get("pages", [])
            by_slug = {p.get("slug"): p for p in pages}
            for exp in expected:
                got = by_slug.get(exp.get("slug"))
                if not got:
                    self.add(cid, label, None, "defect", f"page '{exp.get('slug')}' is not published", "load it")
                elif (got.get("template") or "") not in ((exp.get("template") or ""), "default") \
                        and (exp.get("template") or "") != (got.get("template") or ""):
                    self.add(cid, label, None, "defect",
                             f"page '{exp.get('slug')}' uses template {got.get('template')!r}, expected {exp.get('template')!r}",
                             "set the page template")
        self.ran(cid, label)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sw_wp_theme_check.py", description=__doc__.splitlines()[0])
    parser.add_argument("theme")
    parser.add_argument("--content", help="directory of page content in block markup (*.html, optional pages.json)")
    parser.add_argument("--tokens", help="CSS file declaring the design tokens as custom properties")
    parser.add_argument("--probe", help="JSON saved from scripts/wp-probe on a local test site")
    parser.add_argument("--checks", help="comma-separated check IDs (default: static checks, plus runtime with --probe)")
    parser.add_argument("--record", help="append one evidence record per (check, target) to this verification file")
    parser.add_argument("--root", help="project root for recorded targets (with --record)")
    parser.add_argument("--evidence-out", help="also write this report to PATH (required with --record)")
    parser.add_argument("--require", action="store_true", help="with --record: add each check to required_checks")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    started = time.monotonic()
    theme = Path(args.theme)
    report = ThemeReport(args.theme)
    try:
        wanted = set(STATIC_CHECKS) | (set(RUNTIME_CHECKS) if args.probe else set())
        if args.checks:
            wanted = {c.strip() for c in args.checks.split(",") if c.strip()}
            unknown = wanted - set(ALL_CHECKS)
            if unknown:
                report.diagnostics.append(f"unknown check IDs: {', '.join(sorted(unknown))}")
                return report.emit("error")
            if wanted & set(RUNTIME_CHECKS) and not args.probe:
                report.diagnostics.append("runtime checks need --probe")
                return report.emit("error")
        if args.record and not args.evidence_out:
            report.diagnostics.append("--record needs --evidence-out (evidence_path must name the saved output)")
            return report.emit("error")
        if args.record:
            root = Path(args.root) if args.root else sw_records.default_root(args.record)
            clash = sw_records.cited_evidence_problem(args.record, root, args.evidence_out, TOOL)
            if clash:
                report.diagnostics.append(clash)
                return report.emit("error")
        if not theme.is_dir():
            report.diagnostics.append(f"theme directory not found: {args.theme}")
            return report.emit("error")
        content = Path(args.content) if args.content else None
        if content and not content.is_dir():
            report.diagnostics.append(f"content directory not found: {args.content}")
            return report.emit("error")
        tokens = Path(args.tokens) if args.tokens else None
        if tokens and not tokens.is_file():
            report.diagnostics.append(f"tokens file not found: {args.tokens}")
            return report.emit("error")
        probe = None
        if args.probe:
            probe = json.loads(Path(args.probe).read_text(encoding="utf-8"))
            if not isinstance(probe, dict) or not str(probe.get("probe", "")).startswith("sitewright-wp-probe"):
                report.diagnostics.append("--probe is not output of scripts/wp-probe")
                return report.emit("error")
        checker = Checker(theme, content, tokens, probe, wanted, report)
        checker.check_header()
        checker.check_theme_json()
        markup = checker.markup_targets()
        checker.check_markup(markup)
        checker.check_tokens(markup)
        checker.check_site_structure()
        checker.check_patterns()
        if content:
            checker.check_content_index()
        checker.check_assets()
        checker.check_php()
        if probe is not None:
            checker.check_runtime()
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        report.diagnostics.append(f"{type(exc).__name__}: {exc}")
        return report.emit("error")

    accepted = sw_records.accept_findings(report, lambda loc: checker.paths.get(loc, checker.theme / loc),
                                          args.record, None, args.root)
    checks = [{"check_id": c, "target": t, "result": r} for (c, t), r in sorted(checker.results.items())]
    result = "failed" if any(f["severity"] == "defect" for f in report.findings) else \
        "stale" if checker.stale else "passed"
    payload = {"checks": checks, "php_version": (probe or {}).get("php_version"), "wp_version": (probe or {}).get("wp_version")}
    if probe is not None:
        payload["probe"] = {"path": str(args.probe), "version": probe.get("probe"),
                            "fingerprint": sw_records.fingerprint(args.probe)}
    if accepted is not None:
        payload["accepted"] = accepted
    if args.evidence_out:
        out = {"tool": TOOL, "tool_version": TOOL_VERSION, "target": str(theme), "result": result,
               "findings": report.findings, "diagnostics": report.diagnostics, **payload,
               "timestamp": sw_records.now_iso(), "duration_ms": int((time.monotonic() - started) * 1000)}
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        sw_records.write_json_atomic(args.evidence_out, out)
    if args.record:
        code = record_all(args, checker, checks, report)
        if code:
            return code
        payload["evidence_kept"] = getattr(args, "evidence_kept", True)
    return report.emit(result, payload)


def record_all(args, checker, checks, report):
    root = Path(args.root) if args.root else sw_records.default_root(args.record)
    evidence = Path(args.evidence_out)
    try:
        evidence_rel = evidence.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        evidence_rel = str(evidence)
    covered = []
    for c in checks:
        target_path = checker.paths.get(c["target"], checker.theme / c["target"])
        try:
            target_rel = target_path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            report.diagnostics.append(f"target {target_path} is outside the project root {root}")
            return report.emit("error")
        found = [f["evidence"] for f in report.findings
                 if f["check_id"] == c["check_id"] and f["severity"] == "defect"
                 and f["location"].split(":")[0] == c["target"]]
        kind = "runtime" if c["check_id"] in RUNTIME_CHECKS else "static"
        finding = checker.stale.get(c["check_id"]) if c["result"] == "stale" else "; ".join(found)
        argv = ["record", args.record, "--root", str(root), "--check-id", c["check_id"],
                "--target", target_rel, "--result", c["result"], "--method", "automated",
                "--tool-and-version", f"{TOOL} {TOOL_VERSION}", "--evidence-path", evidence_rel,
                "--finding", (finding or "no defects found by the theme rules")[:400],
                "--limitations", LIMITATIONS[kind]]
        if c["check_id"] == "wp.runtime-content" and checker.content is not None:
            argv += ["--input", str(checker.content)]
        if args.require:
            argv.append("--require")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = sw_records.main(argv)
        if code != 0:
            report.diagnostics.append(f"recording {c['check_id']} for {target_rel} failed: {buf.getvalue()[:300]}")
            return report.emit("error")
        covered.append((c["check_id"], target_rel))
    if checks:
        sw_records.update_recurring(args.record, root, report.findings,
                                    lambda loc: checker.paths.get(loc, checker.theme / loc), covered)
        args.evidence_kept = sw_records.keep_cited_evidence(args.record, evidence_rel, evidence)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # report, never pass silently
        r = ThemeReport("")
        r.diagnostics.append(f"{type(exc).__name__}: {exc}")
        sys.exit(r.emit("error"))
