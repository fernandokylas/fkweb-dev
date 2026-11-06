# Changelog

## 0.3.4 — 2026-11-06

### Fixed

- `tests/visual/test_visual_measure.py` could not load on Python 3.9 because of a syntax error, so its 14 tests never ran there. They now load and pass on Python 3.9. No change to the plugin's behaviour.

## 0.3.3 — 2026-11-06

### Changed

- The README now presents Lite as the free demo of Sitewright, says what the full edition adds, and says Lite is maintained with bug and security fixes. No change in behaviour.

## 0.3.2 — 2026-11-01

### Changed

- Wording of a code comment in `sw_records.py` and of the 0.3.1 notes. No change in behaviour.

## 0.3.1 — 2026-11-01

From a comparison with Ubersuggest's site audit and PageSpeed on two live WordPress sites. `sw_site_check` moves to tool version 6; older records don't become stale, and the new rules apply from the next run.

### Added

- `content.placeholders` warns on a page published empty: under 30 words outside header, nav and footer (or inside a single `<main>`), with no form, table, address, image or embedded media. 404 pages are skipped.
- `media.images` warns when an `<img src>` resolves to a file in the built site heavier than 400 KB.

### Fixed

- `nav.active` reads absolute menu links to the site's own origin, as WordPress writes them, so the current-page marker is checked on CMS menus too.
- `meta.basics` no longer asks a 404 page for a description or canonical.
- `nav.internal-links` treats Elementor `#elementor-action:` popup links as a review warning (they work only with JavaScript). It no longer reports them as missing fragments with advice to add an id.

## 0.3.0 — 2026-11-01

From six projects built with Sitewright 0.2.2 and reviewed on 31 October 2026: the gate passed while visitors could still see problems, records drifted from the site, verification evidence grew without bound, designs stopped at a competent template, and launches went out with draft text. Upstream ideas are adapted with provenance (cards in `docs/development/provenance/`, credits in `NOTICE.md`); nothing is a runtime dependency.

### Migration

Every new field is optional and `state.json` stays at `schema_version` 1. Most new rules start as warnings. These change what an existing project sees:

- **Two new defects.** A page contract's acceptance check that no `required_checks` entry names is a defect from the verify phase on (it was a warning). An open issue whose `blocking` covers the gate's level fails the gate; legacy `blocking: true` blocks production. Map the check with `require`, or close the issue (`status: resolved`).
- **Placeholders.** `content.placeholders` also finds `TBC`, `[NEED:`, `à vérifier` and the bracketed or colon forms of verify and confirm. `sw_records` moves to tool version 4 and `sw_site_check` to 5 (with `content.tells`). The version doesn't make older records stale; the new patterns apply from the next run.
- **`sw_design_check` tool version 4.** `design.raw-literals` adds one warning per stylesheet and kind for spacing and duration literals, from the next run.
- **Identical reruns append nothing.** `record` returns `"unchanged": true` and keeps the older record and its evidence; `--append-unchanged` forces a new record. Helpers delete a fresh evidence file that no record cites.
- **Waivers** may carry `owner`, `expires` and `scope`; older waivers still count, with a `status` warning.
- **`visual.review`** passes written without `--judged` get a `status` warning.

### Added

