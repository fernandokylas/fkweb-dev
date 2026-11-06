---
name: wp-site-setup
description: Apply and verify a clean baseline on a new or freshly installed WordPress site - British English language, date and time formats, media sizes 0 so no duplicate images, no month/year upload folders, comments and registration off, post-name permalinks, default content removed. Use when the user asks to set up, configure, initialise or "do the usual settings" on a WordPress site, or before building a theme on a real WordPress install.
---

# WordPress site setup

Bring a WordPress install to a known baseline, then prove it by reading every value back. Nothing changes without the user seeing the exact commands first.

## 1. Collect what only the user knows

Ask once, together, for anything not already in the project records:

- site title and tagline
- admin email (WP-CLI changes it directly; the wp-admin screen sends a confirmation link instead)
- timezone as a city (`Indian/Mauritius`, `Europe/London`), never a UTC offset, so daylight saving works
- the stage: `setup` (fresh build, `blog_public` 0), `launch` (going public, `blog_public` 1) or `none` (an existing live site: leave search visibility alone)
- how to reach WP-CLI: local path, `wp @alias`, `--ssh=user@host/path`, or a container wrapper

Defaults (British English) come from `assets/default-profile.json`; what each setting does and why is in `references/settings-profile.md`. If the user wants different values, copy the profile into the project (e.g. `docs/website/wp-profile.json`), edit it and pass `--profile`.

## 2. Pick the route (first that works)

1. **WP-CLI.** Check with `<prefix> core version`. Some hosts disable `proc_open`/`exec`, so a failure here means "use the next route", not "WordPress is broken".
2. **Browser on wp-admin.** Use whichever browser tool the session has. Field-by-field map: `references/wp-admin-fallback.md`.
3. **Manual checklist.** Give the user the same map as a checklist, then verify what you can afterwards.

Credentials: never write passwords, application passwords or keys into files, records or commands. Use the user's SSH config, WP-CLI aliases or environment variables. Before any change on a site that already has visitors: confirm a backup from today, run `<prefix> option get` for every key in the plan and save the old values as the rollback, and use `--stage none` unless the user explicitly wants search engines discouraged. A production site gets staging first; if none exists, treat every `option update` as class C (see `wp-page-update/references/safety-rules.md`) and get approval for each.

## 3. Plan, confirm, apply (WP-CLI route)

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wp_settings.py" plan \
  --wp "wp --path=/var/www/html" --stage setup --cleanup \
  --set blogname="…" --set blogdescription="…" --set admin_email=… --set timezone_string=…
```

`--stage` is required.

- `plan` prints commands only. Show them to the user. Lines marked `DESTRUCTIVE` (deleting the default post/page, deleting Hello Dolly) need an explicit yes; drop them if the user declines.
- Run the approved commands one at a time, in `sh` or `bash` (some lines use `ids=$(…)`), and stop on the first unexpected error.
- `--cleanup` is only for an install created in this session with no real content. It trashes the default post and page, deletes the named plugins and closes comments on all existing posts. Refuse it on any site with visitors. Before running it, list what it will touch (`post list`, `plugin list`) and show that list to the user.

## 4. Verify

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/wp_settings.py" verify --wp "…" --stage setup --cleanup --set …   # same --set values as plan
```

Exit 0 means every key matched. Report the table as it is: `failed` and `error` rows stay visible, and you never call a run complete while one remains. For the browser or manual routes, verify with WP-CLI if it becomes available, otherwise re-open each screen and report what it shows.

## 5. What settings cannot do (tell the user)

Media sizes at 0 stop the thumbnail, medium, medium-large and large copies. WordPress core still makes `1536x1536`, `2048x2048` and a `-scaled` copy of large uploads, and themes/plugins (WooCommerce, page builders) register their own sizes. `assets/media-sizes-off.php` is a small reviewed mu-plugin that stops the core extras. Offer it, explain it, and install it into `wp-content/mu-plugins/` only on a yes. It is a class D change (code on the server): show the file contents, take a backup, and give the removal command (`rm wp-content/mu-plugins/media-sizes-off.php`) as the rollback. Trade-off: without generated sizes, WordPress serves the original file everywhere, so images must be resized and compressed before upload.

## 6. Hand-off note

Record in the project (or tell the user) the profile used, the route, the verify result, and anything skipped. At launch, run `wp-predelivery-check`, which re-verifies with `--stage launch`.
