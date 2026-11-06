"""Regression tests for scripts/sw_integrations.py, the offline optional-integration probe (item 12).

Run from the dev root: python3 -m unittest discover tests/integrations
Every run uses a fake PATH, HOME and project tree holding small shell stubs, so results don't
depend on what this machine has installed (except system browser apps, which are only read).
"""
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scripts" / "sw_integrations.py"
DOC = ROOT / "skills" / "website-workflow" / "references" / "optional-integrations.md"
SECRET = "sw-sentinel-credential-value-7f3a"
STATUSES = {"available", "unavailable", "skipped", "error"}


def load_registry():
    spec = importlib.util.spec_from_file_location("sw_integrations", PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.REGISTRY


def stub(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


def package(node_modules, name, version):
    p = node_modules / name / "package.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"name": name, "version": version}))


def tree(root):
    return sorted((str(p.relative_to(root)), p.stat().st_mtime_ns) for p in root.rglob("*"))


class Sandbox:
    """A temporary HOME, PATH dir and project dir (with a space in its name)."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.bin = base / "bin"
        self.project = base / "café project"
        for d in (self.home, self.bin, self.project):
            d.mkdir()
        self.cwd = base / "cwd"
        self.cwd.mkdir()

    def run(self, *args, env=None):
        # Apple's /usr/bin/python3 caches bytecode under $HOME/Library/Caches unless told not to;
        # that is the interpreter's write, not the probe's.
        full = {"PATH": str(self.bin), "HOME": str(self.home), "PYTHONDONTWRITEBYTECODE": "1", **(env or {})}
        start = time.monotonic()
        p = subprocess.run([sys.executable, str(PROBE), *args], capture_output=True, text=True,
                           env=full, cwd=self.cwd, timeout=60)
        return p, time.monotonic() - start

    def probe(self, *args, env=None):
        p, elapsed = self.run("probe", *args, env=env)
        if p.returncode != 0:
            raise AssertionError(f"exit {p.returncode}: {p.stderr}")
        data = json.loads(p.stdout)
        return {i["id"]: i for i in data["integrations"]}, data, p, elapsed

    def close(self):
        self.tmp.cleanup()


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()

    def tearDown(self):
        self.box.close()

    def test_output_schema_and_every_registry_entry(self):
        found, data, _, _ = self.box.probe()
        for key in ("tool", "tool_version", "target", "result", "findings", "diagnostics", "duration_ms"):
            self.assertIn(key, data)
        self.assertEqual(data["result"], "passed")
        self.assertEqual(set(found), set(load_registry()))
        for item in found.values():
            self.assertIn(item["status"], STATUSES, item)
            for key in ("detail", "cost", "data_flow", "authority"):
                self.assertTrue(item[key], (item["id"], key))

    def test_nothing_installed_is_unavailable_with_reasons(self):
        found, data, _, _ = self.box.probe("--project", str(self.box.project))
        for iid in ("playwright-local", "node", "wordpress-playground"):
            self.assertEqual(found[iid]["status"], "unavailable", found[iid])
            self.assertIn("node", found[iid]["detail"])
        self.assertEqual(data["findings"], [])

    def test_session_and_deferred_integrations_are_skipped_never_available(self):
        found, _, _, _ = self.box.probe()
        for iid in ("browser-mcp", "page-builder-runtime", "image-provider", "seo-data-provider",
                    "design-engine", "export-video-3d", "third-party-site-embeds"):
            self.assertEqual(found[iid]["status"], "skipped", iid)
        self.assertIn("deferred", found["seo-data-provider"]["detail"])
        self.assertIn("deferred", found["export-video-3d"]["detail"])

    def test_node_on_path_reports_its_version(self):
        stub(self.box.bin / "node", "echo v99.1.0")
        found, _, _, _ = self.box.probe()
        self.assertEqual((found["node"]["status"], found["node"]["detail"]), ("available", "v99.1.0"))

    def test_browser_command_on_path_is_found(self):
        stub(self.box.bin / "chromium", "echo Chromium 1.0")
        found, _, _, _ = self.box.probe()
        self.assertEqual(found["browser-binary"]["status"], "available")
        self.assertIn(str(self.box.bin / "chromium"), found["browser-binary"]["detail"])

    def test_playwright_cache_in_home_is_found(self):
        (self.box.home / ".cache" / "ms-playwright" / "chromium-1").mkdir(parents=True)
        found, _, _, _ = self.box.probe()
        self.assertIn("ms-playwright", found["browser-binary"]["detail"])

    def test_project_playwright_with_package_version(self):
        nm = self.box.project / "node_modules"
        stub(nm / ".bin" / "playwright", "echo 'Version 1.2.3'")
        package(nm, "playwright", "1.2.3")
        found, _, _, _ = self.box.probe("--project", str(self.box.project))
        pw = found["playwright-local"]
        self.assertEqual((pw["status"], pw["detail"], pw["package_version"]), ("available", "Version 1.2.3", "1.2.3"))
        self.assertTrue(pw["path"].endswith("node_modules/.bin/playwright"))

    def test_playground_in_scratch_dir_with_spaces(self):
        scratch = Path(self.box.tmp.name) / "scratch dir"
        stub(scratch / "node_modules" / ".bin" / "wp-playground-cli", "echo unknown")
        package(scratch / "node_modules", "@wp-playground/cli", "3.1.57")
        found, _, _, _ = self.box.probe("--playground-dir", str(scratch))
        wp = found["wordpress-playground"]
        self.assertEqual((wp["status"], wp["detail"], wp["package_version"]), ("available", "unknown", "3.1.57"))

    def test_crashing_tool_is_error_with_a_warning_finding(self):
        stub(self.box.bin / "node", "echo 'segfault-ish' >&2; exit 3")
        found, data, _, _ = self.box.probe()
        self.assertEqual(found["node"]["status"], "error")
        self.assertIn("exited 3", found["node"]["detail"])
        self.assertEqual(data["result"], "passed")
        self.assertEqual([(f["location"], f["severity"]) for f in data["findings"]], [("node", "warning")])

    def test_silent_tool_is_error_not_available(self):
        stub(self.box.bin / "node", "exit 0")
        found, _, _, _ = self.box.probe()
        self.assertEqual(found["node"]["status"], "error")

    def test_hanging_tool_times_out_and_its_children_are_killed(self):
        # The stub backgrounds a sleeper that inherits stdout, so only a process-group kill ends the run.
        stub(self.box.bin / "node", "/bin/sleep 60 & wait")
        found, _, _, elapsed = self.box.probe()
        self.assertEqual(found["node"]["status"], "error")
        self.assertIn("timed out", found["node"]["detail"])
        self.assertLess(elapsed, 20)

    def test_credentials_report_presence_never_value(self):
        found, _, p, _ = self.box.probe("--credential-env", "SW_TEST_TOKEN", "--credential-env", "SW_UNSET_TOKEN",
                                        env={"SW_TEST_TOKEN": SECRET})
        self.assertEqual(found["image-provider"]["credentials"],
                         [{"name": "SW_TEST_TOKEN", "set": True}, {"name": "SW_UNSET_TOKEN", "set": False}])
        self.assertEqual(found["image-provider"]["status"], "skipped")
        self.assertIn("authority", found["image-provider"]["detail"])
        self.assertNotIn(SECRET, p.stdout + p.stderr)

    def test_probe_writes_nothing(self):
        nm = self.box.project / "node_modules"
        stub(nm / ".bin" / "playwright", "echo 'Version 1.2.3'")
        stub(self.box.bin / "node", "echo v1")
        before = (tree(self.box.project), tree(self.box.home), tree(self.box.cwd))
        for _ in range(2):
            self.box.probe("--project", str(self.box.project))
        self.assertEqual((tree(self.box.project), tree(self.box.home), tree(self.box.cwd)), before)

    def test_bad_arguments_exit_2(self):
        for args in ([], ["probe", "--credential-env", "BAD-NAME"], ["probe", "--project", "/no/such/dir"],
                     ["probe", "--playground-dir", "/no/such/dir"], ["frobnicate"]):
            p, _ = self.box.run(*args)
            self.assertEqual(p.returncode, 2, (args, p.stdout))
            self.assertEqual(p.stdout, "", args)


class StaticTest(unittest.TestCase):
    def test_no_network_modules_or_package_runners(self):
        source = PROBE.read_text(encoding="utf-8")
        tree_ = ast.parse(source)
        imported = set()
        for node in ast.walk(tree_):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertFalse(imported & {"urllib", "socket", "http", "ssl", "ftplib", "smtplib", "asyncio", "requests"},
                         imported)
        strings = {n.value for n in ast.walk(tree_) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        self.assertFalse(strings & {"npx", "npm", "install", "pip"}, strings & {"npx", "npm", "install", "pip"})
        self.assertNotIn("shell=True", source)

    def test_registry_matches_both_doc_tables(self):
        ids = re.findall(r"^\| `([a-z0-9-]+)` \|", DOC.read_text(encoding="utf-8"), flags=re.M)
        registry = set(load_registry())
        self.assertEqual(set(ids), registry)
        for iid in registry:
            self.assertEqual(ids.count(iid), 2, iid)

    def test_doc_names_the_probe_with_a_plugin_relative_path(self):
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_integrations.py" probe', DOC.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
