"""rc.3 regressions from the first real website test: delivery modes, output layout and exclusions,
evidence reuse, the current view (status), archiving (compact) and superseded decisions.
Every scenario runs on a scratch copy; nothing committed is edited."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from test_sw_records import FIXTURE, GateBase, run


def checks_by_id(out):
    return {c["check_id"]: c for c in out["checks"]}


def as_legacy_file(vfile):
    """Put records `record` archived back in front of the active ones, as a 0.2.1 file kept them."""
    archive = vfile.with_name(vfile.stem + "-archive.jsonl")
    data = json.loads(vfile.read_text())
    if archive.exists():
        data["records"] = [json.loads(line)["record"] for line in archive.read_text().splitlines()] + data["records"]
        archive.unlink()
    vfile.write_text(json.dumps(data))


class DeliveryModeTest(GateBase):
    """D-38/D-39: mock-up completion is judged separately and never hides production status."""

    def setUp(self):
        super().setUp()
        self.require({"check_id": "assets.final", "target": "site/index.html", "modes": ["production"]})

    def require(self, *entries):
        data = json.loads(self.vfile.read_text())
        data["required_checks"] += list(entries)
        self.vfile.write_text(json.dumps(data))

    def rec(self, result="passed", mode=None, check_id="a11y.landmarks", **kw):
        args = ["record", self.vfile, "--check-id", check_id, "--target", "site/index.html", "--result", result,
                "--method", "automated", "--tool-and-version", "test 1", "--evidence-path", "evidence/a11y.json"]
        if mode:
            args += ["--mode", mode]
        if result == "skipped":
            args += ["--skip-reason", "not a release run", "--required-or-optional", "optional"]
        for k, v in kw.items():
            args += [f"--{k.replace('_', '-')}", v]
        code, out, err = run(*args)
        self.assertEqual(code, 0, (out, err))
        return out["record"]

    def gate(self, mode=None):
        return run("gate", self.vfile, *(("--mode", mode) if mode else ()))

    def test_default_is_production(self):
        self.rec("passed", "mockup")
        code, out, _ = self.gate()
        self.assertEqual((code, out["mode"]), (1, "production"))

    def test_production_only_check_is_listed_not_required_for_a_mockup(self):
        self.rec("passed", "mockup")
        code, out, _ = self.gate("mockup")
        self.assertEqual((code, out["result"]), (0, "passed"))
        self.assertEqual([(c["check_id"], c["modes"]) for c in out["not_assessed"]], [("assets.final", ["production"])])
        self.assertIn("not part of the mockup criteria", out["not_assessed"][0]["reason"])
        self.assertNotIn("assets.final", checks_by_id(out))           # never counted as passed
        code, out, _ = self.gate("production")
        self.assertEqual(checks_by_id(out)["assets.final"]["result"], "unavailable")

    def test_mockup_skip_cannot_hide_a_production_failure(self):
        """The Husseyne reproduction: a non-release run recorded assets.final as skipped after a release failure."""
        self.rec("passed")
        self.rec("failed", "production", check_id="assets.final")
        self.rec("skipped", "mockup", check_id="assets.final")
        code, out, _ = self.gate("production")
        self.assertEqual((code, out["result"]), (1, "failed"))
        self.assertEqual(checks_by_id(out)["assets.final"]["mode"], "production")

    def test_mockup_run_does_not_replace_production_evidence(self):
        self.rec("failed", "production")
        self.rec("passed", "mockup")
        self.rec("passed", "production", check_id="assets.final")
        self.assertEqual(self.gate("production")[1]["result"], "failed")
        self.assertEqual(self.gate("mockup")[1]["result"], "passed")

    def test_unmoded_records_count_for_both_modes(self):
        self.rec("passed")
        self.rec("passed", check_id="assets.final")
        for mode in ("mockup", "production"):
            code, out, _ = self.gate(mode)
            self.assertEqual((code, out["result"]), (0, "passed"), mode)
            self.assertEqual(checks_by_id(out)["a11y.landmarks"]["mode"], "any")

    def test_required_skip_stays_unmet(self):
        self.rec("passed", check_id="assets.final")
        self.rec("skipped")
        code, out, _ = self.gate()
        line = checks_by_id(out)["a11y.landmarks"]
        self.assertEqual((code, out["result"], line["result"]), (1, "skipped", "skipped"))
        self.assertTrue(line["reason"].startswith("required check skipped (not run); counts as unmet: not a release run"))

    def test_bad_modes_are_errors(self):
        self.require({"check_id": "x", "target": "site/index.html", "modes": ["staging"]})
        code, out, _ = self.gate()
        self.assertEqual((code, out["result"]), (2, "error"))
        code, _, _ = run("record", self.vfile, "--check-id", "x", "--target", "site/index.html", "--result", "passed",
                         "--method", "automated", "--tool-and-version", "t", "--evidence-path", "evidence/a11y.json",
                         "--mode", "staging")
        self.assertEqual(code, 2)

    def test_method_limitations_and_sample_scope_reach_the_gate_and_status(self):
        self.rec("passed", limitations="static only", sample_scope="3 of 12 pages at 320 and 1280px")
        self.rec("passed", check_id="assets.final")
        for cmd in ("gate", "status"):
            line = checks_by_id(run(cmd, self.vfile)[1])["a11y.landmarks"]
            self.assertEqual((line["method"], line["limitations"], line["sample_scope"]),
                             ("automated", "static only", "3 of 12 pages at 320 and 1280px"), cmd)


class LayoutTest(unittest.TestCase):
    """D-40: the build output and the records must not overlap; exclusions are explicit and listed."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw layout "))
        (self.tmp / "index.html").write_text("<h1>Hi</h1>")
        (self.tmp / "styles.css").write_text("h1{color:red}")
        (self.tmp / "assets").mkdir()
        (self.tmp / "assets" / "logo.svg").write_text("<svg/>")
        self.records = self.tmp / "docs" / "website"
        (self.records / "evidence").mkdir(parents=True)
        (self.records / "evidence" / "x.json").write_text("{}")
        self.vfile = self.records / "verification.json"
        self.vfile.write_text(json.dumps({"schema_version": 1, "required_checks": [], "waivers": [], "records": []}))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def record(self, *extra, target="."):
        return run("record", self.vfile, "--root", self.tmp, "--check-id", "site.structure", "--target", target,
                   "--result", "passed", "--method", "automated", "--tool-and-version", "t",
                   "--evidence-path", "docs/website/evidence/x.json", "--require", *extra)

    def test_circular_target_names_the_fix(self):
        code, out, _ = self.record()
        self.assertEqual(code, 2)
        message = " ".join(out["diagnostics"])
        self.assertIn("contains the verification file", message)
        self.assertIn("site/", message)
        self.assertIn("--exclude docs/website", message)

    def test_exclusion_keeps_records_out_of_the_fingerprint(self):
        code, out, _ = self.record("--exclude", "docs/website")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["record"]["exclusions"], ["docs/website"])
        (self.records / "notes.md").write_text("records change all the time")
        code, out, _ = run("gate", self.vfile, "--root", self.tmp)
        self.assertEqual((code, out["result"]), (0, "passed"))
        self.assertEqual(out["checks"][0]["exclusions"], ["docs/website"])   # never silent
        (self.tmp / "styles.css").write_text("h1{color:blue}")
        self.assertEqual(run("gate", self.vfile, "--root", self.tmp)[1]["result"], "stale")

    def test_excluding_website_files_needs_explicit_permission(self):
        code, out, _ = self.record("--exclude", "docs/website", "--exclude", "assets")
        self.assertEqual(code, 2)
        self.assertIn("holds website files", " ".join(out["diagnostics"]))
        code, out, _ = self.record("--exclude", "docs/website", "--exclude", "assets", "--allow-website-exclusion")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["record"]["exclusions"], ["docs/website", "assets"])

    def test_exclusion_must_be_inside_a_folder_target(self):
        for args, target in ((("--exclude", "docs/website"), "index.html"), (("--exclude", "."), "."),
                             (("--exclude", "../x"), "."), (("--exclude", "missing"), ".")):
            self.assertEqual(self.record(*args, target=target)[0], 2, (args, target))

    def test_hand_written_exclusion_outside_the_target_is_an_error(self):
        self.assertEqual(self.record("--exclude", "docs/website")[0], 0)
        data = json.loads(self.vfile.read_text())
        data["records"][0]["exclusions"] = ["../elsewhere"]
        self.vfile.write_text(json.dumps(data))
        self.assertEqual(run("gate", self.vfile, "--root", self.tmp)[1]["result"], "error")

    def test_state_build_output_containing_records_is_caught_at_setup(self):
        state = json.loads((FIXTURE / "state.json").read_text())
        state.pop("completed_artifacts", None)
        state["completed_artifacts"] = []
        state["verification_records"] = ["docs/website/verification.json"]
        path = self.records / "state.json"
        for out_dir, expected in ((".", 1), ("site", 0), ("docs", 1)):
            state["build_output"] = out_dir
            path.write_text(json.dumps(state))
            code, out, _ = run("check-state", path, "--root", self.tmp)
            layout = [f for f in out["findings"] if f["check_id"] == "records.state.layout"]
            self.assertEqual(len(layout), expected, (out_dir, out["findings"]))
            if expected:
                self.assertIn("site/", layout[0]["action"])


