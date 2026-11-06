#!/usr/bin/env python3
"""Sitewright design, style and asset checks (stdlib only, read-only except --record/--evidence-out).

Reads built CSS (a site directory, or a WordPress theme with its theme.json) and the project records
(docs/website/ or the project's canonical records), and reports:

  design.token-drift   every token named in the design record's `semantic_tokens` is defined by the build
                       (a CSS custom property, or a theme.json preset or custom value); a value the record gives
                       matches the built value; root-level custom properties the record doesn't name are a warning
  design.raw-literals  colour literals written straight into declarations instead of tokens (warning per
                       declaration), plus spacing lengths (margin, padding, gap, inset) and durations
                       (transition, animation) written as literals (one warning per stylesheet and kind)
  style.contrast       text and background colours that resolve within one rule meet WCAG 2.2 contrast (4.5:1,
                       or 3:1 for large text) in the default scheme and every colour scheme the CSS defines
                       (basis "declared", a defect); pairings inferred from descendant selectors or the page
                       ground (basis "inferred") are warnings, one per colour pair and scheme with its selectors
  style.leading        running text line height below 1.2 is a defect, below 1.4 a warning; headings below 0.95 a warning
  style.tracking       judged by role. Labels (uppercase or small caps at 16px or less) are held to the design
                       record's `label_tracking_max` (default 0.25em; above it is a warning). Running text (p, li,
                       dd, blockquote, td, ... without a label style) above 0.12em is a defect, above 0.05em or
                       below -0.03em a warning. Uncertain roles (span, strong, dt, th, ::before, ...) above 0.12em
                       get a review warning, never a defect. Selectors with no element type in their last part
                       (.intro, #lead, [data-x]) and large uppercase rules without a tag are unclassified:
                       above 0.05em they get a review warning, the record's limitations name them and the
                       payload lists them in tracking_unclassified, so browser review (visual-measure.js
                       `tracking`) settles the role. They are never a defect and never a silent pass
  style.justify        justified text without hyphenation (warning)
  style.padding        buttons and fields with a fill or border and less than 4px block or 8px inline padding (warning)
  layout.grid-items    a grid container whose own ::before/::after has content and stays in flow: the generated
                       box becomes a grid item and takes a cell (review warning; confirm with visual.measure).
                       Flex containers are left out: a generated icon or rule in a flex row is usually intended
  layout.spacing-reset a later rule sets a heading's top margin to 0 after an earlier rule gave it one (review
                       warning; source order only, so cascade layers declared out of order are not modelled)
  assets.rights        permitted use is known for every asset still in use (with --release, unknown is a defect);
                       attribution is filled when the permitted use requires it; images the build references
                       appear in the assets record (with --release, an unrecorded image is a defect)
  assets.local-path    local_path is a project-relative path, not a URL, an absolute path or a path outside the
                       project; it exists for supplied and approved assets
  assets.final         with --release, no asset is still a placeholder, needed or missing (skipped otherwise)

WordPress themes: a record token maps to theme.json by exact name, by kind prefix plus slug (--color-ink ->
--wp--preset--color--ink, --space-2 -> --wp--preset--spacing--2, --font-size-body, --font-family-body), or by its
tail (--radius -> --wp--custom--radius). A one-step scale written without its number (--radius-1 recorded,
custom.radius built, no --radius-2) is accepted with a warning.

--record writes one evidence record per check and target with sw_records.py; --require adds the checks
that ran to required_checks. A skipped check (assets.final without --release) is recorded as optional
with its reason, never as required. Records of the release-sensitive checks (assets.rights,
assets.local-path, assets.final) carry mode production with --release and mockup without it, so a
non-release run can never replace production evidence; the others judge the same in both modes and
carry no mode unless --mode is given. --exclude PATH (repeatable, relative to
--root) is passed to folder targets that contain it.

What it does not establish: rendered contrast (stacked backgrounds, images, gradients, opacity, inheritance
across components and runtime theme switches need browser.contrast), how text actually wraps, whether a
licence is genuine, or that an image suits its placement. Roles come from the last selector compound's
element and the merged declarations of that selector; class-only selectors without a label style are not
classified, and text length is not known statically, so a long uppercase passage reads as a label.

Output: one JSON object on stdout (website-verify/references/evidence-contract.md).
Exit: 0 passed or skipped, 1 failed, 2 error or unavailable.
"""
import argparse
import bisect
import colorsys
import contextlib
import io
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_records  # noqa: E402  (same directory; shared report, record parsing and evidence logic)

TOOL = "sw_design_check"
TOOL_VERSION = "4"
STYLE_CHECKS = ("style.contrast", "style.leading", "style.tracking", "style.justify", "style.padding")
LAYOUT_CHECKS = ("layout.grid-items", "layout.spacing-reset")
BUILD_CHECKS = ("design.raw-literals",) + STYLE_CHECKS + LAYOUT_CHECKS
ASSET_CHECKS = ("assets.rights", "assets.local-path", "assets.final")
ALL_CHECKS = ("design.token-drift",) + BUILD_CHECKS + ASSET_CHECKS
MAX_BYTES = 5_000_000
MAX_FINDINGS_PER_TARGET = 25
SKIP_DIRS = {"node_modules", ".git", "__pycache__"}

TEXT_TAGS = {"p", "li", "dd", "dt", "blockquote", "td", "th", "figcaption", "body", "html", "article", "main",
             "section", "caption", "address", "label", "small", "span", "a", "em", "strong", "q", "cite", "summary"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
RUNNING_TAGS = {"p", "li", "dd", "blockquote", "td", "figcaption", "body", "html", "article", "main", "section",
                "caption", "address", "summary"}
UNCERTAIN_TAGS = TEXT_TAGS - RUNNING_TAGS      # span, a, em, strong, small, label, cite, q, dt, th
LABEL_TRACKING_MAX = 0.25                      # em; the design record's label_tracking_max overrides it
GENERATED = re.compile(r"::?(?:before|after)\b")
MAX_LISTED = 8
LARGE_BY_DEFAULT = {"h1", "h2", "h3"}       # UA sizes 2em, 1.5em, 1.17em bold: all "large" under WCAG
FIELD_TAGS = {"button", "input", "select", "textarea"}
CONTROL_CLASS = re.compile(r"\.(?:btn|button|cta)(?:[-_][\w-]*)?\b|\[type=['\"]?(?:submit|button|reset)|"
                           r"\[role=['\"]?button", re.IGNORECASE)
NOT_PADDED = re.compile(r"\[type=['\"]?(?:checkbox|radio|range|color|file|hidden)", re.IGNORECASE)
COLOUR_PROP = re.compile(r"color|background|border|outline|fill|stroke|caret|column-rule|text-decoration")
NAMED = {"black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 128, 0),
         "blue": (0, 0, 255), "gray": (128, 128, 128), "grey": (128, 128, 128), "silver": (192, 192, 192),
         "maroon": (128, 0, 0), "navy": (0, 0, 128), "purple": (128, 0, 128), "teal": (0, 128, 128),
         "olive": (128, 128, 0), "orange": (255, 165, 0), "yellow": (255, 255, 0), "lime": (0, 255, 0),
         "aqua": (0, 255, 255), "cyan": (0, 255, 255), "fuchsia": (255, 0, 255), "magenta": (255, 0, 255)}
SPACING_PROP = re.compile(r"^(?:margin|padding|gap|row-gap|column-gap|inset|scroll-margin|scroll-padding)(?:-|$)")
DURATION_PROP = re.compile(r"^(?:transition|animation)(?:-duration|-delay)?$")
LENGTH_LITERAL = re.compile(r"(?<![\w.#-])(-?(?:\d+\.?\d*|\.\d+))(px|rem|em)\b", re.IGNORECASE)
DURATION_LITERAL = re.compile(r"(?<![\w.#-])((?:\d+\.?\d*|\.\d+))(ms|s)\b", re.IGNORECASE)
HEX_LITERAL = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
FUNC_LITERAL = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^()]*\)", re.IGNORECASE)
NAMED_LITERAL = re.compile(r"(?<![\w-])(" + "|".join(NAMED) + r")(?![\w-])", re.IGNORECASE)
TOKEN_NAME = re.compile(r"(?<![\w(-])--([A-Za-z][\w-]*)(?:\.\.(\d+))?")
CSS_FUNCTION = re.compile(r"^(?:clamp|calc|min|max|var|cubic-bezier|steps|rgba?|hsla?|oklch|oklab|lab|lch|"
                          r"color-mix|linear-gradient|radial-gradient)\(", re.IGNORECASE)
GENERIC_FAMILY = re.compile(r"\b(?:serif|sans-serif|monospace|system-ui|cursive|ui-\w+)\b")
IMAGE_EXT = re.compile(r"\.(?:png|jpe?g|gif|webp|avif|svg|ico)(?:[?#].*)?$", re.IGNORECASE)
REMOTE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:)?//", re.IGNORECASE)
UNKNOWN_USE = re.compile(r"^\s*(?:unknown|unclear|tbd|todo|\?)?\s*(?:[:(\u2014-].*)?$", re.IGNORECASE)
EMPTY_FIELD = re.compile(r"^\s*(?:n/?a|none|-|unknown|tbd|todo)?\s*(?:[:(\u2014].*)?$", re.IGNORECASE)
NEEDS_ATTRIBUTION = re.compile(r"\bcc[- ]?by\b|attribution|credit required|must credit", re.IGNORECASE)
NOT_FINAL = ("placeholder", "needed", "missing")
ALIAS_KINDS = (("font-family", "font-family"), ("font-size", "font-size"), ("colour", "color"),
               ("color", "color"), ("spacing", "spacing"), ("space", "spacing"), ("fs", "font-size"),
               ("font", "font-family"))
PRESET_SOURCES = (("color", "palette", "color"), ("font-size", "fontSizes", "size"),
                  ("font-family", "fontFamilies", "fontFamily"), ("spacing", "spacingSizes", "size"))


class DesignReport(sw_records.Report):
    def emit(self, result, extra=None, code=None):
        return super().emit(result, {"tool": TOOL, "tool_version": TOOL_VERSION, **(extra or {})}, code)


