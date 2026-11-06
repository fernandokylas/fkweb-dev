"""Regression tests for the rc.4 live-test findings: a gate run without --root on records kept in
docs/website/ reported every page as "target no longer exists"; the reason did not say where it looked;
a mock-up checkpoint without `delivery_mode` was judged as production; and recording into verification.json
tripped its own completed-artifact fingerprint.

Run from the dev root: python3 -m unittest discover tests/records
Every case works in a scratch project whose path contains spaces, with records under docs/website/.
"""
import json
import sys
import unittest

from test_requirements import Project, RECORDS, run

sys.path.insert(0, str(RECORDS.parent))
from sw_records import fingerprint  # noqa: E402


class RootTest(Project):
    def setUp(self):
        super().setUp()
        index = self.site / "index.html"
        index.write_text(index.read_text().replace('<a href="/">', '<a href="/" aria-current="page">'))
        code, out, err = self.site_check("--mode", "mockup", "--require")
        self.assertIsNotNone(out, err)
        self.local = sum(1 for c in self.data()["required_checks"])

    def test_without_root_a_record_in_docs_website_resolves_against_the_project_root(self):
        for cwd in (self.root, self.vpath.parent, self.root.parent):
            with self.subTest(cwd=cwd):
                code, out, _ = run(RECORDS, "gate", self.vpath.resolve(), "--mode", "mockup", cwd=cwd)
                self.assertEqual((code, out["result"]), (0, "passed"), out)
                self.assertEqual(out["root_source"], "inferred: the folder above docs/website/")
                self.assertEqual(out["root"], str(self.root.resolve()))      # PROJECT, not PROJECT/docs
                self.assertNotEqual(out["root"], str((self.root / "docs").resolve()))
                self.assertEqual(out["diagnostics"], [])
        code, out, _ = run(RECORDS, "gate", "docs/website/verification.json", "--root", ".", "--mode", "mockup",
                           cwd=self.root)
        self.assertEqual((code, out["result"], out["root_source"]), (0, "passed", "--root"))

    def test_a_wrong_root_names_the_path_and_the_root_that_would_work(self):
        code, out, _ = run(RECORDS, "gate", "docs/website/verification.json", "--root", "docs/website",
                           "--mode", "mockup", cwd=self.root)
        self.assertEqual((code, out["result"]), (1, "error"))
        reasons = {c["reason"] for c in out["checks"]}
        self.assertTrue(all("looked for" in r and "--root ." in r for r in reasons), reasons)
        index = next(c for c in out["checks"] if c["target"] == "site/index.html")
        self.assertIn(str((self.root / "docs" / "website" / "site" / "index.html").absolute()), index["reason"])
        diag = " ".join(out["diagnostics"])
        self.assertIn(f"{self.local} of {self.local} local targets are missing", diag)
        self.assertIn(f"exist under {self.root.resolve()}", diag)
        self.assertIn("--root", diag)
        code, status, _ = run(RECORDS, "status", "docs/website/verification.json", "--root", "docs/website",
                              cwd=self.root)
        self.assertIn("rerun with --root", " ".join(status["diagnostics"]))

    def test_a_deleted_page_is_still_reported_and_not_blamed_on_the_root(self):
        (self.site / "404.html").unlink()
        code, out, _ = run(RECORDS, "gate", self.vpath, "--root", self.root, "--mode", "mockup")
        self.assertEqual(out["result"], "error")
        gone = [c for c in out["checks"] if c["target"] == "site/404.html"]
        self.assertTrue(gone and all("no longer exists" in c["reason"] for c in gone))
        self.assertEqual(out["diagnostics"], [])   # the other targets exist: no wrong-root diagnosis

    def test_site_check_without_root_records_project_relative_targets(self):
        code, out, err = run(RECORDS.parent / "sw_site_check.py", self.site, "--mode", "mockup", "--record",
                             self.vpath, "--evidence-out", self.root / "docs" / "website" / "evidence" / "s2.json")
        self.assertIsNotNone(out, err)
        targets = {r["target"] for r in self.data()["records"]}
        self.assertIn("site/index.html", targets)
        self.assertFalse(any(t.startswith("..") or "docs/website/site" in t for t in targets), targets)


