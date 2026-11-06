---
name: wp-page-update
description: Safely change existing pages or posts on a live WordPress site - edit text, images, links or one section without touching the rest, with backups, approvals, a before/after scope check and a rollback note. Use when the user asks to update, edit, fix, replace or tweak content on an existing WordPress page, post or Elementor/Gutenberg layout, or edit a single page's content on a live site.
---

# Update an existing WordPress page

A live site has visitors, search rankings and data you cannot see from one screen. Change only what was asked, prove nothing else moved, and leave a way back.

Read `references/safety-rules.md` before the first change in a session. It holds the remediation ladder (classes A-D), the prohibited "clean-up" list, the WP-CLI verb policy and the page-builder cautions.

## Workflow

1. **Pin the request.** Write down which page (URL and post ID), which section, and the exact change. If the request is vague ("make the homepage better"), propose specific changes and get a yes on each.
2. **Inspect (class A, read-only).**
   - Identify the editor: block editor, Elementor (`_elementor_data` meta present), classic, or another builder. `wp post meta list <ID> --keys=_elementor_data,_elementor_edit_mode` tells you quickly.
   - Note the current revision count and that revisions are enabled.
   - Save the rendered page: `curl -sL <url> > before.html`, or save it from the browser if the page needs a login. Fetch it twice: if the two copies differ (nonces, cache comments, rotating IDs), note that noise; you may widen `--allow` for it, never for content. Take a screenshot if a browser tool is available.
3. **Classify and ask.** State the class (B for a single-page content edit, C for settings or menus, D for anything site-wide) and what approval it needs. For C and D, confirm there is a current backup and write the rollback down first.
4. **Change**, through the narrowest route. Access order: WP-CLI for reading and inspection, then the browser on wp-admin, then a manual checklist for the user. For writes to builder content, use the editor even when WP-CLI works.
   - The page's own editor in a browser (keeps revisions; safest for builders).
   - `wp post update <ID> --post_content=…` only for block or classic content, after exporting the old content to a file. Keep block comment delimiters intact.
   - Elementor JSON only as a targeted, key-level change (see the safety rules), never a whole-meta rewrite.
5. **Prove scope.** Save the page again as `after.html`, then:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/scope_check.py" before.html after.html --allow hero,pricing
   ```
   `--allow` takes comma-separated exact matches against a region's id, aria-label, data-section, class token, heading or tag; `--loose` switches to substring matching. Exit 1 means something outside the allowed section changed: revert it or explain it to the user. Changes in `<head>` or global styles/scripts fail unless `--allow-global` (or `--allow global`) is passed, which needs the user's agreement. Then look at the rendered page on desktop and mobile widths.
6. **Clear caches** if the site uses one (caching plugin, host cache, CDN), then re-check the live URL logged out.
7. **Report.** A short change log: page, change, before/after evidence, scope-check result, how to roll back (revision ID or backup). Remove temporary access and files you created (see the safety rules, section 8).

## Never

- Run anything on the prohibited list without the user naming that exact action.
- Use `wp eval`, `wp shell` or raw SQL to edit content.
- Bulk edit several pages when one was asked for.
- Say "done" on the strength of a successful command. Done means the live page shows the change and nothing else moved.
