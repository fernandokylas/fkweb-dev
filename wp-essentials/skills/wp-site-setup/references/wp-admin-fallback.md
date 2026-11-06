# wp-admin route (no WP-CLI)

Use when WP-CLI is unavailable. Work in the browser the user has logged in; never ask for or type their password yourself unless they explicitly hand it over for this session. Save each screen, then reload it and read the values back.

| Screen | Field label (form name) | Set to |
|---|---|---|
| Settings > General (`options-general.php`) | Site Title (`blogname`), Tagline (`blogdescription`) | user's values |
| | Administration Email Address (`new_admin_email`) | user's value. WordPress emails a confirmation link to the new address; the change is pending until it is clicked. |
| | Membership: Anyone can register (`users_can_register`) | unticked |
| | New User Default Role (`default_role`) | Subscriber |
| | Site Language (`WPLANG`) | English (UK). The translation installs on save if the host allows downloads. |
| | Timezone (`timezone_string`) | the city, not a UTC offset |
| | Date Format (`date_format`) | Custom: `j F Y` |
| | Time Format (`time_format`) | Custom: `H:i` |
| | Week Starts On (`start_of_week`) | Monday |
| Settings > Reading (`options-reading.php`) | Search engine visibility (`blog_public`) | ticked ("Discourage…") on staging, unticked at launch |
| Settings > Discussion (`options-discussion.php`) | Attempt to notify any blogs linked to from the post (`default_pingback_flag`) | unticked |
| | Allow link notifications from other blogs (`default_ping_status`) | unticked |
| | Allow people to submit comments on new posts (`default_comment_status`) | unticked |
| | Users must be registered and logged in to comment (`comment_registration`) | ticked |
| Settings > Media (`options-media.php`) | Thumbnail, Medium, Large width and height (`thumbnail_size_w`, `thumbnail_size_h`, `medium_size_w`, `medium_size_h`, `large_size_w`, `large_size_h`) | `0` |
| | Organize my uploads into month- and year-based folders (`uploads_use_yearmonth_folders`) | unticked |
| Settings > Permalinks (`options-permalink.php`) | Permalink structure | Post name |

wp-admin stores an unticked box as an empty value, not `0` or `closed`. WordPress reads that as off, and `wp_settings.py verify` reports it as passed ("stored as empty").

Log in on the host name in the site's own `siteurl`. If you log in on `127.0.0.1` but the site URL says `localhost`, the cookie is not sent and wp-admin keeps asking you to log in again.

`medium_large_size_w` (768 by default) is not on the Media screen. It is on the unlisted `wp-admin/options.php` (All Settings). Change only that field there and save; the page lists every option, so touch nothing else.

## Clean-up screens (fresh install only, with the user's yes)

- Posts: trash "Hello world!", then empty the trash.
- Pages: trash "Sample Page", then empty the trash. Keep the Privacy Policy draft.
- Existing posts and pages: use Bulk actions > Edit and set Comments to "Do not allow" and Pings to "Do not allow".
- Plugins: deactivate and delete Hello Dolly.

## If the browser cannot be used

Give the user this table as a checklist. Afterwards, ask them to confirm each screen, or read the values back with any tool that becomes available.
