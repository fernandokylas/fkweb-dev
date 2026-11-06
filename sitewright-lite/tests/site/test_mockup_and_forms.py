"""Regression tests for the rc.3 live-test findings 1, 2 and 4 (content.mockup-notes, integration.form-endpoint,
release-sensitive modes). Run from the dev root: python3 -m unittest discover tests/site

Every case writes a small scratch project (with spaces in its path). The same pages pass the mock-up gate and
fail the production gate; legitimate mentions of "placeholder" and hidden documentation are not flagged; a
simulated form never satisfies production, and a declared endpoint stays unmet until a browser or manual
submission record exists. The submission test posts only to a stub server on 127.0.0.1.
"""
import http.server
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from test_site_check import RECORDS, run

HEAD = ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><title>{title}</title>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="description" content="A page."></head><body><header><nav><a href="/">Home</a></nav></header>'
        '<main><h1>{title}</h1>\n{body}\n</main><footer><p>Footer</p></footer></body></html>\n')

MOCKUP_PAGE = """
<figure class="hk-media-frame is-placeholder"><span class="hk-media-frame__label">Placeholder</span></figure>
<p class="hk-placeholder-note">Placeholder: final biography copy pending.</p>
<p>Use the placeholder attribute only as a hint; never as the label.</p>
<aside class="hk-mockup-flag" id="hk-form-flag">Mock-up: this form is not connected yet.</aside>
"""

CLEAN_PAGE = """
<p>Use the placeholder attribute only as a hint; never as the label. A mock-up shows layout before content.</p>
<label for="q">Search</label><input id="q" name="q" placeholder="Placeholder">
<template><p>Placeholder</p></template>
<div hidden><p>Placeholder: hidden author note.</p></div>
<p aria-hidden="true">Mock-up</p>
<div style="display:none">Placeholder image</div>
<pre><code>&lt;p&gt;Placeholder&lt;/p&gt;</code></pre>
<!-- Placeholder: comment for developers -->
<noscript><p>Placeholder</p></noscript>
<h2>Placeholder text in design</h2>
"""


def form(attrs, note=""):
    return (f'<form {attrs} aria-describedby="status"><label for="n">Name</label><input id="n" name="n">'
            f'<button type="submit">Send</button><p id="status" role="status" aria-live="polite">{note}</p></form>')


class Project:
    def __init__(self, pages):
        self.tmp = tempfile.TemporaryDirectory(prefix="sw mockup ")
        self.root = Path(self.tmp.name, "client project")
        self.site = self.root / "site"
        for rel, body in pages.items():
            path = self.site / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(HEAD.format(title=rel, body=body))
        self.verification = self.root / "docs" / "website" / "verification.json"
        self.n = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def check(self, *args, record=True):
        extra = []
        if record:
            self.n += 1
            extra = ["--record", self.verification, "--root", self.root, "--require",
                     "--evidence-out", self.root / "docs" / "website" / "evidence" / f"site-{self.n}.json"]
        return run(self.site, "--checks", "content.mockup-notes,integration.form-endpoint", *args, *extra)

    def gate(self, mode="production"):
        return run("gate", self.verification, "--root", self.root, "--mode", mode, script=RECORDS)

    def results(self, report, cid):
        return {c["target"]: c["result"] for c in report["checks"] if c["check_id"] == cid}


