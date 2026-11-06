# Frameworks and static-site generators

Use this when the project uses, or the brief needs, a framework or a static-site generator. It covers the decisions that change how the page contracts are built and verified. The framework's own documentation decides syntax: check the installed version's docs before writing configuration, because these tools change between major versions.

## Choosing (new projects only)

| Need in the page contracts | Smallest fit |
|---|---|
| A few content pages, a form, no shared data | Plain HTML/CSS/JS |
| Many content pages from Markdown or data, shared layouts, little client state | A static-site generator: Astro or Eleventy |
| Content site with a few interactive widgets | Astro with islands |
| App-like client state across routes, but still deployable as static files | A Vite app with prerendering, or Next.js / SvelteKit / Nuxt with a static export |
| Server features: auth, per-request data, server actions | A server framework. That's an operations decision, so record the host before building. |

Record the framework, its version and the reason in `state.json` `accepted_decisions`. In an existing project, never switch frameworks or add a second rendering approach.

## What to settle before writing pages

- **Output folder**: where the built HTML lands. Verification runs against this folder, not the source.
- **Site URL**: the production origin, used for canonical URLs, sitemaps and Open Graph URLs. If it is unknown, record a placeholder as an assumption; never ship `localhost`.
- **URL shape**: trailing slash or not, `page/index.html` or `page.html`. Keep it consistent with the site map and any redirects.
- **Rendering per route**: static (built once) by default. Anything rendered on the client must still have meaningful HTML at build time for its headings, main content, links and metadata.
- **Images**: use the framework's image pipeline when there is one, and always give explicit dimensions. A static export may need its image optimiser configured or turned off.
- **Fonts and assets**: self-host them from the project, at the licences recorded in the design record.

## Astro

- Static output is the default. `astro build` writes to `dist/`. Set `site` in the config so canonical URLs and the sitemap integration have an origin.
- Pages are files in `src/pages/`; layouts and components are `.astro` files. Content lives in content collections, whose schema is defined in the content config. Map each page contract's fields to schema fields, so a missing field fails the build instead of shipping blank.
- **Islands**: components ship no JavaScript unless they have a `client:*` directive. Choose the latest moment that still works:
  - `client:visible` for below-the-fold widgets
  - `client:idle` for non-urgent widgets
  - `client:load` only for above-the-fold controls the user needs at once
  - `client:media` for a widget that is only interactive at some widths
  - `client:only` renders nothing at build time, so the content must not depend on it
- Head metadata (title, description, canonical, Open Graph, JSON-LD) goes in a shared layout and takes props from each page's contract.
- 404: `src/pages/404.astro`, which builds to `404.html`.

## Eleventy

- The output folder is `_site/` by default. Data comes from front matter, from global data files and from the data cascade. Layouts are templates chained with `layout:`.
- Set permalinks to match the site map, and check that `permalink` values never collide.
- Eleventy ships no client JavaScript of its own, so every interaction is something you add on purpose.

## Next.js static export

- Set `output: 'export'` in the Next config. The build writes plain files to `out/`.
- Server-only features are unavailable in an export: per-request rendering, route handlers that read the request, incremental regeneration and middleware. If a page contract needs one, the project needs a server host instead. Record that.
- The default image optimiser needs a server. In an export, configure a loader or set images to unoptimised.
- Give each route its own metadata through the metadata API. A layout's metadata is inherited, so override the title and description per page.

## Vite apps (React, Vue, Svelte, Solid)

- `vite build` writes to `dist/`.
- A single-page app serves one HTML file for every route. Search engines, link previews and no-JavaScript visitors then see only that shell. For content pages, prerender each route at build time, or use the framework's static mode: SvelteKit's static adapter, `nuxt generate` for Nuxt, a prerender plugin for React.
- Client routing must keep real links (`<a href>`), restore focus and the document title on navigation, and announce route changes, for example by moving focus to the new page's `h1`.

## Progressive enhancement (all frameworks)

- Content, headings, navigation and links work without JavaScript. Hydration only adds behaviour.
- Forms post with a real `action` and `method`. Client validation adds to server or provider validation; it never replaces it.
- Nothing essential is hidden until a script runs: no content that starts hidden waiting for a fade-in, and no menus that exist only once mounted.
- Every component the framework renders still meets the design record's component states, `:focus-visible` and `prefers-reduced-motion` rules.

## Verify the build, not the source

1. Run the project's own build command, then its lint and test commands if it has them.
2. Run the static site check on the output folder:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_site_check.py" dist --routes routes.json
   ```

   Use the framework's output folder in place of `dist`.
3. If routes are produced by client rendering only, the check sees the shell, not the page. Prerender those routes, or record the gap as `unavailable` with its reason. Never record it as passed.
4. Preview the built output with the framework's preview command, not the dev server, for browser checks.