- **Gate and launch safety.** One placeholder pattern for records and page text. `meta.indexing` compares each page's robots meta with its contract (a defect with `--release`). Issue lifecycle fields (`opened`, `source`, `owner`, `status`, `resolved`, `history`, `blocking` by level). Waivers with owner, expiry and scope, and the `waive` command. A launch stage for required checks (`gate --mode production --stage launch`). `begin` markers so an interrupted multi-step run reports `error` instead of leaving an older pass standing.
- **Records and handover.** A short handover file (default `HANDOVER.md` beside `state.json`, under 8 KB) and a portable `next_action` (warnings over 300 characters, absolute paths, missing files). Decisions list the documents they `updates`. In a git project a vanished issue id is a defect: issues are closed, never deleted; plugin housekeeping is never an owner task. `check-records --phase handoff` lists free-text acceptance items. The brief rates confidence per field and ends with questions for the client, each with a recommended default.
- **Leaner verification.** Unchanged reruns are skipped (above). `coverage` by evidence method in `gate`, `status` and the session summary. Site-check rerun hints name only the changed pages (`--page`). `prune-evidence --current-only` archives superseded records and prunes without a passing gate. `accept-finding` records the user's acceptance of one warning, in the narrowest form; helpers report accepted findings apart. `recurring_warnings` counts warnings across helper runs; `status` lists those seen in three.
- **Design quality.** `visual-measure.js` v2: sideways overflow with its culprit, clipped and edge text, framed-media insets, invisible text, the media it measured, template-device counts (`tells`) and shared-component digests (`components`); `swRevealSweep()` before full-page captures. `content.tells` warns on stock contrast cadence. `website-design` carries the direction to every page type before the full build (including 404, article and legal pages) and reviews built pages in at most three critique rounds from fresh screenshots, with a sameness pass.
- **Build defaults** (`website-build-code` `references/delivery.md`): environment-aware canonical and hreflang (reciprocal pairs only, off on review hosts), no lazy LCP image, escaping by context (JSON-LD `<` written as `\u003c`), no inline styles or handlers, CSP Report-Only on staging first, no-JS navigation, menu focus and Escape, print that undoes reveal states, dark mode without a flash.
- **Motion removal** (`website-verify` `references/motion-review.md`): the hazards left behind when an animation goes, and a "from code" or "needs a device recording" label on motion findings.
- **Project hygiene** (`website-build-code` `references/project-setup.md`): git from kickoff with a commit per working step, atomic writes, scratch kept outside the project, no identifiers or secrets inline, the site never bent to suit the records, checks in `package.json` scripts and CI.

### Known limitations

- Whether agents follow the new guidance (critique rounds, client questions, hygiene) is not measured: behaviour runs are paid and were not run for this release.
- The browser measures need a local headless Chrome; without one `tests/visual` reports unavailable.
- wp-essentials' `predelivery_check.py` still uses its own placeholder list (separate release).

## 0.2.2 — 2026-10-31

- Now installed from the `fkweb-dev` marketplace: `claude plugin marketplace add fernandokylas/fkweb-dev`, then `claude plugin install sitewright-lite@fkweb-dev`. The `fernandokylas/sitewright` marketplace is retired. No change to the skills, scripts or hooks.

## 0.2.1 — 2026-10-22

### Migration

Existing records keep evaluating as before; every new field is optional. After the first re-run, the old per-stylesheet and whole-folder pairs show as missing targets or superseded: clear them with `sw_records.py retire --all-missing` (dry run, then `--write`) and `compact --write`. A project that made its CSS file names unhashed for verification can restore hashed names. List intentionally removed pages in `state.json` `removed_routes` before the next site check.

### Added

- **Routing per request.** `website-workflow` §3 is "Pick the owner, then load it": every new request, including a tracker task, a handover or a note, gets its owner from the "By request" table before any file is edited, and is invoked with the Skill tool unless already loaded. The phase table stays. `state.json` takes an optional `next_owner`; the session-start summary (also sent after compaction) names it and prints this edition's owners from `hooks/owners.txt`. When it creates `state.json`, the workflow offers a short CLAUDE.md snippet and records `project_instructions`.
- **File-set targets.** A target or input may be a glob (`dist/**/*.css`) fingerprinted by content, not names, so hashed asset names stay current across rebuilds. `sw_design_check.py` records stylesheet checks against `<build>/**/*.css`, and against the expected record file (not `docs/website`) when the Design or Assets record is missing.
- **Per-route browser records.** `record --inputs-from-page` adds every local stylesheet, script and preload a built page links; the guidance records browser and visual checks per route, never against the whole build folder.
- **Batch recording.** `record --batch FILE.json` validates every entry and writes them in one atomic write, or none; the helpers' `--record` writes a run the same way.
- **Append-only archive.** Superseded records move to `verification-archive.jsonl` as newer ones are recorded (the reuse guard still reads them); `compact` also moves records of pairs no longer required, honours `--exclude` and compares gates per check result.
- **Removed routes.** A page missing from the build stays required and is reported as `site.missing-page`, a potential regression. Only a route listed in `state.json` `removed_routes` with an accepted decision or a `source` is retired by `sw_site_check.py --record`, and reported under `route_changes`.
- **Asset authority.** Assets take `supplied_by`; an owner or client can grant a standing permission (`### Permission: <id>`, with `granted_by_role`, date and source) that `permitted_use: standing:<id>` cites. It never covers third-party material, and only the owner or client grants it.
- **Citing a decision.** `require --remove --decision D-ID` accepts an active accepted decision with a recorded `source` in place of `--decided-by`; `status` lists every weakening by what authorised it. Open issues may link the `decision` they depend on, and `check-state` warns when it is superseded.
- **Speed.** The gate indexes records per pair and fingerprints each path once per run; the session-start summary uses `check-state --quick`.
- **Guidance.** Record verification at checkpoints (phase end, before a deploy, final QA, a named regression) and iterate unrecorded in between; the build records its site check once at its checkpoint; never change a site's build or asset naming to suit verification; judge screenshots from measurements first and open only the ones a finding needs.
- **Budget.** Every `SKILL.md` stays at or under 12,000 characters, so it survives re-attachment after compaction.
- `sw_records.py retire`: stops requiring checks on pages that were removed or moved, after checking the file is gone, the root is right and the site map no longer lists the route. Retired checks show as not assessed, never passed, and apply again if the file returns. It needs no `--decided-by`, so an agent never has to enter a person's name; `require` points to it when a weakening on a missing target is refused.
- `sw_records.py prune-evidence`: once the gate passes, deletes evidence files no record still cites (dry run unless `--write`; only under `evidence/`, symlinks never followed, `compact` archives kept), then re-runs the gate.
- `website-build-code/references/frameworks.md`: choosing a framework or static-site generator, the output folder, site URL and URL shape, Astro islands and content collections, Eleventy, Next.js static export, Vite apps and prerendering, progressive enhancement, and verifying the built output.

