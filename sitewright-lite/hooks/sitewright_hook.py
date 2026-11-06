#!/usr/bin/env python3
"""Sitewright hook wrapper: thin event adapters over scripts/sw_records.py.

Usage (from hooks/hooks.json): sitewright_hook.py post-write | session-start [--data DIR] | stop

A project takes part only when <project>/docs/website/state.json exists; every
other project is skipped silently. The wrapper only reads project files and runs the
read-only helper commands (check-records, check-state, gate), so it never writes to
a project and never triggers itself. It writes nothing. Children run with SITEWRIGHT_HOOK=1 set, and
the wrapper exits at once when it sees that variable.

post-write (PostToolUse on Write|Edit|MultiEdit): after a write to a record in
  docs/website/ (*.md, state.json, verification.json), run the matching helper and
  report this file's defects. The write is already on disk, so the hook cannot
  prevent or undo it.
    exit 0, no output   skipped, or no defects in the written record
    exit 2, stderr      defects in the written record, or the check could not
                        complete (helper crash, timeout, malformed output); Claude sees it
    exit 1, stderr      the hook input is unusable; one-line diagnostic (hook error notice)
  In verification.json only `error` results (malformed evidence) are reported;
  missing, stale or failed evidence is normal while a build is under way.

session-start (SessionStart): when state.json sets "session_summary": true, print
  a compact state summary on stdout (added to Claude's context): scope, phase,
  next action, blocking issues, artefact freshness and the evidence gate result.
  Exit 0 always; an unreadable state or a helper error is reported as a line.

stop (Stop): when state.json declares current_phase "handoff" for a build scope,
  run the evidence gate on the listed verification records. Anything but a fresh
  pass (missing, failed, stale, skipped, error, no record) blocks the stop once
  with a reason that names each check by its result. When stop_hook_active is true
  (Claude is already continuing because of a stop hook) it never blocks again, so
  an unresolved condition cannot loop; the reason tells Claude to report the
  exact remaining checks instead of claiming completion.

Every listed verification record is checked. An entry that is not a usable path
or resolves outside the project is reported, never read. When the hook deadline
(or the list bound) stops it before the end of the list, it says verification is
incomplete and names what was not checked; it never passes on a partial list.

Time budget: each helper 8 s, the whole hook 20 s, inside the 30 s timeouts in
hooks/hooks.json.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True                   # read-only: never leave __pycache__ in the plugin
sys.path.insert(0, str(Path(__file__).resolve().parent))
import re  # noqa: E402
import shlex  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "scripts" / "sw_records.py"
OWNERS = Path(__file__).resolve().parent / "owners.txt"   # this edition's request owners
OWNER_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_OWNERS_LINE = 700
REENTRY = "SITEWRIGHT_HOOK"
HELPER_TIMEOUT = 8
HOOK_DEADLINE = 20          # must stay below the hooks.json timeouts (30)
MAX_LINES = 20
MAX_LINE = 300
MAX_REASON = 2000
MAX_STATE_BYTES = 1_000_000
MAX_VERIFICATION_FILES = 64  # sanity bound; a longer list is reported as incomplete, never cut silently
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}
NO_BUILD_SCOPES = {"plan-only", "design-only", "review-only"}
RESULT_WORDS = ("passed", "failed", "unavailable", "error", "stale", "skipped")
DELIVERY_MODES = ("mockup", "production")
DECISION_ID = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
STARTED = time.monotonic()


class BadInput(Exception):
    pass


NEXT_ACTION_MAX = 200
CLIPPED = " …[line truncated]"


def clip(line):
    return line if len(line) <= MAX_LINE else line[:MAX_LINE - len(CLIPPED)] + CLIPPED


def next_action_line(value):
    """The next action, or its first NEXT_ACTION_MAX characters with an explicit truncation notice: the
    summary is bounded, so resume must read the complete next_action from state.json."""
    if not isinstance(value, str) or not value.strip():
        return "- next action: unknown"
    text = " ".join(value.split())
    if len(text) <= NEXT_ACTION_MAX:
        return f"- next action: {text}"
    return (f"- next action: {text[:NEXT_ACTION_MAX]} …[truncated: {NEXT_ACTION_MAX} of {len(text)} characters; "
            "read the full next_action in docs/website/state.json before acting]")


def handover_line(data, state, project):
    """Where the handover file is (state.json `handover`, else HANDOVER.md beside state.json)."""
    rel = data.get("handover")
    if isinstance(rel, str) and rel and not rel.startswith("/") and ".." not in rel.split("/"):
        path = project / rel
    else:
        path, rel = state.parent / "HANDOVER.md", "docs/website/HANDOVER.md"
    try:
        found = path.is_file() and within(path.resolve(), project)
    except OSError:
        found = False
    if found:
        return f"- handover: {rel}; read it before acting"
    return f"- handover: {rel} is missing; write it at the next checkpoint"


def owner_lines(data):
    """The next step's owner (state.json `next_owner`) and this edition's owners by request, so the
    routing survives compaction: the summary is the one text that is re-sent after it."""
    lines = []
    owner = data.get("next_owner")
    if isinstance(owner, str) and OWNER_NAME.match(owner):
        lines.append(f"- next owner: {owner}; invoke it with the Skill tool before acting on next_action")
    try:
        rows = [r.split(":", 1) for r in OWNERS.read_text(encoding="utf-8").splitlines()
                if ":" in r and not r.lstrip().startswith("#")]
    except OSError:
        rows = []
    if rows:
        text = "- owners by request: " + "; ".join(f"{a.strip()} -> {s.strip()}" for a, s in rows)
        lines.append(text if len(text) <= MAX_OWNERS_LINE else text[:MAX_OWNERS_LINE - len(CLIPPED)] + CLIPPED)
    return lines


def bounded(lines):
    shown = lines[:MAX_LINES]
    if len(lines) > MAX_LINES:
        shown.append(f"  … and {len(lines) - MAX_LINES} more; run sw_records.py for the full list")
    return [clip(l) for l in shown]


def stderr_exit(code, lines):
    sys.stderr.write("\n".join(bounded(lines)) + "\n")
    sys.exit(code)


def within(path, base):
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def read_event(expected):
    raw = sys.stdin.read()
    if not raw.strip():
        raise BadInput("empty stdin")
    try:
        event = json.loads(raw)
    except ValueError as e:
        raise BadInput(f"not JSON: {e.msg} at position {e.pos}")
    if not isinstance(event, dict):
        raise BadInput(f"expected a JSON object, got {type(event).__name__}")
    name = event.get("hook_event_name")
    if name is not None and not isinstance(name, str):
        raise BadInput("hook_event_name is not a string")
    if name is not None and name != expected:
        return None, None                         # registered for another event
    cwd = event.get("cwd")
    if cwd is not None and not isinstance(cwd, str):
        raise BadInput("cwd is not a string")
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd()).resolve()
    return event, project


def participating(project):
    """The project's state.json, or None when the project does not use Sitewright records."""
    state = project / "docs" / "website" / "state.json"
    if not state.is_file() or not within(state.resolve(), project):
        return None
    return state


