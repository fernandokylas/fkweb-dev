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

The Novamira CLI is covered the same way for the abilities that run code on a site
(any `run` of an ability not known to be read-only, including execute-php, run-wp-cli and
execute-ability) and for novamira auth, after splitting the command into shell words.
"""
from __future__ import annotations

import json
import re
import shlex
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
    (r"elementor\s+replace[-_]urls\b", "elementor replace-urls rewrites URLs across the database"),
    (r"elementor\s+(?:kit|library)[-_\s]import(?:[-_]dir)?\b", "elementor kit or library import overwrites site design data or templates"),
]
# Novamira CLI (a client for the Novamira WordPress plugin). The command is split into shell words first, so
# quoting, short options, a path to the binary or `npx @novamira/cli` cannot hide the verb. Any `run` of an
# ability that is not known to be read-only asks, as does `auth`.
NOVAMIRA_BIN = re.compile(r"(?:^|/)novamira$|^@novamira/cli(?:@\S*)?$")
NOVAMIRA_READ_ONLY = {"agent-context"}
NOVAMIRA_WHY = {
    "execute-php": "novamira run execute-php runs arbitrary PHP on the site",
    "run-wp-cli": "novamira run run-wp-cli runs WP-CLI on the site, out of reach of the wp guard",
    "execute-ability": "novamira run execute-ability can run any ability, including PHP or WP-CLI execution, on the site",
}
SEPARATORS = {";", "&", "&&", "|", "||", "(", ")", "\n"}
# Backstop: the earlier pattern rules also run on the raw text, so a command the word split misreads is still caught.
NOVAMIRA_PREFIX = (r"(?:^|[\s;&|(`$'\"])(?:[^\s;&|'\"]*/)?novamira"
                   r"(?:\s+-{1,2}[^\s-]\S*(?:\s+[^-\s;&|]\S*)?)*\s+")
NOVAMIRA_RULES = [
    (r"run\s+['\"]?execute-php\b", NOVAMIRA_WHY["execute-php"]),
    (r"run\s+['\"]?run-wp-cli\b", NOVAMIRA_WHY["run-wp-cli"]),
    (r"run\s+['\"]?execute-ability\b", NOVAMIRA_WHY["execute-ability"]),
    (r"auth\b", "novamira auth signs in to a site, and every login grants full authorisation"),
]
COMPILED = ([(re.compile(PREFIX + pat), why) for pat, why in RULES]
            + [(re.compile(NOVAMIRA_PREFIX + pat), why) for pat, why in NOVAMIRA_RULES])
NESTED = re.compile(r"\s|[;&|`$()]")


def shell_words(command: str) -> list[str]:
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:                                   # unbalanced quotes: fall back to a rough split
        return re.sub(r"[\'\"`]", " ", command).split()


def novamira_reasons(command: str, depth: int = 0) -> list[str]:
    words, found = shell_words(command), []
    for i, word in enumerate(words):
        if depth < 3 and NESTED.search(word):            # a quoted inner command (bash -c "...", eval '...')
            found += novamira_reasons(word, depth + 1)
        if not NOVAMIRA_BIN.search(word.strip("`$")):
            continue
        rest = []
        for w in words[i + 1:]:
            if w in SEPARATORS:
                break
            rest.append(w)
        plain = [w for w in rest if not w.startswith("-")]
        if "auth" in plain:
            found.append("novamira auth signs in to a site, and every login grants full authorisation")
        if "run" in rest:
            # Fail closed: an option value can sit where the ability name would be, so every positional word
            # after `run` must be a known read-only ability, or the command asks.
            after = [w for w in rest[rest.index("run") + 1:] if not w.startswith("-")]
            risky = [w for w in after if w not in NOVAMIRA_READ_ONLY]
            if risky:
                known = [NOVAMIRA_WHY[w] for w in risky if w in NOVAMIRA_WHY]
                found += known or [f"novamira run {risky[0]} may run an ability on the site that is not known to be read-only"]
    return found


MAX_COMMAND = 20_000   # longer commands are not parsed; the guard asks instead (fail closed)


def reasons(command: str) -> list[str]:
    if len(command) > MAX_COMMAND:
        return [f"the command is longer than {MAX_COMMAND:,} characters, too long for the guard to check"]
    return list(dict.fromkeys([why for rx, why in COMPILED if rx.search(command)] + novamira_reasons(command)))


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
    msg = ("wp-essentials: this WP-CLI or Novamira command is hard to reverse (" + "; ".join(dict.fromkeys(found)) +
           "). Confirm the user approved this exact change, on the right site, with a current backup.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "ask",
                                             "permissionDecisionReason": msg}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