# ---------- CSS values ----------

def match_paren(text, open_idx):
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def scale_key(text):
    """A single length (px, rem as 16px, em kept apart) or duration (ms) as a comparable key, else None."""
    m = re.fullmatch(r"\s*(-?(?:\d+\.?\d*|\.\d+))(px|rem|em|ms|s)\s*", text or "", re.IGNORECASE)
    if not m:
        return None
    number, unit = float(m.group(1)), m.group(2).lower()
    if number == 0:
        return None
    if unit == "rem":
        number, unit = number * 16, "px"
    elif unit == "s":
        number, unit = number * 1000, "ms"
    return (round(number, 3), unit)


def split_top(text, seps=","):
    """Split at separators outside parentheses, brackets and quotes."""
    parts, depth, quote, start = [], 0, None, 0
    for i, c in enumerate(text):
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "([":
            depth += 1
        elif c in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and c in seps:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts if p.strip()]


def wp_value(value):
    """theme.json shorthand `var:preset|color|ink` -> `var(--wp--preset--color--ink)`."""
    return re.sub(r"var:(preset|custom)\|([\w|-]+)",
                  lambda m: "var(--wp--" + m.group(1) + "--" + m.group(2).replace("|", "--") + ")", value)


def resolve(value, variables, depth=0):
    """Substitute var() references; None when a reference can't be resolved."""
    if value is None or depth > 8:
        return None
    out, i = [], 0
    while True:
        j = value.find("var(", i)
        if j < 0:
            out.append(value[i:])
            break
        k = match_paren(value, j + 3)
        if k < 0:
            return None
        out.append(value[i:j])
        name, _, fallback = value[j + 4:k].partition(",")
        rep = variables.get(name.strip())
        if rep is None:
            rep = fallback.strip() or None
        rep = resolve(rep, variables, depth + 1)
        if rep is None:
            return None
        out.append(rep)
        i = k + 1
    return "".join(out).strip()


def parse_colour(value):
    """(r, g, b, alpha) for hex, rgb(), hsl() and basic named colours; None otherwise."""
    v = (value or "").strip().lower()
    if v == "transparent":
        return (0, 0, 0, 0.0)
    if v in NAMED:
        return (*NAMED[v], 1.0)
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        alpha = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
    m = re.fullmatch(r"(rgba?|hsla?)\((.*)\)", v)
    if not m:
        return None
    parts = [p for p in re.split(r"[\s,/]+", m.group(2).strip()) if p]
    if len(parts) not in (3, 4):
        return None
    try:
        alpha = 1.0
        if len(parts) == 4:
            alpha = float(parts[3][:-1]) / 100 if parts[3].endswith("%") else float(parts[3])
        if m.group(1).startswith("rgb"):
            rgb = [float(p[:-1]) * 2.55 if p.endswith("%") else float(p) for p in parts[:3]]
        else:
            hue = float(re.sub(r"deg$", "", parts[0])) % 360
            sat, light = float(parts[1].rstrip("%")) / 100, float(parts[2].rstrip("%")) / 100
            rgb = [c * 255 for c in colorsys.hls_to_rgb(hue / 360, light, sat)]
    except ValueError:
        return None
    return (*[min(255.0, max(0.0, c)) for c in rgb], min(1.0, max(0.0, alpha)))


def luminance(c):
    def channel(x):
        x /= 255
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(c[0]) + 0.7152 * channel(c[1]) + 0.0722 * channel(c[2])


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def over(fg, bg):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def show(c):
    return "#%02x%02x%02x" % tuple(round(x) for x in c[:3]) + ("" if c[3] >= 1 else f" at {c[3]:.2f} alpha")


def length_px(value, font_px=16.0):
    """Pixels for px/rem/em/% lengths (rem and em at 16px unless font_px is given); clamp() gives its minimum."""
    v = (value or "").strip().lower()
    m = re.fullmatch(r"clamp\((.*)\)", v)
    if m:
        args = split_top(m.group(1))
        return length_px(args[0], font_px) if args else None
    m = re.fullmatch(r"(-?\d*\.?\d+)(px|rem|em|%)?", v)
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2)
    if unit is None:
        return n if n == 0 else None
    return {"px": n, "rem": n * 16, "em": n * font_px, "%": n / 100 * font_px}[unit]


def time_ms(value):
    m = re.fullmatch(r"(-?\d*\.?\d+)(ms|s)", (value or "").strip().lower())
    return None if not m else float(m.group(1)) * (1 if m.group(2) == "ms" else 1000)


def normalise(value):
    v = re.sub(r"\s+", " ", value.strip().lower()).replace('"', "'")
    return re.sub(r"\s*([,()/])\s*", r"\1", v)


def same_value(a, b):
    ca, cb = parse_colour(a), parse_colour(b)
    if ca and cb:
        return all(abs(x - y) <= 1 for x, y in zip(ca[:3], cb[:3])) and abs(ca[3] - cb[3]) < 0.01
    for conv in (length_px, time_ms):
        la, lb = conv(a), conv(b)
        if la is not None and lb is not None:
            return abs(la - lb) < 0.01
    return normalise(a) == normalise(b)


def looks_like_css(value):
    v = value.strip()
    return bool(parse_colour(v) or length_px(v) is not None or time_ms(v) is not None
                or re.fullmatch(r"-?\d*\.?\d+", v) or CSS_FUNCTION.match(v) or GENERIC_FAMILY.search(v))


# ---------- CSS rules ----------

def strip_comments(text):
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.DOTALL)


def parse_css(text, target, base_line=1):
    """Style rules as dicts {selector, decls {prop: (value, line)}, context, line, target}."""
    text = strip_comments(text)
    newlines = [i for i, c in enumerate(text) if c == "\n"]
    rules = []

    def line(pos):
        return base_line + bisect.bisect_left(newlines, pos)

    def closing(i, end):
        depth, quote = 0, None
        for j in range(i, end):
            c = text[j]
            if quote:
                if c == quote:
                    quote = None
            elif c in "\"'":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return j
        return end

    def declare(decls, start, end):
        chunk = text[start:end]
        if ":" not in chunk or not chunk.strip():
            return
        lead = len(chunk) - len(chunk.lstrip())
        prop, _, value = chunk.strip().partition(":")
        prop = prop.strip()
        prop = prop if prop.startswith("--") else prop.lower()
        value = re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.IGNORECASE)
        if prop and not prop.startswith("@") and re.fullmatch(r"-?-?[A-Za-z][\w-]*", prop):
            decls[prop] = (value, line(start + lead))

    def block(start, end, context, parent):
        decls, seg, i, paren, quote = {}, start, start, 0, None
        while i < end:
            c = text[i]
            if quote:
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    quote = None
            elif c in "\"'":
                quote = c
            elif c == "(":
                paren += 1
            elif c == ")":
                paren = max(0, paren - 1)
            elif paren == 0 and c == ";":
                declare(decls, seg, i)
                seg = i + 1
            elif paren == 0 and c == "{":
                close = closing(i, end)
                raw = text[seg:i]
                nested(" ".join(raw.split()), i + 1, close, context, parent,
                       line(seg + len(raw) - len(raw.lstrip())))
                i = seg = close + 1
                continue
            i += 1
        declare(decls, seg, end)
        return decls

    def nested(prelude, start, end, context, parent, at_line):
        low = prelude.lower()
        if low.startswith("@"):
            name = re.match(r"@([\w-]*)", low).group(1)
            if name in ("media", "supports", "layer", "container", "scope", "document"):
                block(start, end, context + ((name, prelude),), parent)
            return                      # keyframes, font-face, page, property: no style rules
        selector = combine(parent, prelude) if parent else prelude
        decls = block(start, end, context, selector)
        if decls and selector:
            rules.append({"selector": selector, "decls": decls, "context": context, "line": at_line,
                          "target": target})

    block(0, len(text), (), None)
    return rules


def combine(parent, selector):
    parents = split_top(parent)
    whole = parents[0] if len(parents) == 1 else f":is({parent})"
    return ", ".join(part.replace("&", whole) if "&" in part else f"{whole} {part}"
                     for part in split_top(selector))


def last_compound(part):
    tokens = [t for t in re.split(r"\s*[>+~]\s*|\s+", part.strip()) if t]
    return tokens[-1] if tokens else ""


def tag_of(part):
    m = re.match(r"([A-Za-z][\w-]*)", last_compound(part))
    return m.group(1).lower() if m else None


ROOT_QUALIFIER = re.compile(r"(?::root|html|body)((?:\[[^\]]*\]|\.[\w-]+|:(?:not|where|is)\((?:[^()]|\([^()]*\))*\))+)")


def root_kind(part):
    """'base' for :root/html/body, the qualified selector for a scheme root such as :root[data-theme=dark]."""
    p = part.strip()
    if p in (":root", "html", "body", ":host"):
        return "base"
    if ROOT_QUALIFIER.fullmatch(p):
        return p
    return None


STATE_PSEUDO = re.compile(r":(?:hover|focus|focus-visible|focus-within|active|visited|checked|"
                          r"disabled|target)\b")


def descends(child, ancestor):
    """True when selector `child` names elements inside `ancestor` (by its leading compound sequence)."""
    a = STATE_PSEUDO.sub("", ancestor)
    c = STATE_PSEUDO.sub("", child)
    return c != a and (c.startswith(a + " ") or c.startswith(a + ">") or c.startswith(a + " >"))


def scheme_media(context):
    return " ".join(prelude for name, prelude in context if "prefers-color-scheme" in prelude.lower())


# ---------- inputs ----------

class ImageRefs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.refs, self.styles = [], []
        self._style_line = None

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        line = self.getpos()[0]
        if tag in ("img", "source"):
            if a.get("src"):
                self.refs.append((line, a["src"]))
            for cand in split_top(a.get("srcset", "")):
                self.refs.append((line, cand.split()[0]))
        elif tag == "link" and "icon" in a.get("rel", "").lower() and a.get("href"):
            self.refs.append((line, a["href"]))
        elif tag == "meta" and a.get("property", "").lower() in ("og:image", "twitter:image") and a.get("content"):
            self.refs.append((line, a["content"]))
        elif tag == "style":
            self._style_line = line

    def handle_data(self, data):
        if self._style_line is not None:
            self.styles.append((self._style_line, data))

    def handle_endtag(self, tag):
        if tag == "style":
            self._style_line = None