def load_state(state):
    try:
        if state.stat().st_size > MAX_STATE_BYTES:
            return None, f"larger than {MAX_STATE_BYTES} bytes"
        data = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        return None, f"cannot read it ({e})"
    except ValueError as e:
        return None, f"not valid JSON ({e.msg} at line {e.lineno})"
    if not isinstance(data, dict):
        return None, "not a JSON object"
    return data, None


def remaining():
    return HOOK_DEADLINE - (time.monotonic() - STARTED)


def helper(*args):
    """Run sw_records.py; return (report, None) or (None, why it is not usable)."""
    budget = min(HELPER_TIMEOUT, remaining())
    if budget <= 0.5:
        return None, "not run: hook deadline reached"
    if not RECORDS.is_file():
        return None, "unavailable: sw_records.py is not installed"
    env = dict(os.environ, **{REENTRY: "1"})
    p = subprocess.Popen([sys.executable, str(RECORDS), *map(str, args)], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, text=True, env=env,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=budget)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
        p.communicate()
        return None, f"error: timed out after {budget:.0f}s"
    try:
        report = json.loads(out)
        result = report["result"]
        assert result in RESULT_WORDS and isinstance(report.get("findings", []), list)
    except (ValueError, KeyError, TypeError, AssertionError):
        detail = (err.strip().splitlines() or ["no output"])[-1]
        return None, f"error: malformed helper output (exit {p.returncode}: {detail})"
    if args[0] == "gate":            # the gate exits 0 only on a fresh pass; 2 when it cannot read its input
        allowed = {0} if result == "passed" else {1, 2} if result == "error" else {1}
    else:
        allowed = {0} if result in ("passed", "skipped") else {1} if result == "failed" else {2}
    if p.returncode not in allowed:
        return None, f"error: helper said {result} but exited {p.returncode}"
    return report, None


