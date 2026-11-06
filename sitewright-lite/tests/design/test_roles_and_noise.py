"""Regression tests for the rc.3 changes to scripts/sw_design_check.py: tracking judged by role (labels,
running text, uncertain), the design record's accepted label tracking, the contrast basis and grouping of
inferred pairs, grouped token drift, and the static layout review checks.

Run from the dev root: python3 -m unittest discover tests/design
Each case copies the `pass/` fixture to a scratch directory and appends rules to its stylesheet.
"""
import json
import unittest

from test_design_check import RECORDS, ScratchCase, findings, run, site

CSS = "site/assets/style.css"


def of(report, check_id, kind=None):
    return [f for f in report["findings"] if f["check_id"] == check_id and (kind is None or f["kind"] == kind)]


class RoleCase(ScratchCase):
    def append(self, css):
        with open(self.base / CSS, "a") as fh:
            fh.write("\n" + css + "\n")

    def check(self, *checks, extra=()):
        code, report, err = site(self.base, "--checks", ",".join(checks), *extra)
        self.assertIsNotNone(report, err)
        return code, report


class TrackingRoleTest(RoleCase):
    LABELS = """
.meta-list dt { font-size: 0.75rem; letter-spacing: 0.16em; text-transform: uppercase; }
.table thead th { letter-spacing: 0.16em; text-transform: uppercase; }
.frame__label strong { font-size: 0.7rem; letter-spacing: 0.16em; text-transform: uppercase; }
.split dt { text-transform: uppercase; }
.split dt { letter-spacing: 0.16em; }
.caps li { font-variant-caps: all-small-caps; letter-spacing: 0.12em; }
"""

    def test_uppercase_labels_on_text_tags_are_not_running_text(self):
        self.append(self.LABELS)
        code, report = self.check("style.tracking")
        self.assertEqual((code, report["result"]), (0, "passed"), report)
        self.assertEqual(of(report, "style.tracking"), [])

    def test_running_text_still_fails_and_uncertain_roles_get_review_only(self):
        self.append("""
.note p { letter-spacing: 0.15em; }
.hero p { font-size: 2rem; text-transform: uppercase; letter-spacing: 0.2em; }
.inline span { letter-spacing: 0.15em; }
.path > li::before { content: counter(step); position: absolute; letter-spacing: 0.16em; }
.kicker strong { text-transform: uppercase; letter-spacing: 0.3em; }
""")
        code, report = self.check("style.tracking")
        self.assertEqual((code, report["result"]), (1, "failed"), report)
        defects = findings(report, "style.tracking")
        self.assertEqual(len(defects), 2, defects)
        self.assertTrue(any(d.startswith(".note p:") for d in defects))
        self.assertTrue(any(d.startswith(".hero p:") for d in defects))   # uppercase but 32px: not a label
        review = {f["evidence"].split(":")[0] for f in of(report, "style.tracking", "review")}
        self.assertEqual(review, {".inline span", ".path > li"}, review)
        self.assertTrue(all(f["severity"] == "warning" for f in of(report, "style.tracking", "review")))
        label = [f for f in of(report, "style.tracking", "convention") if f.get("role") == "label"]
        self.assertEqual(len(label), 1)
        self.assertIn("default label maximum 0.25em", label[0]["evidence"])

    def test_design_record_sets_the_accepted_label_tracking(self):
        self.append(self.LABELS)
        self.copy.edit("records/website.md", "- layout_rules:", "- label_tracking_max: 0.12em\n- layout_rules:")
        code, report = self.check("style.tracking")
        self.assertEqual(code, 0, report)
        over = [f["evidence"] for f in of(report, "style.tracking") if f.get("role") == "label"]
        self.assertEqual(len(over), 4, over)          # the four 0.16em labels; 0.12em small caps sits at the limit
        self.assertTrue(all("label_tracking_max 0.12em" in e for e in over))

    def test_unreadable_label_tracking_falls_back_with_a_diagnostic(self):
        self.copy.edit("records/website.md", "- layout_rules:", "- label_tracking_max: generous\n- layout_rules:")
        code, report = self.check("style.tracking")
        self.assertEqual(code, 0, report)
        self.assertTrue(any("label_tracking_max" in d for d in report["diagnostics"]), report)

    def test_accepted_label_tracking_binds_the_design_record(self):
        self.copy.edit("records/website.md", "- layout_rules:", "- label_tracking_max: 0.16em\n- layout_rules:")
        verification = self.base / "docs" / "website" / "verification.json"
        evidence = self.base / "docs" / "website" / "evidence" / "design.json"
        code, report, err = site(self.base, "--checks", "style.tracking", "--record", verification,
                                 "--evidence-out", evidence, "--require")
        self.assertEqual(code, 0, (err, report))
        record = json.loads(verification.read_text())["records"][0]
        self.assertIn("records/website.md", record["inputs"])
        self.copy.edit("records/website.md", "label_tracking_max: 0.16em", "label_tracking_max: 0.2em")
        gcode, gate, _ = run("gate", verification, "--root", self.base, script=RECORDS)
        self.assertEqual(gate["result"], "stale", gate)


