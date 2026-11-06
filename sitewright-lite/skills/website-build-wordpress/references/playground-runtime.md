# Local runtime: WordPress Playground

An optional, disposable local WordPress for runtime, capture and editor checks. It is never a core dependency: without it, the static theme check still runs and the rest is `unavailable`.

## Availability

Look for an existing local copy first; don't install anything globally. A project-local or scratch install is acceptable when the user's environment allows it:

```bash
npx --no-install @wp-playground/cli --version     # already available?
npm install --prefix <scratch-dir> @wp-playground/cli@<exact-version>   # local, pinned, only with network permission
```

For a scratch install, `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_integrations.py" probe --playground-dir <scratch-dir>` reports the `wordpress-playground` entry offline. CLI 3.1.57 answered `--version` with `unknown`, so record the probe's `package_version` (read from the installed package) instead.

Installing and the first-run WordPress download use the network. Do it only when the session's permissions allow network installs; otherwise don't work around it, and record the runtime, capture and editor checks as `unavailable`.

Playground downloads WordPress on first run (network) and caches it. Record the CLI, WordPress and PHP versions it actually reports at run time, in the evidence and the environment record.

## Starting a site

Mount the theme and a content folder, define the probe constant, and use a blueprint that activates the theme and loads the content:

```bash
<cli> server --port 9400 --blueprint <blueprint.json> \
  --mount "<theme-dir>:/wordpress/wp-content/themes/<slug>" \
  --mount "<content-dir>:/sitewright-content" \
  --mount "${CLAUDE_PLUGIN_ROOT}/scripts/wp-probe:/wordpress/sw-probe" \
  --define SITEWRIGHT_PROBE 1
```

Quote mount paths; project paths often contain spaces. Wait for the server's ready line instead of polling quickly.

## Probe

`curl -s http://127.0.0.1:9400/sw-probe/ -o docs/website/evidence/probe.json` returns versions, the active theme, registered templates, parts and patterns, and the block structure of published pages. It writes nothing, refuses non-loopback and proxied requests and only runs with `SITEWRIGHT_PROBE` defined. Never mount it on a live or shared site. Keep the probe file inside the project root so recorded targets stay inside it.

The probe (`sitewright-wp-probe 2` or later) also reports the snapshot it observed: a SHA-256 for every file of the active theme (`theme.files`, with `files_truncated` when the theme is too large to list) and for each published page's stored content (`content_sha256`). `sw_wp_theme_check.py --probe` compares these with the `THEME` and `--content` files it is given. If any file differs, the probe is older, or its list is truncated, the runtime checks are recorded `stale`; rerunning the checker cannot refresh them. Mount the current theme and content, probe again, then run the checker. Older probe files without these fields can't be bound to anything and always give `stale`.

When the server runs a login blueprint, the first request is redirected (302) while Playground logs in and sets cookies. Fetch the probe with a cookie jar (`curl -sL -c <jar> -b <jar> …`, the jar in a scratch folder, never committed) or from a server started without login.

## Logging in for editor checks

Editor checks need a logged-in session. Use a scratch copy of the blueprint with `"login": true`, only for a Playground server bound to `127.0.0.1`, and never commit that copy; don't write a username or password anywhere. With Playground CLI 3.1.57 the `--login` flag was ignored when a `--blueprint` was given, while the blueprint property worked. Run visitor-level browser checks in a fresh logged-out browser context or a server started without login. On a login server, a new context is logged in automatically on its first request unless it already carries the cookie `playground_auto_login_already_happened=1` for the server's origin; set it, then confirm there is no `#wpadminbar` before recording visitor checks.

## Known runtime differences (observed with Playground CLI 3.1.57, WordPress 7.1.2 and 7.1.3)

- **PHP version**: the startup banner and the `--php` flag did not match the PHP the probe reported (8.5.10). Record the probe's value.
- **Not-found pages**: a missing pretty-permalink URL redirected 301 to `/` instead of returning 404, because the request path is exposed as the script name. Capture the 404 template through a missing query ID (`/?page_id=99999`) and note that real-server 404 behaviour was not observed.
- **Remote reference**: WordPress core's emoji loader references `s.w.org`; record it as a core privacy and remote-request note, not a theme defect.
- **Node**: on Node 26 the CLI's native file-locking dependency needed `npm rebuild fs-ext-extra-prebuilt --foreground-scripts` in the scratch install.
- **Database**: SQLite, not MySQL. Query-level behaviour that differs between them is unverified.

These are environment observations, not support claims for other versions. Re-check them when the CLI or WordPress version changes.

## Stopping

Stop the server when the checks are done. Don't save in the site editor during checks: a saved template or part becomes a database copy that overrides the theme file (`wp.runtime-templates` fails on it), and the mounted theme folder is the project's real source.
