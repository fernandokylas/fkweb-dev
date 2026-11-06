# wp-essentials tests

Stdlib `unittest` only; no network beyond 127.0.0.1, no WP-CLI, no Docker.

    cd wp-essentials && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover tests -v

- `test_wp_settings.py`: `plan` (missing values, prefix, shell quoting, cleanup), `verify` exit codes, `read_actual` with a stubbed `run_read`.
- `test_scope_check.py`: region diff, global `<head>`/`<style>`, exact vs `--loose`, class tokens, removed/added regions.
- `test_site_probe.py`: a local fake faulty WordPress site; row results, off-site redirect refusal, size cap, launch vs staging, `clean()`.
- `test_predelivery_check.py`: `main()` against the fake site, `manual_rows`, `inside_checks` with canned WP-CLI output.
- `test_wp_guard.py`: the PreToolUse hook as a subprocess (ask vs silent).
