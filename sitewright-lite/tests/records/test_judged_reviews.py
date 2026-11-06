"""0.3.0: a visual.review record lists the screenshots it judged (`judged`), each bound to the record
as an input, so a replaced screenshot makes the review stale; a pass without the list gets a status warning.

Run from the dev root: python3 -m unittest discover tests/records
"""
import json
import unittest

from test_batch_and_archive import Base
from test_requirements import RECORDS, run

SHOT = "docs/website/evidence/visual/home-320-light.png"


class JudgedReviewTest(Base):
    def setUp(self):
        super().setUp()
        (self.evidence / "visual").mkdir()
        for name in ("home-320-light.png", "home-1280-dark.png"):
            (self.evidence / "visual" / name).write_bytes(b"png " + name.encode())

    def review(self, *extra):
        return run(RECORDS, "record", self.vpath, "--root", self.root, "--check-id", "visual.review",
                   "--target", "site/index.html", "--result", "passed", "--method", "manual",
                   "--tool-and-version", "manual: Claude from screenshots",
                   "--evidence-path", self.note("review.md"), "--require", *extra)

    def status(self):
        return run(RECORDS, "status", self.vpath, "--root", self.root)

    def test_judged_screenshots_are_recorded_and_bound_as_inputs(self):
        code, out, err = self.review("--input", SHOT, "--judged", f"/,320,light,{SHOT}")
        self.assertEqual(code, 0, (out, err))
        rec = self.data()["records"][-1]
        self.assertEqual(rec["judged"], [{"route": "/", "width": 320, "theme": "light", "screenshot": SHOT}])
        self.assertIn(SHOT, rec["inputs"])
        self.assertEqual(self.gate()[1]["result"], "passed")
        (self.root / SHOT).write_bytes(b"a newer screenshot")
        self.assertEqual(self.gate()[1]["result"], "stale")

    def test_a_glob_input_covers_judged_screenshots(self):
        code, out, err = self.review("--input", "docs/website/evidence/visual/*.png",
                                     "--judged", f"/,320,light,{SHOT}",
                                     "--judged", "/,1280,dark,docs/website/evidence/visual/home-1280-dark.png")
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(len(self.data()["records"][-1]["judged"]), 2)

    def test_a_judged_screenshot_that_is_not_an_input_is_refused(self):
        code, out, _ = self.review("--judged", f"/,320,light,{SHOT}")
        self.assertNotEqual(code, 0)
        self.assertIn("not an --input", " ".join(out["diagnostics"]))
        self.assertFalse(self.vpath.exists() and self.data().get("records"))

    def test_malformed_or_missing_judged_entries_are_refused(self):
        for value in ("/,320,light", "/,wide,light," + SHOT, "/,320,light,docs/website/evidence/visual/none.png"):
            code, out, _ = self.review("--input", SHOT, "--judged", value)
            self.assertNotEqual(code, 0, value)

    def test_a_tampered_judged_list_makes_the_record_an_error(self):
        self.review("--input", SHOT, "--judged", f"/,320,light,{SHOT}")
        data = self.data()
        data["records"][-1]["judged"][0]["screenshot"] = "docs/website/evidence/visual/home-1280-dark.png"
        self.vpath.write_text(json.dumps(data))
        self.assertEqual(self.gate()[1]["result"], "error")

    def test_status_warns_about_a_pass_without_judged_screenshots(self):
        self.review("--input", SHOT)
        code, out, _ = self.status()
        self.assertEqual(out["result"], "passed")
        self.assertTrue(any("names no judged screenshots" in f["evidence"] for f in out["findings"]))
        self.review("--input", SHOT, "--judged", f"/,320,light,{SHOT}")
        self.assertFalse(any("judged" in f["evidence"] for f in self.status()[1]["findings"]))


if __name__ == "__main__":
    unittest.main()