class Build:
    """CSS rules, custom properties and image references of a built site or a WordPress theme."""

    def __init__(self, root, kind):
        self.root, self.kind = root, kind
        self.rules, self.sheets, self.images = [], [], []
        self.theme_vars = {}            # --wp--preset--*/--wp--custom--* from theme.json
        self.base_vars = {}             # plain root, no colour-scheme context
        self.scheme_vars = {}           # scheme key -> overrides
        self.root_decls = {}            # name -> (target, line, value) at plain root
        self.declared = {}              # name -> (target, line), any selector

    def files(self):
        for p in sorted(self.root.rglob("*")):
            if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(self.root).parts):
                yield p

    def read(self, path):
        size = path.stat().st_size
        if size > MAX_BYTES:
            raise ValueError(f"{path.relative_to(self.root)}: {size} bytes exceeds the {MAX_BYTES}-byte limit")
        return path.read_text(encoding="utf-8")

    def load(self):
        for p in self.files():
            rel = p.relative_to(self.root).as_posix()
            suffix = p.suffix.lower()
            if suffix == ".css":
                self.add_sheet(rel, parse_css(self.read(p), rel))
                self.css_images(rel, self.read(p))
            elif suffix in (".html", ".htm"):
                text = self.read(p)
                parser = ImageRefs()
                parser.feed(text)
                parser.close()
                self.images.extend((rel, line, ref) for line, ref in parser.refs)
                rules = []
                for line, css in parser.styles:
                    rules.extend(parse_css(css, rel, base_line=line))
                    self.css_images(rel, css, base_line=line)
                if rules:
                    self.add_sheet(rel, rules)
                if self.kind == "theme":
                    self.theme_markup_images(rel, text)
            elif suffix == ".php" and self.kind == "theme":
                self.theme_markup_images(rel, self.read(p))
        if self.kind == "theme":
            self.load_theme_json()
        self.collect_vars()

    def add_sheet(self, rel, rules):
        self.sheets.append(rel)
        self.rules.extend(rules)

    def css_images(self, rel, css, base_line=1):
        for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", strip_comments(css)):
            if IMAGE_EXT.search(m.group(1)):
                self.images.append((rel, base_line + css.count("\n", 0, m.start()), m.group(1)))

    def theme_markup_images(self, rel, text):
        for m in re.finditer(r"""["'(]([^"'()<>\s]+?\.(?:png|jpe?g|gif|webp|avif|svg))["')]""", text, re.IGNORECASE):
            self.images.append((rel, text.count("\n", 0, m.start()) + 1, m.group(1)))

    def load_theme_json(self):
        path = self.root / "theme.json"
        if not path.is_file():
            raise ValueError("theme.json not found in the theme directory")
        try:
            data = json.loads(self.read(path))
        except ValueError as exc:
            raise ValueError(f"theme.json does not parse: {exc}") from None
        if not isinstance(data, dict):
            raise ValueError("theme.json is not a JSON object")
        settings = data.get("settings", {}) if isinstance(data.get("settings"), dict) else {}
        for kind, key, field in PRESET_SOURCES:
            section = settings.get("typography" if kind.startswith("font") else
                                   "spacing" if kind == "spacing" else "color", {})
            for item in (section.get(key) or []) if isinstance(section, dict) else []:
                if isinstance(item, dict) and item.get("slug") and isinstance(item.get(field), str):
                    self.theme_vars[f"--wp--preset--{kind}--{item['slug']}"] = wp_value(item[field])

        def flatten(prefix, node):
            for k, v in node.items():
                name = prefix + "--" + re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", k).lower()
                if isinstance(v, dict):
                    flatten(name, v)
                elif isinstance(v, (str, int, float)):
                    self.theme_vars[name] = wp_value(str(v))
        if isinstance(settings.get("custom"), dict):
            flatten("--wp--custom", settings["custom"])
        styles = data.get("styles")
        if isinstance(styles, dict):
            rules = []
            self.theme_style_rules(styles, "body", rules)
            if rules:
                self.add_sheet("theme.json", rules)

    def theme_style_rules(self, node, selector, rules):
        decls = {}
        colour = node.get("color") if isinstance(node.get("color"), dict) else {}
        if isinstance(colour.get("text"), str):
            decls["color"] = (wp_value(colour["text"]), None)
        if isinstance(colour.get("background"), str):
            decls["background-color"] = (wp_value(colour["background"]), None)
        typo = node.get("typography") if isinstance(node.get("typography"), dict) else {}
        for key, prop in (("lineHeight", "line-height"), ("letterSpacing", "letter-spacing"),
                          ("fontSize", "font-size"), ("fontWeight", "font-weight")):
            if isinstance(typo.get(key), (str, int, float)):
                decls[prop] = (wp_value(str(typo[key])), None)
        if decls:
            rules.append({"selector": selector, "decls": decls, "context": (), "line": None, "target": "theme.json"})
        element_selectors = {"link": "a", "button": "button", "heading": "h1, h2, h3, h4, h5, h6", "caption": "figcaption"}
        for name, child in (node.get("elements") or {}).items() if isinstance(node.get("elements"), dict) else []:
            if isinstance(child, dict):
                sel = element_selectors.get(name, name)
                self.theme_style_rules(child, sel if selector == "body" else f"{selector} {sel}", rules)
        for name, child in (node.get("blocks") or {}).items() if isinstance(node.get("blocks"), dict) else []:
            if isinstance(child, dict):
                sel = ".wp-block-" + name.split("/")[-1]
                if name == "core/button":
                    sel = ".wp-block-button__link"
                self.theme_style_rules(child, sel, rules)

    def collect_vars(self):
        self.base_vars.update(self.theme_vars)
        for rule in self.rules:
            media = scheme_media(rule["context"])
            other_media = any(n in ("media", "container") and "prefers-color-scheme" not in p.lower()
                              for n, p in rule["context"])
            kinds = {root_kind(p) for p in split_top(rule["selector"])} - {None}
            for prop, (value, line) in rule["decls"].items():
                if not prop.startswith("--"):
                    continue
                self.declared.setdefault(prop, (rule["target"], line))
                for kind in kinds:
                    if kind == "base" and not media:
                        if other_media:
                            self.base_vars.setdefault(prop, value)
                        else:
                            self.base_vars[prop] = value
                            self.root_decls[prop] = (rule["target"], line, value)
                    else:
                        key = " ".join(x for x in (media, "" if kind == "base" else kind) if x)
                        self.scheme_vars.setdefault(key, {})[prop] = value

    def schemes(self):
        out, seen = [("default", self.base_vars)], [self.base_vars]
        for key, overrides in sorted(self.scheme_vars.items()):
            merged = {**self.base_vars, **overrides}
            if merged not in seen:
                seen.append(merged)
                out.append((key, merged))
        return out


# ---------- the design record's tokens ----------

def parse_tokens(spec):
    """{name: value or None} from a semantic_tokens field; `--space-1..6` expands to a range."""
    tokens = {}
    matches = list(TOKEN_NAME.finditer(spec))
    for n, m in enumerate(matches):
        name, upto = m.group(1).rstrip("-"), m.group(2)
        value = None
        rest = spec[m.end():matches[n + 1].start() if n + 1 < len(matches) else len(spec)]
        stripped = rest.lstrip(" `")
        if not upto and stripped[:1] in (":", "="):
            value = stripped[1:].strip().strip("`")
            value = re.sub(r"[\s,;*`-]+$", "", value)
            value = re.sub(r"\s+\([^()]*\)$", "", value).strip().strip("`")
            value = value or None
        if upto:
            base = re.match(r"(.*?)(\d+)$", name)
            if base and int(upto) >= int(base.group(2)) and int(upto) - int(base.group(2)) < 50:
                for i in range(int(base.group(2)), int(upto) + 1):
                    tokens.setdefault(f"--{base.group(1)}{i}", None)
                continue
        tokens.setdefault("--" + name, value)
        if value is not None:
            tokens["--" + name] = value
    return tokens


def theme_alias(name, theme_vars):
    """The theme.json variable a record token maps to: exact name, kind prefix + slug, or slug alone."""
    if name in theme_vars:
        return name
    bare = name[2:]
    for prefix, kind in ALIAS_KINDS:
        if bare.startswith(prefix + "-"):
            cand = f"--wp--preset--{kind}--{bare[len(prefix) + 1:]}"
            if cand in theme_vars:
                return cand
    for var in theme_vars:
        tail = var.split("--wp--preset--", 1)[-1].split("--", 1)[-1] if var.startswith("--wp--preset--") \
            else var[len("--wp--custom--"):].replace("--", "-")
        if tail == bare:
            return var
    return None


# ---------- the checker ----------

ZERO = re.compile(r"^-?0+(?:\.0+)?(?:px|r?em|%|vh|vw|ch|ex)?$")


def margin_top(decls, variables):
    """The top margin a rule sets, as "0" or the raw value, or None when it sets none (last one wins)."""
    best = None
    for prop in ("margin", "margin-block", "margin-top", "margin-block-start"):
        if prop not in decls:
            continue
        value, line = decls[prop]
        parts = split_top(resolve(value, variables) or value, " ")
        if not parts:
            continue
        if best is None or (line or 0) >= best[1]:
            best = (parts[0].strip().lower(), line or 0)
    if best is None or best[0] in ("auto", "inherit", "initial", "unset", "revert", "revert-layer"):
        return None
    return "0" if ZERO.match(best[0]) else best[0]


