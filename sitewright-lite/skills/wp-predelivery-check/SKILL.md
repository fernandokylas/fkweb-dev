---
name: wp-predelivery-check
description: Final go/no-go gate before a WordPress site is launched or handed to the client - search visibility, https, debug off, placeholder and default content, privacy page, updates, sitemap, links and headers, plus a manual checklist (forms, email, backups, handover) - producing a READY / NOT READY report. Use when the user says the site is finished, asks for a pre-launch, pre-delivery, go-live or handover check, or is about to switch DNS or remove "discourage search engines".
---

# Pre-delivery check

The gate between "built" and "delivered". It reports. It does not fix. Fixes go back through `wp-site-setup` (settings) or `wp-page-update` (content), and then the gate runs again.

## 1. Run the automatic checks

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/predelivery_check.py" \
  --url https://example.com --wp "wp @live" \
  --set timezone_string=Europe/London --set admin_email=owner@example.com \
  --manual docs/website/predelivery-manual.json --out docs/website/predelivery-report.md
```

- `--url` is the address visitors will use. Before DNS switches, run it on final staging, expect the launch-only failures (search engines discouraged, sitemap off) and say so; then run it again on the live address after launch.
- There is no `--stage` flag: the gate always checks to the launch standard.
- `--wp` is optional; reach the site in the usual order (WP-CLI, then the browser on wp-admin for what you can see there, then ask the user). Without it, the settings and inside checks show as "not run", never as passed.
- `--set` takes the same site values used in `wp-site-setup`, so the report checks them too.
- The script needs the `wp-site-audit` and `wp-site-setup` skills next to it, which is how this plugin ships.

## 2. Do the manual checks

The report lists checks no script can prove: forms arrive, email is not spam, backups restore, caching, mobile layout, keyboard use, SEO titles, legal pages, analytics consent, redirects, Search Console, access clean-up and owner handover.

- Do the ones you can with the tools you have. For example, submit a form in the browser, or view key pages at 390 px wide.
- Ask the user to confirm the rest.
- Record each result in `docs/website/predelivery-manual.json`:
  ```json
  {"forms": {"result": "passed", "note": "Contact form: test arrived at hello@… 14:02"}, "analytics": {"result": "n/a", "note": "owner wants no analytics"}}
  ```
- Results are `passed`, `failed`, `warning`, `info`, `n/a` or `open`; any other value is treated as `open`. Only mark one `passed` with evidence in the note. The user's word counts as evidence when you say it was the user's.

## 3. Verdict

- **READY** only when nothing is `failed` or `open`. Warnings are allowed, but list them for the owner.
- **NOT READY**: show the "Before delivery" list from the report, group it by who fixes what, and offer to fix the settings and content items with the right skill.
- Never edit the report or the manual file to make the verdict pass, and never call a site delivered while the verdict is NOT READY. If the user decides to launch anyway, record that decision and the open items in the report.

## 4. After launch

Within a day, check:

- the live address with `--url`
- the sitemap is submitted in Search Console
- staging is no longer publicly reachable or indexable
- every access created for the build is revoked
