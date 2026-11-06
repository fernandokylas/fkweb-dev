# Site structure and page contracts

How to turn the brief into routes, navigation and one contract per page. Field definitions: `../../website-workflow/references/project-records.md`.

## Size the site to the job

Start from the primary action and work backwards: which pages does a visitor need before they act? Most small businesses need a home page, one page per real offer or audience, and a contact or booking page. Add pages only when they hold content the user actually has or a job no other page does. A one-page site is a valid answer.

## Routes and navigation

- Use short, readable routes that match the words visitors use (`/menu`, not `/our-offerings`).
- Primary navigation holds the few destinations most visitors need, in journey order. Legal and secondary pages go in the footer.
- Decide `missing_page_behaviour` (a helpful 404 that links back to the main routes) and `global_components` (header, footer, skip link, any persistent call-to-action).
- Every route in `routes` has a contract, and every contract's route is in `routes`. The records helper checks this.

## The main journey

Write the journey down: entry page → pages read → primary action → what happens after (confirmation, email, call). Check:

- the primary action is reachable from every page in one or two steps;
- nothing in the journey depends on content that is `unknown` without a planned placeholder;
- the post-action state is planned (success message, error message, what the visitor should expect next).

## Filling a page contract

- `page_job`: one sentence about what the visitor should know or do after this page.
- `sections_and_hierarchy`: ordered sections with heading levels. One `h1` per page and no skipped levels. Each section has a reason tied to the page job.
- `content_source`: name where each block of copy comes from. Write `placeholder (OPEN-n)` where content is still owed.
- `navigation_relationships`: what links in, what links out, how the active page is shown.
- `required_components`: reusable pieces (card, menu list, opening-hours table, form). Reuse across pages keeps the build small.
- `form_or_data_integrations`: the real endpoint or service if one exists and is authorised. Otherwise write `simulated` and plan a visible "not yet connected" state. Never plan a fake key or endpoint.
- `states`: empty, loading, error and success for anything dynamic. Write `n/a: static page` when nothing is dynamic.
- `metadata_and_indexing_intent`: title and description purpose, canonical, index or noindex (thank-you pages and drafts usually noindex), and structured-data intent only for facts that are actually known.
- `responsive_intent`: what changes across widths and what must never be hidden on small screens (the primary action, prices, opening hours).
- `acceptance_checks`: verification check IDs that prove the page works, in the form `area.check` (for example `nav.internal-links`, `a11y.focus-visible`, `form.error-state`, `content.no-invented-proof`). List them comma-separated, each item starting with its ID; a note may follow the ID (`form.error-state (?state=error)`). `website-verify` turns these into required checks: from the verify phase on, `check-records` reports an ID that no `required_checks` entry names as a defect.

## Proof placement

Place each piece of supporting evidence beside the claim it supports (an accreditation beside the service it covers, a review beside the offer it praises), not collected in a decorative band. Where proof is missing, the contract keeps the slot with a placeholder and an open issue, or drops the claim.

## Existing sites and small changes

For a change to an existing site, write contracts only for the pages that change, and record the existing conventions (navigation pattern, component names, copy tone) the change must keep. Don't restructure pages that weren't part of the request.
