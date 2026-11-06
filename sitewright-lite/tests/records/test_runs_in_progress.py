"""Runs in progress: `begin` marks a multi-step run; the gate reads `error` until `record` clears it."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sw_records as base  # noqa: E402  (module import: its test classes don't run twice)

run = base.run
KEY = ("a11y.landmarks", "site/index.html")


class RunsInProgressTest(base.GateBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.record()[0], 0)          # an older pass exists
        self.assertEqual(self.gate()[1]["result"], "passed")

    def begin(self, *extra):
        return run("begin", self.vfile, "--check-id", KEY[0], "--target", KEY[1], *extra)

    def data(self):
        return json.loads(self.vfile.read_text())

    def test_crashed_run_never_leaves_the_old_pass_standing(self):
        code, out, _ = self.begin()
        self.assertEqual(code, 0, out)
        marker = self.data()["runs_in_progress"][0]
        self.assertTrue(marker["fingerprint"].startswith("sha256:"), marker)
        # The run "crashes": nothing is recorded. The gate must not report the older pass.
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "error"))
        self.assertIn("never recorded", out["checks"][0]["reason"])
        # Recording the run clears the marker.
        self.assertEqual(self.record()[0], 0)
        self.assertEqual(self.data()["runs_in_progress"], [])
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_cancel_removes_the_marker(self):
        self.begin()
        code, out, _ = self.begin("--cancel")
        self.assertEqual((code, out["cancelled"]), (0, 1))
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_target_changed_during_the_run_is_refused(self):
        self.begin()
        page = self.tmp / KEY[1]
        page.write_text(page.read_text() + "<!-- edited mid-run -->")
        code, out, _ = self.record()
        self.assertEqual(code, 2)
        self.assertTrue(any("changed after `begin`" in d for d in out["diagnostics"]), out["diagnostics"])
        self.assertEqual(len(self.data()["runs_in_progress"]), 1)   # nothing written

    def test_marker_for_another_mode_does_not_block(self):
        self.begin("--mode", "mockup")
        self.assertEqual(self.gate()[1]["result"], "passed")          # production gate
        self.assertEqual(run("gate", self.vfile, "--mode", "mockup")[1]["result"], "error")

    def test_unknown_target_is_refused(self):
        code, out, _ = run("begin", self.vfile, "--check-id", KEY[0], "--target", "site/missing.html")
        self.assertEqual(code, 2)
        self.assertNotIn("runs_in_progress", self.data())


if __name__ == "__main__":
    unittest.main()
