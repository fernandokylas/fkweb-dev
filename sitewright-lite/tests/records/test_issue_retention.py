"""Issues are closed, never deleted (checked against the last commit), and owner tasks stay owner tasks."""

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sw_records as base  # noqa: E402  (module import: its test classes don't run twice)

run = base.run
ISSUE = {"id": "OPEN-1", "issue": "opening hours missing", "blocking": False}


def found(out, needle, severity=None):
    return [f for f in out["findings"] if needle in f["evidence"] and severity in (None, f["severity"])]


@unittest.skipUnless(shutil.which("git"), "git not installed")
class IssueRetentionTest(unittest.TestCase):
    # Only the fixture helpers of RecordsTest, not its tests.
    setUp_, tearDown, state = base.RecordsTest.setUp, base.RecordsTest.tearDown, base.RecordsTest.state

    def setUp(self):
        self.setUp_()
        self.git("init", "-q")
        self.state(open_issues=[ISSUE, dict(ISSUE, id="OPEN-2", issue="logo file")])
        self.git("add", "state.json")
        self.git("commit", "-q", "-m", "state")

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                        "-C", str(self.proj), *args], check=True, capture_output=True)

    def check(self, **changes):
        self.state(**changes)
        return run("check-state", self.proj / "state.json", "--root", self.proj)

    def test_deleted_issue_is_a_defect(self):
        code, out, _ = self.check(open_issues=[ISSUE])
        self.assertEqual(code, 1)
        gone = found(out, "issue OPEN-2 is in the last commit's state.json but no longer listed", "defect")
        self.assertEqual(len(gone), 1, out["findings"])
        self.assertIn("never deleted", gone[0]["action"])

    def test_closed_issue_is_fine(self):
        code, out, _ = self.check(open_issues=[ISSUE, dict(ISSUE, id="OPEN-2", status="resolved",
                                                           resolved="2026-10-31, owner sent the logo")])
        self.assertFalse(found(out, "no longer listed"), out["findings"])

    def test_no_commit_of_state_is_not_checked(self):
        self.git("rm", "-q", "--cached", "state.json")
        self.git("commit", "-q", "-m", "untrack")
        self.assertFalse(found(self.check(open_issues=[])[1], "no longer listed"))


class HousekeepingOwnerTest(unittest.TestCase):
    setUp, tearDown, state = base.RecordsTest.setUp, base.RecordsTest.tearDown, base.RecordsTest.state

    def owner_task(self, text, kind="person"):
        self.state(open_issues=[{"id": "OPEN-5", "issue": text, "blocking": False,
                                 "owner": {"kind": kind, "name": "site owner"}}])
        return run("check-state", self.proj / "state.json")[1]

    def test_plugin_housekeeping_routed_to_a_person_warns(self):
        for text in ("Re-record the browser checks in verification.json", "Compact the verification record",
                     "run prune-evidence after launch"):
            with self.subTest(text):
                self.assertTrue(found(self.owner_task(text), "gives the owner plugin housekeeping", "warning"))
        for text in ("Approve the compact header design", "Send the final logo"):
            with self.subTest(text):
                self.assertFalse(found(self.owner_task(text), "housekeeping"))
        self.assertFalse(found(self.owner_task("Re-record the checks", kind="skill"), "housekeeping"))


if __name__ == "__main__":
    unittest.main()
