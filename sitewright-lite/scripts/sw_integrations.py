#!/usr/bin/env python3
"""Sitewright optional-integration probe (stdlib only, offline).

Usage:
  sw_integrations.py probe [--project DIR] [--playground-dir DIR] [--credential-env NAME ...]

Reports which optional integrations this machine already has, with each one's cost, data flow
and the authority it needs (skills/website-workflow/references/optional-integrations.md). It
never installs, downloads, enables plugins, opens a network connection or runs npx: it only
runs executables already present, with --version, each under its own timeout.

Status per integration:
  available     found (version, or path when no version is cheap to read)
  unavailable   not found; `detail` says what was looked for
  skipped       a script cannot see it (e.g. a browser MCP server in the session) or it is deferred
  error         found but its version check crashed or timed out; treat as unavailable

--credential-env NAME reports only whether that variable is set, never its value. A set
credential is not authority: every paid or external call still needs the user's authority.

Output: one JSON object on stdout, result `passed` when the probe completed (availability is
information, not a check of the site). Exit: 0 probe ran, 2 bad arguments.
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

TOOL_VERSION = "1"
VERSION_TIMEOUT = 5
MAX_VERSION = 120

# Mirrors the table in skills/website-workflow/references/optional-integrations.md (same ids).
REGISTRY = {
    "browser-mcp": {"cost": "none", "data_flow": "local pages only", "authority": "none if already enabled; enabling a plugin or server needs the user"},
    "playwright-local": {"cost": "none", "data_flow": "local pages only", "authority": "none if installed in the project; installing needs the user"},
    "browser-binary": {"cost": "none", "data_flow": "none by itself", "authority": "none"},
    "node": {"cost": "none", "data_flow": "none by itself", "authority": "none"},
    "wordpress-playground": {"cost": "none", "data_flow": "first run downloads WordPress and PHP", "authority": "network permission for the first run; install only into a scratch dir"},
    "page-builder-runtime": {"cost": "builder licence (user's)", "data_flow": "the user's environment", "authority": "the user supplies the environment"},
    "image-provider": {"cost": "paid per call", "data_flow": "prompts and reference images go to the provider", "authority": "the user's authority for each call"},
    "seo-data-provider": {"cost": "paid account", "data_flow": "site URLs and queries go to the provider", "authority": "deferred: not offered"},
    "design-engine": {"cost": "none", "data_flow": "local", "authority": "not bundled"},
    "export-video-3d": {"cost": "varies", "data_flow": "varies", "authority": "deferred: not offered"},
    "third-party-site-embeds": {"cost": "varies", "data_flow": "visitors' requests go to the third party", "authority": "decided in the brief"},
}

BROWSER_APPS = ("/Applications/Google Chrome.app", "/Applications/Chromium.app",
                "/Applications/Microsoft Edge.app", "/Applications/Firefox.app")
BROWSER_COMMANDS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                    "microsoft-edge", "firefox")
PLAYWRIGHT_CACHES = (Path.home() / "Library" / "Caches" / "ms-playwright", Path.home() / ".cache" / "ms-playwright")


def version_of(exe):
    """(status, detail) from `exe --version`, bounded; never through a shell."""
    try:
        p = subprocess.Popen([str(exe), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, text=True, start_new_session=True)
    except OSError as e:
        return "error", f"{exe}: cannot run ({e.strerror or e})"
    try:
        out, err = p.communicate(timeout=VERSION_TIMEOUT)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
        p.communicate()
        return "error", f"{exe}: --version timed out after {VERSION_TIMEOUT}s"
    first = (out.strip().splitlines() or err.strip().splitlines() or [""])[0][:MAX_VERSION]
    if p.returncode != 0 or not first:
        return "error", f"{exe}: --version exited {p.returncode}" + (f" ({first})" if first else "")
    return "available", first


def non_empty_dir(path):
    try:
        return path.is_dir() and any(path.iterdir())
    except OSError:
        return False


def local_bin(dirs, name):
    for d in dirs:
        if d is None:
            continue
        exe = Path(d) / "node_modules" / ".bin" / name
        if exe.is_file():
            return exe
    return None


def package_version(exe, packages):
    """Version from node_modules/<package>/package.json next to a local bin, or None."""
    for name in packages:
        try:
            data = json.loads((exe.parent.parent / name / "package.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("version"), str):
            return data["version"][:MAX_VERSION]
    return None


def local_entry(iid, exe, packages):
    status, detail = version_of(exe)
    return entry(iid, status, detail, path=str(exe), package_version=package_version(exe, packages))


def entry(iid, status, detail, **extra):
    return {"id": iid, "status": status, "detail": detail, **REGISTRY[iid], **extra}


def probe(args):
    project = Path(args.project).resolve() if args.project else None
    out = [entry("browser-mcp", "skipped",
                 "a script cannot see the session's tools; look for a browser MCP server in the tool list")]

    exe = local_bin([project], "playwright")
    if exe:
        out.append(local_entry("playwright-local", exe, ("playwright", "@playwright/test")))
    else:
        out.append(entry("playwright-local", "unavailable",
                         "no node_modules/.bin/playwright in the project" if project else "no --project given"))

    found = [a for a in BROWSER_APPS if Path(a).is_dir()] + [w for c in BROWSER_COMMANDS if (w := shutil.which(c))]
    found += [str(c) for c in PLAYWRIGHT_CACHES if non_empty_dir(c)]
    out.append(entry("browser-binary", "available" if found else "unavailable",
                     "; ".join(found) if found else "no Chrome, Chromium, Edge, Firefox or Playwright browser cache found"))

    node = shutil.which("node")
    out.append(entry("node", *version_of(node)) if node else entry("node", "unavailable", "node is not on PATH"))

    exe = local_bin([Path(args.playground_dir).resolve() if args.playground_dir else None, project], "wp-playground-cli")
    if exe:
        out.append(local_entry("wordpress-playground", exe, ("@wp-playground/cli",)))
    else:
        out.append(entry("wordpress-playground", "unavailable",
                         "no node_modules/.bin/wp-playground-cli in --playground-dir or --project"))

    out.append(entry("page-builder-runtime", "skipped",
                     "needs the user's running site with the builder; probe it through playground-runtime.md"))
    creds = [{"name": n, "set": n in os.environ} for n in args.credential_env]
    if creds:
        out.append(entry("image-provider", "skipped",
                         "credential presence only; any call still needs the user's authority", credentials=creds))
    else:
        out.append(entry("image-provider", "skipped", "no credential named; providers are opt-in per call"))
    out.append(entry("seo-data-provider", "skipped", "deferred (D-21)"))
    out.append(entry("design-engine", "skipped", "not bundled; scripts/sw_design_check.py is the baseline"))
    out.append(entry("export-video-3d", "skipped", "deferred (D-21)"))
    out.append(entry("third-party-site-embeds", "skipped", "a site decision recorded in the brief, not a tool"))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sw_integrations.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--project")
    p.add_argument("--playground-dir")
    p.add_argument("--credential-env", action="append", default=[])
    args = parser.parse_args(argv)
    for name in args.credential_env:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            parser.error(f"--credential-env {name!r} is not an environment variable name")
    for opt in ("project", "playground_dir"):
        value = getattr(args, opt)
        if value and not Path(value).is_dir():
            parser.error(f"--{opt.replace('_', '-')} {value!r} is not a directory")
    start = time.monotonic()
    integrations = probe(args)
    findings = [{"check_id": "integrations.probe", "location": i["id"], "severity": "warning", "kind": "defect",
                 "evidence": i["detail"], "action": "treat as unavailable; repair or reinstall the tool to use it"}
                for i in integrations if i["status"] == "error"]
    print(json.dumps({"tool": "sw_integrations", "tool_version": TOOL_VERSION, "target": args.project or "",
                      "result": "passed", "findings": findings, "diagnostics": [],
                      "duration_ms": int((time.monotonic() - start) * 1000), "integrations": integrations}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