def verification_paths(state_data, state, project):
    """(paths, problems): every listed record that resolves inside the project, and why any entry
    cannot be used. Nothing outside the project is read."""
    listed = state_data.get("verification_records")
    if listed is None:
        return [], []
    if isinstance(listed, str):
        listed = [listed]
    if not isinstance(listed, list):
        return [], [f"verification_records is a {type(listed).__name__}, not a list of paths"]
    paths, problems, seen = [], [], set()
    for i, item in enumerate(listed):
        if i == MAX_VERIFICATION_FILES:
            problems.append(f"verification incomplete: {len(listed) - i} further listed record(s) were not "
                            f"checked (the hook checks at most {MAX_VERIFICATION_FILES})")
            break
        if not isinstance(item, str) or not item.strip() or "\0" in item:
            problems.append(f"verification_records entry {i + 1} ({repr(item)[:60]}) is not a usable path")
            continue
        p = Path(item)
        if not p.is_absolute():
            near = state.parent / p
            p = near if near.exists() else project / p
        try:
            real = p.resolve()
        except (OSError, RuntimeError, ValueError):
            real = None
        if real is None or not within(real, project):
            problems.append(f"{item[:120]}: resolves outside the project, so it was not read")
            continue
        if real not in seen:
            seen.add(real)
            paths.append(p)
    return paths, problems


def rel(path, project):
    try:
        return str(path.resolve().relative_to(project))
    except ValueError:
        return str(path)


# ---------- post-write ----------

def post_write():
    event, project = read_event("PostToolUse")
    if event is None:
        return
    tool = event.get("tool_name")
    if tool is not None and tool not in WRITE_TOOLS:
        return
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise BadInput("tool_input missing or not an object")
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path.strip():
        raise BadInput("tool_input.file_path missing or not a string")
    state = participating(project)
    if state is None:
        return
    records_dir = state.parent
    cwd = event.get("cwd") or os.getcwd()
    path = Path(file_path)
    path = (path if path.is_absolute() else Path(cwd) / path).resolve()
    if path.parent != records_dir.resolve() or not path.is_file():
        return
    name = path.name
    head = f"sitewright records check — {name}"
    if name.endswith(".md"):
        report, why = helper("check-records", records_dir)
    elif name == "state.json":
        report, why = helper("check-state", state, "--root", project)
    elif name == "verification.json":
        report, why = helper("gate", path, "--root", project)
    else:
        return
    if why:
        stderr_exit(2, [f"{head}: {why}; this write is not verified."])

    if name == "verification.json":
        broken = [c for c in report.get("checks", []) + report.get("optional", [])
                  if isinstance(c, dict) and c.get("result") == "error"]
        if broken:
            stderr_exit(2, [f"{head}: {len(broken)} evidence record(s) cannot be trusted as written. "
                            "The write is already on disk; repair or re-record them:",
                            *[f"  {c.get('check_id')} {c.get('target')}: {c.get('reason')}" for c in broken]])
        if report["result"] == "error":
            detail = "; ".join(report.get("diagnostics", [])) or "the gate could not read it"
            stderr_exit(2, [f"{head}: error ({detail}). The write is already on disk; repair the record."])
        return

    if report["result"] == "error":
        detail = "; ".join(report.get("diagnostics", [])) or "no detail"
        stderr_exit(2, [f"{head}: error ({detail}); this write is not verified."])
    mine, others = [], 0
    for f in report.get("findings", []):
        if not isinstance(f, dict) or f.get("severity") != "defect":
            continue
        loc = str(f.get("location", ""))
        if name.endswith(".md") and loc.split(":")[0] not in (name, str(path)):
            others += 1
            continue
        mine.append(f"  {loc} {f.get('check_id')}: {f.get('evidence')} → {f.get('action')}")
    if not mine:
        return
    tail = [f"  ({others} defect(s) in other records are not from this write)"] if others else []
    stderr_exit(2, [f"{head}: failed. The write is already on disk (this hook cannot undo it). "
                    "Fix these in the record; the check runs again on the next write:", *mine, *tail])


