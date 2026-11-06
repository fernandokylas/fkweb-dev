"""Open issues: optional lifecycle fields in check-state, and blocking issues failing the gate."""

import json
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sw_records as base  # noqa: E402  (module import: its test classes don't run twice)

defects, run, sw_records = base.defects, base.run, base.sw_records


class IssueBlocksTest(unittest.TestCase):
    def test_levels(self):
        blocks = sw_records.issue_blocks
        self.assertEqual(blocks({"blocking": True}), "production")          # legacy
        self.assertIsNone(blocks({"blocking": False}))
        self.assertEqual(blocks({"blocking": ["launch"]}), "launch")
        self.assertEqual(blocks({"blocking": ["launch", "mockup"]}), "mockup")
        self.assertIsNone(blocks({"blocking": True, "status": "resolved"}))
        self.assertIsNone(blocks({"blocking": True, "status": "wontfix"}))
        self.assertIsNone(blocks("not an issue"))


class IssueStateTest(unittest.TestCase):
    # Only the fixture helpers of RecordsTest, not its tests.
    setUp, tearDown, state = base.RecordsTest.setUp, base.RecordsTest.tearDown, base.RecordsTest.state

    def issues(self, *issues):
        self.state(open_issues=list(issues))
        return run("check-state", self.proj / "state.json")

    def test_full_lifecycle_fields_pass(self):
        code, out, _ = self.issues(
            {"id": "OPEN-1", "issue": "hours", "blocking": ["launch"], "opened": "2026-10-31",
             "source": "owner, message of 2026-10-30", "owner": {"kind": "person", "name": "site owner"},
             "status": "open", "history": [{"date": "2026-10-31", "change": "opened"}]},
            {"id": "OPEN-2", "issue": "recipient", "blocking": True, "status": "resolved",
             "resolved": "2026-10-31, owner supplied the address", "owner": {"kind": "skill", "name": "website-build-code"}})
        self.assertEqual(code, 0, out["findings"])

    def test_bad_fields_are_defects(self):
        cases = {"blocking": {"blocking": ["live"]}, "status": {"status": "done"},
                 "owner": {"owner": "Fernando"}, "history": {"history": "opened"}, "`opened`": {"opened": 31}}
        for needle, change in cases.items():
            with self.subTest(needle):
                code, out, _ = self.issues(dict({"id": "OPEN-9", "issue": "x", "blocking": False}, **change))
                self.assertEqual(code, 1)
                self.assertTrue(any(needle in f["evidence"] for f in defects(out)), out["findings"])

    def test_closed_without_resolved_warns(self):
        code, out, _ = self.issues({"id": "OPEN-3", "issue": "x", "blocking": True, "status": "wontfix"})
        self.assertEqual(code, 0)
        self.assertTrue(any("without `resolved`" in f["evidence"] for f in out["findings"]))


class IssueGateTest(base.GateBase):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.record()[0], 0)

    def issues(self, *issues, where=None):
        (where or self.tmp / "state.json").write_text(json.dumps({"open_issues": list(issues)}))

    def gate_mode(self, mode, *extra):
        return run("gate", self.vfile, "--mode", mode, *extra)

    def test_no_state_record_changes_nothing(self):
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_legacy_blocking_true_fails_production_not_mockup(self):
        self.issues({"id": "OPEN-2", "issue": "order email recipient", "blocking": True})
        code, out, _ = self.gate_mode("production")
        self.assertEqual((code, out["result"]), (1, "failed"))
        line = [c for c in out["checks"] if c["check_id"] == "issue.OPEN-2"]
        self.assertEqual(len(line), 1)
        self.assertIn("order email recipient", line[0]["reason"])
        self.assertEqual(self.gate_mode("mockup")[1]["result"], "passed")

    def test_mockup_level_blocks_both_modes_and_launch_only_blocks_neither(self):
        self.issues({"id": "OPEN-1", "issue": "logo", "blocking": ["mockup"]},
                    {"id": "OPEN-4", "issue": "translations", "blocking": ["launch"]})
        for mode in ("mockup", "production"):
            out = self.gate_mode(mode)[1]
            ids = {c["check_id"] for c in out["checks"] if c["check_id"].startswith("issue.")}
            self.assertEqual(ids, {"issue.OPEN-1"}, mode)

    def test_closed_and_non_blocking_issues_do_not_fail(self):
        self.issues({"id": "OPEN-1", "issue": "a", "blocking": False},
                    {"id": "OPEN-2", "issue": "b", "blocking": True, "status": "resolved", "resolved": "today"})
        self.assertEqual(self.gate_mode("production")[1]["result"], "passed")

    def test_state_override_and_unreadable_state(self):
        other = self.tmp / "elsewhere.json"
        self.issues({"id": "OPEN-7", "issue": "x", "blocking": True}, where=other)
        self.assertEqual(self.gate()[1]["result"], "passed")
        self.assertEqual(self.gate_mode("production", "--state", other)[1]["result"], "failed")
        (self.tmp / "state.json").write_text("{broken")
        code, out, _ = self.gate()
        self.assertEqual(out["result"], "passed")
        self.assertTrue(any("state record unreadable" in d for d in out["diagnostics"]))


if __name__ == "__main__":
    unittest.main()
