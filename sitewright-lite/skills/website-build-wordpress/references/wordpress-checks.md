# WordPress checks

All results use the shared vocabulary (`passed | failed | unavailable | error | stale | skipped`) and are recorded into `docs/website/verification.json` when a helper runs with `--record --root . --evidence-out <file>`; a run without `--record` is a self-check only. Exit codes: 0 passed (warnings allowed), 1 failed, 2 error.

## Static theme check (no runtime needed)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_wp_theme_check.py" <theme-dir> [--content <dir>] [--tokens <css>] [--probe <probe.json>] [--checks ID,ID] [--record docs/website/verification.json --root . --evidence-out docs/website/evidence/wp-theme-check.json [--require]]
```

| ID | Fails when |
|---|---|
| `wp.theme-header` | `style.css` lacks Theme Name, Version, Requires at least, Requires PHP, License or Text Domain |
| `wp.theme-json` | `theme.json` doesn't parse, has an unsupported version, or names template parts/custom templates with no file |
| `wp.tokens` | Blocks use presets the theme doesn't define, palette entries are invalid or duplicated, or (with `--tokens`) preset values differ from the design's CSS custom properties |
| `wp.block-markup` | Block comments are unbalanced, attributes aren't JSON, or markup sits outside blocks |
| `wp.template-structure` | `index.html` is missing, a template has no or several `main` landmarks, a page template lacks `core/post-content`, or a part or pattern it names doesn't exist |
| `wp.patterns` | A pattern lacks its PHP opening, Title or Slug, uses a slug outside the theme namespace, or duplicates a slug |
| `wp.content-editable` | Content (with `--content`) has classic markup, freeform blocks, no blocks, or names a template that doesn't exist |
| `wp.assets` | A theme file references an asset that doesn't exist |
| `wp.php-safety` | Theme PHP evaluates code, reads request input without sanitising or a nonce, runs unprepared queries, or contains credential-like literals |

Warnings (never a failure on their own): missing "Tested up to", missing `$schema`, missing 404 template, missing pattern categories, Custom HTML or shortcode blocks, remote enqueues, no screenshot, unescaped echo, untranslated strings.

Severity follows context, not pattern matches: `wp.php-safety` fails only for constructs a theme has no legitimate need for. If one is genuinely needed, record a waiver with its reason rather than editing the checker.

## Runtime checks (need `--probe`)

| ID | Fails when |
|---|---|
| `wp.runtime-theme` | The active theme isn't this theme, isn't a block theme, reports errors, or its version differs from `style.css` |
| `wp.runtime-templates` | A theme template, part or pattern isn't registered, or a database copy overrides the theme file |
| `wp.runtime-content` | A content page is missing, has no blocks, has freeform or unregistered blocks, or uses another template than the content index says |

Runtime results count only for the snapshot the probe observed. When the probe's theme file hashes differ from `<theme-dir>`, the probe is older than `sitewright-wp-probe 2`, or its file list is truncated, all three are recorded `stale`; when its stored page content differs from `--content`, `wp.runtime-content` is `stale`. Probe again after any theme or content change. `wp.runtime-content` is recorded with the content folder as an input, so a later content edit makes it stale too (see `playground-runtime.md`, Probe).

## Rendered pages

`sw_capture.py` saves rendered routes from a local server, then `sw_site_check.py` runs the same static site checks the custom-code path uses:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_capture.py" http://127.0.0.1:9400 --out capture --replace --route / --route /about/ --not-found "/?page_id=99999"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_site_check.py" capture --routes capture/routes.json \
  --record docs/website/verification.json --root . --evidence-out docs/website/evidence/site-check-capture.json
```

The capture reports `capture.routes` (each route answered 200 and was saved), `capture.not-found` (the not-found path answered 404), `capture.assets` (same-origin CSS, JS and images were fetched) and `capture.metadata-links` (canonical and similar links resolve; warnings only). It is a convention-level check of the rendered output, not a browser check.

## Browser checks

`browser.wp-editor-valid` (method `browser`): every content page opened in the block editor has no invalid blocks and no `core/freeform` or `core/missing` fallbacks; templates and parts parse valid in the site editor. Plus the shared browser checks run by `website-verify` (`browser.keyboard`, `browser.reflow-320`, `browser.form-states`, `browser.reduced-motion`, `browser.no-js`, `browser.console`) on the rendered site.

Without a runtime, record runtime, capture and browser checks as `unavailable` with the reason.
