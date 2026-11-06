# Evidence contract

How Sitewright records, aggregates and reports verification. Every skill, helper script and hook uses these terms the same way.

## Result vocabulary

| Result | Meaning | Counts as passed |
|---|---|---|
| `passed` | The check ran on the current target and its criterion was met | Yes, while fresh |
| `failed` | The check ran and found a defect that violates its criterion | No |
| `unavailable` | The check could not run: tool missing, environment absent, no evidence recorded | No |
| `error` | The check started but did not produce a trustworthy result: crash, non-zero exit without a result, timeout, malformed or empty output | No |
| `stale` | A result exists but its target, or another input it depended on, has changed since it was recorded | No |
| `skipped` | Deliberately not run, with a `skip_reason` (out of scope, unsupported file type) | No |

Only `passed` on the current target and inputs satisfies a required check. A missing record is `unavailable`, never `passed`. Optional checks are reported but never block.

## Evidence record

| Field | Rule |
|---|---|
| `check_id` | Stable ID, e.g. `nav.internal-links`, `a11y.focus-visible` |
| `target` | Path, route or URL the check examined |
| `result` | One of the six results |
| `required_or_optional` | `required` or `optional` |
| `method` | `automated`, `browser` or `manual` |
| `source_revision_or_target_fingerprint` | `sha256:<64 hex>` of the target content (helper: `sw_records.py fingerprint`), or a git commit `rev:<7–64 hex>` (see the gate rules for when a revision can count) |
| `inputs` | `{project-relative path: sha256:<hex>}` for every other file or folder the result depended on (see Dependency fingerprints); `{}` when the target is the only input. Written by `record --input PATH` (repeatable) |
| `tool_and_version` | e.g. `sw_records 1`, `playwright 1.63.0`; for manual checks the observer, e.g. `manual: Claude via browser snapshot` |
| `timestamp` | ISO 8601 UTC |
| `evidence_path` | File holding the output, capture or notes; empty only for `unavailable` and `skipped` |
| `observed_finding` | What was seen, in one or two sentences |
| `limitations` | What this check does not establish |
| `issue_id_when_applicable` | Open issue ID for `failed`, `error`, `unavailable` |
| `skip_reason_when_applicable` | Required for `skipped` |

Optional fields, written by `record` options:

| Field | Rule |
|---|---|
| `mode` | `mockup` or `production`: the criteria this evidence was judged by (collection mode). Absent means the result holds for both. The helpers set it only on release-sensitive checks, whose criteria differ by mode (`assets.rights`, `assets.local-path`, `assets.final`, `content.fixture-markers`, `content.mockup-notes`, `integration.form-endpoint`): `production` with `--release` or `--mode production`, `mockup` without. Every other check in the same run is written without `mode`, so a mixed run never tags mode-neutral evidence; the helper's `modes_written` lists what it set |
| `exclusions` | Project-relative paths inside the target that the fingerprint leaves out (`--exclude`); listed by `gate` and `status` |
| `evidence_sha256` | `sha256:<hex>` of the evidence file when it was recorded, so a reused file can't stand for a new run |
| `sample_scope` | What part of the site the run covered when it sampled (`--sample-scope "3 of 12 pages at 320 and 1280px"`) |
| `judged` | For a manual review from screenshots (`visual.review`): the screenshots judged, each `{route, width, theme, screenshot}` (`--judged /,320,light,PATH`, repeatable). Every screenshot must also be one of the record's `inputs` (`--input PATH` or a glob that covers it), so replacing a screenshot makes the review stale; `record` refuses one that isn't. `status` warns about a `visual.review` pass without the list |
| `supplied_by` | Who supplied a record written outside the toolkit (a client or another tool); `compact` never archives it |

A record that claims `passed` without `timestamp`, `tool_and_version`, `method`, `evidence_path` or a target identity is incomplete and is treated as `error`, as is any field of the wrong type, a malformed fingerprint, revision or timestamp, or an input path that is absolute or contains `..`. A screenshot does not prove keyboard behaviour; a static check does not prove visual correctness. State what each check covers in `limitations`.