# ---------- session-start ----------

def gate_command(path, project, mode):
    """The complete gate command to run from the project root (script path, --root and --mode included),
    so nobody has to rebuild it from prose."""
    return shlex.join(["python3", str(RECORDS), "gate", rel(path, project), "--root", ".", "--mode", mode])


def not_passed(report):
    return {(c.get("check_id"), c.get("target")): c.get("result") for c in report.get("checks", [])
            if c.get("result") not in ("passed", "waived")}


def production_only_line(path, project, current):
    """For a mock-up: what the production gate adds beyond the mock-up's own unmet checks, labelled as
    production-only so it is never read as a failure of the current criteria."""
    report, why = helper("gate", path, "--root", project, "--mode", "production")
    if why:
        return [f"- production-only blockers ({rel(path, project)}): {why}"]
    extra = {k: r for k, r in not_passed(report).items() if k not in not_passed(current)}
    if not extra:
        return [f"- production-only blockers ({rel(path, project)}): none beyond the mock-up's own unmet checks"]
    by_result = {}
    for (check_id, target), result in sorted(extra.items()):
        by_result.setdefault(result, {}).setdefault(check_id, []).append(target)
    # grouped by check ID so a whole site's worth of pages fits in one bounded line; one page is named
    detail = "; ".join(f"{r} {sum(map(len, ids.values()))}: " + ", ".join(
        f"{c} ×{len(t)}" if len(t) > 1 else f"{c} {t[0]}" for c, t in sorted(ids.items()))
        for r, ids in sorted(by_result.items()))
    return [f"- production-only blockers ({rel(path, project)}; not part of the mock-up criteria, expected "
            f"until production work): {len(extra)} ({detail})"]


def gate_lines(state_data, state, project):
    paths, problems = verification_paths(state_data, state, project)
    if not paths and not problems:
        return ["- evidence gate: no verification record listed yet"]
    lines = [f"- evidence gate: {p}" for p in problems]
    unchecked = []
    mode = delivery_mode(state_data)
    for p in paths:
        if not p.is_file():
            lines.append(f"- evidence gate ({rel(p, project)}): unavailable, the file does not exist")
            continue
        report, why = helper("gate", p, "--root", project, "--mode", mode)
        if why and why.startswith("not run"):
            unchecked.append(rel(p, project))
            continue
        if why:
            lines.append(f"- evidence gate ({rel(p, project)}): {why}")
            continue
        counts = {}
        for c in report.get("checks", []):
            counts[c.get("result")] = counts.get(c.get("result"), 0) + 1
        summary = ", ".join(f"{n} {r}" for r, n in sorted(counts.items(), key=lambda kv: -kv[1]))
        lines.append(f"- evidence gate ({rel(p, project)}): {report['result']}" + (f" ({summary})" if summary else "")
                     + f" in {mode} mode, the current criteria" + coverage_text(report.get("coverage")))
        if mode == "mockup":
            lines += production_only_line(p, project, report)
        lines.append(f"- gate command (run from the project root): {gate_command(p, project, mode)}")
    if unchecked:
        lines.append(f"- evidence gate: verification incomplete, not run: hook deadline reached before "
                     f"{len(unchecked)} record(s): {', '.join(unchecked[:4])}" + (" …" if len(unchecked) > 4 else ""))
    if len(lines) > 12:
        lines = lines[:11] + [f"- evidence gate: {len(lines) - 11} more line(s) not shown"]
    return lines


def coverage_text(cov):
    """`; coverage: automated 40/42, browser 3/10, manual 0/2, 1 waived, 2 no record`, or "" (older helper)."""
    if not isinstance(cov, dict) or not cov:
        return ""
    num = lambda v: isinstance(v, int) and not isinstance(v, bool)     # only fixed names and integers reach context
    parts = [f"{m} {v['passed']}/{v['total']}" for m in ("automated", "browser", "manual", "unknown")
             for v in [cov.get(m)] if isinstance(v, dict) and num(v.get("passed")) and num(v.get("total"))]
    parts += [f"{cov[k]} {k.replace('_', ' ')}" for k in ("waived", "no_record") if num(cov.get(k))]
    return "; coverage: " + ", ".join(parts) if parts else ""


