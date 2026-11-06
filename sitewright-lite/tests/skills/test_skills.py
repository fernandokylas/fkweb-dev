"""Structural tests for the shipped skills (item 05 onward).

Run from the dev root: python3 -m unittest discover tests/skills
Free local checks only; skill behaviour is measured by evals/cases with `claude plugin eval`.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
ALL = sorted(p.parent for p in SKILLS.glob("*/SKILL.md"))
# Skills written for Sitewright lite. The Editorial Web Craft family ships in the full Sitewright plugin.
WRITTEN = [d for d in ALL if d.name.startswith("website-")]
# Shared contracts any phase skill may read; everything else must be the skill's own references.
SHARED = {"website-workflow/references/project-records.md", "website-workflow/references/routing.md",
          "website-workflow/references/precedence.md", "website-workflow/references/optional-integrations.md"}
HELPERS = ("sw_records.py", "sw_site_check.py", "sw_wp_theme_check.py", "sw_capture.py", "sw_design_check.py",
           "sw_integrations.py")
SKILL_MAX = 12_000      # characters per SKILL.md (~3k tokens): compaction re-attaches the first 5,000 tokens of each
                        # invoked skill within 25,000 in all (code.claude.com/docs/en/skills, checked 2026-10-27)
CORE = {"website-workflow", "website-plan", "website-design", "website-build-code", "website-build-wordpress",
        "website-motion", "website-verify", "website-assets"}


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return dict(re.findall(r"^([\w-]+): (.*)$", m.group(1), re.MULTILINE)) if m else None


def referenced(skill_dir, text):
    """Markdown-relative reference paths named in a skill file, resolved against the skills root."""
    out = set()
    for ref in re.findall(r"`((?:\.\./)*(?:[\w-]+/)*references/[\w.-]+\.md)`", text):
        path = (skill_dir / ref).resolve()
        out.add(path.relative_to(SKILLS.resolve()).as_posix())
    return out


class SkillStructureTest(unittest.TestCase):
    def test_core_skills_exist(self):
        self.assertLessEqual(CORE, {d.name for d in WRITTEN})

    def test_frontmatter_name_and_description(self):
        for d in WRITTEN:
            fm = frontmatter((d / "SKILL.md").read_text(encoding="utf-8"))
            self.assertIsNotNone(fm, d.name)
            self.assertEqual(fm.get("name"), d.name)
            desc = fm.get("description", "")
            self.assertGreater(len(desc), 100, d.name)
            self.assertLessEqual(len(desc), 1024, d.name)  # stricter than the 1,536-char listing cap
            self.assertRegex(desc, r"(?i)\buse (it|this)\b", d.name)  # says when to trigger

    def test_skill_files_stay_small(self):
        for d in WRITTEN:
            text = (d / "SKILL.md").read_text()
            self.assertLess(len(text.splitlines()), 500, d.name)
            # 0.2.2: an oversized skill body was cut short when it was re-attached after compaction
            self.assertLessEqual(len(text), SKILL_MAX, d.name)

    def test_every_request_gets_an_owner_from_the_router(self):
        """0.2.2: routing is per request, not only per phase, and the same owners appear in the router's
        table and in hooks/owners.txt (the session-start summary that survives compaction)."""
        text = (SKILLS / "website-workflow" / "SKILL.md").read_text(encoding="utf-8")
        section = text.split("## 3. Pick the owner, then load it", 1)[1].split("\n## ", 1)[0]
        for phrase in ("Every new request has an owner", "tracker", "Before any file is edited",
                       "Invoke it with the Skill tool", "`next_owner`"):
            self.assertIn(phrase, section)
        by_request = section.split("By request:", 1)[1].split("By phase:", 1)[0]
        table = set(re.findall(r"`([a-z][\w-]+)`", by_request))
        listed = {l.split(":", 1)[1] for l in (ROOT / "hooks" / "owners.txt").read_text().splitlines()
                  if ":" in l and not l.startswith("#")}
        self.assertEqual(table, {n.strip() for l in listed for n in l.split(",")})
        self.assertEqual(table | {"website-plan", "website-workflow"}, {d.name for d in ALL})

    def test_every_named_reference_exists(self):
        for d in WRITTEN:
            for md in [d / "SKILL.md", *sorted((d / "references").glob("*.md"))]:
                base = d if md.name == "SKILL.md" else md.parent
                for rel in referenced(base, md.read_text(encoding="utf-8")):
                    self.assertTrue((SKILLS / rel).is_file(), (md.relative_to(ROOT).as_posix(), rel))

    def test_phase_skills_load_only_own_or_shared_references(self):
        for d in WRITTEN:
            text = (d / "SKILL.md").read_text(encoding="utf-8")
            for rel in referenced(d, text):
                own = rel.startswith(f"{d.name}/")
                self.assertTrue(own or rel in SHARED, (d.name, rel))

    def test_every_reference_file_is_reachable_from_its_skill(self):
        for d in WRITTEN:
            text = (d / "SKILL.md").read_text(encoding="utf-8")
            for ref in sorted((d / "references").glob("*.md")):
                self.assertIn(f"references/{ref.name}", text, (d.name, ref.name))

    def test_helper_paths_are_plugin_relative_and_quoted(self):
        for d in WRITTEN:
            for md in [d / "SKILL.md", *sorted((d / "references").glob("*.md"))]:
                for line in md.read_text(encoding="utf-8").splitlines():
                    for helper in HELPERS:
                        if helper in line and line.lstrip().startswith("python3"):
                            self.assertIn(f'"${{CLAUDE_PLUGIN_ROOT}}/scripts/{helper}"', line, md)

    def test_plan_only_boundary_is_stated(self):
        plan = (SKILLS / "website-plan" / "SKILL.md").read_text()
        self.assertRegex(plan, r"(?s)Plan-only scope.*stop here")
        for forbidden in ("tokens", "code", "installs"):
            self.assertIn(forbidden, plan.split("Plan-only scope")[1])

    def test_no_approval_gates_or_outward_defaults(self):
        for d in ALL:
            text = (d / "SKILL.md").read_text(encoding="utf-8").lower()
            for phrase in ("wait for approval", "ask the user to approve", "before proceeding, confirm",
                           "npm install -g", "enableallprojectmcpservers", "~/.claude"):
                self.assertNotIn(phrase, text, (d.name, phrase))

    def test_no_provenance_leaks_into_shipped_skills(self):
        """Credits live in NOTICE.md and the provenance records are not shipped, so skills cite neither."""
        for md in SKILLS.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            where = md.relative_to(ROOT).as_posix()
            self.assertNotIn("Concept credits", text, where)
            self.assertNotRegex(text, r"\bcards? [A-Z]\d\d", where)
            self.assertNotIn("docs/provenance", text, where)

    def test_no_editorial_family_routing_in_core_skills(self):
        for d in ALL:
            self.assertFalse((SKILLS / "web-craft").exists())
            text = (d / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("../web-craft/", text, d.name)

    def test_router_hands_phases_to_their_skills(self):
        """A live run wrote the build from inside website-workflow; the router must call the phase skill."""
        text = (SKILLS / "website-workflow" / "SKILL.md").read_text(encoding="utf-8")
        section = text.split("## 3. Pick the owner, then load it", 1)[1].split("\n## ", 1)[0]
        self.assertIn("by calling the Skill tool", section)
        self.assertIn("do not write that phase's files from here", section)
        self.assertIn("Only if a phase skill is not listed as available", section)

    def test_core_skills_never_look_for_edition_extensions(self):
        """Lite ships no extensions, so no skill sends the model to look for an index that is not there.
        Full's copies get that line from tools/sync_skills.py ("insert"), never from this source."""
        for name in CORE:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertNotIn("extensions/", text, name)
            self.assertNotIn("Edition add-ons", text, name)
            self.assertNotIn("full Sitewright", text, name)
        self.assertEqual(sorted(SKILLS.glob("*/extensions")), [])

    def test_notice_lists_every_concept_source(self):
        notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("## Concept credits", notice)
        for source in ("banana-claude", "Emil Kowalski", "WordPress skills", "Taste", "Impeccable", "Anthropic skills",
                       "UI/UX Pro Max", "Huashu", "claude-blog", "claude-seo", "img2threejs"):
            self.assertIn(source, notice, source)


if __name__ == "__main__":
    unittest.main()
