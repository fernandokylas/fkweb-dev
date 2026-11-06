---
name: website-build-code
description: Builds the production pages of a custom-code website (plain HTML/CSS/JS, or a framework app such as React/Vite) from the Sitewright brief, page contracts and design record. Sets up or follows the project's stack, implements tokens, shared layout, every page with its content, form and data states, metadata and 404, then runs the static site check and hands over to verification. Use it for the implement phase when build_path is custom-code, when the user asks to code, build or extend a static site or framework site (React, Vite, Astro, Next, Vue, Svelte), fix a layout or responsive bug, or add a contact form or 404 page outside WordPress, or when website-workflow routes here. Not for WordPress themes or page builders, and not for planning or visual direction. For a whole website job or a resumed one, `website-workflow` is the entry point and routes here.
---

# Website build: custom code

Owns the **implement** phase for `build_path: custom-code`. It turns the shared records into working pages. The records' fields are defined in `../website-workflow/references/project-records.md`; precedence is in `../website-workflow/references/precedence.md`.

Read the brief, site map, page contracts and design record first. If a design field the build needs is empty, the direction phase isn't done: go back to `website-design`. Don't invent the missing decisions in code.

## 1. Settle the stack

Read `references/project-setup.md`.

- **Existing project**: follow its framework, folder layout, styling method, component library, linting and test commands. Don't reorganise unrelated files or add a second way of doing something the project already does.
- **New project**: choose the smallest stack that serves the page contracts. Plain HTML/CSS/JS for a few content pages; a framework when the contracts need client state, routing or data the server can't render. Record the choice and reason in `state.json` `accepted_decisions`.
- **Framework or static-site generator** (Astro, Eleventy, Next static export, a Vite app): read `references/frameworks.md` for the output folder, site URL, islands and prerendering decisions, and verify the built output, not the source.
- **Dependencies**: prefer the platform. Add a package only for a need the contracts state, pin exact versions, install locally, and never install globally or run install scripts you haven't read. Record each addition and its licence.

## 2. Build the shared layer

1. **Tokens**: implement the design record's tokens as CSS custom properties (or the project's token mechanism). Components use semantic tokens, never raw values.
2. **Base styles**: type scale, measure, spacing rhythm, `:focus-visible` style, and a `prefers-reduced-motion` block, all from the design record.
3. **Shared components**: header with navigation, footer, buttons, form controls and any component listed in more than one page contract. Each one implements every state in the design record's component states.

## 3. Build every page

Map each page contract field to code with `references/page-contract-mapping.md`. For every page:

- One `h1`, landmarks, headings in order; the first viewport serves `page_job` and shows `primary_action`.
- Real content from `content_source`. Where content is missing, use clearly marked fixture copy (`data-fixture` plus a visible note) and log an open issue; the release check rejects fixture markers.
- Navigation from the site map, with `aria-current="page"` on the active item and every internal link resolving.
- Forms and data: read `references/forms-and-states.md`. Build empty, loading, error and success states, and make each reachable for review. A form with no real endpoint gets a labelled simulated handler, never a fake "sent" message.
- Responsive and input behaviour: read `references/responsive-and-touch.md`. No horizontal scroll at 320px; touch and hover handled as capabilities, not breakpoints.
- Metadata from `metadata_and_indexing_intent`, plus the delivery items in `references/delivery.md` (404, canonical, sitemap, icons, build output).

When the design record plans motion beyond simple transitions (a scroll narrative, a sequenced reveal), load `website-motion` for that part. Simple state transitions stay here, written from the design record's `motion_intent`.

## 4. Check before handing over

Run the static site check on the built output (the folder of HTML files, or the framework's build output):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_site_check.py" <built-site>
```

It checks landmarks and headings, metadata, internal links and fragments, active navigation, form labels and states, image alternatives, reduced-motion handling, placeholder copy, fixture markers and the 404 page. Exit 0 is passed (warnings allowed), 1 is failed, 2 is error. For a client-rendered app, check a DOM capture of each route with `--routes` (see `references/delivery.md`); a check of the empty app shell proves nothing about the pages.

While iterating, run it without recording. Fix every `failed` finding and rerun. When the implement phase is done, record it once, adding `--record docs/website/verification.json --root . --evidence-out docs/website/evidence/static-check-<date>.json --require`; `website-verify` then reruns it only if `status` lists it stale or missing. Keep the site's own build setup and asset naming (hashed file names included): never change them to suit verification, since file-set targets already follow content, not names. Then update `state.json` atomically (see `../website-workflow/references/project-records.md`) (`completed_artifacts`, `last_changed_targets`, `next_action`) and continue to `website-verify` for browser checks, without pausing for approval. The static check alone never shows a page works in a browser: don't describe the build as verified until `website-verify` has run.

## Rules that always apply

- Only build what the page contracts ask for. Extra pages, sections or features are scope changes; record them as open issues instead.
- Don't publish, deploy, call paid services or send real form data. A live endpoint needs a recorded user decision and credentials the user supplied. Never write a key, token or sample credential into the code.
- Keep fixture and review-only code (state flags, sample data) out of production behaviour, or mark it so the release check catches it.
- For a small change to an existing site, change only the targets the request names and record them in `last_changed_targets`; rerun the checks for those targets.
