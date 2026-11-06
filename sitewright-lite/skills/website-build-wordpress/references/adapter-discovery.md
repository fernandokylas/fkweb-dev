# Adapter discovery

Decide the adapter from evidence in the project, in this order. Stop at the first match and record it.

| Evidence | Adapter |
|---|---|
| The user named an adapter, or `state.json` already records one | That adapter |
| A theme folder with `theme.json` and `templates/*.html` (block theme) | Block theme, extending the existing theme or a child theme of it |
| `_elementor_data` post meta, `elementor` / `elementor-pro` in the plugin list, or an Elementor export (`.json` templates with `"type": "page"` / `"content"` arrays) | Elementor |
| A classic theme (`index.php` templates, no `theme.json` templates) | Build within it; record "classic theme, conversion not requested" |
| No WordPress files yet | Block theme (new theme in its own folder) |

## What to read, read-only

- Theme files: `style.css` header (name, version, requirements, text domain), `theme.json`, `templates/`, `parts/`, `patterns/`, `functions.php`.
- An export or fixture of the content: a WXR file, a content folder of block markup, or an Elementor export.
- A running local site, only through the read-only probe (`playground-runtime.md`). Never query a live site's database or admin.

## Record

In `state.json` `accepted_decisions`: adapter, theme folder and slug, WordPress and PHP versions known or "unknown", builder edition (free or Pro) if relevant, and which plugins the build depends on. Unknown versions are written as unknown, not guessed.

Builders other than Elementor (Divi, Bricks, Beaver Builder and others) have no adapter in Sitewright. Detect them, say so, and build only what the block-theme adapter can safely add, or stop the WordPress build with that as the named blocker while the shared records stay usable.
