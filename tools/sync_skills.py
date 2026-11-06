#!/usr/bin/env python3
"""One-way sync of shared skills, scripts and hooks between the workspace plugins.

The map (tools/sync-map.json) names a source and its copies. Sources are edited; copies are
overwritten. A copied directory gets a .synced-from marker; a directory copy is refused when
the destination exists without that marker (it was not made by this tool), unless --force.

An entry may list files the destination owns under "except" (paths relative to the entry, a
file or a directory prefix). They are neither compared nor copied nor deleted, so a copy can
carry its own SKILL.md over a shared body. Everything else in the copy is replaced by the source.

An entry may also name, under "insert", a file whose copy gets a fragment added: {"SKILL.md":
"<fragment path>"} puts the fragment's text, as its own paragraph, before the first "## " heading
of that file. The source stays without it, so a line only one edition needs (Full's pointer to its
extensions index) is kept out of the other. A file with no "## " heading, or one that already
contains the fragment, is an error.

  python3 tools/sync_skills.py            copy every source to its destinations
  python3 tools/sync_skills.py --check    report drift only; exit 1 if any copy differs
  python3 tools/sync_skills.py --dry-run  show what would change

Exit codes: 0 in sync / synced, 1 drift (--check) or refused destination, 2 bad map or path.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = ".synced-from"
IGNORE = {"__pycache__", ".DS_Store", MARKER, ".pytest_cache"}


def inside(path: Path) -> Path:
    p = (ROOT / path).resolve()
    if p != ROOT and ROOT not in p.parents:
        raise ValueError(f"path escapes the workspace: {path}")
    return p


def excepted(rel: str, excepts: tuple[str, ...]) -> bool:
    return any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in excepts)


def files(d: Path, excepts: tuple[str, ...] = ()) -> dict[str, Path]:
    out = {}
    for p in sorted(d.rglob("*")):
        rel = p.relative_to(d)
        if p.is_file() and not any(part in IGNORE or part.endswith(".pyc") for part in rel.parts):
            if not excepted(rel.as_posix(), excepts):
                out[rel.as_posix()] = p
    return out


def with_insert(text: str, fragment: str) -> str:
    """text with fragment as its own paragraph before the first '## ' heading."""
    fragment = fragment.strip("\n")
    if fragment in text:
        raise ValueError("the source already contains the fragment")
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("## "):
            return "".join(lines[:i]) + fragment + "\n\n" + "".join(lines[i:])
    raise ValueError("no '## ' heading to insert before")


def expected(p: Path, rel: str, inserts: dict[str, Path]) -> bytes:
    """What the copy of source file p (at rel) must contain."""
    if rel not in inserts:
        return p.read_bytes()
    return with_insert(p.read_text(encoding="utf-8"), inserts[rel].read_text(encoding="utf-8")).encode("utf-8")


def same(p: Path, q: Path, rel: str, inserts: dict[str, Path]) -> bool:
    if rel not in inserts:
        return filecmp.cmp(p, q, shallow=False)
    return expected(p, rel, inserts) == q.read_bytes()


def diff(src: Path, dst: Path, excepts: tuple[str, ...] = (), inserts: dict[str, Path] | None = None) -> list[str]:
    inserts = inserts or {}
    if src.is_file():
        if not dst.is_file():
            return ["missing"]
        return [] if filecmp.cmp(src, dst, shallow=False) else ["content differs"]
    if not dst.is_dir():
        return ["missing"]
    a, b = files(src, excepts), files(dst, excepts)
    out = [f"+ {k}" for k in a.keys() - b.keys()] + [f"- {k} (only in copy)" for k in b.keys() - a.keys()]
    out += [f"~ {k}" for k in a.keys() & b.keys() if not same(a[k], b[k], k, inserts)]
    return sorted(out)


def source_stamp(src: Path) -> str:
    """'<plugin> <version> @ <commit>' for the plugin that holds src, as far as it can be read."""
    parts = []
    for d in (src, *src.parents):
        manifest = d / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                parts.append(f"{data.get('name', d.name)} {data.get('version', '?')}")
            except (OSError, ValueError):
                parts.append(d.name)
            break
        if d == ROOT:
            break
    try:
        head = subprocess.run(["git", "-C", str(src if src.is_dir() else src.parent), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10)
        if head.returncode == 0 and head.stdout.strip():
            parts.append(f"@ {head.stdout.strip()}")
    except (OSError, subprocess.SubprocessError):
        pass
    return " ".join(parts) if parts else "unknown"


def copy(src: Path, dst: Path, label: str, excepts: tuple[str, ...] = (), inserts: dict[str, Path] | None = None) -> None:
    inserts = inserts or {}
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return
    wanted = files(src, excepts)
    if dst.is_dir():
        for rel, p in files(dst, excepts).items():   # synced files that vanished from the source
            if rel not in wanted:
                p.unlink()
        for d in sorted((p for p in dst.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    for rel, p in wanted.items():
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if rel in inserts:
            target.write_bytes(expected(p, rel, inserts))
        else:
            shutil.copy2(p, target)
    text = f"{label}\nCopied by tools/sync_skills.py. Edit the source, not this copy.\n"
    if excepts:
        text += "Owned by this copy, not synced: " + ", ".join(excepts) + "\n"
    for rel, frag in sorted(inserts.items()):
        shown = frag.relative_to(ROOT).as_posix() if frag.is_relative_to(ROOT) else frag.name
        text += f"{rel}: fragment inserted from {shown}\n"
    text += f"Source: {source_stamp(src)}\n"
    (dst / MARKER).write_text(text, encoding="utf-8")


def load_pairs(map_path: Path):
    entries = json.loads(map_path.read_text(encoding="utf-8"))["copies"]
    pairs = []
    for e in entries:
        excepts = tuple(e.get("except", ()))
        if not all(isinstance(x, str) and x and not x.startswith("/") and ".." not in x.split("/") for x in excepts):
            raise ValueError(f"bad except list for {e['from']}: {excepts}")
        inserts = {rel: inside(Path(frag)) for rel, frag in (e.get("insert") or {}).items()}
        for t in e["to"]:
            pairs.append((e["from"], inside(Path(e["from"])), t, inside(Path(t)), excepts, inserts))
    return pairs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="overwrite destination directories without a marker")
    ap.add_argument("--map", type=Path, default=ROOT / "tools" / "sync-map.json")
    args = ap.parse_args(argv)
    try:
        pairs = load_pairs(args.map)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: bad sync map: {exc}", file=sys.stderr)
        return 2
    drift = refused = 0
    for label, src, tlabel, dst, excepts, inserts in pairs:
        if not src.exists():
            print(f"error: source missing: {label}", file=sys.stderr)
            return 2
        try:
            changes = diff(src, dst, excepts, inserts)
        except (OSError, ValueError) as exc:
            print(f"error: {label}: {exc}", file=sys.stderr)
            return 2
        if not changes:
            continue
        drift += 1
        print(f"{tlabel}  <-  {label}")
        for c in changes[:20]:
            print(f"    {c}")
        if args.check or args.dry_run:
            continue
        if src.is_dir() and dst.exists() and not (dst / MARKER).exists() and not args.force:
            print(f"    refused: {tlabel} exists and has no {MARKER} marker (use --force if it is safe to replace)")
            refused += 1
            continue
        copy(src, dst, label, excepts, inserts)
    if args.check:
        print("in sync" if not drift else f"{drift} copy/copies out of sync")
        return 1 if drift else 0
    if not args.dry_run:
        print(f"synced {drift - refused} copy/copies" + (f", refused {refused}" if refused else ""))
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
