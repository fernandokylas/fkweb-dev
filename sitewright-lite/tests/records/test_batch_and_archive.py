"""Regression tests for 0.2.2 recording: `record --batch` (one write, whole or nothing), file-set targets
(`dist/**/*.css`), `--inputs-from-page`, and the append-only archive of superseded records.

Run from the dev root: python3 -m unittest discover tests/records
Every case works in a scratch project whose path contains spaces.
"""
import json
import unittest

from test_requirements import PAGE, RECORDS, Project, run


class Base(Project):
    def setUp(self):
        super().setUp()
        self.evidence = self.root / "docs" / "website" / "evidence"
        self.evidence.mkdir(parents=True)
        self.archive = self.vpath.with_name("verification-archive.jsonl")

    def note(self, name, text=None):
        (self.evidence / name).write_text(text or name)
        return f"docs/website/evidence/{name}"

    def record(self, check_id, target, evidence, *extra):
        method = "browser" if check_id.startswith("browser.") else "manual"
        return run(RECORDS, "record", self.vpath, "--root", self.root, "--check-id", check_id, "--target", target,
                   "--result", "passed", "--method", method, "--tool-and-version", "reviewer 1",
                   "--evidence-path", evidence, "--require", *extra)

    def gate(self, mode="mockup"):
        return run(RECORDS, "gate", self.vpath, "--root", self.root, "--mode", mode)

    def archived(self):
        if not self.archive.exists():
            return []
        return [json.loads(line)["record"] for line in self.archive.read_text().splitlines()]


class BatchTest(Base):
    def batch(self, records, **defaults):
        path = self.root / "batch.json"
        path.write_text(json.dumps({"defaults": {"method": "browser", "tool_and_version": "chrome 1",
                                                 "require": True, **defaults}, "records": records}))
        return run(RECORDS, "record", self.vpath, "--root", self.root, "--batch", path)

    def test_a_batch_is_written_once_and_whole(self):
        ev = self.note("run.txt")
        code, out, err = self.batch([{"check_id": "browser.layout", "target": "site/index.html"},
                                     {"check_id": "browser.layout", "target": "site/404.html"}],
                                    result="passed", evidence_path=ev, input=["site/404.html"])
        self.assertEqual(code, 0, (out, err))
        self.assertEqual((out["recorded"], len(self.data()["records"])), (2, 2))
        self.assertEqual({r["target"] for r in self.data()["records"]}, {"site/index.html", "site/404.html"})

    def test_one_refused_entry_writes_nothing(self):
        ev = self.note("run.txt")
        code, out, _ = self.batch([{"check_id": "browser.layout", "target": "site/index.html"},
                                   {"check_id": "browser.layout", "target": "site/gone.html"}],
                                  result="passed", evidence_path=ev, input=["site/404.html"])
        self.assertNotEqual(code, 0)
        self.assertFalse(self.vpath.exists())
        self.assertTrue(any("whole or not at all" in d for d in out["diagnostics"]), out)

    def test_options_on_the_command_line_are_refused_beside_a_batch(self):
        path = self.root / "batch.json"
        path.write_text(json.dumps([]))
        code, out, _ = run(RECORDS, "record", self.vpath, "--root", self.root, "--batch", path,
                           "--check-id", "x.y")
        self.assertEqual(code, 2)


class FileSetTest(Base):
    def setUp(self):
        super().setUp()
        (self.site / "assets").mkdir()
        self.css = self.site / "assets" / "site.1a2b.css"
        self.css.write_text("body{color:#111}")

    def test_a_renamed_unchanged_file_stays_current_and_a_change_goes_stale(self):
        code, out, err = self.record("design.raw-literals", "site/**/*.css", self.note("css.txt"))
        self.assertEqual(code, 0, (out, err))
        self.css.rename(self.css.with_name("site.9f8e.css"))
        self.assertEqual(self.gate()[1]["result"], "passed")
        self.css.with_name("site.9f8e.css").write_text("body{color:#222}")
        code, gate, _ = self.gate()
        self.assertEqual(gate["result"], "stale", gate)

    def test_no_match_is_refused_at_record_time_and_an_error_at_the_gate(self):
        code, out, _ = self.record("design.raw-literals", "site/**/*.scss", self.note("css.txt"))
        self.assertNotEqual(code, 0)
        self.assertEqual(self.record("design.raw-literals", "site/**/*.css", self.note("css.txt"))[0], 0)
        self.css.unlink()
        self.assertEqual(self.gate()[1]["result"], "error")

    def test_a_file_set_input_follows_content_not_names(self):
        code, out, err = self.record("browser.layout", "site/index.html", self.note("shot.txt"),
                                     "--input", "site/**/*.css")
        self.assertEqual(code, 0, (out, err))
        self.css.rename(self.css.with_name("site.9f8e.css"))
        self.assertEqual(self.gate()[1]["result"], "passed")
        self.css.with_name("site.9f8e.css").write_text("body{color:#222}")
        self.assertEqual(self.gate()[1]["result"], "stale")