class ReuseTest(GateBase):
    """D-43: a new pass must come from a new run, not a copied evidence file."""

    def test_reused_evidence_is_stale_and_a_new_run_passes(self):
        self.assertEqual(self.record()[0], 0)
        self.assertTrue(json.loads(self.vfile.read_text())["records"][0]["evidence_sha256"].startswith("sha256:"))
        self.page.write_text("<h1>Changed</h1>")
        self.assertEqual(self.gate()[1]["result"], "stale")
        self.assertEqual(self.record()[0], 0)                     # same evidence file, unchanged
        code, out, _ = self.gate()
        self.assertEqual(out["result"], "stale")
        self.assertIn("evidence reused", out["checks"][0]["reason"])
        (self.tmp / "evidence" / "a11y.json").write_text('{"run": 2}')   # the check really ran again
        self.assertEqual(self.record()[0], 0)
        self.assertEqual(self.gate()[1]["result"], "passed")

    def test_rerun_on_an_unchanged_target_is_not_reuse(self):
        self.record()
        self.record()
        self.assertEqual(self.gate()[1]["result"], "passed")


class StatusCompactTest(GateBase):
    """D-41/D-42: a readable current view and an explicit, verifiable archive."""

    def setUp(self):
        super().setUp()
        (self.tmp / "site" / "about.html").write_text("<h1>About</h1>")
        (self.tmp / "site" / "style.css").write_text("h1{}")
        data = json.loads(self.vfile.read_text())
        data["required_checks"].append({"check_id": "browser.layout", "target": "site/about.html"})
        data["waivers"] = [{"check_id": "perf.lab", "target": "site/index.html", "reason": "user", "decided_by": "user"}]
        data["client_notes"] = "kept verbatim"
        self.vfile.write_text(json.dumps(data))
        for n in range(3):
            (self.tmp / "evidence" / "a11y.json").write_text(json.dumps({"run": n}))
            self.record()
        self.record(check_id="browser.layout", target="site/about.html", method="browser",
                    inputs=["site/style.css"])
        self.record(check_id="old.check", target="site/index.html")          # no longer required
        as_legacy_file(self.vfile)
        data = json.loads(self.vfile.read_text())
        supplied = dict(data["records"][0], supplied_by="client", observed_finding="client's own audit")
        data["records"].insert(0, supplied)
        self.vfile.write_text(json.dumps(data))

    def test_status_names_stale_inputs_reruns_superseded_and_orphans(self):
        (self.tmp / "site" / "style.css").write_text("h1{color:red}")
        code, out, _ = run("status", self.vfile)
        self.assertEqual(code, 1)
        rows = checks_by_id(out)
        self.assertEqual(rows["browser.layout"]["result"], "stale")
        self.assertIn("input site/style.css changed", rows["browser.layout"]["reason"])
        self.assertEqual(rows["a11y.landmarks"]["history"], 4)
        self.assertEqual([r["tool"] for r in out["rerun"]], ["browser"])
        self.assertEqual(out["history"], {"records": 6, "current": 3, "superseded": 3,
                                          "compact": out["history"]["compact"]})
        self.assertIn({"check_id": "old.check", "target": "site/index.html",
                       "why": "recorded as required but not listed in required_checks"}, out["orphaned"])
        (self.tmp / "site" / "about.html").unlink()
        orphans = {o["check_id"]: o["why"] for o in run("status", self.vfile)[1]["orphaned"]}
        self.assertEqual(orphans["browser.layout"], "target no longer exists")

    def test_compact_dry_run_writes_nothing(self):
        before = self.vfile.read_bytes()
        code, out, _ = run("compact", self.vfile, "--archive", "archive.json")
        # two superseded a11y runs, and old.check, which no gate reads any more
        self.assertEqual((code, out["compact"]["to_archive"], out["compact"]["unread_pairs"],
                          out["compact"]["written"]), (0, 3, 1, False))
        self.assertEqual(self.vfile.read_bytes(), before)
        self.assertFalse((self.tmp / "archive.json").exists())

    def test_compact_preserves_history_current_results_and_client_records(self):
        original = json.loads(self.vfile.read_text())
        gates = {m: run("gate", self.vfile, "--mode", m)[1]["checks"] for m in ("mockup", "production")}
        code, out, _ = run("compact", self.vfile, "--archive", "archive.json", "--write")
        self.assertEqual((code, out["compact"]["written"]), (0, True), out)
        kept = json.loads(self.vfile.read_text())
        archived = json.loads((self.tmp / "archive.json").read_text())
        self.assertEqual(len(kept["records"]) + len(archived["records"]), len(original["records"]))
        for rec in original["records"]:                              # nothing lost, nothing altered
            self.assertIn(rec, kept["records"] + archived["records"])
        self.assertTrue(any(r.get("supplied_by") == "client" for r in kept["records"]))
        self.assertEqual((kept["waivers"], kept["client_notes"], kept["required_checks"]),
                         (original["waivers"], original["client_notes"], original["required_checks"]))
        for mode, checks in gates.items():
            self.assertEqual(run("gate", self.vfile, "--mode", mode)[1]["checks"], checks, mode)
        self.assertEqual(run("compact", self.vfile, "--archive", "archive.json", "--write")[1]["compact"]["to_archive"], 0)

    def test_compact_refuses_an_archive_inside_a_fingerprinted_target(self):
        data = json.loads(self.vfile.read_text())
        data["required_checks"].append({"check_id": "site.all", "target": "site"})
        self.vfile.write_text(json.dumps(data))
        self.record(check_id="site.all", target="site")
        before = self.vfile.read_bytes()
        code, out, _ = run("compact", self.vfile, "--archive", "site/archive.json", "--write")
        self.assertEqual(code, 2)
        self.assertIn("would make that record stale", " ".join(out["diagnostics"]))
        self.assertEqual(self.vfile.read_bytes(), before)
        for bad in ("../outside.json", "verification.json"):
            self.assertEqual(run("compact", self.vfile, "--archive", bad, "--write")[0], 2, bad)


