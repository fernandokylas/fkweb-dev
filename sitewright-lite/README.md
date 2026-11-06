# Sitewright Lite

**The free demo of Sitewright.** It runs the complete website workflow in Claude Code: plan, design, build and verify, with two build paths: custom code (plain HTML/CSS/JS or a framework app) and WordPress (block themes).

The full edition of Sitewright adds content and copywriting, SEO and AI-search visibility, launch preparation, design refinement, WordPress code review, two independent review agents and the Editorial craft specialists. New skills go there. It isn't publicly available yet.

Lite is maintained with bug and security fixes.

Version 0.3.3. See `CHANGELOG.md` for what changed and its known limitations.

## Quick start

1. Install (see [Install](#install)), then open your project folder in Claude Code.
2. Describe the job in plain words: "Plan and build a five-page site for a bakery", "Set up this new WordPress install", "Update the opening hours on the contact page", "Is the site ready to hand over?".
3. Claude picks the skill. To see where a job stands, ask "where are we?"; the status comes from `docs/website/state.json`.

Status words you will see:

- `passed`: the check ran and the result is recorded as evidence.
- `failed`: the check ran and found a problem; it is listed with the fix.
- `unavailable`: the tool the check needs is missing here, so nothing was proven.
- `error`: the check itself could not finish; rerun it.
- `skipped`: the check does not apply to this project.
- `stale`: the check passed once, but the file it checked has changed since.
- waiver: you decided to accept a failed check; your decision and reason are recorded.
- READY / NOT READY: the WordPress pre-delivery verdict.

## What it does

Ask Claude for website work in plain words. `website-workflow` decides the scope, the phase and the build path, then loads only the skill that phase needs.

| Skill | Phase | Output |
|---|---|---|
| `website-workflow` | Entry and resume | Scope (build, plan-only, design-only, review-only, refine, verify-only), phase, build path, state record |
| `website-plan` | Context, structure | Brief; site map with one contract per page |
| `website-design` | Direction, prototype | Design record: direction, semantic tokens, type, layout, component states, responsive and motion intent |
| `website-assets` | Direction | Assets record: source, permitted use, crop, alt text. An asset whose rights are unknown stays a visible placeholder |
| `website-build-code` | Implement (custom code) | Production pages built from the records, in the project's own stack |
| `website-build-wordpress` | Implement (WordPress) | Block theme with editable content; Elementor adapter (specification only) |
| `website-motion` | Implement | Planned motion beyond simple transitions, with reduced-motion handling |
| `website-verify` | Verify, handoff | Static and browser checks, plus a visual composition review, recorded as evidence in the verification record |

WordPress essentials (also available as the standalone `wp-essentials` plugin):

| Skill | Use it to | Output |
|---|---|---|
| `wp-site-setup` | Set up a fresh install the right way: British English, `j F Y` dates, `H:i` time, Monday weeks, city timezone, image sizes 0, no month/year upload folders, comments and registration off, `/%postname%/` permalinks, default content removed | A reviewed WP-CLI command list, then a pass/fail read-back |
| `wp-page-update` | Change one page on a live or staging site safely | Backup, before/after scope check, read-back |
| `wp-site-audit` | Audit an existing site, read-only | Findings report |
| `wp-predelivery-check` | Decide whether the site can be launched or handed over | READY / NOT READY report |

WordPress access order: WP-CLI first, then the browser on wp-admin, then a checklist you follow by hand. Every write is shown first, confirmed by you, then read back.

The records live in `docs/website/` in your project, unless the project already has a document that does the same job. Both build paths read the same records, so you can change your mind about the build path without redoing the plan or design. A new static site is built into `site/`, so the records stay outside the build output.

A project is either a **mock-up** (labelled placeholder content, placeholder assets and simulated forms are allowed and listed) or **production** (final content, assets with known rights, real integrations). The state record says which, and the verification gate judges that mode; production is the default. A mock-up run never hides a production result. In a production run, visible placeholder labels and mock-up notes fail, and a form passes only with a recorded working submission (tested against a local stub or a provider's test mode); an endpoint in the source is not enough. A production pass proves the declared production checks, not every aspect of launch readiness.

To read where verification stands, run `python3 scripts/sw_records.py status docs/website/verification.json --root .` from your project, with the script path inside the plugin. It shows the current result of each required check, what changed for each stale one and a quoted command that re-runs it into a new evidence file, so earlier records keep theirs. To change which mode requires a check, use `sw_records.py require … --reason "…"` (weakening a requirement also needs `--decided-by`); every change is kept in `requirement_history`. `sw_records.py compact` moves superseded records into an archive file when the history grows long; it previews first and changes nothing without `--write`.

## Examples

**New site on custom code:**

> Build a four-page site for my bakery: home, menu, order and contact. Here is our logo and copy deck. People should be able to send a cake order enquiry.

This prompt produces:

1. a brief and site map
2. a design record
3. static pages
4. checks recorded in `docs/website/verification.json`

**WordPress block theme:**

> Make this a WordPress block theme so the owner can edit the menu and opening hours.

This takes the same records through `website-build-wordpress`.

**Plan only:**

> Plan a portfolio site for a recruiter audience. Don't build anything yet.

This stops after the brief and site map.

**Verify only:**

> Check the built site in `site/` against its page contracts.

This runs the checks and records the results without changing pages.

A records layout for a small project:

```
docs/website/
  website.md          # brief, site map, page contracts, design and assets records
  state.json          # scope, phase, build path, decisions, open issues, next action
  verification.json   # each check with its result and a fingerprint of what it checked
```

Results are always one of `passed`, `failed`, `unavailable`, `error`, `stale` or `skipped`. A check that didn't run is never reported as passed. Evidence becomes `stale` when the files it checked change, including the files it depended on (linked CSS and JS, build inputs, the theme and content a WordPress probe observed). A passed result also needs its saved evidence file inside the project; that shows the evidence exists, not that it is true. Record manual results from the project root with `--root .`.

## Requirements

- Claude Code with plugin support. Tested with 2.1.291.
- Python 3.9 or later on `PATH` as `python3`, for the helpers and hooks. Only the standard library is used.
- Optional: browser tools, Node, Playwright, WordPress Playground or a page builder you already have. Sitewright lite never installs them.
  - Run `python3 scripts/sw_integrations.py probe` from the plugin folder to see what this machine has.
  - When a tool is missing, its checks are reported as `unavailable`, not passed.

## Install

### As a Claude Code plugin (recommended)

Inside Claude Code:

```text
/plugin marketplace add fernandokylas/fkweb-dev
/plugin install sitewright-lite@fkweb-dev
```

Or from your shell:

```bash
claude plugin marketplace add fernandokylas/fkweb-dev
claude plugin install sitewright-lite@fkweb-dev
```

Manage it with these commands:

- update: `claude plugin marketplace update fkweb-dev`, then `claude plugin update sitewright-lite@fkweb-dev`
- disable: `claude plugin disable sitewright-lite@fkweb-dev`
- uninstall: `claude plugin uninstall sitewright-lite@fkweb-dev`

Installing or removing it leaves other plugins and settings untouched. Install only one of `wp-essentials` and `sitewright-lite`: Lite already contains the WordPress skills.

### Skills only, with npx

The `website-*` skills call shared scripts and hooks at the plugin root, so they need the plugin install above; copying them with `npx skills` leaves them without their helpers. The four WordPress skills are self-contained and can be installed on their own:

```bash
npx skills add https://github.com/fernandokylas/fkweb-dev/tree/main/wp-essentials --skill '*' -a claude-code
```

### From a local clone

```bash
git clone https://github.com/fernandokylas/fkweb-dev.git
claude --plugin-dir ./fkweb-dev/sitewright-lite
```

## Hooks

Every hook reads files and reports. None of them can undo a write that has already happened. None opens a browser, installs anything or calls the network. Each one has a time limit inside its timeout (5 seconds for the guard, 30 for the others).

| Event | What it does |
|---|---|
| PreToolUse (Bash) | Asks you to confirm a hard-to-reverse WP-CLI command (database reset or import, `search-replace` without `--dry-run`, `eval`, plugin/theme/user/content deletion, config edits and similar). It never blocks or runs anything itself. |
| PostToolUse (Write, Edit, MultiEdit) | Checks a Sitewright record in `docs/website/` after it is written, and reports defects in that file. |
| SessionStart | When the project's `state.json` opts in (`"session_summary": true`), adds a short state summary. It writes nothing. |
| Stop | At handoff, blocks a stop once if the evidence is missing, failed or stale for the project's delivery mode, and names each check. It checks every listed verification record and says when it couldn't check them all. It never blocks twice in a row. |

The records hooks do nothing in projects that have no `docs/website/state.json`; the WP-CLI guard reacts only to `wp` commands.

## Optional integrations and outward actions

`skills/website-workflow/references/optional-integrations.md` lists every optional tool. For each one it gives:

- what it enables
- its dependencies and cost
- what data leaves the machine
- the authority it needs
- how it is detected
- its fallback

Paid image or SEO providers, video export and 3D tools are not included.

The plugin never does these things on its own:

- publishing, deploying or pushing
- paid API calls
- changes to a live WordPress site
- changes to your global Claude Code configuration

Each of these needs your explicit go-ahead in the conversation.

## Support matrix

| Tested | Not yet tested |
|---|---|
| Plain HTML/CSS/JS site: static checks, plus browser checks in Chromium | Linux and Windows |
| Visual measurement script on scratch pages in Chrome for Testing 151 (headless shell) | Visual review by a live model session |
| React, TypeScript and Vite site: typecheck, production build, static and browser checks | Firefox and Safari |
| WordPress block theme on Playground CLI 3.1.57 (WordPress 7.1.2 and 7.1.3, PHP 8.5.10, SQLite): theme checks, runtime probe, rendered capture, block-editor validity, browser checks | Elementor runtime |
| Local marketplace install, update, disable and uninstall (Claude Code 2.1.291, macOS); hooks run from the install cache | Live or staging WordPress, MySQL or MariaDB, other WordPress or PHP versions |
| WordPress essentials on WordPress 7.1.3 with MariaDB 11 and WP-CLI in Docker (setup, read-back, guard, probe) | |
| Python 3.9.6 and 3.14.7 | Python older than 3.9; live sessions measuring model behaviour (paid evals not run) |

## Licence and credits

- **Sitewright lite's own work:** MIT, in `LICENSE`.
- **Credits:** projects whose ideas informed the original guidance are listed in `NOTICE.md`.
