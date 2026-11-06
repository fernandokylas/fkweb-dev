#!/usr/bin/env python3
"""Sitewright page capture from a local server (stdlib only).

Usage:
  sw_capture.py BASE_URL --out DIR --route / [--route /menu/ ...] [--not-found PATH]
                [--timeout SECONDS] [--replace] [--evidence-out PATH]

Fetches each route from a server on this machine (loopback only: 127.0.0.1, ::1 or localhost),
saves the server-rendered HTML as DIR/<route>/index.html, and writes DIR/routes.json so
sw_site_check.py --routes can check the pages. Used for WordPress (and any server-rendered
site) where the built pages only exist when a runtime renders them.

To keep the static link checks meaningful, the capture:
  - rewrites same-origin absolute URLs in <a href>, resource <link href> (stylesheet, preload,
    modulepreload, icon), <script src>, <img src/srcset> and <source src/srcset> to root-relative
    paths; canonical, feed, REST and other metadata links stay absolute and are fetched and
    reported instead of rewritten;
  - mirrors every same-origin stylesheet, script, image and icon those pages load into DIR,
    by path, without its query string.

--not-found PATH fetches a URL that should not exist; when the server answers 404 the page is
saved as DIR/404.html. Any other status is a failed result, reported with the status. PATH is
resolved against BASE_URL and must stay on its origin (scheme, host and port): a local query such
as /?p=999999 is fine, another host is refused before any request.

Containment: every request is checked against the BASE_URL origin, whoever asks for it. Routes are
decoded before use, and a route with a `.` or `..` segment, a backslash or a NUL (in any spelling,
e.g. /%2e%2e/) is refused before anything is written. Every page and asset destination is resolved,
symlinks included, and must stay inside DIR; an asset that can't is reported and not fetched.

Routes must answer 200 without a redirect; redirects are reported, never followed.
What it does not establish: anything a browser has to run (scripts, layout, focus), or how a
production server behaves. The rewriting is recorded in the report's limitations.

Output: one JSON object on stdout. Exit: 0 passed, 1 failed, 2 error.
"""
import argparse
import html
import ipaddress
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sw_records  # noqa: E402

