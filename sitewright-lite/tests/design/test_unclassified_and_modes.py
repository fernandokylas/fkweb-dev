"""Regression tests for rc.3 live-test findings 4 and 6 in sw_design_check.py: class-only selectors whose
text role cannot be settled statically are reported and routed to browser review (never invented, never a
hard failure), and --mode selects criteria without tagging mode-neutral records.

Run from the dev root: python3 -m unittest discover tests/design
"""
import json
import unittest

from test_design_check import RECORDS, run, site, findings
from test_roles_and_noise import RoleCase, of


class UnclassifiedRoleTest(RoleCase):
    def test_class_only_rule_gets_review_and_a_record_limitation_not_a_defect(self):
        self.append(".intro { letter-spacing: 0.3em; }\n#lead { letter-spacing: -0.05em; }\n"
                    "[data-tone] { letter-spacing: 0.04em; }")
        verification = self.base / "docs" / "website" / "verification.json"
        code, report, err = site(self.base, "--checks", "style.tracking", "--record", verification, "--require",
                                 "--evidence-out", self.base / "docs" / "website" / "evidence" / "t.json")
        self.assertEqual((code, report["result"]), (0, "passed"), (err, report))
        self.assertEqual(findings(report, "style.tracking"), [])
        review = {f["evidence"].split(":")[0] for f in of(report, "style.tracking", "review")}
        self.assertEqual(review, {".intro", "#lead"})            # 0.04em is inside the range: nothing to review
        unclassified = [f for f in of(report, "style.tracking", "review") if f.get("role") == "unclassified"]
        self.assertEqual(len(unclassified), 2, report["findings"])
        self.assertTrue(all("browser" in f["action"] for f in unclassified))
        self.assertEqual([u["selector"] for u in report["tracking_unclassified"]], [".intro", "#lead"])
        record = json.loads(verification.read_text())["records"][0]
        self.assertEqual(record["result"], "passed")
        self.assertIn(".intro", record["limitations"])
        self.assertIn("browser review", record["limitations"])
        gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
        line = next(c for c in gate["checks"] if c["check_id"] == "style.tracking")
        self.assertIn(".intro", line["limitations"])

    def test_tagged_selector_still_fails_and_has_no_limitation(self):
        self.append("p.intro { letter-spacing: 0.3em; }")
        code, report = self.check("style.tracking")
        self.assertEqual((code, report["result"]), (1, "failed"), report)
        self.assertTrue(any(d.startswith("p.intro:") for d in findings(report, "style.tracking")))
        self.assertEqual(report["tracking_unclassified"], [])

    def test_large_uppercase_class_is_unclassified_not_a_label(self):
        self.append(".banner { font-size: 20px; text-transform: uppercase; letter-spacing: 0.2em; }")
        code, report = self.check("style.tracking")
        self.assertEqual(code, 0, report)
        self.assertEqual([u["selector"] for u in report["tracking_unclassified"]], [".banner"])
        self.assertEqual(findings(report, "style.tracking"), [])

    def test_tracking_record_binds_the_design_record(self):
        verification = self.base / "docs" / "website" / "verification.json"
        code, report, err = site(self.base, "--checks", "style.tracking", "--record", verification, "--require",
                                 "--evidence-out", self.base / "docs" / "website" / "evidence" / "t.json")
        self.assertEqual(code, 0, (err, report))
        record = json.loads(verification.read_text())["records"][0]
        self.assertIn("records/website.md", record["inputs"])


class ModeTest(RoleCase):
    def test_mode_production_tags_only_release_sensitive_records(self):
        verification = self.base / "docs" / "website" / "verification.json"
        code, report, err = site(self.base, "--mode", "production", "--record", verification, "--require",
                                 "--evidence-out", self.base / "docs" / "website" / "evidence" / "d.json")
        self.assertIsNotNone(report, err)
        tagged = {c for c, m in report["modes_written"].items() if m}
        self.assertEqual(tagged, {"assets.rights", "assets.local-path", "assets.final"})
        self.assertEqual({m for m in report["modes_written"].values() if m}, {"production"})
        modes = {r["check_id"]: r.get("mode") for r in json.loads(verification.read_text())["records"]}
        self.assertIsNone(modes["style.tracking"])
        self.assertEqual(modes["assets.final"], "production")
        # mode-neutral checks count for the mock-up gate even though the run judged production criteria
        gcode, gate, _ = run("gate", verification, "--root", self.base, "--mode", "mockup", script=RECORDS)
        mock = {c["check_id"]: c["result"] for c in gate["checks"]}
        self.assertEqual(mock["style.tracking"], "passed")
        self.assertEqual(mock["assets.final"], "unavailable")

    def test_mockup_mode_with_release_is_an_error(self):
        code, report, _ = site(self.base, "--mode", "mockup", "--release")
        self.assertEqual((code, report["result"]), (2, "error"))


if __name__ == "__main__":
    unittest.main()
