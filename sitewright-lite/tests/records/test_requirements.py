"""Regression tests for rc.3 live-test findings 3 and 5: `sw_records.py require` (supported requirement
editing with history) and evidence-preserving rerun hints from `status`.

Run from the dev root: python3 -m unittest discover tests/records
Every case works in a scratch project whose path contains spaces.
"""
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "scripts" / "sw_records.py"
SITE_CHECK = ROOT / "scripts" / "sw_site_check.py"

PAGE = ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><title>{t}</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="description" content="A page."></head><body><header><nav><a href="/">Home</a></nav>'
        '</header><main><h1>{t}</h1><p>{body}</p></main><footer><p>Footer</p></footer></body></html>\n')


def run(script, *args, cwd=None):
    proc = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True,
                          timeout=60, cwd=cwd)
    return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else None, proc.stderr


class Project(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw require ")
        self.root = Path(self.tmp.name, "client project")
        self.site = self.root / "site"
        self.site.mkdir(parents=True)
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Welcome."))
        (self.site / "404.html").write_text(PAGE.format(t="Not found", body="Try the home page."))
        self.vpath = self.root / "docs" / "website" / "verification.json"

    def tearDown(self):
        self.tmp.cleanup()

    def require(self, *args):
        return run(RECORDS, "require", self.vpath, "--root", self.root, *args)

    def data(self):
        return json.loads(self.vpath.read_text())

    def site_check(self, *args, out="site-1.json"):
        return run(SITE_CHECK, self.site, *args, "--record", self.vpath, "--root", self.root, "--evidence-out",
                   self.root / "docs" / "website" / "evidence" / out)

    def gate(self, mode):
        return run(RECORDS, "gate", self.vpath, "--root", self.root, "--mode", mode)


class RequireCommandTest(Project):
    def test_add_widen_and_narrow_append_history(self):
        code, out, err = self.require("--check-id", "assets.final", "--target", "site", "--modes", "production",
                                      "--reason", "final imagery is a launch criterion")
        self.assertEqual((code, out["change"]), (0, "add"), (err, out))
        self.assertEqual(self.data()["required_checks"],
                         [{"check_id": "assets.final", "target": "site", "modes": ["production"]}])
        code, out, _ = self.require("--check-id", "assets.final", "--target", "site",
                                    "--modes", "mockup,production", "--reason", "also check the mock-up")
        self.assertEqual((code, out["change"], out["requirement"]["weakens"]), (0, "update", False))
        self.assertEqual(self.data()["required_checks"], [{"check_id": "assets.final", "target": "site"}])
        code, out, _ = self.require("--check-id", "assets.final", "--target", "site", "--modes", "production",
                                    "--reason", "mock-up uses agreed stand-ins", "--decided-by", "client")
        self.assertEqual((code, out["requirement"]["weakens"]), (0, True))
        self.assertIn("mockup gate no longer requires assets.final site", out["notes"][0])
        history = self.data()["requirement_history"]
        self.assertEqual([(h["action"], h["from_modes"], h["to_modes"], h["weakens"]) for h in history],
                         [("add", [], ["production"], False),
                          ("update", ["production"], ["mockup", "production"], False),
                          ("update", ["mockup", "production"], ["production"], True)])
        self.assertEqual(history[2]["decided_by"], "client")
        self.assertTrue(all(h["timestamp"] and h["reason"] for h in history))
        # an identical request writes nothing and adds no history
        code, out, _ = self.require("--check-id", "assets.final", "--target", "site", "--modes", "production",
                                    "--reason", "again")
        self.assertEqual((code, out["change"]), (0, "unchanged"))
        self.assertEqual(len(self.data()["requirement_history"]), 3)

    def test_weakening_without_decided_by_is_refused_and_writes_nothing(self):
        self.require("--check-id", "content.mockup-notes", "--target", "site/index.html", "--reason", "launch")
        before = self.vpath.read_bytes()
        for extra in (["--modes", "mockup"], ["--remove"]):
            code, out, _ = self.require("--check-id", "content.mockup-notes", "--target", "site/index.html",
                                        "--reason", "drop it", *extra)
            self.assertEqual((code, out["result"]), (2, "error"))
            self.assertIn("--decided-by", " ".join(out["diagnostics"]))
        self.assertEqual(self.vpath.read_bytes(), before)

    def test_removing_a_failed_requirement_leaves_it_not_assessed_never_passed(self):
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Placeholder: hero copy pending."))
        code, report, err = self.site_check("--checks", "content.mockup-notes", "--require", "--release")
        self.assertEqual(code, 1, err)
        records_before = self.data()["records"]
        code, gate, _ = self.gate("production")
        self.assertEqual(gate["result"], "failed")
        code, out, err = self.require("--check-id", "content.mockup-notes", "--target", "site/index.html",
                                      "--remove", "--reason", "copy owner accepts it", "--decided-by", "owner")
        self.assertEqual(code, 0, (err, out))
        notes = {n.split(" ")[0]: n for n in out["notes"]}
        self.assertIn("(failed) is now listed as not assessed, never as passed", notes["production"])
        self.assertIn("(unavailable)", notes["mockup"])   # the record is production-only
        self.assertEqual(self.data()["records"], records_before)  # records are never rewritten
        code, gate, _ = self.gate("production")
        self.assertNotIn(("content.mockup-notes", "site/index.html"),
                         {(c["check_id"], c["target"]) for c in gate["checks"] if c["result"] == "passed"})
        assessed = {(i["check_id"], i["target"]) for i in gate["not_assessed"]}
        self.assertIn(("content.mockup-notes", "site/index.html"), assessed)
        code, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "production")
        item = next(i for i in status["not_assessed"] if i["check_id"] == "content.mockup-notes")
        self.assertEqual(item["requirement_change"]["action"], "remove")
        self.assertIn("criteria_note", status)

    def test_invalid_requests_are_refused(self):
        cases = [
            (["--check-id", "a b", "--target", "site", "--reason", "x"], "check ID"),
            (["--check-id", "x.y", "--target", "site", "--modes", "launch", "--reason", "x"], "--modes"),
            (["--check-id", "x.y", "--target", "site", "--modes", ",", "--reason", "x"], "--modes"),
            (["--check-id", "x.y", "--target", "../outside", "--reason", "x"], "outside"),
            (["--check-id", "x.y", "--target", "site", "--reason", "  "], "--reason"),
            (["--check-id", "x.y", "--target", "site", "--remove", "--reason", "x", "--decided-by", "me"],
             "not a required check"),
        ]
        for args, needle in cases:
            code, out, err = self.require(*args)
            self.assertEqual(code, 2, (args, out, err))
            self.assertIn(needle, " ".join(out["diagnostics"]), args)
        self.assertFalse(self.vpath.exists())

    def test_record_require_is_logged_and_compact_keeps_history(self):
        for page in ("index.html", "404.html"):   # first run fails, so the two evidence files differ
            path = self.site / page
            path.write_text(path.read_text().replace('<meta name="description" content="A page.">', ""))
        self.site_check("--checks", "meta.basics", "--require")
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Welcome back."))
        (self.site / "404.html").write_text(PAGE.format(t="Not found", body="Try the menu."))
        self.site_check("--checks", "meta.basics", "--require", out="site-2.json")
        history = self.data()["requirement_history"]
        self.assertEqual({(h["action"], h["target"]) for h in history},
                         {("add", "site/index.html"), ("add", "site/404.html")})
        self.assertTrue(all(h["reason"].startswith("added by record --require (sw_site_check") for h in history))
        archive = self.root / "docs" / "website" / "archive.json"
        code, out, err = run(RECORDS, "compact", self.vpath, "--root", self.root, "--archive", archive, "--write")
        self.assertEqual(code, 0, (err, out))
        self.assertEqual(self.data()["requirement_history"], history)
        self.assertEqual(len(self.data()["records"]), 2)

    def test_gate_and_require_output_carry_the_criteria_note(self):
        self.site_check("--checks", "meta.basics", "--require")
        for mode in ("mockup", "production"):
            _, gate, _ = self.gate(mode)
            self.assertIn("not proof of every aspect of launch readiness", gate["criteria_note"])


