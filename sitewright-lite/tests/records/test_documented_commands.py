"""The record and gate commands the skills document must work as written from the project root.

Run from the dev root: python3 -m unittest discover tests/records
"""
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "tests" / "fixtures" / "sites" / "harbour-lane-static"
COMMAND = re.compile(r'^python3 "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/sw_records\.py" (record|gate) .*$', re.M)
# Values for each documented placeholder, keyed by the option it follows.
VALUES = {"--check-id": "browser.keyboard", "--target": "site", "--result": "passed", "--method": "browser",
          "--tool-and-version": "test-browser 1", "--evidence-path": "docs/website/evidence/browser-rc2.json",
          "--finding": "tab order matched the reading order", "--limitations": "one engine only",
          "--input": "site/assets/site.css", "--reason": "launch criterion"}
REQUIRE = re.compile(r'^python3 "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/sw_records\.py" require .*$', re.M)


def documented(rel):
    return [m.group(0) for m in COMMAND.finditer((ROOT / rel).read_text(encoding="utf-8"))]


def argv_for(command, **values):
    """The documented command as argv, with ${CLAUDE_PLUGIN_ROOT} and every <placeholder> filled in
    (`values` overrides VALUES, keyed by option name without the dashes)."""
    VALUES = dict(globals()["VALUES"], **{"--" + k.replace("_", "-"): v for k, v in values.items()})
    tokens = shlex.split(command.replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT)))
    out, i = [], 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("["):  # optional group such as [--input <path> ...]: fill it once
            group = []
            while not tokens[i].endswith("]"):
                group.append(tokens[i])
                i += 1
            opt = group[0].lstrip("[")
            out += [opt, VALUES[opt]]
            i += 1
            continue
        if "<" in tok and out and out[-1] in VALUES:
            tok = VALUES[out[-1]]
        elif "<" in tok:
            raise AssertionError(f"unfilled placeholder {tok!r} in {command!r}")
        out.append(tok)
        i += 1
    return out


class DocumentedCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw doc cmds "))
        self.project = self.tmp / "proj"
        shutil.copytree(SITE, self.project)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cmd(self, argv):
        proc = subprocess.run(argv, cwd=self.project, capture_output=True, text=True, timeout=60)
        return proc.returncode, json.loads(proc.stdout)

    def test_every_documented_record_and_gate_command_sets_root(self):
        missing = []
        for path in sorted((ROOT / "skills").rglob("*.md")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if (re.search(r"sw_records\.py\"? (record|gate)\b", line) or re.search(
                        r"python3 .*sw_records\.py\"? (status|require|compact|check-state)\b", line)) and "--root" not in line:
                    missing.append(f"{path.relative_to(ROOT)}: {line.strip()[:100]}")
        self.assertEqual(missing, [])

    def test_verify_skill_record_command_runs_from_the_project_root(self):
        [record, gate] = documented("skills/website-verify/SKILL.md")
        argv = argv_for(record)
        code, out = self.run_cmd(argv)
        self.assertEqual(code, 0, out)
        rec = out["record"]
        self.assertEqual(rec["target"], "site")
        self.assertEqual(rec["evidence_path"], "docs/website/evidence/browser-rc2.json")
        self.assertEqual(list(rec["inputs"]), ["site/assets/site.css"])
        data = json.loads((self.project / "docs/website/verification.json").read_text())
        self.assertIn({"check_id": "browser.keyboard", "target": "site"}, data["required_checks"])
        code, out = self.run_cmd(argv_for(gate))
        self.assertEqual(out["result"], "passed", out)

    def test_the_command_without_root_infers_the_project_root_for_docs_website(self):
        """rc.2 refused the example without --root (it resolved `site` against docs/website); since rc.5 a
        record kept in docs/website/ resolves against the folder above it, and gate reports where."""
        [record, gate] = documented("skills/website-verify/SKILL.md")
        argv = argv_for(record)
        i = argv.index("--root")
        del argv[i:i + 2]
        code, out = self.run_cmd(argv)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["record"]["target"], "site")
        argv = argv_for(gate)
        i = argv.index("--root")
        del argv[i:i + 2]
        code, out = self.run_cmd(argv)
        self.assertEqual(out["result"], "passed", out)
        self.assertEqual(out["root_source"], "inferred: the folder above docs/website/")
        self.assertEqual(Path(out["root"]).resolve(), self.project.resolve())

    def test_other_documented_record_commands_run_from_the_project_root(self):
        [record] = documented("skills/website-verify/references/no-browser.md")
        code, out = self.run_cmd(argv_for(record))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["record"]["target"], "site")

    def test_browser_checks_record_per_route_with_the_page_inputs(self):
        """0.2.2: a browser check targets the route's built page and takes the files it links as inputs,
        so a rebuild of another page leaves it current (browser-checks.md)."""
        [record] = documented("skills/website-verify/references/browser-checks.md")
        self.assertNotRegex(record, r"--target <build>(?: |$)")
        code, out = self.run_cmd(argv_for(record, target="site/index.html"))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["record"]["target"], "site/index.html")
        self.assertEqual(list(out["record"]["inputs"]), ["site/assets/site.css"])
        code, out = self.run_cmd(argv_for(record.replace(" record ", " gate ", 1).split(" --check-id")[0]))
        self.assertEqual(out["result"], "passed", out)

    def test_documented_require_command_runs_from_the_project_root_and_logs_history(self):
        text = (ROOT / "skills/website-verify/references/evidence-contract.md").read_text(encoding="utf-8")
        [command] = [m.group(0) for m in REQUIRE.finditer(text)]
        self.assertIn("--root .", command)
        argv = argv_for(command)
        argv[argv.index("--check-id") + 1] = "integration.form-endpoint"   # not yet required in the fixture
        code, out = self.run_cmd(argv)
        self.assertEqual((code, out["change"]), (0, "add"), out)
        data = json.loads((self.project / "docs/website/verification.json").read_text())
        self.assertIn({"check_id": "integration.form-endpoint", "target": "site", "modes": ["production"]},
                      data["required_checks"])
        self.assertEqual(data["requirement_history"][-1]["reason"], "launch criterion")


if __name__ == "__main__":
    unittest.main()
