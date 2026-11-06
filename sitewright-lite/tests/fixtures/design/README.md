# Design check fixtures

Inputs for `scripts/sw_design_check.py` and `tests/design/`. Everything here is original fixture material
written for Sitewright lite (a fictional café, Saltmarsh Ferry). Nothing is copied from a source snapshot.

| Fixture | What it shows |
|---|---|
| `pass/` | Records and a small site that agree: every recorded token defined with the recorded value, readable pairs in the light and dark schemes, assets recorded with known rights and local files. Expected: `passed`, warnings allowed. |
| `fail/` | One deliberate defect per check: a missing token, a value that drifted, low-contrast pairs (one only in the dark scheme), tight leading, wide tracking, justified text, a cramped button, raw colours, assets with unknown rights, a missing credit, remote/absolute/outside/missing paths, a placeholder, and images the record doesn't list. Expected: `failed`. |
| `theme/` | A WordPress block theme whose `theme.json` presets carry the recorded tokens, including a one-step scale (`--radius-1` written as `custom.radius`). Expected: `passed` with one alias warning. |

Missing, stale and error cases are built from copies of these in the tests (removed records, an edited
stylesheet after recording, a malformed `theme.json`, an oversized file, bad arguments).