class ContrastNoiseTest(RoleCase):
    def test_declared_pairs_are_defects_and_inferred_pairs_are_grouped(self):
        self.append("""
.declared { color: #777777; background: #888888; }
.swatch-a { color: #f7f5ef; }
.swatch-b { color: #f7f5ef; }
.faint-a { color: #c9c4b8; }
.faint-b { color: #c9c4b8; }
.faint-c { color: #c9c4b8; }
""")
        code, report = self.check("style.contrast")
        self.assertEqual((code, report["result"]), (1, "failed"), report)
        declared = [f for f in of(report, "style.contrast") if f.get("basis") == "declared"]
        self.assertTrue(declared)                      # one per colour scheme the CSS defines
        self.assertTrue(all(f["severity"] == "defect" and f["evidence"].startswith(".declared:") for f in declared))
        inferred = [f for f in of(report, "style.contrast") if f.get("basis") == "inferred"
                    and "#f7f5ef on #f7f5ef" in f["evidence"]]
        self.assertEqual(len(inferred), 1, inferred)
        self.assertEqual(inferred[0]["selectors"], [".swatch-a", ".swatch-b"])
        self.assertIn("non-text element", inferred[0]["action"])
        faint = [f for f in of(report, "style.contrast") if f.get("basis") == "inferred"
                 and f["evidence"].startswith(".faint-a, .faint-b, .faint-c:")]
        self.assertEqual(len(faint), 1, of(report, "style.contrast"))
        self.assertIn("static inference", faint[0]["evidence"])
        self.assertTrue(all(f["severity"] == "warning" for f in of(report, "style.contrast")
                            if f.get("basis") == "inferred"))
        self.assertGreaterEqual(report["contrast_pairs"]["inferred"], 5)


class TokenDriftNoiseTest(RoleCase):
    def test_unnamed_root_tokens_are_one_actionable_warning_per_sheet(self):
        self.append(":root { --hk-gap-x: 1.5rem; --hk-ease: cubic-bezier(.2, 0, 0, 1); --hk-rule: #dddddd; }")
        code, report = self.check("design.token-drift")
        self.assertEqual(code, 0, report)
        drift = of(report, "design.token-drift")
        self.assertEqual(len(drift), 1, drift)
        self.assertEqual(sorted(drift[0]["tokens"]), ["--hk-ease", "--hk-gap-x", "--hk-rule"])
        self.assertIn("3 root tokens", drift[0]["evidence"])
        self.assertIn("--hk-rule (#dddddd)", drift[0]["evidence"])
        self.assertIn("semantic_tokens", drift[0]["action"])
        self.assertIn("component-private", drift[0]["action"])


class LayoutReviewTest(RoleCase):
    def test_clean_fixture_has_no_layout_findings(self):
        code, report = self.check("layout.grid-items", "layout.spacing-reset")
        self.assertEqual((code, report["result"]), (0, "passed"), report)
        self.assertEqual(of(report, "layout.grid-items") + of(report, "layout.spacing-reset"), [])

    def test_generated_box_in_a_grid_is_flagged_for_review(self):
        self.append("""
.path { display: grid; grid-template-columns: repeat(3, 1fr); }
.path::before { content: ""; border-top: 1px solid currentColor; }
.row { display: flex; }
.row::after { content: ""; position: absolute; inset: 0; }
.list { display: grid; }
.list::before { content: none; }
""")
        code, report = self.check("layout.grid-items")
        self.assertEqual(code, 0, report)                    # a review warning never fails the check
        hits = of(report, "layout.grid-items", "review")
        self.assertEqual(len(hits), 1, hits)
        self.assertTrue(hits[0]["evidence"].startswith(".path::before"))
        self.assertIn("visual.measure", hits[0]["action"])

    def test_later_heading_margin_reset_is_flagged_for_review(self):
        self.append("""
h2 { margin-top: 2.5rem; }
.card h2 { margin: 0 0 0.5rem; }
h3 { margin-top: 0; }
""")
        code, report = self.check("layout.spacing-reset")
        self.assertEqual(code, 0, report)
        hits = of(report, "layout.spacing-reset", "review")
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(".card h2 sets the top margin of h2 to 0 after h2", hits[0]["evidence"])


if __name__ == "__main__":
    unittest.main()
