"""Launch stage: required checks with stages ["launch"] are assessed only by gate --stage launch."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sw_records as base  # noqa: E402  (module import: its test classes don't run twice)

run = base.run
LIVE = ("launch.live-pages", "site/index.html")


class LaunchStageTest(base.GateBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.record()[0], 0)

    def data(self):
        return json.loads(self.vfile.read_text())

    def require(self, *extra):
        return run("require", self.vfile, "--check-id", LIVE[0], "--target", LIVE[1],
                   "--reason", "served pages checked after deploy", *extra)

    def gate_at(self, *extra):
        return run("gate", self.vfile, *extra)

    def test_new_launch_check_is_production_only_and_deferred(self):
        code, out, _ = self.require("--stage", "launch")
        self.assertEqual((code, out["change"]), (0, "add"), out)
        entry = next(r for r in self.data()["required_checks"] if r["check_id"] == LIVE[0])
        self.assertEqual((entry["modes"], entry["stages"]), (["production"], ["launch"]))
        self.assertEqual(self.data()["requirement_history"][-1]["to_stages"], ["launch"])
        # The ordinary production gate still passes and lists it as not assessed.
        code, out, _ = self.gate_at()
        self.assertEqual(out["result"], "passed")
        self.assertTrue(any(n["check_id"] == LIVE[0] and "--stage launch" in n["reason"] for n in out["not_assessed"]))
        # The launch stage assesses it: no record yet.
        code, out, _ = self.gate_at("--stage", "launch")
        self.assertEqual((code, out["result"], out["stage"]), (1, "unavailable", "launch"))
        self.record(check_id=LIVE[0])
        self.assertEqual(self.gate_at("--stage", "launch")[1]["result"], "passed")

    def test_stage_needs_production_mode(self):
        code, out, _ = self.gate_at("--mode", "mockup", "--stage", "launch")
        self.assertEqual((code, out["result"]), (2, "error"))
        code, out, _ = self.require("--stage", "launch", "--modes", "mockup,production")
        self.assertEqual(code, 2)

    def test_moving_an_existing_check_to_launch_is_a_weakening(self):
        args = ["require", self.vfile, "--check-id", "a11y.landmarks", "--target", "site/index.html",
                "--modes", "production", "--stage", "launch", "--reason", "only checked once live"]
        code, out, _ = run(*args)
        self.assertEqual(code, 2)
        self.assertTrue(any("every gate before launch" in d for d in out["diagnostics"]), out["diagnostics"])
        code, out, _ = run(*args, "--decided-by", "owner")
        self.assertEqual(code, 0, out)
        self.assertTrue(self.data()["requirement_history"][-1]["weakens"])
        self.assertTrue(any("only by the production gate with --stage launch" in d for d in out["notes"]))
        # Back to every gate is a strengthening: no decider needed.
        code, out, _ = run("require", self.vfile, "--check-id", "a11y.landmarks", "--target", "site/index.html",
                           "--modes", "production", "--stage", "every", "--reason", "check it before launch too")
        self.assertEqual(code, 0, out)
        self.assertNotIn("stages", self.data()["required_checks"][0])

    def test_launch_scoped_issue_and_waiver(self):
        (self.tmp / "state.json").write_text(json.dumps(
            {"open_issues": [{"id": "OPEN-4", "issue": "translations unreviewed", "blocking": ["launch"]}]}))
        self.assertEqual(self.gate_at()[1]["result"], "passed")
        code, out, _ = self.gate_at("--stage", "launch")
        self.assertEqual(out["result"], "failed")
        self.assertIn("issue.OPEN-4", {c["check_id"] for c in out["checks"]})

    def test_malformed_stages_is_an_error(self):
        data = self.data()
        data["required_checks"][0]["stages"] = ["live"]
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.gate_at()[1]["result"], "error")


if __name__ == "__main__":
    unittest.main()