class MockupNotesTest(unittest.TestCase):
    def test_labels_and_notes_fail_release_and_warn_for_the_mockup(self):
        with Project({"index.html": MOCKUP_PAGE}) as p:
            code, report, err = p.check(record=False)
            self.assertEqual((code, report["result"]), (0, "passed"), (err, report))
            notes = [f for f in report["findings"] if f["check_id"] == "content.mockup-notes"]
            self.assertEqual([(f["severity"], f["kind"]) for f in notes], [("warning", "convention")])
            self.assertIn("3 visible mock-up note(s)", notes[0]["evidence"])
            code, report, _ = p.check("--release", record=False)
            self.assertEqual(p.results(report, "content.mockup-notes"), {"index.html": "failed"})
            notes = [f for f in report["findings"] if f["check_id"] == "content.mockup-notes"]
            self.assertEqual(notes[0]["severity"], "defect")
            # the prose sentence that mentions "placeholder attribute" is not one of the three
            self.assertNotIn("hint", notes[0]["evidence"])

    def test_explicit_markers_and_project_classes(self):
        body = ('<div data-mockup>Final hero image goes here</div><p data-mockup-note>Copy to come</p>'
                '<p data-placeholder="true">Pending</p><p data-placeholder="name">Not a marker</p>'
                '<div class="hk-mockup-flag">Swap before launch</div>')
        with Project({"index.html": body}) as p:
            _, report, _ = p.check("--release", record=False)
            evidence = next(f["evidence"] for f in report["findings"] if f["check_id"] == "content.mockup-notes")
            self.assertIn("3 visible", evidence)                   # the class is unknown without --mockup-class
            _, report, _ = p.check("--release", "--mockup-class", "hk-mockup-flag", record=False)
            evidence = next(f["evidence"] for f in report["findings"] if f["check_id"] == "content.mockup-notes")
            self.assertIn("4 visible", evidence)

    def test_legitimate_mentions_and_hidden_documentation_are_not_flagged(self):
        with Project({"index.html": CLEAN_PAGE}) as p:
            code, report, err = p.check("--release", record=False)
            self.assertEqual(p.results(report, "content.mockup-notes"), {"index.html": "passed"}, report["findings"])
            self.assertEqual([f for f in report["findings"] if f["check_id"] == "content.mockup-notes"], [])

    def test_same_pages_pass_the_mockup_gate_and_fail_the_production_gate(self):
        with Project({"index.html": MOCKUP_PAGE + form('data-handler="simulated"', "Not connected: demo only.")}) as p:
            code, _, err = p.check()
            self.assertEqual(code, 0, err)
            code, report, err = p.check("--release")
            self.assertEqual(code, 1, err)
            gcode, gate, _ = p.gate("mockup")
            self.assertEqual((gcode, gate["result"]), (0, "passed"), gate)
            gcode, gate, _ = p.gate("production")
            self.assertEqual((gcode, gate["result"]), (1, "failed"), gate)
            failed = {c["check_id"] for c in gate["checks"] if c["result"] == "failed"}
            self.assertEqual(failed, {"content.mockup-notes", "integration.form-endpoint"})
            self.assertIn("not proof of every aspect of launch readiness", gate["criteria_note"])