def delivery_mode(data):
    mode = data.get("delivery_mode", "production")
    return mode if mode in DELIVERY_MODES else "production"


def superseded_line(data):
    """Only ids that match the decision-id pattern reach the context: no free text from the project."""
    pairs = []
    for d in data.get("accepted_decisions", []) if isinstance(data.get("accepted_decisions"), list) else []:
        if isinstance(d, dict) and d.get("status") == "superseded":
            did, by = d.get("id"), d.get("superseded_by")
            if isinstance(did, str) and DECISION_ID.match(did) and isinstance(by, str) and DECISION_ID.match(by):
                pairs.append(f"{did}→{by}")
    if not pairs:
        return []
    return ["- superseded decisions (follow only the replacements): " + ", ".join(pairs[:12])
            + (f" and {len(pairs) - 12} more" if len(pairs) > 12 else "")]


def session_start(data_dir=None):      # --data is accepted for hooks.json compatibility; nothing is written
    event, project = read_event("SessionStart")
    if event is None:
        return
    state = participating(project)
    if state is None:
        return
    data, why = load_state(state)
    if why:
        print(f"Sitewright: docs/website/state.json is {why}. Repair it before resuming "
              "(scripts/sw_records.py check-state).")
        return
    if data.get("session_summary") is not True:
        return                                    # opt-in per project
    get = lambda k: data.get(k) if isinstance(data.get(k), str) and data.get(k).strip() else "unknown"
    lines = ["Sitewright project state (docs/website/state.json indexes evidence; it is not proof):",
             f"- scope {get('requested_scope')}, build path {get('build_path')} "
             f"({get('selected_framework_or_builder')}), design family {get('selected_design_family')}, "
             f"phase {get('current_phase')}",
             next_action_line(data.get("next_action")), *owner_lines(data), handover_line(data, state, project)]
    mode = delivery_mode(data)
    criteria = data.get("delivery_criteria") if isinstance(data.get("delivery_criteria"), list) else []
    lines.append(f"- delivery mode: {mode}" + (f" ({len(criteria)} criteria in state.json)" if criteria else "")
                 + (" (not set in state.json, so the production default; set delivery_mode explicitly, "
                    "\"mockup\" for a mock-up)" if "delivery_mode" not in data else "")
                 + ("; a mock-up gate pass means mock-up criteria met, production not assessed"
                    if mode == "mockup" else ""))
    if "delivery_mode" in data and data.get("delivery_mode") not in DELIVERY_MODES:
        lines.append("- delivery mode in state.json is not mockup or production; gating as production")
    lines += superseded_line(data)
    issues = [i for i in data.get("open_issues", []) if isinstance(i, dict) and i.get("status", "open") == "open"
              and (i.get("blocking") is True or (isinstance(i.get("blocking"), list) and i["blocking"]))] \
        if isinstance(data.get("open_issues"), list) else []
    if issues:
        lines.append("- blocking issues (they fail the gate they name): " + "; ".join(
            f"{i.get('id')} {i.get('issue')} "
            f"({'production' if i['blocking'] is True else ', '.join(map(str, i['blocking']))})" for i in issues[:5]))
    deps = [d for d in data.get("blocked_dependencies", []) if isinstance(d, dict)] \
        if isinstance(data.get("blocked_dependencies"), list) else []
    if deps:
        lines.append("- blocked: " + "; ".join(f"{d.get('dependency')} (needs: {d.get('action_needed')})"
                                               for d in deps[:3]))
    report, why = helper("check-state", state, "--root", project, "--quick")
    if why:
        lines.append(f"- artefacts: {why}")
    else:
        changed = [f.get("location") for f in report.get("findings", [])
                   if isinstance(f, dict) and f.get("severity") == "defect"]
        lines.append("- artefacts and state: " + (report["result"] if not changed else
                     f"{report['result']} ({len(changed)} defect(s): {', '.join(map(str, changed[:5]))})"))
        warned = [f.get("evidence") for f in report.get("findings", []) if isinstance(f, dict)
                  and f.get("severity") == "warning" and f.get("check_id") == "records.state"
                  and isinstance(f.get("evidence"), str)]
        if warned:
            lines.append("- state warnings: " + "; ".join(warned[:3]))
    lines += gate_lines(data, state, project)
    lines.append("Resume through website-workflow: reconcile these with the user's request before trusting any phase; "
                 "use the complete next_action from docs/website/state.json, not this summary. For any other "
                 "request, take its owner from the owners line and invoke it before editing files.")
    print("\n".join(l if l.startswith(("- next action:", "- owners by request:")) else clip(l) for l in lines))


