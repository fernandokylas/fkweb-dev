# fkweb-dev

Fernando Kylas's Claude Code plugin marketplace. It lists three plugins, and each one installs on its own: pick the ones you need.

| Plugin | Pick it if you want | Contents | Needs |
|---|---|---|---|
| [`wp-essentials`](wp-essentials/) | Only WordPress chores: setting up a fresh install, safe page edits, a read-only audit, a launch gate | 4 skills, 1 hook | Python 3.9+ |
| [`sitewright-lite`](sitewright-lite/) | The free demo of Sitewright: the website workflow, plan → design → build (custom code or WordPress block theme) → verify, plus the WordPress essentials | 12 skills, 4 hooks | Python 3.9+ |
| [`editorial-web-craft`](editorial-web-craft/) | Editorial-grade web interfaces: ledger layouts, fluid type, optical polish, dual-ground colour, tactile motion, and audits that keep it honest | 21 skills, 1 command, 1 hook, Chrome DevTools MCP | Python 3; Node and Chrome for previews |

`sitewright-lite` already contains the `wp-essentials` skills, so install one of those two, not both.

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

This repository's own files are MIT, © 2026 Fernando Kylas (`LICENSE`). Each plugin carries its own licence file: `wp-essentials`, `sitewright-lite` and `editorial-web-craft` are MIT.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).
