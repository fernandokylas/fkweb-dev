"""Decisions name the documents they updated; a pivot must reach those documents."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sw_records as base  # noqa: E402  (module import: its test classes don't run twice)

run = base.run


def found(out, needle, severity=None):
    return [f for f in out["findings"] if needle in f["evidence"] and severity in (None, f["severity"])]


class DecisionUpdatesTest(unittest.TestCase):
    # Only the fixture helpers of RecordsTest, not its tests.
    setUp, tearDown, state = base.RecordsTest.setUp, base.RecordsTest.tearDown, base.RecordsTest.state

    def check(self, *decisions):
        self.state(accepted_decisions=list(decisions))
        return run("check-state", self.proj / "state.json", "--root", self.proj)

    def doc(self, rel, text):
        path = self.proj / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def test_shape(self):
        code, out, _ = self.check({"id": "D-1", "decision": "x", "reason": "y", "updates": "brief.md"})
        self.assertEqual(code, 1)
        self.assertTrue(found(out, "`updates` must list project-relative paths", "defect"))
        code, out, _ = self.check({"id": "D-1", "decision": "x", "reason": "y", "updates": ["/etc/brief.md"]})
        self.assertTrue(found(out, "`updates` must list", "defect"))

    def test_listed_paths_must_exist(self):
        self.doc("docs/website/brief.md", "Brief.")
        code, out, _ = self.check({"id": "D-1", "decision": "x", "reason": "y",
                                   "updates": ["docs/website/brief.md", "docs/website/design.md"]})
        self.assertEqual(code, 0, out["findings"])
        self.assertEqual([f["location"] for f in found(out, "which is not a file")], ["docs/website/design.md"])

    def test_superseding_decision_must_reach_its_documents(self):
        self.doc("docs/website/brief.md", "Audience: families (D-7).")
        self.doc("docs/website/design.md", "Palette per D-3, dark green.")
        old = {"id": "D-3", "decision": "dark green", "reason": "r", "status": "superseded", "superseded_by": "D-7"}
        new = {"id": "D-7", "decision": "warm palette", "reason": "r",
               "updates": ["docs/website/brief.md", "docs/website/design.md"]}
        code, out, _ = self.check(old, new)
        self.assertEqual(code, 0, out["findings"])
        stale = found(out, "does not mention decision D-7", "warning")
        self.assertEqual([f["location"] for f in stale], ["docs/website/design.md"], out["findings"])
        self.assertIn("superseded D-3", stale[0]["evidence"])
        self.doc("docs/website/design.md", "Palette per D-70.")              # a longer id is not a mention
        self.assertTrue(found(self.check(old, new)[1], "does not mention decision D-7"))
        self.doc("docs/website/design.md", "Warm palette (D-7), replacing D-3.")
        self.assertFalse(found(self.check(old, new)[1], "does not mention"))

    def test_plain_decision_needs_no_mention(self):
        self.doc("docs/website/brief.md", "Brief.")
        code, out, _ = self.check({"id": "D-1", "decision": "x", "reason": "y", "updates": ["docs/website/brief.md"]})
        self.assertFalse(found(out, "does not mention"))


if __name__ == "__main__":
    unittest.main()
