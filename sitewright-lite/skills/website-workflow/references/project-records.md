# Project records

Six records carry a website job from planning to handoff. Both build paths (custom code and WordPress) read the same brief, site map, design and assets records; only the build skills translate them into files, templates or builder structures.

## Where records live

1. Look for existing canonical records first: a product brief, brand guide, design-system doc, sitemap, content inventory, issue tracker or CI report. Link them from the state record instead of copying them.
2. Create `docs/website/` in the user's project only for roles that nothing existing already serves. A small job may keep brief, site map, design and assets in one `docs/website/website.md` with one section per record.
3. `state.json` and `verification.json` are always JSON so helpers can read them. Write them atomically (write a temporary file, then rename).
4. Never create records in a review-only job unless the user asked for them. A planning-only job ends with brief and site map (and design when requested), no build artefacts.

## Field conventions (Markdown records)

- Each record is a heading followed by `- field_name: value` bullets. Page contracts use one `### Page: <route>` heading each.
- A required field is never silently empty. When the value is genuinely not known, write `unknown (OPEN-n)` and add the item to `open_issues` in the state record. When it does not apply, write `n/a: <reason>`.
- Mark the status of every factual claim: `[fact]` (verified business fact), `[supplied]` (given by the user, not independently checked), `[assumption]` (decided by the toolkit to proceed; listed in `assumptions`), `[fixture]` (labelled test data). A real client site never ships `[fixture]` or unlabelled invented testimonials, metrics, prices, awards, legal terms or contact details.

## Brief

| Field | Meaning |
|---|---|
| `audience` | Who the site serves and what they need to decide or do |
| `purpose` | Business outcome the site exists for |
| `primary_action` | The one action that most matters (enquire, buy, book, read, sign up) |
| `claims_and_evidence` | Each public claim with its status marker and evidence source |
| `scope` | Requested pages/features; what is out of scope |
| `delivery_route` | `custom-code`, `wordpress` or `undecided`, plus the discovery facts in "Delivery route discovery" |
| `constraints` | Brand, accessibility, performance, hosting, budget, deadline, legal or content constraints actually stated |
| `unknowns` | Open questions, each with its impact, whether it blocks anything, and the recommended default the work proceeds on |
| `confidence` | Optional: `high`, `medium` or `low` per field, with the reason (see `../../website-plan/references/brief.md`) |

### Delivery route discovery

Record only what was found; do not invent.

- Custom code: framework, rendering mode, routing, component library, styling system, content source, forms backend, hosting boundary.
- WordPress: theme (block, classic or child), builder/editor, active plugins with versions, custom-plugin/child-theme boundary, content fields, templates, forms, staging, access level.

## Site map and page contracts

Site-level fields: `routes` (list), `navigation` (menus and their order), `missing_page_behaviour` (404 handling), `global_components` (header, footer and so on).

Each page contract has these fields:

| Field | Meaning |
|---|---|
| `route` | Path or slug |
| `page_job` | What this page must achieve for the audience |
| `audience` | Primary visitor for this page, if narrower than the brief |
| `primary_action` | The page's main action and its destination |
| `content_source` | Where the copy and data come from (supplied doc, CMS, fixture) |
| `sections_and_hierarchy` | Ordered sections with heading levels |
| `navigation_relationships` | Inbound and outbound links, active-state rules |
| `required_components` | Reusable components the page needs |
| `form_or_data_integrations` | Forms, embeds, APIs; the real backend boundary or `simulated` |
| `states` | Empty, loading, error and success states, or `n/a: <reason>` |
| `metadata_and_indexing_intent` | Title, description, canonical, index/noindex, schema intent |
| `responsive_intent` | How the layout changes across widths |
| `acceptance_checks` | Check IDs from the verification record that prove this page, then any free-text items no check proves (`check-records --phase handoff` lists those as `acceptance_items`, for the handover to mark delivered or dropped) |

The page contract names behaviour, not machinery: no file names, block names or builder widgets. The build skills map each field to their route (`website-build-code` and `website-build-wordpress` each keep a mapping table for every field above).

## Design

| Field | Meaning |
|---|---|
| `authority_source` | Brand guide, existing site, supplied references, or `toolkit default` |
| `design_family` | `none` (default), a named client system, or a family an edition bundles (for example `editorial`) |
| `selected_direction` | The chosen direction in one paragraph and why it fits the brief |
| `semantic_tokens` | Colour, type, space, radius, shadow and motion tokens by role, not by raw value only |
| `type_rules` | Families, scale, measure, weights and their sources/licences |
| `layout_rules` | Grid, rhythm, breakpoints, density |
| `component_states` | Default, hover, focus-visible, active, disabled, loading, error per component |
| `responsive_intent` | Site-wide reflow and zoom behaviour |
| `motion_intent` | Where motion helps, durations/easing tokens, and the reduced-motion behaviour |
| `label_tracking_max` | Optional. The accepted letter spacing for uppercase or small-caps labels, for example `0.16em`. `sw_design_check.py` warns on labels above it (default 0.25em). Running text keeps its own limits |

