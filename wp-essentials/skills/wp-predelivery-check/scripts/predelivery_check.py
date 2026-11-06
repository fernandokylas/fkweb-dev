#!/usr/bin/env python3
"""Pre-delivery gate for a WordPress site: is it ready to hand over or launch?

Combines three kinds of evidence into one report:
  outside  read-only HTTP checks (wp-site-audit/scripts/site_probe.py, stage "launch")
  inside   read-only WP-CLI checks, when --wp is given: launch settings via
           wp-site-setup/scripts/wp_settings.py, plus debug, file editor, admin username,
           updates, placeholder text, privacy page, site icon
  manual   things no script can prove (forms arrive, backups restore, mobile layout…);
           they stay "open" until recorded in a --manual JSON file

Usage:
  predelivery_check.py --url https://example.com
  predelivery_check.py --url https://example.com --wp "wp @live" --set timezone_string=Europe/London \\
                       --manual docs/website/predelivery-manual.json --out docs/website/predelivery-report.md

--manual file: {"forms": {"result": "passed", "note": "test enquiry arrived at info@…"}, ...}
Results: passed, failed, warning, info, unverified, open. Verdict READY only when nothing is
failed or open. Exit 0 READY, 1 NOT READY, 2 usage error or site unreachable.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True  # sibling imports must not leave __pycache__ in the installed plugin

SKILLS = Path(__file__).resolve().parent.parent.parent
for sub in ("wp-site-audit/scripts", "wp-site-setup/scripts"):
    sys.path.insert(0, str(SKILLS / sub))
try:
    import site_probe  # noqa: E402
    import wp_settings  # noqa: E402
except ImportError as exc:  # pragma: no cover
    print(f"error: needs the wp-site-audit and wp-site-setup skills next to this one ({exc})", file=sys.stderr)
    sys.exit(2)

PLACEHOLDERS = ("lorem ipsum", "sample page", "hello world", "your content here", "coming soon", "add your text", "example.com")

MANUAL = [
    ("forms", "Every form submitted once with test data; the message arrived at the right inbox and the visitor saw a confirmation."),
    ("email", "Site email (forms, password reset) is sent through SMTP or a mail service, not PHP mail; it reaches the inbox, not spam."),
    ("backups", "Automatic backups are scheduled, stored off the server, and one restore has been tested."),
    ("caching", "Page cache is on (plugin, host or CDN) and was purged after the last change; logged-out pages show current content."),
    ("mobile", "Key pages checked at phone width: no sideways scrolling, readable text, usable menus and buttons."),
    ("keyboard", "Main navigation, forms and dialogs work with the keyboard alone, with a visible focus outline."),
    ("seo_titles", "Each page has its own title and meta description (SEO plugin or theme); social share preview checked."),
    ("legal", "Privacy policy (and cookie notice or terms where needed) published, linked in the footer, and correct for this business."),
    ("analytics", "Analytics and consent banner (if used) installed, and tracking only starts after consent where the law requires it."),
    ("redirects", "Old URLs (previous site, changed slugs) redirect with 301s to the right new pages."),
    ("search_console", "Search Console (or Bing Webmaster) verified and the sitemap submitted after launch."),
    ("access_cleanup", "Temporary accounts, application passwords, staging links and tool access created for the build are removed."),
    ("owner_handover", "Owner has the admin login, knows how to edit a page, and has the hosting, domain and backup details."),
]


def row(section, check, result, detail, evidence=""):
    return {"section": section, "check": check, "result": result, "detail": detail, "evidence": evidence}


def wp_read(prefix, args):
    code, out = wp_settings.run_read(prefix, args)
    return code, (out or "").strip()


def inside_checks(prefix, profile_path, sets):
    rows = []
    try:
        profile = wp_settings.load_profile(profile_path, sets, "launch")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [row("settings", "profile", "failed", f"cannot load profile: {exc}")]
    code, out = wp_read(prefix, ["core", "version"])
    if code != 0:
        return [row("inside", "wp-cli", "unverified", f"WP-CLI not usable ({out or code}); inside checks not run. Not verified is not passed.")]
    values, missing = wp_settings.expected_values(profile, allow_missing=True)
    cleanup = profile["cleanup"]
    actual = wp_settings.read_actual(prefix, list(values), cleanup)
    for r in wp_settings.compare(values, profile["locale"], actual, cleanup):
        res = r["result"] if r["result"] in ("passed", "failed") else "unverified"
        if r["key"] == "blog_public" and res == "failed":
            detail = "search engines are still discouraged (Settings > Reading)"
        else:
            detail = f"expected {r['expected']!r}, got {r['actual']!r}"
        rows.append(row("settings", r["key"], res, detail))
    for key in missing:
        rows.append(row("settings", key, "unverified", "no expected value given; pass --set to check it"))

    for opt in ("siteurl", "home"):
        code, out = wp_read(prefix, ["option", "get", opt])
        rows.append(row("inside", opt, "passed" if code == 0 and out.startswith("https://") else
                        "failed" if code == 0 else "unverified", out or "not readable"))

    code, out = wp_read(prefix, ["config", "get", "WP_DEBUG"])
    val = out.lower()
    if code != 0:
        rows.append(row("inside", "WP_DEBUG", "passed", "WP_DEBUG not defined (off)"))
    elif val in ("", "false", "0"):
        rows.append(row("inside", "WP_DEBUG", "passed", "off"))
    elif val in ("true", "1"):
        rows.append(row("inside", "WP_DEBUG", "failed", "debug mode is on"))
    else:
        rows.append(row("inside", "WP_DEBUG", "unverified", "set by an expression in wp-config.php; check it manually", out))

    code, out = wp_read(prefix, ["config", "get", "DISALLOW_FILE_EDIT"])
    rows.append(row("inside", "DISALLOW_FILE_EDIT", "passed" if code == 0 and out.lower() in ("true", "1") else "warning",
                    "theme/plugin file editor disabled" if code == 0 and out.lower() in ("true", "1")
                    else "file editor in wp-admin is enabled; add define('DISALLOW_FILE_EDIT', true); to wp-config.php"))

    code, out = wp_read(prefix, ["user", "list", "--role=administrator", "--field=user_login"])
    if code == 0:
        admins = [a for a in out.splitlines() if a.strip()]
        bad = [a for a in admins if a.lower() in ("admin", "administrator", "root", "test", "demo")]
        rows.append(row("inside", "admin_usernames", "failed" if bad else "passed",
                        f"{len(admins)} administrator(s)" + (f"; guessable username(s): {', '.join(bad)}" if bad else "")))
    else:
        rows.append(row("inside", "admin_usernames", "unverified", out))

    for label, args in (("core_updates", ["core", "check-update", "--format=count"]),
                        ("plugin_updates", ["plugin", "list", "--update=available", "--format=count"]),
                        ("theme_updates", ["theme", "list", "--update=available", "--format=count"])):
        code, out = wp_read(prefix, args)
        n = out.splitlines()[-1].strip() if code == 0 and out else ""
        if n.isdigit():
            rows.append(row("inside", label, "passed" if n == "0" else "warning", f"{n} pending"))
        else:
            rows.append(row("inside", label, "unverified", out or f"exit {code}"))

    found = []
    for phrase in PLACEHOLDERS:
        code, out = wp_read(prefix, ["post", "list", "--post_type=page,post", "--post_status=publish",
                                     f"--s={phrase}", "--field=post_name"])
        if code == 0 and out:
            found.append(f"{phrase!r}: {', '.join(out.split()[:5])}")
    rows.append(row("content", "placeholder_text", "failed" if found else "passed",
                    "placeholder text in published content" if found else "no common placeholder phrases in published posts/pages",
                    "; ".join(found)))

    code, out = wp_read(prefix, ["option", "get", "wp_page_for_privacy_policy"])
    if code == 0 and out.isdigit() and out != "0":
        c2, status = wp_read(prefix, ["post", "get", out, "--field=post_status"])
        rows.append(row("content", "privacy_page", "passed" if status == "publish" else "failed",
                        f"privacy page {out} is {status or 'missing'}"))
    else:
        rows.append(row("content", "privacy_page", "failed", "no privacy policy page set (Settings > Privacy)"))

    code, out = wp_read(prefix, ["option", "get", "site_icon"])
    rows.append(row("content", "site_icon", "passed" if code == 0 and out not in ("", "0") else "warning",
                    "site icon set" if code == 0 and out not in ("", "0") else "no site icon (favicon) set in Appearance > Customize or the Site Editor"))

    code, out = wp_read(prefix, ["plugin", "list", "--status=inactive", "--field=name"])
    if code == 0 and out:
        rows.append(row("inside", "inactive_plugins", "info",
                        "inactive plugins present: ask the owner whether to keep them (never delete without a yes)", ", ".join(out.split())))
    return rows


def manual_rows(path: Path | None):
    given = {}
    if path:
        given = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for key, text in MANUAL:
        g = given.get(key) or {}
        res = g.get("result", "open")
        if res not in ("passed", "failed", "warning", "info", "open", "n/a"):
            res = "open"
        rows.append(row("manual", key, res, text, site_probe.clean(g.get("note", ""), 200)))
    return rows


def render(report):
    out = [f"# Pre-delivery report: {report['site']}", "",
           f"Generated {report['generated']}. Verdict: **{report['verdict']}**", ""]
    counts = report["counts"]
    out.append(", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    for section in ("outside", "settings", "inside", "content", "manual"):
        rs = [r for r in report["rows"] if r["section"] == section]
        if not rs:
            continue
        out += ["", f"## {section.capitalize()}", "", "| Check | Result | Detail | Evidence |", "|---|---|---|---|"]
        for r in rs:
            out.append(f"| {r['check']} | {r['result']} | {site_probe.clean(r['detail'], 220)} | {site_probe.clean(r['evidence'], 200)} |")
    blockers = [r for r in report["rows"] if r["result"] in ("failed", "open")]
    if blockers:
        out += ["", "## Before delivery", ""] + [f"- {r['section']}/{r['check']}: {site_probe.clean(r['detail'], 220)}" for r in blockers]
    if report.get("not_run"):
        out += ["", "## Not run", ""] + [f"- {n}" for n in report["not_run"]]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="live (or final staging) address")
    ap.add_argument("--wp", help="WP-CLI prefix; without it, inside checks are listed as not run")
    ap.add_argument("--profile", type=Path, default=wp_settings.DEFAULT_PROFILE)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--manual", type=Path, help="JSON with results for the manual checks")
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--out", type=Path, help="write the markdown report here (e.g. docs/website/predelivery-report.md)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        probe = site_probe.probe(args.url, "launch", max(args.sample, 0))
        manual = manual_rows(args.manual)
        prefix = shlex.split(args.wp) if args.wp else None
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rows = [row("outside", r["check"], r["result"], r["detail"], r["evidence"]) for r in probe["rows"]]
    not_run = []
    if prefix:
        rows += inside_checks(prefix, args.profile, args.set)
    else:
        not_run.append("Inside checks (settings, debug, users, updates, placeholder text, privacy page): no --wp given. "
                       "Check them in wp-admin or run again with WP-CLI access.")
    rows += manual
    counts = {}
    for r in rows:
        counts[r["result"]] = counts.get(r["result"], 0) + 1
    ready = probe["reachable"] and not any(r["result"] in ("failed", "open") for r in rows)
    report = {"site": probe["origin"], "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              "verdict": "READY" if ready else "NOT READY", "counts": counts, "rows": rows, "not_run": not_run}
    text = render(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps(report, indent=2) if args.json else text)
    if not probe["reachable"]:
        return 2
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
