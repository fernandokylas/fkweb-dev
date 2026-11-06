"""Contract tests for scripts/sw_records.py and the shared project records (item 03).

Run from the dev root: python3 -m unittest discover tests/records
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "sw_records.py"
FIXTURE = ROOT / "tests" / "fixtures" / "records" / "shared-project"
sys.path.insert(0, str(ROOT / "scripts"))
import sw_records  # noqa: E402


def run(*args):
    proc = subprocess.run([sys.executable, str(HELPER), *map(str, args)], capture_output=True, text=True, timeout=60)
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        out = None
    return proc.returncode, out, proc.stderr


def defects(out):
    return [f for f in out["findings"] if f["severity"] == "defect"]


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw records "))  # space in path on purpose
        self.proj = self.tmp / "proj"
        shutil.copytree(FIXTURE, self.proj)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def state(self, **changes):
        path = self.proj / "state.json"
        data = json.loads(path.read_text())
        data.update(changes)
        path.write_text(json.dumps(data))

    def edit(self, old, new):
        path = self.proj / "website.md"
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_fixture_records_pass(self):
        code, out, _ = run("check-records", self.proj)
        self.assertEqual((code, out["result"]), (0, "passed"), out["findings"])

    def test_same_records_serve_both_routes(self):
        for path, builder in (("custom-code", "static-html"), ("custom-code", "react-vite"),
                              ("wordpress", "block-theme"), ("wordpress", "elementor")):
            self.state(build_path=path, selected_framework_or_builder=builder)
            code, out, _ = run("check-records", self.proj)
            self.assertEqual(code, 0, (path, builder, out["findings"]))

    def test_route_mappings_cover_every_page_field(self):
        for rel in ("skills/website-build-code/references/page-contract-mapping.md",
                    "skills/website-build-wordpress/references/page-contract-mapping.md"):
            rows = re.findall(r"^\| `([a-z_]+)` \|", (ROOT / rel).read_text(), re.MULTILINE)
            self.assertEqual(sorted(rows), sorted(sw_records.PAGE_FIELDS), rel)

    def test_contract_doc_lists_every_field(self):
        doc = (ROOT / "skills/website-workflow/references/project-records.md").read_text()
        for name in (sw_records.BRIEF_FIELDS + sw_records.PAGE_FIELDS + sw_records.DESIGN_FIELDS
                     + sw_records.STATE_FIELDS + sw_records.ASSET_FIELDS + sw_records.OPTIONAL_STATE_FIELDS
                     + sw_records.OPTIONAL_DESIGN_FIELDS):
            self.assertIn(f"`{name}`", doc, name)
        evidence = (ROOT / "skills/website-verify/references/evidence-contract.md").read_text()
        for name in sw_records.EVIDENCE_FIELDS + sw_records.OPTIONAL_EVIDENCE_FIELDS + sw_records.RESULTS:
            self.assertIn(f"`{name}`", evidence, name)
        for name in sw_records.OPTIONAL_VERIFICATION_KEYS + sw_records.REQUIREMENT_ACTIONS:
            self.assertIn(name, evidence, name)
        for name in ("from_modes", "to_modes", "decided_by", "weakens", "criteria_note"):
            self.assertIn(f"`{name}`", evidence, name)

    def test_missing_field_fails(self):
        self.edit("- primary_action: tap-to-call link\n", "")
        code, out, _ = run("check-records", self.proj)
        self.assertEqual((code, out["result"]), (1, "failed"))
        self.assertTrue(any("primary_action" in f["evidence"] for f in out["findings"]))

    def test_placeholder_fails(self):
        self.edit("- page_job: give address", "- page_job: TBD give address")
        code, out, _ = run("check-records", self.proj)
        self.assertEqual(code, 1)

    def test_note_form_markers_fail(self):
        original = (self.proj / "website.md").read_text()
        for marker in ("TBC", "(verify with owner)", "[confirm]", "[NEED: hours]", "à vérifier"):
            with self.subTest(marker):
                (self.proj / "website.md").write_text(original)
                self.edit("- page_job: give address", f"- page_job: give address {marker}")
                code, out, _ = run("check-records", self.proj)
                self.assertEqual(code, 1, out["findings"])
                self.assertTrue(any("placeholder" in f["evidence"] for f in out["findings"]))

    def unmapped(self, out):
        return {(f["severity"], f["evidence"].split(" names check ")[1].split(",")[0])
                for f in out["findings"] if " names check " in f["evidence"]}

    def test_unmapped_acceptance_checks_warn_before_verify(self):
        code, out, _ = run("check-records", self.proj, "--phase", "implement")
        self.assertEqual(code, 0, out["findings"])
        self.assertIn(("warning", "form.states"), self.unmapped(out))

    def test_unmapped_acceptance_checks_are_defects_from_verify(self):
        for phase in ("verify", "handoff"):
            code, out, _ = run("check-records", self.proj, "--phase", phase)
            self.assertEqual(code, 1, phase)
            self.assertIn(("defect", "form.states"), self.unmapped(out))
        ids = ["nav.internal-links", "a11y.landmarks", "meta.basics", "form.labels", "form.states"]
        (self.proj / "verification.json").write_text(json.dumps(
            {"required_checks": [{"check_id": c, "target": "site"} for c in ids], "records": []}))
        code, out, _ = run("check-records", self.proj, "--phase", "verify")
        self.assertEqual(self.unmapped(out), set())

    def test_free_text_acceptance_items_are_not_check_ids(self):
        self.edit("- acceptance_checks: nav.internal-links, a11y.landmarks\n",
                  "- acceptance_checks: tap-to-call works on mobile, see index.html, e.g. a map\n")
        self.assertEqual(sw_records.acceptance_ids("tap-to-call works, index.html, e.g. x, `form.error-state` (?state=error)"),
                         ["form.error-state"])
        code, out, _ = run("check-records", self.proj, "--phase", "implement")
        self.assertFalse({c for _, c in self.unmapped(out)} & {"tap-to-call", "index.html", "e.g"})

    def test_route_without_contract_fails(self):
        self.edit("- routes: /, /menu, /order, /contact", "- routes: /, /menu, /order, /contact, /about")
        code, out, _ = run("check-records", self.proj)
        self.assertEqual(code, 1)
        self.assertTrue(any("/about" in f["evidence"] for f in out["findings"]))

    def test_missing_design_record_fails_at_implement_but_not_at_structure(self):
        text = (self.proj / "website.md").read_text()
        (self.proj / "website.md").write_text(text.split("# Design")[0])
        code, _, _ = run("check-records", self.proj, "--phase", "implement")
        self.assertEqual(code, 1)
        code, out, _ = run("check-records", self.proj, "--phase", "direction")
        self.assertEqual(code, 0, out["findings"])

    def test_plan_only_cannot_be_implementing(self):
        self.state(requested_scope="plan-only", current_phase="implement")
        code, out, _ = run("check-state", self.proj / "state.json")
        self.assertEqual(code, 1)

    def test_bad_state_enum_fails_and_unreadable_state_errors(self):
        self.state(build_path="squarespace")
        self.assertEqual(run("check-state", self.proj / "state.json")[0], 1)
        (self.proj / "state.json").write_text("{not json")
        code, out, _ = run("check-state", self.proj / "state.json")
        self.assertEqual((code, out["result"]), (2, "error"))

    def test_optional_session_summary_must_be_boolean(self):
        self.state(session_summary=True)
        self.assertEqual(run("check-state", self.proj / "state.json")[0], 0)
        self.state(session_summary="yes")
        code, out, _ = run("check-state", self.proj / "state.json")
        self.assertEqual(code, 1)
        self.assertIn("session_summary", out["findings"][0]["evidence"])

    def test_resume_confirms_recorded_artifacts(self):
        fp = sw_records.fingerprint(self.proj / "website.md")
        self.state(completed_artifacts=[{"path": "website.md", "phase": "direction", "fingerprint": fp}])
        code, out, _ = run("check-state", self.proj / "state.json")
        self.assertEqual(code, 0, out["findings"])
        self.edit("warm, plain and legible", "cool and dense")
        code, out, _ = run("check-state", self.proj / "state.json")
        self.assertEqual(code, 1)
        self.assertIn("changed since", defects(out)[0]["evidence"])
        (self.proj / "website.md").unlink()
        code, out, _ = run("check-state", self.proj / "state.json")
        self.assertEqual(code, 1)
        self.assertIn("missing", defects(out)[0]["evidence"])

    def test_completed_artifact_without_fingerprint_fails(self):
        # Item 08 (card A03): completion with no evidence is refused, not a warning.
        self.state(completed_artifacts=[{"path": "website.md", "phase": "direction"}])
        code, out, _ = run("check-state", self.proj / "state.json")
        self.assertEqual((code, out["result"]), (1, "failed"))
        self.assertIn("no fingerprint", defects(out)[0]["evidence"])

    def test_resume_artifacts_resolve_against_root_and_stay_inside_it(self):
        site = self.proj / "site"
        site.mkdir()
        (site / "index.html").write_text("<h1>x</h1>\n")
        records = self.proj / "docs" / "website"
        records.mkdir(parents=True)
        shutil.move(self.proj / "state.json", records / "state.json")
        fp = sw_records.fingerprint(site / "index.html")
        data = json.loads((records / "state.json").read_text())
        data["completed_artifacts"] = [{"path": "site/index.html", "phase": "implement", "fingerprint": fp}]
        (records / "state.json").write_text(json.dumps(data))
        self.assertEqual(run("check-state", records / "state.json", "--root", self.proj)[0], 0)
        # without --root, a state file in docs/website/ resolves against the folder above it (rc.5)
        self.assertEqual(run("check-state", records / "state.json")[0], 0)
        data["completed_artifacts"] = [{"path": "../../../outside", "phase": "implement", "fingerprint": fp}]
        (records / "state.json").write_text(json.dumps(data))
        code, out, _ = run("check-state", records / "state.json", "--root", self.proj)
        self.assertIn("outside the project root", defects(out)[0]["evidence"])

    def test_missing_directory_errors(self):
        code, out, _ = run("check-records", self.tmp / "nope")
        self.assertEqual((code, out["result"]), (2, "error"))


class GateBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw gate "))
        (self.tmp / "site").mkdir()
        self.page = self.tmp / "site" / "index.html"
        self.page.write_text("<h1>Hi</h1>")
        (self.tmp / "evidence").mkdir()
        (self.tmp / "evidence" / "a11y.json").write_text("{}")
        self.vfile = self.tmp / "verification.json"
        self.vfile.write_text(json.dumps({"schema_version": 1, "records": [], "waivers": [],
                                          "required_checks": [{"check_id": "a11y.landmarks", "target": "site/index.html"}]}))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def record(self, result="passed", **kw):
        args = ["record", self.vfile, "--check-id", kw.get("check_id", "a11y.landmarks"),
                "--target", kw.get("target", "site/index.html"), "--result", result,
                "--method", kw.get("method", "automated"), "--tool-and-version", "test 1",
                "--evidence-path", kw.get("evidence", "evidence/a11y.json"), "--finding", "ok"]
        for given in kw.get("inputs", ()):
            args += ["--input", given]
        if "fingerprint" in kw:
            args += ["--fingerprint", kw["fingerprint"]]
        if result == "skipped":
            args += ["--skip-reason", kw.get("skip_reason", "unsupported")]
        return run(*args)

    def gate(self):
        return run("gate", self.vfile)


class GateTest(GateBase):
    def test_missing_evidence_is_unavailable_not_passed(self):
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "unavailable"))

    def test_fresh_pass_passes(self):
        self.assertEqual(self.record()[0], 0)
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (0, "passed"))

    def test_interrupted_write_keeps_the_previous_file(self):
        """V30: a write that fails part-way leaves the last good file and no temporary file."""
        self.assertEqual(self.record()[0], 0)
        before = self.vfile.read_bytes()
        with self.assertRaises(TypeError):
            sw_records.write_json_atomic(self.vfile, {"records": [object()]})   # fails mid-serialisation
        self.assertEqual(self.vfile.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["evidence", "site", "verification.json"])
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_moved_project_keeps_its_evidence(self):
        """V30: targets are project-relative and fingerprinted by content, so a moved project still
        passes, and an edit made after the move is still caught."""
        self.assertEqual(self.record()[0], 0)
        moved = Path(tempfile.mkdtemp(prefix="sw moved ")) / "new home"
        shutil.move(str(self.tmp), str(moved))
        self.tmp = moved
        self.vfile, self.page = moved / "verification.json", moved / "site" / "index.html"
        self.assertEqual(self.gate()[1]["result"], "passed")
        self.page.write_text("<h1>Changed</h1>")
        self.assertEqual(self.gate()[1]["result"], "stale")

    def test_changed_target_is_stale(self):
        self.record()
        self.page.write_text("<h1>Changed</h1>")
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "stale"))

    def test_deleted_target_is_error(self):
        self.record()
        self.page.unlink()
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "error"))

    def test_failed_outranks_others_and_newest_record_wins(self):
        self.record()
        self.record("failed")
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "failed"))
        self.record()
        self.assertEqual(self.gate()[0], 0)

    def test_required_skip_does_not_pass(self):
        self.record("skipped")
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "skipped"))

    def test_incomplete_passed_record_is_error(self):
        data = json.loads(self.vfile.read_text())
        data["records"].append({"check_id": "a11y.landmarks", "target": "site/index.html", "result": "passed"})
        self.vfile.write_text(json.dumps(data))
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "error"))

    def test_unknown_result_word_is_error(self):
        data = json.loads(self.vfile.read_text())
        data["records"].append({"check_id": "a11y.landmarks", "target": "site/index.html", "result": "ok"})
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.gate()[1]["result"], "error")

    def test_waiver_needs_reason_and_decider(self):
        data = json.loads(self.vfile.read_text())
        data["waivers"] = [{"check_id": "a11y.landmarks", "target": "site/index.html", "reason": "dropped"}]
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.gate()[1]["result"], "unavailable")
        data["waivers"][0]["decided_by"] = "user"
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.gate()[0], 0)

    def test_target_outside_root_is_error(self):
        data = json.loads(self.vfile.read_text())
        data["required_checks"] = [{"check_id": "x.y", "target": "../outside.html"}]
        data["records"] = [{"check_id": "x.y", "target": "../outside.html", "result": "passed",
                            "method": "automated", "tool_and_version": "t", "timestamp": "2026-10-06T00:00:00Z",
                            "evidence_path": "e", "source_revision_or_target_fingerprint": "sha256:00"}]
        self.vfile.write_text(json.dumps(data))
        code, out, _ = self.gate()
        self.assertEqual(out["result"], "error")

    def test_malformed_verification_file_exits_2(self):
        self.vfile.write_text("[1, 2")
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (2, "error"))
        self.vfile.write_text(json.dumps({"records": []}))
        self.assertEqual(self.gate()[0], 2)

    def test_no_required_checks_is_not_a_pass(self):
        self.vfile.write_text(json.dumps({"required_checks": [], "records": []}))
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "unavailable"))

    def test_record_rejects_missing_target(self):
        code, out, _ = self.record(target="site/missing.html")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(self.vfile.read_text())["records"], [])

    def test_browser_check_needs_browser_method(self):
        for method in ("manual", "automated"):
            code, out, _ = self.record(check_id="browser.keyboard", method=method)
            self.assertEqual((code, out["result"]), (2, "error"), method)
        self.assertEqual(json.loads(self.vfile.read_text())["records"], [])
        code, out, _ = self.record(check_id="browser.keyboard", method="browser", target="site")
        self.assertEqual(code, 0, out)

    def test_visual_measurement_and_judgement_take_their_own_methods(self):
        for method in ("manual", "automated"):
            code, out, _ = self.record(check_id="visual.measure", method=method, target="site")
            self.assertEqual((code, out["result"]), (2, "error"), method)
        for method in ("browser", "automated"):
            code, out, _ = self.record(check_id="visual.review", method=method, target="site")
            self.assertEqual((code, out["result"]), (2, "error"), method)
        self.assertEqual(json.loads(self.vfile.read_text())["records"], [])
        self.assertEqual(self.record(check_id="visual.measure", method="browser", target="site")[0], 0)
        self.assertEqual(self.record(check_id="visual.review", method="manual", target="site")[0], 0)

    def test_directory_fingerprint_tracks_contents(self):
        before = sw_records.fingerprint(self.tmp / "site")
        (self.tmp / "site" / "about.html").write_text("x")
        self.assertNotEqual(before, sw_records.fingerprint(self.tmp / "site"))


class EvidenceSupportTest(GateBase):
    """Finding 3 and 7: a pass needs a well-formed identity, a readable supporting file inside the project,
    and current fingerprints for every input it consumed."""

    def edit_record(self, **fields):
        data = json.loads(self.vfile.read_text())
        data["records"][-1].update(fields)
        self.vfile.write_text(json.dumps(data))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs FIFOs")
    def test_fifo_evidence_is_unavailable_without_opening_it(self):
        self.assertEqual(self.record()[0], 0)
        evidence = self.tmp / "evidence" / "a11y.json"
        evidence.unlink()
        os.mkfifo(evidence)
        with patch.object(sw_records.os, "open", side_effect=AssertionError("must not open a FIFO")):
            result = sw_records.evidence_file(self.tmp, "evidence/a11y.json")
        self.assertEqual(result[0], "unavailable")
        proc = subprocess.run([sys.executable, str(HELPER), "gate", str(self.vfile)],
                              capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["result"], "unavailable")

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "needs nonblocking FIFOs")
    def test_evidence_replaced_by_fifo_after_stat_does_not_block(self):
        self.assertEqual(self.record()[0], 0)
        evidence = self.tmp / "evidence" / "a11y.json"
        original_open = os.open

        def replace_then_open(path, flags):
            evidence.unlink()
            os.mkfifo(evidence)
            self.assertTrue(flags & os.O_NONBLOCK)
            return original_open(path, flags)

        with patch.object(sw_records.os, "open", side_effect=replace_then_open):
            result = sw_records.evidence_file(self.tmp, "evidence/a11y.json")
        self.assertEqual(result[0], "unavailable")
        self.assertIn("not a regular file", result[1])

    def result(self):
        code, out, _ = self.gate()
        return out["result"], out["checks"][0]["reason"] if out.get("checks") else ""

    def test_missing_evidence_file_does_not_pass(self):
        code, out, _ = self.record(evidence="evidence/never-written.json")
        self.assertEqual(code, 2, out)
        self.assertEqual(json.loads(self.vfile.read_text())["records"], [])
        self.assertEqual(self.record()[0], 0)
        (self.tmp / "evidence" / "a11y.json").unlink()
        result, reason = self.result()
        self.assertEqual(result, "unavailable")
        self.assertIn("missing or unreadable", reason)

    def test_evidence_directory_or_url_is_not_support(self):
        self.assertEqual(self.record()[0], 0)
        self.edit_record(evidence_path="evidence")
        self.assertEqual(self.result()[0], "unavailable")
        self.edit_record(evidence_path="https://ci.example.org/run/1")
        self.assertEqual(self.result()[0], "unavailable")

    def test_evidence_outside_the_project_is_error(self):
        outside = Path(tempfile.mkdtemp(prefix="sw outside "))
        self.addCleanup(shutil.rmtree, outside)
        (outside / "e.json").write_text("{}")
        self.assertEqual(self.record()[0], 0)
        self.edit_record(evidence_path="../" + outside.name + "/e.json")
        self.assertEqual(self.result()[0], "error")
        (self.tmp / "evidence" / "link.json").symlink_to(outside / "e.json")
        self.edit_record(evidence_path="evidence/link.json")
        self.assertEqual(self.result()[0], "error")
        self.edit_record(evidence_path=str(outside / "e.json"))
        self.assertEqual(self.result()[0], "error")

    def test_malformed_identity_is_error(self):
        self.assertEqual(self.record()[0], 0)
        for value in ("sha256:00", "sha256:" + "A" * 64, "md5:abc", "abc", "rev:", "rev:xyz", "rev:--help"):
            self.edit_record(source_revision_or_target_fingerprint=value)
            self.assertEqual(self.result()[0], "error", value)
        code, out, _ = self.record(fingerprint="sha256:00")
        self.assertEqual(code, 2)

    def test_wrong_field_types_are_error_not_a_crash(self):
        self.assertEqual(self.record()[0], 0)
        for field, value in (("source_revision_or_target_fingerprint", 12), ("evidence_path", ["a"]),
                             ("result", ["passed"]), ("timestamp", None), ("inputs", ["site"]),
                             ("inputs", {"/etc/passwd": "sha256:" + "0" * 64}),
                             ("inputs", {"../x": "sha256:" + "0" * 64}), ("inputs", {"site": "sha256:1"})):
            self.edit_record(**{field: value})
            code, out, _ = self.gate()
            self.assertEqual((code, out["result"]), (1, "error"), (field, value))
            self.assertEqual(self.record()[0], 0)

    def test_malformed_timestamp_is_error(self):
        self.assertEqual(self.record()[0], 0)
        self.edit_record(timestamp="yesterday")
        self.assertEqual(self.result()[0], "error")

    def test_explicit_fingerprint_must_match_the_current_target(self):
        code, out, _ = self.record(fingerprint="sha256:" + "0" * 64)
        self.assertEqual(code, 2)
        self.assertIn("does not match", " ".join(out["diagnostics"]))
        self.assertEqual(self.record(fingerprint=sw_records.fingerprint(self.page))[0], 0)

    def test_changed_input_is_stale(self):
        css = self.tmp / "site" / "style.css"
        css.write_text("a{}")
        self.assertEqual(self.record(inputs=["site/style.css"])[0], 0)
        rec = json.loads(self.vfile.read_text())["records"][-1]
        self.assertEqual(rec["inputs"], {"site/style.css": sw_records.fingerprint(css)})
        self.assertEqual(self.result()[0], "passed")
        css.write_text("a{color:red}")
        result, reason = self.result()
        self.assertEqual(result, "stale")
        self.assertIn("site/style.css", reason)
        css.unlink()
        self.assertEqual(self.result()[0], "stale")

    def test_input_outside_the_project_is_refused(self):
        code, out, _ = self.record(inputs=["../elsewhere.css"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(self.vfile.read_text())["records"], [])

    def test_identity_may_not_cover_its_own_evidence(self):
        """Circular invalidation: a fingerprint over the evidence or verification file is refused."""
        code, out, _ = self.record(target=".")
        self.assertEqual(code, 2, out)
        code, out, _ = self.record(inputs=["evidence"])
        self.assertEqual(code, 2, out)
        self.assertEqual(self.record()[0], 0)
        self.edit_record(inputs={"evidence": sw_records.fingerprint(self.tmp / "evidence")})
        self.assertEqual(self.result()[0], "error")

    def test_browser_evidence_needs_its_dependencies(self):
        data = json.loads(self.vfile.read_text())
        data["required_checks"] = [{"check_id": "browser.keyboard", "target": "site/index.html"}]
        self.vfile.write_text(json.dumps(data))
        code, out, _ = self.record(check_id="browser.keyboard", method="browser")
        self.assertEqual(code, 2, out)   # one HTML file is not what the browser rendered
        (self.tmp / "site" / "app.js").write_text("1")
        self.assertEqual(self.record(check_id="browser.keyboard", method="browser",
                                     inputs=["site/app.js"])[0], 0)
        self.assertEqual(self.result()[0], "passed")
        (self.tmp / "site" / "app.js").write_text("2")
        self.assertEqual(self.result()[0], "stale")
        self.edit_record(inputs=None)
        data = json.loads(self.vfile.read_text())
        del data["records"][-1]["inputs"]
        self.vfile.write_text(json.dumps(data))
        result, reason = self.result()
        self.assertEqual(result, "stale")   # recorded before the dependency contract
        self.assertIn("--input", reason)

    def test_legacy_runtime_record_cannot_be_refreshed_by_its_probe(self):
        probe = self.tmp / "evidence" / "probe.json"
        probe.write_text("{}")
        data = json.loads(self.vfile.read_text())
        data["required_checks"] = [{"check_id": "wp.runtime-theme", "target": "evidence/probe.json"}]
        data["records"] = [{"check_id": "wp.runtime-theme", "target": "evidence/probe.json", "result": "passed",
                            "method": "automated", "tool_and_version": "t", "timestamp": "2026-10-06T00:00:00Z",
                            "evidence_path": "evidence/a11y.json",
                            "source_revision_or_target_fingerprint": sw_records.fingerprint(probe)}]
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.result()[0], "stale")

    def test_url_target_needs_a_local_snapshot(self):
        data = json.loads(self.vfile.read_text())
        data["required_checks"] = [{"check_id": "browser.console", "target": "http://127.0.0.1:8000/"}]
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.record(check_id="browser.console", method="browser", target="http://127.0.0.1:8000/",
                                     fingerprint="sha256:" + "1" * 64)[0], 2)
        self.assertEqual(self.record(check_id="browser.console", method="browser", target="http://127.0.0.1:8000/",
                                     fingerprint="sha256:" + "1" * 64, inputs=["site"])[0], 0)
        self.assertEqual(self.result()[0], "passed")
        self.page.write_text("<h1>Changed</h1>")
        self.assertEqual(self.result()[0], "stale")


@unittest.skipUnless(shutil.which("git"), "git not installed")
class RevisionIdentityTest(GateBase):
    """rev:<id> passes only when git shows the target unchanged since that commit."""

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.tmp), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                              capture_output=True, text=True, timeout=30)

    def commit(self):
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x")
        return self.git("rev-parse", "HEAD").stdout.strip()

    def test_rev_outside_git_is_unavailable(self):
        self.assertEqual(self.record(fingerprint="rev:" + "a" * 40)[0], 2)
        self.record()
        data = json.loads(self.vfile.read_text())
        data["records"][-1]["source_revision_or_target_fingerprint"] = "rev:" + "a" * 40
        self.vfile.write_text(json.dumps(data))
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (1, "unavailable"))

    def test_rev_is_verified_against_the_working_tree(self):
        rev = self.commit()
        self.assertEqual(self.record(fingerprint="rev:" + rev)[0], 0)
        self.assertEqual(self.gate()[1]["result"], "passed")
        self.page.write_text("<h1>Edited</h1>")
        self.assertEqual(self.gate()[1]["result"], "stale")
        self.git("checkout", "-q", "--", "site/index.html")
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_untracked_ignored_or_unknown_content_does_not_pass(self):
        rev = self.commit()
        data = json.loads(self.vfile.read_text())
        data["required_checks"] = [{"check_id": "site.404", "target": "site"}]
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.record(check_id="site.404", target="site", fingerprint="rev:" + rev)[0], 0)
        self.assertEqual(self.gate()[1]["result"], "passed")
        (self.tmp / "site" / "new.html").write_text("x")
        self.assertEqual(self.gate()[1]["result"], "stale")
        (self.tmp / ".gitignore").write_text("site/new.html\n")
        self.assertEqual(self.gate()[1]["result"], "stale")  # ignored or not, rev:<id> doesn't contain it
        (self.tmp / "site" / "new.html").unlink()
        self.assertEqual(self.gate()[1]["result"], "passed")
        data = json.loads(self.vfile.read_text())
        data["records"][-1]["source_revision_or_target_fingerprint"] = "rev:" + "0" * 40
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.gate()[1]["result"], "unavailable")

    def test_repository_config_never_runs_a_program(self):
        """The Stop hook gates records in whatever project is open, so the project's own git config
        (fsmonitor, clean filters, textconv, external diff) must not get a program run."""
        rev = self.commit()
        self.assertEqual(self.record(fingerprint="rev:" + rev)[0], 0)
        marker = self.tmp / "ran"
        cmd = f"touch '{marker}'; false"
        for key, value in (("core.fsmonitor", cmd), ("filter.evil.clean", cmd), ("filter.evil.process", cmd),
                           ("diff.evil.textconv", cmd), ("diff.external", cmd)):
            self.git("config", key, value)
        (self.tmp / ".gitattributes").write_text("* filter=evil diff=evil\n")
        self.page.write_text("<h1>Edited</h1>")
        self.assertEqual(self.gate()[1]["result"], "stale")
        self.git("-c", "core.fsmonitor=false", "-c", "filter.evil.clean=cat", "-c", "filter.evil.process=",
                 "checkout", "-q", rev, "--", "site/index.html")
        marker.unlink(missing_ok=True)
        self.assertEqual(self.gate()[1]["result"], "passed")
        self.assertFalse(marker.exists(), "a program named by repository config ran")

    def test_promisor_remote_cannot_run_a_transport(self):
        """A partial clone fetches missing objects from its promisor remote; the repository's own
        protocol.ext.allow overrides protocol.allow. Simulate a git older than 2.44, which ignores
        GIT_NO_LAZY_FETCH: the transport must still be refused."""
        rev = self.commit()
        marker = Path(tempfile.mkdtemp(prefix="sw-marker")) / "ran"
        self.addCleanup(shutil.rmtree, marker.parent)
        for key, value in (("extensions.partialClone", "origin"), ("remote.origin.promisor", "true"),
                           ("remote.origin.url", f"ext::sh -c touch% {marker}"), ("protocol.ext.allow", "always"),
                           ("protocol.file.allow", "always"), ("remote.origin.uploadpack", f"touch {marker}; false")):
            self.git("config", key, value)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update({k: v for k, v in sw_records.GIT_ENV.items() if k != "GIT_NO_LAZY_FETCH"})
        proc = subprocess.run(["git", *sw_records.GIT_SAFE, "-C", str(self.tmp), "rev-parse", "--verify", "--quiet",
                               "--end-of-options", "a" * 40 + "^{commit}"], capture_output=True, env=env,
                              stdin=subprocess.DEVNULL, timeout=30)
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(marker.exists(), "the promisor remote's transport ran")
        self.assertEqual(sw_records.verify_revision(self.tmp, "b" * 40, self.page)[0], "unavailable")
        self.assertEqual(sw_records.verify_revision(self.tmp, rev, self.page)[0], "passed")
        self.assertFalse(marker.exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs FIFOs")
    def test_a_file_replaced_by_a_fifo_is_stale_without_blocking(self):
        rev = self.commit()
        self.assertEqual(self.record(fingerprint="rev:" + rev)[0], 0)
        self.page.unlink()
        os.mkfifo(self.page)
        self.assertEqual(sw_records.verify_revision(self.tmp, rev, self.page)[0], "stale")

    def test_extra_or_missing_files_under_the_target_are_stale(self):
        rev = self.commit()
        data = json.loads(self.vfile.read_text())
        data["required_checks"] = [{"check_id": "site.404", "target": "site"}]
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(self.record(check_id="site.404", target="site", fingerprint="rev:" + rev)[0], 0)
        self.page.unlink()
        self.assertEqual(self.gate()[1]["result"], "stale")
        self.git("checkout", "-q", "--", "site/index.html")
        (self.tmp / "site" / "link").symlink_to("index.html")
        self.assertEqual(self.gate()[1]["result"], "stale")


if __name__ == "__main__":
    unittest.main()
