# Project setup for custom-code sites

## Read the project before adding anything

Before writing code in an existing project, find out:

- the framework and version (`package.json`, lockfile, config files), and whether it renders on the server, at build time or in the browser;
- where pages, components, styles and static files live, and how routes are declared;
- the styling method already in use (plain CSS, CSS modules, a utility framework, CSS-in-JS) and any token or theme file;
- which UI component library is installed, if any;
- the commands for dev, build, typecheck, lint and test, and whether they currently pass.

Follow what you find. A second styling method, router or component library in one project is a defect, not a choice.

## Where the build goes

Settle the output folder before writing the first page, and record it as `build_output` in `state.json`. A new static project builds into `site/` and keeps its records in `docs/website/`, so a check of the site never fingerprints the records it writes. A framework app keeps its own output folder (`dist/`, `build/`). In an existing project, keep the layout it has. When the site is built at the project root and can't move, record checks against a narrower target or pass `--exclude docs/website` when recording; never exclude website files (pages, styles, scripts, images, fonts) to make a check pass. `check-state` reports a `build_output` that contains the records.

## Choosing a stack for a new project

| Page contracts need | Default |
|---|---|
| A handful of content pages, a form, no client state | Plain HTML, one CSS file with tokens, small progressive-enhancement scripts |
| Many pages from structured content (menu, listings, articles) | A static site generator or a build script that renders templates from content files |
| Client state, interactive tools, data fetched after load, many interdependent views | A framework app (for example React with TypeScript and Vite) |

Prefer output that works without JavaScript for content pages. When a page needs JavaScript to show its content, give it a `<noscript>` message with an alternative (a phone number, an email, a static copy).

## Choosing UI primitives

1. An existing component library in the project wins, whatever you would have picked yourself.
2. If the need is met by native elements (`<details>`, `<dialog>`, `<select>`, form validation), use them.
3. Only when a component is hard to make accessible by hand (combobox, date picker with keyboard grid, menus with typeahead), add one maintained, accessible library for it, and only for the components that need it. Record the package, exact version and licence.

## Dependencies

- Pin exact versions in `package.json` and commit the lockfile.
- Install into the project only. No global installs, no `curl | sh`, no post-install scripts you haven't read (`npm install --ignore-scripts` when in doubt).
- Each added dependency gets a line in `accepted_decisions`: what need it serves and its licence.
- Fonts, icons and images follow the assets record; a file with unknown rights is a placeholder, not a final asset.
- Keep `node_modules`, build output and local caches out of version control.

## Project hygiene

- **Version control from the start.** In a new project, run `git init` at kickoff (with the user's go-ahead if the folder already holds their files) and commit at each working step: setup, each page or template, each fix round. One commit at launch loses the history that explains a regression. Never commit secrets, and never push without the user's go-ahead.
- **Atomic writes.** A script that writes a large file writes it to a temporary name in the same folder and renames it into place, and removes the temporary file on failure. Half-written files and leftover `.tmp` files are defects.
- **Scratch stays out of the project.** Browser-tool output (`.playwright-mcp/`, traces, ad-hoc screenshots), downloads and experiments go in a scratch folder outside the project, or in an ignored folder. Screenshots that are evidence go under `docs/website/evidence/`.
- **No identifiers or secrets inline.** Host account IDs, project IDs, API tokens and form keys live in environment variables or the host's settings, read by the build or the deploy command; the repository holds their names, not their values.
- **The site doesn't bend to the records.** Never change the site's build, routes or markup only to satisfy a Sitewright check or record. If a check misreads the site, record the false positive (`accept-finding` for a warning, decided by the user) or report it; change the site only when the finding is real.
- **Checks live with the project.** Add the build, typecheck and any check the project can run on its own to `package.json` scripts (or the project's task runner), so they run the same way locally and in CI. Sitewright's records point at those commands; they don't replace them.

## Commands to know before hand-over

Record in the project's README or state the exact commands for: install, dev server, build, typecheck and tests. Run build and typecheck before calling the implement phase done; a build that has not been run is `unavailable`, not passed.
