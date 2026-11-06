# Safety rules for changing a live WordPress site

A well-meant "clean-up" on a live site can destroy data that no backup shows is missing. They apply to every change.

## 1. Capability is not permission

Having admin access, WP-CLI or an application password means you *can* change something. It does not mean you *may*. Only the user's explicit, specific approval for that change grants permission. A general "fix the site" is not approval to delete, migrate or bulk-edit.

## 2. Remediation ladder

Classify every proposed action before doing it:

| Class | What | Approval |
|---|---|---|
| A | Read-only evidence: inspect, list, export, screenshot, back up | None needed. Always start here. |
| B | Reversible content edit on one page or post (text, image, link), with a revision kept | User approves the specific change |
| C | Reversible configuration: settings, menus, widgets, a plugin's own settings, activating a plugin on staging | User approves each change, with the rollback written down first |
| D | Hard to reverse or site-wide: plugin/theme install or update on production, database writes outside the editor, search-replace, migrations, user/role changes | User approves each change; staging run first; fresh backup verified as restorable; rollback written down |

Never move up a class because the lower one "didn't work". Report and ask.

## 3. Prohibited unless the user asks for that exact action, by name, with a backup

These look like tidying but destroy evidence or data, or break things in ways that show up weeks later:

- database "clean-up" or optimisation plugins and queries
- deleting orphaned post meta, transients in bulk, or "unused" options
- pruning or deleting revisions
- deleting inactive plugins or themes (inactive is not unused: some are kept for rollback, licences or later use)
- deleting media that "looks unused" (builders, CSS and emails reference media in ways a scan cannot see)
- emptying trash or spam
- changing the table prefix, salts, file permissions or `.htaccess` rules
- running `search-replace` without `--dry-run` first
- regenerating thumbnails with `--delete-unknown`

What stays safe: reading, exporting, and making a single-page edit through the editor (which keeps a revision).

## 4. WP-CLI verb policy

- **Read (allowed as evidence):** `list`, `get`, `status`, `version`, `check-update`, `size`, `count`, `is-installed`, `is-active`, `verify-checksums`, `export` to a local file, `search-replace --dry-run`.
- **Write (class B-D, needs approval):** `post update`, `option update`, `menu …`, `plugin activate`.
- **Hard to reverse (class D):** `install`, `update`, `deactivate`, `delete`, `uninstall`, `search-replace` without `--dry-run`, `db import/reset/drop/query`, `user delete`, `site empty`.
- **Never:** `eval`, `eval-file`, `shell`, `db query` with writes. If the job truly needs PHP, write a reviewed mu-plugin or snippet and show it to the user.

The plugin's WP-CLI guard hook (a PreToolUse hook on Bash) asks for confirmation when a Bash command uses the hard-to-reverse verbs. It is a seatbelt, not permission.

## 5. Lack of access is not lack of evidence

If WP-CLI is unavailable (some hosts disable `proc_open` or `exec`), a REST route returns 401, or a screen is hidden, say "not verified", never "not present". Name what you could not check and how the user can check it.

## 6. Backups and staging

- Before class C or D: confirm a backup exists from today and that the user knows how to restore it (host snapshot, backup plugin, or `wp db export` plus `wp-content`). A backup nobody has restored is a hope, not a backup.
- If the host offers staging, change staging, show the user, then repeat on production.
- For class B, the post revision is the rollback. Check revisions are enabled (`WP_POST_REVISIONS` is not `false` or `0`) before relying on it.

## 7. Page builders

- **Elementor:** the page lives in the `_elementor_data` post meta (JSON), not `post_content`. Edit in the Elementor editor, or make a targeted change to that JSON: change only the target widget's setting, keep every other key and id, and save through Elementor's own API or editor. Never overwrite the whole meta. Afterwards, regenerate Elementor CSS (Elementor > Tools > Regenerate CSS) and view the page.
- **Block editor (Gutenberg):** content is HTML with `<!-- wp:… -->` comments. Keep the comment delimiters and their JSON attributes intact, or the block shows as invalid.
- **Other builders (Divi, WPBakery, Bricks, Oxygen):** use the builder's own editor. Their storage formats are easy to corrupt.

## 8. When you are done

- Give the user a change log: page, what changed, before/after, how to roll back.
- Remove anything temporary you created: application passwords, temporary admin users, debug flags (`WP_DEBUG`), probe or snippet files, staging links shared publicly.
- Tell the user to revoke any access given to you or to tools for this job.
