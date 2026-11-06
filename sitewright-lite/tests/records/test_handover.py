"""Handover: next_action stays short and portable; the handover file exists and stays small."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_sw_records as base  # noqa: E402  (module import: its test classes don't run twice)

run = base.run


def found(out, needle, severity=None):
    return [f for f in out["findings"] if needle in f["evidence"] and severity in (None, f["severity"])]


class HandoverTest(unittest.TestCase):
    # Only the fixture helpers of RecordsTest, not its tests.
    setUp, tearDown, state = base.RecordsTest.setUp, base.RecordsTest.tearDown, base.RecordsTest.state

    def check(self, **changes):
        self.state(**changes)
        return run("check-state", self.proj / "state.json", "--root", self.proj)

    def write_handover(self, text="Phase implement; next: build the contact page.\n", name="HANDOVER.md"):
        path = self.proj / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_missing_handover_warns_then_fails_at_handoff(self):
        code, out, _ = self.check()
        self.assertEqual(code, 0, out["findings"])
        self.assertTrue(found(out, "no handover file", "warning"))
        code, out, _ = self.check(current_phase="handoff")
        self.assertEqual(code, 1)
        self.assertTrue(found(out, "no handover file", "defect"))

    def test_handover_beside_state_or_named(self):
        self.write_handover()
        code, out, _ = self.check()
        self.assertFalse(found(out, "handover"), out["findings"])
        self.write_handover(name="notes/handover.md")
        code, out, _ = self.check(handover="notes/handover.md", current_phase="handoff")
        self.assertEqual(code, 0, out["findings"])
        code, out, _ = self.check(handover="/abs/handover.md")
        self.assertTrue(found(out, "`handover` must be a project-relative path", "defect"))

    def test_large_handover(self):
        self.write_handover("x" * 9000)
        code, out, _ = self.check()
        self.assertTrue(found(out, "handover file is 9000 bytes", "warning"))

    def test_next_action_length_and_absolute_paths(self):
        self.write_handover()
        code, out, _ = self.check(next_action="Build the page. " * 25)
        self.assertEqual(code, 0)
        self.assertTrue(found(out, "characters (keep it under 300)"))
        home, disk = "/" + "Users/me", "/" + "Volumes/Work"     # split: shipped files never name local paths
        for action in (f"Run python3 {home}/plugins/sw/scripts/sw_records.py status x.json --root .",
                       f"Open \"{disk}/site/index.html\" and fix the header",
                       r"Check C:\projects\site\index.html"):
            with self.subTest(action):
                code, out, _ = self.check(next_action=action)
                self.assertTrue(found(out, "names an absolute path"), out["findings"])
        code, out, _ = self.check(next_action="Fix the hero in site/index.html, then re-run the gate with --root .")
        self.assertFalse(found(out, "absolute path"))

    def test_named_files_must_exist_unless_created(self):
        self.write_handover()
        (self.proj / "site").mkdir(exist_ok=True)
        (self.proj / "site" / "index.html").write_text("<h1>x</h1>")
        code, out, _ = self.check(next_action="Fix the hero in site/index.html and site/about.html.")
        names = [f["evidence"] for f in found(out, "which does not exist")]
        self.assertEqual(names, ["`next_action` names site/about.html, which does not exist in the project"])
        code, out, _ = self.check(next_action="Create site/contact.html from the page contract.")
        self.assertFalse(found(out, "which does not exist"))
        self.write_handover("{}", name="docs/website/verification.json")    # the plugin path is never checked
        code, out, _ = self.check(next_action='Run python3 "<plugin>/scripts/sw_records.py" gate '
                                              "docs/website/verification.json --root . --mode mockup")
        self.assertFalse(found(out, "which does not exist"), out["findings"])


class AcceptanceItemsTest(unittest.TestCase):
    setUp, tearDown, edit = base.RecordsTest.setUp, base.RecordsTest.tearDown, base.RecordsTest.edit

    def test_handoff_lists_free_text_acceptance_items(self):
        self.edit("- acceptance_checks: nav.internal-links, a11y.landmarks\n",
                  "- acceptance_checks: nav.internal-links, tap-to-call works on mobile; `map.embed` (lazy), n/a\n")
        self.assertEqual(base.sw_records.acceptance_free_text("a.b, tap to call; index.html, n/a, `c.d` (x)"),
                         ["tap to call", "index.html"])
        _, out, _ = run("check-records", self.proj, "--phase", "handoff")
        self.assertEqual([i["item"] for i in out["acceptance_items"]], ["tap-to-call works on mobile"])
        self.assertTrue(out["acceptance_items"][0]["route"].startswith("/"))
        _, out, _ = run("check-records", self.proj, "--phase", "implement")
        self.assertNotIn("acceptance_items", out)


if __name__ == "__main__":
    unittest.main()
