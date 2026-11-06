"""Tests for skills/wp-predelivery-check/scripts/predelivery_check.py."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "wp-site-audit" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "wp-site-setup" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "wp-predelivery-check" / "scripts"))
import predelivery_check as pc  # noqa: E402
import wp_settings  # noqa: E402
from test_site_probe import start  # noqa: E402  (local fake WordPress site)

SITE_SETS = ["blogname=Harbour Lights", "blogdescription=Seafood by the quay",
             "admin_email=owner@example.com", "timezone_string=Indian/Mauritius"]


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = pc.main(argv)
    return code, out.getvalue(), err.getvalue()


class ManualRowsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_no_file_all_open(self):
        rows = pc.manual_rows(None)
        self.assertEqual([r["check"] for r in rows], [k for k, _ in pc.MANUAL])
        self.assertTrue(all(r["result"] == "open" and r["section"] == "manual" for r in rows))

    def test_given_results_and_unknown_value(self):
        path = self.dir / "m.json"
        path.write_text(json.dumps({"forms": {"result": "passed", "note": "arrived | `ok`"},
                                    "email": {"result": "definitely"},
                                    "backups": {"result": "n/a"},
                                    "mobile": {}}), encoding="utf-8")
        by = {r["check"]: r for r in pc.manual_rows(path)}
        self.assertEqual(by["forms"]["result"], "passed")
        self.assertNotIn("|", by["forms"]["evidence"])
        self.assertNotIn("`", by["forms"]["evidence"])
        self.assertEqual(by["email"]["result"], "open")
        self.assertEqual(by["backups"]["result"], "n/a")
        self.assertEqual(by["mobile"]["result"], "open")
        self.assertEqual(by["legal"]["result"], "open")  # missing key


class OutsideRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = start()
        tmp = tempfile.TemporaryDirectory()
        cls.tmp = tmp
        cls.manual = Path(tmp.name) / "manual.json"
        cls.manual.write_text(json.dumps({k: {"result": "passed"} for k, _ in pc.MANUAL}), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()
        cls.tmp.cleanup()

    def test_not_ready_because_of_outside_failures(self):
        out_file = Path(self.tmp.name) / "reports" / "report.md"
        code, out, _ = run_main(["--url", self.srv.origin, "--manual", str(self.manual), "--out", str(out_file), "--sample", "5"])
        self.assertEqual(code, 1)
        self.assertIn("Verdict: **NOT READY**", out)
        self.assertIn("Verdict: **NOT READY**", out_file.read_text(encoding="utf-8"))
        self.assertIn("## Not run", out)
        self.assertIn("Inside checks", out)
        self.assertIn("outside/exposure.debug_log", out)

    def test_json_report_structure(self):
        code, out, _ = run_main(["--url", self.srv.origin, "--manual", str(self.manual), "--json"])
        report = json.loads(out)
        self.assertEqual(code, 1)
        self.assertEqual(report["verdict"], "NOT READY")
        self.assertEqual(len(report["not_run"]), 1)
        self.assertFalse([r for r in report["rows"] if r["section"] in ("inside", "settings", "content")])
        manual = [r for r in report["rows"] if r["section"] == "manual"]
        self.assertTrue(all(r["result"] == "passed" for r in manual))
        failed = {r["check"] for r in report["rows"] if r["result"] == "failed"}
        self.assertIn("exposure.debug_log", failed)

    def test_unreachable_site_exit_2(self):
        dead = start()
        origin = dead.origin
        dead.close()
        code, out, _ = run_main(["--url", origin])
        self.assertEqual(code, 2)
        self.assertIn("NOT READY", out)

    def test_bad_manual_json_exit_2(self):
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text("{nope", encoding="utf-8")
        code, _, err = run_main(["--url", self.srv.origin, "--manual", str(bad)])
        self.assertEqual(code, 2)
        self.assertIn("error", err)


class InsideChecksTests(unittest.TestCase):
    def setUp(self):
        self.profile = wp_settings.load_profile(wp_settings.DEFAULT_PROFILE, SITE_SETS, "launch")
        self.values, _ = wp_settings.expected_values(self.profile, allow_missing=True)
        self.original = wp_settings.run_read
        self.addCleanup(setattr, wp_settings, "run_read", self.original)
        self.overrides = {}
        wp_settings.run_read = self.fake

    def fake(self, prefix, args):
        key = tuple(args)
        if key in self.overrides:
            return self.overrides[key]
        a = list(args)
        if a == ["core", "version"]:
            return 0, "7.0"
        if a[:2] == ["option", "get"]:
            name = a[2]
            if name in ("siteurl", "home"):
                return 0, "https://example.com"
            if name == "wp_page_for_privacy_policy":
                return 0, "3"
            if name == "site_icon":
                return 0, "0"
            return 0, self.values[name]
        if a[:3] == ["language", "core", "list"]:
            return 0, self.profile["locale"]
        if a[0] == "post" and a[1] == "list" and any(x.startswith("--name=") for x in a):
            return 0, "0"
        if a[:2] == ["plugin", "is-installed"]:
            return 1, ""
        if a == ["config", "get", "WP_DEBUG"]:
            return 0, ""
        if a == ["config", "get", "DISALLOW_FILE_EDIT"]:
            return 1, "Error: The constant 'DISALLOW_FILE_EDIT' is not defined"
        if a[:2] == ["user", "list"]:
            return 0, "site_owner\nadmin"
        if a[:2] in (["core", "check-update"], ["theme", "list"]) or (a[:2] == ["plugin", "list"] and "--update=available" in a):
            return 0, "0"
        if a[:2] == ["post", "list"]:
            s = [x for x in a if x.startswith("--s=")][0]
            return 0, "about-us" if s == "--s=lorem ipsum" else ""
        if a[:2] == ["post", "get"]:
            return 0, "publish"
        if a[:2] == ["plugin", "list"]:
            return 0, ""
        raise AssertionError(f"unexpected WP-CLI call: {a}")

    def rows(self):
        return {(r["section"], r["check"]): r for r in pc.inside_checks(["wp"], wp_settings.DEFAULT_PROFILE, SITE_SETS)}

    def test_expected_results(self):
        rows = self.rows()
        res = lambda s, c: rows[(s, c)]["result"]  # noqa: E731
        self.assertEqual(res("inside", "admin_usernames"), "failed")
        self.assertIn("admin", rows[("inside", "admin_usernames")]["detail"])
        self.assertEqual(res("content", "placeholder_text"), "failed")
        self.assertIn("lorem ipsum", rows[("content", "placeholder_text")]["evidence"])
        self.assertEqual(res("inside", "DISALLOW_FILE_EDIT"), "warning")
        self.assertEqual(res("content", "site_icon"), "warning")
        self.assertEqual(res("inside", "WP_DEBUG"), "passed")
        self.assertEqual(res("inside", "siteurl"), "passed")
        self.assertEqual(res("inside", "home"), "passed")
        self.assertEqual(res("content", "privacy_page"), "passed")
        for c in ("core_updates", "plugin_updates", "theme_updates"):
            self.assertEqual(res("inside", c), "passed")
        self.assertNotIn(("inside", "inactive_plugins"), rows)

    def test_launch_settings_all_pass(self):
        rows = self.rows()
        settings = [r for (s, _), r in rows.items() if s == "settings"]
        self.assertTrue(settings)
        self.assertEqual({r["result"] for r in settings}, {"passed"}, [r for r in settings if r["result"] != "passed"])
        self.assertEqual(rows[("settings", "blog_public")]["result"], "passed")

    def test_blog_public_still_discouraged(self):
        self.overrides[("option", "get", "blog_public")] = (0, "0")
        r = self.rows()[("settings", "blog_public")]
        self.assertEqual(r["result"], "failed")
        self.assertIn("discouraged", r["detail"])

    def test_http_siteurl_fails_and_debug_on_fails(self):
        self.overrides[("option", "get", "siteurl")] = (0, "http://example.com")
        self.overrides[("config", "get", "WP_DEBUG")] = (0, "true")
        rows = self.rows()
        self.assertEqual(rows[("inside", "siteurl")]["result"], "failed")
        self.assertEqual(rows[("inside", "WP_DEBUG")]["result"], "failed")

    def test_pending_updates_and_inactive_plugins(self):
        self.overrides[("core", "check-update", "--format=count")] = (0, "2")
        self.overrides[("plugin", "list", "--status=inactive", "--field=name")] = (0, "akismet\nhello")
        rows = self.rows()
        self.assertEqual(rows[("inside", "core_updates")]["result"], "warning")
        self.assertEqual(rows[("inside", "inactive_plugins")]["result"], "info")

    def test_wp_cli_unusable_is_unverified_not_passed(self):
        self.overrides[("core", "version")] = (None, "command not found: wp")
        rows = pc.inside_checks(["wp"], wp_settings.DEFAULT_PROFILE, SITE_SETS)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["result"], "unverified")

    def test_missing_privacy_page_fails(self):
        self.overrides[("option", "get", "wp_page_for_privacy_policy")] = (0, "0")
        self.assertEqual(self.rows()[("content", "privacy_page")]["result"], "failed")


if __name__ == "__main__":
    unittest.main()
