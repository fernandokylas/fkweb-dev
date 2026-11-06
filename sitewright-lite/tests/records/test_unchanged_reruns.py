"""0.3.0: a rerun that repeats the current record about the same target state appends nothing;
gate and status report coverage by method.

Run from the dev root: python3 -m unittest discover tests/records
"""
import json
import unittest

from test_batch_and_archive import Base
from test_requirements import PAGE, RECORDS, run


class UnchangedRerunTest(Base):
    def record(self, evidence, *extra, finding="landmarks present", result="passed", text=None):
        return run(RECORDS, "record", self.vpath, "--root", self.root, "--check-id", "a11y.landmarks",
                   "--target", "site/index.html", "--result", result, "--method", "manual",
                   "--tool-and-version", "reviewer 1", "--evidence-path", self.note(evidence, text),
                   "--finding", finding, "--require", *extra)

    def records(self):
        return self.data()["records"]

    def test_identical_rerun_writes_no_record(self):
        code, out, _ = self.record("r1.txt")
        self.assertEqual((code, out["unchanged"]), (0, False))
        code, out, _ = self.record("r2.txt")
        self.assertEqual((code, out["unchanged"], out["archived"]), (0, True, 0), out)
        self.assertEqual(out["record"]["evidence_path"], "docs/website/evidence/r1.txt")
        self.assertEqual([r["evidence_path"] for r in self.records()], ["docs/website/evidence/r1.txt"])
        self.assertFalse(self.archive.exists())

    def test_a_different_finding_result_or_target_state_appends(self):
        self.record("r1.txt")
        self.assertFalse(self.record("r2.txt", finding="one landmark missing")[1]["unchanged"])
        self.assertFalse(self.record("r3.txt", finding="one landmark missing", result="failed")[1]["unchanged"])
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Changed."))
        self.assertFalse(self.record("r4.txt", finding="one landmark missing", result="failed")[1]["unchanged"])
        self.assertEqual(len(self.records()), 1)            # each one superseded the last
        self.assertEqual(len(self.archived()), 3)

    def test_a_changed_input_appends(self):
        self.record("r1.txt", "--input", "site/404.html")
        self.assertTrue(self.record("r2.txt", "--input", "site/404.html")[1]["unchanged"])
        (self.site / "404.html").write_text(PAGE.format(t="Not found", body="Changed."))
        self.assertFalse(self.record("r3.txt", "--input", "site/404.html")[1]["unchanged"])

    def test_old_evidence_gone_or_rewritten_appends(self):
        self.record("r1.txt")
        (self.evidence / "r1.txt").unlink()
        self.assertFalse(self.record("r2.txt")[1]["unchanged"])
        self.assertFalse(self.record("r2.txt", "--append-unchanged")[1]["unchanged"])
        self.assertFalse(self.record("r2.txt", text="rewritten in place by a later run")[1]["unchanged"])

    def test_append_unchanged_opts_out(self):
        self.record("r1.txt")
        code, out, _ = self.record("r2.txt", "--append-unchanged")
        self.assertEqual((code, out["unchanged"]), (0, False))
        self.assertEqual(self.records()[-1]["evidence_path"], "docs/website/evidence/r2.txt")

    def test_a_record_for_another_mode_does_not_block_and_an_any_mode_one_does(self):
        self.record("r1.txt", "--mode", "production")
        self.record("r2.txt", "--mode", "mockup")
        self.assertTrue(self.record("r3.txt", "--mode", "production")[1]["unchanged"])
        self.record("r4.txt")                                  # counts in every mode: it decides now
        self.assertFalse(self.record("r5.txt", "--mode", "production")[1]["unchanged"])

    def test_unchanged_rerun_still_ends_the_run_in_progress(self):
        self.record("r1.txt")
        code, out, _ = run(RECORDS, "begin", self.vpath, "--root", self.root, "--check-id", "a11y.landmarks",
                           "--target", "site/index.html")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.record("r2.txt")[1]["unchanged"])
        self.assertEqual(self.data().get("runs_in_progress"), [])
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_batch_reports_unchanged_entries(self):
        self.record("r1.txt")
        path = self.root / "batch.json"
        path.write_text(json.dumps({"defaults": {"method": "manual", "tool_and_version": "reviewer 1",
                                                 "result": "passed", "require": True,
                                                 "finding": "landmarks present"},
                                    "records": [{"check_id": "a11y.landmarks", "target": "site/index.html",
                                                 "evidence_path": self.note("b.txt")},
                                                {"check_id": "a11y.landmarks", "target": "site/404.html",
                                                 "evidence_path": self.note("b.txt")}]}))
        code, out, err = run(RECORDS, "record", self.vpath, "--root", self.root, "--batch", path)
        self.assertEqual((code, out["recorded"], out["unchanged"]), (0, 1, 1), (out, err))
        self.assertEqual(len(self.records()), 2)


class HelperRerunTest(Base):
    def test_second_identical_site_check_adds_nothing_and_drops_its_evidence(self):
        code, out, err = self.site_check("--checks", "meta.basics", "--require")
        self.assertIn(code, (0, 1), err)
        self.assertTrue(out["evidence_kept"])
        before = self.data()["records"]
        code, out, err = self.site_check("--checks", "meta.basics", out="site-2.json")
        self.assertIn(code, (0, 1), err)
        self.assertFalse(out["evidence_kept"], out)
        self.assertEqual(self.data()["records"], before)
        self.assertFalse((self.evidence / "site-2.json").exists())
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Welcome back."))
        code, out, _ = self.site_check("--checks", "meta.basics", out="site-3.json")
        self.assertTrue(out["evidence_kept"], out)                 # the edited page cites the new file
        self.assertTrue((self.evidence / "site-3.json").exists())
        self.assertTrue((self.evidence / "site-1.json").exists())  # the unchanged page still cites this one


class CoverageTest(Base):
    """0.3.0: gate and status count the required lines by how they were shown."""

    def test_counts_by_method_waived_and_missing(self):
        for check, target, method, result in (("seo.title", "site/index.html", "automated", "passed"),
                                              ("seo.title", "site/404.html", "automated", "failed"),
                                              ("browser.layout", "site/index.html", "browser", "passed")):
            code, out, err = run(RECORDS, "record", self.vpath, "--root", self.root, "--check-id", check,
                                 "--target", target, "--result", result, "--method", method,
                                 "--tool-and-version", "t 1", "--evidence-path", self.note(f"{check}{target[5:]}"),
                                 "--require", "--input", "site/404.html" if target.endswith("index.html") else
                                 "site/index.html")
            self.assertEqual(code, 0, (out, err))
        self.require("--check-id", "a11y.landmarks", "--target", "site/index.html", "--reason", "contract")
        self.require("--check-id", "a11y.landmarks", "--target", "site/404.html", "--reason", "contract")
        code, out, err = run(RECORDS, "waive", self.vpath, "--root", self.root, "--check-id", "a11y.landmarks",
                             "--target", "site/404.html", "--reason", "owner accepts", "--decided-by", "owner")
        self.assertEqual(code, 0, (out, err))
        want = {"automated": {"passed": 1, "total": 2}, "browser": {"passed": 1, "total": 1}, "waived": 1,
                "no_record": 1}
        self.assertEqual(self.gate()[1]["coverage"], want)
        _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "mockup")
        self.assertEqual(status["coverage"], want)


if __name__ == "__main__":
    unittest.main()
