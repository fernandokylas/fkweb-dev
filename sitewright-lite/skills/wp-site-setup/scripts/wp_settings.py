#!/usr/bin/env python3
"""Plan and verify a WordPress settings baseline with WP-CLI.

  plan    print the WP-CLI commands that apply a profile (nothing is executed)
  verify  read the live values back (read-only WP-CLI) and compare them to the profile

The profile is JSON (see ../assets/default-profile.json). Site values that are null in the
profile (site name, tagline, admin email, timezone) must be supplied with --set KEY=VALUE.

Examples:
  wp_settings.py plan   --set blogname="Harbour Lights" --set blogdescription="Seafood by the quay" \\
                        --set admin_email=owner@example.com --set timezone_string=Indian/Mauritius
  wp_settings.py plan   --wp "wp --path=/var/www/html" --cleanup --stage setup
  wp_settings.py verify --wp "wp @staging" --set timezone_string=Indian/Mauritius --stage launch
  wp_settings.py verify --actual readback.json          # offline: {"option": "value", ...}

--wp is the command prefix that runs WP-CLI: "wp", "wp --path=…", "wp @alias",
"wp --ssh=user@host/path" or a container wrapper such as "docker compose run --rm cli" whose
entrypoint is wp. verify runs only `option get`, `language core list`, `post list --format=count`
and `plugin is-installed`, never a write.

Exit codes: plan 0 ok / 2 missing values or bad profile; verify 0 all match / 1 mismatch /
2 error or unavailable (WP-CLI missing, timeout, unreadable value).
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_PROFILE = Path(__file__).resolve().parent.parent / "assets" / "default-profile.json"
DEFAULT_CONTENT = (("post", "hello-world"), ("page", "sample-page"))
TIMEOUT = 60
# wp-admin saves an unticked box as "" rather than "0" or "closed"; core reads "" as off for these.
EMPTY_MEANS_OFF = {"uploads_use_yearmonth_folders": "0", "default_pingback_flag": "0", "users_can_register": "0",
                   "default_comment_status": "closed", "default_ping_status": "closed"}


def load_profile(path: Path, sets: list[str], stage: str) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    site = dict(data.get("site", {}))
    options = {k: str(v) for k, v in data.get("options", {}).items()}
    for item in sets:
        if "=" not in item:
            raise ValueError(f"--set expects KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        if key in site:
            site[key] = value
        else:
            options[key] = value
    if stage != "none":
        stages = data.get("stages", {})
        if stage not in stages:
            raise ValueError(f"profile has no stage {stage!r}")
        options.update({k: str(v) for k, v in stages[stage].items()})
    return {
        "locale": data.get("locale", "en_US"),
        "site": site,
        "options": options,
        "cleanup": data.get("cleanup", {}),
    }


def expected_values(profile: dict, allow_missing: bool) -> tuple[dict, list[str]]:
    values, missing = {}, []
    for key, value in profile["site"].items():
        if value is None or str(value).strip() == "":
            missing.append(key)
        else:
            values[key] = str(value)
    values.update(profile["options"])
    return values, ([] if allow_missing else missing)


def plan(profile: dict, prefix: list[str], cleanup: bool, allow_missing: bool) -> tuple[list[str], list[str]]:
    values, missing = expected_values(profile, allow_missing)
    if missing:
        return [], missing
    wp = shlex.join(prefix)
    cmds = []
    if profile["locale"] and profile["locale"] != "en_US":
        cmds.append(f"{wp} language core install {shlex.quote(profile['locale'])} --activate")
    for key, value in values.items():
        if key == "permalink_structure":
            continue
        cmds.append(f"{wp} option update {shlex.quote(key)} {shlex.quote(value)}")
    if "permalink_structure" in values:
        cmds.append(f"{wp} rewrite structure {shlex.quote(values['permalink_structure'])}")
    if cleanup:
        c = profile["cleanup"]
        if c.get("close_comments_on_existing"):
            for ptype in ("post", "page"):
                cmds.append(f"ids=$({wp} post list --post_type={ptype} --post_status=any --format=ids); "
                            f"[ -n \"$ids\" ] && {wp} post update $ids --comment_status=closed --ping_status=closed")
        if c.get("delete_default_content"):
            for ptype, slug in DEFAULT_CONTENT:
                cmds.append(f"ids=$({wp} post list --post_type={ptype} --name={slug} --post_status=any --format=ids); "
                            f"[ -n \"$ids\" ] && {wp} post delete $ids   # DESTRUCTIVE: default {ptype}, to the trash")
        for slug in c.get("remove_plugins", []):
            cmds.append(f"{wp} plugin delete {shlex.quote(slug)}   # DESTRUCTIVE: confirm first")
        if c.get("remove_inactive_default_themes"):
            cmds.append(f"{wp} theme list --status=inactive --field=name   # review, then delete named themes one by one")
    return cmds, []


def run_read(prefix: list[str], args: list[str]) -> tuple[int | None, str]:
    try:
        proc = subprocess.run(prefix + args, capture_output=True, text=True, timeout=TIMEOUT)
    except FileNotFoundError:
        return None, f"command not found: {prefix[0]}"
    except subprocess.TimeoutExpired:
        return None, f"timed out after {TIMEOUT}s"
    out = proc.stdout.strip()
    return proc.returncode, out if proc.returncode == 0 else (proc.stderr.strip() or out)


def read_actual(prefix: list[str], keys: list[str], cleanup: dict | None) -> dict:
    actual: dict = {}
    for key in keys:
        code, out = run_read(prefix, ["option", "get", key])
        actual[key] = out if code == 0 else {"error": out or f"exit {code}"}
    code, out = run_read(prefix, ["language", "core", "list", "--status=active", "--field=language"])
    actual["locale"] = out if code == 0 else {"error": out or f"exit {code}"}
    if cleanup is not None:
        if cleanup.get("delete_default_content"):
            for ptype, slug in DEFAULT_CONTENT:
                code, out = run_read(prefix, ["post", "list", f"--post_type={ptype}", f"--name={slug}",
                                              "--post_status=any", "--format=count"])
                actual[f"_default_{ptype}"] = out if code == 0 else {"error": out or f"exit {code}"}
        for slug in cleanup.get("remove_plugins", []):
            code, out = run_read(prefix, ["plugin", "is-installed", slug])
            actual[f"_plugin_{slug}"] = ("installed" if code == 0 else "absent" if code == 1
                                         else {"error": out or f"exit {code}"})
    return actual


def compare(values: dict, locale: str, actual: dict, cleanup: dict | None) -> list[dict]:
    expected = dict(values)
    expected["locale"] = locale
    if cleanup is not None:
        if cleanup.get("delete_default_content"):
            for ptype, _ in DEFAULT_CONTENT:
                expected[f"_default_{ptype}"] = "0"
        for slug in cleanup.get("remove_plugins", []):
            expected[f"_plugin_{slug}"] = "absent"
    rows = []
    for key, want in expected.items():
        got = actual.get(key)
        if got is None:
            rows.append({"key": key, "expected": want, "actual": None, "result": "unavailable"})
        elif isinstance(got, dict):
            rows.append({"key": key, "expected": want, "actual": got.get("error"), "result": "error"})
        else:
            got_s = str(got).strip()
            if got_s == "" and EMPTY_MEANS_OFF.get(key) == str(want):
                got_s = f"{want} (stored as empty)"
                rows.append({"key": key, "expected": want, "actual": got_s, "result": "passed"})
                continue
            rows.append({"key": key, "expected": want, "actual": got_s,
                         "result": "passed" if got_s == str(want) else "failed"})
    return rows


def render(rows: list[dict]) -> str:
    lines = ["| Setting | Expected | Actual | Result |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['key']} | `{r['expected']}` | `{r['actual']}` | {r['result']} |")
    counts = {k: sum(1 for r in rows if r["result"] == k) for k in ("passed", "failed", "error", "unavailable")}
    lines.append("")
    lines.append(", ".join(f"{v} {k}" for k, v in counts.items() if v))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["plan", "verify"])
    ap.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--stage", choices=["setup", "launch", "none"], required=True,
                    help="setup: fresh build, search engines discouraged; launch: going public; none: leave blog_public alone (existing live sites)")
    ap.add_argument("--wp", default="wp", help="WP-CLI command prefix (default: wp)")
    ap.add_argument("--cleanup", action="store_true", help="include default-content and plugin clean-up")
    ap.add_argument("--allow-missing", action="store_true", help="skip site values that are not set")
    ap.add_argument("--actual", type=Path, help="verify against a JSON read-back instead of running WP-CLI")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        profile = load_profile(args.profile, args.set, args.stage)
        prefix = shlex.split(args.wp)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not prefix:
        print("error: --wp is empty", file=sys.stderr)
        return 2

    if args.action == "plan":
        cmds, missing = plan(profile, prefix, args.cleanup, args.allow_missing)
        if missing:
            print("Missing site values; ask the user, then pass --set KEY=VALUE: " + ", ".join(missing), file=sys.stderr)
            return 2
        print(json.dumps(cmds, indent=2) if args.json else "\n".join(cmds))
        return 0

    values, missing = expected_values(profile, allow_missing=False)
    cleanup = profile["cleanup"] if args.cleanup else None
    if args.actual:
        try:
            actual = json.loads(args.actual.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read {args.actual}: {exc}", file=sys.stderr)
            return 2
    else:
        actual = read_actual(prefix, list(values), cleanup)
    rows = compare(values, profile["locale"], actual, cleanup)
    if missing:
        rows += [{"key": k, "expected": "(not set: pass --set)", "actual": None, "result": "skipped"} for k in missing]
    print(json.dumps(rows, indent=2) if args.json else render(rows))
    results = {r["result"] for r in rows}
    if results & {"error", "unavailable"}:
        return 2
    return 1 if "failed" in results else 0


if __name__ == "__main__":
    sys.exit(main())
