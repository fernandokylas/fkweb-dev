"""Regression tests for scripts/sw_capture.py against a loopback http.server (item 07).

Run from the dev root: python3 -m unittest discover tests/capture
The server serves a small fake site whose pages use absolute same-origin URLs, a query-string
asset, a remote reference and a redirecting route, so each capture rule is exercised.
"""
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAPTURE = ROOT / "scripts" / "sw_capture.py"
SITE_CHECK = ROOT / "scripts" / "sw_site_check.py"

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<meta name="description" content="Test page">
<link rel="stylesheet" href="{origin}/assets/site.css?ver=1.2">
<link rel="canonical" href="{origin}{route}">
<link rel="alternate" type="application/rss+xml" href="{origin}/feed/">
<script src="https://s.w.org/remote.js"></script>
</head><body><header><a href="{origin}/">Home</a><nav aria-label="Main"><a href="{origin}/"{home_cur}>Home</a> <a href="/about/"{about_cur}>About</a></nav></header>
<main><h1>{title}</h1><img src="{origin}/assets/pic.png?v=2" srcset="{origin}/assets/pic.png?v=2 1x, /assets/pic.png 2x" alt="A picture" width="1" height="1"></main>
<footer><p>Footer</p></footer><script src="{origin}/assets/app.js"></script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, body=b"", ctype="text/html; charset=utf-8", headers=()):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        path = self.path.split("?")[0]
        if "p=" in self.path.partition("?")[2]:
            return self.send(404, b"<html><title>Not found</title></html>")
        pages = {"/": "Home", "/about/": "About"}
        if path in pages:
            body = PAGE.format(title=pages[path], origin=origin, route=path,
                               home_cur=' aria-current="page"' if path == "/" else "",
                               about_cur=' aria-current="page"' if path == "/about/" else "")
            return self.send(200, body.encode())
        if path == "/moved/":
            return self.send(301, headers=[("Location", origin + "/")])
        if path == "/assets/site.css":
            return self.send(200, b"body{color:#111}", "text/css")
        if path == "/assets/app.js":
            return self.send(200, b"console.log(1)", "text/javascript")
        if path == "/assets/pic.png":
            return self.send(200, b"\x89PNG\r\n", "image/png")
        if ".." in path or "%2e" in path.lower() or path.lstrip("/").lower().startswith(("esc", "%2fesc", "%5c")):
            # A permissive server: answers 200 for traversal-looking paths, as a careless runtime might.
            return self.send(200, PAGE.format(title="Escape", origin=origin, route="/", home_cur="",
                                              about_cur="").encode())
        if path == "/symlinked/":
            return self.send(200, b'<html><head><link rel="stylesheet" href="/linked/x.css"></head></html>')
        if path == "/linked/x.css":
            return self.send(200, b"body{}", "text/css")
        if path == "/missing-but-200/":
            return self.send(200, b"<html></html>")
        if path == "/feed/":
            return self.send(404, b"no feed")
        body = PAGE.format(title="Not found", origin=origin, route="/404/", home_cur="", about_cur="")
        return self.send(404, body.encode())


def run(*args, script=CAPTURE):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, timeout=60)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


class CaptureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw capture ")
        self.out = Path(self.tmp.name) / "cap ture"

    def tearDown(self):
        self.tmp.cleanup()

    def test_capture_rewrites_mirrors_and_feeds_site_check(self):
        code, rep, err = run(self.base, "--out", self.out, "--route", "/", "--route", "/about/",
                             "--not-found", "/zzqx-missing/", "--evidence-out", self.out.parent / "ev.json")
        self.assertEqual((code, rep["result"]), (0, "passed"), (err, rep))
        routes = json.loads((self.out / "routes.json").read_text())
        self.assertEqual(routes, {"index.html": "/", "about/index.html": "/about/", "404.html": "/404.html"})
        home = (self.out / "index.html").read_text()
        self.assertNotIn(self.base + "/assets", home)
        self.assertIn('href="/assets/site.css?ver=1.2"', home)
        self.assertIn('href="/"', home)
        self.assertIn('srcset="/assets/pic.png?v=2 1x, /assets/pic.png 2x"', home)
        self.assertIn(f'rel="canonical" href="{self.base}/"', home)  # metadata stays absolute
        self.assertIn("https://s.w.org/remote.js", home)
        for asset in ("assets/site.css", "assets/app.js", "assets/pic.png"):
            self.assertTrue((self.out / asset).is_file(), asset)
        self.assertEqual(rep["metadata_links"], {self.base + "/feed/": 404})
        self.assertTrue(any(f["check_id"] == "capture.metadata-links" and f["severity"] == "warning"
                            for f in rep["findings"]))
        self.assertTrue(json.loads((self.out.parent / "ev.json").read_text())["timestamp"])
        code, site, err = run(self.out, "--routes", self.out / "routes.json", script=SITE_CHECK)
        failed = [(c["check_id"], c["target"]) for c in site["checks"] if c["result"] == "failed"]
        self.assertNotIn("nav.internal-links", {c for c, _ in failed}, site["findings"])
        self.assertNotIn("site.404", {c for c, _ in failed})

    def test_redirecting_route_fails_with_location(self):
        code, rep, _ = run(self.base, "--out", self.out, "--route", "/moved/")
        self.assertEqual((code, rep["result"]), (1, "failed"))
        self.assertEqual(rep["pages"][0]["status"], 301)
        self.assertIn("/", rep["pages"][0]["location"])
        self.assertFalse((self.out / "moved" / "index.html").exists())

    def test_not_found_answering_200_fails(self):
        code, rep, _ = run(self.base, "--out", self.out, "--route", "/", "--not-found", "/missing-but-200/")
        self.assertEqual((code, rep["result"]), (1, "failed"))
        self.assertTrue(any(f["check_id"] == "capture.not-found" for f in rep["findings"]))
        self.assertFalse((self.out / "404.html").exists())

    def test_non_loopback_host_is_refused(self):
        # Item 08 (card Q05): metadata address, a DNS name that resolves to loopback,
        # numeric host spellings and userinfo confusion are all refused before any request.
        for url in ("http://example.org", "http://192.168.1.10:8080", "http://10.0.0.1",
                    "http://169.254.169.254", "http://127.0.0.1.nip.io", "http://0x7f000001",
                    "http://2130706433", "http://user@127.0.0.1@evil.example"):
            code, rep, _ = run(url, "--out", self.out, "--route", "/")
            self.assertEqual((code, rep["result"]), (2, "error"), url)
            self.assertIn("refusing", rep["diagnostics"][0])
        self.assertFalse(self.out.exists())

    def test_existing_directory_needs_replace_and_marker(self):
        self.out.mkdir(parents=True)
        (self.out / "keep.txt").write_text("user file")
        code, rep, _ = run(self.base, "--out", self.out, "--route", "/", "--replace")
        self.assertEqual(code, 2)
        self.assertIn("not made by", rep["diagnostics"][0])
        self.assertTrue((self.out / "keep.txt").exists())
        other = Path(self.tmp.name) / "fresh"
        self.assertEqual(run(self.base, "--out", other, "--route", "/")[0], 0)
        self.assertEqual(run(self.base, "--out", other, "--route", "/")[0], 2)
        self.assertEqual(run(self.base, "--out", other, "--route", "/", "--replace")[0], 0)

    def test_bad_arguments_are_errors(self):
        self.assertEqual(run(self.base, "--out", self.out)[0], 2)  # no route
        self.assertEqual(run(self.base, "--out", self.out, "--route", "about")[0], 2)
        self.assertEqual(run(self.base, "--out", self.out, "--route", "/?x=1")[0], 2)
        self.assertEqual(run("ftp://127.0.0.1", "--out", self.out, "--route", "/")[0], 2)
        self.assertEqual(run(self.base, "--route", "/")[0], 2)  # missing --out

    def tree(self):
        return sorted(str(p.relative_to(self.tmp.name)) for p in Path(self.tmp.name).rglob("*"))

    def test_traversal_routes_are_refused_before_anything_is_written(self):
        """Finding 1: decoded routes may not leave the capture directory (plain, encoded, mixed
        case, double-slash and backslash spellings); nothing is written anywhere."""
        before = self.tree()
        for route in ("/%2e%2e/outside", "/%2E%2E/%2e%2e/outside/", "/a/../../outside", "/%2e%2e%2foutside",
                      "/./x", "/a/%2e/b", "/esc%5c..%5coutside", "/x%00y"):
            code, rep, err = run(self.base, "--out", self.out, "--route", route)
            self.assertEqual((code, rep["result"]), (2, "error"), (route, err))
            self.assertTrue(any("route" in d for d in rep["diagnostics"]), (route, rep["diagnostics"]))
        self.assertEqual(self.tree(), before)
        self.assertFalse((Path(self.tmp.name) / "outside").exists())

    def test_absolute_looking_routes_stay_inside(self):
        """`//etc/x` and `/%2fetc%2fx` are paths on the local server, stored under DIR, never at /etc."""
        code, rep, err = run(self.base, "--out", self.out, "--route", "//esc-abs/", "--route", "/%2fesc-enc/")
        self.assertEqual(code, 0, (err, rep))
        for entry in rep["pages"]:
            dest = (self.out / entry["file"]).resolve()
            self.assertTrue(str(dest).startswith(str(self.out.resolve()) + "/"), entry)

    def test_page_and_asset_destinations_reject_symlink_escapes(self):
        """A symlink inside DIR (for instance placed while a capture runs) can't redirect a page or
        asset write outside DIR; destinations are checked after resolving."""
        sys.path.insert(0, str(ROOT / "scripts"))
        import sw_capture
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        self.out.mkdir()
        (self.out / "linked").symlink_to(outside, target_is_directory=True)
        self.assertIsNone(sw_capture.contained(self.out, "linked/x.css"))
        self.assertIsNone(sw_capture.contained(self.out, "linked/index.html"))
        self.assertIsNone(sw_capture.contained(self.out, "../outside/x"))
        self.assertIsNone(sw_capture.contained(self.out, "/etc/passwd"))
        self.assertEqual(sw_capture.contained(self.out, "ok/index.html"), self.out.resolve() / "ok" / "index.html")
        cap = sw_capture.Capture(self.base, self.out, 5, sw_capture.CaptureReport(self.base))
        cap.pending.append((self.base + "/linked/x.css", "/linked/x.css"))
        cap.mirror_assets()
        self.assertEqual(cap.assets["/linked/x.css"], "skipped")
        self.assertEqual(list(outside.iterdir()), [])

    def test_encoded_traversal_asset_is_skipped_not_written(self):
        """An asset reference that decodes to ../ is reported and never fetched or stored."""
        sys.path.insert(0, str(ROOT / "scripts"))
        import sw_capture
        self.out.mkdir()
        cap = sw_capture.Capture(self.base, self.out, 5, sw_capture.CaptureReport(self.base))
        cap.rewrite(self.base + "/", '<link rel="stylesheet" href="/%2e%2e/evil.css"><img src="/a/%2E%2E/%2e%2e/pic.png">')
        cap.mirror_assets()
        self.assertTrue(all(v == "skipped" for v in cap.assets.values()), cap.assets)
        self.assertFalse((Path(self.tmp.name) / "evil.css").exists())

    def test_not_found_must_stay_on_the_local_origin(self):
        """Finding 2: an absolute or scheme-relative --not-found URL is refused before any request."""
        for value in ("http://example.org/missing", "//example.org/missing", "https://127.0.0.1/x",
                      f"http://127.0.0.2:{self.httpd.server_port}/x", "http://localhost.example/x",
                      f"http://user@example.org:{self.httpd.server_port}/x"):
            code, rep, _ = run(self.base, "--out", self.out, "--route", "/", "--not-found", value)
            self.assertEqual((code, rep["result"]), (2, "error"), value)
            self.assertIn("refusing", " ".join(rep["diagnostics"]), value)
            self.assertFalse(self.out.exists(), value)

    def test_query_based_not_found_still_works(self):
        """A local WordPress-style missing-page check (`?p=` query, relative or root-relative) is kept."""
        for value in ("/?p=999999", "?p=999999", self.base + "/zzqx-missing/"):
            out = Path(self.tmp.name) / f"q{abs(hash(value))}"
            code, rep, err = run(self.base, "--out", out, "--route", "/", "--not-found", value)
            self.assertEqual((code, rep["not_found"]["status"]), (0, 404), (value, err, rep))
            self.assertTrue((out / "404.html").is_file())

    def test_every_fetch_is_checked_against_the_origin(self):
        """Defence in depth: fetch() refuses any URL off the authorised origin, whatever the caller."""
        sys.path.insert(0, str(ROOT / "scripts"))
        import sw_capture
        from unittest import mock
        with mock.patch.object(sw_capture.OPENER, "open") as opener:
            for url in ("http://example.org/", "https://" + self.base.split("://")[1] + "/", "file:///etc/passwd"):
                with self.assertRaises(ValueError, msg=url):
                    sw_capture.fetch(url, 1, self.base)
            opener.assert_not_called()

    def test_unreachable_server_is_error_not_failure(self):
        code, rep, _ = run("http://127.0.0.1:9", "--out", self.out, "--route", "/", "--timeout", "2")
        self.assertEqual((code, rep["result"]), (2, "error"))
        self.assertTrue(rep["diagnostics"])


if __name__ == "__main__":
    unittest.main()
