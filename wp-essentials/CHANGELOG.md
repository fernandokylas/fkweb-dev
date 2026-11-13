# Changelog

## 0.1.2 (2026-11-13)

- `wp_guard` now asks for confirmation before Novamira commands that run code or sign in to a site (any `novamira run` of an ability not known to be read-only, such as `execute-php`, `run-wp-cli` or `execute-ability`, and `novamira auth`; the command is split into shell words first, so quoting, short options, a path or `npx @novamira/cli` cannot hide the verb) and before `wp elementor replace-urls`, `kit-import` and `library-import`. New tests cover each rule and the safe commands that stay allowed.
- `wp-page-update` safety rules: Elementor V4 caution (atomic classes and variables cannot be applied to v3 widgets; inspect the page data before any programmatic edit; edit through the editor), `wp elementor flush-css` to regenerate CSS, `--skip-columns=guid` for search-replace, multisite scope (`--url`, `--network`) and batching of large changes.
- `wp-site-audit` inside checks: `wp elementor system-info` and `wp elementor experiments-status` as read-only builder checks, and detection of Mosaic Builder (`wp-content/plugins/mosaic/`).

## 0.1.1 (2026-10-31)

- Now installed from the `fkweb-dev` marketplace: `claude plugin marketplace add fernandokylas/fkweb-dev`, then `claude plugin install wp-essentials@fkweb-dev`. The `fernandokylas/sitewright` marketplace is retired. No change to the skills or the hook.

## 0.1.0 (2026-10-19)

- First release: `wp-site-setup`, `wp-page-update`, `wp-site-audit`, `wp-predelivery-check` and the `wp_guard` PreToolUse hook.
- Security review fixes: `wp_guard` also catches wp after a quote (`ssh host "wp …"`, `bash -c 'wp …'`), with a path (`./wp-cli.phar`) or after a global flag with a separate value; `--dry-run` counts only as the exact flag in the same command; changing `siteurl`/`home` and `wp package install` now ask. `site_probe.py` follows links and redirects only to the same host and port (http and https swap only on default ports).
- Tested against WordPress 7.1.3 (Docker: `wordpress:php8.3-apache`, `wordpress:cli-php8.3`, MariaDB 11).
