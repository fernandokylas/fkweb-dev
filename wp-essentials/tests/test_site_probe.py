"""Tests for skills/wp-site-audit/scripts/site_probe.py against a local 127.0.0.1 server."""
import http.server
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "wp-site-audit" / "scripts"))
import site_probe  # noqa: E402

# Never route loopback test traffic through a proxy from the environment.
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

WORDS = " ".join(["Fresh seafood from the quay, caught daily and served with care."] * 20)


def make_handler(noindex=False, block_all=False, other_port=None):
    """Handler class for a fake, deliberately faulty WordPress site."""

    class Handler(http.server.BaseHTTPRequestHandler):
        hits = []

        def log_message(self, *args):
            pass

        def send(self, status, body="", ctype="text/html; charset=utf-8", headers=None):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            host = f"http://127.0.0.1:{self.server.server_address[1]}"
            Handler.hits.append(self.path)
            if path == "/":
                robots = '<meta name="robots" content="noindex, nofollow">' if noindex else ""
                self.send(200, f"""<!doctype html><html lang="en-GB"><head><title>Harbour Lights</title>
<meta name="description" content="Seafood by the quay"><meta name="viewport" content="width=device-width">
<link rel="canonical" href="{host}/"><meta name="generator" content="WordPress 7.0">{robots}</head>
<body><h1>Harbour Lights</h1><p>{WORDS}</p>
<a href="/about">About</a> <a href="/missing-page">Gone</a> <a href="http://other.example/x">Away</a>
<a href="/wp-admin/">Admin</a></body></html>""")
            elif path == "/about":
                self.send(200, "<html><head><title>About</title></head><body>About us</body></html>")
            elif path == "/robots.txt":
                body = f"User-agent: *\n{'Disallow: /' if block_all else 'Disallow: /wp-admin/'}\nSitemap: {host}/wp-sitemap.xml\n"
                self.send(200, body, "text/plain")
            elif path == "/wp-sitemap.xml":
                self.send(200, f"<sitemapindex><sitemap><loc>{host}/wp-sitemap-posts.xml</loc></sitemap></sitemapindex>", "application/xml")
            elif path == "/wp-sitemap-posts.xml":
                self.send(200, f"<urlset><url><loc>{host}/about</loc></url><url><loc>{host}/gone</loc></url></urlset>", "application/xml")
            elif path == "/wp-json/":
                self.send(200, json.dumps({"namespaces": ["wp/v2", "oembed/1.0"], "routes": {"/": {}, "/wp/v2/posts": {}}}), "application/json")
            elif path == "/wp-json/wp/v2/users":
                self.send(200, json.dumps([{"id": 1, "slug": "site_owner"}]), "application/json")
            elif path == "/readme.html":
                self.send(200, "<html>WordPress readme</html>")
            elif path == "/wp-content/debug.log":
                self.send(200, "PHP Notice: something", "text/plain")
            elif path == "/xmlrpc.php":
                self.send(405, "XML-RPC server accepts POST requests only.", "text/plain")
            elif path == "/offsite":
                self.send(302, "", headers={"Location": f"http://localhost:{other_port}/stolen"})
            elif path == "/big":
                self.send(200, "x" * 5000, "text/plain")
            else:
                self.send(404, "not found")

    return Handler


class Server:
    def __init__(self, handler):
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.handler = handler
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.httpd.server_address[1]
        self.origin = f"http://127.0.0.1:{self.port}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(5)


def start(**kwargs):
    return Server(make_handler(**kwargs))


def rows_by_check(result):
    return {r["check"]: r for r in result["rows"]}


class FaultySiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.other = Server(make_handler())  # the "other host"; must never be contacted
        cls.srv = start(other_port=cls.other.port)
        cls.result = site_probe.probe(cls.srv.origin, "staging", sample=10, link_limit=30)
        cls.rows = rows_by_check(cls.result)

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()
        cls.other.close()

    def check(self, name, result):
        self.assertIn(name, self.rows)
        self.assertEqual(self.rows[name]["result"], result, self.rows[name])

    def test_reachable_and_counted(self):
        self.assertTrue(self.result["reachable"])
        self.assertGreater(self.result["requests"], 10)

    def test_home_rows(self):
        for name in ("home.status", "home.title", "home.meta_description", "home.h1", "home.lang",
                     "home.viewport", "home.canonical", "home.text"):
            self.check(name, "passed")
        self.check("home.generator", "warning")
        self.assertNotIn("home.noindex", self.rows)

    def test_no_https_row_for_loopback_http(self):
        self.assertFalse([c for c in self.rows if c.startswith("https")])

    def test_robots_and_sitemap(self):
        self.check("robots.blocks_all", "passed")
        self.check("robots.sitemap", "passed")
        self.check("sitemap", "passed")
        self.assertIn("2 URL(s)", self.rows["sitemap"]["detail"])
        self.check("sitemap.sample", "failed")
        self.assertIn("/gone", self.rows["sitemap.sample"]["evidence"])

    def test_rest(self):
        self.check("rest.namespaces", "info")
        self.assertIn("wp/v2", self.rows["rest.namespaces"]["evidence"])
        self.check("rest.users", "warning")
        self.assertIn("site_owner", self.rows["rest.users"]["evidence"])

    def test_exposure(self):
        self.check("exposure.debug_log", "failed")
        self.check("exposure.readme", "warning")
        self.check("exposure.xmlrpc", "info")
        self.assertIn("answers", self.rows["exposure.xmlrpc"]["detail"])
        self.check("exposure.author_enum", "passed")

    def test_404_and_links(self):
        self.check("404", "passed")
        self.check("links.internal", "failed")
        self.assertIn("/missing-page", self.rows["links.internal"]["evidence"])
        self.assertIn("1/2", self.rows["links.internal"]["detail"])  # /about ok, /missing-page bad; offsite and wp-admin skipped

    def test_security_headers_flagged(self):
        self.check("headers.nosniff", "warning")
        self.check("headers.framing", "warning")

    def test_main_exit_code_and_out_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "sub" / "probe.json"
            with mock.patch("sys.stdout"):
                code = site_probe.main([self.srv.origin, "--out", str(out), "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out.read_text())["origin"], self.srv.origin)

    def test_main_bad_origin_exit_2(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(site_probe.main(["ftp://example.com"]), 2)


class FetcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.other = Server(make_handler())
        cls.srv = start(other_port=cls.other.port)

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()
        cls.other.close()

    def test_offsite_redirect_not_followed(self):
        before = len(self.other.handler.hits)
        f = site_probe.Fetcher(self.srv.origin)
        r = f.get("/offsite")
        self.assertIsNotNone(r.error)
        self.assertIn("not followed", r.error)
        self.assertEqual(r.status, 302)
        self.assertEqual(len(self.other.handler.hits), before)
        self.assertEqual(f.count, 1)

    def test_other_host_refused_without_network(self):
        f = site_probe.Fetcher(self.srv.origin)
        r = f.get("http://other.example/")
        self.assertIn("refused", r.error)
        self.assertIsNone(r.status)
        self.assertEqual(f.count, 0)

    def test_same_site_compares_port(self):
        f = site_probe.Fetcher("https://example.test")
        self.assertTrue(f.same_site("https://example.test/a"))
        self.assertTrue(f.same_site("https://EXAMPLE.test:443/a"))
        self.assertTrue(f.same_site("http://example.test/"))          # http<->https on default ports
        self.assertFalse(f.same_site("http://example.test:6379/"))
        self.assertFalse(f.same_site("https://example.test:8443/"))
        self.assertFalse(f.same_site("https://example.test:99999/"))  # invalid port
        g = site_probe.Fetcher("http://127.0.0.1:8089")
        self.assertTrue(g.same_site("http://127.0.0.1:8089/x"))
        self.assertFalse(g.same_site("http://127.0.0.1/x"))
        self.assertFalse(g.same_site("https://127.0.0.1:8089/x"))

    def test_response_size_cap(self):
        f = site_probe.Fetcher(self.srv.origin)
        with mock.patch.object(site_probe, "MAX_BYTES", 100):
            r = f.get("/big")
        self.assertTrue(r.truncated)
        self.assertEqual(len(r.body), 100)
        self.assertFalse(f.get("/big").truncated)

    def test_connection_refused_is_an_error_row(self):
        dead = start()
        origin = dead.origin
        dead.close()
        res = site_probe.probe(origin)
        self.assertFalse(res["reachable"])
        self.assertEqual(res["rows"][0]["result"], "failed")
        with mock.patch("sys.stdout"):
            self.assertEqual(site_probe.main([origin]), 2)

    def test_invalid_origin(self):
        with self.assertRaises(ValueError):
            site_probe.Fetcher("example.com")


class StageSeverityTests(unittest.TestCase):
    def probe(self, stage, **kw):
        srv = start(**kw)
        self.addCleanup(srv.close)
        return rows_by_check(site_probe.probe(srv.origin, stage, sample=0, link_limit=0))

    def test_noindex_page(self):
        self.assertEqual(self.probe("staging", noindex=True)["home.noindex"]["result"], "info")
        self.assertEqual(self.probe("launch", noindex=True)["home.noindex"]["result"], "failed")

    def test_disallow_all_robots(self):
        self.assertEqual(self.probe("staging", block_all=True)["robots.blocks_all"]["result"], "info")
        self.assertEqual(self.probe("launch", block_all=True)["robots.blocks_all"]["result"], "failed")


class CleanTests(unittest.TestCase):
    def test_strips_control_chars_pipes_backticks(self):
        out = site_probe.clean("a\x00b\nc\x1bd|e`f\x7fg")
        for bad in ("\x00", "\n", "\x1b", "|", "`", "\x7f"):
            self.assertNotIn(bad, out)
        self.assertIn("/", out)
        self.assertIn("'", out)

    def test_truncates(self):
        out = site_probe.clean("x" * 500, 50)
        self.assertEqual(len(out), 50)
        self.assertTrue(out.endswith("…"))
        self.assertEqual(site_probe.clean("short"), "short")


if __name__ == "__main__":
    unittest.main()