class Checker:
    def __init__(self, wanted, release, report):
        self.wanted, self.release, self.report = wanted, release, report
        self.results, self.defects, self.counts, self.seen = {}, {}, {}, set()
        self.targets = {}               # display target -> absolute path
        self.matched = self.compared = 0        # tokens found in the build / values compared
        self.pairs = {"checked": 0, "unresolved": 0, "inferred": 0}
        self.inferred = {}              # (fg, bg, scheme, need) -> [(rule, ratio, how, large)]
        self.label_max, self.label_source = LABEL_TRACKING_MAX, None
        self.tracking_unclassified = []   # [{selector, letter_spacing_em, target, line}] for browser review
        self.skip_reasons = {}
        self.build_root = self.design_path = None   # further inputs the records depend on

    def add(self, check_id, target, line, severity, evidence, action, kind="defect", where=None, also=(), extra=None):
        """One finding. `target` keys the result (what gets recorded); `where` is the file shown in the
        location when it differs; `also` lists further targets the same defect fails; `extra` adds fields
        (such as the contrast `basis`) to the finding."""
        if check_id not in self.wanted:
            return
        where = where or target
        key = (check_id, where, line, evidence)
        if key in self.seen:
            return
        self.seen.add(key)
        for t in (target, *also):
            if severity == "defect":
                self.results[(check_id, t)] = "failed"
                self.defects.setdefault((check_id, t), []).append(evidence)
            else:
                self.results.setdefault((check_id, t), "passed")
        n = self.counts[(check_id, target)] = self.counts.get((check_id, target), 0) + 1
        if n == MAX_FINDINGS_PER_TARGET + 1:
            self.report.add(check_id, target, "warning", "more findings for this check and target were not listed",
                            "fix the listed ones and rerun", kind="convention")
        elif n <= MAX_FINDINGS_PER_TARGET or severity == "defect":
            self.report.add(check_id, f"{where}:{line}" if line else where, severity, evidence, action, kind)
            if extra:
                self.report.findings[-1].update(extra)

    def ran(self, check_id, target, result="passed", reason=None):
        if check_id in self.wanted:
            if result == "skipped" and reason:
                self.skip_reasons[(check_id, target)] = reason
            if result == "passed":
                self.results.setdefault((check_id, target), "passed")
            elif self.results.get((check_id, target)) != "failed":
                self.results[(check_id, target)] = result

    # ----- tokens -----
    def token_drift(self, build, design, record_target):
        """Results for two targets: the build directory (".") and the design record file."""
        cid = "design.token-drift"
        loc = design.get("_lines", {}).get("semantic_tokens", design.get("_loc", record_target)).split(":")
        line = int(loc[1]) if len(loc) > 1 and loc[1].isdigit() else None
        spec = design.get("semantic_tokens")
        if not spec or EMPTY_FIELD.match(spec):
            self.add(cid, record_target, line, "defect", "design record has no semantic_tokens",
                     "record the semantic tokens with their values", also=(".",))
            return
        tokens = parse_tokens(spec)
        if not tokens:
            reason = "semantic_tokens names no custom properties (--name); nothing to compare"
            self.ran(cid, ".", "skipped", reason)
            self.ran(cid, record_target, "skipped", reason)
            self.report.diagnostics.append("semantic_tokens names no custom properties (--name); nothing to compare")
            return
        self.ran(cid, ".")
        self.ran(cid, record_target)
        for name, recorded in tokens.items():
            built_name = name if name in build.declared else (theme_alias(name, build.theme_vars)
                                                               if build.kind == "theme" else None)
            single = re.fullmatch(r"(--.+)-1", name)
            if not built_name and build.kind == "theme" and single and f"{single.group(1)}-2" not in tokens:
                built_name = theme_alias(single.group(1), build.theme_vars)
                if built_name:
                    self.add(cid, record_target, line, "warning",
                             f"{name} matched {built_name} (one-step scale written without its number)",
                             "name the theme.json key after the record token to make the mapping exact",
                             kind="convention")
            if not built_name:
                self.add(cid, record_target, line, "defect",
                         f"{name} is in the design record but the build never defines it",
                         "define it in the stylesheet (or theme.json), or remove it from the record", also=(".",))
                continue
            self.matched += 1
            if recorded is None or not looks_like_css(recorded):
                continue
            where, at, raw = build.root_decls.get(built_name, ("theme.json", None, build.theme_vars.get(built_name)))
            if raw is None:
                continue
            built = resolve(raw, build.base_vars)
            wanted = resolve(recorded, build.base_vars) or recorded
            if built is None:
                self.add(cid, ".", at, "warning", f"{name}: the built value {raw!r} does not resolve statically; "
                         "not compared", "compare it in the browser", kind="convention", where=where)
                continue
            self.compared += 1
            if not same_value(wanted, built):
                self.add(cid, ".", at, "defect", f"{name}: the design record says {recorded!r}, the build has {raw!r}",
                         "change the build or update the design record so they agree", where=where,
                         also=(record_target,))
        unnamed = {}
        for name, (where, at, raw) in build.root_decls.items():
            if name not in tokens and not name.startswith("--wp--"):
                unnamed.setdefault(where, []).append((at or 0, name, raw))
        for where, found in sorted(unnamed.items()):      # one warning per stylesheet, not one per token
            found.sort()
            listed = ", ".join(f"{n} ({' '.join(str(v).split())[:40]})" for _, n, v in found[:MAX_LISTED * 2])
            more = f" and {len(found) - MAX_LISTED * 2} more" if len(found) > MAX_LISTED * 2 else ""
            self.add(cid, ".", found[0][0] or None, "warning",
                     f"{len(found)} root token{'s' if len(found) != 1 else ''} the design record doesn't name: "
                     f"{listed}{more}",
                     "add them to semantic_tokens if they belong to the design system; otherwise make them "
                     "component-private (declare them on the component) or move them off :root",
                     kind="convention", where=where, extra={"tokens": [n for _, n, _ in found]})

    def raw_literals(self, build, tokens):
        cid = "design.raw-literals"
        by_value = {}
        for name, value in tokens.items():
            v = resolve(value, build.base_vars) if value else resolve(build.base_vars.get(name), build.base_vars)
            if v and parse_colour(v):
                by_value.setdefault(show(parse_colour(v)), name)
        for name, (_, _, value) in build.root_decls.items():
            c = parse_colour(resolve(value, build.base_vars) or "")
            if c:
                by_value.setdefault(show(c), name)
        for target in build.sheets:
            if target == "theme.json":
                continue
            self.ran(cid, target)
        for rule in build.rules:
            if rule["target"] == "theme.json":
                continue
            for prop, (value, line) in rule["decls"].items():
                if prop.startswith("--") or not COLOUR_PROP.search(prop):
                    continue
                text = re.sub(r"\"[^\"]*\"|'[^']*'|url\([^)]*\)", "", value)
                text = re.sub(r"var\([^()]*(?:\([^()]*\))?[^()]*\)", "", text)
                m = HEX_LITERAL.search(text) or FUNC_LITERAL.search(text) or NAMED_LITERAL.search(text)
                if not m:
                    continue
                c = parse_colour(m.group(0))
                token = by_value.get(show(c)) if c else None
                action = f"use var({token})" if token else "add it to the design record's tokens and use var(--...)"
                self.add(cid, rule["target"], line, "warning", f"{rule['selector']} {{ {prop}: {m.group(0)} }} is a raw colour",
                         action, kind="convention")
        self.raw_scale_literals(build, tokens)

    def raw_scale_literals(self, build, tokens):
        """Spacing lengths and durations written as literals. Hairlines (1px or less), zero and values inside
        var() fallbacks are left alone. One warning per stylesheet and kind, with a count and samples, so a
        large sheet stays readable; a literal equal to a token's value names that token."""
        cid = "design.raw-literals"
        known = {}
        values = {**{n: v for n, v in tokens.items() if v}, **{n: v for n, (_, _, v) in build.root_decls.items()}}
        for name, value in values.items():
            v = (resolve(value, build.base_vars) or "").strip()
            key = scale_key(v)
            if key:
                known.setdefault(key, name)
        found = {}
        for rule in build.rules:
            if rule["target"] == "theme.json":
                continue
            for prop, (value, line) in rule["decls"].items():
                if prop.startswith("--"):
                    continue
                kind = "spacing" if SPACING_PROP.match(prop) else "duration" if DURATION_PROP.match(prop) else None
                if not kind:
                    continue
                text = re.sub(r"var\([^()]*(?:\([^()]*\))?[^()]*\)", "", value)
                pattern = LENGTH_LITERAL if kind == "spacing" else DURATION_LITERAL
                for m in pattern.finditer(text):
                    key = scale_key(m.group(0))
                    if key is None or (kind == "spacing" and abs(key[0]) <= 1 and key[1] == "px"):
                        continue
                    found.setdefault((rule["target"], kind), []).append((line, rule["selector"], prop, m.group(0), known.get(key)))
        for (target, kind), items in sorted(found.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
            samples = "; ".join(f"{sel} {{ {prop}: {lit} }}" + (f" = var({tok})" if tok else "")
                                for _, sel, prop, lit, tok in items[:4])
            more = f" and {len(items) - 4} more" if len(items) > 4 else ""
            matched = sum(1 for item in items if item[4])
            what = "spacing lengths (margin, padding, gap, inset)" if kind == "spacing" else "durations (transition, animation)"
            action = ("use the space tokens of the design record; " if kind == "spacing" else "use the motion tokens of the design record; ") + \
                     (f"{matched} of them equal an existing token, so start there; " if matched else "") + \
                     "a value the system lacks belongs in the design record first"
            self.add(cid, target, items[0][0], "warning", f"{len(items)} raw {what}: {samples}{more}", action,
                     kind="convention", extra={"kind": kind, "count": len(items)})

    # ----- style -----
    def colours(self, rule, variables):
        d = rule["decls"]
        fg = parse_colour(resolve(d["color"][0], variables) or "") if "color" in d else None
        bg_decl = None
        for prop in ("background", "background-color"):
            if prop in d and (bg_decl is None or (d[prop][1] or 0) >= (bg_decl[1] or 0)):
                bg_decl = d[prop]
        bg = None
        if bg_decl:
            value = resolve(bg_decl[0], variables)
            if value is None or re.search(r"url\(|gradient\(|image\(", value, re.IGNORECASE):
                bg = "complex"
            else:
                for token in split_top(value, " "):
                    bg = parse_colour(token) or bg
        return fg, bg, ("color" in d), bg_decl is not None

    def is_large(self, rule, variables):
        d = rule["decls"]
        size = None
        if "font-size" in d:
            size = length_px(resolve(d["font-size"][0], variables) or "")
        elif "font" in d:
            m = re.search(r"(\S+?)(?:/\S+)?\s+[^/]*$", (resolve(d["font"][0], variables) or "").split(",")[0])
            size = length_px(m.group(1)) if m else None
        weight = (resolve(d.get("font-weight", ("",))[0], variables) or "").strip().lower()
        bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 700)
        if size is None:
            tags = {tag_of(p) for p in split_top(rule["selector"])}
            return bool(tags) and tags <= LARGE_BY_DEFAULT
        return size >= 24 or (bold and size >= 18.66)

    def judge(self, rule, fg, bg, ground, variables, scheme, severity, how):
        if fg is None or bg is None or bg == "complex":
            self.pairs["unresolved"] += 1
            return
        if bg[3] < 1:
            if ground is None or ground == "complex" or ground[3] < 1:
                self.pairs["unresolved"] += 1
                return
            bg = over(bg, ground)
        self.pairs["checked"] += 1
        if fg[3] < 1:
            fg = over(fg, bg)
        large = self.is_large(rule, variables)
        need = 3.0 if large else 4.5
        ratio = contrast(fg, bg)
        if severity != "defect":
            self.pairs["inferred"] += 1
        if ratio + 1e-9 >= need:
            return
        if severity != "defect":                  # inferred: grouped per colour pair in contrast_groups()
            self.inferred.setdefault((show(fg), show(bg), scheme, need), []).append((rule, ratio, how, large))
            return
        where = "" if scheme == "default" else f" in the {scheme} scheme"
        self.add("style.contrast", rule["target"], rule["line"], severity,
                 f"{rule['selector']}: text {show(fg)} on {show(bg)} is {ratio:.2f}:1{where}, needs {need:g}:1"
                 f"{' (large text)' if large else ''}{how}",
                 "change one colour of the pair, record the new ratio in the design record, "
                 "then confirm with browser.contrast", extra={"basis": "declared"})

    def contrast_groups(self):
        """One warning per inferred (text, background, scheme) pair, listing its selectors. A declared pair
        is always reported on its own as a defect."""
        for (fg, bg, scheme, need), hits in self.inferred.items():
            rule, ratio, how, large = hits[0]
            sels = []
            for r, *_ in hits:
                if r["selector"] not in sels:
                    sels.append(r["selector"])
            shown = ", ".join(sels[:MAX_LISTED]) + (f" (+{len(sels) - MAX_LISTED} more)" if len(sels) > MAX_LISTED else "")
            where = "" if scheme == "default" else f" in the {scheme} scheme"
            if fg == bg:
                action = ("likely a non-text element (swatch, rule or decoration) that sets a colour; if it holds "
                          "no text, ignore this; otherwise confirm with browser.contrast")
            else:
                action = ("confirm the real pairing with browser.contrast; if it holds, change one colour and "
                          "record the new ratio in the design record")
            self.add("style.contrast", rule["target"], rule["line"], "warning",
                     f"{shown}: text {fg} on {bg} is {ratio:.2f}:1{where}, needs {need:g}:1"
                     f"{' (large text)' if large else ''}{how}", action, kind="convention",
                     extra={"basis": "inferred", "selectors": sels})

    def contrast_checks(self, build):
        """Merge declarations per selector (in source order, per colour scheme), let a state selector
        (:hover, :focus, ...) inherit its base selector's declarations, then judge each selector that sets a
        colour or a background: both resolved in one selector is a defect; a partner found through a
        descendant selector or the page ground is a warning (static inference)."""
        for target in build.sheets:
            self.ran("style.contrast", target)
        for scheme, variables in build.schemes():
            merged, origin, order = {}, {}, []
            for r in build.rules:
                media = scheme_media(r["context"])
                if media and (scheme == "default" or media not in scheme):
                    continue
                for part in split_top(r["selector"]):
                    if part not in merged:
                        merged[part] = {}
                        order.append(part)
                    merged[part].update(r["decls"])
                    origin[part] = r
            def effective(part):
                base = STATE_PSEUDO.sub("", part)
                return {**merged.get(base, {}), **merged[part]} if base != part else merged[part]
            def view(part):
                return {"selector": part, "decls": effective(part), "target": origin[part]["target"],
                        "line": origin[part]["line"]}
            ground, ground_text = None, None
            for part in order:
                if root_kind(part) == "base":
                    fg, bg, _, has_bg = self.colours(view(part), variables)
                    ground = bg if has_bg and bg is not None else ground
                    ground_text = fg or ground_text
            backgrounds = []
            for part in order:
                own = merged[part]
                if not ({"color", "background", "background-color"} & set(own)):
                    continue
                rule = view(part)
                fg, bg, has_fg, has_bg = self.colours(rule, variables)
                if has_bg and bg is not None and bg != "complex" and not root_kind(part):
                    backgrounds.append((part, bg))
                if has_fg and has_bg:
                    self.judge(rule, fg, bg, ground, variables, scheme, "defect", "")
                elif has_bg and not root_kind(part):
                    children = [c for c in order if "color" in merged[c] and descends(c, part)]
                    if not children:
                        self.judge(rule, ground_text, bg, ground, variables, scheme, "warning",
                                   "; the text colour is inherited from the page (static inference)")
            for part in order:
                rule = view(part)
                fg, _, has_fg, has_bg = self.colours(rule, variables)
                if not has_fg or has_bg or root_kind(part):
                    continue
                parents = [(len(b), b, bg) for b, bg in backgrounds if descends(part, b)]
                if parents:
                    _, b, bg = max(parents)
                    self.judge(rule, fg, bg, ground, variables, scheme, "warning",
                               f"; background from {b} (static inference)")
                elif ground is not None:
                    self.judge(rule, fg, ground, ground, variables, scheme, "warning",
                               "; assumes the page background (static inference)")
        self.contrast_groups()

    def categories(self, rule):
        tags = {tag_of(p) for p in split_top(rule["selector"])}
        return ("running" if tags & TEXT_TAGS else "heading" if tags & HEADING_TAGS else None), tags

    def font_px(self, rule, variables):
        d = rule["decls"]
        if "font-size" in d:
            return length_px(resolve(d["font-size"][0], variables) or "")
        return None

    def line_height(self, rule, variables):
        d = rule["decls"]
        raw = d["line-height"][0] if "line-height" in d else None
        if raw is None and "font" in d:
            m = re.search(r"/\s*([^\s,]+)", resolve(d["font"][0], variables) or "")
            raw = m.group(1) if m else None
        value = (resolve(raw, variables) or "").strip().lower() if raw else ""
        m = re.fullmatch(r"(\d*\.?\d+)(%|em|px|rem)?", value)
        if not m:
            return None
        n, unit = float(m.group(1)), m.group(2)
        if unit in (None, "em"):
            return n
        if unit == "%":
            return n / 100
        size = self.font_px(rule, variables)
        return None if not size else (n if unit == "px" else n * 16) / size

    def type_checks(self, build):
        variables = build.base_vars
        for target in build.sheets:
            for cid in ("style.leading", "style.tracking", "style.justify", "style.padding"):
                self.ran(cid, target)
        for rule in build.rules:
            if scheme_media(rule["context"]):
                continue
            category, tags = self.categories(rule)
            d, sel, target, line = rule["decls"], rule["selector"], rule["target"], rule["line"]
            lh = self.line_height(rule, variables)
            if lh is not None and category == "running":
                if lh < 1.2:
                    self.add("style.leading", target, line, "defect", f"{sel}: line height {lh:.2f} on running text",
                             "use at least 1.4 for body text (1.5 suits long reading)")
                elif lh < 1.4:
                    self.add("style.leading", target, line, "warning", f"{sel}: line height {lh:.2f} on running text is tight",
                             "use at least 1.4 for body text", kind="convention")
            elif lh is not None and category == "heading" and lh < 0.95:
                self.add("style.leading", target, line, "warning", f"{sel}: heading line height {lh:.2f} can clip or collide",
                         "keep heading line height at 1.0 or more, and check two-line headings", kind="convention")
            if "text-align" in d and d["text-align"][0].strip().lower() == "justify" and not tags <= HEADING_TAGS:
                hyphens = (d.get("hyphens") or d.get("-webkit-hyphens") or ("",))[0].strip().lower()
                if hyphens != "auto":
                    self.add("style.justify", target, line, "warning", f"{sel}: justified text without hyphenation",
                             "align left (start), or add hyphens: auto with a lang attribute, and check narrow widths",
                             kind="convention")
            self.padding(rule, variables)
        if "style.tracking" in self.wanted:
            self.tracking(build)

    def merged_parts(self, build):
        """Declarations merged per selector part in source order (colour-scheme rules left out), with the
        rule that last set each part; `font-size` etc. from one rule apply to `letter-spacing` from another."""
        merged, origin, order = {}, {}, []
        for r in build.rules:
            if scheme_media(r["context"]):
                continue
            for part in split_top(r["selector"]):
                if part not in merged:
                    merged[part], origin[part] = {}, {}
                    order.append(part)
                for prop, decl in r["decls"].items():
                    merged[part][prop] = decl
                    origin[part][prop] = r
        return merged, origin, order

    def role(self, part, decls, variables):
        """label | running | uncertain | unclassified | None (not judged). `unclassified`: the last compound
        names no element type (.intro, #lead, [data-x]), so the role cannot be read from the source."""
        transform = (resolve(decls.get("text-transform", ("",))[0], variables) or "").lower()
        caps = " ".join((resolve(decls.get(p, ("",))[0], variables) or "").lower()
                        for p in ("font-variant", "font-variant-caps"))
        if "uppercase" in transform or "small-caps" in caps:
            size = length_px(resolve(decls["font-size"][0], variables) or "") if "font-size" in decls else None
            if size is None or size <= 16:
                return "label"
        if GENERATED.search(last_compound(part)):
            return "uncertain"
        tag = tag_of(part)
        if tag is None and last_compound(part)[:1] in (".", "#", "["):
            return "unclassified"
        if tag in RUNNING_TAGS:
            return "running"
        if tag in UNCERTAIN_TAGS:
            return "uncertain"
        return None

    def tracking(self, build):
        variables = build.base_vars
        merged, origin, order = self.merged_parts(build)
        for part in order:
            decls = merged[part]
            if "letter-spacing" not in decls:
                continue
            role = self.role(part, decls, variables)
            if role is None:
                continue
            raw, line = decls["letter-spacing"]
            rule = origin[part]["letter-spacing"]
            value = (resolve(raw, variables) or "").strip().lower()
            em = None
            if value in ("normal", "0"):
                em = 0.0
            else:
                m = re.fullmatch(r"(-?\d*\.?\d+)(em|px|rem)", value)
                if m:
                    n = float(m.group(1))
                    size = self.font_px({"decls": decls}, variables) or 16.0
                    em = n if m.group(2) == "em" else (n if m.group(2) == "px" else n * 16) / size
            if em is None:
                continue
            target = rule["target"]
            if role == "label":
                if em > self.label_max + 1e-9:
                    source = f"the design record's label_tracking_max {self.label_max:g}em" if self.label_source \
                        else f"the default label maximum {self.label_max:g}em"
                    self.add("style.tracking", target, line, "warning",
                             f"{part}: letter spacing {em:.3f}em on a label is above {source}",
                             "reduce it, or record the accepted value as label_tracking_max in the design record",
                             kind="convention", extra={"role": role})
            elif role == "running":
                if em > 0.12:
                    self.add("style.tracking", target, line, "defect", f"{part}: letter spacing {em:.3f}em on running text",
                             "keep running text tracking at or below 0.05em; if this is a short label, give it "
                             "its label style (uppercase or small caps) or a label class", extra={"role": role})
                elif em > 0.05:
                    self.add("style.tracking", target, line, "warning", f"{part}: letter spacing {em:.3f}em on running "
                             "text is wide", "keep running text tracking at or below 0.05em", kind="convention",
                             extra={"role": role})
                elif em < -0.03:
                    self.add("style.tracking", target, line, "warning", f"{part}: letter spacing {em:.3f}em on running "
                             "text is tight", "keep running text tracking at or above -0.03em", kind="convention",
                             extra={"role": role})
            elif role == "unclassified":
                if em > 0.05 or em < -0.03:
                    self.tracking_unclassified.append({"selector": part, "letter_spacing_em": round(em, 3),
                                                       "target": target, "line": line})
                    self.add("style.tracking", target, line, "warning",
                             f"{part}: letter spacing {em:.3f}em; the selector names no element, so its role "
                             "(label or running text) is not known statically",
                             "confirm the role in browser review (visual-measure.js tracking): running text "
                             "should stay at or below 0.05em; a short label is fine up to the label maximum",
                             kind="review", extra={"role": role})
            elif em > 0.12:
                self.add("style.tracking", target, line, "warning",
                         f"{part}: letter spacing {em:.3f}em; its role (label or running text) is uncertain",
                         "confirm the role: a short label is fine up to the label maximum; running text should "
                         "stay at or below 0.05em", kind="review", extra={"role": role})

    # ----- layout -----
    def layout_checks(self, build):
        for target in build.sheets:
            for cid in LAYOUT_CHECKS:
                self.ran(cid, target)
        variables = build.base_vars
        merged, origin, order = self.merged_parts(build)
        if "layout.grid-items" in self.wanted:
            for part in order:
                display = (resolve(merged[part].get("display", ("",))[0], variables) or "").strip().lower()
                if display not in ("grid", "inline-grid"):
                    continue
                for pseudo in ("::before", "::after", ":before", ":after"):
                    gen = merged.get(part + pseudo)
                    if not gen or "content" not in gen:
                        continue
                    content = (gen["content"][0] or "").strip().lower()
                    position = (resolve(gen.get("position", ("",))[0], variables) or "").strip().lower()
                    shown = (resolve(gen.get("display", ("",))[0], variables) or "").strip().lower()
                    if content in ("none", "normal") or position in ("absolute", "fixed") or shown == "none":
                        continue
                    raw, line = gen["content"]
                    self.add("layout.grid-items", origin[part + pseudo]["content"]["target"], line, "warning",
                             f"{part + pseudo} has content and stays in flow inside a {display} container, so it "
                             "becomes a grid item: it takes a cell and shifts the real children",
                             "position it absolutely (or draw it on a child or a border) if it is decoration; "
                             "confirm the layout with visual.measure", kind="review")
        if "layout.spacing-reset" in self.wanted:
            given = {}                                   # heading tag -> (selector, line, target) giving a top margin
            for rule in build.rules:
                if scheme_media(rule["context"]):
                    continue
                top = margin_top(rule["decls"], variables)
                if top is None:
                    continue
                for part in split_top(rule["selector"]):
                    tag = tag_of(part)
                    if tag not in HEADING_TAGS:
                        continue
                    if top != "0":
                        given[(rule["target"], tag)] = (part, rule["line"])
                        continue
                    src = given.get((rule["target"], tag))
                    if src and src[0] != part:
                        self.add("layout.spacing-reset", rule["target"], rule["line"], "warning",
                                 f"{part} sets the top margin of {tag} to 0 after {src[0]} (line {src[1]}) gave it "
                                 "one; the gap above these headings may collapse",
                                 "if the reset is intended, ignore this; otherwise keep the spacing the layout rules "
                                 "set (or give the gap to the container) and confirm with visual.measure",
                                 kind="review")

    def padding(self, rule, variables):
        sel, d = rule["selector"], rule["decls"]
        parts = split_top(sel)
        if not any((tag_of(p) in FIELD_TAGS or CONTROL_CLASS.search(last_compound(p))) and
                   not NOT_PADDED.search(last_compound(p)) for p in parts):
            return
        fg, bg, _, has_bg = self.colours(rule, variables)
        filled = has_bg and bg is not None and (bg == "complex" or bg[3] > 0)
        border = d.get("border", d.get("border-width", ("",)))[0].strip().lower()
        bordered = bool(border) and not re.match(r"^(none|0(px)?)\b", border)
        if not (filled or bordered):
            return
        sides = {}
        if "padding" in d:
            vals = split_top(resolve(d["padding"][0], variables) or "", " ")
            if 1 <= len(vals) <= 4:
                top, right = vals[0], vals[1 if len(vals) > 1 else 0]
                bottom, left = vals[2 if len(vals) > 2 else 0], vals[3 if len(vals) > 3 else (1 if len(vals) > 1 else 0)]
                sides.update(top=top, right=right, bottom=bottom, left=left)
        for prop, keys in (("padding-block", ("top", "bottom")), ("padding-inline", ("left", "right"))):
            if prop in d:
                vals = split_top(resolve(d[prop][0], variables) or "", " ")
                if vals:
                    sides[keys[0]], sides[keys[1]] = vals[0], vals[-1]
        for side, props in (("top", ("padding-top", "padding-block-start")), ("bottom", ("padding-bottom", "padding-block-end")),
                            ("left", ("padding-left", "padding-inline-start")), ("right", ("padding-right", "padding-inline-end"))):
            for prop in props:
                if prop in d:
                    sides[side] = resolve(d[prop][0], variables) or ""
        if not sides:
            return
        px = {k: length_px(v) for k, v in sides.items()}
        block = [px[k] for k in ("top", "bottom") if px.get(k) is not None]
        inline = [px[k] for k in ("left", "right") if px.get(k) is not None]
        if (block and min(block) < 4) or (inline and min(inline) < 8):
            self.add("style.padding", rule["target"], rule["line"], "warning",
                     f"{sel}: padding {min(block) if block else '?'}px block / {min(inline) if inline else '?'}px inline "
                     "on a filled or bordered control is cramped",
                     "use at least 4px block and 8px inline padding (larger for touch targets)", kind="convention")

    # ----- assets -----
    def asset_checks(self, assets, record_target, root, build):
        entries = assets.get("entries", {})
        rights_targets = [record_target] + (["."] if build else [])
        for cid in ASSET_CHECKS:
            for t in (rights_targets if cid == "assets.rights" else [record_target]):
                self.ran(cid, t)
        if not self.release:
            self.results[("assets.final", record_target)] = "skipped"
            self.skip_reasons[("assets.final", record_target)] = "release-only check; run with --release before release"
        recorded_paths, recorded_text = set(), []
        for aid, entry in sorted(entries.items()):
            loc = entry.get("_loc", record_target).split(":")
            line = int(loc[1]) if len(loc) > 1 and loc[1].isdigit() else None
            status = entry.get("status", "").strip().lower().split(" ")[0]
            use = entry.get("permitted_use", "")
            in_use = status != "rejected"
            standing = sw_records.standing_problem(entry, assets.get("permissions", {}))
            if in_use and standing:
                self.add("assets.rights", record_target, line, "defect" if self.release or status == "approved"
                         else "warning", f"asset {aid}: {standing}",
                         "record the owner's or client's grant as a `### Permission:` entry, or record a licence",
                         **({} if self.release or status == "approved" else {"kind": "convention"}))
            elif in_use and UNKNOWN_USE.match(use):
                if self.release or status == "approved":
                    self.add("assets.rights", record_target, line, "defect",
                             f"asset {aid} ({status or 'no status'}) has unknown permitted use",
                             "confirm the licence or permission and record it, or replace the asset")
                else:
                    self.add("assets.rights", record_target, line, "warning",
                             f"asset {aid} has unknown permitted use; it cannot ship like this",
                             "confirm the permitted use before release", kind="convention")
            if in_use and NEEDS_ATTRIBUTION.search(use) and EMPTY_FIELD.match(entry.get("attribution", "")):
                self.add("assets.rights", record_target, line, "defect",
                         f"asset {aid}: permitted use requires attribution but none is recorded",
                         "record the exact credit line and where it appears")
            path_value = entry.get("local_path", "").strip().strip("`")
            recorded_text.extend([path_value, entry.get("source", "")])
            if REMOTE.match(path_value) or re.match(r"^(?:https?|ftp|data):", path_value, re.IGNORECASE):
                self.add("assets.local-path", record_target, line, "defect",
                         f"asset {aid}: local_path is a remote address ({path_value[:80]})",
                         "store the file in the project (with permission) and record the remote address in source")
            elif path_value and not EMPTY_FIELD.match(path_value):
                p = Path(path_value)
                if p.is_absolute() or re.match(r"^[A-Za-z]:[\\/]|^~", path_value):
                    self.add("assets.local-path", record_target, line, "defect",
                             f"asset {aid}: local_path {path_value!r} is absolute",
                             "use a path relative to the project root")
                else:
                    full = (root / p).resolve()
                    try:
                        full.relative_to(root.resolve())
                    except ValueError:
                        self.add("assets.local-path", record_target, line, "defect",
                                 f"asset {aid}: local_path {path_value!r} points outside the project",
                                 "copy the file into the project and record that path")
                        full = None
                    if full is not None:
                        recorded_paths.add(full)
                        if not full.exists() and status in ("supplied", "approved"):
                            self.add("assets.local-path", record_target, line, "defect",
                                     f"asset {aid} is {status} but {path_value} does not exist",
                                     "add the file or correct local_path")
            elif status in ("supplied", "approved"):
                self.add("assets.local-path", record_target, line, "defect",
                         f"asset {aid} is {status} but has no local_path", "record where the file is in the project")
            if status in NOT_FINAL and self.release:
                self.add("assets.final", record_target, line, "defect",
                         f"asset {aid} is still {status} in a release build",
                         "supply and approve the asset, or remove its placement")
        if build:
            unrecorded = {}             # image -> (first file, line, number of files)
            for where, line, ref in build.images:
                if ref.startswith("data:"):
                    continue
                if REMOTE.match(ref):
                    if any(ref in t for t in recorded_text if t):
                        continue
                    key = ref[:100]
                else:
                    path = local_ref(build.root, where, ref)
                    if path is None or not path.exists() or path.resolve() in recorded_paths:
                        continue
                    key = path.relative_to(build.root.resolve()).as_posix() if is_inside(path, build.root) else ref
                first = unrecorded.get(key)
                unrecorded[key] = (first[0], first[1], first[2] + 1) if first else (where, line, 1)
            severity, kind = ("defect", "defect") if self.release else ("warning", "convention")
            for key, (where, line, n) in sorted(unrecorded.items()):
                files = f" (and {n - 1} more files)" if n > 1 else ""
                self.add("assets.rights", ".", line, severity,
                         f"image {key} is used by the build{files} but is not in the assets record",
                         "add an asset entry (source, permitted use, attribution, status) for it, or self-host "
                         "and record a remote image", kind=kind, where=where)


