# Check catalogue

Standard check IDs. Use them exactly so records from different runs line up. Add project-specific IDs under the same prefixes when a page contract needs them (`browser.scroll-story`, `browser.lifecycle`).

## Static checks (`sw_site_check.py`)

Method `automated`. They read HTML, CSS and JS files only; nothing runs in a browser.

| ID | Proves | Doesn't prove |
|---|---|---|
| `a11y.landmarks` | `<html lang>`, exactly one `main`, header, nav and footer present, one `h1`, no skipped heading levels (`<noscript>` content ignored) | Reading order on screen, focus behaviour |
| `meta.basics` | Non-empty title and meta description, viewport meta; no canonical is a warning; a 404 page needs neither description nor canonical | That titles are unique or the copy is good |
| `meta.indexing` | Each page's robots meta (`robots`/`googlebot` with `noindex` or `none`) matches its page contract's `metadata_and_indexing_intent`, read from `--records DIR` (default: the folder of `--record`, whose Markdown records become inputs, so a contract change makes the record stale). A mismatch either way is a warning without `--release` and a defect with it; a noindex at release with no stated intent is a warning (404 pages exempt). Mode as for fixture markers | `X-Robots-Tag` headers, `robots.txt`, or what the live host serves (check those after deploy) |
| `nav.internal-links` | Internal links and `#fragments` resolve to files or declared routes; no `href="#"`, empty or example-domain links. An Elementor `#elementor-action:` link (popup) is a warning to check in a browser | External links work |
| `nav.active` | The current page is marked `aria-current="page"` in the navigation, and no other link is | That the style makes it visible |
| `form.labels` | Every control has a label | Labels are understandable |
| `form.states` | The page has a live status region; a form with no endpoint is marked `data-handler="simulated"` and says so in visible text | That the states work when triggered |
| `media.images` | Every image has an `alt` attribute; missing width and height is a warning, and so is a local image file over 400 KB (a slow largest paint on phones) | That alt text is accurate, or that decorative images use empty alt |
| `motion.reduced` | Pages that animate in CSS or scripts have `prefers-reduced-motion` handling | That the handling is complete |
| `content.placeholders` | No lorem ipsum, TODO, TBD, TBC, FIXME, template company names or draft notes (`(verify …`, `[confirm …`, `verify:`, `[NEED: …`, `à vérifier`) in page text; plain "verify"/"confirm" in copy is fine. Warning: a page other than the 404 with under 30 words outside header, nav and footer and no form, table, address, image or embed (a page published empty) | Content is correct |
| `content.tells` | Warns (`review`, never a defect) when a page's visible copy uses a stock contrast cadence three or more times: "Not a X. Y.", "X, not Y." or a short "No …" / "Just …" rebuttal | That the voice is wrong: keep it when the content direction asks for it, otherwise rewrite; a lasting exception is an `accept-finding` decided by the user |
| `content.mockup-notes` | Visible placeholder labels and mock-up notes. Explicit markers come first: `data-mockup`, `data-mockup-note`, `data-placeholder` (a value other than `false`), and any class named with `--mockup-class` (repeatable, e.g. the project's `is-placeholder`). A cautious text rule adds an element whose whole text is a label such as "Placeholder", "Placeholder image" or "Mock-up", or that starts with "Placeholder:" / "Mock-up:". Hidden, `aria-hidden`, `display:none`, `<template>`, `<script>`, `<style>`, `<noscript>`, code samples, comments, attribute values (including `placeholder=""`) and prose that only mentions the word are never flagged. A warning without `--release`; with it, a defect. Mode as for fixture markers | That nothing unmarked remains; wording that doesn't match the label rule |
| `integration.form-endpoint` | One record per page with a form. With `--release`: a declared simulation (`data-handler="simulated"`, or visible text the form describes as not connected or demo only), a missing endpoint (`action` empty or `#` and no handler) or an example host fails; a real-looking endpoint is `unavailable` and nothing is recorded, because source alone does not show a working submission. Without `--release`, a disclosed simulation or a declared endpoint passes the mock-up criteria. Production needs a `browser` or `manual` submission record (see below) | That submission works; spam protection, delivery and notifications |
| `content.fixture-markers` | Fixture markers reported as a warning; with `--release`, any marker fails (recorded with mode `production`; without `--release`, mode `mockup`) | That the labelled content is acceptable for a mock-up |
| `site.404` | A `404.html` or `404/index.html` page exists (with `--routes`, among the captured page files) | That it links home, or that the server returns status 404 |

## Design and asset checks (`sw_design_check.py`)

`scripts/sw_design_check.py` compares the design and assets records with the built CSS (`--site <dir>`) or a block theme and its `theme.json` (`--theme <dir>`). It reads source only; nothing is rendered.

| Check ID | Proves | Does not prove |
|---|---|---|
| `design.token-drift` | Every token in `semantic_tokens` is defined by the build, with the recorded value where the record gives one | That components use the tokens |
| `design.raw-literals` | Warns on colour literals written into declarations instead of tokens (one warning each), and on spacing lengths (margin, padding, gap, inset) and durations (transition, animation) written as literals (one summary warning per stylesheet and kind, naming the token a literal equals). Zero, hairlines of 1px or less and `var()` fallbacks are ignored | — |
| `style.contrast` | Text/background pairs that resolve from the CSS meet 4.5:1 (3:1 large text) in every colour scheme the CSS defines. A pair set in one rule (`basis: declared`) is a defect; a pair inferred from separate rules (`basis: inferred`) is a warning, one per colour pair with its selectors | Rendered contrast over images, gradients, stacked or runtime backgrounds: run `browser.contrast` |
| `style.leading` | Running-text line height is inside readable bounds | How text actually wraps |
| `style.tracking` | Letter spacing judged by role. Running text (paragraphs, list items, cells) above 0.12em is a defect. An uppercase or small-caps label at 16px or less is judged against the design record's `label_tracking_max` (default 0.25em, warning only). An element whose role is unclear (inline text, generated content) above 0.12em is a `review` warning. A selector with no element type in its last part (`.intro`, `#lead`, `[data-tone]`), or an uppercase rule above 16px with no tag, is `unclassified`: above 0.05em or below -0.03em it is a `review` warning sent to browser review, listed in `tracking_unclassified` and in the record's `limitations`, and never a defect. Settle the role with the `tracking` section of `visual-measure.js` | The role a selector plays on every page; text length |
| `layout.grid-items` | Warns (`review`) when a grid container's own `::before`/`::after` has content and stays in flow, so it takes a grid cell | That it is visible or wrong: run `visual.measure` |
| `layout.spacing-reset` | Warns (`review`) when a later rule in the same stylesheet sets a heading's top margin to 0 after another rule gave it one | Cascade layers, specificity and which rule wins on a page |
| `style.justify`, `style.padding` | Warn on justified text without hyphenation and cramped filled controls | Touch-target size: run the browser check |
| `assets.rights` | Each asset has a known permitted use (unknown is a defect when approved or with `--release`), a credit where the licence asks for one, and every build image is in the assets record | That a licence is genuine |
| `assets.local-path` | `local_path` is project-relative (not a URL, absolute or outside the project) and exists for supplied and approved assets | That the image suits its placement |
| `assets.final` | With `--release`, no asset is still `placeholder`, `needed` or `missing` (skipped otherwise, recorded as optional) | — |

The asset checks are recorded with mode `production` under `--release` and `mockup` without it; the other design checks carry no mode and count for both. Pass `--mode` to override.

A missing design or assets record is `unavailable`; a text-led site with no assets and no images skips the asset checks; malformed `theme.json`, oversized or undecodable files and bad arguments are `error`.

## Browser checks

Method `browser`. Record the tool and browser versions exactly.

| ID | Procedure | Passed when |
|---|---|---|
| `browser.keyboard` | Tab through each page from the top; use the skip link | Every interactive element is reached in a sensible order with a visible focus indicator; the skip link moves the next Tab into `main`; no trap |
| `browser.reflow-320` | Set the viewport to 320px wide on every page | `scrollWidth` ≤ viewport width; no clipped text or overlapping controls |
| `integration.form-endpoint` (submission) | Submit valid input to a local capture stub on 127.0.0.1, or to the provider's test mode when the user has authorised that call. Never send a real enquiry or call an external service without authority. Save the request and response (or network capture) as the evidence | The request arrives with the expected fields and the page shows the success state. Record with `--method browser` (or `manual`) and `--mode production`; only such a record satisfies the production gate |
| `browser.form-states` | Submit empty, invalid and valid input; reach the loading state | Errors are announced and linked, focus moves, loading prevents resubmission, success says what happened (and that it was simulated, if it was) |
| `browser.reduced-motion` | Emulate `prefers-reduced-motion: reduce`, reload, and also switch it while open | No movement or pinning; content complete; transform and position transitions removed; opacity or colour changes 150 ms or less |
| `browser.no-js` | Disable JavaScript and load each page | Content pages read in full; client-rendered pages show their `<noscript>` alternative |
| `browser.console` | Load every page and run the main interactions | No errors and no failed requests for site files |
| `browser.contrast` | On every page, in the default theme and each colour scheme the site ships, read each visible text element's computed colour and the first opaque background behind it, and compute the WCAG contrast ratio; repeat for focus indicators and control borders | Text ≥ 4.5:1, large text (≥ 24px, or ≥ 18.66px bold) ≥ 3:1, focus indicators and control boundaries ≥ 3:1 against what is next to them. Text over an image, gradient or video can't be computed this way: list each one in the limitations and judge it from a screenshot, or the check isn't passed |
| `browser.scroll-story` | Scroll each narrative step to the centre | The active step and visual follow in order |
| `browser.lifecycle` | Mount, unmount and remount motion components several times | The live observer or listener count returns to the unmounted baseline after each unmount and doesn't grow across remounts; no animations left on removed nodes; the record names how the count was taken |

`browser.*` IDs only carry method `browser`; `sw_records.py` rejects any other method for them.

## Visual composition

See `visual-review.md`. Measurement and judgement are separate records.

| ID | Method | Passed when |
|---|---|---|
| `visual.measure` | `browser` only | `scripts/visual-measure.js` ran after `swRevealSweep()` on every page, width and colour scheme in the sample, plus a print pass per template type, and its JSON is saved. It measures gaps, edges, grid cells, sideways overflow, clipped, edge and invisible text, framed media, repeated template devices and the look of shared components; it never judges |
| `visual.review` | `manual` only | Every screenshot in the sample was judged (each listed in `judged` and bound as an input) against the design record's `layout_rules` and space tokens, and no spacing, alignment, hierarchy, grid-item, responsive, breakage, hidden-content, template-device or cross-page consistency finding is open |

Without a browser both are `unavailable`.

Other browser IDs used by page contracts: `a11y.focus-visible` (every focusable element shows a visible focus indicator), `form.error-state` (an error state is reached and announced).

## Stress cases

`stress.long-text`, `stress.translation`, `stress.missing-image`, `stress.empty-list`, `stress.one-item`, `stress.many-items`, `stress.zoom`, `stress.slow-network`: method `browser` or `manual`, with the values used in the finding. See `stress-cases.md`.

## Source review

`source.focus-styles`, `source.reduced-motion`, `source.form-states`, `source.cleanup`: method `manual`, for when no browser is available (`no-browser.md`). They never satisfy a `browser.*` requirement.

## Manual checks

Method `manual`, for judgements a tool can't make: copy accuracy, image suitability, whether alt text describes what each image contributes, brand fit (for example `content.accuracy`, `content.no-invented-proof`). Name the reviewer's basis in the finding. A manual check is never recorded as passed on the strength of a static or browser result alone.

## WordPress checks

The WordPress path adds its own IDs, defined with their failure conditions in `website-build-wordpress` (its `wordpress-checks.md` reference); the gate treats them the same way.

- Static theme (method `automated`, no runtime): `wp.theme-header`, `wp.theme-json`, `wp.tokens`, `wp.block-markup`, `wp.template-structure`, `wp.patterns`, `wp.content-editable`, `wp.assets`, `wp.php-safety`.
- Runtime (method `automated`, needs the read-only probe from a local WordPress): `wp.runtime-theme`, `wp.runtime-templates`, `wp.runtime-content`.
- Rendered capture (method `automated`): `capture.routes`, `capture.not-found`, `capture.assets`, `capture.metadata-links`; the capture is then checked with the static site IDs above.
- Editor (method `browser`): `browser.wp-editor-valid`, every content page opens in the block editor with no invalid or fallback blocks.

Without a WordPress runtime the runtime, capture and editor IDs are `unavailable`.
