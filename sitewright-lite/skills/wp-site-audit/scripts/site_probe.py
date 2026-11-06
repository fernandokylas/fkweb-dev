#!/usr/bin/env python3
"""Read-only HTTP probe of a WordPress site, from the outside.

Sends only GET requests, only to the origin you give (redirects to another host are not
followed), with a timeout and a size cap per response. Everything fetched is untrusted
data: it is parsed, never executed, and quoted values are truncated and cleaned.

Checks: home page basics (status, title, description, h1, lang, viewport, canonical,
noindex, generator version, extractable text ratio), http->https redirect, security
headers, robots.txt, sitemap (and a sample of its URLs), REST API namespaces and the
public users endpoint, exposed files (readme.html, debug.log, xmlrpc.php), author
enumeration, a real 404, and internal links on the home page.

Usage:
  site_probe.py https://example.com
  site_probe.py https://example.com --stage launch --sample 20 --json
  site_probe.py http://localhost:8089 --out docs/website/evidence/site-probe.json

--stage staging (default) reports "discourage search engines" as expected; --stage launch
fails it. Exit 0 no failures, 1 at least one failure, 2 usage error or site unreachable.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

TIMEOUT = 15
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 5
UA = "wp-essentials-site-probe/0.1 (read-only)"
SKIP_TEXT = {"script", "style", "noscript", "template", "svg", "head"}


def clean(value, limit: int = 120) -> str:
    s = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value)).replace("|", "/").replace("`", "'").strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


class Response:
    def __init__(self, url, status=None, headers=None, body=b"", error=None, redirects=None, truncated=False):
        self.url, self.status, self.headers, self.body = url, status, headers or {}, body
        self.error, self.redirects, self.truncated = error, redirects or [], truncated

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def header(self, name: str) -> str:
        return self.headers.get(name.lower(), "")


DEFAULT_PORTS = {"http": 80, "https": 443}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Fetcher:
    def __init__(self, origin: str):
        u = urllib.parse.urlsplit(origin)
        if u.scheme not in ("http", "https") or not u.hostname:
            raise ValueError(f"not an http(s) origin: {origin!r}")
        self.scheme, self.host = u.scheme, u.hostname.lower()
        self.port = u.port
        self.base = f"{u.scheme}://{u.netloc}"
        self.opener = urllib.request.build_opener(_NoRedirect)
        self.count = 0

    def same_site(self, url: str) -> bool:
        """Same host and same effective port; http and https may swap only on their default ports."""
        u = urllib.parse.urlsplit(url)
        if u.scheme not in DEFAULT_PORTS or (u.hostname or "").lower() != self.host:
            return False
        try:
            port = u.port or DEFAULT_PORTS[u.scheme]
        except ValueError:
            return False
        if u.scheme == self.scheme:
            return port == (self.port or DEFAULT_PORTS[self.scheme])
        return port == DEFAULT_PORTS[u.scheme] and (self.port or DEFAULT_PORTS[self.scheme]) == DEFAULT_PORTS[self.scheme]

    def url(self, path: str) -> str:
        return urllib.parse.urljoin(self.base + "/", path.lstrip("/")) if not path.startswith("http") else path

    def get(self, path_or_url: str, follow: bool = True) -> Response:
        url = self.url(path_or_url)
        if not self.same_site(url):
            return Response(url, error="refused: not the probed site")
        chain = []
        for _ in range(MAX_REDIRECTS + 1):
            self.count += 1
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"}, method="GET")
            try:
                resp = self.opener.open(req, timeout=TIMEOUT)
                status, headers = resp.status, resp.headers
            except urllib.error.HTTPError as exc:
                resp, status, headers = exc, exc.code, exc.headers
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                return Response(url, error=clean(getattr(exc, "reason", exc)), redirects=chain)
            hdrs = {k.lower(): v for k, v in (headers.items() if headers else [])}
            if status in (301, 302, 303, 307, 308) and follow and "location" in hdrs:
                nxt = urllib.parse.urljoin(url, hdrs["location"])
                chain.append((status, nxt))
                try:
                    resp.close()
                except Exception:
                    pass
                if not self.same_site(nxt):
                    return Response(url, status, hdrs, error=f"redirect to another site not followed: {clean(nxt)}", redirects=chain)
                url = nxt
                continue
            try:
                body = resp.read(MAX_BYTES + 1) if resp else b""
            except Exception as exc:
                return Response(url, status, hdrs, error=clean(exc), redirects=chain)
            finally:
                try:
                    resp.close()
                except Exception:
                    pass
            return Response(url, status, hdrs, body[:MAX_BYTES], redirects=chain, truncated=len(body) > MAX_BYTES)
        return Response(url, error="too many redirects", redirects=chain)


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.lang, self.meta, self.links = "", "", {}, []
        self.canonical, self.h1, self.text = "", 0, []
        self._skip, self._in_title = 0, False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = a.get("href", "")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "h1":
            self.h1 += 1
        if tag in SKIP_TEXT:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in SKIP_TEXT and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.text.append(data.strip())


def parse(body: str) -> PageParser:
    p = PageParser()
    try:
        p.feed(body)
        p.close()
    except Exception:
        pass
    return p


def row(check, result, detail, evidence=""):
    return {"check": check, "result": result, "detail": detail, "evidence": clean(evidence, 200) if evidence else ""}


def check_home(f: Fetcher, stage: str):
    rows, r = [], f.get("/")
    if r.error or r.status is None:
        return [row("home", "failed", f"home page unreachable: {r.error}")], None
    rows.append(row("home.status", "passed" if r.status == 200 else "failed", f"HTTP {r.status}", r.url))
    if r.redirects:
        rows.append(row("home.redirects", "info", f"{len(r.redirects)} redirect(s)", " -> ".join(u for _, u in r.redirects)))
    p = parse(r.text)
    title = clean(" ".join(p.title.split()))
    rows.append(row("home.title", "passed" if title else "failed", "title present" if title else "no <title>", title))
    desc = p.meta.get("description", "")
    rows.append(row("home.meta_description", "passed" if desc else "warning", "present" if desc else "missing", desc))
    rows.append(row("home.h1", "passed" if p.h1 == 1 else "warning", f"{p.h1} <h1> element(s)"))
    rows.append(row("home.lang", "passed" if p.lang else "warning", p.lang or "no lang attribute on <html>"))
    rows.append(row("home.viewport", "passed" if "viewport" in p.meta else "failed",
                    "viewport meta present" if "viewport" in p.meta else "no viewport meta (not mobile-ready)"))
    rows.append(row("home.canonical", "passed" if p.canonical else "warning", p.canonical and clean(p.canonical) or "no canonical link"))
    robots = p.meta.get("robots", "").lower()
    if "noindex" in robots:
        rows.append(row("home.noindex", "failed" if stage == "launch" else "info", f"meta robots: {clean(robots)}"))
    gen = p.meta.get("generator", "")
    if re.search(r"\d+\.\d+", gen):
        rows.append(row("home.generator", "warning", "version number published in generator meta", gen))
    text = " ".join(p.text)
    words = len(text.split())
    ratio = len(text.encode()) / max(len(r.body), 1)
    res = "passed" if words >= 150 and ratio >= 0.05 else "warning"
    rows.append(row("home.text", res, f"{words} words of extractable text, text/HTML ratio {ratio:.1%}",
                    "low values suggest content only visible after JavaScript, or in images" if res == "warning" else ""))
    return rows, (r, p)


def check_https(f: Fetcher):
    rows = []
    if f.scheme != "https":
        if f.host not in ("localhost", "127.0.0.1", "::1"):
            rows.append(row("https", "failed", "site probed over http; use the https address"))
        return rows
    r = f.get(f"http://{f.host}{':' + str(f.port) if f.port and f.port != 443 else ''}/", follow=False)
    loc = r.header("location")
    if r.status in (301, 308) and loc.startswith("https://"):
        rows.append(row("https.redirect", "passed", f"http redirects to https ({r.status})"))
    elif r.status in (302, 307) and loc.startswith("https://"):
        rows.append(row("https.redirect", "warning", f"http redirects to https with a temporary {r.status}; use 301"))
    else:
        rows.append(row("https.redirect", "failed" if r.status else "unverified",
                        f"http did not redirect to https (status {r.status}, error {r.error})"))
    return rows


def check_headers(home: Response | None, f: Fetcher):
    if home is None:
        return []
    rows, h = [], home.headers
    if f.scheme == "https":
        rows.append(row("headers.hsts", "passed" if "strict-transport-security" in h else "warning",
                        "Strict-Transport-Security " + ("set" if "strict-transport-security" in h else "missing")))
    rows.append(row("headers.nosniff", "passed" if h.get("x-content-type-options", "").lower() == "nosniff" else "warning",
                    "X-Content-Type-Options: " + (h.get("x-content-type-options") or "missing")))
    framing = "x-frame-options" in h or "frame-ancestors" in h.get("content-security-policy", "")
    rows.append(row("headers.framing", "passed" if framing else "warning",
                    "clickjacking protection " + ("set" if framing else "missing (X-Frame-Options or CSP frame-ancestors)")))
    rows.append(row("headers.referrer", "passed" if "referrer-policy" in h else "info",
                    "Referrer-Policy: " + (h.get("referrer-policy") or "not set")))
    if re.search(r"\d", h.get("x-powered-by", "")):
        rows.append(row("headers.powered_by", "warning", "server software version disclosed", h["x-powered-by"]))
    return rows


def check_robots(f: Fetcher, stage: str):
    r = f.get("/robots.txt")
    if r.status != 200:
        return [row("robots", "warning", f"robots.txt not served (status {r.status}, {r.error or 'no error'})")], []
    lines = [ln.split("#", 1)[0].strip() for ln in r.text.splitlines()]
    sitemaps = [ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("sitemap:")]
    agent, block_all = None, False
    for ln in lines:
        low = ln.lower()
        if low.startswith("user-agent:"):
            agent = low.split(":", 1)[1].strip()
        elif low.startswith("disallow:") and agent == "*" and low.split(":", 1)[1].strip() == "/":
            block_all = True
    rows = [row("robots.blocks_all", ("failed" if stage == "launch" else "info") if block_all else "passed",
                "robots.txt disallows the whole site" if block_all else "robots.txt does not block the whole site")]
    rows.append(row("robots.sitemap", "passed" if sitemaps else "warning",
                    f"{len(sitemaps)} Sitemap line(s)" if sitemaps else "no Sitemap line in robots.txt", ", ".join(sitemaps)))
    return rows, sitemaps


LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)


def check_sitemap(f: Fetcher, declared: list[str], sample: int, stage: str):
    candidates = [u for u in declared if f.same_site(u)] + ["/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"]
    rows, found = [], None
    for c in candidates:
        r = f.get(c)
        if r.status == 200 and "<loc>" in r.text.lower():
            found = r
            break
    if found is None:
        note = "" if stage == "launch" else " (expected while search engines are discouraged: WordPress turns its sitemap off)"
        return [row("sitemap", "failed" if stage == "launch" else "warning",
                    "no XML sitemap at robots.txt Sitemap lines, /wp-sitemap.xml, /sitemap_index.xml or /sitemap.xml" + note)], []
    urls, children = [], []
    if "<sitemapindex" in found.text.lower():
        children = LOC.findall(found.text)
        for child in children[:10]:
            if not f.same_site(child):
                continue
            cr = f.get(child)
            if cr.status == 200:
                urls += LOC.findall(cr.text)
            if len(urls) >= 1000:
                break
    else:
        urls = LOC.findall(found.text)
    off = [u for u in urls if not f.same_site(u)]
    rows.append(row("sitemap", "passed" if urls else "failed",
                    f"{len(urls)} URL(s) from {len(children) or 1} sitemap file(s)", found.url))
    if off:
        rows.append(row("sitemap.other_host", "failed", f"{len(off)} sitemap URL(s) point at another host", off[0]))
    bad = []
    for u in [u for u in urls if f.same_site(u)][:sample]:
        r = f.get(u)
        if r.status != 200:
            bad.append(f"{u} ({r.status or r.error})")
        elif "noindex" in parse(r.text).meta.get("robots", "").lower():
            bad.append(f"{u} (noindex)")
    if urls and sample:
        n = min(sample, len(urls))
        rows.append(row("sitemap.sample", "passed" if not bad else "failed",
                        f"{n - len(bad)}/{n} sampled sitemap URLs return 200 and are indexable", "; ".join(bad[:5])))
    return rows, urls


def check_rest(f: Fetcher):
    rows, r = [], f.get("/wp-json/")
    if r.status != 200:
        return [row("rest", "unverified", f"/wp-json/ returned {r.status or r.error}; REST may be disabled or blocked. Not verified is not absent.")]
    try:
        data = json.loads(r.text)
    except ValueError:
        return [row("rest", "unverified", "/wp-json/ did not return JSON")]
    ns = [clean(n, 60) for n in data.get("namespaces", []) if isinstance(n, str)]
    routes = data.get("routes", {})
    rows.append(row("rest.namespaces", "info", f"{len(ns)} namespaces, {len(routes) if isinstance(routes, dict) else '?'} routes",
                    ", ".join(ns)))
    u = f.get("/wp-json/wp/v2/users")
    try:
        users = json.loads(u.text) if u.status == 200 else None
    except ValueError:
        users = None
    if isinstance(users, list) and users:
        slugs = [clean(x.get("slug", "?"), 40) for x in users if isinstance(x, dict)]
        rows.append(row("rest.users", "warning", f"public users endpoint lists {len(slugs)} user slug(s) (login-name hints)", ", ".join(slugs)))
    else:
        rows.append(row("rest.users", "passed", f"users endpoint not listing users (status {u.status or u.error})"))
    return rows


def check_exposure(f: Fetcher):
    rows = []
    r = f.get("/wp-content/debug.log", follow=False)
    rows.append(row("exposure.debug_log", "failed" if r.status == 200 and r.body else "passed",
                    "debug.log is publicly readable" if r.status == 200 and r.body else f"debug.log not served ({r.status or r.error})"))
    r = f.get("/readme.html", follow=False)
    rows.append(row("exposure.readme", "warning" if r.status == 200 else "passed",
                    "readme.html is public (reveals WordPress)" if r.status == 200 else f"readme.html not served ({r.status})"))
    r = f.get("/xmlrpc.php", follow=False)
    on = r.status in (200, 405) and "xml-rpc" in r.text.lower()
    rows.append(row("exposure.xmlrpc", "info", "xmlrpc.php answers: decide whether it is needed (Jetpack, apps) or block it"
                    if on else f"xmlrpc.php not answering ({r.status or r.error})"))
    r = f.get("/?author=1")
    if r.status == 200 and any("/author/" in u for _, u in r.redirects):
        rows.append(row("exposure.author_enum", "warning", "?author=1 redirects to an author archive (reveals a username)",
                        r.redirects[-1][1]))
    else:
        rows.append(row("exposure.author_enum", "passed", "?author=1 does not reveal an author slug"))
    return rows


def check_404(f: Fetcher):
    r = f.get(f"/wp-essentials-404-check-{secrets.token_hex(4)}/")
    ok = r.status == 404
    return [row("404", "passed" if ok else "failed", f"missing page returns {r.status or r.error}" + ("" if ok else " (should be 404)"))]


def check_links(f: Fetcher, home, limit: int):
    if home is None:
        return []
    resp, p = home
    seen, bad = [], []
    for href in p.links:
        u = urllib.parse.urljoin(resp.url, href.split("#", 1)[0])
        if not u or not f.same_site(u) or u in seen or "/wp-admin" in u or "/wp-login" in u or "logout" in u:
            continue
        seen.append(u)
        if len(seen) > limit:
            break
        r = f.get(u)
        if r.status != 200:
            bad.append(f"{u} ({r.status or r.error})")
    return [row("links.internal", "passed" if not bad else "failed",
                f"{len(seen) - len(bad)}/{len(seen)} internal links on the home page return 200", "; ".join(bad[:5]))]


def probe(origin: str, stage: str = "staging", sample: int = 10, link_limit: int = 30) -> dict:
    f = Fetcher(origin)
    rows, home = check_home(f, stage)
    if home is None:
        return {"origin": f.base, "stage": stage, "reachable": False, "requests": f.count, "rows": rows}
    rows += check_https(f)
    rows += check_headers(home[0], f)
    rrows, declared = check_robots(f, stage)
    rows += rrows
    srows, _ = check_sitemap(f, declared, sample, stage)
    rows += srows
    rows += check_rest(f)
    rows += check_exposure(f)
    rows += check_404(f)
    rows += check_links(f, home, link_limit)
    return {"origin": f.base, "stage": stage, "reachable": True, "requests": f.count, "rows": rows}


def render(res: dict) -> str:
    lines = [f"Site probe: {res['origin']} (stage {res['stage']}, {res['requests']} GET requests)", "",
             "| Check | Result | Detail | Evidence |", "|---|---|---|---|"]
    for r in res["rows"]:
        lines.append(f"| {r['check']} | {r['result']} | {clean(r['detail'], 160)} | {r['evidence']} |")
    counts: dict[str, int] = {}
    for r in res["rows"]:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    lines += ["", ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("origin", help="site address, e.g. https://example.com")
    ap.add_argument("--stage", choices=["staging", "launch"], default="staging")
    ap.add_argument("--sample", type=int, default=10, help="sitemap URLs to fetch (default 10)")
    ap.add_argument("--links", type=int, default=30, help="home-page internal links to check (default 30)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=Path, help="also write the JSON result to this file")
    args = ap.parse_args(argv)
    try:
        res = probe(args.origin, args.stage, max(args.sample, 0), max(args.links, 0))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=2) if args.json else render(res))
    if not res["reachable"]:
        return 2
    return 1 if any(r["result"] == "failed" for r in res["rows"]) else 0


if __name__ == "__main__":
    sys.exit(main())