class InputsFromPageTest(Base):
    def setUp(self):
        super().setUp()
        (self.site / "assets").mkdir()
        (self.site / "assets" / "site.css").write_text("body{margin:0}")
        (self.site / "assets" / "app.js").write_text("console.log(1)")
        (self.site / "about.html").write_text(PAGE.format(t="About", body="Us.").replace(
            "</head>", '<link rel="stylesheet" href="/assets/site.css"><script type="module" src="assets/app.js">'
                       '</script><link rel="stylesheet" href="https://fonts.example/x.css"></head>'))
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Welcome.").replace(
            "</head>", '<link rel="stylesheet" href="/assets/site.css"></head>'))

    def test_linked_local_files_become_inputs_and_only_their_pages_go_stale(self):
        code, out, err = self.record("browser.layout", "site/about.html", self.note("about.txt"),
                                     "--inputs-from-page", "--site", "site")
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(set(out["record"]["inputs"]), {"site/assets/site.css", "site/assets/app.js"})
        self.assertEqual(self.record("browser.layout", "site/index.html", self.note("home.txt"),
                                     "--inputs-from-page", "--site", "site")[0], 0)
        (self.site / "assets" / "app.js").write_text("console.log(2)")
        code, gate, _ = self.gate()
        stale = {c["target"] for c in gate["checks"] if c["result"] == "stale"}
        self.assertEqual(stale, {"site/about.html"}, gate)

    def test_refused_for_a_target_that_is_not_a_page(self):
        code, out, _ = self.record("browser.layout", "site/assets/site.css", self.note("x.txt"),
                                   "--inputs-from-page")
        self.assertNotEqual(code, 0)


class RollingArchiveTest(Base):
    """Identical reruns are appended here on purpose (--append-unchanged) to exercise the archive."""

    def record(self, *args):
        return super().record(*args, "--append-unchanged")

    def test_superseded_records_move_to_the_archive_and_the_gate_is_unchanged(self):
        for n in range(3):
            self.assertEqual(self.record("a11y.landmarks", "site/index.html", self.note(f"r{n}.txt"))[0], 0)
        self.assertEqual(len(self.data()["records"]), 1)
        self.assertEqual([r["evidence_path"] for r in self.archived()],
                         ["docs/website/evidence/r0.txt", "docs/website/evidence/r1.txt"])
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_evidence_of_an_archived_record_cannot_pass_a_changed_target(self):
        first = self.note("first.txt")
        self.assertEqual(self.record("a11y.landmarks", "site/index.html", first)[0], 0)
        self.assertEqual(self.record("a11y.landmarks", "site/index.html", self.note("second.txt"))[0], 0)
        self.assertEqual(len(self.archived()), 1)
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Changed."))
        code, out, _ = self.record("a11y.landmarks", "site/index.html", first)
        self.assertNotEqual(code, 0)
        self.assertTrue(any("evidence reused" in d and "archived" in d for d in out["diagnostics"]), out)

    def test_a_record_sharing_evidence_with_the_current_one_is_kept_active(self):
        """The reuse guard reads both records, so the earlier one may not leave the active file."""
        shared = self.note("shared.txt")
        self.assertEqual(self.record("a11y.landmarks", "site/index.html", shared)[0], 0)
        self.assertEqual(self.record("a11y.landmarks", "site/index.html", shared)[0], 0)
        self.assertEqual((len(self.data()["records"]), self.archived()), (2, []))