# ---------- stop ----------

def stop():
    event, project = read_event("Stop")
    if event is None:
        return
    active = event.get("stop_hook_active", False)
    if not isinstance(active, bool):
        raise BadInput("stop_hook_active is not a boolean")
    if active:
        return                                    # already continuing because of a stop hook: never loop
    state = participating(project)
    if state is None:
        return
    data, why = load_state(state)
    if why:
        return block([f"docs/website/state.json is {why}, so a declared completion cannot be checked. "
                      "Repair the state record, or tell the user it is broken."])
    if data.get("current_phase") != "handoff" or data.get("requested_scope") in NO_BUILD_SCOPES:
        return
    paths, problems = verification_paths(data, state, project)
    if not paths and not problems:
        return block(["state.json declares current_phase handoff but lists no verification record, "
                      "so no required evidence exists."])
    unchecked = []
    for p in paths:
        where = rel(p, project)
        if not p.is_file():
            problems.append(f"{where}: unavailable (the file does not exist)")
            continue
        report, why = helper("gate", p, "--root", project, "--mode", delivery_mode(data))
        if why and why.startswith("not run"):
            unchecked.append(where)
            continue
        if why:
            problems.append(f"{where}: the gate could not be evaluated ({why})")
            continue
        if report["result"] == "passed":
            continue
        by_result = {}
        for c in report.get("checks", []):
            if c.get("result") not in ("passed", "waived"):
                label = "missing" if c.get("reason") == "no evidence record" else c.get("result")
                by_result.setdefault(label, []).append(f"{c.get('check_id')} {c.get('target')}")
        detail = "; ".join(f"{label} {len(items)}: {', '.join(items[:4])}" + (" …" if len(items) > 4 else "")
                           for label, items in sorted(by_result.items()))
        diag = "; ".join(report.get("diagnostics", []))
        problems.append(f"{where}: gate {report['result']} ({delivery_mode(data)} mode; rerun from the project root: "
                        f"{gate_command(p, project, delivery_mode(data))})" + (f" — {detail}" if detail else "")
                        + (f" ({diag})" if diag else ""))
    if unchecked:                                 # first, so a long reason cannot clip it away
        problems.insert(0, f"verification incomplete: the hook deadline was reached before {len(unchecked)} "
                        f"record(s) were checked ({', '.join(unchecked[:4])}" + (" …" if len(unchecked) > 4 else "")
                        + "); run each from the project root, e.g. "
                        + gate_command(project / unchecked[0], project, delivery_mode(data)))
    if problems:
        block([f"state.json declares current_phase handoff, but the evidence gate has not passed: "
               + " | ".join(problems)])


def block(lines):
    reason = ("Sitewright completion gate: " + " ".join(lines) + " Do not report the site as complete. "
              "Run and record the missing or stale checks, or fix the failures. If they cannot be done now, "
              "set current_phase back to verify, record the blocker in blocked_dependencies, and tell the user "
              "exactly which checks remain and why. This gate blocks once per stop and will not block again "
              "while you continue.")
    print(json.dumps({"decision": "block", "reason": reason if len(reason) <= MAX_REASON else reason[:MAX_REASON] + "…"}))


MODES = {"post-write": post_write, "session-start": session_start, "stop": stop}


def main():
    if os.environ.get(REENTRY):
        return                                    # started by our own helper: never recurse
    args = sys.argv[1:]
    mode = args[0] if args else None
    extra = args[1:]
    if mode not in MODES or (extra and not (mode == "session-start" and len(extra) == 2 and extra[0] == "--data")):
        stderr_exit(1, [f"sitewright hook: unknown mode or arguments {args!r}; expected one of {', '.join(MODES)}"
                        " (session-start also takes --data DIR)"])
    try:
        if extra:
            MODES[mode](extra[1])
        else:
            MODES[mode]()
    except BadInput as e:
        stderr_exit(1, [f"sitewright {mode} hook: invalid hook input ({e}); nothing was checked."])


if __name__ == "__main__":
    main()