## Assets

One entry per asset: `asset_id`, `local_path`, `source`, `permitted_use` (what the supplier or licence allows, or `unknown`), `attribution`, `crop_and_size`, `placement` (route and section), `alt_text` (or `decorative`), `status` (`supplied | needed | placeholder | approved | rejected | missing`).

Optional per asset: `supplied_by` (`owner | client | third-party | generated | unknown`), who handed it over or made it.

A text-led site may have an empty asset list. An asset with `permitted_use: unknown` is not published as final; it stays a placeholder or an open issue. Hotlinked remote images are not a final asset. `website-assets` owns this record.

**Standing permission.** When the owner or client says once that a class of their own material may be used (for example "my portfolio work, portraits and the logos of the clients I list"), record it under the assets heading as `### Permission: <id>` with `scope`, `granted_by_role` (`owner` or `client`), `date` and `source` (where they said it). An asset inside that scope then sets `permitted_use: standing:<id>`. This counts as known rights only when `supplied_by` is `owner` or `client`; third-party material still needs its own licence. Only the owner or client grants a permission; Claude records who granted it and when, and never grants one itself. "Supplied" alone is not "authorised".

## State (`state.json`)

The state record indexes artefacts and evidence. It is never proof that they are correct.

| Field | Type |
|---|---|
| `schema_version` | `1` |
| `project_identifier` | string |
| `requested_scope` | `end-to-end-build | plan-only | design-only | review-only | refine-component | verify-only` |
| `build_path` | `custom-code | wordpress | undecided` |
| `selected_framework_or_builder` | string (`static-html`, `react-vite`, `block-theme`, `elementor`, ...) or `undecided` |
| `selected_design_family` | `none | <named client system> | <bundled family>` |
| `current_phase` | `context | structure | direction | prototype | implement | verify | handoff` |
| `completed_artifacts` | list of `{path, phase, fingerprint}`; paths relative to the project root, fingerprints from `sw_records.py fingerprint` |
| `accepted_decisions` | list of `{id, decision, reason}`, each optionally with `status` (`active` or `superseded`), `superseded_by` (the id that replaced it), `source` (who made the decision and when, e.g. `owner, message of 2026-10-25`; needed before `require --decision` may cite it) and `updates` (the project documents the decision changed, e.g. `["docs/website/brief.md"]`) |
| `assumptions` | list of `{id, assumption, affects}` |
| `open_issues` | list of `{id, issue, blocking}`, each optionally with `decision` (the decision it depends on; `check-state` warns once that decision is superseded) and the lifecycle fields in "Issue lifecycle". `blocking` is `true`/`false` or a list of the gate levels it blocks (`mockup`, `production`, `launch`); open blocking issues fail that gate |
| `blocked_dependencies` | list of `{dependency, needed_for, action_needed}` |
| `verification_records` | path(s) to verification records; list them here, not in `completed_artifacts`, since every recorded run changes them |
| `last_changed_targets` | list of paths changed in the last work step |
| `next_owner` | optional skill name that owns `next_action` (e.g. `website-seo`); the session-start summary tells the next session to invoke it first. `check-state` reports a name that is not a skill of the running plugin |
| `next_action` | one sentence under 300 characters, project paths relative to the root (`check-state` warns about longer actions, absolute paths and named files that don't exist); a step that runs a helper gives the complete command to run from the project root, e.g. `python3 "<plugin>/scripts/sw_records.py" gate docs/website/verification.json --root . --mode mockup` |
| `handover` | optional project-relative path of the handover file; default `HANDOVER.md` beside `state.json`. See "Handover file" |
| `session_summary` | optional `true | false`; `true` opts the project in to the session-start summary hook |
| `delivery_mode` | `mockup | production`; what this job is delivering. Set it explicitly and keep it at every checkpoint: absent means production, and `check-state` warns about that for build scopes |
| `delivery_criteria` | optional list of strings: what a mock-up is allowed to leave unfinished (labelled placeholders, simulated forms), each also an open issue |
| `build_output` | optional project-relative folder the build writes into (`site/` for a new static project) |
| `project_instructions` | optional `added | declined`: the project-instruction snippet (see `website-workflow` §2) was offered once and the user's answer |
| `removed_routes` | optional list of `{route, reason}` with `decision` (an accepted decision id) or `source` (who asked and when): routes removed on purpose. See "Removed routes" |

### Handover file

`docs/website/HANDOVER.md` (or the path in `handover`) is what a fresh session reads first. Rewrite it at every checkpoint as the current picture, not a log, and keep it under 8 KB: where the project stands (phase, delivery mode, gate result), what changed this session, the next step and its owner, open questions for the owner, and anything a new session would otherwise rediscover (a local server command, a known trap). Plugin housekeeping (re-recording checks, compacting the verification record) is a task for the next session's skill, never for the owner. `check-state` warns when the file is missing or larger than 8 KB, and reports a defect in phase `handoff`; the session-start summary names it.

### Delivery modes

A **mock-up** is complete when the pages, structure and design are built and every gap is labelled: placeholder assets carry status `placeholder`, fixture content carries `data-fixture`, and integrations without a real endpoint say they are simulated. Each gap is named in `delivery_criteria` and in `open_issues`. **Production** additionally requires final assets with known rights, no fixture markers and real integrations. Report a mock-up pass as "mock-up criteria met; production not assessed". Nothing moves a job from mock-up to production except the user saying so; never waive a production check to make a mock-up look finished. Projects without `delivery_mode` are gated as production, exactly as before.

### Issue lifecycle

Every field below is optional; older issues with only `{id, issue, blocking}` stay valid.

| Field | Meaning |
|---|---|
| `blocking` | `false`, `true` (blocks production and launch, as before) or a list of levels: `["mockup"]` blocks every gate, `["production"]` production and launch, `["launch"]` only the launch stage. Each level includes the ones before it |
| `status` | `open` (default), `resolved` or `wontfix`. Only open issues block |
| `opened` / `resolved` | date and context; `resolved` says who or what closed it (`check-state` warns when a closed issue has none) |
| `source` | who raised it and where, e.g. "owner, message of 2026-10-30" or "website-verify run" |
| `owner` | `{kind: person or skill, name}`: who acts next. Plugin housekeeping (records, evidence, reruns) belongs to a skill, never to the site owner; `check-state` warns when a person owns it |
| `history` | list of `{date, change}`, appended when the issue changes level, owner or status |

Close an issue by setting `status` and `resolved`; don't delete it, so the record shows what was decided. In a git project `check-state` compares with the last commit's `state.json` and reports an issue id that disappeared as a defect. Never lower `blocking` or close an issue just to make a gate pass: that needs the fix, or the user's decision recorded in `history`.

### Output layout

Decide where the build goes before writing any page. A new static project builds into `site/` and keeps its records in `docs/website/`, outside the build output. `check-state` reports `build_output` as a defect when it contains the state record, `verification.json` or the evidence folder, because every check of the build would then fingerprint its own evidence. For an existing structure that mixes them, record a narrower target, or pass `--exclude PATH` (repeatable) when recording, both to the records helper and to the check helpers' `--record`; an exclusion lies inside the target, is listed by `gate` and `status`, and is refused when it holds website files unless `--allow-website-exclusion` is given.

### Removed routes

A page that disappears is a potential regression until the record says otherwise. When the owner removes a page on purpose, add `{"route": "/old-page", "reason": "...", "source": "owner, message of 2026-10-27"}` (or `"decision": "D-7"`) to `removed_routes`. `sw_site_check.py --record` then retires that route's required checks and says so; a missing page that is not listed stays required and is reported as `site.missing-page` (a potential regression). Never add an entry the owner did not ask for.

### Superseded decisions

Never delete a decision. When a later decision replaces one, set the old one's `status: "superseded"` and `superseded_by` to the new id; ids used this way match `[A-Za-z0-9._-]{1,32}`. `check-state` reports an unknown replacement, a superseded decision without one, and cycles. Follow only active decisions on resume. When superseding a decision, review the open issues linked to it: close or re-link each one, and list in the new decision's `updates` every document you changed to match it (brief, design, site map). `check-state` warns when a listed path does not exist, and when a listed document of a decision that replaced another never mentions the new id: a pivot that left the brief or design describing the old direction.

`website-workflow` sets `session_summary: true` when it creates the state record, unless the user declines; set it to `false` to silence the summary. The plugin hooks only read these records (see `../../website-verify/references/evidence-contract.md`, "Plugin hooks").

## Verification (`verification.json`)

See `../../website-verify/references/evidence-contract.md`. It holds `required_checks`, optional `waivers`, and the evidence `records`.

## Invalidation

- A changed brief invalidates the decisions, pages and checks that depend on the changed fields, not the whole project.
- A moved or edited target changes its fingerprint; evidence recorded against the old fingerprint becomes `stale` and cannot be promoted to `passed`.
- A changed token system or design family makes visual and contrast evidence stale for every page that uses those tokens.

## Resume

On resume: read the handover file and `state.json`, check that every `completed_artifacts` path still exists with the recorded fingerprint (`scripts/sw_records.py check-state docs/website/state.json --root <project>`), run the evidence gate (`scripts/sw_records.py gate docs/website/verification.json --root <project> --mode <delivery_mode>`) and read the current view (`scripts/sw_records.py status docs/website/verification.json --root <project>`) to find stale or missing evidence and how to re-run it, reconcile with what the user now asks, then continue with the complete `next_action` from `state.json` (the SessionStart summary shows at most 200 characters and marks a shortened one `…[truncated: N of M characters; read the full next_action in docs/website/state.json before acting]`; never resume from that text) or the first unmet item. Never trust a phase marked done without its artefacts and evidence. A saved summary of verification results (for example a `verification_status` sentence) is a note from the time it was written; the gate's current result replaces it, so report the gate, and update or drop the note.