### Changed

- The design-family wording in `website-workflow` and the project records is generic: `none`, a named client system, or a family an edition bundles. Lite's own default is unchanged.
- `website-workflow` hands each phase to its skill by calling the Skill tool and does not write that phase's files itself; it does a phase's work directly only when the phase skill is not listed as available.

## 0.2.0 — 2026-10-19

First release after the release candidates. Lite is now a slim core plus WordPress essentials.

### Added

- WordPress essentials, kept in step with the standalone `wp-essentials` plugin:
  - `wp-site-setup`: a British English baseline profile (`en_GB`, `j F Y`, `H:i`, Monday weeks, city timezone), image sizes 0, no month/year upload folders, comments, pings and registration off, `/%postname%/` permalinks and default content removed. `wp_settings.py plan` prints the commands; `verify` reads them back.
  - `wp-page-update`: safe edits to one page on a live or staging site, with a backup, a before/after scope check (`scope_check.py`) and a read-back.
  - `wp-site-audit`: read-only audit (`site_probe.py`).
  - `wp-predelivery-check`: READY / NOT READY gate before launch or handover (`predelivery_check.py`).
- PreToolUse guard hook (`hooks/wp_guard.py`): asks before hard-to-reverse WP-CLI commands.
- `website-build-wordpress` routes real installs to `wp-site-setup` and live page edits to `wp-page-update`; `website-verify` runs `wp-predelivery-check` before a WordPress handoff.
- README quick start and a one-line meaning for each status word.

### Changed

- The Editorial craft family (20 specialists and `web-craft`), its write hook and the plugin-conflict notice moved to the full Sitewright plugin.
- Provenance notes moved to `docs/development/provenance/` and are no longer shipped; concept credits live in `NOTICE.md` only.
- The WordPress probe (`sitewright-wp-probe 3`) refuses proxied requests (`X-Forwarded-For`, `Forwarded`, `X-Real-IP`) as well as non-loopback ones, and reports hook callback counts instead of callback names. The theme check accepts probe versions 2 and 3.
- Manifest: version 0.2.0, `license` and `keywords` added.

### Known limitations

- WordPress essentials were tested on WordPress 7.1.3 with MariaDB 11 in Docker, not on a managed host. Core's 1536/2048 image sizes and the `-scaled` copy need the optional mu-plugin that `wp-site-setup` shows; options alone cannot stop them.
- Browser checks used scripted headless Chromium; Safari, Firefox and real devices were not tested.
- The packager ships git-tracked files only: new files must be added to git before `dev/package.py` will include them.

## Earlier versions

0.1.0-rc.1 to rc.5 (6–9 October 2026) built the records contract, the evidence gate, the two build paths and the visual review. Their full notes are in `docs/development/CHANGELOG-0.1.md`.