## Verification file

```json
{
  "schema_version": 1,
  "required_checks": [{"check_id": "nav.internal-links", "target": "site/index.html"},
                      {"check_id": "assets.final", "target": "site", "modes": ["production"]}],
  "waivers": [{"check_id": "perf.lab", "target": "site/index.html", "reason": "user removed the requirement", "decided_by": "user", "timestamp": "2026-10-06T10:00:00Z"}],
  "accepted_findings": [],
  "recurring_warnings": {},
  "records": []
}
```

Records are appended, never edited; the newest record for a `check_id` + `target` pair that counts for the gate's mode is the current one. A required check may carry `modes` (applicability): `["production"]` means it is not a mock-up criterion. Without `modes` it is required in every mode. Applicability says which gates require a check; a record's `mode` says which criteria its evidence was judged by. They are set separately: a helper's `--mode` never changes `required_checks`.

### Changing a requirement

Use `sw_records.py require`, never a hand edit:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" require docs/website/verification.json --root . --check-id <check-id> --target <path> --modes production --reason "<why>"
```

`--modes` takes `mockup`, `production` or both (default both); `--remove` drops the requirement. `--reason` is required. Adding a requirement or adding a mode is a strengthening. Dropping a mode or removing a requirement weakens it and also needs `--decided-by <who>`. The output names each gate that stops requiring the check, and its current result there is listed under `not_assessed`, never as passed. The command validates the check ID, modes and target (inside `--root`), writes atomically, and appends one entry to `requirement_history` (`timestamp`, `check_id`, `target`, `action` add/update/remove, `from_modes`, `to_modes`, `reason`, `decided_by`, `weakens`). History entries are never rewritten, and records and waivers are never touched. `record --require` adds a missing requirement through the same path and logs it; it never narrows one. A removed requirement stays visible under the gate's `not_assessed` with its reason. A waiver is still the only way to accept a required check as unmet, and only the user or an accepted project decision can grant one.

### Waivers

A waiver accepts one required check as unmet. Only the user grants one, through `waive`; an agent never fills in `--decided-by` and gives the user the command to run instead (prefixed with `!` in Claude Code):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" waive docs/website/verification.json --root . --check-id <check-id> --target <path> --reason "<why>" --decided-by "<the user>" --owner "<who follows it up>" --expires YYYY-MM-DD --scope production
```

`--owner`, `--expires` and `--scope` are optional but expected. `--scope` lists the gate levels the waiver counts in (`mockup`, `production`, `launch`; default all) and is matched exactly, so a production waiver doesn't carry into the launch stage unless the user says so. After `expires` the check reads `stale` until the user renews the waiver or the check is run. A new waiver on the same pair replaces the old one; `--remove` withdraws it. Each change is appended to `requirement_history` (`action` waive or unwaive; a grant counts as a weakening). Waivers written before 0.3.0 (only `reason`, `decided_by`, `timestamp`) still count, and `status` warns about each one until it is recorded again with `waive`.

### Accepted findings

