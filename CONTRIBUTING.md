# Contributing

Issues and pull requests are welcome. This repository is built from a private development workspace, so an accepted pull request is applied there and arrives here with the next release.

## Where to edit

Some skills exist in more than one plugin. Each copy has a `.synced-from` marker naming its source. Edit the source, never a copy:

| Source | Copied into |
|---|---|
| `wp-essentials/skills/wp-*`, `wp-essentials/hooks/wp_guard.py` | `sitewright-lite/` |

After editing a source, refresh and check the copies:

```bash
python3 tools/sync_skills.py
python3 tools/sync_skills.py --check
```

## Checks before a pull request

```bash
# from the repository root
claude plugin validate .
for p in wp-essentials sitewright-lite editorial-web-craft; do claude plugin validate $p; done

# tests and validators shipped with the plugins, each from its own folder
(cd wp-essentials && python3 -m unittest discover tests)
(cd sitewright-lite && for s in records site skills design hooks integrations capture wordpress visual; do python3 -m unittest discover tests/$s; done)
(cd editorial-web-craft && python3 scripts/validate.py && python3 tests/run_fixtures.py && python3 tests/smoke.py)
```

The site and WordPress fixtures in `sitewright-lite/tests/fixtures/` carry committed verification records fingerprinted against their files. If you edit a fixture, its tests fail until the checks are re-run and re-recorded.

## Ground rules

- Hooks stay cheap and bounded by timeouts, and never call the network.
- A check that could not run is reported as `unavailable` or `error`, never as `passed`.
- No plugin ships credentials, and no change to a live site or Google property runs without the user's go-ahead.
- Material adapted from another project needs its licence checked and a credit in that plugin's notice file (`NOTICE.md` or `THIRD_PARTY_NOTICES.md`).
