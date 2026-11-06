# Inside checks (read-only WP-CLI)

Run only when the user has given WP-CLI access. Every command here is read-only. `<wp>` is the prefix the user gave (`wp --path=…`, `wp @alias`, `wp --ssh=…`).

| Area | Command | Look for |
|---|---|---|
| Core | `<wp> core version --extra` | Version, then compare with the latest release |
| | `<wp> core check-update --format=count` | Above 0 means updates are pending |
| | `<wp> core verify-checksums` | Modified core files are a possible compromise: report them, do not "fix" them |
| PHP and server | `<wp> cli info` | PHP version; anything below a currently supported PHP branch is a finding |
| Plugins | `<wp> plugin list --fields=name,status,version,update,auto_update --format=csv` | Pending updates, inactive plugins (report them, never delete), several plugins doing one job (two SEO or two cache plugins) |
| | `<wp> plugin verify-checksums --all` | Modified plugin files (only works for wordpress.org plugins) |
| Themes | `<wp> theme list --fields=name,status,version,update --format=csv` | Active theme, child theme in use, pending updates |
| Users | `<wp> user list --fields=ID,user_login,roles,user_registered --format=csv` | Usernames `admin` or the domain name, more administrators than people, unknown accounts. Report them; never delete. Keep the full list out of the saved report: record counts and the administrator usernames only. |
| | `<wp> user application-password list <user> --format=count` (per administrator) | Application passwords nobody remembers creating |
| Settings | `<wp> option get blog_public`, `users_can_register`, `default_role`, `default_comment_status` | Compare with the wp-site-setup baseline |
| | `<wp> option get siteurl` and `home` | Both https and identical in scheme and host |
| Config | `<wp> config get WP_DEBUG`, `WP_DEBUG_DISPLAY`, `DISALLOW_FILE_EDIT`, `WP_POST_REVISIONS` | Debug off on production; file editor disabled; revisions kept |
| Content | `<wp> post list --post_type=page --post_status=publish --fields=ID,post_title,post_name --format=csv` | Page inventory to compare against the sitemap |
| | `<wp> post list --post_status=draft,pending,private --format=count` | Unfinished work the owner may have forgotten |
| Builder | `<wp> post meta list <ID> --keys=_elementor_edit_mode` | Which pages Elementor manages |
| Cron | `<wp> cron event list --fields=hook,next_run_relative --format=csv` | Overdue events mean WP-Cron is not firing; a host cron may be needed |
| Size | `<wp> db size --tables --format=csv`, `<wp> post list --post_type=attachment --format=count` | Very large tables (logs, sessions) are a finding. Recommend a reviewed clean-up; do not clean up yourself. |

If a command fails because the host disables `proc_open` or `exec`, or because of permissions, record it as "not verified (reason)". Do not record it as a pass or as absent.