A helper warning that is a false positive, or an exception the user chose (a fixture page, a host that sets the canonical header), can be accepted so it stops coming back. Only the user accepts one; the agent gives the user the command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" accept-finding docs/website/verification.json --root . --check-id <check-id> --target <file or folder> --match "<text from the finding>" --reason "<who decided: why>" --decided-by "<the user>" [--expires YYYY-MM-DD]
```

The scope is as narrow as it can be: one check ID (no wildcard), one file or folder (no glob, no URL) and a `--match` text that must occur in the finding's evidence. It is stored in `accepted_findings` (`check_id`, `target`, `match`, `reason`, `decided_by`, `timestamp`, optional `expires`) and logged in `requirement_history` as a weakening; the same check, target and match replaces the old entry, and `--remove` withdraws it. The static helpers read it from `--record` (or `verification.json` in `--records`) and move matching warnings from `findings` to `accepted`, each with the acceptance it matched. A defect is never moved: an unmet check needs a fix or a waiver. After `expires` the finding is reported again, with a diagnostic. Acceptances change what helpers report, never a check's result or the gate.

Triage every warning before reporting: fix real problems; accept only a false positive or an exception you can name, with the user's decision; when unsure, ask the user once in one line; never accept a warning to skip a fix. (Triage outcomes adapted from impeccable `skill/reference/hooks.md`, Apache-2.0.)

### Recurring warnings

Helpers run with `--record` keep `recurring_warnings` in the same write as their records: one entry per open warning (`check_id`, project-relative `location` without the line, `evidence`, `first_seen`, `last_seen`, `runs`). A warning the run reports again counts one more run; a warning the run covered (it recorded that check on a target holding the file) but did not report is dropped, and so is one whose file is gone. Accepted findings never count. `status` lists warnings seen in three or more runs under `recurring_warnings`: fix each one, or ask the user once whether to accept it. The list never changes the gate.

### Runs in progress

A browser or manual check that takes several steps (open the page, try the menu, submit the form, read back) can stop half-way: the session ends, the browser crashes, the context runs out. So that the older pass doesn't stand in for the unfinished run, mark the run before starting:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" begin docs/website/verification.json --root . --check-id integration.form-submit --target site/contact/index.html [--target …] [--input PATH …] [--mode production]
```

`begin` writes one entry per target to `runs_in_progress` (`check_id`, `target`, `started`, `mode`, and the target and input fingerprints at that moment) in one atomic write. Until `record` is run for the pair, every gate it applies to reports the pair as `error` ("a run began … and was never recorded"). `record` clears the marker, and refuses the result as `stale` if the target or a named input changed after `begin`: the run may have judged other content, so begin again and re-run. If the run won't happen, `begin --cancel` with the same check ID and targets removes the marker. The static helpers don't need it: they record a whole run in one write, so a crash writes nothing and fingerprints decide the rest.

### Current view and history

`sw_records.py status docs/website/verification.json --root . [--mode mockup|production]` is the readable current view. It shows one line per required check with its result, mode, method, time, evidence path, limitations, sample scope, exclusions and how many records it has. Stale lines name the target or input that changed, and a line whose requirement changed shows the last `requirement_change`. `rerun` groups everything not passed by the tool that re-runs it. Each hint has a new `evidence_out` path (`docs/website/evidence/<tool>-<UTC time>.json`, or a dated folder for browser and manual checks) that no record cites and nothing occupies. For a helper it also gives `argv` and a shell-quoted `command` to run from `run_from` (the project root), which works with paths that contain spaces and adds `--release` in production mode. When every line to re-run is a page check on an existing page of the site folder (at most ten pages), a site-check hint adds `--page` for each of them (listed in `pages`), so only those pages run again; a stale `site.404` (it reads only the page list) runs with them, and a removed page keeps the full run. A site-check hint repeats the `--mockup-class` names saved in the evidence it replaces, and a check with only a mock-up record is still routed to the tool that collected it. Running it leaves the earlier records linked to the files they cite. With `--record`, the helpers refuse an `--evidence-out` that a record already cites, and suggest a fresh path instead. It also lists `superseded` records (older than the newest of their check, target and mode) and `orphaned` ones (the target is gone, or a required record whose check is no longer in `required_checks`). It writes nothing.

