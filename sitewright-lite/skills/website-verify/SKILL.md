---
name: website-verify
description: Verifies a built website against its page contracts and records honest evidence. Runs the static site check, browser checks for keyboard, reflow, form states, reduced motion, colour contrast, no-JS behaviour, motion lifecycle and console errors when a browser tool is available, stress cases with worst-case content, motion review and a visual composition review of spacing, alignment and grids; records every result as passed, failed, unavailable, error, stale or skipped and runs the verification gate. Use it after building or changing pages, before any hand-over or release claim, when the user asks to test, check, audit or QA a website, asks whether it is ready, or wants an accessibility, keyboard or release check, or when website-workflow routes the verify phase here. Works with no browser available, reporting browser checks as unavailable rather than passed.
---

# Website verify

Owns the **verify** and **handoff** phases for both build paths. It checks the built site, writes evidence records, and reports what is and isn't proven. The evidence rules are in `references/evidence-contract.md`; read it before recording anything.

The one rule above all: a check that didn't run isn't a pass. Missing tools, crashes, timeouts and old results are `unavailable`, `error` or `stale`, and the report says so.

## 1. Plan the checks

From the page contracts' `acceptance_checks` and states, and the design record's motion and component states, list the checks this site needs. `references/check-catalogue.md` names the standard check IDs and what each one proves. Add a site-specific check (for example `browser.scroll-story`) where a contract asks for behaviour the catalogue doesn't cover.

Mark each check required or optional. Required checks block the gate; optional ones are reported. Record an optional check with `--required-or-optional optional` and without `--require`.

## 2. Static checks (always available)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_site_check.py" <built-site> --record docs/website/verification.json --root . --evidence-out docs/website/evidence/static-check.json --require
```

Then compare the records with the build:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_design_check.py" --site <built-site> --records docs/website --root . --record docs/website/verification.json --evidence-out docs/website/evidence/design-check.json --require
```

Use `--theme <theme-dir>` instead of `--site` for a block theme. `style.contrast` here covers only pairs the CSS resolves; `browser.contrast` stays required.

When the build recorded its site check at its checkpoint and `status` lists it current, don't run it again. Give each later run a new `--evidence-out` (for example with the date in its name): a helper refuses to overwrite a file that earlier records cite, and its error suggests a free path. Add `--release` (or `--mode production`) to both before a release. Only release-sensitive checks are recorded with that mode, so one run serves both gates. Pass project marker classes for placeholders and mock-up notes with `--mockup-class` (repeatable). Pass `--records docs/website` (or the project's records folder) so `meta.indexing` compares each page's robots meta with its page contract; with `--record` beside the records it is found on its own. For a client-rendered app, check DOM captures with `--routes`, following the capture procedure in the `website-build-code` delivery reference. For a WordPress build, run `sw_site_check.py` on captured front-end HTML (it doesn't read theme files), and also run `sw_wp_theme_check.py` on the theme and content with the same `--record --root . --evidence-out <file> --require` flags, adding `--probe` when a local WordPress ran; the commands and IDs are in `website-build-wordpress`'s `wordpress-checks.md`.

## 3. Browser checks (when a browser tool exists)

Read `references/browser-checks.md`. Probe for a browser automation tool already available in the session; don't install one or enable a plugin to get it. If there is one: serve the site locally, look at the page before acting, run each browser check, and record it with method `browser` and the exact tool and browser versions. Record against each route you visited (its built HTML page) with `--inputs-from-page`, never against the whole build folder, so one page's edit makes only that page stale; record all of a run's checks in one `record --batch` file. Before a run of several steps (a form submission, a menu walk-through), mark it with `sw_records.py begin` so an interrupted run reads `error`, not the older pass (`references/evidence-contract.md`, "Runs in progress").

