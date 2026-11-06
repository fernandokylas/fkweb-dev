#!/usr/bin/env python3
"""Run audit.py over tests/fixtures and compare FAIL counts to expected.json.

Also fails on: a checker reporting ERROR or UNAVAILABLE, audit.py producing no
parseable JSON, an exit code that disagrees with audit.py's own rule (1 if any
checker has fails or an ERROR status), and fixture files not listed in
expected.json.  Exit 1 on any mismatch."""
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
AUDIT = HERE.parent / "skills" / "web-craft" / "scripts" / "audit.py"
expected = json.loads((FIXTURES / "expected.json").read_text())
bad = 0
for fname, checks in expected.items():
    path = FIXTURES / fname
    if not path.exists():
        bad += 1
        print(f"BAD {fname:<22} fixture listed in expected.json but missing")
        continue
    r = subprocess.run([sys.executable, str(AUDIT), str(path), "--json"], capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
        results = data["results"]
    except (ValueError, KeyError, TypeError):
        bad += 1
        print(f"BAD {fname:<22} audit produced no JSON (exit {r.returncode})")
        err = r.stderr.strip()
        if err:
            print("    " + "\n    ".join(err[:600].splitlines()))
        continue
    got = {x["checker"]: len(x["fails"]) for x in results}
    status = {x["checker"]: x.get("status") for x in results}
    for checker, n in checks.items():
        ok = got.get(checker) == n
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {fname:<22} {checker:<12} expected {n} got {got.get(checker)}")
    for x in results:
        if x.get("status") in ("ERROR", "UNAVAILABLE"):
            bad += 1
            note = f" ({x['note']})" if x.get("note") else ""
            print(f"BAD {fname:<22} {x['checker']:<12} status {x['status']}{note}")
    want_rc = 1 if any(x["fails"] or x.get("status") == "ERROR" for x in results) else 0
    if r.returncode != want_rc:
        bad += 1
        print(f"BAD {fname:<22} {'exit code':<12} expected {want_rc} got {r.returncode}")

unlisted = sorted(p.name for p in FIXTURES.iterdir()
                  if p.is_file() and p.name != "expected.json" and not p.name.startswith(".") and p.name not in expected)
for name in unlisted:
    bad += 1
    print(f"BAD {name:<22} fixture not listed in expected.json")
sys.exit(1 if bad else 0)
