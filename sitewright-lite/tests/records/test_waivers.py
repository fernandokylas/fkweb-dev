"""Waivers v2: owner, expiry and scope, and the `waive` command."""

import datetime
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sw_records as base  # noqa: E402  (module import: its test classes don't run twice)

run, sw_records = base.run, base.sw_records
TODAY = datetime.date(2026, 10, 31)
KEY = ("a11y.landmarks", "site/index.html")


def waiver(**extra):
    return dict({"check_id": KEY[0], "target": KEY[1], "reason": "owner accepts", "decided_by": "owner"}, **extra)


class WaiverLineTest(unittest.TestCase):
    def line(self, *waivers, level="production"):
        return sw_records.waiver_line(list(waivers), KEY, level, today=TODAY)

    def test_legacy_waiver_counts_with_a_note(self):
        result, _, note = self.line(waiver())
        self.assertEqual(result, "waived")
        self.assertIn("legacy waiver", note)

    def test_needs_reason_and_decider(self):
        self.assertIsNone(self.line(waiver(decided_by="")))
        self.assertIsNone(self.line(waiver(reason="")))

    def test_expiry(self):
        self.assertEqual(self.line(waiver(expires="2026-10-31"))[:1], ("waived",))   # last valid day
        result, reason, _ = self.line(waiver(expires="2026-10-30", owner="ops"))
        self.assertEqual(result, "stale")
        self.assertIn("expired 2026-10-30", reason)
        self.assertEqual(self.line(waiver(expires="soon"))[0], "error")

    def test_scope_is_matched_exactly(self):
        self.assertIsNone(self.line(waiver(scope=["mockup"])))
        self.assertEqual(self.line(waiver(scope=["mockup"]), level="mockup")[0], "waived")
        self.assertIsNone(self.line(waiver(scope=["production"]), level="launch"))

    def test_newest_waiver_decides(self):
        self.assertEqual(self.line(waiver(), waiver(expires="2026-01-01"))[0], "stale")


class WaiveCommandTest(base.GateBase):
    def waive(self, *extra):
        return run("waive", self.vfile, "--check-id", KEY[0], "--target", KEY[1], "--reason", "owner accepts", *extra)

    def data(self):
        return json.loads(self.vfile.read_text())

    def test_grant_needs_decider(self):
        code, out, _ = self.waive()
        self.assertEqual((code, out["result"]), (2, "error"))
        self.assertTrue(any("--decided-by is required" in d for d in out["diagnostics"]))
        self.assertEqual(self.data()["waivers"], [])

    def test_grant_then_gate_then_remove(self):
        self.assertEqual(self.gate()[1]["result"], "unavailable")
        code, out, _ = self.waive("--decided-by", "owner", "--owner", "studio", "--expires", "2099-01-01",
                                  "--scope", "production,mockup")
        self.assertEqual(code, 0, out)
        w = self.data()["waivers"][0]
        self.assertEqual((w["owner"], w["expires"], w["scope"]), ("studio", "2099-01-01", ["mockup", "production"]))
        history = self.data()["requirement_history"]
        self.assertEqual((history[-1]["action"], history[-1]["weakens"]), ("waive", True))
        code, out, _ = self.gate()
        self.assertEqual(out["result"], "passed")
        self.assertIn("owner studio", out["checks"][0]["reason"])
        # Re-waiving replaces rather than stacking.
        self.waive("--decided-by", "owner", "--expires", "2099-02-01")
        self.assertEqual(len(self.data()["waivers"]), 1)
        code, out, _ = self.waive("--remove")
        self.assertEqual((code, out["change"]), (0, "unwaive"))
        self.assertEqual(self.data()["waivers"], [])
        self.assertEqual(self.gate()[1]["result"], "unavailable")

    def test_refusals(self):
        cases = {"not a required check": ["--check-id", "perf.lab"],
                 "--expires must be a date": ["--expires", "31/10/2099"],
                 "--expires is in the past": ["--expires", "2001-01-01"],
                 "--scope must list": ["--scope", "live"]}
        for needle, extra in cases.items():
            with self.subTest(needle):
                code, out, _ = run("waive", self.vfile, "--check-id", KEY[0], "--target", KEY[1],
                                   "--reason", "r", "--decided-by", "owner", *extra)
                self.assertEqual(code, 2)
                self.assertTrue(any(needle in d for d in out["diagnostics"]), out["diagnostics"])

    def test_status_warns_about_legacy_waivers(self):
        data = self.data()
        data["waivers"] = [waiver()]
        self.vfile.write_text(json.dumps(data))
        code, out, _ = run("status", self.vfile)
        self.assertEqual(out["result"], "passed")
        self.assertTrue(any("legacy waiver" in f["evidence"] for f in out["findings"]))


if __name__ == "__main__":
    unittest.main()
