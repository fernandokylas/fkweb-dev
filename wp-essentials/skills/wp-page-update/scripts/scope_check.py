#!/usr/bin/env python3
"""Scope-regression check for targeted revisions of an HTML page.

Parses each page into a tree, then selects *regions*: landmark/sectioning elements
(<header> <nav> <main>* <section> <article> <aside> <footer> <form> <dialog>) and any
element with an id or data-section that does not itself contain such elements. Wrapper
elements (a <div class="page">, <main>, <body>) are transparent, so regions are found at
any depth. Body content that belongs to no region is collected as "(unsectioned)" so
nothing is silently ignored. Each region is named by id, aria-label, data-section,
aria-labelledby or first heading, normalised for whitespace and compared before/after.

Global code — <head>, and <style>/<script> outside any region — is compared separately.
A change there affects every section, so it FAILS unless explicitly authorised with
--allow-global (or "global" in --allow); a shared-token change may be technically
necessary, but it must be declared, never silent.

Usage:
  scope_check.py before.html after.html --allow hero,testimonials,faq
  scope_check.py before.html after.html --allow hero --allow-global
  scope_check.py before.html after.html --allow hero --json
  scope_check.py before.html after.html --allow pricing --loose   # substring match

Get before/after HTML with e.g. `curl -s URL > before.html` (or a browser "save page")
before and after the edit. On WordPress the rendered page is what matters, not post_content.

Matching: an --allow token matches a region when it equals the region's id, aria-label,
data-section, one of its classes, its heading, or its tag. --loose matches substrings
instead (short tokens like "a" then match almost everything; use with care).
Exit 0 when every changed/added/removed region is allowed and no unauthorised global
change exists; 1 on out-of-scope change; 2 on usage error.

Limitations (deterministic HTML diff — complement it with browser review):
  * It compares two HTML files. External stylesheets/scripts and other pages are not
    read; for multi-file builds compare those with `git diff` and apply the same rule.
  * A change in an *allowed* region that alters shared behaviour (a class rule inside an
    allowed section's <style scoped>, a script that targets other sections) passes here.
  * It sees markup, not pixels: cascade side-effects, font loading, images and layout are
    for a rendered before/after comparison in a browser.
  * Regions without id/heading are named by tag and position; renaming or reordering
    shows as removed+added, which is flagged (never hidden).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REGION_TAGS = {"header", "nav", "section", "article", "aside", "footer", "form", "dialog"}
TRANSPARENT = {"html", "body", "main", "div", "span"}
HEADINGS = {"h1", "h2", "h3", "h4"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
LOOSE = "(unsectioned)"


class Node:
    __slots__ = ("tag", "attrs", "children", "start", "end")

    def __init__(self, tag: str, attrs: dict, start: str):
        self.tag, self.attrs, self.start = tag, attrs, start
        self.children: list = []  # Node | str
        self.end = "" if tag in VOID else f"</{tag}>"

    def serialize(self) -> str:
        return self.start + "".join(c.serialize() if isinstance(c, Node) else c for c in self.children) + self.end

    def text(self) -> str:
        return "".join(c.text() if isinstance(c, Node) else c for c in self.children)

    def iter(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.iter()

    def find_first(self, tags: set[str]):
        for n in self.iter():
            if n.tag in tags:
                return n
        return None

    def has_region_descendant(self) -> bool:
        return any(n.tag in REGION_TAGS for n in self.iter())


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = Node("#root", {}, "")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, self.get_starttag_text() or f"<{tag}>")
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, {k: (v or "") for k, v in attrs}, self.get_starttag_text() or f"<{tag}/>"))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def handle_entityref(self, name):
        self.stack[-1].children.append(f"&{name};")

    def handle_charref(self, name):
        self.stack[-1].children.append(f"&#{name};")

    def handle_comment(self, data):
        self.stack[-1].children.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.stack[-1].children.append(f"<!{decl}>")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def digest(s: str) -> str:
    return hashlib.sha1(norm(s).encode("utf-8")).hexdigest()[:12]


def region_name(node: Node, order: int) -> str:
    for key in ("id", "aria-label", "data-section", "aria-labelledby"):
        if node.attrs.get(key, "").strip():
            return node.attrs[key].strip()
    h = node.find_first(HEADINGS)
    if h is not None and norm(h.text()):
        return norm(h.text())[:60]
    return f"{node.tag}#{order}"


def region_keys(node: Node, name: str) -> list[str]:
    keys = [name, node.tag]
    for key in ("id", "aria-label", "data-section", "class"):
        if node.attrs.get(key):
            keys.append(node.attrs[key])
    h = node.find_first(HEADINGS)
    if h is not None:
        keys.append(norm(h.text()))
    return [k.lower() for k in keys]


def is_region(node: Node) -> bool:
    if node.tag in REGION_TAGS:
        return True
    if node.attrs.get("id") or node.attrs.get("data-section"):
        return not node.has_region_descendant()
    return False


def collect(root: Node) -> tuple[list[tuple[str, Node]], dict[str, list[str]], list[str]]:
    """Return (regions as (name, node)), global blocks, loose fragments."""
    regions: list[tuple[str, Node]] = []
    globals_: dict[str, list[str]] = {"head": [], "style": [], "script": []}
    loose: list[str] = []
    counter = {"n": 0}

    def walk(node: Node):
        for child in node.children:
            if isinstance(child, str):
                if norm(child):
                    loose.append(child)
                continue
            if child.tag == "head":
                globals_["head"].append(child.serialize())
            elif child.tag in ("style", "script"):
                globals_[child.tag].append(child.serialize())
            elif is_region(child):
                counter["n"] += 1
                regions.append((region_name(child, counter["n"]), child))
            elif child.tag in TRANSPARENT or child.has_region_descendant():
                walk(child)
            else:
                loose.append(child.serialize())

    walk(root)
    return regions, globals_, loose


def split(path: Path) -> tuple[dict[str, dict], dict[str, str]]:
    tb = TreeBuilder()
    tb.feed(path.read_text(encoding="utf-8", errors="replace"))
    tb.close()
    regions, globals_, loose = collect(tb.root)
    named: dict[str, dict] = {}
    for name, node in regions:
        key, i = name, 2
        while key in named:
            key = f"{name}#{i}"
            i += 1
        named[key] = {"digest": digest(node.serialize()), "keys": region_keys(node, name)}
    if loose:
        named[LOOSE] = {"digest": digest("".join(loose)), "keys": [LOOSE, "unsectioned", "loose"]}
    return named, {k: digest("".join(v)) for k, v in globals_.items()}


LOOSE_MATCH = False


def allowed(keys: list[str], allow: list[str]) -> bool:
    if LOOSE_MATCH:
        return any(tok in k for tok in allow for k in keys)
    words = set(keys)
    for k in keys:
        words.update(k.split())
    return any(tok in words for tok in allow)


def compare(before: Path, after: Path, allow: list[str], allow_global: bool) -> dict:
    b, b_glob = split(before)
    a, a_glob = split(after)
    findings = []
    for name, r in b.items():
        if name not in a:
            findings.append({"region": name, "change": "removed", "allowed": allowed(r["keys"], allow)})
        elif r["digest"] != a[name]["digest"]:
            findings.append({"region": name, "change": "changed", "allowed": allowed(r["keys"], allow) or allowed(a[name]["keys"], allow)})
    for name, r in a.items():
        if name not in b:
            findings.append({"region": name, "change": "added", "allowed": allowed(r["keys"], allow)})
    global_changes = [k for k in ("head", "style", "script") if b_glob.get(k) != a_glob.get(k)]
    out_of_scope = [f for f in findings if not f["allowed"]]
    if global_changes and not allow_global:
        out_of_scope += [{"region": f"<{g}>", "change": "changed", "allowed": False, "global": True} for g in global_changes]
    return {
        "before": str(before), "after": str(after), "allow": allow, "allow_global": allow_global,
        "regions_before": list(b), "regions_after": list(a),
        "findings": findings, "global_changes": global_changes,
        "out_of_scope": out_of_scope, "pass": not out_of_scope,
    }


def render(res: dict) -> str:
    lines = [f"# Scope check — {'PASS' if res['pass'] else 'FAIL'}", "",
             f"before: `{res['before']}`  after: `{res['after']}`  allow: {', '.join(res['allow']) or '(none)'}"
             + ("  + global" if res["allow_global"] else ""), ""]
    if not res["findings"]:
        lines.append("No region changed.")
    else:
        lines += ["| Region | Change | In scope |", "|---|---|---|"]
        for f in res["findings"]:
            lines.append(f"| {f['region']} | {f['change']} | {'yes' if f['allowed'] else '**NO**'} |")
    if res["global_changes"]:
        tag = "authorised (--allow-global)" if res["allow_global"] else "**NOT authorised** — affects every section"
        lines += ["", "Global code changed: " + ", ".join(f"`<{g}>`" for g in res["global_changes"]) + f" — {tag}. "
                  "Shared styles/scripts may be technically necessary; if so, re-run with --allow-global and tell the user what changed and why."]
    if res["out_of_scope"]:
        lines += ["", "Out-of-scope changes: " + ", ".join(f"{f['region']} ({f['change']})" for f in res["out_of_scope"]) +
                  ". Revert them, or explain each to the user and get it approved before publishing."]
    lines += ["", f"Regions before: {len(res['regions_before'])} · after: {len(res['regions_after'])}",
              "This is a markup diff. Also compare the rendered page (cascade, fonts, images, layout) in a browser."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--allow", default="", help="comma-separated region names allowed to change (exact match on id/aria-label/data-section/class/heading/tag)")
    ap.add_argument("--loose", action="store_true", help="match --allow tokens as substrings")
    ap.add_argument("--allow-global", action="store_true", help="authorise changes to <head>, and <style>/<script> outside regions")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    global LOOSE_MATCH
    LOOSE_MATCH = args.loose
    b, a = Path(args.before), Path(args.after)
    if not b.is_file() or not a.is_file():
        print("both before and after must be existing HTML files", file=sys.stderr)
        return 2
    allow = [t.strip().lower() for t in args.allow.split(",") if t.strip()]
    allow_global = args.allow_global or "global" in allow
    allow = [t for t in allow if t != "global"]
    res = compare(b, a, allow, allow_global)
    print(json.dumps(res, indent=2) if args.json else render(res))
    return 0 if res["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
