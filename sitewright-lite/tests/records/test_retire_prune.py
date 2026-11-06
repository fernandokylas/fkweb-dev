"""Regression tests for `sw_records.py retire` (removed or moved pages stop blocking the gate without
anyone's name being entered) and `prune-evidence` (old evidence files go once the gate passes).

Run from the dev root: python3 -m unittest discover tests/records
Every case works in a scratch project whose path contains spaces.
"""
import json
import os
import unittest
from pathlib import Path

from test_requirements import PAGE, RECORDS, Project, run


class Records(Project):
    def setUp(self):
        super().setUp()
        (self.site / "services").mkdir()
        self.page = self.site / "services" / "seo.html"
        self.page.write_text(PAGE.format(t="SEO", body="Search."))
        self.evidence = self.root / "docs" / "website" / "evidence"
        for n, target in enumerate(("site/index.html", "site/services/seo.html")):
            self.record("content.placeholders", target, f"run-{n}/notes.txt")
            self.record("a11y.landmarks", target, f"run-{n}/notes.txt")

    def record(self, check_id, target, evidence, result="passed", *extra, text=None):
        note = self.evidence / evidence
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(text or f"{check_id} {target}\n")
        code, out, err = run(RECORDS, "record", self.vpath, "--root", self.root, "--check-id", check_id,
                             "--target", target, "--result", result, "--method", "manual",
                             "--tool-and-version", "reviewer 1",
                             "--evidence-path", f"docs/website/evidence/{evidence}", "--require", *extra)
        self.assertEqual(code, 0, (out, err))

    def retire(self, *args):
        return run(RECORDS, "retire", self.vpath, "--root", self.root, "--reason", "moved to Notion", *args)

    def sitemap(self, routes):
        (self.vpath.parent / "website.md").write_text(f"# Site map\n\n- routes: {routes}\n")


class Retire(Records):
    def test_refused_while_the_target_exists(self):
        before = self.vpath.read_text()
        code, out, _ = self.retire("--target", "site/services/seo.html", "--write")
        self.assertEqual(code, 2)
        self.assertIn("still exists", out["retire"]["refused"][0]["why"])
        self.assertEqual(self.vpath.read_text(), before)

    def test_refused_for_a_url_and_while_the_site_map_lists_the_route(self):
        self.page.unlink()
        code, out, _ = self.retire("--target", "https://example.com/seo")
        self.assertEqual(code, 2)
        self.assertIn("URL", out["retire"]["refused"][0]["why"])
        self.sitemap("/, /services/seo")
        code, out, _ = self.retire("--all-missing", "--write")
        self.assertEqual(code, 2)
        self.assertIn("/services/seo", out["retire"]["refused"][0]["why"])
        self.assertNotIn("retired", self.vpath.read_text())

    def test_dry_run_then_write_moves_checks_to_not_assessed_and_the_gate_passes(self):
        self.page.unlink()
        self.sitemap("/")
        code, gate, _ = self.gate("mockup")
        self.assertEqual((code, gate["result"]), (1, "error"))
        before = self.vpath.read_text()
        code, out, _ = self.retire("--all-missing", "--replaced-by", "https://notion.so/seo")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["retire"]["plan"], [{"target": "site/services/seo.html",
                                                  "check_ids": ["a11y.landmarks", "content.placeholders"]}])
        self.assertFalse(out["retire"]["written"])
        self.assertEqual(self.vpath.read_text(), before)
        code, out, _ = self.retire("--all-missing", "--replaced-by", "https://notion.so/seo", "--write")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["gate"], {"mockup": "passed", "production": "passed"})
        code, gate, _ = self.gate("mockup")
        self.assertEqual((code, gate["result"]), (0, "passed"))
        retired = [c for c in gate["not_assessed"] if c["target"] == "site/services/seo.html"]
        self.assertEqual(len(retired), 2)
        self.assertIn("replaced by https://notion.so/seo", retired[0]["reason"])
        self.assertIn("never passed", retired[0]["reason"])
        self.assertFalse(any(c["target"] == "site/services/seo.html" for c in gate["checks"]))
        history = [h for h in self.data()["requirement_history"] if h["action"] == "retire"]
        self.assertEqual(len(history), 2)
        for h in history:
            self.assertEqual(h["decided_by"], "")
            self.assertFalse(h["weakens"])
            self.assertIn("no person's decision", h["basis"])
        code, out, _ = self.retire("--all-missing", "--write")      # already retired: nothing left to do
        self.assertEqual(code, 0)
        self.assertEqual(out["retire"]["plan"], [])

    def test_requirement_returns_when_the_target_does(self):
        self.page.unlink()
        self.retire("--all-missing", "--write")
        self.page.write_text(PAGE.format(t="SEO", body="Search again."))
        code, gate, _ = self.gate("mockup")
        self.assertEqual(code, 1)
        lines = [c for c in gate["checks"] if c["target"] == "site/services/seo.html"]
        self.assertEqual({c["result"] for c in lines}, {"stale"})
        self.assertIn("exists again", lines[0]["reactivated"])

    def test_require_remove_on_a_missing_target_still_needs_a_decider_and_names_retire(self):
        self.page.unlink()
        code, out, _ = self.require("--check-id", "a11y.landmarks", "--target", "site/services/seo.html",
                                    "--remove", "--reason", "gone")
        self.assertEqual(code, 2)
        self.assertTrue(any("--decided-by" in d for d in out["diagnostics"]))
        self.assertTrue(any("retire" in d for d in out["diagnostics"]))

    def test_wrong_root_is_refused_rather_than_read_as_removed(self):
        code, out, _ = run(RECORDS, "retire", self.vpath, "--root", self.site, "--reason", "x",
                           "--target", "site/services/seo.html")
        self.assertEqual(code, 2)
        self.assertIn("root", out["retire"]["refused"][0]["why"])