class DecisionCitationTest(Base):
    """0.2.2: a weakening may cite an active accepted decision with a recorded source instead of a name."""

    def state(self, **decision):
        (self.vpath.parent / "state.json").write_text(json.dumps({"accepted_decisions": [
            {"id": "D-4", "decision": "drop the order page", "status": "active", **decision}]}))

    def remove(self, *extra):
        return run(RECORDS, "require", self.vpath, "--root", self.root, "--check-id", "a11y.landmarks",
                   "--target", "site/index.html", "--remove", "--reason", "page content moved", *extra)

    def setUp(self):
        super().setUp()
        self.assertEqual(self.record("a11y.landmarks", "site/index.html", self.note("r.txt"))[0], 0)

    def test_an_active_sourced_decision_authorises_the_weakening_and_status_lists_it(self):
        self.state(source="owner, message of 2026-10-25")
        code, out, err = self.remove("--decision", "D-4")
        self.assertEqual(code, 0, (out, err))
        entry = self.data()["requirement_history"][-1]
        self.assertEqual((entry["decision"], entry["decided_by"], entry["weakens"]), ("D-4", "", True))
        self.assertEqual(entry["decision_source"], "owner, message of 2026-10-25")
        weakenings = run(RECORDS, "status", self.vpath, "--root", self.root)[1]["weakenings"]
        self.assertEqual([(w["basis"], [c["check_id"] for c in w["changes"]]) for w in weakenings],
                         [("decision D-4", ["a11y.landmarks"])])

    def test_a_decision_without_a_source_or_no_longer_active_is_refused(self):
        for decision in ({}, {"source": "  "}, {"source": "owner", "status": "superseded", "superseded_by": "D-9"}):
            self.state(**decision)
            code, out, _ = self.remove("--decision", "D-4")
            self.assertNotEqual(code, 0, decision)
            self.assertTrue(any("no active decision" in d for d in out["diagnostics"]), out)
        self.assertEqual(len(self.data()["required_checks"]), 1)

    def test_without_a_decider_the_message_names_both_ways(self):
        code, out, _ = self.remove()
        self.assertNotEqual(code, 0)
        self.assertTrue(any("--decided-by" in d and "--decision" in d for d in out["diagnostics"]), out)


class StateFieldTest(Base):
    """0.2.2 state fields: next_owner, open-issue links to decisions, removed_routes."""

    def findings(self, **state):
        path = self.vpath.parent / "state.json"
        path.write_text(json.dumps({"project": "x", "current_phase": "implement", "next_action": "build",
                                    "accepted_decisions": [], "open_issues": [], **state}))
        return [(f["severity"], f["evidence"]) for f in run(RECORDS, "check-state", path)[1]["findings"]
                if f["check_id"].startswith("records.state")]

    def test_next_owner_must_name_a_skill_of_this_plugin(self):
        self.assertEqual([f for f in self.findings(next_owner="website-motion") if "next_owner" in f[1]], [])
        self.assertIn("defect", {s for s, e in self.findings(next_owner="Website Motion!") if "next_owner" in e})
        warned = [e for s, e in self.findings(next_owner="website-nonesuch") if "next_owner" in e]
        self.assertTrue(warned and "not a skill of this plugin" in warned[0], warned)

    def test_an_issue_linked_to_a_superseded_decision_is_reported(self):
        decisions = [{"id": "D-3", "status": "superseded", "superseded_by": "D-9"}, {"id": "D-9", "status": "active"}]
        found = self.findings(accepted_decisions=decisions, open_issues=[{"id": "OPEN-1", "decision": "D-3"},
                                                                         {"id": "OPEN-2", "decision": "D-9"}])
        joined = " | ".join(e for _, e in found)
        self.assertIn("OPEN-1 depends on D-3, superseded by D-9", joined)
        self.assertNotIn("OPEN-2", joined)

    def test_a_removed_route_needs_a_decision_or_a_source(self):
        bad = self.findings(removed_routes=[{"route": "/order/", "reason": "dropped"}])
        self.assertTrue(any("names no accepted decision or `source`" in e for _, e in bad), bad)
        good = self.findings(removed_routes=[{"route": "/order/", "reason": "dropped",
                                              "source": "owner, message of 2026-10-27"}])
        self.assertFalse(any("removed_routes" in e for _, e in good), good)


if __name__ == "__main__":
    unittest.main()
