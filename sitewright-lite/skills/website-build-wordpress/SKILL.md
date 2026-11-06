---
name: website-build-wordpress
description: Builds the WordPress side of a Sitewright website: block theme (theme.json, templates, template parts, patterns) or an existing Elementor site, with page content the owner can keep editing. Use it for the implement phase when build_path is wordpress; when the user asks to build, extend or restyle a WordPress theme, full-site-editing templates, patterns or an Elementor layout; to turn page contracts into WordPress pages; or to check that WordPress content stays editable in the block editor. Not for custom-code sites (website-build-code), plugin development, a real site's settings (wp-site-setup) or edits to a live site's pages (wp-page-update). For a whole or resumed website job, start at website-workflow.
---

# Website build: WordPress

Owns the **implement** phase for `build_path: wordpress`. It uses the same records as the custom-code path (fields in `../website-workflow/references/project-records.md`, precedence in `../website-workflow/references/precedence.md`) and turns them into WordPress structure that the site owner can keep editing. Static HTML pasted into WordPress with a WordPress label is not this path.

Read the brief, site map, page contracts and design record first. If a design field the build needs is empty, route that field back to `website-design`, then continue here; don't decide it in theme code.

## 1. Find the adapter

Read `references/adapter-discovery.md`. It decides, from what's actually in the project, which adapter applies:

- **Block theme** (default): `theme.json`, templates, template parts and patterns. Use it for a new site, or when the site already runs a block theme.
- **Elementor**: only when the site already uses Elementor or the user has chosen it. Read `references/elementor-adapter.md`; it is unverified without an Elementor runtime, so say so in the record.
- **Classic theme already in place**: don't convert it unasked. Build within it and record the limitation, or record the conversion as an open decision.

Record the adapter, WordPress and PHP versions (or "unknown") and the reason in `state.json` `accepted_decisions`. For a new theme, set `Requires at least` from the newest feature used (for example `theme.json` version 3 needs 6.6) and `Requires PHP` to the lowest version the theme's PHP actually needs; don't raise either without a reason.

**Real (non-disposable) WordPress install:** before the theme goes on, run `wp-site-setup` so locale, dates, media sizes, uploads folders, comments, registration and permalinks follow the agreed profile. Edits to pages that already exist on a staging or live site go through `wp-page-update`, never straight from this skill.

## 2. Map the design into the theme

Read `references/block-theme.md` for the block-theme adapter:

1. **Tokens → `theme.json`**: colours to the palette, type to font families and sizes, spacing to spacing sizes, radii and durations to `settings.custom`. Turn off defaults the design doesn't allow (custom colours, default palettes) so editors pick from the design.
2. **Shared parts**: header (with the Navigation block) and footer as template parts; a 404 template.
3. **Templates**: `index.html` plus only the templates the page contracts need. Each has one `main` landmark; page templates render `core/post-content`.
4. **Patterns** for repeated sections, in the theme's namespace.
5. **Scoped CSS** only for what `theme.json` can't express (focus styles, reduced motion, state flags), loaded by `functions.php` with the theme version.

## 3. Build the content

Read `references/page-contract-mapping.md` for field-by-field mapping and `references/content-model.md` for where content lives. Every page's content is real blocks the editor can open without "invalid block" or classic-block fallbacks. Fixture copy stays in a local content export, never in theme files: one block-markup file per page plus a `pages.json` index (`front_page`, and per page `slug`, `title`, `file`, `menu_order`, `template`, `excerpt`), which the theme check reads with `--content` and a disposable site loads. A form with no form plugin chosen is a labelled simulated handler (Custom HTML, recorded as a known exception; the theme check's warning on it is expected), never a fake "sent" message; choosing a form plugin is a recorded decision. Images the content uses are either theme assets (decorative, shipped with the theme) or media-library uploads (content); a theme file may only reference assets that exist, or `wp.assets` fails.

## 4. Check

Read `references/wordpress-checks.md`. Always run the static theme check:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_wp_theme_check.py" <theme-dir> --content <content-dir> --tokens <tokens.css>
```

These runs are the build's self-check; `website-verify` reruns them with `--record` and owns the verification record.

When a disposable local WordPress is available (see `references/playground-runtime.md`), also:

- save the read-only probe (`curl -s http://127.0.0.1:9400/sw-probe/ -o docs/website/evidence/probe.json`) and rerun the theme check with `--probe docs/website/evidence/probe.json` for the runtime checks;
- capture the rendered routes with `sw_capture.py` and run `sw_site_check.py` on the capture (commands in `references/wordpress-checks.md`);
- open each page in the block editor and record `browser.wp-editor-valid`, plus the usual browser checks, through `website-verify`.

Without a runtime, every runtime, rendered-page and editor check is `unavailable`, never `passed`, and the hand-over says WordPress behaviour was not observed. Fix every `failed` finding and rerun; when a flagged construct is genuinely needed, record a waiver with its reason instead of working around the checker. Then update `state.json` atomically (temporary file, then rename; `sw_records.py check-state` validates it) (`completed_artifacts`, `last_changed_targets`, `next_action`) and continue to `website-verify` without pausing for approval.

## Rules that always apply

- Never change a live WordPress site, its database or its plugins without a recorded user decision giving that authority. Playground and other disposable local sites are fine.
- Never write credentials into a blueprint, theme or record. No sample admin logins, API keys or application passwords.
- Don't replace an SEO, form or cache plugin the site already uses; work with it.
- Builder support (Elementor or another) is only claimed after a check ran in a matching environment. Pro-only features are recorded as a requirement, not assumed.
- Only build what the page contracts ask for. Extra templates, patterns or plugins are scope changes; record them as open issues.