def is_inside(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def local_ref(root, target, ref):
    parts = urlsplit(ref)
    if parts.scheme or parts.netloc:
        return None
    path = unquote(parts.path)
    if not path:
        return None
    base = root if path.startswith("/") else (root / target).parent
    cand = (base / path.lstrip("/")).resolve()
    if not cand.exists():
        alt = (root / path.lstrip("/")).resolve()
        cand = alt if alt.exists() else cand
    return cand


# ---------- main ----------

def load_records(directory):
    texts = []
    for p in sorted(Path(directory).glob("*.md")):
        texts.append((p.name, p.read_text(encoding="utf-8")))
    return sw_records.parse_records(texts)


def record_file(records_dir, rec):
    return (Path(records_dir) / rec["_loc"].split(":")[0]).as_posix()


def absent_record_target(records_dir, records):
    """Where an `unavailable` result for a missing Design or Assets record is filed: the record file that
    holds the other project records (adding the missing section there changes it), else the first Markdown
    file. Never the records folder itself, which holds verification.json and the evidence."""
    for key in ("brief", "sitemap", "design", "assets"):
        if key in records:
            return record_file(records_dir, records[key])
    found = sorted(Path(records_dir).glob("*.md"))
    return found[0].as_posix() if found else Path(records_dir).as_posix()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sw_design_check.py", description=__doc__.splitlines()[0])
    build_arg = parser.add_mutually_exclusive_group()
    build_arg.add_argument("--site", help="built site (or source) directory with HTML and CSS")
    build_arg.add_argument("--theme", help="WordPress theme directory (theme.json, CSS, templates, patterns)")
    parser.add_argument("--records", help="project records directory (docs/website/)")
    parser.add_argument("--root", help="project root: local_path and recorded targets are relative to it (default: cwd)")
    parser.add_argument("--checks", help="comma-separated check IDs (default: every check the inputs allow)")
    parser.add_argument("--release", action="store_true", help="release build: unknown rights and unfinished assets fail")
    parser.add_argument("--record", help="append one evidence record per (check, target) to this verification file")
    parser.add_argument("--evidence-out", help="also write this report to PATH (required with --record)")
    parser.add_argument("--require", action="store_true", help="with --record: add each check to required_checks")
    parser.add_argument("--mode", choices=sw_records.DELIVERY_MODES,
                        help="criteria to judge: production is the same as --release, mockup the default; only "
                             "release-sensitive checks (assets.*) are recorded with it, the others count for both")
    parser.add_argument("--exclude", action="append", default=[], metavar="PATH",
                        help="with --record: leave PATH (relative to --root) out of folder targets that contain it")
    parser.add_argument("--allow-website-exclusion", action="store_true",
                        help="with --exclude: allow excluding a folder that holds website files")
    try:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            args = parser.parse_args(argv)
    except SystemExit as exc:
        if not exc.code:
            return 0
        r = DesignReport("")
        r.diagnostics.append("invalid arguments: " + (err.getvalue().strip().splitlines() or ["?"])[-1])
        return r.emit("error")
    started = time.monotonic()
    build_dir = args.site or args.theme
    report = DesignReport(build_dir or args.records or "")
    root = Path(args.root or ".")
    possible = set()
    if build_dir:
        possible |= set(BUILD_CHECKS)
    if args.records:
        possible |= set(ASSET_CHECKS)
        if build_dir:
            possible.add("design.token-drift")
    wanted = possible
    if args.checks:
        wanted = {c.strip() for c in args.checks.split(",") if c.strip()}
        unknown = wanted - set(ALL_CHECKS)
        if unknown:
            report.diagnostics.append(f"unknown check IDs: {', '.join(sorted(unknown))}")
            return report.emit("error")
        if wanted - possible:
            report.diagnostics.append(f"these checks need inputs that were not given: {', '.join(sorted(wanted - possible))} "
                                      "(design.token-drift needs --records and --site/--theme; assets.* need --records)")
            return report.emit("error")
    if not wanted:
        report.diagnostics.append("nothing to check: give --site or --theme, and/or --records")
        return report.emit("error")
    if args.record and not args.evidence_out:
        report.diagnostics.append("--record needs --evidence-out (evidence_path must name the saved output)")
        return report.emit("error")
    if args.mode == "mockup" and args.release:
        report.diagnostics.append("--mode mockup contradicts --release (release criteria are production)")
        return report.emit("error")
    args.release = args.release or args.mode == "production"
    if args.record:
        clash = sw_records.cited_evidence_problem(args.record, root, args.evidence_out, TOOL)
        if clash:
            report.diagnostics.append(clash)
            return report.emit("error")
    checker = Checker(wanted, args.release, report)
    build = None
    try:
        if build_dir:
            if not Path(build_dir).is_dir():
                report.diagnostics.append(f"build directory not found: {build_dir}")
                return report.emit("error")
            build = Build(Path(build_dir), "theme" if args.theme else "site")
            build.load()
            checker.build_root = build.root
            checker.inline_sheets = [t for t in build.sheets if not t.endswith(".css")]
            checker.targets["."] = build.root
            for t in build.sheets:
                checker.targets[t] = build.root / t
            if any(t.endswith(".css") for t in build.sheets):
                checker.targets[CSS_SET] = build.root / CSS_SET
            if not build.sheets and wanted & set(BUILD_CHECKS):
                report.diagnostics.append("no CSS found in the build directory")
        records = {}
        if args.records:
            if not Path(args.records).is_dir():
                report.diagnostics.append(f"records directory not found: {args.records}")
                return report.emit("error")
            records = load_records(args.records)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        report.diagnostics.append(f"{type(exc).__name__}: {exc}")
        return report.emit("error")

    tokens = {}
    if "design.token-drift" in wanted:
        design = records.get("design")
        if design is None:
            report.diagnostics.append("no Design record in the records directory: token drift not checked")
            absent = absent_record_target(args.records, records)
            checker.ran("design.token-drift", absent, "unavailable")
            checker.targets[absent] = Path(absent)
        else:
            target = record_file(args.records, design)
            checker.targets[target] = Path(target)
            checker.design_path = Path(target)
            checker.token_drift(build, design, target)
            label_tracking(checker, design, report)
            tokens = parse_tokens(design.get("semantic_tokens", "") or "")
    elif records.get("design"):
        checker.design_path = Path(record_file(args.records, records["design"]))
        label_tracking(checker, records["design"], report)
        tokens = parse_tokens(records["design"].get("semantic_tokens", "") or "")
    if build:
        if build.sheets:
            if "design.raw-literals" in wanted:
                checker.raw_literals(build, tokens)
            if "style.contrast" in wanted:
                checker.contrast_checks(build)
            if wanted & {"style.leading", "style.tracking", "style.justify", "style.padding"}:
                checker.type_checks(build)
            if wanted & set(LAYOUT_CHECKS):
                checker.layout_checks(build)
        else:
            for cid in wanted & set(BUILD_CHECKS):
                checker.ran(cid, ".", "skipped", "no CSS found in the build directory")
    if wanted & set(ASSET_CHECKS):
        assets = records.get("assets")
        if assets is None:
            report.diagnostics.append("no Assets record in the records directory: asset checks not run")
            absent = absent_record_target(args.records, records)
            checker.targets[absent] = Path(absent)
            for cid in wanted & set(ASSET_CHECKS):
                checker.ran(cid, absent, "unavailable")
        else:
            target = record_file(args.records, assets)
            checker.targets[target] = Path(target)
            if not assets.get("entries") and not (build and build.images):
                for cid in wanted & set(ASSET_CHECKS):
                    checker.ran(cid, target, "skipped", "text-led site: no assets recorded and no images in the build")
                report.diagnostics.append("assets record has no entries and the build references no images")
            else:
                if not assets.get("entries"):
                    report.diagnostics.append("assets record has no entries")
                checker.asset_checks(assets, target, root, build)
                for cid in ASSET_CHECKS:
                    if cid not in wanted:
                        for key in [k for k in checker.results if k[0] == cid]:
                            del checker.results[key]

    collapse_stylesheets(checker)
    accepted = sw_records.accept_findings(
        report, lambda loc: checker.targets.get(loc) or (checker.build_root or root) / loc,
        args.record, args.records, root)
    checks = [{"check_id": c, "target": t, "result": r} for (c, t), r in sorted(checker.results.items())]
    present = {c["result"] for c in checks}
    if any(f["severity"] == "defect" for f in report.findings) or "failed" in present:
        result = "failed"
    elif "unavailable" in present:
        result = "unavailable"
    elif present and present <= {"skipped"}:
        result = "skipped"
    elif not checks:
        result = "skipped"
    else:
        result = "passed"
    mode = "production" if args.release else "mockup"
    payload = {"checks": checks, "release_mode": args.release, "mode": mode,
               "modes_written": {cid: record_mode(args, cid) for cid in sorted({c["check_id"] for c in checks})}}
    if "style.tracking" in wanted:
        payload["tracking_unclassified"] = checker.tracking_unclassified
    if "design.token-drift" in wanted:
        payload["tokens"] = {"recorded": len(tokens), "found": checker.matched, "values_compared": checker.compared}
    if "style.contrast" in wanted:
        payload["contrast_pairs"] = checker.pairs
    if accepted is not None:
        payload["accepted"] = accepted
    if args.evidence_out:
        out = {"tool": TOOL, "tool_version": TOOL_VERSION, "target": report.target, "result": result,
               "run": {"site": args.site, "theme": args.theme, "records": args.records, "release": checker.release},
               "findings": report.findings, "diagnostics": report.diagnostics, "checks": checks,
               **({"accepted": accepted} if accepted is not None else {}),
               "timestamp": sw_records.now_iso(), "duration_ms": int((time.monotonic() - started) * 1000)}
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        sw_records.write_json_atomic(args.evidence_out, out)
    if args.record:
        code = record_all(args, root, checker, checks, report)
        if code:
            return code
        payload["evidence_kept"] = getattr(args, "evidence_kept", True)
    return report.emit(result, payload)


LIMITATIONS = {
    "design.token-drift": "compares names and recorded values only; not whether pages use the tokens",
    "design.raw-literals": "colour, spacing and duration literals in stylesheets only; inline style attributes "
                           "are not read; rem is compared with tokens at 16px",
    "style.contrast": "static pairs only (declared pairs judged, inferred pairs warned); stacked backgrounds, "
                      "images and inherited colours need browser.contrast",
    "style.tracking": "role from selector and merged declarations; text length is not known statically",
    "layout.grid-items": "static: generated boxes on grid containers only; rendered layout needs visual.measure",
    "layout.spacing-reset": "static source order; cascade layers and specificity are not modelled; "
                            "rendered gaps need visual.measure",
    "assets.rights": "checks the record's fields, not that a licence is genuine",
}


RELEASE_SENSITIVE = ("assets.rights", "assets.local-path", "assets.final")   # --release changes what they judge


def record_mode(args, check_id):
    """The collection mode of a record: a release-sensitive check is production with --release (or --mode
    production) and mockup without it; any other check (same criteria in both modes) carries no mode, so it
    counts for both gates. Which gates require a check is required_checks[].modes, set with `require`."""
    if check_id in RELEASE_SENSITIVE:
        return "production" if args.release else "mockup"
    return None


def label_tracking(checker, design, report):
    """The design record's accepted label tracking (e.g. `0.16em`) replaces the default maximum."""
    raw = design.get("label_tracking_max")
    if raw is None or EMPTY_FIELD.match(raw):
        return
    m = re.fullmatch(r"\s*(\d*\.?\d+)\s*(?:em)?\s*(?:[(\u2014-].*)?", raw)
    if not m:
        report.diagnostics.append(f"label_tracking_max {raw!r} is not an em value; the default "
                                  f"{LABEL_TRACKING_MAX:g}em is used")
        return
    checker.label_max, checker.label_source = float(m.group(1)), "design"


CSS_SET = "**/*.css"     # one target for every stylesheet of the build, so hashed file names keep their pair
RESULT_WEIGHT = {"passed": 0, "skipped": 1, "unavailable": 2, "failed": 3}


def css_set_pattern(root, build_root):
    rel = sw_records.project_rel(root, build_root)
    return CSS_SET if rel in ("", ".") else f"{rel}/{CSS_SET}"


def collapse_stylesheets(checker):
    """Fold the per-stylesheet results into the build's CSS-set target. A build that renames hashed
    stylesheets then keeps the same check pairs; findings keep naming the sheet they were found in."""
    if CSS_SET not in checker.targets:
        return
    for (cid, t) in [k for k in checker.results if k[1].endswith(".css")]:
        result = checker.results.pop((cid, t))
        held = checker.results.get((cid, CSS_SET))
        if held is None or RESULT_WEIGHT.get(result, 3) > RESULT_WEIGHT.get(held, 3):
            checker.results[(cid, CSS_SET)] = result
        checker.defects.setdefault((cid, CSS_SET), []).extend(checker.defects.pop((cid, t), []))
        reason = checker.skip_reasons.pop((cid, t), None)
        if reason:
            checker.skip_reasons.setdefault((cid, CSS_SET), reason)
    for u in checker.tracking_unclassified:
        if u["target"].endswith(".css"):
            u["target"] = CSS_SET


def record_inputs(checker, check_id, target, root):
    """Files besides the target that a check read (evidence-contract.md, "Dependency fingerprints"):
    token drift and asset checks compare a record with the build; stylesheet checks resolve tokens across
    every sheet, so the CSS set and each page with inline styles is an input of the others (never the
    whole build folder, which would go stale on any rebuild); raw literals also read the design
    record's token names."""
    deps = []
    sheet_targets = [t for t in checker.targets if t == CSS_SET or t in getattr(checker, "inline_sheets", ())]
    if target in [checker.targets[t] for t in sheet_targets]:
        for t in sheet_targets:
            if checker.targets[t] != target:
                deps.append(sw_records.project_rel(root, checker.targets[t]) if t != CSS_SET else
                            css_set_pattern(root, checker.build_root))
    elif checker.build_root is not None and checker.build_root.resolve() != target.resolve():
        deps.append(checker.build_root)
    if check_id == "design.raw-literals" and checker.design_path is not None:
        deps.append(checker.design_path)
    if check_id == "style.tracking" and checker.design_path is not None:
        deps.append(checker.design_path)   # label_tracking_max (or its absence) decides the label threshold
    return deps


def record_all(args, root, checker, checks, report):
    evidence = Path(args.evidence_out)
    try:
        evidence_rel = evidence.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        evidence_rel = str(evidence)
    entries = []
    for c in checks:
        path = checker.targets.get(c["target"])
        if path is None:
            report.diagnostics.append(f"no path known for target {c['target']}")
            return report.emit("error")
        try:
            target_rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            report.diagnostics.append(f"target {path} is outside the project root {root}")
            return report.emit("error")
        found = checker.defects.get((c["check_id"], c["target"]), [])
        argv = ["record", args.record, "--root", str(root), "--check-id", c["check_id"],
                "--target", target_rel, "--result", c["result"], "--method", "automated",
                "--tool-and-version", f"{TOOL} {TOOL_VERSION}", "--evidence-path", evidence_rel,
                "--finding", "; ".join(found)[:400] or "no defects found by the static rules",
                "--limitations", LIMITATIONS.get(c["check_id"], "static source check; nothing was rendered")]
        for dep in record_inputs(checker, c["check_id"], path, root):
            argv += ["--input", str(dep)]
        unclassified = [u["selector"] for u in checker.tracking_unclassified if u["target"] == c["target"]]
        if c["check_id"] == "style.tracking" and unclassified:
            argv[argv.index("--limitations") + 1] = (
                f"{LIMITATIONS['style.tracking']}; {len(unclassified)} rule(s) with no element in the selector "
                f"could not be given a role ({', '.join(unclassified[:4])}{', …' if len(unclassified) > 4 else ''}): "
                "confirm them in browser review")[:600]
        mode = record_mode(args, c["check_id"])
        if mode:
            argv += ["--mode", mode]
        for given in sw_records.exclusions_within(root, path, args.exclude):
            argv += ["--exclude", given]
        if args.allow_website_exclusion:
            argv.append("--allow-website-exclusion")
        if c["result"] == "skipped":
            reason = checker.skip_reasons.get((c["check_id"], c["target"])) or "; ".join(report.diagnostics)
            argv += ["--skip-reason", reason[:300] or "not applicable to this run",
                     "--required-or-optional", "optional"]
        if args.require and c["result"] != "skipped":   # a skipped check is not required in this run
            argv.append("--require")
        entries.append(argv[4:])
    # one validated, atomic write for the whole run; a refused entry leaves the file untouched
    def resolve(loc):
        return checker.targets.get(loc) or (checker.build_root or root) / loc

    if entries and sw_records.record_many(args.record, root, entries, report, resolve=resolve) is None:
        report.diagnostics.append("recording failed: nothing was written")
        return report.emit("error")
    if entries:
        args.evidence_kept = sw_records.keep_cited_evidence(args.record, evidence_rel, evidence)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # report, never pass silently
        r = DesignReport("")
        r.diagnostics.append(f"{type(exc).__name__}: {exc}")
        sys.exit(r.emit("error"))
