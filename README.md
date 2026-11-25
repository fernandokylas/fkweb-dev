# fkweb-dev

**Claude Code plugins for building, checking and launching websites, by Fernando Kylas.** This is the free set. Each plugin installs on its own: pick the ones you need.

| Plugin | Pick it if you want | Contents | Needs |
|---|---|---|---|
| [`sitewright-lite`](sitewright-lite/) | The website workflow: plan, design, build (custom code or a WordPress block theme) and verify, plus by-hand page checklists (404, FAQ, footer, About, features, testimonials) and the WordPress essentials | 12 skills, hooks, scripts | Python 3.9+ |
| [`wp-essentials`](wp-essentials/) | Only WordPress chores: setting up a fresh install, safe page edits, a read-only audit, a launch gate | 4 skills, 1 hook | Python 3.9+ |
| [`editorial-web-craft`](editorial-web-craft/) | Editorial-grade web interfaces: ledger layouts, fluid type, optical polish, dual-ground colour, tactile motion, and audits that keep it honest | 21 skills | Python 3.9+; Node and Chrome for previews |

`sitewright-lite` already contains the `wp-essentials` skills, so install one of those two, not both.

## Free and Pro

The free plugins do the work by hand where Pro automates it. Pro is the private fkweb-dev-pro set.

| | Free (this repository) | Pro (fkweb-dev-pro) |
|---|---|---|
| Plan, design, build, verify | Sitewright Lite | Sitewright, with more build paths (headless WordPress with Astro, custom plugins and blocks) |
| Page checklists | Checked by hand | Checked automatically, with evidence for each item |
| Content and copy | | Copywriting, landing pages, case studies, AI-sounding text checks |
| SEO and AI search | | Indexability, structured data, multilingual and local SEO, answer-engine readiness; SEO Lab for client audits and monitoring |
| Launch | | Security headers, redirects, consent-safe analytics, go-live checklist |
| Design review | Editorial Web Craft audits | Design refinement and two independent review agents |
| Google Search Console and GA4 | | Google Toolkit: reports, property setup, sitemaps, PageSpeed |

**Get Pro:** ask through [contact.fernandokylas.com](https://contact.fernandokylas.com/).

## Install

You need [Claude Code](https://code.claude.com/docs). Inside Claude Code:

```text
/plugin marketplace add fernandokylas/fkweb-dev
/plugin install sitewright-lite@fkweb-dev
```

Swap `sitewright-lite` for `wp-essentials` or `editorial-web-craft`. The same steps from your shell:

```bash
claude plugin marketplace add fernandokylas/fkweb-dev
claude plugin install editorial-web-craft@fkweb-dev
```

To update or remove a plugin:

```bash
claude plugin marketplace update fkweb-dev          # fetch the latest catalogue
claude plugin update <plugin>@fkweb-dev             # update the plugin
claude plugin disable <plugin>@fkweb-dev            # turn it off for now
claude plugin uninstall <plugin>@fkweb-dev          # remove it
```

Auto-update depends on how you added this marketplace. Added by hand in Claude Code (`/plugin marketplace add`), it is off by default. Added from claude.ai, it is on by default. From a Claude Code release on or after 30 November 2026, a marketplace listed in managed settings (`extraKnownMarketplaces`) also updates automatically unless its entry sets `"autoUpdate": false`. You can change auto-update for any marketplace in `/plugin` under Marketplaces. Details: https://code.claude.com/docs/en/discover-plugins (Keep plugins updated).

In the Claude desktop app or on claude.ai, add the marketplace `fernandokylas/fkweb-dev` in Claude's plugin settings, then turn on the plugin you want.

Each plugin's README covers its own setup. Editorial's browser previews need Node and Chrome.

### Skills only, with npx

The open [`skills`](https://github.com/vercel-labs/skills) installer copies skill folders into `.claude/skills/` (or `~/.claude/skills/` with `-g`). It installs **no hooks, commands, MCP servers or shared scripts**, so use it only for self-contained skills, and always point it at one plugin folder:

```bash
npx skills add https://github.com/fernandokylas/fkweb-dev/tree/main/wp-essentials --skill '*' -a claude-code
npx skills add https://github.com/fernandokylas/fkweb-dev/tree/main/editorial-web-craft --skill web-craft
```

The `website-*` skills of `sitewright-lite` need the plugin install.

### From a clone, for trying or developing

```bash
git clone https://github.com/fernandokylas/fkweb-dev.git
claude --plugin-dir ./fkweb-dev/editorial-web-craft
```

## Safety

- Nothing outward happens on its own. Publishing, deploying, pushing, paid API calls, changes to a live WordPress site, and changes to your global Claude Code settings each need your go-ahead in the conversation.
- No plugin ships credentials.
- Checks that cannot run on your machine are reported as `unavailable`, never as passed.

More in [`SECURITY.md`](SECURITY.md).

## Licence

This repository's own files are MIT, © 2026 Fernando Kylas (`LICENSE`). Each plugin carries its own licence file: `wp-essentials`, `sitewright-lite` and `editorial-web-craft` are MIT. The page checklists in `sitewright-lite` are CC BY 4.0: reuse them with credit and a link to fkweb-dev.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
