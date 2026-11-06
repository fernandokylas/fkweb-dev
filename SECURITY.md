# Security

## Reporting a problem

Report security problems privately through GitHub's **Report a vulnerability** button on this repository's Security tab, not in a public issue. Include the plugin, the file and the steps to reproduce. You will get a reply within a week.

## What the plugins do and don't do

**`wp-essentials` and `sitewright-lite`**

- **Hooks:** read-only. They inspect the tool call or the file that was just written and either report or ask you to confirm. They never write to your project, open a browser, install anything or call the network.
- **Helper scripts:** Python standard library only. Subprocess calls use argument lists with timeouts, with no shell strings.
- **Fetchers** (`fetch_page.py`, `site_probe.py`): follow redirects only on the same host, refuse private, loopback-alias and cloud-metadata addresses, and cap response size and time.
- **WordPress runtime probe** (`scripts/wp-probe`): answers loopback requests only and refuses proxied ones.
- **Credentials:** passwords and keys are never written to files. Use SSH config, WP-CLI aliases or environment variables.

**`editorial-web-craft`**

- **Hook:** after a write, audits the file only when it is HTML or CSS carrying the set's layer marker, and reports failures. It never edits the file or calls the network.
- **MCP server:** `chrome-devtools-mcp`, started with `npx` (fetched from npm on first use), drives a local Chrome for previews.

**Every plugin:** any change to a live site, publication, deployment or paid API call needs your explicit go-ahead in the conversation.