class StateModeTest(Project):
    def state(self, **fields):
        data = {"schema_version": 1, "project_identifier": "x", "requested_scope": "end-to-end-build",
                "build_path": "custom-code", "selected_framework_or_builder": "static-html",
                "selected_design_family": "f", "current_phase": "verify", "completed_artifacts": [],
                "accepted_decisions": [], "assumptions": [], "open_issues": [], "blocked_dependencies": [],
                "verification_records": ["docs/website/verification.json"], "last_changed_targets": [],
                "next_action": "Run the browser checks."}
        data.update(fields)
        path = self.root / "docs" / "website" / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
        code, out, _ = run(RECORDS, "check-state", path, "--root", self.root)
        return code, out

    def warnings(self, out):
        return [f["evidence"] for f in out["findings"] if f["severity"] == "warning"]

    def test_missing_delivery_mode_is_named(self):
        code, out = self.state()
        self.assertEqual(code, 0)
        self.assertTrue(any("`delivery_mode` is not set" in w for w in self.warnings(out)), out)
        code, out = self.state(delivery_mode="mockup", delivery_criteria=["simulated contact form"])
        self.assertFalse(any("delivery_mode" in w for w in self.warnings(out)), out)
        code, out = self.state(requested_scope="plan-only")
        self.assertFalse(any("delivery_mode" in w for w in self.warnings(out)), out)

    def test_next_action_gate_without_root_is_named(self):
        saved = ("Resume the test: from the project root run sw_records.py gate on docs/website/verification.json "
                 "with --mode mockup and note the result.")
        code, out = self.state(delivery_mode="mockup", delivery_criteria=["x"], next_action=saved)
        self.assertTrue(any("without --root" in w for w in self.warnings(out)), out)
        fixed = ('Run python3 "/p/scripts/sw_records.py" gate docs/website/verification.json --root . '
                 "--mode mockup from the project root.")
        code, out = self.state(delivery_mode="mockup", delivery_criteria=["x"], next_action=fixed)
        self.assertFalse(any("--root" in w for w in self.warnings(out)), out)
        code, out = self.state(delivery_mode="mockup", delivery_criteria=["x"],
                               next_action="Check the status of the client's images.")
        self.assertFalse(any("--root" in w for w in self.warnings(out)), out)

    def test_recording_into_a_listed_verification_record_is_not_an_artifact_defect(self):
        self.site_check("--mode", "mockup", "--require")
        art = [{"path": "docs/website/verification.json", "phase": "verify", "fingerprint": fingerprint(self.vpath)}]
        self.assertEqual(self.state(delivery_mode="mockup", delivery_criteria=["x"], completed_artifacts=art)[0], 0)
        (self.site / "index.html").write_text((self.site / "index.html").read_text() + "<!-- edit -->\n")
        self.site_check("--mode", "mockup", out="site-2.json")          # appends records: the file changes
        code, out = self.state(delivery_mode="mockup", delivery_criteria=["x"], completed_artifacts=art)
        self.assertEqual((code, out["result"]), (0, "passed"), out)
        self.assertTrue(any("verification record changed" in w for w in self.warnings(out)), out)
        other = self.site / "index.html"
        art.append({"path": "site/index.html", "phase": "implement", "fingerprint": fingerprint(other)})
        other.write_text(other.read_text() + "<!-- edit -->\n")
        code, out = self.state(delivery_mode="mockup", delivery_criteria=["x"], completed_artifacts=art)
        self.assertEqual(code, 1)                                         # any other artifact still fails


if __name__ == "__main__":
    unittest.main()