TOOL = "sw_capture"
TOOL_VERSION = "2"
MAX_BYTES = 10_000_000
MARKER = ".sw-capture"
TAG = re.compile(r"<(a|link|script|img|source)\b[^>]*>", re.IGNORECASE)
ATTR = re.compile(r"""(\s)(href|src|srcset)(\s*=\s*)("([^"]*)"|'([^']*)')""", re.IGNORECASE)
REL = re.compile(r"""\brel\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)
RESOURCE_RELS = {"stylesheet", "preload", "modulepreload", "icon", "apple-touch-icon"}
LIMITATIONS = ("pages fetched from a local runtime; same-origin absolute URLs rewritten to root-relative "
               "and assets mirrored without query strings; scripts not executed; a production server "
               "may differ")


class CaptureReport(sw_records.Report):
    def emit(self, result, extra=None, code=None):
        return super().emit(result, {"tool": TOOL, "tool_version": TOOL_VERSION, **(extra or {})}, code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def origin_of(url):
    p = urlsplit(url)
    return p.scheme.lower(), (p.netloc or "").lower()


def fetch(url, timeout, base):
    """Return (status, headers, body bytes). Redirects come back as their own status.
    Raises ValueError for any URL off the BASE_URL origin, so no caller can reach another host."""
    if origin_of(url) != origin_of(base) or origin_of(url)[0] not in ("http", "https"):
        raise ValueError(f"refusing {url}: requests stay on {base}")
    req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL}/{TOOL_VERSION}", "Accept": "text/html,*/*"})
    try:
        with OPENER.open(req, timeout=timeout) as resp:
            body = resp.read(MAX_BYTES + 1)
            return resp.status, resp.headers, body
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BYTES + 1) if exc.fp else b""
        return exc.code, exc.headers, body


def route_problem(route):
    """Why a route can't be captured safely, or None. The check runs on the decoded path, so
    %2e%2e, %2f and %5c spellings are caught as well as plain ones."""
    decoded = unquote(urlsplit(route).path)
    if "\\" in decoded or "\x00" in decoded:
        return "contains a backslash or NUL"
    if any(seg in (".", "..") for seg in decoded.split("/")):
        return "contains a . or .. segment"
    return None


def route_file(route):
    path = unquote(urlsplit(route).path).strip("/")
    return f"{path}/index.html" if path else "index.html"


def contained(out, rel):
    """The resolved destination for `rel` under `out`, or None when it would leave `out`
    (.. segments, an absolute path, or a symlink anywhere on the way)."""
    rel = str(rel)
    if not rel or rel.startswith("/") or "\x00" in rel or "\\" in rel:
        return None
    root = out.resolve()
    target = (root / rel).resolve()
    if target == root or root not in target.parents:
        return None
    return target


def safe_join(out, url_path):
    rel = unquote(url_path).lstrip("/")
    if not rel or rel.endswith("/"):
        return None
    return contained(out, rel)


class Capture:
    def __init__(self, base, out, timeout, report):
        self.base = base
        self.out = out
        self.timeout = timeout
        self.report = report
        self.assets = {}      # url path -> status
        self.metadata = {}    # absolute url -> status
        self.pending = []     # (absolute url, url path)

    def same_origin(self, absolute):
        return origin_of(absolute) == origin_of(self.base)

    def relative(self, absolute):
        p = urlsplit(absolute)
        rel = p.path or "/"
        if p.query:
            rel += "?" + p.query
        if p.fragment:
            rel += "#" + p.fragment
        return rel

    def rewrite(self, page_url, text):
        def tag_sub(m):
            tag = m.group(0)
            name = m.group(1).lower()
            rels = set()
            if name == "link":
                rm = REL.search(tag)
                rels = set((next(g for g in rm.groups()[1:] if g is not None) if rm else "").lower().split())
            resource = name in ("script", "img", "source") or (name == "link" and rels & RESOURCE_RELS)

            def attr_sub(a):
                attr = a.group(2).lower()
                raw = a.group(5) if a.group(5) is not None else a.group(6)
                if name == "a" and attr != "href":
                    return a.group(0)
                if attr == "srcset":
                    items = []
                    for part in raw.split(","):
                        bits = part.strip().split(None, 1)
                        if not bits:
                            continue
                        bits[0] = self.ref(page_url, bits[0], True)
                        items.append(" ".join(bits))
                    new = ", ".join(items)
                elif name == "link" and not resource:
                    absolute = urljoin(page_url, html.unescape(raw))
                    if self.same_origin(absolute) and "canonical" not in rels:
                        self.metadata.setdefault(absolute, None)
                    return a.group(0)
                else:
                    new = self.ref(page_url, raw, bool(resource))
                q = '"' if a.group(5) is not None else "'"
                return f"{a.group(1)}{a.group(2)}{a.group(3)}{q}{new}{q}"

            return ATTR.sub(attr_sub, tag)

        return TAG.sub(tag_sub, text)

    def ref(self, page_url, raw, resource):
        value = html.unescape(raw.strip())
        if value.startswith(("data:", "mailto:", "tel:", "javascript:", "#")) or not value:
            return raw
        absolute = urljoin(page_url, value)
        if not self.same_origin(absolute):
            return raw
        rel = self.relative(absolute)
        if resource:
            path = urlsplit(absolute).path
            if path not in self.assets:
                self.assets[path] = None
                self.pending.append((absolute, path))
        return html.escape(rel, quote=True)

    def mirror_assets(self):
        while self.pending:
            absolute, path = self.pending.pop(0)
            target = safe_join(self.out, path)
            if target is None:
                self.assets[path] = "skipped"
                self.report.add("capture.assets", path, "warning", "asset path cannot be stored as a file",
                                "check the reference by hand", kind="convention")
                continue
            status, _, body = fetch(absolute, self.timeout, self.base)
            self.assets[path] = status
            if status != 200:
                self.report.add("capture.assets", path, "defect", f"asset returned HTTP {status}",
                                "fix the enqueue or the reference")
                continue
            if len(body) > MAX_BYTES:
                self.report.add("capture.assets", path, "defect", f"asset larger than {MAX_BYTES} bytes",
                                "check the asset")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)

    def check_metadata(self):
        for absolute in sorted(self.metadata):
            status, _, _ = fetch(absolute, self.timeout, self.base)
            self.metadata[absolute] = status
            if status >= 400:
                self.report.add("capture.metadata-links", self.relative(absolute), "warning",
                                f"head link returned HTTP {status}", "check the feed, REST or alternate link",
                                kind="convention")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sw_capture.py", description=__doc__.splitlines()[0])
    parser.add_argument("base_url")
    parser.add_argument("--out", required=True, help="capture directory (created; see --replace)")
    parser.add_argument("--route", action="append", default=[], help="route to capture, e.g. / or /menu/")
    parser.add_argument("--not-found", help="path that should answer 404; saved as 404.html")
    parser.add_argument("--timeout", type=float, default=15.0, help="seconds per request (default 15)")
    parser.add_argument("--replace", action="store_true", help="replace an earlier capture in --out")
    parser.add_argument("--evidence-out", help="also write this report to PATH")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    started = time.monotonic()
    report = CaptureReport(args.base_url)
    parts = urlsplit(args.base_url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        report.diagnostics.append("BASE_URL must be an http(s) URL")
        return report.emit("error")
    if not is_loopback(parts.hostname):
        report.diagnostics.append(f"refusing {parts.hostname}: capture only reads servers on this machine")
        return report.emit("error")
    if not args.route:
        report.diagnostics.append("give at least one --route")
        return report.emit("error")
    bad = [r for r in args.route if not r.startswith("/") or urlsplit(r).query or urlsplit(r).fragment]
    if bad:
        report.diagnostics.append(f"routes must be paths starting with / and without query or fragment: {bad}")
        return report.emit("error")
    unsafe = [f"{r} ({route_problem(r)})" for r in args.route if route_problem(r)]
    if unsafe:
        report.diagnostics.append(f"refusing route outside the capture directory: {unsafe}")
        return report.emit("error")
    base = args.base_url.rstrip("/")
    not_found_url = None
    if args.not_found:
        not_found_url = urljoin(base + "/", args.not_found)
        if origin_of(not_found_url) != origin_of(base):
            report.diagnostics.append(f"refusing --not-found {args.not_found}: it must stay on {base}")
            return report.emit("error")
    if not 0 < args.timeout <= 300:
        report.diagnostics.append("--timeout must be between 0 and 300 seconds")
        return report.emit("error")
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        if not args.replace:
            report.diagnostics.append(f"{out} is not empty; pass --replace to overwrite an earlier capture")
            return report.emit("error")
        if not (out / MARKER).is_file():
            report.diagnostics.append(f"{out} was not made by {TOOL}; refusing to replace it")
            return report.emit("error")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / MARKER).write_text(f"{TOOL} {TOOL_VERSION}\n", encoding="utf-8")

    cap = Capture(base, out, args.timeout, report)
    routes, pages = {}, []
    try:
        for route in args.route:
            url = base + route
            status, headers, body = fetch(url, args.timeout, base)
            entry = {"route": route, "status": status}
            if status in (301, 302, 303, 307, 308):
                entry["location"] = headers.get("Location", "")
            pages.append(entry)
            if status != 200:
                report.add("capture.routes", route, "defect",
                           f"HTTP {status}" + (f" to {entry['location']}" if "location" in entry else ""),
                           "the route must render with status 200")
                continue
            if len(body) > MAX_BYTES:
                report.add("capture.routes", route, "defect", "page larger than the capture limit", "check the page")
                continue
            charset = headers.get_content_charset() or "utf-8"
            text = cap.rewrite(url, body.decode(charset, errors="replace"))
            rel = route_file(route)
            if rel in routes:
                report.add("capture.routes", route, "defect", f"two routes map to {rel}", "remove the duplicate")
                continue
            dest = contained(out, rel)
            if dest is None:
                report.add("capture.routes", route, "defect", f"{rel} would be stored outside {out}",
                           "capture a route that maps inside the capture directory")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            routes[rel] = route if route.endswith("/") else route + "/"
            entry["file"] = rel
        not_found = None
        if args.not_found:
            url = not_found_url
            status, headers, body = fetch(url, args.timeout, base)
            not_found = {"path": args.not_found, "status": status}
            if status in (301, 302, 303, 307, 308):
                not_found["location"] = headers.get("Location", "")
            if status == 404:
                charset = headers.get_content_charset() or "utf-8"
                dest = contained(out, "404.html")
                if dest is None:
                    raise ValueError(f"404.html would be stored outside {out}")
                dest.write_text(cap.rewrite(url, body.decode(charset, errors="replace")), encoding="utf-8")
                routes["404.html"] = "/404.html"
                not_found["file"] = "404.html"
            else:
                report.add("capture.not-found", args.not_found, "defect",
                           f"expected HTTP 404, got {status}" + (f" to {not_found['location']}" if "location" in not_found else ""),
                           "missing URLs must answer 404 with the site's not-found page")
        cap.mirror_assets()
        cap.check_metadata()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        report.diagnostics.append(f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}")
        return report.emit("error")

    sw_records.write_json_atomic(out / "routes.json", routes)
    result = "failed" if any(f["severity"] == "defect" for f in report.findings) else "passed"
    payload = {"out": str(out), "routes_file": str(out / "routes.json"), "pages": pages,
               "not_found": not_found, "assets": cap.assets, "metadata_links": cap.metadata,
               "limitations": LIMITATIONS}
    if args.evidence_out:
        record = {"tool": TOOL, "tool_version": TOOL_VERSION, "target": args.base_url, "result": result,
                  "findings": report.findings, "diagnostics": report.diagnostics, **payload,
                  "timestamp": sw_records.now_iso(), "duration_ms": int((time.monotonic() - started) * 1000)}
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        sw_records.write_json_atomic(args.evidence_out, record)
    return report.emit(result, payload)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # report, never pass silently
        r = CaptureReport("")
        r.diagnostics.append(f"{type(exc).__name__}: {exc}")
        sys.exit(r.emit("error"))
