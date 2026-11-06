"""Asset authority (0.2.2): `supplied_by` and a standing permission granted by the owner or client.

Run from the dev root: python3 -m unittest discover tests/design
A standing permission makes an owner- or client-supplied asset's rights known; it never covers third-party
material, and only the owner or client can grant it (Claude records the grant, never makes it).
"""
import json
import unittest

from test_design_check import PASS, RECORDS, ScratchCase, findings, run, site

LOGO_USE = "- permitted_use: owner's mark, supplied for use on this site"
PERMISSION = """
### Permission: owner-material

- scope: the owner's own portfolio work, portraits and logo, on this site
- granted_by_role: {role}
- date: 2026-10-27
- source: owner's message in the project chat, 27 Oct 2026
"""


class StandingPermissionTest(ScratchCase):
    source = PASS

    def grant(self, supplied_by="owner", role="owner", with_permission=True):
        self.copy.edit("records/website.md", LOGO_USE,
                       f"- permitted_use: standing:owner-material\n- supplied_by: {supplied_by}")
        if with_permission:
            with open(self.base / "records" / "website.md", "a") as fh:
                fh.write(PERMISSION.format(role=role))

    def rights(self):
        code, report, err = site(self.base, "--release", "--checks", "assets.rights")
        self.assertIsNotNone(report, err)
        return report

    def test_owner_asset_under_a_recorded_permission_passes_a_release_build(self):
        self.grant()
        report = self.rights()
        self.assertEqual(findings(report, "assets.rights"), [], report)
        self.assertEqual({c["result"] for c in report["checks"]}, {"passed"}, report)

    def test_a_standing_permission_never_covers_third_party_material(self):
        self.grant(supplied_by="third-party")
        self.assertTrue(any("needs its own licence" in f for f in findings(self.rights(), "assets.rights")))

    def test_a_cited_permission_must_exist_and_be_granted_by_the_owner_or_client(self):
        self.grant(with_permission=False)
        self.assertTrue(any("does not hold" in f for f in findings(self.rights(), "assets.rights")))

    def test_check_records_refuses_a_grant_by_anyone_but_the_owner_or_client(self):
        self.grant(role="assistant")
        code, out, _ = run("check-records", self.base / "records", script=RECORDS)
        problems = [f["evidence"] for f in out["findings"] if f["severity"] == "defect"]
        self.assertTrue(any("only the owner or client grants" in p for p in problems), out)
        self.assertTrue(any("standing permission owner-material is incomplete" in p
                            or "only the owner or client" in p for p in problems))

    def test_supplied_alone_is_not_authorised(self):
        """The unchanged default: a supplied asset with unknown permitted use fails a release build."""
        self.copy.edit("records/website.md", LOGO_USE, "- permitted_use: unknown\n- supplied_by: owner")
        self.assertTrue(any("unknown permitted use" in f for f in findings(self.rights(), "assets.rights")))


if __name__ == "__main__":
    unittest.main()