class RerunHintTest(Project):
    def stale_site(self):
        self.site_check("--checks", "meta.basics,content.mockup-notes", "--require")
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Welcome back."))
        code, status, err = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "mockup")
        self.assertEqual(code, 1, (err, status))
        return status

    def test_hint_writes_new_evidence_and_keeps_old_records_linked(self):
        status = self.stale_site()
        hint = next(h for h in status["rerun"] if h["tool"] == "sw_site_check")
        self.assertTrue(hint["evidence_out"].startswith("docs/website/evidence/site-check-"), hint)
        self.assertFalse((self.root / hint["evidence_out"]).exists())
        self.assertEqual(shlex.split(hint["command"]), hint["argv"])
        self.assertIn("--release", hint["argv"]) if status["mode"] == "production" else \
            self.assertNotIn("--release", hint["argv"])
        old = {(r["check_id"], r["target"]): r["evidence_path"] for r in self.data()["records"]}
        old_bytes = (self.root / "docs/website/evidence/site-1.json").read_bytes()
        # run it exactly as printed, through a shell, from the project root (whose path has spaces)
        proc = subprocess.run(hint["command"].replace("python3", shlex.quote(sys.executable), 1), shell=True,
                              cwd=hint["run_from"], capture_output=True, text=True, timeout=60)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        self.assertTrue((self.root / hint["evidence_out"]).is_file())
        self.assertEqual((self.root / "docs/website/evidence/site-1.json").read_bytes(), old_bytes)
        archive = self.vpath.with_name("verification-archive.jsonl")      # superseded records, unaltered
        archived = [json.loads(line)["record"] for line in archive.read_text().splitlines()]
        changed = {k for k in old if k[1] == "site/index.html"}     # the edited page; the rest is unchanged
        self.assertTrue(changed and len(changed) < len(old), old)
        self.assertEqual({(r["check_id"], r["target"]) for r in archived}, changed)
        for rec in archived:
            self.assertEqual(rec["evidence_path"], old[(rec["check_id"], rec["target"])])
        for rec in self.data()["records"]:      # unchanged reruns keep their older record and its evidence
            key = (rec["check_id"], rec["target"])
            self.assertEqual(rec["evidence_path"], hint["evidence_out"] if key in changed else old[key])
        code, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "mockup")
        self.assertEqual(code, 0, status)

    def test_hint_reruns_only_the_changed_page(self):
        status = self.stale_site()
        hint = next(h for h in status["rerun"] if h["tool"] == "sw_site_check")
        self.assertEqual(hint["pages"], ["index.html"])
        argv = hint["argv"]
        self.assertEqual([argv[i + 1] for i, a in enumerate(argv) if a == "--page"], ["index.html"])
        before = {(r["check_id"], r["target"]): r for r in self.data()["records"]}
        proc = subprocess.run(hint["command"].replace("python3", shlex.quote(sys.executable), 1), shell=True,
                              cwd=hint["run_from"], capture_output=True, text=True, timeout=60)
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual({c["target"] for c in out["checks"]}, {"index.html"}, out)   # site-relative
        self.assertFalse(out.get("route_changes", {}).get("retired"), out)
        after = {(r["check_id"], r["target"]): r for r in self.data()["records"]}
        self.assertEqual(after[("meta.basics", "site/404.html")], before[("meta.basics", "site/404.html")])

    def test_a_stale_site_404_runs_with_the_changed_page(self):
        """site.404 is recorded on the site folder, so any page edit makes it stale; it needs only the page list."""
        self.site_check("--checks", "meta.basics,site.404", "--require")
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Welcome back."))
        _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "mockup")
        hint = next(h for h in status["rerun"] if h["tool"] == "sw_site_check")
        self.assertEqual(hint["pages"], ["index.html"], hint)
        proc = subprocess.run(hint["command"].replace("python3", shlex.quote(sys.executable), 1), shell=True,
                              cwd=hint["run_from"], capture_output=True, text=True, timeout=60)
        out = json.loads(proc.stdout)
        self.assertEqual({(c["check_id"], c["target"]) for c in out["checks"]},
                         {("meta.basics", "index.html"), ("site.404", ".")}, out)
        _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "mockup")
        self.assertFalse([h for h in status["rerun"] if h["tool"] == "sw_site_check"], status["rerun"])

    def test_a_stale_site_level_check_keeps_the_full_run(self):
        self.site_check("--checks", "meta.basics,site.404", "--require")
        (self.site / "404.html").unlink()
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="Welcome back."))
        _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "mockup")
        hint = next(h for h in status["rerun"] if h["tool"] == "sw_site_check")
        self.assertNotIn("--page", hint["argv"])
        self.assertNotIn("pages", hint)

    def test_consecutive_status_runs_never_suggest_a_cited_path(self):
        self.stale_site()
        cited = {r["evidence_path"] for r in self.data()["records"]}
        seen = set()
        for mode in ("mockup", "production", "mockup"):
            _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", mode)
            for hint in status["rerun"]:
                self.assertNotIn(hint["evidence_out"], cited)
                self.assertFalse((self.root / hint["evidence_out"]).exists())
                seen.add(hint["evidence_out"])
        production = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "production")[1]
        hint = next(h for h in production["rerun"] if h["tool"] == "sw_site_check")
        self.assertIn("--release", hint["argv"])

    def test_paths_with_spaces_and_unknown_site_are_quoted_and_marked(self):
        status = self.stale_site()
        hint = next(h for h in status["rerun"] if h["tool"] == "sw_site_check")
        self.assertIn(shlex.quote(str(SITE_CHECK)), hint["command"])
        self.assertIn("site", hint["argv"])
        # a browser record gets a fresh folder and a description rather than a command
        note = self.root / "docs" / "website" / "evidence" / "kb" / "notes.txt"
        note.parent.mkdir(parents=True)
        note.write_text("tab order checked\n")
        run(RECORDS, "record", self.vpath, "--root", self.root, "--check-id", "browser.keyboard", "--target",
            "site/index.html", "--result", "failed", "--method", "browser", "--tool-and-version", "chrome 1",
            "--evidence-path", "docs/website/evidence/kb/notes.txt", "--require")
        _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "mockup")
        browser = next(h for h in status["rerun"] if h["tool"] == "browser")
        self.assertNotIn("command", browser)
        self.assertIn(browser["evidence_out"], browser["how"])
        self.assertNotEqual(browser["evidence_out"], "docs/website/evidence/kb")

    def test_hint_keeps_the_project_mockup_classes_of_the_run_it_replaces(self):
        (self.site / "index.html").write_text(PAGE.format(t="Home", body='Welcome.</p><p class="is-draft">Bio TBC'))
        self.site_check("--checks", "content.mockup-notes", "--mockup-class", "is-draft", "--require")
        evidence = self.root / "docs/website/evidence/site-1.json"
        saved = json.loads(evidence.read_text())
        self.assertEqual(saved["mockup_classes"], ["is-draft"])
        _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "production")
        hint = next(h for h in status["rerun"] if h["tool"] == "sw_site_check")
        self.assertEqual(hint["argv"][hint["argv"].index("--mockup-class") + 1], "is-draft")
        argv = [sys.executable] + hint["argv"][1:]
        proc = subprocess.run(argv, cwd=hint["run_from"], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 1, proc.stdout)   # the class-only note still fails the release run
        self.assertTrue(any(f["check_id"] == "content.mockup-notes" and "class is-draft" in f["evidence"]
                            for f in json.loads(proc.stdout)["findings"]))
        # a class name the helper would never write (edited evidence) is not echoed into a command
        saved["mockup_classes"] = ["is-draft", "x; rm -rf ~", "--release"]
        evidence.write_text(json.dumps(saved))
        _, status, _ = run(RECORDS, "status", self.vpath, "--root", self.root, "--mode", "production")
        hint = next(h for h in status["rerun"] if h["tool"] == "sw_site_check")
        self.assertEqual([hint["argv"][i + 1] for i, a in enumerate(hint["argv"]) if a == "--mockup-class"],
                         ["is-draft"])
        self.assertEqual(hint["argv"].count("--release"), 1)   # from the mode, never from the evidence file

    def test_helper_refuses_to_overwrite_cited_evidence(self):
        self.site_check("--checks", "meta.basics", "--require")
        before = (self.root / "docs/website/evidence/site-1.json").read_bytes()
        code, out, _ = self.site_check("--checks", "meta.basics")
        self.assertEqual(code, 2)
        self.assertIn("already holds evidence", " ".join(out["diagnostics"]))
        self.assertIn("--evidence-out", " ".join(out["diagnostics"]))
        self.assertEqual((self.root / "docs/website/evidence/site-1.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