class FormEndpointTest(unittest.TestCase):
    def test_simulated_form_passes_only_the_mockup(self):
        with Project({"contact.html": form('data-handler="simulated"', "Demo only: messages are not sent.")}) as p:
            _, report, _ = p.check(record=False)
            self.assertEqual(p.results(report, "integration.form-endpoint"), {"contact.html": "passed"})
            _, report, _ = p.check("--release", record=False)
            self.assertEqual(p.results(report, "integration.form-endpoint"), {"contact.html": "failed"})
            self.assertIn("simulated", " ".join(f["evidence"] for f in report["findings"]))

    def test_disclosure_in_described_by_text_counts_as_simulated(self):
        page = ('<p id="flag">Mock-up: this form is not connected yet.</p>'
                '<form action="#" aria-describedby="flag"><label for="e">Email</label><input id="e" name="e">'
                '<button>Send</button></form>')
        with Project({"contact.html": page}) as p:
            _, report, _ = p.check("--release", record=False)
            self.assertEqual(p.results(report, "integration.form-endpoint"), {"contact.html": "failed"})

    def test_missing_endpoint_and_example_host(self):
        with Project({"a.html": form('method="post"'), "b.html": form('action="https://forms.example.com/x"')}) as p:
            _, report, _ = p.check(record=False)
            self.assertEqual(p.results(report, "integration.form-endpoint"), {"a.html": "passed", "b.html": "failed"})
            _, report, _ = p.check("--release", record=False)
            self.assertEqual(p.results(report, "integration.form-endpoint"), {"a.html": "failed", "b.html": "failed"})

    def test_page_without_a_form_has_no_form_endpoint_record(self):
        with Project({"index.html": "<p>No form here.</p>"}) as p:
            _, report, _ = p.check("--release", record=False)
            self.assertEqual(p.results(report, "integration.form-endpoint"), {})

    def test_declared_endpoint_is_not_a_production_pass(self):
        with Project({"contact.html": form('action="https://forms.realprovider.test/f/abc" method="post"')}) as p:
            _, report, _ = p.check("--release", record=False)
            self.assertEqual(p.results(report, "integration.form-endpoint"), {"contact.html": "unavailable"})
            warning = next(f for f in report["findings"] if f["check_id"] == "integration.form-endpoint")
            self.assertEqual(warning["kind"], "evidence")
            p.check()
            p.check("--release")
            gcode, gate, _ = p.gate("production")
            line = next(c for c in gate["checks"] if c["check_id"] == "integration.form-endpoint")
            self.assertEqual(line["result"], "unavailable", gate)
            gcode, gate, _ = p.gate("mockup")
            self.assertEqual(gate["result"], "passed", gate)

    def test_automated_pass_is_refused_at_record_time_and_unmet_at_gate_time(self):
        with Project({"contact.html": form('action="/send" method="post"')}) as p:
            note = p.root / "docs" / "website" / "evidence" / "static.txt"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text("action=/send found in source\n")
            base = ["record", p.verification, "--root", p.root, "--check-id", "integration.form-endpoint",
                    "--target", "site/contact.html", "--result", "passed", "--tool-and-version", "hand 1",
                    "--evidence-path", "docs/website/evidence/static.txt", "--require"]
            code, report, _ = run(*base, "--method", "automated", script=RECORDS)
            self.assertEqual((code, report["result"]), (2, "error"))
            self.assertIn("cannot stand for a working submission", " ".join(report["diagnostics"]))
            # a hand-edited automated pass (bypassing record) still does not satisfy production
            code, _, _ = run(*base, "--method", "automated", "--mode", "mockup", script=RECORDS)
            data = json.loads(p.verification.read_text())
            data["records"][-1].pop("mode")
            p.verification.write_text(json.dumps(data))
            gcode, gate, _ = p.gate("production")
            line = next(c for c in gate["checks"] if c["check_id"] == "integration.form-endpoint")
            self.assertEqual(line["result"], "unavailable", gate)
            self.assertIn("endpoint in source is not enough", line["reason"])

    def test_browser_submission_against_a_local_stub_passes_production(self):
        received = []

        class Stub(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                self.send_response(303)
                self.send_header("Location", "/thanks")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Stub)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/send"
            with Project({"contact.html": form(f'action="{url}" method="post"')}) as p:
                p.check("--release")
                gcode, gate, _ = p.gate("production")
                self.assertNotEqual(gate["result"], "passed")
                request = urllib.request.Request(url, data=b"n=Test", method="POST")
                opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,),
                                                          {"redirect_request": lambda *a, **k: None}))
                try:
                    status = opener.open(request, timeout=5).status
                except urllib.error.HTTPError as exc:
                    status = exc.code
                    exc.close()
                capture = p.root / "docs" / "website" / "evidence" / "submission" / "capture.json"
                capture.parent.mkdir(parents=True, exist_ok=True)
                capture.write_text(json.dumps({"url": url, "status": status, "received": len(received)}))
                code, report, err = run("record", p.verification, "--root", p.root, "--check-id",
                                        "integration.form-endpoint", "--target", "site/contact.html", "--result",
                                        "passed", "--method", "browser", "--mode", "production",
                                        "--tool-and-version", "local stub 1", "--evidence-path",
                                        "docs/website/evidence/submission/capture.json",
                                        "--finding", "POST arrived at the local stub; 303 to /thanks",
                                        script=RECORDS)
                self.assertEqual(code, 0, (err, report))
                self.assertEqual((status, len(received)), (303, 1))
                gcode, gate, _ = p.gate("production")
                line = next(c for c in gate["checks"] if c["check_id"] == "integration.form-endpoint")
                self.assertEqual(line["result"], "passed", gate)
                # a later static release run does not overwrite the submission decision
                p.check("--release")
                gcode, gate, _ = p.gate("production")
                line = next(c for c in gate["checks"] if c["check_id"] == "integration.form-endpoint")
                self.assertEqual(line["result"], "passed", gate)
        finally:
            server.shutdown()
            server.server_close()


class MixedModeTest(unittest.TestCase):
    def test_production_run_tags_only_release_sensitive_checks(self):
        with Project({"index.html": MOCKUP_PAGE}) as p:
            code, report, _ = run(p.site, "--mode", "production", "--checks",
                                  "content.mockup-notes,meta.basics,a11y.landmarks", "--record", p.verification,
                                  "--root", p.root, "--require", "--evidence-out",
                                  p.root / "docs" / "website" / "evidence" / "mixed.json")
            self.assertEqual(report["modes_written"], {"a11y.landmarks": None, "content.mockup-notes": "production",
                                                       "meta.basics": None})
            modes = {(r["check_id"], r.get("mode")) for r in json.loads(p.verification.read_text())["records"]}
            self.assertEqual(modes, {("content.mockup-notes", "production"), ("meta.basics", None),
                                     ("a11y.landmarks", None)})
            # the mode-neutral checks count in the mock-up gate; the production-only record does not
            gcode, gate, _ = p.gate("mockup")
            mock = {c["check_id"]: c["result"] for c in gate["checks"]}
            self.assertEqual(mock["meta.basics"], "passed")
            self.assertEqual(mock["content.mockup-notes"], "unavailable")
            gcode, gate, _ = p.gate("production")
            prod = {c["check_id"]: c["result"] for c in gate["checks"]}
            self.assertEqual((prod["meta.basics"], prod["content.mockup-notes"]), ("passed", "failed"))


if __name__ == "__main__":
    unittest.main()
