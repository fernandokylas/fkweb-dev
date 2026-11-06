# Delivery items

The pieces a site needs beyond its page bodies. Each is checked before hand-over.

## Per page

- `<html lang>` set to the content language.
- `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- A unique `<title>` and meta description from `metadata_and_indexing_intent`.
- A canonical link once the production origin is known. Until then, the static check reports its absence as a warning; record the origin as an open issue rather than inventing one. Build canonical, `hreflang` and Open Graph URLs from one configured origin per environment: on a preview or review host they are left out (and the page is `noindex`), never pointed at production from a host that serves different content.
- `hreflang` only for pages that exist in every listed language, as reciprocal pairs (each version lists all the others and itself) plus `x-default` where there is a language chooser. A page whose translation isn't live yet carries no `hreflang` for it.
- `robots` meta only when the contract says the page shouldn't be indexed. Fixture and preview builds use `noindex`.
- Structured data (JSON-LD) only for types the contract names, with values that match the visible page. Don't add schema for content that isn't on the page.
- An icon (`<link rel="icon">`), so browsers don't log a missing `favicon.ico`.
- The image most likely to be the largest paint above the fold (hero, first product photo) is not `loading="lazy"`; give it `fetchpriority="high"` instead. Lazy loading is for images further down.

## Safe output

- **Escape by context.** Text from content files goes through the template's escaping; attribute values are quoted and escaped (`"`, `&`, `<`). JSON-LD is serialised with a real JSON serialiser and every `<` written as `\u003c`, so a title containing `</script>` or `<!--` can't end the script element. Never build markup or JSON by string concatenation of content.
- **No inline styles or handlers.** No `style=""` attributes and no `onclick=`-style handlers in the output: they force a weaker Content Security Policy. Dynamic values go in classes or custom properties set from a stylesheet or a script file.
- **CSP on staging first.** Send `Content-Security-Policy-Report-Only` on the staging or preview host from the first deploy, so anything the policy would block shows up in the console before production enforces it. Move to an enforced `Content-Security-Policy` when the report is clean; record the policy and any allowed third-party origin in `accepted_decisions`.
- **One file per route.** Two sources must not produce the same URL (`about.html` and `about/index.html`, a page and a redirect, two content entries with the same slug). Check the build output for duplicates before hand-over, and decide trailing-slash handling once.
- **Clean output.** The release build holds only what the site serves: no source files, `.env`, editor or OS files, test fixtures, unminified duplicates or draft pages that aren't linked.

## Without JavaScript, in print and in dark mode

- Content and navigation work without JavaScript: links are real links, the menu is reachable (an open list, or a `<details>` disclosure that scripts enhance), and revealed-on-scroll content is visible by default, hidden only by a class that the script adds.
- A menu that opens over the page moves focus into it, keeps background content out of reach (`inert` on the rest of the page, or a modal `<dialog>`), closes on Escape and returns focus to its button.
- Print styles undo reveal and motion start states (`opacity: 0`, transforms, clipped heights), hide navigation and decorative media, and show link URLs where they matter. Check with print emulation.
- Dark mode, when the design has one, comes from `prefers-color-scheme` in CSS. A toggle may override it, but the page renders in the right scheme before any script runs, with no flash, and both schemes meet the contrast thresholds.

## Per site

- A custom 404 page (`404.html` or the framework's not-found route) with the site navigation or at least a link home.
- A `sitemap.xml` and `robots.txt` once the production origin is known.
- No links to example domains, `#` or empty `href` values; links to routes that don't exist yet are open issues, not placeholders.

## Build output

- The production build runs from a clean install with the recorded commands, without errors or type errors.
- Fixture markers (`data-fixture`, "[fixture]") are allowed during development, in test fixtures and in a mock-up whose `delivery_criteria` accept them. Before a release build, `sw_site_check.py --release` fails on any that remain.
- A mock-up is finished when its own criteria pass (`gate --mode mockup`): labelled fixture copy, placeholder assets and simulated integrations are allowed, each listed in `delivery_criteria` and open issues. Production also needs final content and assets with known rights and real integrations (`gate --mode production`, the default). Report a mock-up as "mock-up criteria met; production not assessed", never as ready to publish.
- Placeholder labels and mock-up notes carry an explicit marker (`data-mockup`, `data-mockup-note`, `data-placeholder`, or a project class passed with `--mockup-class`), so `sw_site_check.py --release` finds every one that remains. Hidden documentation stays out of visitor-facing output.
- A form in a mock-up says it is simulated (`data-handler="simulated"` plus visible text). For production it needs a real handler, and a submission tested against a local capture stub or the provider's test mode (with authority for any external call), recorded with `--method browser` or `manual`. An endpoint in source is not a working form.
- `--mode production` on a helper means the same as `--release`; `--mode mockup --release` is an error. Only release-sensitive checks are recorded with a mode, so one run gives accurate mock-up and production status. Set which gates require a check with `sw_records.py require`, not by hand.
- A production pass establishes only the required checks declared for production. Report it as that, not as proof of every aspect of launch readiness.
- Source maps, review flags and debug logging are off in the release build unless the user asked for them.

## Checking client-rendered output

`sw_site_check.py` reads HTML files. For a framework app whose HTML is an empty shell until JavaScript runs:

1. Build and serve the production output locally.
2. With a browser tool, capture `document.documentElement.outerHTML` for each route after it renders, and save each capture as a file in a folder that also holds the build's assets (copy the build output, then overwrite its HTML with the captures).
3. Write a routes file mapping each capture to its URL path, for example `{"index.html": "/", "about.html": "/about", "404.html": "/404"}`.
4. Run `sw_site_check.py <capture-folder> --routes routes.json --evidence-out docs/website/evidence/static-check-rendered-dom.json`, then record the result against the source folder with `sw_records.py record docs/website/verification.json --root . --target <source-folder>`, adding `--input` for each build input outside it (`index.html`, `package.json`, the lockfile, the build configuration).

`<noscript>` content is ignored when counting landmarks and headings, because it never renders alongside the scripted page. If no browser is available, check the shell and say plainly that the rendered routes weren't checked.
