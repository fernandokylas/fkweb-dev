#!/usr/bin/env python3
"""Smoke checks beyond validate.py and run_fixtures.py: every bundled asset and example passes the
audit, bundled JS parses (needs Node; skipped without it), and the write hook runs.

Run from the plugin folder: python3 tests/smoke.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "skills" / "web-craft" / "scripts" / "audit.py"
PAGES = ["skills/encapsulated-mockup-builder/assets/boilerplate.html",
         "skills/layout-editorial-rail/assets/template.html"]
# Stylesheets meant to sit inside a host page's layer order.
HOSTED = ["skills/perceived-latency-mask/assets/skeleton.css",
          "skills/sub-pixel-inertia-scroll/assets/kinetic-planes.css",
          "skills/adaptive-luminescent-border/assets/luminous-borders.css",
          "skills/magnetic-hitbox-warp/assets/magnetic.css"]
LAYERS = "@layer base, layout, components, utilities;\n"

failed = []


def run(label, cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120, **kw)
    if r.returncode:
        failed.append(label)
        print(f"FAIL {label}\n{(r.stdout + r.stderr).strip()[-800:]}")


for page in PAGES:
    run(page, [sys.executable, str(AUDIT), page])
with tempfile.TemporaryDirectory() as tmp:
    for css in HOSTED:
        hosted = Path(tmp) / Path(css).name
        hosted.write_text(LAYERS + (ROOT / css).read_text(encoding="utf-8"), encoding="utf-8")
        run(css, [sys.executable, str(AUDIT), str(hosted)])
for example in sorted(ROOT.glob("examples/*.html")):
    run(example.name, [sys.executable, str(AUDIT), str(example), "--allow-cdn", "--allow-fonts"])

scripts = sorted(ROOT.glob("skills/*/assets/*.js"))
if shutil.which("node"):
    for js in scripts:
        run(js.name, ["node", "-e", "new Function(require('fs').readFileSync(process.argv[1], 'utf8'))", str(js)])
else:
    print(f"skipped: {len(scripts)} JS syntax checks (node unavailable)")

event = json.dumps({"tool_name": "Write", "tool_input": {"file_path": "examples/case-study.html"}})
run("hook", [sys.executable, "hooks/on-write.py"], input=event,
    env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(ROOT)})

print(f"failed: {', '.join(failed)}" if failed else "passed: smoke checks")
sys.exit(1 if failed else 0)
