#!/usr/bin/env python3
"""Sitewright project records helper (stdlib only, read-only except `record`).

Commands:
  fingerprint PATH...                 sha256 fingerprint of files or directories
  check-records DIR [--phase P]       required fields in brief/site map/design/assets and state.json
  check-state STATE_JSON [--root D]   state record fields and values; recorded artifacts still match
  gate VERIFICATION_JSON [--root D] [--mode M]     aggregate required evidence into one result
  status VERIFICATION_JSON [--root D] [--mode M]   current view: one row per required check, what to
                                      rerun, superseded and orphaned records (read-only)
  compact VERIFICATION_JSON --archive PATH [--root D] [--write]
                                      move superseded records to an archive (dry run unless --write)
  retire VERIFICATION_JSON (--target PATH... | --all-missing) --reason TEXT [--replaced-by URL] [--root D] [--write]
                                      stop requiring checks on removed targets: not assessed, never passed
  prune-evidence VERIFICATION_JSON [--root D] [--mode M] [--current-only] [--write]
                                      once the gate passes, delete evidence files no record cites
  record VERIFICATION_JSON ...        append one evidence record atomically
  accept-finding VERIFICATION_JSON --check-id ID --target PATH --match TEXT --reason TEXT --decided-by USER
                                      the user accepts one named warning (a false positive or exception)

Output: one JSON object on stdout (see website-verify/references/evidence-contract.md).
Exit: 0 passed or skipped, 1 failed / gate not passed, 2 error or unavailable.
"""
import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from html.parser import HTMLParser
from pathlib import Path

TOOL = "sw_records"
TOOL_VERSION = "4"
RESULTS = ("passed", "failed", "unavailable", "error", "stale", "skipped")
OVERALL_ORDER = ("failed", "error", "stale", "unavailable", "skipped")
PHASES = ("context", "structure", "direction", "prototype", "implement", "verify", "handoff")
GATE_MENTION = re.compile(r"sw_records(?:\.py)?\b[^.;]*\b(?:gate|status)\b|\b(?:gate|status)\b[^.;]*sw_records")
SCOPES = ("end-to-end-build", "plan-only", "design-only", "review-only", "refine-component", "verify-only")
BUILD_PATHS = ("custom-code", "wordpress", "undecided")
EVIDENCE_METHODS = ("automated", "browser", "manual")
DELIVERY_MODES = ("mockup", "production")   # what "done" means; production is the default and strictest

BRIEF_FIELDS = ("audience", "purpose", "primary_action", "claims_and_evidence", "scope",
                "delivery_route", "constraints", "unknowns")
SITE_FIELDS = ("routes", "navigation", "missing_page_behaviour")
PAGE_FIELDS = ("route", "page_job", "audience", "primary_action", "content_source",
               "sections_and_hierarchy", "navigation_relationships", "required_components",
               "form_or_data_integrations", "states", "metadata_and_indexing_intent",
               "responsive_intent", "acceptance_checks")
DESIGN_FIELDS = ("authority_source", "design_family", "selected_direction", "semantic_tokens",
                 "type_rules", "layout_rules", "component_states", "responsive_intent", "motion_intent")
ASSET_FIELDS = ("asset_id", "local_path", "source", "permitted_use", "attribution", "crop_and_size",
                "placement", "alt_text", "status")
ASSET_STATUSES = ("supplied", "needed", "placeholder", "approved", "rejected", "missing")
ASSET_SUPPLIERS = ("owner", "client", "third-party", "generated", "unknown")   # optional `supplied_by`
GRANTING_ROLES = ("owner", "client")          # only they grant a standing permission; Claude records it
PERMISSION_FIELDS = ("scope", "granted_by_role", "date", "source")
STANDING_RE = re.compile(r"^\s*standing:\s*([A-Za-z0-9._-]{1,32})\b")
STATE_FIELDS = ("schema_version", "project_identifier", "requested_scope", "build_path",
                "selected_framework_or_builder", "selected_design_family", "current_phase",
                "completed_artifacts", "accepted_decisions", "assumptions", "open_issues",
                "blocked_dependencies", "verification_records", "last_changed_targets", "next_action")
STATE_LISTS = ("completed_artifacts", "accepted_decisions", "assumptions", "open_issues",
               "blocked_dependencies", "last_changed_targets")
EVIDENCE_FIELDS = ("check_id", "target", "result", "required_or_optional", "method",
                   "source_revision_or_target_fingerprint", "tool_and_version", "timestamp",
                   "evidence_path", "observed_finding", "limitations", "issue_id_when_applicable",
                   "skip_reason_when_applicable")
# Optional record fields (all absent in records written before 0.1.0-rc.3, which count for every mode).
OPTIONAL_EVIDENCE_FIELDS = ("inputs", "mode", "exclusions", "evidence_sha256", "sample_scope", "supplied_by",
                            "judged")
# Optional top-level keys of verification.json (append-only log written by `require`).
OPTIONAL_VERIFICATION_KEYS = ("requirement_history", "runs_in_progress", "accepted_findings", "recurring_warnings")
RECURRING_RUNS = 3   # status lists a warning seen in this many helper runs in a row
OPTIONAL_STATE_FIELDS = ("session_summary", "delivery_mode", "delivery_criteria", "build_output", "next_owner",
                         "project_instructions", "removed_routes")
PROJECT_INSTRUCTIONS = ("added", "declined")   # the CLAUDE.md routing snippet was offered once
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"   # the running edition's skills
OPTIONAL_DESIGN_FIELDS = ("label_tracking_max",)   # read by sw_design_check.py; absent means the 0.25em default
DECISION_STATUSES = ("active", "superseded")
DECISION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
# Files a website is made of: an exclusion holding any of these needs --allow-website-exclusion.
WEBSITE_SUFFIXES = (".html", ".htm", ".css", ".js", ".mjs", ".jsx", ".ts", ".tsx", ".php", ".svg", ".png",
                    ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".otf")
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REV_RE = re.compile(r"^rev:([0-9a-f]{7,64})$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
MULTI_INPUT_CHECKS = ("browser.", "wp.runtime-", "visual.measure")   # results depend on more than the target
RENDERED_CHECKS = ("browser.", "visual.measure")   # only a browser run can stand for these
JUDGED_CHECKS = ("visual.review",)                 # a person's judgement from screenshots: method manual
# A production pass for these needs an observed submission (browser or manual), never a source reading.
SUBMISSION_CHECKS = ("integration.form-endpoint",)
CHECK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
REQUIREMENT_ACTIONS = ("add", "update", "remove")
CRITERIA_NOTE = ("a pass establishes only the required checks declared for this mode, judged by their own "
                 "criteria and limitations; it is not proof of every aspect of launch readiness")
GIT_TIMEOUT = 10
QUICK_FILE_BUDGET = 2000
NEXT_ACTION_MAX = 300           # characters: one sentence; the detail belongs in the handover file
HANDOVER_MAX = 8192             # bytes: a handover a fresh session reads in full
ABSOLUTE_PATH = re.compile(r"(?:^|[\s\"'=(`])(/(?:Users|home|Volumes|private|tmp|var|opt|mnt|srv|root)/[^\s\"'`)]*"
                           r"|[A-Za-z]:[\\/][^\s\"'`)]*)")
NAMED_PATH = re.compile(r"(?<![\w<$/.-])((?:\./)?[\w.-]+(?:/[\w.-]+)+\.(?:json|md|html|css|js|csv|txt|xml|php))\b")
CREATES_PATH = re.compile(r"\b(?:create|write|draft|add|generate|make|build|save|export)\b[^.;]{0,40}$", re.I)
# Draft markers left in copy or records. One source: sw_site_check.py builds its page-text pattern
# from PLACEHOLDER_MARKERS. "verify"/"confirm" count only in note forms ("(verify …", "[confirm …",
# "verify:") so ordinary copy such as "verify your email" is not flagged.
PLACEHOLDER_MARKERS = (r"\blorem ipsum\b|\bTODO\b|\bTBD\b|\bTBC\b|\bFIXME\b"
                       r"|\[\s*(?:NEED|TODO|verify|confirm)\b|\(\s*(?:verify|confirm|to be confirmed)\b"
                       r"|\bverify:|\bà (?:vérifier|confirmer)\b")
PLACEHOLDER_RE = re.compile(PLACEHOLDER_MARKERS + r"|\bxxx\b", re.IGNORECASE)
RECORD_NAMES = {"brief": "brief", "site map": "sitemap", "sitemap": "sitemap",
                "design": "design", "assets": "assets"}
# Records each phase needs before work in that phase can proceed.
PHASE_RECORDS = {"context": (), "structure": ("brief",), "direction": ("brief", "sitemap"),
                 "prototype": ("brief", "sitemap", "design"),
                 "implement": ("brief", "sitemap", "design", "assets"),
                 "verify": ("brief", "sitemap", "design", "assets"),
                 "handoff": ("brief", "sitemap", "design", "assets")}


class Report:
    def __init__(self, target):
        self.target = str(target)
        self.findings = []
        self.diagnostics = []
        self.started = time.monotonic()

    def add(self, check_id, location, severity, evidence, action, kind="defect"):
        self.findings.append({"check_id": check_id, "location": location, "severity": severity,
                              "kind": kind, "evidence": evidence, "action": action})

    def emit(self, result, extra=None, code=None):
        out = {"tool": TOOL, "tool_version": TOOL_VERSION, "target": self.target, "result": result,
               "findings": self.findings, "diagnostics": self.diagnostics,
               "duration_ms": int((time.monotonic() - self.started) * 1000)}
        out.update(extra or {})
        print(json.dumps(out, indent=1))
        return code if code is not None else {"passed": 0, "skipped": 0, "failed": 1}.get(result, 2)

    def finish(self, extra=None):
        failed = any(f["severity"] == "defect" for f in self.findings)
        return self.emit("failed" if failed else "passed", extra)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# File hashes seen in this process, keyed by what stat reports, so a file read for several records
# (a shared stylesheet, a page in many checks) is hashed once; a changed file has a new key.
_FILE_HASHES = {}
FINGERPRINT_STATS = {"hashed": 0}


def file_hash(path):
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_ino, st.st_size, st.st_mtime_ns)
    if key not in _FILE_HASHES:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        FINGERPRINT_STATS["hashed"] += 1
        _FILE_HASHES[key] = "sha256:" + h.hexdigest()
    return _FILE_HASHES[key]


def fingerprint(path, exclude=()):
    """sha256 over file bytes, or over sorted (relative path, file hash) pairs for a directory.
    Symlinks contribute their link text and are never followed. `exclude` holds paths relative
    to a directory target (posix spelling) that are left out; with none, the hash is unchanged."""
    path = Path(path)
    skip = set(exclude)
    if path.is_symlink():
        return "sha256:" + hashlib.sha256(("link:" + os.readlink(path)).encode()).hexdigest()
    if path.is_file():
        return file_hash(path)
    if path.is_dir():
        h = hashlib.sha256()
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
            here = Path(dirpath).relative_to(path)
            dirnames[:] = sorted(d for d in dirnames if d not in (".git", "node_modules", "__pycache__")
                                 and (here / d).as_posix() not in skip)
            for name in sorted(filenames):
                p = Path(dirpath, name)
                rel = p.relative_to(path).as_posix()
                if rel in skip:
                    continue
                h.update(f"{rel}\0{fingerprint(p)}\n".encode())
        return "sha256:" + h.hexdigest()
    raise FileNotFoundError(str(path))