Then review composition: read `references/visual-review.md`, take the screenshot set, run `scripts/visual-measure.js` in each page (judge from its numbers first, and open only the screenshots a finding needs; hand a full visual pass to a reviewer agent when one is available, so the images stay out of this context), and record `visual.measure` (method `browser`, the numbers) and `visual.review` (method `manual`, your judgement against the design record's layout rules) as separate records. The static `layout.grid-items` and `layout.spacing-reset` warnings tell you where to look first.

If there isn't one, read `references/no-browser.md`: record each required `browser.*` and `visual.*` check as `unavailable` with an issue ID, keep the static findings, and make no claims about appearance, interaction or motion.

## 4. Stress cases and motion review

- Read `references/stress-cases.md` and run the cases that apply: long and translated text, missing images, empty, one and many items, 200% and 400% zoom.
- Where the site has motion, read `references/motion-review.md` and review it by purpose, frequency, reduced-motion behaviour and lifecycle.

## 5. Record and gate

Each check that isn't recorded by a helper is recorded, from the project root, with:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" record docs/website/verification.json --root . --check-id <id> --target <path> [--input <path> ...] --result <result> --method <automated|browser|manual> --tool-and-version "<tool version>" --evidence-path <file> --finding "<what was observed>" --limitations "<what this does not show>" --require
```

Always pass `--root .` from the project root; it makes every path project-relative. Add `--input` for every other file the check depended on; for a built page, `--inputs-from-page` adds the stylesheets and scripts it links. A file set such as `dist/**/*.css` is a valid target or input and follows file content, not names, so hashed asset names need no change to the build. Several checks from one run go in one `record --batch FILE.json` call; a rerun that repeats the current record appends nothing. Details: `references/evidence-contract.md` ("Dependency fingerprints", "Recording in one write", "Unchanged reruns").

**When to record.** Record the full set at the end of a phase, before any deploy, at final QA and for a named regression. Between those checkpoints, iterate with unrecorded runs (the same helpers without `--record`); then rerun only what `status` lists as stale or missing.

Then run the gate:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" gate docs/website/verification.json --root . --mode production
```

Pass the mode in `state.json`'s `delivery_mode`: `--mode mockup` for a mock-up. If every page reads as "target no longer exists", check the root before anything else: the reason names the path it looked for, and the gate's diagnostics say when the targets exist under another root.

Exit 0 means every required check passed on the current files. Any other result means it isn't ready: fix `failed` findings in the build skill and rerun; turn `stale` into a fresh run; leave `unavailable` as a named limitation. A required `skipped` check is unmet. Don't edit a record by hand to make the gate pass.

The gate judges production criteria unless given `--mode mockup`. Use the mode in `state.json`'s `delivery_mode`, and keep that field set explicitly (`"mockup"` or `"production"`) at every checkpoint: without it, hooks and gates judge the project as production; for a mock-up, also say that production was not assessed. Don't run the helpers without `--release` to make a production failure go away: a mock-up record never counts for the production gate. To change which gates require a check, use `sw_records.py require` with `--reason` (and `--decided-by` when it weakens a requirement), never a hand edit (`references/evidence-contract.md`, "Changing a requirement"). A production pass shows only the declared production checks; it does not establish every aspect of launch readiness.

For a readable current view, run `sw_records.py status` with the same arguments as the gate. It names what changed for each stale check and groups everything not passed by the command that re-runs it. Each hint has a quoted `command` to run from the project root and a new `evidence_out`, so earlier records keep their evidence. Re-run those checks; reusing an earlier evidence file for a new pass is reported as `stale`. Superseded records move to the append-only `verification-archive.jsonl` as new ones are recorded; `sw_records.py compact` (dry run; `--write` to apply) also moves older history ("Current view and history"). A page that disappears stays required and is reported as a potential regression; only a route listed in `state.json` `removed_routes` with the owner's decision is retired by `sw_site_check.py --record`, and `sw_records.py retire` handles the rest. Once the gate passes, `prune-evidence` deletes uncited evidence files; before that, `prune-evidence --current-only` archives superseded records and deletes only what no current record cites ("Pages removed or moved", "Pruning evidence").

## 6. Report

Follow the reporting rules in `references/evidence-contract.md`: the delivery mode judged, each required check with its result and evidence path, grouped as automated checks, browser measurements and visual review, then optional checks, then open issues and limitations, carrying every sampled scope into the summary. Update `state.json` (`current_phase`, `open_issues`, `verification_records`, `next_action`), writing it atomically as `../website-workflow/references/project-records.md` describes.

**Triage each warning.** Fix a real problem. A warning you can show is a false positive, or an exception the user already chose, gets the narrowest acceptance: the user runs `sw_records.py accept-finding` for that check, file and quoted finding text ("Accepted findings"). If unsure, ask the user once, in one line. Never accept a warning to avoid a fix; defects can't be accepted. `status` lists warnings seen in three or more recorded runs (`recurring_warnings`): triage those first.

Handoff doesn't wait for anyone: report every unmet required check as an open issue with its result. The site counts as verified only when the gate passes; a waiver needs an explicit user decision, recorded with `sw_records.py waive` (owner, expiry and scope; the user supplies `--decided-by`, never the agent: see `references/evidence-contract.md`, "Waivers"). Publishing, deploying and live WordPress changes are outside this skill; they need a separate instruction from the user. On the WordPress path, when the site runs on a real staging or live install, run `wp-predelivery-check` before handoff and put its READY / NOT READY verdict and report path in the handover; a NOT READY verdict is an open issue, never a pass.
