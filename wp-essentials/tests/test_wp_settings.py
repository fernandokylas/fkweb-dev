"""Tests for skills/wp-site-setup/scripts/wp_settings.py (no WP-CLI needed)."""
import contextlib
import io
import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "wp-site-setup" / "scripts"))
import wp_settings  # noqa: E402

SITE = ["--set", "blogname=Harbour Lights", "--set", "blogdescription=Seafood by the quay",
        "--set", "admin_email=owner@example.com", "--set", "timezone_string=Indian/Mauritius"]
SITE_SETS = [SITE[i] for i in range(1, len(SITE), 2)]


def run_main(argv, default_stage=True):
    # --stage is required; most tests exercise the fresh-build "setup" stage.
    if default_stage and argv and "--stage" not in argv:
        argv = [*argv, "--stage", "setup"]
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = wp_settings.main(argv)
    return code, out.getvalue(), err.getvalue()


def matching_readback(stage="setup", cleanup=False):
    """The JSON a fully correct site would give back, built from the profile."""
    profile = wp_settings.load_profile(wp_settings.DEFAULT_PROFILE, SITE_SETS, stage)
    values, _ = wp_settings.expected_values(profile, allow_missing=True)
    data = dict(values)
    data["locale"] = profile["locale"]
    if cleanup:
        data["_default_post"] = "0"
        data["_default_page"] = "0"
        data["_plugin_hello"] = "absent"
    return data


class PlanTests(unittest.TestCase):
    def test_refuses_when_site_values_missing(self):
        code, out, err = run_main(["plan"])
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        for key in ("blogname", "blogdescription", "admin_email", "timezone_string"):
            self.assertIn(key, err)

    def test_allow_missing_skips_the_check(self):
        code, out, _ = run_main(["plan", "--allow-missing"])
        self.assertEqual(code, 0)
        self.assertNotIn("blogname", out)

    def test_full_plan(self):
        code, out, _ = run_main(["plan", *SITE])
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertIn("wp language core install en_GB --activate", lines)
        self.assertIn("wp rewrite structure /%postname%/", lines)
        profile = wp_settings.load_profile(wp_settings.DEFAULT_PROFILE, SITE_SETS, "setup")
        values, _ = wp_settings.expected_values(profile, False)
        for key, value in values.items():
            if key == "permalink_structure":
                continue
            self.assertIn(f"wp option update {shlex.quote(key)} {shlex.quote(value)}", lines)
        self.assertIn("wp option update blog_public 0", lines)
        self.assertFalse(any("DESTRUCTIVE" in ln for ln in lines))

    def test_cleanup_adds_destructive_lines(self):
        code, out, _ = run_main(["plan", *SITE, "--cleanup"])
        self.assertEqual(code, 0)
        destructive = [ln for ln in out.splitlines() if "DESTRUCTIVE" in ln]
        self.assertTrue(any("post delete" in ln and "default post" in ln for ln in destructive))
        self.assertTrue(any("post delete" in ln and "default page" in ln for ln in destructive))
        self.assertTrue(any("plugin delete hello" in ln for ln in destructive))
        self.assertIn("comment_status=closed", out)

    def test_launch_stage_plan_opens_to_search_engines(self):
        _, out, _ = run_main(["plan", *SITE, "--stage", "launch"])
        self.assertIn("wp option update blog_public 1", out.splitlines())

    def test_wp_prefix_applied(self):
        _, out, _ = run_main(["plan", *SITE, "--cleanup", "--wp", "wp --path=/var/www/html"])
        lines = out.splitlines()
        self.assertIn("wp --path=/var/www/html language core install en_GB --activate", lines)
        for ln in lines:
            if ln.startswith("ids="):
                self.assertIn("wp --path=/var/www/html post list", ln)
            else:
                self.assertTrue(ln.startswith("wp --path=/var/www/html "), ln)

    def test_json_output(self):
        code, out, _ = run_main(["plan", *SITE, "--json"])
        self.assertEqual(code, 0)
        self.assertIsInstance(json.loads(out), list)

    def test_hostile_values_stay_single_arguments(self):
        evil = "O'Neil & Sons; rm -rf /"
        argv = ["plan", "--set", f"blogname={evil}", "--set", 'blogdescription=say "hi" $(id) `x`',
                "--set", "admin_email=a@b.co", "--set", "timezone_string=UTC"]
        _, out, _ = run_main(argv)
        by_key = {}
        for ln in out.splitlines():
            parts = shlex.split(ln)
            if parts[:3] == ["wp", "option", "update"]:
                self.assertEqual(len(parts), 5, ln)
                by_key[parts[3]] = parts[4]
        self.assertEqual(by_key["blogname"], evil)
        self.assertEqual(by_key["blogdescription"], 'say "hi" $(id) `x`')

    def test_bad_set_and_unknown_stage_profile(self):
        code, _, err = run_main(["plan", "--set", "novalue"])
        self.assertEqual(code, 2)
        self.assertIn("KEY=VALUE", err)

    def test_empty_wp_prefix_rejected(self):
        code, _, err = run_main(["plan", *SITE, "--wp", ""])
        self.assertEqual(code, 2)
        self.assertIn("empty", err)


class VerifyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def verify(self, data, *extra):
        path = self.dir / "actual.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return run_main(["verify", "--actual", str(path), *SITE, *extra])

    def test_all_match_exit_0(self):
        code, out, _ = self.verify(matching_readback())
        self.assertEqual(code, 0, out)
        self.assertIn("passed", out)

    def test_all_match_with_cleanup(self):
        code, out, _ = self.verify(matching_readback(cleanup=True), "--cleanup")
        self.assertEqual(code, 0, out)

    def test_cleanup_keys_missing_is_unavailable(self):
        code, _, _ = self.verify(matching_readback(), "--cleanup")
        self.assertEqual(code, 2)

    def test_leftover_default_content_fails(self):
        data = matching_readback(cleanup=True)
        data["_default_post"] = "1"
        data["_plugin_hello"] = "installed"
        code, out, _ = self.verify(data, "--cleanup", "--json")
        self.assertEqual(code, 1)
        failed = {r["key"] for r in json.loads(out) if r["result"] == "failed"}
        self.assertEqual(failed, {"_default_post", "_plugin_hello"})

    def test_one_difference_exit_1(self):
        data = matching_readback()
        data["date_format"] = "d/m/Y"
        code, out, _ = self.verify(data, "--json")
        self.assertEqual(code, 1)
        failed = [r for r in json.loads(out) if r["result"] == "failed"]
        self.assertEqual([r["key"] for r in failed], ["date_format"])

    def test_unticked_box_saved_as_empty_passes(self):
        data = matching_readback()
        data["uploads_use_yearmonth_folders"] = ""
        data["default_comment_status"] = ""
        code, out, _ = self.verify(data, "--json")
        self.assertEqual(code, 0, out)
        data["date_format"] = ""
        code, out, _ = self.verify(data, "--json")
        self.assertEqual(code, 1)
        failed = [r["key"] for r in json.loads(out) if r["result"] == "failed"]
        self.assertEqual(failed, ["date_format"])

    def test_error_dict_exit_2(self):
        data = matching_readback()
        data["blogname"] = {"error": "Error: option does not exist"}
        code, out, _ = self.verify(data, "--json")
        self.assertEqual(code, 2)
        row = next(r for r in json.loads(out) if r["key"] == "blogname")
        self.assertEqual(row["result"], "error")

    def test_missing_key_exit_2(self):
        data = matching_readback()
        del data["locale"]
        code, out, _ = self.verify(data, "--json")
        self.assertEqual(code, 2)
        row = next(r for r in json.loads(out) if r["key"] == "locale")
        self.assertEqual(row["result"], "unavailable")

    def test_launch_stage_expects_blog_public_1(self):
        code, _, _ = self.verify(matching_readback(stage="launch"), "--stage", "launch")
        self.assertEqual(code, 0)
        # a site still discouraging search engines fails the launch stage
        code, _, _ = self.verify(matching_readback(stage="setup"), "--stage", "launch")
        self.assertEqual(code, 1)

    def test_stage_is_required(self):
        with self.assertRaises(SystemExit):
            run_main(["plan", *SITE], default_stage=False)

    def test_unreadable_actual_file_exit_2(self):
        code, _, err = run_main(["verify", "--actual", str(self.dir / "nope.json"), *SITE])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)

    def test_unset_site_values_are_skipped_not_failed(self):
        path = self.dir / "a.json"
        data = matching_readback()
        for k in ("blogname", "blogdescription", "admin_email", "timezone_string"):
            del data[k]
        path.write_text(json.dumps(data), encoding="utf-8")
        code, out, _ = run_main(["verify", "--actual", str(path), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(sum(r["result"] == "skipped" for r in json.loads(out)), 4)


class ReadActualTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.original = wp_settings.run_read
        wp_settings.run_read = self.fake
        self.addCleanup(setattr, wp_settings, "run_read", self.original)

    def fake(self, prefix, args):
        self.calls.append(args)
        if args[:2] == ["option", "get"]:
            return (1, "Error: no such option") if args[2] == "bad" else (0, f"val-{args[2]}")
        if args[:2] == ["language", "core"]:
            return 0, "en_GB"
        if args[0] == "post":
            return 0, "0" if "--post_type=post" in args else "2"
        if args[:2] == ["plugin", "is-installed"]:
            return {"hello": (1, ""), "gone": (0, ""), "weird": (None, "boom")}[args[2]]
        raise AssertionError(args)

    def test_options_and_locale(self):
        actual = wp_settings.read_actual(["wp"], ["blogname", "bad"], None)
        self.assertEqual(actual["blogname"], "val-blogname")
        self.assertEqual(actual["bad"], {"error": "Error: no such option"})
        self.assertEqual(actual["locale"], "en_GB")
        self.assertNotIn("_default_post", actual)

    def test_cleanup_reads(self):
        cleanup = {"delete_default_content": True, "remove_plugins": ["hello", "gone", "weird"]}
        actual = wp_settings.read_actual(["wp"], [], cleanup)
        self.assertEqual(actual["_default_post"], "0")
        self.assertEqual(actual["_default_page"], "2")
        self.assertEqual(actual["_plugin_hello"], "absent")
        self.assertEqual(actual["_plugin_gone"], "installed")
        self.assertEqual(actual["_plugin_weird"], {"error": "boom"})

    def test_only_read_commands_are_issued(self):
        wp_settings.read_actual(["wp"], ["blogname"], {"delete_default_content": True, "remove_plugins": ["hello"]})
        for args in self.calls:
            self.assertIn(args[0], ("option", "language", "post", "plugin"))
            self.assertNotIn(args[1], ("update", "delete"))

    def test_run_read_missing_command(self):
        code, out = self.original(["definitely-not-a-real-binary-xyz"], ["x"])
        self.assertIsNone(code)
        self.assertIn("command not found", out)


if __name__ == "__main__":
    unittest.main()
