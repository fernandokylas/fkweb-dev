# Baseline settings: what and why

Values are those in `assets/default-profile.json`. Option names are the `wp_options` keys used by WP-CLI.

| Area | Option (value) | Why |
|---|---|---|
| Language | locale `en_GB` (`wp language core install en_GB --activate`) | Admin and front-end strings in British English. Needs the translation download; offline hosts must upload the language pack. |
| Timezone | `timezone_string` = a city, e.g. `Indian/Mauritius` | A city keeps daylight saving correct; a UTC offset does not. Scheduled posts and form timestamps use it. |
| Date | `date_format` `j F Y` (19 October 2026) | Unambiguous day-month order. |
| Time | `time_format` `H:i` (14:05) | 24-hour clock. |
| Week | `start_of_week` `1` | Monday. |
| Media | `thumbnail_size_w/h`, `medium_size_w/h`, `medium_large_size_w/h`, `large_size_w/h` all `0` | WordPress stops making resized copies of every upload. Images are prepared at the right size before upload. See the limits below. |
| Uploads | `uploads_use_yearmonth_folders` `0` | All media in one `uploads/` folder: stable, readable URLs that do not reveal dates. |
| Comments | `default_comment_status` `closed`, `comment_registration` `1` | No comments on new posts; if comments are reopened on one post, only logged-in users can comment. |
| Pings | `default_ping_status` `closed`, `default_pingback_flag` `0` | No pingbacks or trackbacks in either direction (spam source). |
| Registration | `users_can_register` `0`, `default_role` `subscriber` | Nobody can create an account or subscribe; if registration is ever enabled, new users get the least power. |
| Permalinks | `permalink_structure` `/%postname%/` | Readable URLs. On Apache, if pages 404 after the change, the `.htaccess` rules are missing: save Settings > Permalinks once in wp-admin. On nginx, the server needs `try_files $uri $uri/ /index.php?$args;`. |
| Visibility | `blog_public` `0` at setup, `1` at launch | Keeps staging out of search results. Forgetting to switch it back at launch is a common, expensive mistake; `wp-predelivery-check` catches it. |
| Site | `blogname`, `blogdescription`, `admin_email` | Asked from the user; never guessed. |

## Clean-up on a fresh install (`--cleanup`)

- Close comments and pings on posts and pages that already exist; the defaults only affect new content.
- Delete the "Hello world!" post (its default comment goes with it) and "Sample Page". Keep the draft Privacy Policy page; it is needed later.
- Delete the Hello Dolly plugin (`hello`). Akismet: delete only if the user will not use it.
- Inactive default themes: list them and delete only the ones the user names. Keep one default block theme as a fallback if the site's own theme breaks.

## Limits of media settings

Setting sizes to 0 does not stop:

- core sizes `1536x1536` and `2048x2048` (registered in code since WordPress 5.3)
- the `-scaled` copy of uploads wider or taller than 2560 px (`big_image_size_threshold`)
- sizes added by the theme or plugins (WooCommerce, page builders)

Tested on WordPress 7.1.3: with the profile applied, a 3000x2000 upload produced `-1536x1024`, `-2048x1365` and `-scaled` copies; with `assets/media-sizes-off.php` installed, only the original was stored.

The mu-plugin removes the core extras and the scaled copy. It keeps theme and plugin sizes unless `define( 'WP_ESSENTIALS_ALL_SIZES_OFF', true );` is in `wp-config.php`. Turning all sizes off can break themes or shops that rely on their own crops, so ask first.

Images uploaded before the change keep their old copies. Removing them (`wp media regenerate --delete-unknown`) is destructive and needs the user's agreement and a backup.
