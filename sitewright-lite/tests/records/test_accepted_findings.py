"""0.3.0: the user accepts one named warning (a false positive or a sanctioned exception); helpers then
report it under `accepted` instead of `findings`. Defects are never accepted.

Run from the dev root: python3 -m unittest discover tests/records
"""
import datetime
import json
import unittest

from test_batch_and_archive import Base
from test_requirements import PAGE, RECORDS, run


class AcceptFindingCommandTest(Base):
    def setUp(self):
        super().setUp()
        self.require("--check-id", "meta.basics", "--target", "site/index.html", "--reason", "contract")

    def accept(self, *args, target="site/index.html", match="no canonical link", decided_by="owner"):
        argv = ["accept-finding", self.vpath, "--root", self.root, "--check-id", "meta.basics", "--target", target,
                "--match", match, "--reason", "canonical set by the host"]
        if decided_by is not None:
            argv += ["--decided-by", decided_by]
        return run(RECORDS, *argv, *args)

    def test_grant_is_logged_and_replaces_the_same_acceptance(self):
        code, out, err = self.accept("--expires", "2999-01-01")
        self.assertEqual((code, out["change"]), (0, "accept-finding"), (out, err))
        self.accept()
        found = self.data()["accepted_findings"]
        self.assertEqual(len(found), 1)
        self.assertEqual({k: found[0][k] for k in ("check_id", "target", "match", "decided_by")},
                         {"check_id": "meta.basics", "target": "site/index.html", "match": "no canonical link",
                          "decided_by": "owner"})
        history = [h for h in self.data()["requirement_history"] if h["action"] == "accept-finding"]
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0]["weakens"])
        code, out, _ = self.accept("--remove", decided_by=None)
        self.assertEqual((code, out["change"]), (0, "unaccept-finding"))
        self.assertEqual(self.data()["accepted_findings"], [])

    def test_refuses_without_a_decider_or_with_a_broad_or_empty_scope(self):
        before = self.vpath.read_text()
        for kwargs, args in (({"decided_by": None}, ()), ({"target": "site/*.html"}, ()),
                             ({"target": "https://example.com/"}, ()), ({"match": "  "}, ()),
                             ({"target": "../outside"}, ()), ({}, ("--expires", "2000-01-01")),
                             ({}, ("--expires", "soon"))):
            code, out, _ = self.accept(*args, **kwargs)
            self.assertEqual(code, 2, (kwargs, args, out))
        code, out, _ = run(RECORDS, "accept-finding", self.vpath, "--root", self.root, "--check-id", "meta.*",
                           "--target", "site/index.html", "--match", "x", "--reason", "r", "--decided-by", "owner")
        self.assertEqual(code, 2, out)
        self.assertEqual(self.vpath.read_text(), before)


class HelperAcceptanceTest(Base):
    def setUp(self):
        super().setUp()       # a second ordinary page without a canonical (404 pages need none)
        (self.site / "about.html").write_text(PAGE.format(t="About", body="About us."))

    def accept(self, target, match, expires=None, check_id="meta.basics"):
        argv = ["accept-finding", self.vpath, "--root", self.root, "--check-id", check_id, "--target", target,
                "--match", match, "--reason", "canonical set by the host", "--decided-by", "owner"]
        code, out, err = run(RECORDS, *argv, *(["--expires", expires] if expires else []))
        self.assertEqual(code, 0, (out, err))

    def canonical_warnings(self, out):
        return sorted(f["location"] for f in out["findings"] if "canonical" in f["evidence"])

    def test_a_matched_warning_moves_to_accepted_and_others_stay(self):
        code, out, err = self.site_check("--checks", "meta.basics", "--require")
        self.assertIn(code, (0, 1), err)
        self.assertNotIn("accepted", out)                    # no acceptances: no key
        self.assertEqual(self.canonical_warnings(out), ["about.html", "index.html"])
        self.accept("site/index.html", "no canonical link")
        code, out, err = self.site_check("--checks", "meta.basics", out="site-2.json")
        self.assertEqual(self.canonical_warnings(out), ["about.html"])
        self.assertEqual([f["location"] for f in out["accepted"]], ["index.html"])
        self.assertEqual(out["accepted"][0]["accepted"]["decided_by"], "owner")

    def test_a_folder_target_covers_the_pages_inside(self):
        self.site_check("--checks", "meta.basics", "--require")
        self.accept("site", "no canonical link")
        code, out, _ = self.site_check("--checks", "meta.basics", out="site-2.json")
        self.assertEqual(self.canonical_warnings(out), [])
        self.assertEqual(len(out["accepted"]), 2)

    def test_an_expired_acceptance_reports_the_finding_again(self):
        self.site_check("--checks", "meta.basics", "--require")
        self.accept("site/index.html", "no canonical link", expires="2999-01-01")
        data = self.data()
        data["accepted_findings"][0]["expires"] = "2000-01-01"
        self.vpath.write_text(json.dumps(data))
        code, out, _ = self.site_check("--checks", "meta.basics", out="site-2.json")
        self.assertEqual(self.canonical_warnings(out), ["about.html", "index.html"])
        self.assertEqual(out["accepted"], [])
        self.assertTrue(any("expired" in d for d in out["diagnostics"]))

    def test_a_defect_is_never_accepted(self):
        (self.site / "index.html").write_text(PAGE.format(t="Home", body="<span data-fixture>Sample</span>"))
        code, out, err = self.site_check("--checks", "content.fixture-markers", "--require")
        self.assertEqual([f["severity"] for f in out["findings"]], ["warning"], (out, err))
        self.accept("site/index.html", "fixture content", check_id="content.fixture-markers")
        code, out, _ = self.site_check("--checks", "content.fixture-markers", out="site-2.json")
        self.assertEqual((out["findings"], len(out["accepted"])), ([], 1))
        code, out, _ = self.site_check("--checks", "content.fixture-markers", "--release", out="site-3.json")
        self.assertEqual([f["severity"] for f in out["findings"]], ["defect"])
        self.assertEqual((code, out["accepted"]), (1, []))
        self.assertTrue(any("never covers a defect" in d for d in out["diagnostics"]))


class ApplyAcceptancesTest(unittest.TestCase):
    def test_unit_rules(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(RECORDS.parent))
        import sw_records
        root = Path("/p")
        findings = [{"check_id": "a.b", "location": "x/y.html:3", "severity": "warning", "evidence": "foo bar"},
                    {"check_id": "a.b", "location": "x/z.html", "severity": "warning", "evidence": "foo"},
                    {"check_id": "a.c", "location": "x/y.html", "severity": "warning", "evidence": "foo"},
                    {"check_id": "a.b", "location": "xy/y.html", "severity": "warning", "evidence": "foo"}]
        acc = [{"check_id": "a.b", "target": "site/x/y.html", "match": "foo"},
               {"check_id": "a.b", "target": "site/x", "match": "nothing like it"},
               {"check_id": "a.b", "target": "site/x", "match": ""},                     # malformed: ignored
               {"check_id": "a.b"}]                                                       # malformed: ignored
        kept, accepted, notes = sw_records.apply_acceptances(findings, acc, root, lambda loc: root / "site" / loc,
                                                             today=datetime.date(2026, 10, 31))
        self.assertEqual([f["location"] for f in accepted], ["x/y.html:3"])
        self.assertEqual(len(kept), 3)                       # other file, other check, a sibling folder name
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
