# wp-essentials

Four WordPress skills and one safety hook for Claude Code. They need nothing else installed: Python 3 (standard library) on your machine, and WP-CLI or a browser for the site.

| Skill | Ask for it like | What it does |
|---|---|---|
| `wp-site-setup` | "Set up this WordPress site the usual way" | Language, timezone, date and time format, media sizes 0, no month/year folders, comments, pingbacks and registration off, post-name permalinks, search engines hidden until launch, default content removed. It shows the exact commands, applies them after your yes, then reads every value back. |
| `wp-page-update` | "Change the opening hours on the Contact page" | Safe edits to a live page: backup and approval rules, the right route for block editor or Elementor, and a before/after check that nothing outside the section moved. |
| `wp-site-audit` | "Audit example.com" | Read-only health check from outside (HTTP) and inside (read-only WP-CLI): exposure, headers, sitemap, REST API, updates, users, broken links. Severity-rated findings. |
| `wp-predelivery-check` | "Is the site ready to launch?" | A go/no-go gate: automatic checks plus a manual checklist (forms, email, backups, mobile, handover). Writes `docs/website/predelivery-report.md`. |

**Hook:** before Bash runs a hard-to-reverse WP-CLI command (`db reset`, `search-replace` without `--dry-run`, `plugin delete`, `eval`, `core update` and similar), Claude Code asks you to confirm. It never blocks on its own and never writes anything.

## Defaults

British English: `en_GB`, dates like 19 October 2026 (`j F Y`), 24-hour time (`H:i`), week starts Monday, timezone as a city. Change them by copying `skills/wp-site-setup/assets/default-profile.json` into your project and editing it.

## How it reaches WordPress

1. **WP-CLI** (local, `wp @alias` or `wp --ssh=…`).
2. **wp-admin in a browser**, if a browser tool is connected.
3. **A manual checklist** for you to follow.

Passwords and keys are never written to files. Use your SSH config, WP-CLI aliases or environment variables.

## Requirements

- Claude Code with plugin support.
- Python 3.9 or later on `PATH` as `python3` (standard library only).
- For the site: WP-CLI (local, alias or SSH), or a browser tool connected to Claude Code, or neither (you get a manual checklist).

## Install

### As a Claude Code plugin (recommended)

Inside Claude Code:

```text
/plugin marketplace add fernandokylas/fkweb-dev
/plugin install wp-essentials@fkweb-dev
```

Or from your shell:

```bash
claude plugin marketplace add fernandokylas/fkweb-dev
claude plugin install wp-essentials@fkweb-dev
```

This gives you the four skills and the WP-CLI guard hook. Update with `claude plugin marketplace update fkweb-dev` followed by `claude plugin update wp-essentials@fkweb-dev`; remove with `claude plugin uninstall wp-essentials@fkweb-dev`.

The same four skills are already inside `sitewright-lite`. Install only one of the two.

### Skills only, with npx

The four skills are self-contained, so they also work through the open [`skills`](https://github.com/vercel-labs/skills) installer, without the plugin:

```bash
# see what is available
npx skills add https://github.com/fernandokylas/fkweb-dev/tree/main/wp-essentials --list
# install all four into this project (.claude/skills/)
npx skills add https://github.com/fernandokylas/fkweb-dev/tree/main/wp-essentials --skill '*' -a claude-code
# or one skill, for every project (~/.claude/skills/)
npx skills add https://github.com/fernandokylas/fkweb-dev/tree/main/wp-essentials --skill wp-site-audit -a claude-code -g
```

The npx route copies skill folders only: you do not get the WP-CLI guard hook, so Claude Code will not ask before hard-to-reverse `wp` commands beyond its normal permission prompts.

### From a local clone

```bash
git clone https://github.com/fernandokylas/fkweb-dev.git
claude --plugin-dir ./fkweb-dev/wp-essentials
```

## Usage

Open the project or site folder in Claude Code and ask in plain words; the skill table above shows typical requests. Every change to a site follows the same steps: Claude shows a dry run of what it will change, waits for your yes, applies it, then reads every value back and reports `passed` or `failed` for each. The audit and pre-delivery check only read.

## Development

```bash
python3 -m unittest discover tests -v
claude plugin validate .
```

This folder is the source of truth for these skills. The copies in other plugins, such as `sitewright-lite`, are refreshed with `python3 ../tools/sync_skills.py`.

## Licence and credits

MIT, © 2026 Fernando Kylas; see `LICENSE`. All content is original; see `NOTICE.md`.