The verification file holds the current records; history lives in `verification-archive.jsonl` beside it, one record per line, append-only. When `record` (or a helper's `--record`) writes a newer record for the same check, target and mode (an unchanged rerun writes none; see "Unchanged reruns"), the older one moves there unchanged, unless its evidence file has the same hash as a record that stays (the reuse guard reads both, so both stay). `status` and the gate read only the verification file; the reuse guard also reads the archive, so archived evidence can never pass a changed target.

`sw_records.py compact docs/website/verification.json --root .` is a dry run that says what else would move (`--write` moves it). It moves superseded records and the records of pairs that are no longer required (retired, orphaned or removed requirements), keeping the newest one of each. It keeps every current record, every `supplied_by` record, `required_checks`, `waivers` and unknown keys. It refuses an archive inside a target or input (an `--exclude` on the record counts), and it writes nothing unless each gate decides every check the same way before and after. Nothing else ever removes a record. `--archive PATH` names another archive file.

### Pages removed or moved

When a page has been deleted or moved elsewhere (another site, a Notion page), its required checks report `error: target no longer exists`. That a file is gone is a fact the helper can check, so it needs no decider:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" retire docs/website/verification.json --root . --all-missing --reason "<why>" [--replaced-by <URL>]
```

A page that disappears from a build is never retired on its own: the helpers keep its checks required and report it as `site.missing-page`, a potential regression. When the owner decides a route goes, record that in `state.json` `removed_routes` (`route`, `reason`, and `decision` naming an accepted decision or `source` saying who said so and when; `../../website-workflow/references/project-records.md`, "Removed routes"). The next `sw_site_check.py --record` run then retires that route's checks itself and reports each one under `route_changes`. For everything else:

It is a dry run that lists each target and its check IDs; `--write` applies it. `--target <path>` (repeatable) names targets instead of `--all-missing`. It refuses a target that still exists, a URL, a target that exists under another likely root (a wrong `--root`), and one whose route the site map's `routes` or `### Page:` entries still list, so remove the route from the site map first. Each `required_checks` entry on the target gets a `retired` field (`timestamp`, `reason`, `replaced_by`, `last_identity`), and `requirement_history` gets one `retire` entry per check with an empty `decided_by` and a `basis` saying the helper checked absence. While the target stays absent the gate lists those checks under `not_assessed`, never as passed. If the file comes back, the requirement applies again and `status` marks the line `reactivated`. Records and waivers are untouched.

Any other weakening is a person's decision. Never enter a name for `--decided-by` yourself, the user's included. When the owner has already made that decision and it is in `state.json` `accepted_decisions` with a `source` (who decided, when, where), pass `--decision D-ID` instead: the history entry records the decision and an empty `decided_by`, and `status` groups weakenings by decision so the owner can audit them. Cite only a decision the owner actually made; one you inferred is not a decision. Otherwise show the user the exact command to run, prefixed with `!` and with the script's full path, with `--decided-by "<your name>"` left for them to fill in.

### Pruning evidence

After a build change, re-run the whole stale set that `status` lists in one pass, browser checks included, before judging the gate. Once the gate passes, old evidence files can go:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" compact docs/website/verification.json --root . --write
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" prune-evidence docs/website/verification.json --root . --mode <mode>
```

`prune-evidence` runs only when the gate in `--mode` (default production) passes. It is a dry run that lists the files and folders under the verification file's `evidence/` folder that no record left in the verification file cites as evidence, target or input; `--write` deletes them and re-runs the gate, which must still pass. A cited folder keeps all its contents, and the folder holding a cited file is entered, never removed. It never deletes outside `evidence/`, removes a symlink without following it, and keeps any `compact` archive stored there. Records archived by `compact` then cite files that no longer exist; that is expected, since the archive is history, not evidence.

While the gate still fails, `prune-evidence --current-only` frees space without waiting for it: it moves superseded records to `verification-archive.jsonl` (keeping the same records `compact` keeps: client-supplied ones, ones with evidence problems, and ones sharing an evidence file with a current record), then prunes what the remaining records don't cite. It writes nothing unless every gate decides each check the same way before and after, and it refuses (`skipped`) while a `begin` marker is open, because that run may already have written evidence no record cites yet. It is a dry run without `--write`; the output lists the archived records under `prune.archived`. Archived records may then cite pruned files.

## Dependency fingerprints

A check that reads more than its target must name everything else it read, so a later change to any of it makes the result stale. The target fingerprint covers the target; `inputs` covers the rest.

| Check | Target | Inputs |
|---|---|---|
| Static page checks (`sw_site_check.py`) | the page | `motion.reduced`: the local CSS and JS the page links; `nav.internal-links`: the local pages it links to. Added by the helper |
| Design checks (`sw_design_check.py`) | the built site or theme; stylesheet checks target the file set `<build>/**/*.css` | the design and assets records it compared against. Added by the helper |
| `wp.runtime-content` | the theme | the content folder. Added by the helper |
| `wp.runtime-theme`, `wp.runtime-templates` | the theme | none; the probe itself must have observed exactly this theme (below) |
| `browser.*`, `visual.measure` | each route visited: its built page | the CSS, JS and preloads the page links (`--inputs-from-page`), plus any data it fetches (`--input`) |
| `visual.review` | each route reviewed: its built page | as above, plus the screenshots and the `visual.measure` output it judged, and the design record (`--input`) |

Rules:

- **Runtime snapshots.** The WordPress probe (`sitewright-wp-probe 2` or later) reports a SHA-256 for every theme file it served and for each published page's stored content. `sw_wp_theme_check.py --probe` compares those with the theme and `--content` files on disk. When they differ, or the probe is older or listed only some files, the runtime checks are recorded `stale`, not `passed`. Running the checker again over an old probe cannot refresh runtime evidence: only a new probe of the current theme and content can.
- **Browser evidence** binds the snapshot the browser actually loaded. Record it per route: the page's built HTML as target with `--inputs-from-page`, which adds every local stylesheet, script and preload the page links (`--site <build>` when root-relative links resolve against a folder other than the nearest one holding them). Editing one page then makes only that page stale; editing a shared stylesheet makes every page that links it stale. A site-wide check lists the routes it visited, one record each. Don't target the whole build folder: any rebuild would make every browser check stale. The gate treats a passed `browser.*` record whose target is a single file with no inputs as `stale`.
- **File sets.** A target or input may be a glob under the project root (`dist/**/*.css`; no `..`, not absolute). Its fingerprint covers the sorted content of the matching files, not their names, so a rebuild that renames assets with new hashes but the same content stays current; changed content goes stale, and no match at all is an error. Keep the site's own build and asset naming; never change them to suit verification.
- **No circular inputs.** The verification file and the record's own evidence file must lie outside its target and inputs; otherwise every write would invalidate the record. `record` and the gate report this as `error`, naming the fix: build into a folder such as `site/`, record a narrower target, or `--exclude docs/website`. Settle the layout before building (`../../website-workflow/references/project-records.md`, "Output layout").
- **A new pass needs a new run.** When a passed record cites an evidence file whose hash equals an earlier record's for the same check and target, and that earlier record saw a different target or input state, the gate treats it as `stale`: the file shows an old run, not a new one. Re-run the check and record its new output.
- **Older records.** A passed `browser.*` or `wp.runtime-*` record written before `inputs` existed is `stale`: what it depended on was never recorded. Re-run the check rather than adding inputs afterwards, unless you can show exactly which files the original run used.
- No hook or helper starts a browser, a WordPress runtime or a paid service to refresh evidence. Stale evidence stays stale until someone re-runs the check.

### Recording in one write

A run that produced several checks records them with one `record --batch FILE.json`: `{"defaults": {...}, "records": [{...}, ...]}`, keyed by the `record` options with underscores (`check_id`, `target`, `input: [...]`, `inputs_from_page: true`, `require: true`, …), each entry merged over the defaults. Every entry is validated first; one refused entry writes nothing, and the rest are written in one atomic write. No other options go beside `--batch`. The helpers' `--record` already writes its whole run this way.

### Unchanged reruns

A record that repeats the current one for the same check, target and mode (same result, method, finding, limitations, tool, inputs, exclusions, sample scope and target fingerprint, with the earlier evidence file still present and unaltered) is not appended: the earlier record and its evidence stay the deciding ones, and `record` reports `"unchanged": true` (a batch reports how many entries were unchanged). Ending a run in progress and `--require` still apply. The evidence path and hash are left out of the comparison, because helper output always carries a new time. `--append-unchanged` (or `"append_unchanged": true` in a batch) appends anyway, for instance to re-date a manual check on purpose. When every check of a helper run is unchanged, the helper deletes the evidence file it just wrote, since no record cites it, and reports `"evidence_kept": false`.

## Gate aggregation

`scripts/sw_records.py gate docs/website/verification.json --root <project>` reports one line per required check and an overall result:

1. For each required check in the gate's mode (`--mode`, default `production`), take the newest record whose `mode` is absent or equal to it. None: `unavailable`. A record that breaks the field rules above: `error`. A check whose `modes` leave out the gate's mode is listed under `not_assessed`, never counted as passed. A pair with an open `runs_in_progress` marker is `error` whatever its records say, until `record` or `begin --cancel` clears it.
2. Resolve the target, every input and the evidence path inside `--root` (symlinks resolved). Anything outside the project root is `error`, and so is a missing target.
3. Recompute the target and input fingerprints. Any difference, or a missing input, turns any result into `stale`.
4. For a `rev:<id>` identity on a passed record, the target in the working tree must be exactly its content at that commit: the same files with the same bytes. A file that differs, an extra file (ignored or not), a missing file, or content git stores through a filter or line-ending conversion is `stale`. No git, no such commit, nothing under the target at that commit, or a submodule there: `unavailable`. A revision is never accepted unchecked. The helper only reads git's object store (`rev-parse`, `ls-tree`) and hashes the working files itself, with every network or local transport refused, so a project's own git settings (fsmonitor, filters, textconv, external diff, a partial clone's promisor remote) can't run a program, even when the Stop hook checks a project just opened. If a project needs filters, record a `sha256:` identity instead.
5. A passed record needs its supporting file: `evidence_path` must resolve inside the project and be a readable file, otherwise `unavailable` (a URL can't be confirmed from the machine and is `unavailable` too). This shows the evidence exists, not that what it says is true; the record's method, tool and limitations say how far to trust it.
6. A URL target with no inputs is `unavailable`: nothing on disk shows it is current. Record the local snapshot that was served with `--input`.
7. A required check whose newest record is `skipped` stays unmet: skipping is not running.
8. Open issues in the state record (`state.json` beside the verification file, or `--state PATH`) that block the gate's level add one `failed` line each, `issue.<id>` with target `state.json`. `blocking: true` blocks production (and launch); a list such as `["mockup"]` or `["launch"]` names the lowest level it blocks, and each level includes the ones before it (mockup, production, launch). Resolved or `wontfix` issues never block. No state record changes nothing; an unreadable one is a diagnostic, not a failure. Close an issue by fixing it and setting `status`, never by deleting it or editing `blocking` to get a pass.
9. Overall result: `passed` only when every non-waived required check is fresh `passed`. Otherwise the overall result is the first present of `failed`, `error`, `stale`, `unavailable`, `skipped`.

In production mode, a passed `integration.form-endpoint` record counts only when its method is `browser` or `manual`; an automated or static pass is `unavailable` (an endpoint in source does not show a working submission), and `record` refuses one unless it is `--mode mockup`.

Gate and status output carry `criteria_note`: a pass establishes only the required checks declared for that mode, judged by their own criteria and limitations. It is not proof of every aspect of launch readiness.

They also carry `coverage`: how the required lines were shown, as passed/total per evidence method (`automated`, `browser`, `manual`; a record without a method counts as `unknown`), plus the number of `waived` lines and of lines with `no_record`. Methods with no lines are left out, and `issue.<id>` lines are not counted. A gate that passes on automated records alone says nothing about how pages render or behave; the coverage shows that at a glance.

**Launch stage.** A required check with `stages: ["launch"]` (for example `launch.live-pages`, checked against the served site after deploy) is a production check that only the launch gate assesses: `gate docs/website/verification.json --root . --mode production --stage launch`. Every other gate lists it under `not_assessed`. The launch gate also counts open issues blocking `launch` and waivers scoped to `launch`. `require ... --stage launch` adds such a check (production mode); moving an existing check there is a weakening and needs `--decided-by`, and `--stage every` moves it back. A stage is not a delivery mode: records keep `mode: production`.

A mock-up run can't hide a production result: a `mockup` record never counts for the production gate, and the default gate is production. Records without `mode` (all records before 0.1.0-rc.3) count for both, so older projects gate as before.

Exit status: `0` gate passed, `1` gate not passed (findings listed), `2` the gate itself could not run (unreadable or malformed verification file). A caller must treat any status other than `0` as not passed.

## Helper and hook output contract

Helpers that check files print one JSON object on stdout:

```json
{"tool": "name", "tool_version": "1", "target": "path", "result": "failed",
 "findings": [{"check_id": "", "location": "file:line", "severity": "defect|warning", "kind": "defect|convention", "evidence": "", "action": ""}],
 "diagnostics": [], "duration_ms": 0}
```

- `severity: defect` fails a required check; `warning` and `kind: convention` never do on their own. Toolkit or family conventions stay separate from real defects. `kind: review` marks a finding a person must look at because the tool can't tell (for example a letter-spaced element whose role is unclear, or generated content inside a grid). It is always a warning.
- Some findings carry context: `basis` (`declared` when one rule sets both colours, a defect; `inferred` when the pair was assembled from separate rules, a warning), `role` (`label`, `running` or `uncertain` for tracking), `selectors` and `tokens` for grouped warnings. Repeated identical findings are reported once, and inferred pairs with the same colours are one warning listing their selectors. A declared defect is never grouped away.
- Exit `0` with `result: passed` or `skipped`; exit `1` with `result: failed`; exit `2` with `result: error` or `unavailable`. Callers check the exit status and the parsed `result`, never a keyword in free text.
- Empty stdout, unparseable JSON, a result outside the vocabulary, or a status/result mismatch is `error` for the caller, with a bounded excerpt of stderr as the diagnostic.
- Every subprocess a helper starts has its own timeout; the helper also has an overall deadline below its caller's timeout. A timed-out child is terminated and reaped, reported as `error` with `timeout` in the diagnostic, and the remaining checks still run.

## Plugin hooks

All plugin hooks are read-only wrappers over the helpers above (`hooks/hooks.json`). They act only in projects that have `docs/website/state.json`, never write files, and never start themselves again (each sets a re-entry variable for its children). Each helper call has its own timeout, and each hook has an overall deadline below its `hooks.json` timeout.

| Event | Hook | What it does |
|---|---|---|
| After Write/Edit | Records check | After a write to a record in `docs/website/`, runs `check-records`, `check-state` or `gate` and reports only that record's defects. For `verification.json` it reports only `error` evidence: missing, stale or failed checks are normal mid-build. |
| Session start | State summary | When `state.json` sets `session_summary: true`: scope, phase, delivery mode, next action, open blocking issues with the level each blocks, superseded decision ids, artefact freshness and the evidence gate result with its coverage by method (`; coverage: automated 40/42, browser 3/10, manual 0/2`), as context. |
| Stop | Completion gate | When `state.json` says `current_phase: handoff` for a build scope, runs the gate in the state's `delivery_mode` (production when absent) on each listed verification record. Unless every one passes fresh, it blocks the stop once and names each check as missing, failed, stale, skipped or error. |

A write hook runs after the write: the file is already on disk, and the hook cannot prevent or undo it. Its report names what to fix; the check runs again on the next write. A helper crash, timeout or malformed output is reported as "not verified", never as a pass.

The completion gate never blocks twice in a row (`stop_hook_active`). When it blocks, either run and record the missing checks, or set `current_phase` back to `verify`, record the blocker in `blocked_dependencies`, and tell the user exactly which checks remain. Don't edit the records to get past the gate.

## Reporting

Final reports list each required check with its result and evidence path, then optional checks, then open issues. Never round `unavailable`, `error`, `stale` or `skipped` up to "done". Say what was not verified and why.

- **Say which mode was judged.** "Mock-up criteria met; production not assessed" is not "ready to publish". When both modes matter, report both gate results.
- **Group results by how they were obtained:** automated checks (static helpers), browser measurements (`browser.*`, `visual.measure`) and visual review (`visual.review`, manual judgement from screenshots). A measurement is not a judgement, and a judgement made from three screenshots covers only those three.
- **Carry sampling into the summary.** When a record has `sample_scope` or its limitations say it sampled, the summary says so in the same sentence: "keyboard checked on 3 of 12 pages at 320 and 1280px; the rest unverified".
- **Count grouped warnings honestly:** "6 inferred contrast warnings (91 inferred pairs)", not "6 contrast issues".
