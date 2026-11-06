"""0.3.0: helper runs keep `recurring_warnings`; status lists a warning seen in three runs in a row.

Run from the dev root: python3 -m unittest discover tests/records
"""
import unittest

from test_batch_and_archive import Base
from test_requirements import PAGE, RECORDS, run


class RecurringWarningsTest(Base):
    def setUp(self):
        super().setUp()
        self.runs = 0         # a second ordinary page without a canonical (404 pages need none)
        (self.site / "about.html").write_text(PAGE.format(t="About", body="About us."))

    def check(self):
        self.runs += 1
        code, out, err = self.site_check("--checks", "meta.basics", "--require", out=f"site-{self.runs}.json")
        self.assertIn(code, (0, 1), (err, out.get("diagnostics")))
        return out

    def recurring(self):
        return self.data().get("recurring_warnings", {})

    def status(self):
        return run(RECORDS, "status", self.vpath, "--root", self.root)[1]["recurring_warnings"]

    def canonical(self, page):
        return [e for e in self.recurring().values()
                if e["location"] == f"site/{page}" and "canonical" in e["evidence"]]

    def test_three_runs_list_the_warning_in_status(self):
        self.check()
        self.check()
        self.assertEqual(self.canonical("index.html")[0]["runs"], 2)
        self.assertEqual(self.status(), [])
        self.check()
        listed = [e for e in self.status() if e["location"] == "site/index.html" and "canonical" in e["evidence"]]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["runs"], 3)
        self.assertIn("accept-finding", listed[0]["action"])
        self.assertLessEqual(listed[0]["first_seen"], listed[0]["last_seen"])

    def test_a_fixed_warning_is_dropped(self):
        self.check()
        self.check()
        fixed = PAGE.format(t="Home", body="Hello.").replace(
            "</head>", '<link rel="canonical" href="https://example.com/"></head>')
        (self.site / "index.html").write_text(fixed)
        self.check()
        self.assertEqual(self.canonical("index.html"), [])
        self.assertEqual(self.canonical("about.html")[0]["runs"], 3)

    def test_an_acceptance_stops_the_count(self):
        self.check()
        self.check()
        code, out, err = run(RECORDS, "accept-finding", self.vpath, "--root", self.root, "--check-id", "meta.basics",
                             "--target", "site/index.html", "--match", "no canonical link",
                             "--reason", "host sets it", "--decided-by", "owner")
        self.assertEqual(code, 0, (out, err))
        self.check()
        self.assertEqual(self.canonical("index.html"), [])
        self.assertFalse(any(e["location"] == "site/index.html" for e in self.status()))

    def test_a_run_of_other_checks_keeps_the_count(self):
        self.check()
        self.check()
        self.site_check("--checks", "content.placeholders", out="other.json")
        self.check()
        self.assertEqual(self.canonical("index.html")[0]["runs"], 3)


if __name__ == "__main__":
    unittest.main()
