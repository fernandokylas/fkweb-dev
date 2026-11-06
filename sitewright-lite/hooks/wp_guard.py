#!/usr/bin/env python3
"""PreToolUse guard for Bash: ask before hard-to-reverse WP-CLI commands.

Reads the hook payload on stdin. When tool_input.command contains a destructive WP-CLI
call, it prints a permissionDecision "ask" with the reason, so the user confirms in the
normal permission prompt. Anything else (including malformed input) exits 0 silently and
the normal permission flow applies. It never blocks, writes files or runs commands.

It is a safety net for mistakes, not a security boundary: the normal permission flow still
applies. It reads the command text, so wp is caught after a shell separator, a quote (as in
ssh host "wp ..." or bash -c 'wp ...') or a path (./wp-cli.phar, /usr/local/bin/wp), with
global flags in --flag=value or --flag value form. A wrapper whose entrypoint is wp (for
example "docker compose run cli plugin delete x") is caught only when "wp" or a "cli" service
name precedes the verb; scripts that call wp internally are not seen.
"""
from __future__ import annotations

import json
import re
import sys

# Text between the wp invocation and the verb: global flags (with an optional separate value),
# @alias, or a container wrapper. The invocation may follow a quote or carry a path.
PREFIX = (r"(?:^|[\s;&|(`$'\"])(?:[^\s;&|'\"]*/)?(?:wp|wp-cli(?:\.phar)?|cli)"
          r"(?:\s+(?:@\S+|--\S+(?:\s+[^-\s;&|]\S*)?))*\s+")
# The rest of the same command: stops at a shell operator or a newline that is not a continuation.
SAME = r"(?:[^;&|\n\\]|\\.|\\\n)*"

RULES = [
    (r"db\s+(?:reset|drop|import|clean|query)\b", "database reset/drop/import/query changes or replaces the whole database"),
    (r"search-replace\b(?!" + SAME + r"\s--dry-run(?![\w-]))", "search-replace without --dry-run rewrites the database"),
    (r"(?:eval|eval-file|shell)\b", "eval/eval-file/shell runs arbitrary PHP on the site"),
    (r"(?:plugin|theme)\s+(?:delete|uninstall)\b", "deleting a plugin or theme removes its files (and, on uninstall, its data)"),
    (r"(?:plugin|theme|core|language\s+core)\s+(?:update|install)\b", "installing or updating code on the site"),
    (r"plugin\s+deactivate\b", "deactivating a plugin can break the site or lose settings"),
    (r"user\s+(?:delete|set-role|remove-role|remove-cap|application-password\s+delete)\b", "user deletion or role/capability change"),
    (r"site\s+(?:empty|delete)\b", "site empty/delete removes content"),
    (r"post\s+delete\b[^;&|]*--force", "permanent post deletion (skips the trash)"),
    (r"(?:post|comment|term|menu)\s+delete\b", "deleting content"),
    (r"(?:option|transient|post\s+meta|user\s+meta)\s+delete\b", "deleting stored settings or metadata"),
    (r"config\s+(?:set|delete|shuffle-salts|create)\b", "editing wp-config.php"),
    (r"media\s+regenerate\b[^;&|]*--delete-unknown", "media regenerate --delete-unknown deletes image files"),
    (r"rewrite\s+flush\b[^;&|]*--hard", "rewrite flush --hard rewrites .htaccess"),
    (r"cache\s+flush\b", "flushing the object cache on a live site"),
    (r"option\s+update\s+['\"]?(?:siteurl|home)\b", "changing siteurl or home can lock everyone out of the site"),
    (r"package\s+install\b", "installing a WP-CLI package runs third-party code"),
]
COMPILED = [(re.compile(PREFIX + pat), why) for pat, why in RULES]


def reasons(command: str) -> list[str]:
    return [why for rx, why in COMPILED if rx.search(command)]


def main() -> int:
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command", "")
        if data.get("tool_name") != "Bash" or not isinstance(command, str) or not command:
            return 0
    except Exception:
        return 0
    found = reasons(command)
    if not found:
        return 0
    msg = ("wp-essentials: this WP-CLI command is hard to reverse (" + "; ".join(dict.fromkeys(found)) +
           "). Confirm the user approved this exact change, on the right site, with a current backup.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "ask",
                                             "permissionDecisionReason": msg}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
