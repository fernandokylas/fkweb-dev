# Browser checks

How to run the `browser.*` checks with whatever browser automation the session already has.

## 1. Find a tool, don't install one

Look for browser automation already available: a browser MCP server in the session's tool list, or Playwright already installed in the project (`npx --no-install playwright --version` succeeds; plain `npx` may download). Don't enable plugins, install packages globally or download browsers to get one. If nothing is available, follow `no-browser.md`. `sw_integrations.py probe` (see `../../website-workflow/references/optional-integrations.md`) lists the local candidates (project Playwright, installed browsers) without installing anything; it can't see MCP servers, so check the tool list yourself.

Record the exact versions you used: the tool (for example the MCP server package and version), its automation library if it reports one, and the browser name and version. "Latest" isn't a version.

## 2. Decide what needs serving

| Site | How to load it |
|---|---|
| Plain HTML with only relative links | Serving is still better than `file://`, because root-relative links and some APIs fail on `file://` |
| Root-relative links, a build step, or client routing | Build, then serve the build output |
| Needs a backend | Start the project's own dev server command |

Start servers as an argument list, never through a shell string, bound to `127.0.0.1`, on a free port, with a start-up timeout. Wait until the port answers before navigating. Stop every server you started when you finish, even if a check failed, then confirm its port no longer answers: stopping a shell wrapper can leave the real server running.

A framework dev server may run extra development-only behaviour (React StrictMode mounts effects twice, for example). Run the final checks on the production build, and say which you used.

## 3. Look before acting

For each page: navigate, wait for a specific element the page contract names (the `h1`, the form), then take an accessibility snapshot or read the DOM before clicking or typing. Act on what the snapshot shows, not on guessed selectors. Wait for a named element or state change after each action, not for a fixed delay or for "network idle", which never arrives on pages with polling or streaming.

Read the source too when it helps you find the right element or state flag; the checks judge the rendered behaviour, not the code.

## 4. Run and capture

- Keep each check's measurements small and factual: the tab order as a list of names, the `scrollWidth` at 320px per page, the computed `transition-duration` with and without reduced motion, each contrast pair as foreground, background, ratio and selector, the observer count after each remount, console messages.
- Save them as one JSON evidence file per run (`docs/website/evidence/browser-<date>.json`), with the URL, viewport and versions. Screenshots are optional supporting evidence; a screenshot alone doesn't prove keyboard, motion or lifecycle behaviour.
- Use the browser tool's own JavaScript evaluation to read state; don't inject scripts into the site's source to make it testable.

## 5. Record

One record per check and route visited, method `browser`, written from the project root:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" record docs/website/verification.json --root . --check-id browser.keyboard --target <build>/<route>/index.html --inputs-from-page --result passed --method browser --tool-and-version "<tool version>" --evidence-path docs/website/evidence/browser-<date>.json --finding "<what was observed>" --limitations "<what this does not show>" --require
```

Bind the evidence to what the browser loaded: the route's built page as target, with `--inputs-from-page` for the stylesheets, scripts and preloads it links, and `--input` for any data it fetches. Then editing one page makes only its checks stale. Never target the whole build folder, which any rebuild makes stale. A single HTML file with no inputs is recorded but the gate reports it `stale`, because the CSS and JS it loaded aren't covered. Put a run's records in one `record --batch` file (`evidence-contract.md`, "Recording in one write"). Keep the evidence file outside the target and inputs. Each record carries the evidence path, what you observed in the finding, and what it doesn't show in the limitations (for example "Chromium only; Safari and Firefox not run"). A check that crashed, timed out or gave you output you can't trust is `error`, not `failed` and not `passed`.
