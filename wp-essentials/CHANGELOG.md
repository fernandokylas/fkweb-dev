# Changelog

## 0.1.1 (2026-10-31)

- Now installed from the `fkweb-dev` marketplace: `claude plugin marketplace add fernandokylas/fkweb-dev`, then `claude plugin install wp-essentials@fkweb-dev`. The `fernandokylas/sitewright` marketplace is retired. No change to the skills or the hook.

## 0.1.0 (2026-10-19)

- First release: `wp-site-setup`, `wp-page-update`, `wp-site-audit`, `wp-predelivery-check` and the `wp_guard` PreToolUse hook.
- Security review fixes: `wp_guard` also catches wp after a quote (`ssh host "wp …"`, `bash -c 'wp …'`), with a path (`./wp-cli.phar`) or after a global flag with a separate value; `--dry-run` counts only as the exact flag in the same command; changing `siteurl`/`home` and `wp package install` now ask. `site_probe.py` follows links and redirects only to the same host and port (http and https swap only on default ports).
- Tested against WordPress 7.1.3 (Docker: `wordpress:php8.3-apache`, `wordpress:cli-php8.3`, MariaDB 11).
