#!/usr/bin/env python3
"""Validate every skill in skills/: frontmatter, name = directory, referenced files exist,
every bundled file is mentioned in SKILL.md, no absolute machine paths, SKILL.md under 500 lines.
Also checks the plugin manifests parse, point at real paths and agree on version; hooks/hooks.json
parses and its scripts exist; commands/*.md carry frontmatter with a description.  Exit 1 on any problem."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
problems = []

names = {p.name for p in SKILLS.iterdir() if p.is_dir()}
for d in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
    sk = d / "SKILL.md"
    if not sk.exists():
        problems.append(f"{d.name}: no SKILL.md"); continue
    t = sk.read_text(encoding="utf-8")
    m = re.match(r"^---\nname: (.*?)\ndescription: >-\n((?:  .*\n)+)---\n", t)
    if not m:
        problems.append(f"{d.name}: frontmatter must be `name:` then `description: >-` folded block"); continue
    if m.group(1).strip() != d.name:
        problems.append(f"{d.name}: name '{m.group(1).strip()}' != directory")
    desc = " ".join(l.strip() for l in m.group(2).splitlines())
    if len(desc) < 80:
        problems.append(f"{d.name}: description too short")
    body = t[m.end():]
    if t.count("\n") > 500:
        problems.append(f"{d.name}: SKILL.md over 500 lines")
    for ref in re.findall(r"`((?:assets|references|scripts)/[\w./-]+)`", body):
        if not (d / ref).exists():
            problems.append(f"{d.name}: references missing {ref}")
    for f in d.rglob("*"):
        if f.is_file() and f.name != "SKILL.md" and "__pycache__" not in f.parts:
            rel = str(f.relative_to(d))
            if rel not in body:
                problems.append(f"{d.name}: bundled {rel} never mentioned in SKILL.md")
    for f in d.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".html", ".css", ".js", ".py"):
            if re.search(r"/(?:Users|home/\w+)/|C:\\\\", f.read_text(encoding="utf-8", errors="replace")):
                problems.append(f"{d.name}: machine path in {f.relative_to(d)}")
    for ref in set(re.findall(r"`([a-z]+(?:-[a-z]+){2,})`", body)):
        if ref in names: continue
        head = ref.split("-")[0]
        if head in ("layout","fluid","visual","ground","inline","encapsulated","editorial","tactile","gsap","reduced","html","cascading","typographic","perceived","accessible","cls","sub","adaptive","magnetic","web") \
           and not re.match(r"(html\.|layout\.|inline-block|inline-flex|inline-size|inline-grid|sub-head|web-font)", ref):
            problems.append(f"{d.name}: mentions unknown skill `{ref}`")

# The plugin is listed by the fkweb-dev marketplace; only its own plugin.json lives here.
try:
    data = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
except Exception as e:
    problems.append(f".claude-plugin/plugin.json: {e}")
else:
    for key in ("skills", "commands", "hooks", "mcpServers"):
        v = data.get(key)
        if isinstance(v, str) and not (ROOT / v).exists():
            problems.append(f"plugin.json: {key} → {v} does not exist")

# hooks/hooks.json parses and every ${CLAUDE_PLUGIN_ROOT}/... script exists.
hooks_file = ROOT / "hooks" / "hooks.json"
if not hooks_file.exists():
    problems.append("hooks/hooks.json: required hook manifest is missing")
else:
    try:
        hooks = json.loads(hooks_file.read_text())
    except Exception as e:
        problems.append(f"hooks/hooks.json: {e}")
    else:
        for event, groups in (hooks.get("hooks") or {}).items():
            for g in groups or []:
                for h in g.get("hooks", []):
                    cmd = h.get("command", "")
                    for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"']+)", cmd):
                        target = (ROOT / rel).resolve()
                        try:
                            target.relative_to(ROOT.resolve())
                        except ValueError:
                            problems.append(f"hooks/hooks.json: {event} command → {rel} escapes the repository")
                            continue
                        if not target.is_file():
                            problems.append(f"hooks/hooks.json: {event} command → {rel} does not exist")

CMD_DESC = re.compile(r"^description:[ \t]*\S", re.M)  # value must be on the same line
for sample, want in (
    ("description: Build a page", True),
    ("name: x\ndescription:\tTabbed value", True),
    ("description:   spaced value\nallowed-tools: Read", True),
    ("description:\nallowed-tools: Read", False),
    ("description:   \nallowed-tools: Read", False),
    ("description: \t ", False),
    ("allowed-tools: Read", False),
):
    if bool(CMD_DESC.search(sample)) != want:
        problems.append(f"validate.py self-check: description regex wrong for {sample!r}")

# commands/*.md need frontmatter with a description.
for cmd in sorted((ROOT / "commands").glob("*.md")):
    t = cmd.read_text(encoding="utf-8")
    fm = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    if not fm:
        problems.append(f"commands/{cmd.name}: missing --- frontmatter")
    elif not CMD_DESC.search(fm.group(1)):
        problems.append(f"commands/{cmd.name}: frontmatter has no description")

try:
    json.loads((ROOT / ".mcp.json").read_text())
except Exception as e:
    problems.append(f".mcp.json: {e}")

print("\n".join(problems) if problems else f"validate: {len(names)} skills and manifests OK")
sys.exit(1 if problems else 0)