def write_json_atomic(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ---------- Markdown records ----------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FIELD_RE = re.compile(r"^(\s*)[-*]\s+`?([a-z][a-z0-9_]*)`?\s*:\s*(.*)$")


def parse_records(texts):
    """Return {'brief': {...}, 'sitemap': {..., 'pages': {route: {...}}}, 'design': {...},
    'assets': {..., 'entries': {id: {...}}}} from Markdown texts [(name, text)]."""
    records = {}
    for source, text in texts:
        record = None
        record_level = 0
        sub = None
        pending = None
        for lineno, line in enumerate(text.splitlines(), 1):
            m = HEADING_RE.match(line)
            if m:
                level, title = len(m.group(1)), m.group(2).strip()
                key = RECORD_NAMES.get(title.lower())
                if key:
                    record, record_level, sub, pending = key, level, None, None
                    records.setdefault(key, {"_loc": f"{source}:{lineno}"})
                    continue
                if record and level <= record_level:
                    record, sub, pending = None, None, None
                    continue
                if record == "sitemap" and title.lower().startswith("page:"):
                    route = title.split(":", 1)[1].strip()
                    sub = records[record].setdefault("pages", {}).setdefault(route, {"_loc": f"{source}:{lineno}"})
                    pending = None
                    continue
                if record == "assets" and title.lower().startswith(("asset:", "permission:")):
                    kind, aid = (part.strip() for part in title.split(":", 1))
                    bucket = "entries" if kind.lower() == "asset" else "permissions"
                    sub = records[record].setdefault(bucket, {}).setdefault(aid, {"_loc": f"{source}:{lineno}"})
                    pending = None
                    continue
                continue
            if not record:
                continue
            target = sub if sub is not None else records[record]
            fm = FIELD_RE.match(line)
            if fm and (pending is None or len(fm.group(1)) <= pending[1]):
                name, value = fm.group(2), fm.group(3).strip()
                target[name] = value
                target.setdefault("_lines", {})[name] = f"{source}:{lineno}"
                pending = (target, len(fm.group(1)), name) if not value else None
                continue
            if pending and line.strip() and (len(line) - len(line.lstrip())) > pending[1]:
                tgt, _, name = pending
                tgt[name] = (tgt[name] + " " + line.strip()).strip()
    return records


ACCEPTANCE_ID = re.compile(r"[a-z][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+(?=$|[\s(:`])")
NOT_CHECK_IDS = re.compile(r"\.(?:html?|css|js|mjs|json|md|php|xml|txt|svg|png|jpe?g|webp|avif)$|^(?:e\.g|i\.e)$")


def acceptance_ids(text):
    """Check IDs (`area.check`) that start the comma- or semicolon-separated items of an
    `acceptance_checks` value; free-text items, file names and abbreviations are not IDs."""
    ids = []
    for item in re.split(r"[,;]", text or ""):
        m = ACCEPTANCE_ID.match(item.strip().strip("`").strip())
        if m and not NOT_CHECK_IDS.search(m.group(0)):
            ids.append(m.group(0))
    return list(dict.fromkeys(ids))


def acceptance_free_text(text):
    """The free-text items of an `acceptance_checks` value: what no check ID proves, so the handover must
    say whether each was delivered or dropped."""
    items = [i.strip().strip("`").strip() for i in re.split(r"[,;]", text or "")]
    return [i for i in items if i and i.lower() not in ("n/a", "none") and not acceptance_ids(i)]


def check_value(report, check_id, loc, name, value):
    if not value:
        report.add(check_id, loc, "defect", f"`{name}` is empty",
                   f"fill `{name}`, or write `unknown (OPEN-n)` / `n/a: <reason>`")
    elif PLACEHOLDER_RE.search(value):
        report.add(check_id, loc, "defect", f"`{name}` holds a placeholder: {value[:80]}",
                   "replace the placeholder with real content or an explicit open issue")
    elif value.lower().startswith("unknown") and "OPEN-" not in value:
        report.add(check_id, loc, "warning", f"`{name}` is unknown without an open issue ID",
                   "add the gap to open_issues and reference its ID", kind="convention")


def require_fields(report, check_id, rec, fields, where):
    for name in fields:
        loc = rec.get("_lines", {}).get(name, rec.get("_loc", where))
        if name not in rec:
            report.add(check_id, rec.get("_loc", where), "defect", f"{where}: missing field `{name}`",
                       f"add `- {name}: ...`")
        else:
            check_value(report, check_id, loc, name, rec[name])


def split_routes(value):
    return [t.strip("`,;") for t in re.split(r"[\s,;]+", value) if t.strip("`,;").startswith("/")]


def cmd_check_records(args):
    root = Path(args.dir)
    report = Report(root)
    if not root.is_dir():
        report.diagnostics.append(f"not a directory: {root}")
        return report.emit("error")
    md = sorted(p for p in root.glob("*.md"))
    texts = []
    for p in md:
        try:
            texts.append((p.name, p.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as exc:
            report.diagnostics.append(f"cannot read {p.name}: {exc}")
            return report.emit("error")
    records = parse_records(texts)
    state = None
    state_path = root / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report.add("records.state", "state.json", "defect", f"state.json unreadable: {exc}",
                       "repair state.json")
    phase = args.phase or (state or {}).get("current_phase") or "structure"
    if phase not in PHASES:
        report.diagnostics.append(f"unknown phase {phase!r}")
        return report.emit("error")
    if state is not None and isinstance(state, dict):
        check_state(report, state, "state.json")
    needed = PHASE_RECORDS[phase]
    for key in needed:
        if key not in records:
            report.add(f"records.{key}", str(root), "defect", f"no `{key}` record for phase `{phase}`",
                       f"create the {key} record (heading `# {key.title()}`) or link an existing one")
    if "brief" in records:
        require_fields(report, "records.brief", records["brief"], BRIEF_FIELDS, "brief")
    if "sitemap" in records:
        sm = records["sitemap"]
        require_fields(report, "records.sitemap", sm, SITE_FIELDS, "site map")
        pages = sm.get("pages", {})
        if not pages:
            report.add("records.sitemap", sm["_loc"], "defect", "site map has no `### Page:` contracts",
                       "add one page contract per route")
        for route, page in pages.items():
            require_fields(report, "records.page", page, PAGE_FIELDS, f"page {route}")
            if page.get("route") and page["route"].strip("` ") != route:
                report.add("records.page", page["_loc"], "defect",
                           f"heading route {route} differs from field route {page['route']}",
                           "make the heading and `route` field agree")
        listed = split_routes(sm.get("routes", ""))
        for r in listed:
            if r not in pages:
                report.add("records.sitemap", sm["_loc"], "defect", f"route {r} has no page contract",
                           "add a `### Page:` contract or remove the route")
        for r in pages:
            if listed and r not in listed:
                report.add("records.sitemap", pages[r]["_loc"], "defect", f"page {r} is not in `routes`",
                           "list the route in `routes`")
        verification = root / "verification.json"
        # From verify on, a page's acceptance check that no gate requires is a defect: the gate could
        # pass while the page's own proof was never run.
        late = phase in ("verify", "handoff")
        named = {route: acceptance_ids(page.get("acceptance_checks", "")) for route, page in pages.items()}
        if verification.exists():
            try:
                required = {c.get("check_id") for c in json.loads(verification.read_text(encoding="utf-8"))
                            .get("required_checks", [])}
            except (OSError, ValueError, AttributeError) as exc:
                required = None
                report.add("records.verification", "verification.json", "defect",
                           f"verification.json unreadable: {exc}", "repair verification.json")
        else:
            required = set()
        if required is not None:
            for route, ids in named.items():
                for cid in ids:
                    if cid not in required:
                        report.add("records.page", pages[route]["_loc"], "defect" if late else "warning",
                                   f"page {route} names check {cid}, which is not in required_checks"
                                   + ("" if verification.exists() else " (no verification.json yet)"),
                                   f"run the check with --require, or `sw_records.py require --check-id {cid} "
                                   "--target <page file> --reason ...`; drop it from the contract only by a "
                                   "recorded decision", kind="defect" if late else "convention")
    extra = {}
    if phase == "handoff" and "sitemap" in records:
        # The handover says, for each of these, delivered or dropped (and by whose decision).
        extra["acceptance_items"] = [{"route": route, "item": item, "location": page.get("_loc")}
                                     for route, page in records["sitemap"].get("pages", {}).items()
                                     for item in acceptance_free_text(page.get("acceptance_checks", ""))]
    if "design" in records:
        require_fields(report, "records.design", records["design"], DESIGN_FIELDS, "design")
    if "assets" in records:
        assets = records["assets"]
        entries = assets.get("entries", {})
        if not entries and "assets" not in assets:
            report.add("records.assets", assets["_loc"], "defect", "assets record has no entries",
                       "add `### Asset:` entries, or `- assets: none (<reason>)` for a text-led site")
        for aid, entry in entries.items():
            require_fields(report, "records.asset", entry, ASSET_FIELDS, f"asset {aid}")
            status = entry.get("status", "")
            if status and status not in ASSET_STATUSES:
                report.add("records.asset", entry["_loc"], "defect", f"asset {aid}: unknown status {status!r}",
                           f"use one of {', '.join(ASSET_STATUSES)}")
            if status == "approved" and entry.get("permitted_use", "").lower().startswith("unknown"):
                report.add("records.asset", entry["_loc"], "defect",
                           f"asset {aid} is approved with unknown permitted use",
                           "confirm permitted use or keep it as a placeholder")
            supplier = entry.get("supplied_by", "").strip().lower().split(" ")[0]
            if supplier and supplier not in ASSET_SUPPLIERS:
                report.add("records.asset", entry["_loc"], "defect", f"asset {aid}: unknown supplied_by {supplier!r}",
                           f"use one of {', '.join(ASSET_SUPPLIERS)}")
            problem = standing_problem(entry, assets.get("permissions", {}))
            if problem:
                report.add("records.asset", entry["_loc"], "defect", f"asset {aid}: {problem}",
                           "record the owner's or client's permission as a `### Permission:` entry, or a licence")
        for pid, perm in assets.get("permissions", {}).items():
            for problem in permission_problems(pid, perm):
                report.add("records.asset", perm["_loc"], "defect", problem,
                           "record scope, granted_by_role (owner or client), date and source of the grant")
    return report.finish(extra)


def permission_problems(pid, perm):
    """Defects of one `### Permission: <id>` entry: a standing grant by the owner or client, never by Claude."""
    out = [f"permission {pid}: missing {name}" for name in PERMISSION_FIELDS if not perm.get(name, "").strip()]
    role = perm.get("granted_by_role", "").strip().lower()
    if role and role not in GRANTING_ROLES:
        out.append(f"permission {pid}: granted_by_role {role!r}; only the owner or client grants a standing "
                   "permission (record a third party's licence on the asset itself)")
    return out


def standing_problem(entry, permissions):
    """Why an asset's `permitted_use: standing:<id>` does not count as known rights, or None. It counts only
    for owner- or client-supplied assets under a complete permission entry."""
    m = STANDING_RE.match(entry.get("permitted_use", ""))
    if not m:
        return None
    perm = permissions.get(m.group(1))
    if perm is None:
        return f"permitted_use cites standing permission {m.group(1)}, which the assets record does not hold"
    if permission_problems(m.group(1), perm):
        return f"standing permission {m.group(1)} is incomplete"
    supplier = entry.get("supplied_by", "").strip().lower().split(" ")[0]
    if supplier not in GRANTING_ROLES:
        return (f"a standing permission covers only owner- or client-supplied material; this asset is "
                f"supplied_by {supplier or 'unrecorded'}, so it needs its own licence")
    return None


# ---------- state ----------

def check_state(report, state, where):
    if not isinstance(state, dict):
        report.add("records.state", where, "defect", "state is not a JSON object", "rewrite state.json")
        return
    for name in STATE_FIELDS:
        if name not in state:
            report.add("records.state", where, "defect", f"missing field `{name}`", f"add `{name}`")
    if state.get("schema_version", 1) != 1:
        report.add("records.state", where, "defect", f"unsupported schema_version {state.get('schema_version')!r}",
                   "use schema_version 1")
    for name, allowed in (("requested_scope", SCOPES), ("build_path", BUILD_PATHS), ("current_phase", PHASES)):
        if name in state and state[name] not in allowed:
            report.add("records.state", where, "defect", f"`{name}` is {state[name]!r}",
                       f"use one of {', '.join(allowed)}")
    for name in STATE_LISTS:
        if name in state and not isinstance(state[name], list):
            report.add("records.state", where, "defect", f"`{name}` must be a list", f"make `{name}` a list")
    if state.get("requested_scope") == "plan-only" and state.get("current_phase") in PHASES[2:]:
        report.add("records.state", where, "defect",
                   f"plan-only scope is in phase {state['current_phase']}",
                   "planning stays planning: stop after the site map, or record the user's change of scope")
    if state.get("requested_scope") == "review-only" and state.get("current_phase") == "implement":
        report.add("records.state", where, "defect", "review-only scope is in phase implement",
                   "report findings; implement only if the user asked for fixes")
    if "session_summary" in state and not isinstance(state["session_summary"], bool):
        report.add("records.state", where, "defect", "`session_summary` must be true or false",
                   "set `session_summary` to true (opt in to the session-start summary) or false")
    if "delivery_mode" in state and state["delivery_mode"] not in DELIVERY_MODES:
        report.add("records.state", where, "defect", f"`delivery_mode` is {state['delivery_mode']!r}",
                   f"use one of {', '.join(DELIVERY_MODES)} (production when unsure)")
    criteria = state.get("delivery_criteria")
    if criteria is not None and not (isinstance(criteria, list) and all(isinstance(c, str) for c in criteria)):
        report.add("records.state", where, "defect", "`delivery_criteria` must be a list of strings",
                   "list each criterion the delivery is judged on, e.g. \"placeholders labelled data-fixture\"")
    if "delivery_mode" not in state and state.get("requested_scope") in ("end-to-end-build", "refine-component",
                                                                     "verify-only"):
        report.add("records.state", where, "warning",
                   "`delivery_mode` is not set, so hooks and gates judge this project as production",
                   "set `delivery_mode` to \"mockup\" or \"production\" explicitly at every checkpoint",
                   kind="convention")
    action = state.get("next_action")
    if isinstance(action, str) and GATE_MENTION.search(action) and "--root" not in action:
        report.add("records.state", where, "warning",
                   "`next_action` asks for a gate or status run without --root",
                   "write the complete command, run from the project root: python3 \"<plugin>/scripts/"
                   "sw_records.py\" gate docs/website/verification.json --root . --mode <delivery_mode>",
                   kind="convention")
    if isinstance(action, str) and len(action) > NEXT_ACTION_MAX:
        report.add("records.state", where, "warning",
                   f"`next_action` is {len(action)} characters (keep it under {NEXT_ACTION_MAX})",
                   "keep next_action to one sentence and put the detail in the handover file "
                   "(docs/website/HANDOVER.md)", kind="convention")
    if isinstance(action, str) and (absolute := ABSOLUTE_PATH.search(action)):
        report.add("records.state", where, "warning",
                   f"`next_action` names an absolute path ({absolute.group(1)[:60]})",
                   "write project paths relative to the project root and the plugin's scripts as "
                   "\"<plugin>/scripts/…\": absolute paths break on another machine or checkout", kind="convention")
    if "handover" in state and not relative_path_ok(state["handover"]):
        report.add("records.state.handover", where, "defect", "`handover` must be a project-relative path",
                   "record it as e.g. docs/website/HANDOVER.md")
    if state.get("delivery_mode") == "mockup" and not criteria:
        report.add("records.state", where, "warning", "mock-up delivery without `delivery_criteria`",
                   "name what the mock-up is allowed to simulate (placeholders, fake forms) so nothing is "
                   "waived silently", kind="convention")
    if "build_output" in state and not relative_path_ok(state["build_output"]):
        report.add("records.state.layout", where, "defect", "`build_output` must be a project-relative path",
                   "record the build folder, e.g. site/")
    if "accepted_decisions" in state and isinstance(state["accepted_decisions"], list):
        check_decisions(report, state["accepted_decisions"], where)
        check_issue_links(report, state, where)
        check_issues(report, state, where)
    owner = state.get("next_owner")
    if owner is not None:
        if not (isinstance(owner, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", owner)):
            report.add("records.state", where, "defect", "`next_owner` must be a skill name such as website-seo",
                       "name the skill that owns next_action")
        elif SKILLS_DIR.is_dir() and not (SKILLS_DIR / owner / "SKILL.md").is_file():
            report.add("records.state", where, "warning",
                       f"`next_owner` {owner!r} is not a skill of this plugin",
                       "use one of: " + ", ".join(sorted(p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md"))),
                       kind="convention")
    if "project_instructions" in state and state["project_instructions"] not in PROJECT_INSTRUCTIONS:
        report.add("records.state", where, "defect", f"`project_instructions` is {state['project_instructions']!r}",
                   f"use one of {', '.join(PROJECT_INSTRUCTIONS)} (whether the CLAUDE.md routing lines were added)")
    if "removed_routes" in state:
        for problem in removed_route_problems(state["removed_routes"], state.get("accepted_decisions")):
            report.add("records.state", where, "defect", problem,
                       "list each intentionally removed route as {route, reason, decision or source}")
    if not str(state.get("next_action", "")).strip():
        report.add("records.state", where, "warning", "`next_action` is empty",
                   "record the next useful action for resume", kind="convention")


PLUGIN_HOUSEKEEPING = re.compile(r"verification\.json|sw_records|prune-evidence|\bre-?record|\bfingerprint"
                                 r"|\b(?:compact|retire|prune)\w* (?:the )?(?:verification|records?|evidence|checks?)",
                                 re.I)
ISSUE_LEVELS = ("mockup", "production", "launch")     # each level includes the ones before it
ISSUE_STATUSES = ("open", "resolved", "wontfix")
OWNER_KINDS = ("person", "skill")


def issue_blocks(issue):
    """The lowest gate level an open issue blocks ("mockup" < "production" < "launch"), or None.
    Legacy `blocking: true` blocks production (and so launch); a list names levels."""
    if not isinstance(issue, dict) or issue.get("status", "open") != "open":
        return None
    blocking = issue.get("blocking")
    if blocking is True:
        return "production"
    if isinstance(blocking, list):
        levels = [ISSUE_LEVELS.index(b) for b in blocking if b in ISSUE_LEVELS]
        return ISSUE_LEVELS[min(levels)] if levels else None
    return None


def check_issues(report, state, where):
    """Shape of the optional issue fields: opened, source, owner, blocking, status, resolved, history."""
    for n, issue in enumerate(state.get("open_issues") or []):
        if not isinstance(issue, dict):
            report.add("records.state.issues", where, "defect", f"open_issues[{n}] is not an object",
                       "write {id, issue, blocking}")
            continue
        label = issue.get("id") if isinstance(issue.get("id"), str) else f"open_issues[{n}]"
        blocking = issue.get("blocking", False)
        if not (isinstance(blocking, bool) or (isinstance(blocking, list) and blocking
                                               and all(b in ISSUE_LEVELS for b in blocking))):
            report.add("records.state.issues", where, "defect", f"{label}: `blocking` is {blocking!r}",
                       f"use true/false or a list of {', '.join(ISSUE_LEVELS)}")
        status = issue.get("status", "open")
        if status not in ISSUE_STATUSES:
            report.add("records.state.issues", where, "defect", f"{label}: `status` is {status!r}",
                       f"use one of {', '.join(ISSUE_STATUSES)}")
        elif status != "open" and not issue.get("resolved"):
            report.add("records.state.issues", where, "warning", f"{label} is {status} without `resolved`",
                       "add `resolved` (date and who or what closed it)", kind="convention")
        owner = issue.get("owner")
        if owner is not None and not (isinstance(owner, dict) and owner.get("kind") in OWNER_KINDS
                                      and isinstance(owner.get("name"), str) and owner["name"].strip()):
            report.add("records.state.issues", where, "defect", f"{label}: `owner` must be {{kind, name}}",
                       f"kind is one of {', '.join(OWNER_KINDS)}; name is the person or the skill")
        if (isinstance(owner, dict) and owner.get("kind") == "person" and status == "open"
                and PLUGIN_HOUSEKEEPING.search(str(issue.get("issue", "")))):
            report.add("records.state.issues", where, "warning",
                       f"{label} gives the owner plugin housekeeping ({str(issue.get('issue'))[:60]})",
                       "re-recording checks, compacting or pruning records is the next session's work: give it a "
                       "skill owner (website-verify) and keep owner tasks to decisions and material", kind="convention")
        if "history" in issue and not isinstance(issue["history"], list):
            report.add("records.state.issues", where, "defect", f"{label}: `history` must be a list",
                       "append one entry per change: {date, change}")
        for name in ("opened", "source", "resolved"):
            if name in issue and not isinstance(issue[name], str):
                report.add("records.state.issues", where, "defect", f"{label}: `{name}` must be a string",
                           f"write `{name}` as text")


def blocking_issues(state, level):
    """Open issues that block a gate at `level` (mockup, production or launch)."""
    rank = ISSUE_LEVELS.index(level)
    return [i for i in (state or {}).get("open_issues") or []
            if issue_blocks(i) is not None and ISSUE_LEVELS.index(issue_blocks(i)) <= rank]


def gate_state(args, vpath):
    """The state record the gate reads for blocking issues: --state, else state.json beside the
    verification file. A missing file is no state; an unreadable one is a diagnostic."""
    path = Path(args.state) if getattr(args, "state", None) else Path(vpath).parent / "state.json"
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data if isinstance(data, dict) else None), path
    except (OSError, ValueError) as exc:
        return None, f"{path}: {exc}"


def check_issue_links(report, state, where):
    """An open issue may name the decision it depends on; once that decision is superseded the issue
    must be closed or re-linked rather than outlive it."""
    decisions = {d.get("id"): d for d in state["accepted_decisions"] if isinstance(d, dict)}
    for n, issue in enumerate(state.get("open_issues") or []):
        if not isinstance(issue, dict) or "decision" not in issue:
            continue
        label = issue.get("id") if isinstance(issue.get("id"), str) else f"open_issues[{n}]"
        linked = decisions.get(issue["decision"])
        if linked is None:
            report.add("records.state.issues", where, "warning",
                       f"{label} depends on unknown decision {str(issue['decision'])[:40]!r}",
                       "point `decision` at an id in accepted_decisions, or drop the link", kind="convention")
        elif linked.get("status") == "superseded":
            report.add("records.state.issues", where, "warning",
                       f"{label} depends on {issue['decision']}, superseded by {linked.get('superseded_by', '?')}",
                       "close the issue or re-link it to the decision that replaced it", kind="convention")
    for d in decisions.values():
        if "source" in d and not (isinstance(d["source"], str) and d["source"].strip()):
            report.add("records.state.decisions", where, "defect",
                       f"decision {d.get('id')}: `source` must say who made it and when",
                       "e.g. \"owner, message of 2026-10-25\"")


def active_decision(state, did):
    """The active accepted decision `did` with a recorded source, or None."""
    for d in (state or {}).get("accepted_decisions") or []:
        if isinstance(d, dict) and d.get("id") == did:
            ok = d.get("status", "active") == "active" and isinstance(d.get("source"), str) and d["source"].strip()
            return d if ok else None
    return None


def removed_route_problems(entries, decisions):
    if not isinstance(entries, list):
        return ["`removed_routes` must be a list"]
    known = {d.get("id") for d in decisions or [] if isinstance(d, dict)}
    problems = []
    for n, e in enumerate(entries):
        if not (isinstance(e, dict) and isinstance(e.get("route"), str) and e["route"].startswith("/")
                and isinstance(e.get("reason"), str) and e["reason"].strip()):
            problems.append(f"removed_routes[{n}] needs a `route` starting with / and a `reason`")
        elif not (e.get("decision") in known or (isinstance(e.get("source"), str) and e["source"].strip())):
            problems.append(f"removed_routes[{n}] ({e['route']}) names no accepted decision or `source` showing "
                            "the removal was intended")
    return problems


def check_decisions(report, decisions, where):
    """Superseded decisions stay in the list, marked with status and the id that replaced them."""
    ids = [d.get("id") for d in decisions if isinstance(d, dict)]
    known = {i for i in ids if isinstance(i, str)}
    replaced_by = {}
    for n, d in enumerate(decisions):
        if not isinstance(d, dict):
            continue
        did, status, by = d.get("id"), d.get("status"), d.get("superseded_by")
        label = did if isinstance(did, str) else f"accepted_decisions[{n}]"
        if status is not None and status not in DECISION_STATUSES:
            report.add("records.state.decisions", where, "defect", f"decision {label}: status {status!r}",
                       f"use one of {', '.join(DECISION_STATUSES)}")
        updates = d.get("updates")
        if updates is not None and not (isinstance(updates, list) and all(relative_path_ok(u) for u in updates)):
            report.add("records.state.decisions", where, "defect",
                       f"decision {label}: `updates` must list project-relative paths",
                       "list the documents the decision changed, e.g. [\"docs/website/brief.md\"]")
        if status == "superseded" and by is None:
            report.add("records.state.decisions", where, "defect",
                       f"decision {label} is superseded but names no replacement",
                       "set `superseded_by` to the id of the decision that replaced it")
        if by is None:
            continue
        if status == "active":
            report.add("records.state.decisions", where, "defect",
                       f"decision {label} is active but names `superseded_by`",
                       "set status to superseded, or remove `superseded_by`")
        if not (isinstance(did, str) and DECISION_ID_RE.match(did)):
            report.add("records.state.decisions", where, "defect",
                       f"decision {label} has an id unusable in a supersession",
                       "give it an id of 1-32 letters, digits, dots, dashes or underscores")
            continue
        if not (isinstance(by, str) and DECISION_ID_RE.match(by)) or by not in known or by == did:
            report.add("records.state.decisions", where, "defect",
                       f"decision {did} is superseded by an unknown decision {str(by)[:40]!r}",
                       "point `superseded_by` at an existing decision id")
            continue
        replaced_by[did] = by
    for start in sorted(replaced_by):
        seen, cur = [start], replaced_by[start]
        while cur in replaced_by and cur not in seen:
            seen.append(cur)
            cur = replaced_by[cur]
        if cur == start and start == min(seen):    # report each cycle once
            report.add("records.state.decisions", where, "defect",
                       "decisions supersede each other in a cycle: " + " → ".join(seen + [cur]),
                       "the newest decision must stay active")


def check_layout(report, state, where, root, state_path):
    """A build folder that contains the records would fingerprint its own evidence: catch it at setup."""
    out = state.get("build_output")
    if not isinstance(out, str) or not relative_path_ok(out):
        return
    path, err = resolve_target(root, out)
    if err:
        report.add("records.state.layout", where, "defect", f"`build_output` {out}: {err}",
                   "keep the build inside the project")
        return
    listed = state.get("verification_records")
    listed = [listed] if isinstance(listed, str) else listed if isinstance(listed, list) else []
    records = [("the state record", Path(state_path))]
    records += [(f"verification record {v}", root / v) for v in listed if isinstance(v, str) and relative_path_ok(v)]
    for label, rec in records:
        if covers(path, rec):
            report.add("records.state.layout", where, "defect",
                       f"`build_output` {out} contains {label}; every recorded check of the build would "
                       "fingerprint its own records and evidence",
                       "build into its own folder such as site/ and keep records and evidence in docs/website/")
            return


def is_verification_record(state, root, path):
    listed = state.get("verification_records")
    listed = [listed] if isinstance(listed, str) else listed if isinstance(listed, list) else []
    return any(isinstance(v, str) and relative_path_ok(v) and covers(root / v, path) and covers(path, root / v)
               for v in listed)


def too_many_files(folder, budget):
    seen = 0
    for _dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in GLOB_SKIP]
        seen += len(filenames)
        if seen > budget:
            return True
    return False


def check_artifacts(report, state, where, root, budget=None):
    """Resume check: every completed artifact still exists with its recorded fingerprint. With a file
    `budget` (the session hook's quick mode), a larger folder is reported as not checked, never as current."""
    for n, art in enumerate(state.get("completed_artifacts") or []):
        if not isinstance(art, dict) or not str(art.get("path", "")).strip():
            report.add("records.state.artifact", where, "defect", f"completed_artifacts[{n}] has no path",
                       "record {path, phase, fingerprint}")
            continue
        path, err = resolve_target(root, art["path"])
        if err:
            report.add("records.state.artifact", art["path"], "defect", err, "record paths inside the project")
        elif not path.exists():
            report.add("records.state.artifact", art["path"], "defect",
                       f"recorded {art.get('phase', '?')} artifact is missing",
                       "treat its phase as not done; rebuild it or remove the entry with a reason")
        elif not str(art.get("fingerprint", "")).strip():
            report.add("records.state.artifact", art["path"], "defect",
                       f"{art.get('phase', '?')} artifact recorded as complete with no fingerprint",
                       "fingerprint it with `sw_records.py fingerprint` once it is checked; until then treat its phase as not done")
        elif (budget is not None and path.is_dir() and not path.is_symlink()
              and too_many_files(path, budget)):
            report.add("records.state.artifact", art["path"], "warning",
                       f"not checked in this quick summary: the folder holds more than {budget} files",
                       "run `sw_records.py check-state` without --quick to compare its fingerprint",
                       kind="convention")
        elif (current := fingerprint(path)) != art["fingerprint"] and is_verification_record(state, root, path):
            report.add("records.state.artifact", art["path"], "warning",
                       "verification record changed since its fingerprint was taken (expected: every recorded "
                       "run appends to it); its currency is the gate's result, not this fingerprint",
                       "run the gate; list verification records in verification_records rather than "
                       "completed_artifacts", kind="convention")
        elif current != art["fingerprint"]:
            report.add("records.state.artifact", art["path"], "defect",
                       "artifact changed since it was recorded",
                       "re-read it, reconcile decisions and evidence that depend on it, then re-record its fingerprint")


def handover_path(state, root, state_path):
    """The handover file: state `handover` (project-relative), else HANDOVER.md beside state.json."""
    rel = state.get("handover")
    if isinstance(rel, str) and relative_path_ok(rel):
        return root / rel, rel
    path = Path(state_path).parent / "HANDOVER.md"
    try:
        return path, path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path, str(path)


def check_handover(report, state, where, root, state_path):
    """The short handover file a fresh session reads first, and the paths next_action names."""
    if "handover" in state and not relative_path_ok(state["handover"]):
        return                                   # reported by check_state
    path, label = handover_path(state, root, state_path)
    severity = "defect" if state.get("current_phase") == "handoff" else "warning"
    kind = "defect" if severity == "defect" else "convention"
    if not path.is_file():
        report.add("records.state.handover", label, severity, "no handover file",
                   "write it at every checkpoint (under 8 KB): where the project stands, what changed this "
                   "session, the next step and its owner, questions for the owner", kind=kind)
    elif (size := path.stat().st_size) > HANDOVER_MAX:
        report.add("records.state.handover", label, severity,
                   f"handover file is {size} bytes (keep it under {HANDOVER_MAX})",
                   "rewrite it as the current picture, not a log: move history to the decision ledger or git",
                   kind=kind)
    action = state.get("next_action")
    if not isinstance(action, str):
        return
    for m in NAMED_PATH.finditer(action):
        rel = m.group(1)
        if rel.startswith(("scripts/", "skills/", "hooks/")) or CREATES_PATH.search(action[:m.start()]):
            continue                             # a plugin path, or a file the step is meant to create
        target, err = resolve_target(root, rel)
        if err is None and not target.exists():
            report.add("records.state", where, "warning",
                       f"`next_action` names {rel}, which does not exist in the project",
                       "fix the path (relative to the project root); if the step creates the file, say so",
                       kind="convention")


def check_decision_updates(report, state, where, root):
    """`updates` lists the documents a decision changed: each must exist, and a decision that replaced
    another must be named in each of them, so the brief or design cannot keep the old direction."""
    decisions = [d for d in state.get("accepted_decisions") or [] if isinstance(d, dict)]
    replaced = {}
    for d in decisions:
        if isinstance(d.get("superseded_by"), str):
            replaced.setdefault(d["superseded_by"], []).append(str(d.get("id")))
    for d in decisions:
        updates, did = d.get("updates"), d.get("id")
        if not (isinstance(updates, list) and all(relative_path_ok(u) for u in updates)):
            continue                             # reported by check_decisions
        for rel in updates:
            path, err = resolve_target(root, rel)
            if err or not path.is_file():
                report.add("records.state.decisions", rel, "warning",
                           f"decision {did} updates {rel}, which is not a file in the project",
                           "fix the path in `updates`, or write the change into that document", kind="convention")
                continue
            if did not in replaced or d.get("status", "active") != "active":
                continue
            try:
                with path.open("rb") as fh:
                    text = fh.read(2_000_000).decode("utf-8", "replace")
            except OSError:
                continue
            if not re.search(rf"(?<![\w.-]){re.escape(str(did))}(?![\w-])", text):
                report.add("records.state.decisions", rel, "warning",
                           f"{rel} does not mention decision {did}, which superseded {', '.join(replaced[did])}",
                           f"update the document to the new decision and cite {did} where the old direction "
                           "was", kind="convention")


def check_issue_retention(report, state, where, state_path):
    """In a git project, an issue id in the last commit's state.json must still be listed: closing an
    issue means `status` resolved or wontfix, never deleting it (its history is the audit trail)."""
    if not shutil.which("git") or not isinstance(state.get("open_issues"), list):
        return
    here = Path(state_path).resolve()
    try:
        shown = git_run(here.parent, "show", f"HEAD:./{here.name}")
    except (OSError, subprocess.SubprocessError):
        return
    if shown.returncode:
        return                                   # not a git project, no commit yet, or state.json not committed
    try:
        before = json.loads(shown.stdout.decode("utf-8"))
    except ValueError:
        return
    ids = lambda data: [i["id"] for i in data.get("open_issues") or []
                        if isinstance(i, dict) and isinstance(i.get("id"), str)] if isinstance(data, dict) else []
    kept = set(ids(state))
    for gone in [i for i in ids(before) if i not in kept]:
        report.add("records.state.issues", where, "defect",
                   f"issue {gone} is in the last commit's state.json but no longer listed",
                   "put it back and close it with `status` resolved or wontfix plus `resolved` (date and how): "
                   "issues are closed, never deleted")


def cmd_check_state(args):
    report = Report(args.state)
    try:
        state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.diagnostics.append(f"cannot read state: {exc}")
        return report.emit("error")
    check_state(report, state, args.state)
    if isinstance(state, dict):
        root = Path(args.root) if args.root else default_root(args.state)
        check_handover(report, state, args.state, root, args.state)
        check_decision_updates(report, state, args.state, root)
        check_issue_retention(report, state, args.state, args.state)
    if isinstance(state, dict) and isinstance(state.get("completed_artifacts"), list):
        root = Path(args.root) if args.root else default_root(args.state)
        check_artifacts(report, state, args.state, root, budget=QUICK_FILE_BUDGET if args.quick else None)
    if isinstance(state, dict) and "build_output" in state:
        root = Path(args.root) if args.root else default_root(args.state)
        check_layout(report, state, args.state, root, args.state)
    return report.finish()


# ---------- evidence ----------

def evidence_problems(rec):
    """Reasons a record cannot be trusted as written (types and formats; nothing on disk is read)."""
    if not isinstance(rec, dict):
        return ["record is not an object"]
    problems = []
    for name in EVIDENCE_FIELDS:
        if name in rec and not isinstance(rec[name], str):
            problems.append(f"`{name}` must be a string, not {type(rec[name]).__name__}")
    if problems:
        return problems
    if rec.get("result") not in RESULTS:
        problems.append(f"result {rec.get('result')!r} outside the vocabulary")
    if rec.get("result") == "passed":
        for name in ("timestamp", "tool_and_version", "method", "evidence_path",
                     "source_revision_or_target_fingerprint"):
            if not rec.get(name, "").strip():
                problems.append(f"passed without `{name}`")
        if rec.get("method") not in EVIDENCE_METHODS:
            problems.append(f"method {rec.get('method')!r} not one of {', '.join(EVIDENCE_METHODS)}")
    identity = rec.get("source_revision_or_target_fingerprint", "")
    if identity and not (SHA_RE.match(identity) or REV_RE.match(identity)):
        problems.append(f"malformed `source_revision_or_target_fingerprint` {identity[:80]!r}: "
                        "expected sha256:<64 hex> or rev:<7-64 hex>")
    stamp = rec.get("timestamp", "")
    if stamp and not TIMESTAMP_RE.match(stamp):
        problems.append(f"malformed `timestamp` {stamp[:40]!r}: expected ISO 8601 with a timezone")
    evidence = rec.get("evidence_path", "")
    if evidence and ("\0" in evidence or "\\" in evidence):
        problems.append("`evidence_path` contains a NUL or backslash")
    if "inputs" in rec:
        problems.extend(input_problems(rec["inputs"]))
    if "mode" in rec and rec["mode"] not in DELIVERY_MODES:
        problems.append(f"mode {str(rec['mode'])[:40]!r} not one of {', '.join(DELIVERY_MODES)}")
    for name in ("sample_scope", "supplied_by"):
        if name in rec and not isinstance(rec[name], str):
            problems.append(f"`{name}` must be a string")
    if "evidence_sha256" in rec and not (isinstance(rec["evidence_sha256"], str) and SHA_RE.match(rec["evidence_sha256"])):
        problems.append("malformed `evidence_sha256`: expected sha256:<64 hex>")
    if "judged" in rec:
        problems.extend(judged_problems(rec["judged"], rec.get("inputs")))
    if "exclusions" in rec:
        excl = rec["exclusions"]
        if not isinstance(excl, list) or not all(relative_path_ok(e) for e in excl):
            problems.append("`exclusions` must be a list of project-relative paths without '..', NUL or backslash")
    if rec.get("check_id", "").startswith(RENDERED_CHECKS) and rec.get("method") != "browser":
        problems.append(f"browser check {rec.get('check_id')!r} recorded with method {rec.get('method')!r}; "
                        "only a browser run can stand for it (use a source.* ID for source review)")
    if rec.get("check_id", "").startswith(JUDGED_CHECKS) and rec.get("method") != "manual":
        problems.append(f"{rec.get('check_id')!r} is a judgement from screenshots and takes method 'manual', not "
                        f"{rec.get('method')!r}; record the measurements as visual.measure")
    if rec.get("result") == "skipped" and not rec.get("skip_reason_when_applicable", "").strip():
        problems.append("skipped without `skip_reason_when_applicable`")
    return problems


def input_problems(inputs):
    """`inputs` is {project-relative path: sha256 fingerprint} for every further file a check consumed."""
    if not isinstance(inputs, dict):
        return ["`inputs` must be an object mapping project-relative paths to sha256 fingerprints"]
    problems = []
    for key, value in inputs.items():
        if not relative_path_ok(key):
            problems.append(f"input path {str(key)[:80]!r} must be project-relative, without '..', NUL or backslash")
        if not isinstance(value, str) or not SHA_RE.match(value):
            problems.append(f"input {str(key)[:80]!r} has malformed fingerprint {str(value)[:80]!r}")
    return problems


JUDGED_KEYS = ("route", "width", "theme", "screenshot")


def judged_problems(judged, inputs):
    """`judged` lists what a manual review looked at: [{route, width, theme, screenshot}], each screenshot a
    project-relative file that is also one of the record's `inputs` (directly or through a glob input), so
    a replaced screenshot makes the review stale (the review is bound to the files it judged)."""
    if not isinstance(judged, list) or not judged:
        return ["`judged` must be a non-empty list of {route, width, theme, screenshot}"]
    inputs = inputs if isinstance(inputs, dict) else {}
    globbed = any(is_glob(k) for k in inputs)
    problems = []
    for item in judged:
        if not isinstance(item, dict) or set(item) != set(JUDGED_KEYS):
            problems.append("each `judged` entry needs exactly route, width, theme and screenshot")
            continue
        if not (isinstance(item["route"], str) and item["route"]) or not isinstance(item["theme"], str) \
                or not item["theme"] or not (isinstance(item["width"], int) and item["width"] > 0):
            problems.append(f"judged entry {str(item)[:80]}: route and theme are text, width a positive whole px")
        shot = item["screenshot"]
        if not relative_path_ok(shot):
            problems.append(f"judged screenshot {str(shot)[:80]!r} must be project-relative")
        elif shot not in inputs and not globbed:
            problems.append(f"judged screenshot {shot} is not one of the record's inputs")
    return problems


def parse_judged(value):
    """`ROUTE,WIDTH,THEME,PATH` (the path last, so it may hold commas) → dict, or a refusal text."""
    parts = value.split(",", 3)
    if len(parts) != 4 or not all(p.strip() for p in parts):
        return None, f"--judged {value!r}: expected ROUTE,WIDTH,THEME,SCREENSHOT (e.g. /,320,light,docs/website/evidence/visual/home-320-light.png)"
    route, width, theme, shot = (p.strip() for p in parts)
    if not width.isdigit() or int(width) <= 0:
        return None, f"--judged {value!r}: width must be whole px"
    return {"route": route, "width": int(width), "theme": theme, "screenshot": shot}, None


def relative_path_ok(rel):
    if not isinstance(rel, str) or not rel or "\0" in rel or "\\" in rel or rel.startswith("/"):
        return False
    return ".." not in rel.split("/")


def is_url(value):
    return value.startswith(("http://", "https://"))


def default_root(record_path):
    """The project root used when --root is not given: the folder above `docs/website/` for a record kept
    there (the standard layout, whose targets are project-relative), else the record's own folder."""
    parent = Path(record_path).resolve().parent
    if parent.name == "website" and parent.parent.name == "docs":
        return parent.parent.parent
    return parent


def root_source(args_root, record_path):
    """How the root was chosen, for gate and status output."""
    if args_root:
        return "--root"
    if default_root(record_path) != Path(record_path).resolve().parent:
        return "inferred: the folder above docs/website/"
    return "default: the record's folder"


def missing_target(root, path, what="target"):
    """The missing-target reason, naming where it was looked for so a wrong root is visible."""
    return (f"{what} no longer exists (looked for {Path(path).absolute()}, root {Path(root).absolute()}); "
            "if the file is there, the root is wrong: run from the project root with --root .")


def resolve_target(root, target):
    p = Path(target)
    p = p if p.is_absolute() else root / p
    real_root = root.resolve()
    try:
        p.resolve().relative_to(real_root)
    except ValueError:
        return None, "target resolves outside the project root"
    return p, None


GLOB_CHARS = ("*", "?", "[")
GLOB_SKIP = (".git", "node_modules", "__pycache__")


def is_glob(target):
    """A file-set target such as `dist/**/*.css`. Its identity is the set of matched contents, not their
    names, so a build that renames hashed files without changing them leaves it current."""
    return isinstance(target, str) and not is_url(target) and any(c in target for c in GLOB_CHARS)


def glob_problem(pattern):
    if not relative_path_ok(pattern):
        return f"file-set target {pattern[:80]!r} must be a project-relative pattern without '..', NUL or backslash"
    return None


def glob_files(root, pattern):
    """Regular files inside the root that `pattern` matches, sorted; symlinks and tool folders are skipped."""
    real = Path(root).resolve()
    out = []
    for p in Path(root).glob(pattern):
        if p.is_symlink() or not p.is_file() or any(part in GLOB_SKIP for part in p.relative_to(root).parts):
            continue
        try:
            p.resolve().relative_to(real)
        except ValueError:
            continue
        out.append(p)
    return sorted(out)


def glob_fingerprint(files):
    h = hashlib.sha256(b"file-set\n")
    for digest in sorted(file_hash(p) for p in files):
        h.update(f"{digest}\n".encode())
    return "sha256:" + h.hexdigest()


def target_present(root, target):
    """True when a local target exists inside the root (a file-set target: matches at least one file)."""
    if is_glob(target):
        return not glob_problem(target) and bool(glob_files(root, target))
    path, err = resolve_target(root, target)
    return not err and (path.exists() or path.is_symlink())


def covers(container, path):
    """True when `path` is `container` or lies inside it (both resolved)."""
    try:
        path.resolve().relative_to(container.resolve())
        return True
    except ValueError:
        return False


def exclusions_within(root, target, given):
    """The `--exclude` values (relative to `root`) that lie inside folder `target`, for helpers that record
    several targets from one command line: a page target simply gets none."""
    target = Path(target)
    if not target.is_dir():
        return []
    picked = []
    for g in given:
        path = Path(g) if Path(g).is_absolute() else Path(root) / g
        if covers(target, path) and path.resolve() != target.resolve():
            picked.append(g)
    return picked


def project_rel(root, path):
    """Project-relative spelling of `path`, keeping its own name where possible (a symlinked input stays
    keyed by the link); falls back to resolved paths when the two spellings differ (/var vs /private/var).
    Containment is checked separately."""
    try:
        return Path(os.path.abspath(path)).relative_to(os.path.abspath(root)).as_posix()
    except ValueError:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()


def evidence_file(root, evidence, digest=None):
    """(result, reason) for a passed record's supporting file; None when it exists and is readable.
    This shows the file is there, not that what it says is true. When `digest` is a list, the file's
    sha256 is appended to it."""
    if is_url(evidence):
        return "unavailable", f"evidence {evidence} is a URL; it cannot be confirmed from this machine"
    path, err = resolve_target(root, evidence)
    if err:
        return "error", "evidence_path resolves outside the project root"
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            return "unavailable", f"evidence_path {evidence} is not a regular file"
        # Nonblocking open also protects against replacement by a FIFO after stat.
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                return "unavailable", f"evidence_path {evidence} is not a regular file"
            if digest is None:
                f.read(1)
            else:
                h = hashlib.sha256()
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
                digest.append("sha256:" + h.hexdigest())
    except IsADirectoryError:
        return "unavailable", f"evidence_path {evidence} is a directory, not a saved output"
    except OSError as exc:
        return "unavailable", f"supporting evidence {evidence} is missing or unreadable ({type(exc).__name__})"
    return None


# The gate also runs from the Stop hook in whatever project is open, and a project's own git config
# can name programs (core.fsmonitor, filter drivers via .gitattributes, textconv, external diff,
# lazy fetches). So git is only asked to read its object database (rev-parse, ls-tree), with those
# settings switched off; the working tree is hashed here, never through git.
GIT_SAFE = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "protocol.allow=never",
            "-c", "core.untrackedCache=false", "--no-optional-locks")
# A partial clone fetches missing objects from its promisor remote, and the repository's own
# protocol.<name>.allow (e.g. ext::, or file:// with remote.*.uploadpack) overrides protocol.allow.
# GIT_ALLOW_PROTOCOL replaces all protocol config (git 2.12+), so no transport can start even on a
# git older than 2.44, which ignores GIT_NO_LAZY_FETCH.
GIT_ENV = {"GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": "none", "GIT_TERMINAL_PROMPT": "0",
           "GIT_PAGER": "cat", "GIT_CONFIG_NOSYSTEM": "1"}


def git_run(root, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_ENV)
    return subprocess.run(["git", *GIT_SAFE, "-C", str(root), *args], capture_output=True,
                          stdin=subprocess.DEVNULL, env=env, timeout=GIT_TIMEOUT)


def blob_id(path, algo):
    """Git's object id for `path` as stored without filters (a symlink stores its link text)."""
    data = os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
    h = hashlib.new(algo)
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def worktree_files(path, top):
    """{repo-relative path: Path} for every file and symlink at or under `path`, skipping .git."""
    if path.is_symlink() or not path.is_dir():
        return {path.relative_to(top).as_posix(): path}
    found = {}
    for dirpath, dirnames, filenames in os.walk(path):
        here = Path(dirpath)
        for d in list(dirnames):
            if d == ".git" or (here / d).is_symlink():
                dirnames.remove(d)
                if d != ".git":
                    filenames.append(d)
        for name in filenames:
            found[(here / name).relative_to(top).as_posix()] = here / name
    return found


def verify_revision(root, rev, path):
    """(result, reason): `passed` only when `path` in the working tree is exactly its content at `rev`
    (same files, same bytes). Extra or missing files, or content git stores through a filter, are
    `stale`; anything git cannot attest (no git, unknown revision, nothing tracked there) is `unavailable`."""
    if not shutil.which("git"):
        return "unavailable", f"rev:{rev} cannot be verified: git is not installed"
    try:
        top = git_run(root, "rev-parse", "--show-toplevel")
        if top.returncode or not top.stdout.strip():
            return "unavailable", f"rev:{rev} cannot be verified: the project is not a git work tree"
        commit = git_run(root, "rev-parse", "--verify", "--quiet", "--end-of-options", rev + "^{commit}")
        if commit.returncode:
            return "unavailable", f"rev:{rev} is not a commit in this repository"
        oid = commit.stdout.decode("ascii", "replace").strip()
        tree = git_run(root, "ls-tree", "-r", "-z", "--full-tree", oid)
        if tree.returncode:
            return "unavailable", f"rev:{rev} cannot be verified: git ls-tree exited {tree.returncode}"
    except (OSError, subprocess.SubprocessError) as exc:
        return "unavailable", f"rev:{rev} cannot be verified: {type(exc).__name__}"
    toplevel = Path(os.fsdecode(top.stdout.strip())).resolve()
    if not path.exists() and not path.is_symlink():
        return "stale", missing_target(root, path)
    target = path.parent.resolve() / path.name  # parents resolved; a symlinked target stays a symlink
    try:
        rel = target.relative_to(toplevel).as_posix()
    except ValueError:
        return "unavailable", f"rev:{rev} cannot cover the target: it lies outside the git work tree"
    algo = "sha256" if len(oid) == 64 else "sha1"
    expected = {}
    for entry in tree.stdout.split(b"\0"):
        if not entry:
            continue
        meta, _, name = entry.partition(b"\t")
        mode, kind, blob = meta.decode("ascii", "replace").split(" ")
        name = os.fsdecode(name)
        if rel == "." or name == rel or name.startswith(rel + "/"):
            if kind != "blob":
                return "unavailable", f"rev:{rev} cannot attest {name}: it is a {kind}, not a file"
            expected[name] = (mode, blob)
    if not expected:
        return "unavailable", f"rev:{rev} cannot cover the target: that commit has no files there"
    on_disk = worktree_files(target, toplevel)
    extra = sorted(set(on_disk) - set(expected))
    if extra:
        return "stale", f"the target has files that rev:{rev} does not contain ({extra[0]})"
    missing = sorted(set(expected) - set(on_disk))
    if missing:
        return "stale", f"files from rev:{rev} are missing from the target ({missing[0]})"
    for name, (mode, blob) in sorted(expected.items()):
        file = on_disk[name]
        if (mode == "120000") != file.is_symlink():
            return "stale", f"{name} changed type since rev:{rev}"
        if not file.is_symlink() and not file.is_file():  # a FIFO or device: never open it
            return "stale", f"{name} is no longer a regular file"
        try:
            if blob_id(file, algo) != blob:
                return "stale", f"the target differs from rev:{rev} in the working tree ({name})"
        except OSError as exc:
            return "unavailable", f"rev:{rev} cannot be verified: {name} is unreadable ({type(exc).__name__})"
    return "passed", ""


def currency(root, rec, vpath):
    """(result, reason) for a well-formed record, or None when it is still current and supported.
    Checks the target identity, every recorded input, and (for a pass) the supporting file."""
    target = rec.get("target", "")
    passed = rec.get("result") == "passed"
    inputs = rec.get("inputs") or {}
    vfile = vpath.resolve()
    evidence = None
    if passed and rec.get("evidence_path") and not is_url(rec["evidence_path"]):
        evidence, err = resolve_target(root, rec["evidence_path"])
        if err:
            return "error", "evidence_path resolves outside the project root"
    covered, files = [], None
    if is_url(target):
        if not inputs:
            return "unavailable", ("a URL target cannot be shown current from this machine; "
                                   "record the local snapshot it served with --input")
    elif is_glob(target):
        problem = glob_problem(target)
        if problem:
            return "error", problem
        if rec.get("exclusions"):
            return "error", "exclusions need a folder target"
        files = glob_files(root, target)
        if not files:
            return "error", (f"file-set target {target} matches no files (root {Path(root).absolute()}); if the "
                             "build is there, the root is wrong: run from the project root with --root .")
        resolved = {f.resolve() for f in files}
        if vfile in resolved or (evidence is not None and evidence.resolve() in resolved):
            return "error", f"file-set target {target} matches its own verification or evidence file"
    else:
        path, err = resolve_target(root, target)
        if err:
            return "error", err
        if not path.exists() and not path.is_symlink():
            return "error", missing_target(root, path)
        covered.append(("target", path))
    excluded, skip = [], []
    if rec.get("exclusions"):
        if is_url(target) or not covered[0][1].is_dir():
            return "error", "exclusions need a folder target"
        if not SHA_RE.match(rec.get("source_revision_or_target_fingerprint", "")):
            return "error", "exclusions need a sha256 target identity (a rev: identity covers every file)"
        top = covered[0][1].resolve()
        for given in rec["exclusions"]:
            path, err = resolve_target(root, given)
            if err:
                return "error", f"exclusion {given} resolves outside the project root"
            if not covers(top, path) or path.resolve() == top:
                return "error", f"exclusion {given} must lie inside the target folder and not be the target"
            excluded.append(path)
            skip.append(path.resolve().relative_to(top).as_posix())
    input_sets = {}
    for rel in sorted(inputs):
        if is_glob(rel):
            if glob_problem(rel):
                return "error", f"input {rel}: " + glob_problem(rel)
            input_sets[rel] = glob_files(root, rel)
            resolved = {f.resolve() for f in input_sets[rel]}
            if vfile in resolved or (evidence is not None and evidence.resolve() in resolved):
                return "error", f"file-set input {rel} matches its own verification or evidence file"
            continue
        path, err = resolve_target(root, rel)
        if err:
            return "error", f"input {rel} resolves outside the project root"
        covered.append((f"input {rel}", path))
    fix = ("; build into its own folder such as site/, record a narrower target, or exclude the records "
           "folder with --exclude (e.g. --exclude docs/website)")
    for label, path in covered:
        spared = label == "target" and excluded
        if covers(path, vfile) and not (spared and any(covers(e, vfile) for e in excluded)):
            return "error", f"{label} contains the verification file; its fingerprint would cover its own records" + fix
        if evidence is not None and covers(path, evidence) \
                and not (spared and any(covers(e, evidence) for e in excluded)):
            return "error", f"{label} contains the evidence file; its fingerprint would cover its own evidence" + fix
    if files is not None:
        identity = rec.get("source_revision_or_target_fingerprint", "")
        if SHA_RE.match(identity):
            if identity != glob_fingerprint(files):
                return "stale", "the matched files changed since the evidence was recorded"
        elif passed:
            return "error", "a file-set target is identified by its sha256 fingerprint, not a revision"
    elif not is_url(target):
        identity = rec.get("source_revision_or_target_fingerprint", "")
        path = covered[0][1]
        if SHA_RE.match(identity):
            if identity != fingerprint(path, skip):
                return "stale", "target changed since the evidence was recorded"
        elif REV_RE.match(identity):
            if passed:
                result, reason = verify_revision(root, REV_RE.match(identity).group(1), path)
                if result != "passed":
                    return result, reason
        elif passed:
            return "error", "passed without a target identity"
    for rel in sorted(inputs):
        if rel in input_sets:
            if not input_sets[rel]:
                return "stale", f"file-set input {rel} matches no files any more"
            if inputs[rel] != glob_fingerprint(input_sets[rel]):
                return "stale", f"the files of input {rel} changed since the evidence was recorded"
            continue
        path = root / rel
        if not path.exists() and not path.is_symlink():
            return "stale", missing_target(root, path, f"input {rel}")
        if inputs[rel] != fingerprint(path):
            return "stale", f"input {rel} changed since the evidence was recorded"
    if passed and rec.get("check_id", "").startswith(MULTI_INPUT_CHECKS):
        if "inputs" not in rec:
            return "stale", ("recorded without its dependency fingerprints (no `inputs`), so it cannot be "
                             "shown current; re-run the check and record it with --input")
        if rec["check_id"].startswith(RENDERED_CHECKS) and not inputs and not is_url(target) \
                and files is None and not covered[0][1].is_dir():
            return "stale", ("browser evidence bound to one file only; record the build snapshot "
                             "(or the page's linked files) with --input")
    if passed:
        return evidence_file(root, rec["evidence_path"])
    return None


class Malformed(ValueError):
    pass


def load_verification(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    required, records, waivers = data["required_checks"], data.get("records", []), data.get("waivers", [])
    if not isinstance(required, list) or not isinstance(records, list) or not isinstance(waivers, list):
        raise ValueError("required_checks, records and waivers must be lists")
    if not isinstance(data.get("requirement_history", []), list):
        raise ValueError("requirement_history must be a list")
    if not isinstance(data.get("runs_in_progress", []), list):
        raise ValueError("runs_in_progress must be a list")
    return data


def target_absent(root, target):
    """True when a local target resolves inside the root and nothing (not even a symlink) is there."""
    if not isinstance(target, str) or not target or is_url(target):
        return False
    if is_glob(target):
        return not glob_problem(target) and not glob_files(root, target)
    path, err = resolve_target(root, target)
    return not err and not (path.exists() or path.is_symlink())


def retired_reason(retired):
    reason = f"retired {retired.get('timestamp', '')} because the target no longer exists: {retired.get('reason', '')}"
    if retired.get("replaced_by"):
        reason += f"; replaced by {retired['replaced_by']}"
    return reason + "; not assessed, never passed (it is required again if the target returns)"


def applies(rec, mode):
    """A record counts for a delivery mode when it names that mode or none (records before 0.1.0-rc.3)."""
    return isinstance(rec, dict) and rec.get("mode") in (None, mode)


def pair(rec):
    return (rec.get("check_id"), rec.get("target"))


def by_pair(records):
    """{pair: [records in appended order]}, built once per evaluation so lookups need no scan."""
    out = {}
    for rec in records:
        if isinstance(rec, dict):
            out.setdefault(pair(rec), []).append(rec)
    return out


def reused_evidence(records, rec, index=None):
    """True when a passed record cites evidence byte-identical to what an earlier record of the same
    check cited for a different target state: the pass was copied forward, not produced by a new run."""
    digest = rec.get("evidence_sha256")
    if not digest:
        return False
    state = (rec.get("source_revision_or_target_fingerprint"), rec.get("inputs") or {})
    same = index.get(pair(rec), []) if index is not None else records
    for earlier in same:
        if earlier is rec:
            return False
        if isinstance(earlier, dict) and pair(earlier) == pair(rec) and earlier.get("evidence_sha256") == digest \
                and (earlier.get("source_revision_or_target_fingerprint"), earlier.get("inputs") or {}) != state:
            return True
    return False


WAIVER_SCOPES = ("mockup", "production", "launch")
STAGES = ("launch",)   # a stage adds checks to the production gate; it is not a delivery mode


def waiver_date(value):
    """The date part of `expires` (YYYY-MM-DD or a full timestamp), or None when it is not a date."""
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def waiver_line(waivers, key, level, today=None):
    """How the waivers on `key` decide it at gate level `level`: (result, reason, note) or None when no
    waiver counts here. A waiver needs `reason` and `decided_by`. `scope` lists the levels it counts in
    (absent: every level); past `expires` it is stale, so it has to be renewed with the user or the
    check run. The newest matching waiver decides."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    found = [w for w in waivers if isinstance(w, dict) and (w.get("check_id"), w.get("target")) == key
             and w.get("reason") and w.get("decided_by")]
    if not found:
        return None
    w = found[-1]
    scope = w.get("scope")
    if isinstance(scope, list) and scope and level not in scope:
        return None
    who = f"decided by {w['decided_by']}" + (f", owner {w['owner']}" if w.get("owner") else "")
    if "expires" in w:
        until = waiver_date(w["expires"])
        if until is None:
            return "error", f"waiver `expires` {str(w['expires'])[:30]!r} is not a date (YYYY-MM-DD)", None
        if today > until:
            return "stale", (f"waiver expired {until.isoformat()} ({who}): renew it with the user "
                             "(`waive`) or run the check"), None
    legacy = not any(k in w for k in ("owner", "expires", "scope"))
    return "waived", f"waiver recorded ({who})" + (f", until {w['expires']}" if w.get("expires") else ""), \
        ("legacy waiver: no owner, expiry or scope; record it again with `waive`" if legacy else None)


def marker_applies(marker, check_id, target, mode):
    return isinstance(marker, dict) and (marker.get("check_id"), marker.get("target")) == (check_id, target) \
        and (not marker.get("mode") or not mode or marker["mode"] == mode)


def open_run(data, key, mode):
    """The newest `runs_in_progress` marker on `key` that applies to `mode`, or None."""
    markers = data.get("runs_in_progress") if isinstance(data.get("runs_in_progress"), list) else []
    found = [m for m in markers if marker_applies(m, key[0], key[1], mode)]
    return found[-1] if found else None


def evaluate(data, root, vpath, mode, stage=None):
    """(checks, optional, not_assessed) for one delivery mode. For each required check the newest record
    that counts for the mode decides, so a mock-up run never replaces production evidence."""
    required, records, waivers = data["required_checks"], data.get("records", []), data.get("waivers", [])
    level = "launch" if stage == "launch" else mode
    newest = {}
    for rec in records:
        if applies(rec, mode):
            newest[pair(rec)] = rec   # appended order: last wins
    index = by_pair(records)
    checks, not_assessed = [], []
    for req in required:
        if not isinstance(req, dict) or not isinstance(req.get("check_id"), str) \
                or not isinstance(req.get("target"), str) or not req["check_id"] or not req["target"]:
            raise Malformed(f"malformed required check: {req!r}")
        modes = req.get("modes", list(DELIVERY_MODES))
        if not isinstance(modes, list) or not modes or any(m not in DELIVERY_MODES for m in modes):
            raise Malformed(f"required check {req['check_id']} {req['target']}: `modes` must list "
                            f"{' and/or '.join(DELIVERY_MODES)}")
        key = (req["check_id"], req["target"])
        retired = req.get("retired") if isinstance(req.get("retired"), dict) else None
        if retired and target_absent(root, key[1]):
            not_assessed.append({"check_id": key[0], "target": key[1], "modes": modes,
                                 "reason": retired_reason(retired)})
            continue
        if mode not in modes:
            not_assessed.append({"check_id": key[0], "target": key[1], "modes": modes,
                                 "reason": f"not part of the {mode} criteria; required for {', '.join(modes)}"})
            continue
        stages = req.get("stages") or []
        if not isinstance(stages, list) or any(x not in STAGES for x in stages):
            raise Malformed(f"required check {req['check_id']} {req['target']}: `stages` may only list "
                            f"{', '.join(STAGES)}")
        if "launch" in stages and stage != "launch":
            not_assessed.append({"check_id": key[0], "target": key[1], "modes": modes, "stages": stages,
                                 "reason": "launch-stage check: assessed by the production gate with --stage launch"})
            continue
        run_open = open_run(data, key, mode)
        if run_open is not None:
            checks.append({"check_id": key[0], "target": key[1], "result": "error",
                           "reason": f"a run began {run_open.get('started', '?')} and was never recorded (still "
                                     "running, or it crashed): record its result, or `begin --cancel` and re-run"})
            continue
        waiver = waiver_line(waivers, key, level)
        if waiver is not None:
            line = {"check_id": key[0], "target": key[1], "result": waiver[0], "reason": waiver[1]}
            if waiver[2]:
                line["waiver_note"] = waiver[2]
            checks.append(line)
            continue
        rec = newest.get(key)
        line = {"check_id": key[0], "target": key[1]}
        if rec is None:
            result, reason = "unavailable", "no evidence record"
        else:
            problems = evidence_problems(rec)
            result = "error" if problems else rec["result"]
            reason = "; ".join(problems) or rec.get("observed_finding", "")
            if not problems:
                found = currency(root, rec, vpath)
                if found:
                    result, reason = found
                elif result == "passed" and reused_evidence(records, rec, index):
                    result, reason = "stale", ("evidence reused: the cited file is unchanged from an earlier "
                                               "record of this check made on a different target state, so no new "
                                               "run is shown; re-run the check and record its new output")
                if result == "skipped":
                    why = rec.get("skip_reason_when_applicable", "")
                    reason = "required check skipped (not run); counts as unmet" + (f": {why}" if why else "")
                if result == "passed" and mode == "production" and key[0] in SUBMISSION_CHECKS \
                        and rec.get("method") not in ("browser", "manual"):
                    result, reason = "unavailable", (
                        f"a {rec.get('method') or 'static'} pass does not show a working submission; production "
                        "needs a browser or manual submission record against a local stub or the provider's test "
                        "mode (an endpoint in source is not enough)")
            line.update({"mode": rec.get("mode", "any"), "method": rec.get("method", "")})
            for name in ("limitations", "sample_scope", "exclusions"):
                if rec.get(name):
                    line[name] = rec[name]
        if retired:
            line["reactivated"] = (f"retired {retired.get('timestamp', '')}, but the target exists again, "
                                   "so it is required as before")
        line.update({"result": result, "reason": reason})
        checks.append(line)
    listed = {(c["check_id"], c["target"]) for c in checks + not_assessed}
    removed = {}
    for entry in data.get("requirement_history", []) if isinstance(data.get("requirement_history"), list) else []:
        if isinstance(entry, dict):
            removed[(entry.get("check_id"), entry.get("target"))] = entry if entry.get("action") == "remove" else None
    for key, entry in removed.items():
        if entry and key not in listed:   # a removed requirement is shown as not assessed, never dropped silently
            not_assessed.append({"check_id": key[0], "target": key[1], "modes": [],
                                 "reason": f"requirement removed {entry.get('timestamp', '')} by "
                                           f"{entry.get('decided_by') or 'decision ' + str(entry.get('decision', ''))}"
                                           f": {entry.get('reason', '')}"})
            listed.add(key)
    optional = [{"check_id": r.get("check_id"), "target": r.get("target"), "result": r.get("result")}
                for k, r in newest.items() if r.get("required_or_optional") == "optional" and k not in listed]
    return checks, optional, not_assessed


def overall_of(report, checks):
    for c in checks:
        if c["result"] not in ("passed", "waived"):
            report.add(c["check_id"], c["target"], "defect", f"{c['result']}: {c['reason']}",
                       "run the check against the current target and record the result")
    present = {c["result"] for c in checks}
    overall = next((r for r in OVERALL_ORDER if r in present), "passed")
    if not checks:
        report.diagnostics.append("no required checks declared for this mode")
        overall = "unavailable"
    return overall


def open_verification(report, args):
    """(data, root, vpath) or None after reporting why the file cannot be used."""
    vpath = Path(args.verification)
    try:
        data = load_verification(vpath)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.diagnostics.append(f"cannot read verification record: {exc}")
        return None
    return data, (Path(args.root) if args.root else default_root(vpath)), vpath


def root_diagnostics(report, checks, root, vpath):
    """When targets are missing, say whether they exist under another likely root (the project root
    above docs/website/, the working directory, the record's folder), so a wrong --root is named as
    such instead of reading as deleted pages."""
    missing = [c["target"] for c in checks if "the root is wrong" in c.get("reason", "")
               and c["reason"].startswith("target ") and not is_url(c["target"])]
    if not missing:
        return
    local = sum(1 for c in checks if not is_url(c["target"]))
    here = root.resolve()
    for other in (default_root(vpath), Path.cwd().resolve(), vpath.resolve().parent):
        if other == here:
            continue
        found = sum(1 for t in missing if (other / t).exists())
        if found:
            report.diagnostics.append(
                f"{len(missing)} of {local} local targets are missing under root {here}, but {found} of them "
                f"exist under {other}: rerun with --root {shlex.quote(str(other))} (targets are relative to "
                "the project root)")
            return
    if len(missing) == local:
        report.diagnostics.append(f"every local target ({local}) is missing under root {here}; check --root "
                                  "before treating the pages as deleted")


def root_fields(args, root):
    return {"root": str(root.absolute()), "root_source": root_source(args.root, args.verification)}


def coverage(checks):
    """How the required lines were shown: passed/total per evidence method, plus waived and no-record counts.

    Issue lines (`issue.<id>`) are not checks and are left out. Any other method value counts as "unknown"."""
    out = {m: {"passed": 0, "total": 0} for m in EVIDENCE_METHODS}
    out.update({"waived": 0, "no_record": 0})
    for c in checks:
        if str(c.get("check_id", "")).startswith("issue."):
            continue
        if c.get("result") == "waived":
            out["waived"] += 1
        elif "method" not in c:
            out["no_record"] += 1
        else:
            method = c["method"] if c["method"] in EVIDENCE_METHODS else "unknown"   # never free text
            slot = out.setdefault(method, {"passed": 0, "total": 0})
            slot["total"] += 1
            slot["passed"] += c.get("result") == "passed"
    return {k: v for k, v in out.items() if (v["total"] if isinstance(v, dict) else v)}


def cmd_gate(args):
    report = Report(args.verification)
    if getattr(args, "stage", None) and args.mode != "production":
        report.diagnostics.append("--stage launch adds checks to the production gate; use it with --mode production")
        return report.emit("error")
    opened = open_verification(report, args)
    if opened is None:
        return report.emit("error")
    try:
        checks, optional, not_assessed = evaluate(*opened, args.mode, stage=args.stage)
    except Malformed as exc:
        report.diagnostics.append(str(exc))
        return report.emit("error")
    state, state_path = gate_state(args, opened[2])
    if isinstance(state_path, str):
        report.diagnostics.append(f"state record unreadable, blocking issues not read: {state_path}")
    level = "launch" if getattr(args, "stage", None) == "launch" else args.mode
    for issue in blocking_issues(state, level):
        checks.append({"check_id": f"issue.{issue.get('id', '?')}", "target": "state.json", "result": "failed",
                       "reason": f"open issue blocks the {level} gate: {str(issue.get('issue', ''))[:160]}"})
    overall = overall_of(report, checks)
    root_diagnostics(report, [c for c in checks if not c["check_id"].startswith("issue.")], opened[1], opened[2])
    # The gate ran: only a fresh overall pass exits 0; every other result is "not passed".
    return report.emit(overall, {"mode": args.mode, **({"stage": args.stage} if args.stage else {}),
                                 **root_fields(args, opened[1]), "checks": checks, "coverage": coverage(checks),
                                 "optional": optional, "not_assessed": not_assessed, "criteria_note": CRITERIA_NOTE},
                       code=0 if overall == "passed" else 1)


# ---------- current view and history ----------

RERUN_HOW = {
    "sw_wp_theme_check": "probe the theme again in a local runtime, then sw_wp_theme_check.py --probe with --record",
    "browser": "repeat the browser checks on the current build and record each with its --input files",
    "manual": "repeat the review on the current build and record new notes",
}
HELPER_SLUGS = {"sw_site_check": "site-check", "sw_design_check": "design-check",
                "sw_wp_theme_check": "wp-theme-check", "browser": "browser", "manual": "manual"}
SCRIPTS = Path(__file__).resolve().parent
MAX_EVIDENCE_READ = 2_000_000


def cited_paths(data):
    return {r.get("evidence_path") for r in data.get("records", []) if isinstance(r, dict) and r.get("evidence_path")}


def fresh_evidence_path(root, tool, taken=(), folder=False):
    """A project-relative evidence destination that does not exist yet and no record cites:
    docs/website/evidence/<tool>-<UTC stamp>[-N].json (a folder for browser and manual evidence)."""
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = f"docs/website/evidence/{HELPER_SLUGS.get(tool, re.sub(r'[^A-Za-z0-9_-]+', '-', tool) or 'check')}-{stamp}"
    n, suffix = 1, "" if folder else ".json"
    rel = base + suffix
    while rel in taken or (Path(root) / rel).exists() or os.path.lexists(Path(root) / rel):
        n += 1
        rel = f"{base}-{n}{suffix}"
    return rel


def cited_evidence_problem(verification, root, evidence_out, tool):
    """Why a helper must not write `evidence_out` (an existing file that a record already cites), or None.
    Overwriting it would change what earlier records point to and break their evidence_sha256."""
    path = Path(evidence_out)
    if not os.path.lexists(path):
        return None
    try:
        data = json.loads(Path(verification).read_text(encoding="utf-8"))
        cited = cited_paths(data) if isinstance(data, dict) and isinstance(data.get("records"), list) else set()
    except (OSError, ValueError):
        return None   # an unreadable verification file is reported when the first record is written
    try:
        rel = project_rel(root, path)
    except ValueError:
        rel = str(path)
    if rel not in cited:
        return None
    fresh = fresh_evidence_path(root, tool, cited)
    return (f"--evidence-out {evidence_out} already holds evidence that records in {verification} cite; "
            f"writing over it would detach those records from what they observed. Write this run to a new "
            f"file, e.g. --evidence-out {shlex.quote(fresh)}")


def saved_output(root, evidence_path):
    """The JSON object a helper saved at `evidence_path` (inside the root, size-bounded), or {}."""
    if not isinstance(evidence_path, str) or not evidence_path or is_url(evidence_path):
        return {}
    path, err = resolve_target(root, evidence_path)
    try:
        if err or not path.is_file() or path.stat().st_size > MAX_EVIDENCE_READ:
            return {}
        out = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return out if isinstance(out, dict) else {}


def existing_dir(root, given):
    if not isinstance(given, str) or not given or is_url(given):
        return None
    path, err = resolve_target(root, given)
    if err or not path.is_dir():
        return None
    return project_rel(root, path) or "."


CLASS_NAME = re.compile(r"-?[A-Za-z_][A-Za-z0-9_-]{0,63}")


RERUN_PAGE_LIMIT = 10


def page_scope(root, site, items):
    """Site-relative pages for `--page` when every item is a page check on an existing .html file inside the
    site folder (or `site.404` on the site folder, which a `--page` run checks when `--checks` names it) and
    there are at most RERUN_PAGE_LIMIT pages; otherwise [] (the full run)."""
    if not site:
        return []
    base = (root / site).resolve()
    pages = set()
    for item in items:
        target = item.get("target")
        if item.get("check_id") == "site.404" and isinstance(target, str) \
                and not resolve_target(root, target)[1] and resolve_target(root, target)[0].resolve() == base:
            continue
        if str(item.get("check_id", "")).startswith("site.") or not isinstance(target, str) \
                or not target.endswith(".html"):
            return []
        path, err = resolve_target(root, target)
        if err or not path.is_file():
            return []
        try:
            pages.add(path.resolve().relative_to(base).as_posix())
        except ValueError:
            return []
    return sorted(pages) if len(pages) <= RERUN_PAGE_LIMIT else []


def rerun_hint(tool, items, data, root, vpath, mode, taken):
    """One rerun suggestion: a quoted command (run from the project root) that writes a new evidence file,
    so the records being replaced stay linked to the files they cite."""
    checks = sorted({i["check_id"] for i in items})
    hint = {"tool": tool, "checks": [f"{i['check_id']} {i['target']} ({i['result']})" for i in items]}
    evidence_out = fresh_evidence_path(root, tool, taken, folder=tool in ("browser", "manual"))
    taken.add(evidence_out)
    hint["evidence_out"] = evidence_out
    vrel = project_rel(root, vpath)
    records = [r for r in data.get("records", []) if isinstance(r, dict) and tool_of(r) == tool]
    argv = None
    saved = [saved_output(root, i.get("evidence_path")) for i in items]
    if tool == "sw_site_check":
        site = next((existing_dir(root, r.get("target")) for r in reversed(records) if r.get("check_id") == "site.404"
                     and existing_dir(root, r.get("target"))), None) \
            or next((existing_dir(root, o.get("target")) for o in saved if existing_dir(root, o.get("target"))), None)
        argv = ["python3", str(SCRIPTS / "sw_site_check.py"), site or "SITE_DIR", "--checks", ",".join(checks)]
        pages = page_scope(root, site, items)
        for rel in pages:      # only the pages that changed; a site-level check keeps the full run
            argv += ["--page", rel]
        if pages:
            hint["pages"] = pages
        classes = sorted({c for o in saved for c in (o.get("mockup_classes") or [])
                          if isinstance(c, str) and CLASS_NAME.fullmatch(c)})
        for name in classes:   # the rerun judges with the same project markers as the run it replaces
            argv += ["--mockup-class", name]
        if not site:
            hint["fill_in"] = "SITE_DIR: the built site folder"
    elif tool == "sw_design_check":
        run = next((o["run"] for o in saved if isinstance(o.get("run"), dict)), {})
        argv = ["python3", str(SCRIPTS / "sw_design_check.py")]
        theme, site = existing_dir(root, run.get("theme")), existing_dir(root, run.get("site"))
        if theme:
            argv += ["--theme", theme]
        else:
            argv += ["--site", site or "SITE_DIR"]
            if not site:
                hint["fill_in"] = "SITE_DIR: the built site folder (or --theme THEME_DIR for a block theme)"
        argv += ["--records", existing_dir(root, run.get("records")) or "docs/website", "--root", ".",
                 "--checks", ",".join(checks)]
    if argv is None:
        hint["how"] = RERUN_HOW.get(tool, "re-run the tool named in tool_and_version") + \
            f"; save the new evidence under {evidence_out}, not over the files the old records cite"
        return hint
    if mode == "production":
        argv.append("--release")
    if tool == "sw_site_check":
        argv += ["--root", "."]
    argv += ["--record", vrel, "--evidence-out", evidence_out]
    hint.update({"argv": argv, "run_from": str(root), "command": shlex.join(argv),
                 "how": "run `command` from the project root (run_from); it writes a new evidence file and "
                        "leaves the earlier records linked to theirs"})
    return hint


def tool_of(rec):
    if rec.get("method") in ("browser", "manual"):
        return rec["method"]
    name = str(rec.get("tool_and_version", "")).split(" ")[0]
    return name or "unknown"


def current_indices(records):
    """Indices of records that decide some (check, target) pair in some delivery mode."""
    keep = set()
    for mode in DELIVERY_MODES:
        newest = {}
        for i, rec in enumerate(records):
            if applies(rec, mode):
                newest[pair(rec)] = i
        keep |= set(newest.values())
    return keep


def orphaned_pairs(data, root):
    """{pair: why} for recorded pairs nothing will check again: the target is gone, or the newest record
    says the check is required but required_checks no longer lists it."""
    required = {(r.get("check_id"), r.get("target")) for r in data["required_checks"] if isinstance(r, dict)}
    latest = {}
    for rec in data.get("records", []):
        if isinstance(rec, dict):
            latest[pair(rec)] = rec
    out = {}
    for key, rec in latest.items():
        target = key[1]
        if isinstance(target, str) and target and not is_url(target):
            if is_glob(target):
                gone = bool(glob_problem(target)) or not glob_files(root, target)
            else:
                path, err = resolve_target(root, target)
                gone = bool(err) or not (path.exists() or path.is_symlink())
            if gone:
                out[key] = "target no longer exists"
                continue
        if key not in required and rec.get("required_or_optional") == "required":
            out[key] = "recorded as required but not listed in required_checks"
    return out


def newest_record(records, check, mode):
    """The newest record of the check's pair that counts for `mode`, or None."""
    for rec in reversed(records):
        if isinstance(rec, dict) and pair(rec) == (check["check_id"], check["target"]) and applies(rec, mode):
            return rec
    return None


def cmd_status(args):
    report = Report(args.verification)
    if getattr(args, "stage", None) and args.mode != "production":
        report.diagnostics.append("--stage launch adds checks to the production gate; use it with --mode production")
        return report.emit("error")
    opened = open_verification(report, args)
    if opened is None:
        return report.emit("error")
    data, root, vpath = opened
    try:
        checks, optional, not_assessed = evaluate(data, root, vpath, args.mode, stage=args.stage)
    except Malformed as exc:
        report.diagnostics.append(str(exc))
        return report.emit("error")
    overall = overall_of(report, checks)
    root_diagnostics(report, checks, root, vpath)
    for c in checks:
        rec = newest_record(data.get("records", []), c, args.mode)
        if c["check_id"] == "visual.review" and c["result"] == "passed" and rec is not None and not rec.get("judged"):
            report.add(c["check_id"], c["target"], "warning",
                       "this visual.review pass names no judged screenshots (written before 0.3.0), so nothing "
                       "shows which shots it rests on",
                       "on the next review record each screenshot with --judged ROUTE,WIDTH,THEME,PATH and "
                       "pass the same files as --input", kind="convention")
    for c in checks:
        if c.get("waiver_note"):
            report.add(c["check_id"], c["target"], "warning", c["waiver_note"],
                       "ask the user to confirm it with `waive` (owner, --expires, --scope)", kind="convention")
    records = data.get("records", [])
    history, newest, any_mode = {}, {}, {}
    for rec in records:
        if isinstance(rec, dict):
            history[pair(rec)] = history.get(pair(rec), 0) + 1
            any_mode[pair(rec)] = rec
            if applies(rec, args.mode):
                newest[pair(rec)] = rec
    rerun, last_change, weakenings = {}, {}, {}
    for entry in data.get("requirement_history", []):
        if isinstance(entry, dict):
            last_change[(entry.get("check_id"), entry.get("target"))] = entry
            if entry.get("weakens"):
                # every weakening, grouped by what authorised it, so the owner can audit the list in one place
                basis = (f"decision {entry['decision']}" if entry.get("decision") else
                         f"decided_by {entry['decided_by']}" if entry.get("decided_by") else "no decider recorded")
                weakenings.setdefault(basis, []).append(
                    {k: entry.get(k) for k in ("timestamp", "check_id", "target", "action", "reason")})
    for item in not_assessed:
        if (item["check_id"], item["target"]) in last_change:
            item["requirement_change"] = last_change[(item["check_id"], item["target"])]
    for c in checks:
        rec = newest.get((c["check_id"], c["target"]))
        c["history"] = history.get((c["check_id"], c["target"]), 0)
        if rec is not None:
            c.update({"timestamp": rec.get("timestamp", ""), "evidence_path": rec.get("evidence_path", "")})
        change = last_change.get((c["check_id"], c["target"]))
        if change:
            c["requirement_change"] = change
        if c["result"] not in ("passed", "waived"):
            # with no record for this mode, the newest one in another mode still names the tool that collects it
            source = rec if rec is not None else any_mode.get((c["check_id"], c["target"]))
            tool = tool_of(source) if source is not None else "no record yet"
            rerun.setdefault(tool, []).append({**c, "evidence_path": source.get("evidence_path", "") if source else ""})
    keep = current_indices(records)
    superseded = [i for i, rec in enumerate(records) if isinstance(rec, dict) and i not in keep]
    orphans = orphaned_pairs(data, root)
    taken = cited_paths(data)
    return report.emit(overall, {
        "mode": args.mode, **root_fields(args, root), "checks": checks, "coverage": coverage(checks),
        "rerun": [rerun_hint(t, items, data, root, vpath, args.mode, taken) for t, items in sorted(rerun.items())],
        "criteria_note": CRITERIA_NOTE,
        "not_assessed": not_assessed, "optional": optional,
        "history": {"records": len(records), "current": len(keep), "superseded": len(superseded),
                    "compact": "sw_records.py compact moves superseded records to an archive"},
        "orphaned": [{"check_id": k[0], "target": k[1], "why": why} for k, why in sorted(orphans.items(), key=str)],
        "weakenings": [{"basis": b, "changes": items} for b, items in sorted(weakenings.items())],
        "recurring_warnings": recurring_list(data),
    }, code=0 if overall == "passed" else 1)


def gate_shape(result):
    """What a gate decides, without reason text: (check, target, result) for every line it reports."""
    checks, optional, not_assessed = result
    return (sorted((c["check_id"], c["target"], c["result"]) for c in checks),
            sorted((c["check_id"], c["target"], str(c.get("result"))) for c in optional),
            sorted((c["check_id"], c["target"]) for c in not_assessed))


def cmd_compact(args):
    """Move records no gate reads, verbatim, to an archive: superseded records, and every record of a pair
    that is no longer required. The newest record for every required check and mode, client-supplied and
    malformed records, required checks, waivers and unknown keys stay; each gate must decide the same
    checks the same way before and after, or nothing is written."""
    report = Report(args.verification)
    opened = open_verification(report, args)
    if opened is None:
        return report.emit("error")
    data, root, vpath = opened
    given = args.archive or project_rel(root, archive_path(vpath))
    archive, err = resolve_target(root, given)
    if err or archive.resolve() == vpath.resolve():
        report.diagnostics.append(f"archive {given}: " + (err.replace("target", "path") if err else
                                                          "is the verification file itself"))
        return report.emit("error")
    records = data["records"] if isinstance(data.get("records"), list) else []
    required = {(r.get("check_id"), r.get("target")) for r in data["required_checks"] if isinstance(r, dict)}
    newest = {}
    for i, rec in enumerate(records):
        if isinstance(rec, dict):
            newest[pair(rec)] = i
    unread = {k for k, i in newest.items() if k not in required
              and records[i].get("required_or_optional") != "optional"}
    keep = {i for i in current_indices(records) if pair(records[i]) not in unread}
    move = movable(records, keep, range(len(records)))
    moving = set(move)
    for i, rec in enumerate(records):
        if i not in moving and isinstance(rec, dict) and watches(root, rec, archive):
            report.diagnostics.append(f"archive {given} lies inside {rec.get('target')} (or an input of it), which "
                                      "a kept record fingerprints; writing it would make that record stale. Put "
                                      "the archive next to the verification file")
            return report.emit("error")
    summary = {"records": len(records), "kept": len(records) - len(move), "to_archive": len(move),
               "unread_pairs": len(unread), "archive": given, "written": False}
    if not args.write or not move:
        if not move:
            report.diagnostics.append("nothing to archive")
        else:
            report.diagnostics.append("dry run: nothing written; add --write to move the records")
        return report.emit("passed", {"compact": summary})
    compacted = dict(data)
    compacted["records"] = [rec for i, rec in enumerate(records) if i not in moving]
    try:
        before = {m: evaluate(data, root, vpath, m) for m in DELIVERY_MODES}
        after = {m: evaluate(compacted, root, vpath, m) for m in DELIVERY_MODES}
    except Malformed as exc:
        report.diagnostics.append(str(exc))
        return report.emit("error")
    changed = [m for m in DELIVERY_MODES if gate_shape(before[m]) != gate_shape(after[m])]
    if changed:
        report.diagnostics.append(f"compaction would change the {' and '.join(changed)} gate; nothing was written")
        return report.emit("error", {"compact": summary})
    source = project_rel(root, vpath) if covers(root, vpath) else str(vpath)
    if archive.suffix == ".jsonl":
        append_archive(archive, [records[i] for i in move], source)
    else:                                       # a JSON archive named by an earlier `compact --archive`
        try:
            held = json.loads(archive.read_text(encoding="utf-8")) if archive.exists() else \
                {"schema_version": 1, "archived_from": source, "records": []}
            if not isinstance(held, dict) or not isinstance(held.get("records"), list):
                raise ValueError("not an archive (expected an object with a records list)")
        except (OSError, ValueError) as exc:
            report.diagnostics.append(f"cannot read archive {given}: {exc}")
            return report.emit("error")
        held["records"].extend(records[i] for i in move)
        held.setdefault("compactions", []).append({"timestamp": now_iso(), "moved": len(move), "from": source})
        archive.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(archive, held)        # archive first: a failure here leaves the records in place
    write_json_atomic(vpath, compacted)
    summary["written"] = True
    if archive.suffix != ".jsonl":
        report.diagnostics.append("a JSON archive is not read by the record-time reuse guard; prefer the default "
                                  f"{archive_path(vpath).name}")
    return report.emit("passed", {"compact": summary,
                                  "gate": {m: overall_of(Report(""), after[m][0]) for m in DELIVERY_MODES}})


def has_website_files(path):
    if path.is_file():
        return path.suffix.lower() in WEBSITE_SUFFIXES
    for _dirpath, _dirs, files in os.walk(path, followlinks=False):
        if any(Path(f).suffix.lower() in WEBSITE_SUFFIXES for f in files):
            return True
    return False


def parse_modes(text):
    """`mockup,production` style list in DELIVERY_MODES order; ValueError when empty or unknown."""
    given = [m.strip() for m in (text or "").split(",") if m.strip()]
    unknown = [m for m in given if m not in DELIVERY_MODES]
    if unknown or not given:
        raise ValueError(f"--modes must list {' and/or '.join(DELIVERY_MODES)}, comma-separated"
                         + (f" (unknown: {', '.join(unknown)})" if unknown else ""))
    return [m for m in DELIVERY_MODES if m in given]


def set_requirement(data, check_id, target, modes, reason, decided_by="", remove=False, existing_only=False,
                    decision=None, stages=None):
    """Add, change or remove one entry of required_checks and log it in requirement_history.
    Returns (history entry or None when nothing changed, dropped modes). Records and waivers are never
    touched, so a failed record is never turned into a pass; a dropped mode only stops requiring it.
    Narrowing or removing (a weakening) needs `decided_by`, or `decision` (an active accepted decision with
    a recorded source, as {id, source}); ValueError otherwise."""
    required = data.setdefault("required_checks", [])
    current = next((r for r in required if isinstance(r, dict) and r.get("check_id") == check_id
                    and r.get("target") == target), None)
    before = None if current is None else list(current.get("modes", list(DELIVERY_MODES)))
    before_stages = [] if current is None else list(current.get("stages") or [])
    after_stages = before_stages if stages is None else list(stages)
    if remove:
        if current is None:
            raise ValueError(f"{check_id} {target} is not a required check; nothing to remove")
        after, action = [], "remove"
    elif current is None:
        after, action = list(modes), "add"
    else:
        if existing_only:
            return None, []
        after, action = list(modes), "update"
    if before is not None and set(before) == set(after) and (remove or set(before_stages) == set(after_stages)):
        return None, []
    dropped = [m for m in (before or []) if m not in after]
    # moving an existing check to the launch stage takes it out of the ordinary gates: also a weakening
    deferred = current is not None and not remove and "launch" in after_stages and "launch" not in before_stages
    if deferred:
        dropped = dropped + ["every gate before launch"]
    if dropped and not (decided_by or "").strip() and not decision:
        raise ValueError(f"this change stops requiring {check_id} {target} in {', '.join(dropped)}; weakening a "
                         "requirement needs --decided-by naming who decided it, or --decision citing an active "
                         "accepted decision with a recorded source (and --reason)")
    if remove:
        required.remove(current)
    elif current is None:
        entry = {"check_id": check_id, "target": target}
        if set(after) != set(DELIVERY_MODES):
            entry["modes"] = after
        if after_stages:
            entry["stages"] = after_stages
        required.append(entry)
    else:
        if set(after) == set(DELIVERY_MODES):
            current.pop("modes", None)
        else:
            current["modes"] = after
        if after_stages:
            current["stages"] = after_stages
        else:
            current.pop("stages", None)
    logged = {"timestamp": now_iso(), "check_id": check_id, "target": target, "action": action,
              "from_modes": before or [], "to_modes": after, "reason": reason, "decided_by": decided_by or "",
              "weakens": bool(dropped)}
    if before_stages or after_stages:
        logged.update({"from_stages": before_stages, "to_stages": [] if remove else after_stages})
    if decision:
        logged.update({"decision": decision["id"], "decision_source": decision["source"]})
    data.setdefault("requirement_history", []).append(logged)
    return logged, dropped



def cmd_waive(args):
    """Record (or with --remove, withdraw) the user's waiver of one required check. Granting needs
    --decided-by: the user, never the agent. Logged in requirement_history; records are untouched."""
    report = Report(args.verification)
    vpath = Path(args.verification)
    root = Path(args.root) if args.root else default_root(vpath)
    try:
        data = load_verification(vpath)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.diagnostics.append(f"cannot read verification record: {exc}")
        return report.emit("error")
    target = args.target
    if not is_url(target):
        path, err = resolve_target(root, target)
        if err:
            report.diagnostics.append(err)
            return report.emit("error")
        target = project_rel(root, path)
    key = (args.check_id, target)
    if not any(isinstance(r, dict) and (r.get("check_id"), r.get("target")) == key for r in data["required_checks"]):
        report.diagnostics.append(f"{args.check_id} on {target} is not a required check; nothing to waive")
        return report.emit("error")
    if not (args.reason or "").strip():
        report.diagnostics.append("--reason is required: say why the check is accepted as unmet")
        return report.emit("error")
    waivers = data.setdefault("waivers", [])
    kept = [w for w in waivers if not (isinstance(w, dict) and (w.get("check_id"), w.get("target")) == key)]
    entry = {"timestamp": now_iso(), "check_id": key[0], "target": key[1], "reason": args.reason.strip()}
    if args.remove:
        if len(kept) == len(waivers):
            report.diagnostics.append("no waiver on this check; nothing written")
            return report.emit("passed", {"change": "unchanged", "target": target})
        entry.update({"action": "unwaive", "decided_by": args.decided_by.strip(), "weakens": False})
        data["waivers"] = kept
    else:
        if not args.decided_by.strip():
            report.diagnostics.append("--decided-by is required: only the user can accept a required check as "
                                      "unmet. An agent never fills it in; give the user this command to run")
            return report.emit("error")
        scope = [x.strip() for x in (args.scope or "").split(",") if x.strip()]
        if any(x not in WAIVER_SCOPES for x in scope):
            report.diagnostics.append(f"--scope must list {', '.join(WAIVER_SCOPES)}, comma-separated")
            return report.emit("error")
        waiver = {"check_id": key[0], "target": key[1], "reason": entry["reason"],
                  "decided_by": args.decided_by.strip(), "timestamp": entry["timestamp"]}
        if args.owner.strip():
            waiver["owner"] = args.owner.strip()
        if args.expires:
            until = waiver_date(args.expires)
            if until is None or len(args.expires) != 10:
                report.diagnostics.append("--expires must be a date, YYYY-MM-DD")
                return report.emit("error")
            if until < datetime.datetime.now(datetime.timezone.utc).date():
                report.diagnostics.append("--expires is in the past")
                return report.emit("error")
            waiver["expires"] = args.expires
        if scope:
            waiver["scope"] = [x for x in WAIVER_SCOPES if x in scope]
        data["waivers"] = kept + [waiver]
        entry.update({"action": "waive", "decided_by": waiver["decided_by"], "weakens": True,
                      **{k: waiver[k] for k in ("owner", "expires", "scope") if k in waiver}})
    data.setdefault("requirement_history", []).append(entry)
    write_json_atomic(vpath, data)
    return report.emit("passed", {"change": entry["action"], "target": target, "logged": entry})

def cmd_accept_finding(args):
    """Record (or with --remove, withdraw) the user's acceptance of one warning: one check ID, one file or
    folder, and a text that occurs in the finding. Granting needs --decided-by: the user, never the agent.
    Logged in requirement_history. Warnings only; a defect needs a fix or a waiver of the check."""
    report = Report(args.verification)
    vpath = Path(args.verification)
    root = Path(args.root) if args.root else default_root(vpath)
    try:
        data = load_verification(vpath)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.diagnostics.append(f"cannot read verification record: {exc}")
        return report.emit("error")
    if not CHECK_ID_RE.match(args.check_id or ""):
        report.diagnostics.append("--check-id must name one check (no wildcard)")
        return report.emit("error")
    if is_url(args.target) or is_glob(args.target):
        report.diagnostics.append("--target must be one file or folder in the project (no URL, no glob)")
        return report.emit("error")
    path, err = resolve_target(root, args.target)
    if err:
        report.diagnostics.append(err)
        return report.emit("error")
    target = project_rel(root, path)
    match = (args.match or "").strip()
    if not match:
        report.diagnostics.append("--match must quote text from the finding's evidence, so only that finding "
                                  "is accepted")
        return report.emit("error")
    if not (args.reason or "").strip():
        report.diagnostics.append("--reason is required: say why the finding is a false positive or an "
                                  "accepted exception")
        return report.emit("error")
    key = (args.check_id, target, match)
    found = data.get("accepted_findings")
    found = found if isinstance(found, list) else []
    kept = [a for a in found if not (isinstance(a, dict) and (a.get("check_id"), a.get("target"),
                                                              a.get("match")) == key)]
    entry = {"timestamp": now_iso(), "check_id": key[0], "target": target, "match": match,
             "reason": args.reason.strip()}
    if args.remove:
        if len(kept) == len(found):
            report.diagnostics.append("no such acceptance; nothing written")
            return report.emit("passed", {"change": "unchanged", "target": target})
        entry.update({"action": "unaccept-finding", "decided_by": args.decided_by.strip(), "weakens": False})
        data["accepted_findings"] = kept
    else:
        if not args.decided_by.strip():
            report.diagnostics.append("--decided-by is required: only the user can accept a finding. An agent "
                                      "never fills it in; give the user this command to run")
            return report.emit("error")
        acceptance = {"check_id": key[0], "target": target, "match": match, "reason": entry["reason"],
                      "decided_by": args.decided_by.strip(), "timestamp": entry["timestamp"]}
        if args.expires:
            until = waiver_date(args.expires)
            if until is None or len(args.expires) != 10:
                report.diagnostics.append("--expires must be a date, YYYY-MM-DD")
                return report.emit("error")
            if until < datetime.datetime.now(datetime.timezone.utc).date():
                report.diagnostics.append("--expires is in the past")
                return report.emit("error")
            acceptance["expires"] = args.expires
        data["accepted_findings"] = kept + [acceptance]
        entry.update({"action": "accept-finding", "decided_by": acceptance["decided_by"], "weakens": True,
                      **({"expires": acceptance["expires"]} if "expires" in acceptance else {})})
    data.setdefault("requirement_history", []).append(entry)
    write_json_atomic(vpath, data)
    return report.emit("passed", {"change": entry["action"], "target": target, "logged": entry})


def cmd_require(args):
    report = Report(args.verification)
    vpath = Path(args.verification)
    root = Path(args.root) if args.root else default_root(vpath)
    try:
        data = load_verification(vpath) if vpath.exists() else \
            {"schema_version": 1, "required_checks": [], "waivers": [], "records": []}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.diagnostics.append(f"cannot read verification record: {exc}")
        return report.emit("error")
    if not CHECK_ID_RE.match(args.check_id or ""):
        report.diagnostics.append(f"check ID {args.check_id[:80]!r} must be letters, digits, '.', '_' or '-'")
        return report.emit("error")
    if not (args.reason or "").strip():
        report.diagnostics.append("--reason is required: say why the requirement changes")
        return report.emit("error")
    target = args.target
    if not is_url(target):
        path, err = resolve_target(root, target)
        if err or "\0" in target or "\\" in target:
            report.diagnostics.append(err or "target contains a NUL or backslash")
            return report.emit("error")
        target = project_rel(root, path)
        if not (path.exists() or path.is_symlink()):
            report.diagnostics.append(f"note: {target} does not exist yet; the gate reports it unavailable "
                                      "until a record exists")
    try:
        stages = None if not args.stage else [] if args.stage == "every" else [args.stage]
        if stages and args.modes and parse_modes(args.modes) != ["production"]:
            raise ValueError("a launch-stage check is a production check: use --modes production or leave it out")
        modes = [] if args.remove else parse_modes(args.modes) if args.modes else \
            ["production"] if stages else list(DELIVERY_MODES)
        before = {m: evaluate(data, root, vpath, m) for m in DELIVERY_MODES}
        decision = None
        if args.decision:
            state = json.loads((vpath.parent / "state.json").read_text(encoding="utf-8")) \
                if (vpath.parent / "state.json").is_file() else {}
            found = active_decision(state if isinstance(state, dict) else {}, args.decision)
            if found is None:
                raise ValueError(f"--decision {args.decision[:40]}: no active decision with that id and a recorded "
                                 f"`source` in {vpath.parent / 'state.json'}; cite only a decision the owner "
                                 "actually made, or have them run the command with --decided-by")
            decision = {"id": found["id"], "source": found["source"].strip()}
        logged, dropped = set_requirement(data, args.check_id, target, modes, args.reason.strip(),
                                          args.decided_by, remove=args.remove, decision=decision, stages=stages)
    except (ValueError, Malformed) as exc:
        report.diagnostics.append(str(exc))
        if "--decided-by" in str(exc) and target_absent(root, target):
            report.diagnostics.append(f"{target} no longer exists: if the page was removed or moved, use "
                                      "`sw_records.py retire`, which checks that and needs no decider")
        return report.emit("error")
    if logged is None:
        report.diagnostics.append("requirement already reads this way; nothing written")
        return report.emit("passed", {"change": "unchanged", "target": target})
    notes = []
    for m in dropped:
        if m not in DELIVERY_MODES:
            notes.append(f"{args.check_id} {target} is now assessed only by the production gate with --stage "
                         "launch; the ordinary gates list it as not assessed, never as passed")
            continue
        line = next((c for c in before.get(m, ([], [], []))[0]
                     if (c["check_id"], c["target"]) == (args.check_id, target)), None)
        result = line["result"] if line else "unavailable"
        notes.append(f"{m} gate no longer requires {args.check_id} {target}; its current {m} result "
                     f"({result}) is now listed as not assessed, never as passed")
    try:
        for m in DELIVERY_MODES:
            evaluate(data, root, vpath, m)
    except Malformed as exc:
        report.diagnostics.append(str(exc))
        return report.emit("error")
    vpath.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(vpath, data)
    return report.emit("passed", {"change": logged["action"], "requirement": logged, "notes": notes,
                                  "criteria_note": CRITERIA_NOTE})


# ---------- removed targets and evidence pruning ----------

def norm_route(route):
    """A site-map route without backticks, query, fragment or trailing slash ("/" stays "/")."""
    return "/" + re.split(r"[?#]", str(route).strip("` "))[0].strip("/")


def page_contracts(folder):
    """({normalised route: page contract}, [record files read]) from the Markdown records in `folder`."""
    texts, files = [], []
    for p in sorted(Path(folder).glob("*.md")):
        try:
            texts.append((p.name, p.read_text(encoding="utf-8")))
            files.append(p)
        except (OSError, UnicodeDecodeError):
            continue
    pages = parse_records(texts).get("sitemap", {}).get("pages", {})
    return {norm_route(r): c for r, c in pages.items()}, files


def site_routes(vpath):
    """Routes the site map in the records folder still lists (`routes` and `### Page:` contracts),
    normalised without a trailing slash; None when the folder holds no site map."""
    texts = []
    for p in sorted(vpath.parent.glob("*.md")):
        try:
            texts.append((p.name, p.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    sm = parse_records(texts).get("sitemap")
    if sm is None:
        return None
    listed = set(split_routes(sm.get("routes", ""))) | set(sm.get("pages", {}))
    return {"/" + re.split(r"[?#]", r.strip("` "))[0].strip("/") for r in listed}


def route_of(rel):
    """The route a built page path (relative to its build folder) serves, or None for a non-page."""
    rel = Path(rel)
    if rel.name == "index.html":
        parent = rel.parent.as_posix()
        return "/" if parent == "." else "/" + parent
    if rel.suffix == ".html":
        return "/" + rel.with_suffix("").as_posix()
    return None


def listed_route(target, routes, folders):
    """A site-map route that still maps to `target`, judged against each build folder that contains it
    (folder targets of other checks), or by suffix for routes other than / when no folder contains it."""
    for folder in folders:
        if target.startswith(folder.rstrip("/") + "/"):
            route = route_of(target[len(folder.rstrip("/")) + 1:])
            if route in routes:
                return route
    for route in routes - {"/"}:
        tail = route.lstrip("/")
        if target == tail + ".html" or target.endswith(("/" + tail + "/index.html", "/" + tail + ".html")) \
                or target in (tail + "/index.html",):
            return route
    return None


def retire_target(data, required, newest, target, reason, replaced_by, stamp, basis, decision=""):
    """Mark every active requirement on `target` retired and log each in requirement_history."""
    history = data.setdefault("requirement_history", [])
    for req in required:
        if req["target"] != target or req.get("retired"):
            continue
        last = newest.get(pair(req), {}).get("source_revision_or_target_fingerprint", "")
        req["retired"] = {"timestamp": stamp, "reason": reason, "replaced_by": replaced_by, "last_identity": last}
        modes = list(req.get("modes", list(DELIVERY_MODES)))
        entry = {"timestamp": stamp, "check_id": req["check_id"], "target": req["target"], "action": "retire",
                 "from_modes": modes, "to_modes": modes, "reason": reason, "decided_by": "", "basis": basis,
                 "replaced_by": replaced_by, "weakens": False}
        if decision:
            entry["decision"] = decision
        history.append(entry)


def intended_removals(vpath):
    """{route: entry} for the well-formed `removed_routes` of the state.json beside the verification file:
    routes whose removal was recorded as intended, with an accepted decision or a source."""
    state_file = Path(vpath).with_name("state.json")
    try:
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
    except (OSError, ValueError):
        return {}
    entries = state.get("removed_routes") if isinstance(state, dict) else None
    if not isinstance(entries, list):
        return {}
    return {"/" + e["route"].strip().strip("/"): e for e in entries
            if not removed_route_problems([e], state.get("accepted_decisions"))}


def retire_removed_routes(data, root, vpath, site_rel):
    """For a helper run over the build at `site_rel` (project-relative): active requirements on pages of
    that build that are gone. A page is retired only when state.json `removed_routes` records its route as
    intentionally removed; a page that is merely missing (or no longer in the site map) is returned as a
    potential regression and stays required. Edits `data`; returns (retired, regressions)."""
    intended = intended_removals(vpath)
    required = [r for r in data.get("required_checks", []) if isinstance(r, dict)
                and isinstance(r.get("target"), str) and not r.get("retired")]
    prefix = "" if site_rel in ("", ".") else site_rel.rstrip("/") + "/"
    gone = {}
    for r in required:
        t = r["target"]
        if not is_url(t) and not is_glob(t) and t.startswith(prefix) and target_absent(root, t):
            gone.setdefault(t, []).append(r["check_id"])
    newest = {pair(rec): rec for rec in data.get("records", []) if isinstance(rec, dict)}
    stamp, retired, regressions = now_iso(), [], []
    for t, cids in sorted(gone.items()):
        route = route_of(t[len(prefix):])
        item = {"target": t, "route": route, "check_ids": sorted(cids)}
        entry = intended.get(route) if route else None
        if entry is None:
            regressions.append(item)
            continue
        why = f"decision {entry['decision']}" if entry.get("decision") else f"source: {entry['source'].strip()}"
        retire_target(data, required, newest, t, entry["reason"].strip(), str(entry.get("replaced_by", "")).strip(),
                      stamp, f"target absent and its route is recorded as intentionally removed in state.json "
                      f"removed_routes ({why}); retired by a helper run", decision=entry.get("decision", ""))
        retired.append(item)
    return retired, regressions


def cmd_retire(args):
    """Stop requiring checks on targets that no longer exist: a fact this command checks (the target is
    absent and the site map no longer lists its route), not a decision, so it needs no --decided-by.
    Retired checks are listed as not assessed, never passed, and are required again if the target returns."""
    report = Report(args.verification)
    opened = open_verification(report, args)
    if opened is None:
        return report.emit("error")
    data, root, vpath = opened
    if not (args.reason or "").strip():
        report.diagnostics.append("--reason is required: say why the target is gone")
        return report.emit("error")
    replaced_by = (args.replaced_by or "").strip()
    if any(ord(ch) < 32 for ch in replaced_by) or len(replaced_by) > 500:
        report.diagnostics.append("--replaced-by must be one line of at most 500 characters")
        return report.emit("error")
    required = [r for r in data["required_checks"] if isinstance(r, dict) and isinstance(r.get("target"), str)]
    refused, targets = [], []
    if args.all_missing:
        targets = sorted({r["target"] for r in required if not r.get("retired") and target_absent(root, r["target"])})
    for given in args.target:
        if is_url(given):
            refused.append({"target": given, "why": "a URL target cannot be shown absent from this machine"})
            continue
        if is_glob(given):
            if glob_problem(given):
                refused.append({"target": given, "why": glob_problem(given)})
            else:
                targets.append(given)
            continue
        path, err = resolve_target(root, given)
        if err:
            refused.append({"target": given, "why": err})
            continue
        targets.append(project_rel(root, path))
    routes = site_routes(vpath)
    folders = sorted({r["target"] for r in required if not is_url(r["target"]) and not is_glob(r["target"])
                      and (root / r["target"]).is_dir()}, key=len, reverse=True)
    others = [o for o in (default_root(vpath), Path.cwd().resolve(), vpath.resolve().parent) if o != root.resolve()]
    plan = []
    for target in dict.fromkeys(targets):
        active = [r for r in required if r["target"] == target and not r.get("retired")]
        if target_present(root, target):
            why = "it still exists"
        elif any(target_present(o, target) for o in others):
            why = "it exists under another likely root, so --root looks wrong; run from the project root with --root ."
        elif not active:
            why = "no active required check targets it"
        elif routes is not None and listed_route(target, routes, folders):
            why = f"the site map still lists route {listed_route(target, routes, folders)}; remove it there first"
        else:
            plan.append({"target": target, "check_ids": sorted(r["check_id"] for r in active)})
            continue
        refused.append({"target": target, "why": why})
    summary = {"targets": len(plan), "pairs": sum(len(p["check_ids"]) for p in plan), "plan": plan,
               "refused": refused, "replaced_by": replaced_by, "written": False,
               "site_map": "checked" if routes is not None else "no site map found; only absence on disk was checked"}
    if refused:
        report.diagnostics.append("nothing written: every named target must be retirable")
        return report.emit("error", {"retire": summary})
    if not plan:
        report.diagnostics.append("no required check targets a missing file; nothing to retire")
        return report.emit("passed", {"retire": summary})
    if not args.write:
        report.diagnostics.append("dry run: nothing written; add --write to retire these requirements")
        return report.emit("passed", {"retire": summary})
    newest = {pair(rec): rec for rec in data.get("records", []) if isinstance(rec, dict)}
    stamp, reason = now_iso(), args.reason.strip()
    for item in plan:
        retire_target(data, required, newest, item["target"], reason, replaced_by, stamp,
                      "target absent and not listed in the site map; checked by sw_records.py retire, "
                      "no person's decision recorded")
    try:
        gates = {m: overall_of(Report(""), evaluate(data, root, vpath, m)[0]) for m in DELIVERY_MODES}
    except Malformed as exc:
        report.diagnostics.append(str(exc))
        return report.emit("error")
    write_json_atomic(vpath, data)
    summary["written"] = True
    return report.emit("passed", {"retire": summary, "gate": gates, "criteria_note": CRITERIA_NOTE})


def prune_plan(folder, refs):
    """Entries under `folder` that no reference keeps: a referenced path keeps itself and everything in
    it, and a folder holding a referenced path is entered rather than removed. Symlinks are never followed."""
    out = []
    for child in sorted(folder.iterdir()):
        if child in refs or any(r in child.parents for r in refs) or is_archive(child):
            continue
        if child.is_dir() and not child.is_symlink() and any(child in r.parents for r in refs):
            out.extend(prune_plan(child, refs))
        else:
            out.append(child)
    return out


def is_archive(path):
    """A records archive kept under evidence/ (`compact` JSON or the append-only JSON lines) is a record,
    not evidence: never pruned."""
    if path.is_symlink() or path.suffix not in (".json", ".jsonl") or not path.is_file():
        return False
    try:
        if path.suffix == ".jsonl":
            with open(path, encoding="utf-8") as f:
                first = json.loads(f.readline() or "{}")
            return isinstance(first, dict) and "archived_at" in first and "record" in first
        return "archived_from" in json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False


def entry_size(path):
    if path.is_symlink() or not path.is_dir():
        return path.lstat().st_size
    return sum((Path(d) / f).lstat().st_size for d, _dirs, files in os.walk(path, followlinks=False) for f in files)


def cmd_prune_evidence(args):
    """Delete evidence files no record in the verification file cites, once the gate passes in the mode."""
    report = Report(args.verification)
    opened = open_verification(report, args)
    if opened is None:
        return report.emit("error")
    data, root, vpath = opened
    current_only = getattr(args, "current_only", False)
    try:
        overall = overall_of(Report(""), evaluate(data, root, vpath, args.mode)[0])
        before = {m: gate_shape(evaluate(data, root, vpath, m)) for m in DELIVERY_MODES}
    except Malformed as exc:
        report.diagnostics.append(str(exc))
        return report.emit("error")
    if current_only:
        if [m for m in data.get("runs_in_progress") or [] if isinstance(m, dict)]:
            report.diagnostics.append("a run is in progress (`begin` marker open): it may have written evidence no "
                                      "record cites yet, so nothing was archived or deleted; record or cancel it first")
            return report.emit("skipped", {"mode": args.mode}, code=1)
    elif overall != "passed":
        report.diagnostics.append(f"the {args.mode} gate reads {overall}; evidence is pruned only after every "
                                  "required check passes, so nothing was deleted (--current-only keeps what the "
                                  "current records cite and prunes the rest without a passing gate)")
        return report.emit("skipped", {"mode": args.mode}, code=1)
    rolled = []
    if current_only:       # superseded records go to the archive first, so only current evidence stays cited
        records = data["records"]
        move = movable(records, current_indices(records),
                       [i for i, r in enumerate(records) if isinstance(r, dict) and isinstance(r.get("target"), str)])
        archive = archive_path(vpath)
        if move and any(watches(root, r, archive) for i, r in enumerate(records)
                        if i not in set(move) and isinstance(r, dict)):
            report.diagnostics.append(f"a kept record fingerprints {archive.name}; no record was archived")
            move = []
        trimmed = dict(data, records=[r for i, r in enumerate(records) if i not in set(move)])
        try:
            changed = [m for m in DELIVERY_MODES if gate_shape(evaluate(trimmed, root, vpath, m)) != before[m]]
        except Malformed as exc:
            report.diagnostics.append(str(exc))
            return report.emit("error")
        if changed:
            report.diagnostics.append(f"archiving would change the {' and '.join(changed)} gate; nothing was written")
            return report.emit("error", {"mode": args.mode})
        rolled = [records[i] for i in move]
        if args.write and move:
            append_archive(archive, rolled, project_rel(root, vpath) if covers(Path(root), vpath) else str(vpath))
            write_json_atomic(vpath, trimmed)
        data = trimmed
    evidence = vpath.parent / "evidence"
    if evidence.is_symlink() or not evidence.is_dir():
        report.diagnostics.append(f"no evidence folder at {evidence} (or it is a symlink); nothing to prune")
        return report.emit("passed", {"mode": args.mode})
    rroot = root.resolve()
    try:
        ev = rroot / project_rel(root, evidence)
    except ValueError:
        report.diagnostics.append("the evidence folder lies outside the project root; nothing was deleted")
        return report.emit("error")
    records = [r for r in data.get("records", []) if isinstance(r, dict)]
    cited = [vpath]
    for rec in records:
        inputs = rec.get("inputs") if isinstance(rec.get("inputs"), dict) else {}
        cited += [v for v in [rec.get("evidence_path"), rec.get("target"), *inputs] if isinstance(v, str) and v and not is_url(v)]
    refs = set()
    for value in cited:
        path, err = resolve_target(root, value)
        if not err:
            refs.add(Path(os.path.normpath(rroot / project_rel(root, path))))
    doomed = prune_plan(ev, refs)
    summary = {"evidence_dir": project_rel(root, evidence), "to_delete": [project_rel(rroot, p) for p in doomed],
               "bytes": sum(entry_size(p) for p in doomed), "written": False}
    if current_only:
        summary["archived"] = [{"check_id": r.get("check_id"), "target": r.get("target"),
                                "evidence_path": r.get("evidence_path")} for r in rolled]
        summary["records_archived"] = bool(rolled) and bool(args.write)
    superseded = len(records) - len(current_indices(records))
    if superseded:
        report.diagnostics.append(f"{superseded} superseded records still cite their evidence, which is kept; run "
                                  "`compact --write` first to archive them so their files can be pruned")
    if archive_path(vpath).exists():
        report.diagnostics.append(f"archived records in {archive_path(vpath).name} keep their digests (the reuse "
                                  "guard reads them) but not their evidence files")
    if not doomed:
        report.diagnostics.append("every evidence file is cited by a record; nothing to prune")
        return report.emit("passed", {"mode": args.mode, "prune": summary})
    if not args.write:
        report.diagnostics.append("dry run: nothing deleted; add --write to delete these files")
        return report.emit("passed", {"mode": args.mode, "prune": summary})
    for path in doomed:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    summary["written"] = True
    report.diagnostics.append("deleted; archived records (from `compact`) that cited these files now point to "
                              "files that no longer exist")
    after = overall_of(Report(""), evaluate(data, root, vpath, args.mode)[0])
    if current_only:
        changed = [m for m in DELIVERY_MODES if gate_shape(evaluate(data, root, vpath, m)) != before[m]]
        if changed:
            report.diagnostics.append(f"the {' and '.join(changed)} gate changed after pruning")
            return report.emit("error", {"mode": args.mode, "prune": summary})
        return report.emit("passed", {"mode": args.mode, "prune": summary, "gate": after})
    if after != "passed":
        report.diagnostics.append(f"the {args.mode} gate reads {after} after pruning")
        return report.emit("error", {"mode": args.mode, "prune": summary})
    return report.emit("passed", {"mode": args.mode, "prune": summary, "gate": after})


class _RecordArgs(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def add_record_options(p):
    """The per-record options, shared by `record` and each entry of a `record --batch` file."""
    p.add_argument("--check-id")
    p.add_argument("--target")
    p.add_argument("--result", choices=RESULTS)
    p.add_argument("--required-or-optional", default="required", choices=("required", "optional"))
    p.add_argument("--method", choices=EVIDENCE_METHODS)
    p.add_argument("--tool-and-version")
    p.add_argument("--evidence-path")
    p.add_argument("--finding")
    p.add_argument("--limitations")
    p.add_argument("--issue-id")
    p.add_argument("--skip-reason")
    p.add_argument("--fingerprint", help="explicit fingerprint or rev:<id> (default: computed)")
    p.add_argument("--input", action="append", default=[], metavar="PATH",
                   help="a further file or directory the check consumed; fingerprinted into `inputs` (repeatable)")
    p.add_argument("--inputs-from-page", action="store_true",
                   help="for a built HTML page target: add every local stylesheet, script and preload it links "
                        "as an input, so a shared-file change makes the record stale")
    p.add_argument("--site", help="with --inputs-from-page: the build folder that root-relative links resolve "
                                  "against (default: the nearest folder above the page that holds the file)")
    p.add_argument("--require", action="store_true", help="also add the check to required_checks")
    p.add_argument("--mode", choices=DELIVERY_MODES,
                   help="the delivery criteria this run was judged against; omit for a check that counts in every mode")
    p.add_argument("--exclude", action="append", default=[], metavar="PATH",
                   help="a path inside a folder target left out of its fingerprint (repeatable; listed in the record)")
    p.add_argument("--allow-website-exclusion", action="store_true",
                   help="permit an exclusion that holds pages, styles, scripts, images or fonts")
    p.add_argument("--sample-scope", help="what was sampled, e.g. '3 of 12 pages at 320 and 1280px'")
    p.add_argument("--judged", action="append", default=[], metavar="ROUTE,WIDTH,THEME,SCREENSHOT",
                   help="a screenshot a manual review judged (repeatable); each must also be an --input, so "
                        "replacing it makes the review stale")
    p.add_argument("--append-unchanged", action="store_true",
                   help="append the record even when the current one already says the same about the same "
                        "target state (by default such a rerun writes nothing and is reported as unchanged)")


def record_parser():
    p = _RecordArgs(prog="record entry", add_help=False)
    add_record_options(p)
    return p


class _LinkedAssets(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        rel = a.get("rel", "").lower().split()
        if tag == "link" and a.get("href"):
            if any("stylesheet" in r for r in rel):
                self.found.append(("style", a["href"]))
            elif "modulepreload" in rel:
                self.found.append(("script", a["href"]))
            elif "preload" in rel:
                self.found.append(("preload", a["href"]))
        elif tag == "script" and a.get("src"):
            self.found.append(("script", a["src"]))

    handle_startendtag = handle_starttag


def linked_assets(html_text):
    """[(kind, reference)] for the files a page loads: stylesheets ("style"), scripts and module preloads
    ("script"), and other preloads ("preload"), in document order. Shared by sw_site_check.py."""
    parser = _LinkedAssets()
    parser.feed(html_text)
    parser.close()
    return parser.found


def page_inputs(root, page, site=None):
    """(project-relative inputs, notes) for the local files `page` links. A root-relative reference
    (/assets/a.css) resolves against `site`, or else the nearest folder above the page that holds it."""
    text = page.read_text(encoding="utf-8", errors="replace")
    real = Path(root).resolve()
    found, notes = [], []
    for _kind, ref in linked_assets(text):
        clean = re.split(r"[?#]", ref.strip())[0]
        if not clean or re.match(r"^[a-z][a-z0-9+.-]*:|^//", clean, re.IGNORECASE):
            continue                       # another origin or a data: URL; not a local file
        candidates = []
        if clean.startswith("/"):
            given = Path(site) if site and Path(site).is_absolute() else Path(root) / site if site else None
            bases = [given] if given else [p for p in [page.parent, *page.parent.parents] if covers(real, p)]
            candidates = [b / clean.lstrip("/") for b in bases]
        else:
            candidates = [page.parent / clean]
        hit = next((c for c in candidates if c.is_file() and covers(real, c)), None)
        if hit is None:
            notes.append(f"{ref}: linked by {page.name} but not found inside the project; not recorded as an input")
            continue
        rel = project_rel(root, hit)
        if rel not in found:
            found.append(rel)
    return found, notes


def archive_path(vpath):
    """The append-only archive beside a verification file: superseded records, one JSON line each."""
    vpath = Path(vpath)
    return vpath.with_name(vpath.stem + "-archive.jsonl")


_ARCHIVED = {}


def archived_states(archive):
    """{pair: [(evidence_sha256, state)]} of archived records that cite hashed evidence (read once)."""
    key = str(archive)
    if key not in _ARCHIVED:
        out = {}
        try:
            with open(archive, encoding="utf-8") as f:
                for line in f:
                    if '"evidence_sha256"' not in line:
                        continue
                    try:
                        rec = json.loads(line).get("record")
                    except (ValueError, AttributeError):
                        continue
                    if isinstance(rec, dict) and rec.get("evidence_sha256") and isinstance(rec.get("target"), str):
                        out.setdefault(pair(rec), []).append(
                            (rec["evidence_sha256"], (rec.get("source_revision_or_target_fingerprint"),
                                                      rec.get("inputs") or {})))
        except OSError:
            pass
        _ARCHIVED[key] = out
    return _ARCHIVED[key]


def append_archive(archive, recs, source):
    """Append records verbatim, one line each; earlier lines are never rewritten."""
    stamp = now_iso()
    Path(archive).parent.mkdir(parents=True, exist_ok=True)
    with open(archive, "a", encoding="utf-8") as f:
        for rec in recs:
            f.write(json.dumps({"archived_at": stamp, "from": source, "record": rec}, separators=(",", ":")) + "\n")
        f.flush()
        os.fsync(f.fileno())
    _ARCHIVED.pop(str(archive), None)


def watches(root, rec, path):
    """True when a record's target (less its exclusions) or one of its inputs fingerprints `path`."""
    target = rec.get("target")
    if isinstance(target, str) and target and not is_url(target):
        if is_glob(target):
            if covers(Path(root), path) and fnmatch.fnmatch(project_rel(root, path), target):
                return True
        else:
            t, err = resolve_target(root, target)
            if not err and covers(t, path):
                excl = [resolve_target(root, e)[0] for e in rec.get("exclusions") or [] if isinstance(e, str)]
                if not any(e is not None and covers(e, path) for e in excl):
                    return True
    inputs = rec.get("inputs") if isinstance(rec.get("inputs"), dict) else {}
    for rel in inputs:
        if isinstance(rel, str) and rel and is_glob(rel):
            if covers(Path(root), path) and fnmatch.fnmatch(project_rel(root, path), rel):
                return True
        elif isinstance(rel, str) and rel and not is_url(rel):
            p, err = resolve_target(root, rel)
            if not err and covers(p, path):
                return True
    return False


def movable(records, keep, candidates):
    """The candidate indices that may leave the active file: not read by any mode, not client-supplied,
    well formed, and not sharing evidence with a current record of the same check (the reuse guard)."""
    current = {(pair(records[i]), records[i].get("evidence_sha256")) for i in keep}
    return [i for i in candidates if i not in keep and isinstance(records[i], dict)
            and not records[i].get("supplied_by") and not evidence_problems(records[i])
            and not (records[i].get("evidence_sha256") and (pair(records[i]), records[i]["evidence_sha256"]) in current)]


def roll_superseded(data, root, vpath, pairs):
    """Move records of `pairs` that no delivery mode reads any more to the archive beside the file, so the
    active file holds current results. Returns how many moved; none move when a kept record would
    fingerprint the archive."""
    records = data["records"]
    keep = current_indices(records)
    candidates = [i for i, r in enumerate(records) if isinstance(r, dict) and isinstance(r.get("target"), str)
                  and pair(r) in pairs]
    move = movable(records, keep, candidates)
    if not move:
        return 0
    archive, moving = archive_path(vpath), set(move)
    if any(watches(root, r, archive) for i, r in enumerate(records) if i not in moving and isinstance(r, dict)):
        return 0
    append_archive(archive, [records[i] for i in move], project_rel(root, vpath) if covers(Path(root), vpath)
                   else str(vpath))
    data["records"] = [r for i, r in enumerate(records) if i not in moving]
    return len(move)


RECORD_REQUIRED = ("check_id", "target", "result", "method", "tool_and_version")


def add_record(data, args, root, vpath, report, label=""):
    """Validate one record from `args` and append it to `data`; None (with diagnostics) when refused."""
    def refuse(text):
        report.diagnostics.append(label + text)
        return None
    missing = [f"--{n.replace('_', '-')}" for n in RECORD_REQUIRED if not getattr(args, n)]
    if missing:
        return refuse(f"missing {', '.join(missing)}")
    rec = {k: "" for k in EVIDENCE_FIELDS}
    rec.update({"check_id": args.check_id, "target": args.target, "result": args.result,
                "required_or_optional": args.required_or_optional, "method": args.method,
                "tool_and_version": args.tool_and_version, "timestamp": now_iso(),
                "evidence_path": args.evidence_path or "", "observed_finding": args.finding or "",
                "limitations": args.limitations or "", "issue_id_when_applicable": args.issue_id or "",
                "skip_reason_when_applicable": args.skip_reason or ""})
    if args.check_id in SUBMISSION_CHECKS and args.result == "passed" and args.method == "automated" \
            and args.mode != "mockup":
        return refuse(f"{args.check_id}: an automated pass cannot stand for a working submission; "
                      "record a browser or manual submission test (local stub or provider test mode), "
                      "or pass --mode mockup for a mock-up-only pass")
    if args.mode:
        rec["mode"] = args.mode
    if args.sample_scope:
        rec["sample_scope"] = args.sample_scope
    target_path, glob = None, is_glob(args.target)
    if glob:
        problem = glob_problem(args.target)
        if problem:
            return refuse(problem)
        if args.exclude or args.inputs_from_page:
            return refuse("a file-set target takes neither --exclude nor --inputs-from-page")
        matched = glob_files(root, args.target)
        if not matched:
            return refuse(f"file-set target {args.target} matches no files under --root {root}")
    elif not is_url(args.target):
        target_path, err = resolve_target(root, args.target)
        if err or not (target_path.exists() or target_path.is_symlink()):
            return refuse(err or f"target not found: {args.target} (relative targets resolve "
                                 f"against --root, here {root})")
    skip, exclusions = [], []
    for given in args.exclude:
        path, err = resolve_target(root, given)
        if err or not (path.exists() or path.is_symlink()):
            return refuse(f"exclusion {given}: " + (err.replace("target", "path") if err else "not found"))
        if target_path is None or not target_path.is_dir() or not covers(target_path, path) \
                or path.resolve() == target_path.resolve():
            return refuse(f"exclusion {given} must lie inside the target folder and not be the target")
        if has_website_files(path) and not args.allow_website_exclusion:
            return refuse(f"exclusion {given} holds website files (pages, styles, scripts, images or "
                          "fonts); excluding them would hide changes to the site. Narrow the exclusion, "
                          "or pass --allow-website-exclusion if they really are not part of this check")
        exclusions.append(project_rel(root, path))
        skip.append(path.resolve().relative_to(target_path.resolve()).as_posix())
    if exclusions:
        rec["exclusions"] = exclusions
    current = glob_fingerprint(matched) if glob else \
        fingerprint(target_path, skip) if target_path is not None else None
    if args.fingerprint:
        if current is not None and SHA_RE.match(args.fingerprint) and args.fingerprint != current:
            return refuse("--fingerprint does not match the current target; evidence about an "
                          "older snapshot would be stale as soon as it is written")
        rec["source_revision_or_target_fingerprint"] = args.fingerprint
    elif current is not None:
        rec["source_revision_or_target_fingerprint"] = current
    given_inputs = list(args.input)
    if args.inputs_from_page:
        if target_path is None or not target_path.is_file() or target_path.suffix.lower() not in (".html", ".htm"):
            return refuse("--inputs-from-page needs a built HTML page as the target")
        linked, notes = page_inputs(root, target_path, args.site)
        report.diagnostics.extend(label + n for n in notes)
        given_inputs += [i for i in linked if i not in given_inputs]
    inputs = {}
    for given in given_inputs:
        if is_glob(given):
            matched_input = [] if glob_problem(given) else glob_files(root, given)
            if not matched_input:
                return refuse(f"input {given}: " + (glob_problem(given) or "matches no files"))
            inputs[given] = glob_fingerprint(matched_input)
            continue
        path, err = resolve_target(root, given)
        if err or not (path.exists() or path.is_symlink()):
            return refuse(f"input {given}: " + (err.replace("target", "path") if err else "not found"))
        inputs[project_rel(root, path)] = fingerprint(path)
    rec["inputs"] = inputs
    if args.judged:
        judged = []
        for value in args.judged:
            item, problem = parse_judged(value)
            if problem:
                return refuse(problem)
            path, err = resolve_target(root, item["screenshot"])
            if err or not path.is_file():
                return refuse(f"judged screenshot {item['screenshot']}: " + (err or "not a file"))
            item["screenshot"] = project_rel(root, path)
            covered = item["screenshot"] in inputs or any(
                is_glob(k) and path in glob_files(root, k) for k in inputs)
            if not covered:
                return refuse(f"judged screenshot {item['screenshot']} is not an --input of this record; "
                              "pass it with --input (or a glob that covers it) so the review is bound to it")
            judged.append(item)
        rec["judged"] = judged
    problems = evidence_problems(rec)
    if not problems:
        found = currency(root, rec, vpath)
        if found and (found[0] == "error" or args.result == "passed"):
            problems.append(f"{found[0]}: {found[1]}")
    if problems:
        report.diagnostics.extend(label + p for p in problems)
        return None
    digest = []
    if rec["evidence_path"] and not is_url(rec["evidence_path"]) \
            and evidence_file(root, rec["evidence_path"], digest) is None and digest:
        rec["evidence_sha256"] = digest[0]
    if rec["result"] == "passed" and rec.get("evidence_sha256"):
        state = (rec["source_revision_or_target_fingerprint"], rec["inputs"])
        if any(d == rec["evidence_sha256"] and s != state
               for d, s in archived_states(archive_path(vpath)).get(pair(rec), [])):
            return refuse("stale: evidence reused: the cited file is unchanged from an archived record of this "
                          "check made on a different target state, so no new run is shown; re-run the check "
                          "and record its new output")
    markers = data.get("runs_in_progress") if isinstance(data.get("runs_in_progress"), list) else []
    begun = [m for m in markers if marker_applies(m, rec["check_id"], rec["target"], args.mode)]
    for m in begun:
        if m.get("fingerprint") and current is not None and m["fingerprint"] != current:
            return refuse(f"stale: the target changed after `begin` at {m.get('started', '?')}, so the run may "
                          "have judged other content (or --exclude differs from the one given to begin); "
                          "`begin` again, re-run the check and record that run")
        changed = [k for k, v in (m.get("inputs") or {}).items() if k in inputs and inputs[k] != v]
        if changed:
            return refuse(f"stale: input {changed[0]} changed after `begin` at {m.get('started', '?')}; "
                          "`begin` again, re-run the check and record that run")
    if begun:
        data["runs_in_progress"] = [m for m in markers if not any(m is b for b in begun)]
    if args.require:   # adds a missing requirement (every mode); never narrows an existing one
        set_requirement(data, args.check_id, args.target, list(DELIVERY_MODES),
                        f"added by record --require ({args.tool_and_version})", existing_only=True)
    same = None if getattr(args, "append_unchanged", False) else unchanged_from(data["records"], rec, root, vpath)
    if same is not None:
        return Unchanged(same)
    data["records"].append(rec)
    return rec


class Unchanged(dict):
    """What `add_record` returns instead of appending: the newest record of the same check, target and
    mode already says the same about the same target state, so it stays the deciding record."""


# Fields an identical rerun may differ in: when it ran and the output file it wrote (helper output
# carries its own timestamp and duration, so its hash differs on every run).
RERUN_FIELDS = ("timestamp", "evidence_path", "evidence_sha256")


def unchanged_from(records, rec, root, vpath):
    """The current record that `rec` would only repeat, or None. It must be the newest record of the pair
    in rec's mode with no later record of the pair that counts for the same mode, still current and
    sound, and equal to `rec` in every field but RERUN_FIELDS. When both cite the same evidence file and
    the file changed, the old record no longer matches its file, so nothing is reused."""
    mode = rec.get("mode")
    for old in reversed(records):
        if not isinstance(old, dict) or pair(old) != pair(rec):
            continue
        if old.get("mode") != mode:
            if old.get("mode") is None or mode is None:
                return None     # a later record that counts for this mode too decides; append after it
            continue
        strip = lambda r: {k: v for k, v in r.items() if k not in RERUN_FIELDS}  # noqa: E731
        if strip(old) != strip(rec) or evidence_problems(old) or currency(root, old, vpath):
            return None
        if old.get("evidence_path") == rec.get("evidence_path") \
                and old.get("evidence_sha256") != rec.get("evidence_sha256"):
            return None
        return old
    return None


BATCH_LISTS = ("input", "exclude", "judged")
BATCH_FLAGS = ("require", "allow_website_exclusion", "inputs_from_page", "append_unchanged")
BATCH_KEYS = RECORD_REQUIRED + BATCH_LISTS + BATCH_FLAGS + (
    "required_or_optional", "evidence_path", "finding", "limitations", "issue_id", "skip_reason",
    "fingerprint", "mode", "sample_scope", "site")


def batch_argvs(path):
    """Record option lists from a batch file: {"defaults": {...}, "records": [{...}, ...]} or a bare list,
    keyed by option name with underscores (check_id, target, input: [...], require: true, ...)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    defaults, entries = ({}, raw) if isinstance(raw, list) else (raw.get("defaults") or {}, raw.get("records"))
    if not isinstance(entries, list) or not entries or not isinstance(defaults, dict):
        raise ValueError("a batch file holds a non-empty `records` list (and optional `defaults` object)")
    argvs = []
    for n, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"batch entry {n} is not an object")
        merged = {**defaults, **entry}
        unknown = sorted(set(merged) - set(BATCH_KEYS))
        if unknown:
            raise ValueError(f"batch entry {n}: unknown keys {', '.join(unknown)}")
        argv = []
        for key, value in merged.items():
            flag = "--" + key.replace("_", "-")
            if key in BATCH_FLAGS:
                if value is True:
                    argv.append(flag)
                elif value not in (False, None):
                    raise ValueError(f"batch entry {n}: {key} must be true or false")
            elif key in BATCH_LISTS:
                values = value if isinstance(value, list) else [value]
                if not all(isinstance(v, str) for v in values):
                    raise ValueError(f"batch entry {n}: {key} must be a path or a list of paths")
                for v in values:
                    argv += [flag, v]
            elif isinstance(value, str):
                argv += [flag, value]
            elif value is not None:
                raise ValueError(f"batch entry {n}: {key} must be a string")
        argvs.append(argv)
    return argvs


def load_for_record(vpath):
    data = json.loads(vpath.read_text(encoding="utf-8")) if vpath.exists() else \
        {"schema_version": 1, "required_checks": [], "waivers": [], "records": []}
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    data.setdefault("records", [])
    return data


def record_many(verification, root, argvs, report, before_write=None, resolve=None):
    """Validate every option list, then append them all with one atomic write; nothing is written when
    any entry is refused. `before_write(data)` may amend the file in the same write (a helper's
    retirements); with `resolve` (finding location -> path) the run's warnings update
    `recurring_warnings` in that write too. Returns (records added, number archived, records left
    unchanged) or None."""
    vpath = Path(verification)
    try:
        data = load_for_record(vpath)
    except (OSError, ValueError) as exc:
        report.diagnostics.append(f"cannot read verification record: {exc}")
        return None
    added, unchanged = [], []
    for n, argv in enumerate(argvs):
        try:
            args = record_parser().parse_args(argv)
        except ValueError as exc:
            report.diagnostics.append(f"entry {n}: {exc}")
            return None
        rec = add_record(data, args, root, vpath, report, label=f"entry {n} ({args.check_id} {args.target}): "
                         if len(argvs) > 1 else "")
        if rec is None:
            if len(argvs) > 1:
                report.diagnostics.append("nothing written: a batch is recorded whole or not at all")
            return None
        (unchanged if isinstance(rec, Unchanged) else added).append(rec)
    archived = roll_superseded(data, root, vpath, {pair(r) for r in added})
    if before_write is not None:
        before_write(data)
    if resolve is not None:
        track_recurring(data, Path(root), report.findings, resolve, [(r["check_id"], r["target"]) for r in added + unchanged])
    write_json_atomic(vpath, data)   # also when nothing was added: begin markers and requirements may change
    return added, archived, unchanged



def target_holds(target, rel):
    """True when a record target (a file, a folder, "." or a file-set glob) covers the project path rel."""
    t = str(target).rstrip("/")
    if is_glob(t):
        return fnmatch.fnmatchcase(rel, t)
    return t in (".", "") or rel == t or rel.startswith(t + "/")


def track_recurring(data, root, findings, resolve, covered, now=None):
    """Count how many helper runs in a row reported the same warning (same check ID, file and evidence
    text; line numbers are ignored because edits move them). Accepted warnings never reach this (the helper
    moved them out of findings first). A stored warning that this run covered (a record of its check whose
    target holds its file) but did not report, or whose file is gone, is dropped, so the map holds only
    warnings that are still open."""
    now = now or now_iso()
    old = data.get("recurring_warnings")
    old = old if isinstance(old, dict) else {}
    seen = {}
    for f in findings:
        if not isinstance(f, dict) or f.get("severity") != "warning":
            continue
        try:
            path = resolve(str(f.get("location", "")).split(":")[0])
            rel = project_rel(root, path) if path is not None else None
        except (OSError, ValueError):
            rel = None
        check = f.get("check_id")
        if not rel or not any(c == check and target_holds(t, rel) for c, t in covered):
            continue
        evidence = str(f.get("evidence", ""))[:300]
        key = f"{check}|{rel}|{evidence}"
        prev = old.get(key) if isinstance(old.get(key), dict) else {}
        seen[key] = {"check_id": check, "location": rel, "evidence": evidence,
                     "first_seen": prev.get("first_seen", now), "last_seen": now,
                     "runs": (prev.get("runs") if isinstance(prev.get("runs"), int) else 0) + 1}
    kept = {}
    for key, entry in old.items():
        if key in seen or not isinstance(entry, dict):
            continue
        loc, check = str(entry.get("location", "")), entry.get("check_id")
        if any(c == check and target_holds(t, loc) for c, t in covered) or not (root / loc).exists():
            continue   # covered and not reported: fixed or accepted; or the file is gone
        kept[key] = entry
    kept.update(seen)
    if kept:
        data["recurring_warnings"] = dict(sorted(kept.items()))
    else:
        data.pop("recurring_warnings", None)


def update_recurring(verification, root, findings, resolve, covered):
    """For a helper that records check by check (the WordPress theme checker): one more atomic write that
    updates `recurring_warnings` after its records are in."""
    vpath = Path(verification)
    try:
        data = load_for_record(vpath)
    except (OSError, ValueError):
        return
    track_recurring(data, Path(root), findings, resolve, covered)
    write_json_atomic(vpath, data)


def recurring_list(data):
    """The warnings status reports: seen in at least RECURRING_RUNS helper runs in a row."""
    found = data.get("recurring_warnings")
    items = [e for e in found.values() if isinstance(e, dict) and isinstance(e.get("runs"), int)
             and e["runs"] >= RECURRING_RUNS] if isinstance(found, dict) else []
    return [dict(e, action="fix it, or ask the user once whether to accept it (sw_records.py accept-finding)")
            for e in sorted(items, key=lambda e: (-e["runs"], str(e.get("check_id")), str(e.get("location"))))]


def keep_cited_evidence(verification, evidence_rel, evidence_out):
    """After a helper recorded its run: delete the evidence file it just wrote when no record cites it
    (every check was unchanged, so the older records and their files still decide). True when kept."""
    try:
        data = load_for_record(Path(verification))
    except (OSError, ValueError):
        return True
    if any(isinstance(r, dict) and r.get("evidence_path") == evidence_rel for r in data.get("records", [])):
        return True
    Path(evidence_out).unlink(missing_ok=True)
    return False


def load_acceptances(verification):
    """The `accepted_findings` of a verification file; [] when the file or the list is absent or unreadable
    (a helper run never fails over it)."""
    try:
        data = json.loads(Path(verification).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    found = data.get("accepted_findings") if isinstance(data, dict) else None
    return [a for a in found if isinstance(a, dict)] if isinstance(found, list) else []


def apply_acceptances(findings, acceptances, root, resolve, today=None):
    """Split off the warnings the user accepted. A finding matches an acceptance when the check ID is the
    same, its file (`resolve(location file)`, a path) is the acceptance target or lies inside that folder,
    and the acceptance `match` text occurs in its evidence. Defects are never moved (an unmet check needs a
    fix or a waiver); an expired acceptance leaves the finding in place. Returns (kept, accepted, notes)."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    live, notes = [], []
    for a in acceptances:
        if not all(isinstance(a.get(k), str) and a.get(k).strip() for k in ("check_id", "target", "match")):
            continue
        until = waiver_date(a["expires"]) if a.get("expires") else None
        if a.get("expires") and (until is None or until < today):
            notes.append(f"the acceptance of {a['check_id']} on {a['target']} ({a['match']!r}) expired on "
                         f"{a['expires']}: its findings are reported again; fix them or ask the user to renew it")
            continue
        live.append(a)
    kept, accepted = [], []
    for f in findings:
        hit = None
        if live and isinstance(f, dict):
            try:
                path = resolve(str(f.get("location", "")).split(":")[0])
                rel = project_rel(root, path) if path is not None else None
            except (OSError, ValueError):
                rel = None
            for a in live:
                t = a["target"].rstrip("/")
                if (a["check_id"] == f.get("check_id") and rel and (rel == t or rel.startswith(t + "/") or t == ".")
                        and a["match"] in str(f.get("evidence", ""))):
                    hit = a
                    break
        if hit and f.get("severity") != "warning":
            notes.append(f"{f.get('check_id')} at {f.get('location')} is a defect: an acceptance never covers "
                         "a defect; fix it, or the user waives the check")
            hit = None
        if hit:
            accepted.append(dict(f, accepted={k: hit[k] for k in ("reason", "decided_by", "timestamp", "expires")
                                              if k in hit}))
        else:
            kept.append(f)
    return kept, accepted, notes


def accept_findings(report, resolve, record=None, records_dir=None, root=None):
    """For the helpers: move the warnings the user accepted out of `report.findings`. The acceptances come
    from --record, else verification.json in --records. Returns the accepted findings, or None when the
    file holds no acceptances (the output then has no `accepted` key)."""
    vpath = Path(record) if record else Path(records_dir) / "verification.json" if records_dir else None
    acceptances = load_acceptances(vpath) if vpath else []
    if not acceptances:
        return None
    root = Path(root) if root else default_root(vpath)
    report.findings, accepted, notes = apply_acceptances(report.findings, acceptances, root, resolve)
    report.diagnostics.extend(notes)
    return accepted


def cmd_begin(args):
    """Mark checks as running before a multi-step (browser or manual) run starts. The marker keeps the
    target and input fingerprints seen at the start: the gate reports the pair as `error` until `record`
    clears it, and `record` refuses a result whose target or inputs changed meanwhile."""
    report = Report(args.verification)
    vpath = Path(args.verification)
    root = Path(args.root) if args.root else default_root(vpath)
    try:
        data = load_for_record(vpath)
    except (OSError, ValueError) as exc:
        report.diagnostics.append(f"cannot read verification record: {exc}")
        return report.emit("error")
    if not CHECK_ID_RE.match(args.check_id or ""):
        report.diagnostics.append(f"check ID {args.check_id[:80]!r} must be letters, digits, '.', '_' or '-'")
        return report.emit("error")
    if args.exclude and len(args.target) > 1:
        report.diagnostics.append("--exclude takes a single --target")
        return report.emit("error")
    markers = [m for m in data.get("runs_in_progress") or [] if isinstance(m, dict)]
    targets = list(dict.fromkeys(args.target))
    kept = [m for m in markers if not any(marker_applies(m, args.check_id, t, args.mode) for t in targets)]
    if args.cancel:
        data["runs_in_progress"] = kept
        write_json_atomic(vpath, data)
        return report.emit("passed", {"cancelled": len(markers) - len(kept)})
    inputs = {}
    for given in args.input:
        path, err = resolve_target(root, given)
        if err or not path.exists():
            report.diagnostics.append(f"input {given}: {err or 'not found'}")
            return report.emit("error")
        inputs[project_rel(root, path)] = fingerprint(path)
    started, added = now_iso(), []
    for target in targets:
        marker = {"check_id": args.check_id, "target": target, "started": started}
        if args.mode:
            marker["mode"] = args.mode
        if is_glob(target):
            matched = glob_files(root, target)
            if matched:
                marker["fingerprint"] = glob_fingerprint(matched)
        elif not is_url(target):
            path, err = resolve_target(root, target)
            if err or not (path.exists() or path.is_symlink()):
                report.diagnostics.append(err or f"target not found: {target}")
                return report.emit("error")
            skip = []
            for given in args.exclude:
                excluded, err = resolve_target(root, given)
                if err or not path.is_dir() or not covers(path, excluded):
                    report.diagnostics.append(f"exclusion {given} must lie inside the target folder")
                    return report.emit("error")
                skip.append(excluded.resolve().relative_to(path.resolve()).as_posix())
            marker["fingerprint"] = fingerprint(path, skip)
        if inputs:
            marker["inputs"] = inputs
        added.append(marker)
    data["runs_in_progress"] = kept + added
    write_json_atomic(vpath, data)
    return report.emit("passed", {"begun": added})

def cmd_record(args):
    report = Report(args.verification)
    root = Path(args.root) if args.root else default_root(args.verification)
    if args.batch:
        defaults = vars(record_parser().parse_args([]))
        if any(getattr(args, k) != v for k, v in defaults.items()):
            report.diagnostics.append("--batch takes every record option from the batch file")
            return report.emit("error")
        try:
            argvs = batch_argvs(args.batch)
        except (OSError, ValueError) as exc:
            report.diagnostics.append(f"cannot read batch file {args.batch}: {exc}")
            return report.emit("error")
    else:
        argvs = None
    if argvs is None:
        vpath = Path(args.verification)
        try:
            data = load_for_record(vpath)
        except (OSError, ValueError) as exc:
            report.diagnostics.append(f"cannot read verification record: {exc}")
            return report.emit("error")
        rec = add_record(data, args, root, vpath, report)
        if rec is None:
            return report.emit("error")
        same = isinstance(rec, Unchanged)
        archived = 0 if same else roll_superseded(data, root, vpath, {pair(rec)})
        write_json_atomic(vpath, data)
        return report.emit("passed", {"record": dict(rec), "unchanged": same, "archived": archived})
    done = record_many(args.verification, root, argvs, report)
    if done is None:
        return report.emit("error", {"written": False})
    added, archived, unchanged = done
    return report.emit("passed", {"recorded": len(added), "unchanged": len(unchanged), "archived": archived,
                                  "records": [{"check_id": r["check_id"], "target": r["target"],
                                               "result": r["result"]} for r in added]})


def cmd_fingerprint(args):
    report = Report(" ".join(args.paths))
    out = {}
    for p in args.paths:
        try:
            out[p] = fingerprint(p)
        except FileNotFoundError:
            report.diagnostics.append(f"not found: {p}")
    if report.diagnostics:
        return report.emit("error", {"fingerprints": out})
    return report.emit("passed", {"fingerprints": out})


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sw_records.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("fingerprint")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_fingerprint)
    p = sub.add_parser("check-records")
    p.add_argument("dir")
    p.add_argument("--phase", choices=PHASES)
    p.set_defaults(func=cmd_check_records)
    p = sub.add_parser("check-state")
    p.add_argument("state")
    p.add_argument("--root", help="project root for artifact paths (default: the folder above docs/website/ for a state file kept there, else its directory)")
    p.add_argument("--quick", action="store_true",
                   help=f"report artifact folders over {QUICK_FILE_BUDGET} files as not checked (session hook)")
    p.set_defaults(func=cmd_check_state)
    p = sub.add_parser("gate")
    p.add_argument("verification")
    p.add_argument("--root", help="project root for relative targets (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.add_argument("--mode", choices=DELIVERY_MODES, default="production",
                   help="delivery criteria to gate against (default: production, the strictest)")
    p.add_argument("--state", help="state record whose open blocking issues fail the gate "
                   "(default: state.json beside the verification file)")
    p.add_argument("--stage", choices=STAGES, help="also assess launch-stage checks (production mode only)")
    p.set_defaults(func=cmd_gate)
    p = sub.add_parser("status")
    p.add_argument("verification")
    p.add_argument("--root", help="project root for relative targets (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.add_argument("--mode", choices=DELIVERY_MODES, default="production")
    p.add_argument("--stage", choices=STAGES, help="also assess launch-stage checks (production mode only)")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("compact")
    p.add_argument("verification")
    p.add_argument("--archive", help="project-relative archive file (default: the append-only "
                                     "verification-archive.jsonl beside the verification file)")
    p.add_argument("--root", help="project root (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.add_argument("--write", action="store_true", help="move the records (default: dry run)")
    p.set_defaults(func=cmd_compact)
    p = sub.add_parser("retire", help="stop requiring checks on targets that were removed or moved (no decider needed)")
    p.add_argument("verification")
    p.add_argument("--root", help="project root (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.add_argument("--target", action="append", default=[], help="removed target as recorded (repeatable)")
    p.add_argument("--all-missing", action="store_true", help="every required target that no longer exists")
    p.add_argument("--reason", required=True, help="why the target is gone, e.g. 'service pages moved to Notion'")
    p.add_argument("--replaced-by", default="", help="where the content lives now (a URL), if anywhere")
    p.add_argument("--write", action="store_true", help="write the change (default: dry run)")
    p.set_defaults(func=cmd_retire)
    p = sub.add_parser("prune-evidence", help="once the gate passes, delete evidence files no record cites")
    p.add_argument("verification")
    p.add_argument("--root", help="project root (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.add_argument("--mode", choices=DELIVERY_MODES, default="production", help="the gate that must pass first")
    p.add_argument("--current-only", action="store_true",
                   help="archive superseded records, then prune what the current records don't cite; no passing "
                        "gate needed (refused while a run is in progress)")
    p.add_argument("--write", action="store_true", help="archive and delete (default: dry run)")
    p.set_defaults(func=cmd_prune_evidence)
    p = sub.add_parser("require", help="add, change or remove a required check (logged in requirement_history)")
    p.add_argument("verification")
    p.add_argument("--check-id", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--modes", help="gates that require it: mockup,production (default for a new requirement), "
                                   "production or mockup")
    p.add_argument("--remove", action="store_true", help="stop requiring it in every mode (needs --decided-by)")
    p.add_argument("--stage", choices=(*STAGES, "every"),
                   help="launch: assess it only at the launch stage (production; moving an existing check there "
                        "needs --decided-by); every: back to every gate")
    p.add_argument("--reason", required=True, help="why the requirement changes (kept in requirement_history)")
    p.add_argument("--decided-by", default="", help="who decided; required when a change stops requiring a mode")
    p.add_argument("--decision", default="", help="instead of --decided-by: an active accepted decision in "
                                                  "state.json whose `source` records who made it")
    p.add_argument("--root", help="project root for relative targets (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.set_defaults(func=cmd_require)
    p = sub.add_parser("waive", help="record the user's waiver of a required check (logged in requirement_history)")
    p.add_argument("verification")
    p.add_argument("--check-id", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--reason", required=True, help="why the check is accepted as unmet")
    p.add_argument("--decided-by", default="", help="the user who accepts it; required to grant, never filled in by an agent")
    p.add_argument("--owner", default="", help="who follows the waived check up")
    p.add_argument("--expires", help="YYYY-MM-DD; after it the check reads stale until renewed or run")
    p.add_argument("--scope", help="gate levels it counts in: mockup, production, launch (comma-separated; default all)")
    p.add_argument("--remove", action="store_true", help="withdraw the waiver")
    p.add_argument("--root", help="project root for relative targets (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.set_defaults(func=cmd_waive)
    p = sub.add_parser("accept-finding", help="record the user's acceptance of one warning (logged in "
                                              "requirement_history); never a defect")
    p.add_argument("verification")
    p.add_argument("--check-id", required=True, help="one check ID, no wildcard")
    p.add_argument("--target", required=True, help="one file or folder in the project, no glob")
    p.add_argument("--match", required=True, help="text that occurs in the finding's evidence")
    p.add_argument("--reason", required=True, help="why it is a false positive or an accepted exception")
    p.add_argument("--decided-by", default="", help="the user who accepts it; required to grant, never filled in by an agent")
    p.add_argument("--expires", help="YYYY-MM-DD; after it the finding is reported again")
    p.add_argument("--remove", action="store_true", help="withdraw the acceptance")
    p.add_argument("--root", help="project root for relative targets (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.set_defaults(func=cmd_accept_finding)
    p = sub.add_parser("begin", help="mark a multi-step check run as started (gate: error until recorded)")
    p.add_argument("verification")
    p.add_argument("--check-id", required=True)
    p.add_argument("--target", action="append", required=True, help="repeatable: every target the run covers")
    p.add_argument("--input", action="append", default=[], help="inputs whose change during the run voids it")
    p.add_argument("--exclude", action="append", default=[], help="as on record (single --target only)")
    p.add_argument("--mode", choices=DELIVERY_MODES)
    p.add_argument("--cancel", action="store_true", help="drop the markers instead (the run won't happen)")
    p.add_argument("--root", help="project root for relative targets (default: the folder above docs/website/ for a record kept there, else the file's directory; pass --root . from the project root)")
    p.set_defaults(func=cmd_begin)
    p = sub.add_parser("record")
    p.add_argument("verification")
    add_record_options(p)
    p.add_argument("--batch", metavar="FILE.json",
                   help="record every entry of this file in one write, all or nothing (see batch_argvs)")
    p.add_argument("--root")
    p.set_defaults(func=cmd_record)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        return args.func(args)
    except Exception as exc:  # report, never pass silently
        report = Report("")
        report.diagnostics.append(f"{type(exc).__name__}: {exc}")
        return report.emit("error")


if __name__ == "__main__":
    sys.exit(main())