class PruneEvidence(Records):
    def prune(self, *args):
        return run(RECORDS, "prune-evidence", self.vpath, "--root", self.root, "--mode", "mockup", *args)

    def test_refused_while_the_gate_fails(self):
        self.page.unlink()
        stray = self.evidence / "old" / "shot.png"
        stray.parent.mkdir()
        stray.write_bytes(b"png")
        code, out, _ = self.prune("--write")
        self.assertEqual(code, 1)
        self.assertEqual(out["result"], "skipped")
        self.assertTrue(stray.exists())

    def test_dry_run_lists_and_write_deletes_only_uncited_files(self):
        old = self.evidence / "old" / "shot.png"
        old.parent.mkdir()
        old.write_bytes(b"png")
        loose = self.evidence / "run-0" / "extra.txt"       # beside a cited file, itself uncited
        loose.write_text("x")
        outside = self.root / "keep.txt"
        outside.write_text("outside")
        os.symlink(outside, self.evidence / "link.txt")
        archive = self.evidence / "archive.json"
        archive.write_text(json.dumps({"schema_version": 1, "archived_from": "x", "records": []}))
        code, out, _ = self.prune()
        self.assertEqual(code, 0, out)
        planned = set(out["prune"]["to_delete"])
        self.assertEqual(planned, {"docs/website/evidence/old", "docs/website/evidence/run-0/extra.txt",
                                   "docs/website/evidence/link.txt"})
        self.assertTrue(old.exists())
        code, out, _ = self.prune("--write")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["gate"], "passed")
        self.assertFalse(old.parent.exists() or loose.exists() or (self.evidence / "link.txt").is_symlink())
        self.assertEqual(outside.read_text(), "outside")      # the link went, never what it pointed to
        self.assertTrue(archive.exists())
        self.assertTrue((self.evidence / "run-0" / "notes.txt").exists())
        self.assertTrue((self.evidence / "run-1" / "notes.txt").exists())

    def test_superseded_records_keep_their_files_until_compacted(self):
        self.record("seo.title", "site/index.html", "solo/first.txt")
        self.record("seo.title", "site/index.html", "solo/second.txt", "passed", "--append-unchanged")
        code, out, _ = self.prune()
        self.assertEqual(code, 0)
        self.assertEqual(out["prune"]["to_delete"], [])     # the superseded record still cites solo/first.txt
        self.assertTrue(any("compact" in d for d in out["diagnostics"]))


class PruneCurrentOnly(Records):
    """0.3.0: --current-only archives superseded records and prunes their files without a passing gate."""

    def prune(self, *args):
        return run(RECORDS, "prune-evidence", self.vpath, "--root", self.root, "--mode", "mockup", "--current-only",
                   *args)

    def supersede_then_fail(self):
        """A file written before 0.2.2 rolled superseded records into the archive: old and new side by side."""
        old = []
        for target, first, second, result in (("site/index.html", "first.txt", "second.txt", "passed"),
                                              ("site/services/seo.html", "seo-ok.txt", "seo-bad.txt", "failed")):
            self.record("seo.title", target, f"solo/{first}")
            old.append(self.data()["records"][-1])
            self.record("seo.title", target, f"solo/{second}", result, "--append-unchanged", text=f"{second}\n")
        data = self.data()
        data["records"] = old + data["records"]
        self.vpath.write_text(json.dumps(data))
        self.vpath.with_name("verification-archive.jsonl").unlink(missing_ok=True)
        return self.evidence / "solo"

    def test_superseded_files_go_while_the_gate_fails(self):
        solo = self.supersede_then_fail()
        before = run(RECORDS, "gate", self.vpath, "--root", self.root, "--mode", "mockup")[1]
        self.assertEqual(before["result"], "failed")
        code, out, _ = run(RECORDS, "prune-evidence", self.vpath, "--root", self.root, "--mode", "mockup", "--write")
        self.assertEqual((code, out["result"]), (1, "skipped"))           # without the flag: refused
        code, out, _ = self.prune()                                         # dry run: nothing moves
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(out["prune"]["to_delete"]), ["docs/website/evidence/solo/first.txt",
                                                              "docs/website/evidence/solo/seo-ok.txt"])
        self.assertEqual(len(out["prune"]["archived"]), 2)
        self.assertTrue((solo / "first.txt").exists())
        self.assertEqual(len(self.data()["records"]), 8)
        code, out, _ = self.prune("--write")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(p.name for p in solo.iterdir()), ["second.txt", "seo-bad.txt"])
        self.assertEqual(len(self.data()["records"]), 6)
        self.assertTrue(self.vpath.with_name("verification-archive.jsonl").exists())
        after = run(RECORDS, "gate", self.vpath, "--root", self.root, "--mode", "mockup")[1]
        self.assertEqual([(c["check_id"], c["target"], c["result"]) for c in after["checks"]],
                         [(c["check_id"], c["target"], c["result"]) for c in before["checks"]])

    def test_refused_while_a_run_is_in_progress(self):
        solo = self.supersede_then_fail()
        code, out, _ = run(RECORDS, "begin", self.vpath, "--root", self.root, "--check-id", "seo.title",
                           "--target", "site/index.html")
        self.assertEqual(code, 0, out)
        code, out, _ = self.prune("--write")
        self.assertEqual((code, out["result"]), (1, "skipped"), out)
        self.assertTrue((solo / "first.txt").exists())


if __name__ == "__main__":
    unittest.main()