class DecisionTest(unittest.TestCase):
    """D-47: superseded decisions stay, marked, and point at an existing replacement."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw decisions "))
        shutil.copytree(FIXTURE, self.tmp / "proj")
        self.path = self.tmp / "proj" / "state.json"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def check(self, decisions, **extra):
        data = json.loads(self.path.read_text())
        data["accepted_decisions"] = decisions
        data.update(extra)
        self.path.write_text(json.dumps(data))
        return run("check-state", self.path)[1]["findings"]

    def ids(self, findings, check_id="records.state.decisions"):
        return [f["evidence"] for f in findings if f["check_id"] == check_id]

    def test_valid_supersession(self):
        self.assertEqual(self.ids(self.check([
            {"id": "D-2", "decision": "folder URLs", "status": "superseded", "superseded_by": "D-8"},
            {"id": "D-8", "decision": "flat files", "status": "active"}])), [])

    def test_broken_supersessions(self):
        found = self.ids(self.check([
            {"id": "D-1", "status": "superseded"},
            {"id": "D-2", "status": "superseded", "superseded_by": "D-99"},
            {"id": "D-3", "status": "superseded", "superseded_by": "D-4"},
            {"id": "D-4", "status": "superseded", "superseded_by": "D-3"},
            {"id": "D-5", "status": "retired"},
            {"id": "bad id!", "status": "superseded", "superseded_by": "D-3"}]))
        joined = " | ".join(found)
        self.assertIn("D-1 is superseded but names no replacement", joined)
        self.assertIn("superseded by an unknown decision 'D-99'", joined)
        self.assertEqual(sum("cycle" in f for f in found), 1)
        self.assertIn("status 'retired'", joined)
        self.assertIn("id unusable", joined)

    def test_delivery_fields(self):
        findings = self.check([], delivery_mode="beta")
        self.assertTrue(any("delivery_mode" in f["evidence"] for f in findings))
        findings = self.check([], delivery_mode="mockup")
        self.assertTrue(any("without `delivery_criteria`" in f["evidence"] and f["severity"] == "warning"
                            for f in findings))
        findings = self.check([], delivery_mode="mockup", delivery_criteria=["placeholders labelled data-fixture"])
        self.assertFalse(any("delivery" in f["evidence"] for f in findings))
        findings = self.check([], delivery_criteria="all of it")
        self.assertTrue(any("list of strings" in f["evidence"] for f in findings))


if __name__ == "__main__":
    unittest.main()
