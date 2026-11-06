# Optional integrations

Everything Sitewright needs to plan, design, build and statically check a site runs on Python's standard library and the files in the project. The integrations below add evidence or assets when the user's environment already has them. None of them is a dependency: when one is missing, the job continues on its fallback and the affected check is recorded honestly.

## Rules

- **Find, don't install.** Use what the session or project already has. Don't install anything globally, download browsers, enable plugins or MCP servers, or run `npx` without `--no-install`. A project-local or scratch install happens only when the selected stack needs it or the user asks, with network permission, and is reported.
- **Missing is never passing.** A check that needed a missing integration is `unavailable` (or `skipped` with the reason when it doesn't apply to this job). A tool that crashed or timed out is `error`. Neither counts as `passed`.
- **Authority per outward call.** A paid or external call (generator, stock service, SEO data, upload) needs the user's authority in this conversation for that call. A credential being present is not authority.
- **Credentials stay in the user's environment.** Read them from environment variables or the provider's own login only when a call is authorised. Never write a key, token or password into a record, evidence file, page, log or commit, and never print one.
- **Say what leaves the machine** before the call: which files, prompts or URLs go to which service.

## Probe what is available

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_integrations.py" probe --project <project-dir> [--playground-dir <scratch-dir>] [--credential-env NAME ...]
```

It is offline: it looks for local executables and runs only their `--version`, each with a 5 second limit, and reads installed package versions from `node_modules`. It installs and downloads nothing. Each integration comes back `available` (with a version or path), `unavailable` (with what was looked for), `skipped` (a script can't see it, or it is deferred) or `error` (found but its version check crashed or timed out; treat it as unavailable). `--credential-env` reports only whether a variable is set, never its value. The probe can't see the session's MCP tools, so `browser-mcp` is always `skipped` there: look at the tool list yourself.

Record the versions you actually use in the evidence and the environment notes, not the probe's output alone.

## Registry

What each integration enables and what happens without it:

| id | Used by | Enables | Fallback when missing | Result when missing |
|---|---|---|---|---|
| `browser-mcp` | website-verify, website-motion | Rendered-page checks (`browser.*`), screenshots, motion review | Project Playwright, else `no-browser.md` | `browser.*` checks `unavailable` |
| `playwright-local` | website-verify | Same rendered-page checks from a script | A browser MCP server, else `no-browser.md` | `browser.*` checks `unavailable` |
| `browser-binary` | website-verify | A browser for the two above to drive | none; static checks still run | `browser.*` checks `unavailable` |
| `node` | website-build-code, website-build-wordpress | JS builds (Vite/React fixtures), Playwright, Playground | Plain HTML/CSS/JS build; static WordPress checks | build or runtime checks `unavailable` |
| `wordpress-playground` | website-build-wordpress | Local WordPress runtime, probe and editor checks (`playground-runtime.md`) | `sw_wp_theme_check.py` static checks | `wp.runtime-*` (theme, templates, content), capture and editor checks `unavailable` |
| `page-builder-runtime` | website-build-wordpress | Verified Elementor (or other builder) output | Block theme; adapter marked unverified (`elementor-adapter.md`) | builder checks `unavailable`; no support claim |
| `image-provider` | website-assets | Generated or stock images | Asset brief, `needed`/`placeholder` assets, user-supplied files | asset stays `needed` or `placeholder` |
| `seo-data-provider` | website-plan | Keyword and ranking data | Brief-led content plan and static SEO checks | deferred: not offered |
| `design-engine` | website-design, website-verify | Third-party design linting | `sw_design_check.py` (token drift, static contrast and type, asset rights) | baseline only |
| `export-video-3d` | none | Video, slide, PDF or single-file artifact export, 3D reconstruction | Not part of a website job | deferred: not offered |
| `third-party-site-embeds` | website-plan, website-build-code, website-build-wordpress | Web fonts from a CDN, maps, video, analytics inside the built site | Self-hosted fonts and media, a static map image or link | a decision in the brief, not a check |

What each one costs, sends and needs:

| id | Dependencies | Cost | Data leaving the machine | Authority needed | How to detect |
|---|---|---|---|---|---|
| `browser-mcp` | A browser automation MCP server already enabled in the session | none | Local pages only (loopback) | None if already enabled; enabling one is the user's choice | The session's tool list |
| `playwright-local` | Playwright in the project's `node_modules`, plus a browser | none | Local pages only | None if installed; installing needs the user | `node_modules/.bin/playwright` in the project |
| `browser-binary` | Chrome, Chromium, Edge or Firefox, or Playwright's browser cache | none | None by itself | None | Application paths, `PATH`, Playwright cache |
| `node` | Node.js on `PATH` | none | None by itself; package installs use the network | None to use; installs need permission | `node --version` |
| `wordpress-playground` | Node and `@wp-playground/cli` in a scratch or project dir | none | First run downloads WordPress and PHP; serving is loopback only | Network permission for the install and first run | `node_modules/.bin/wp-playground-cli` (`--playground-dir`) |
| `page-builder-runtime` | The user's WordPress site with the builder (and its licence) | the user's builder licence | Stays in the user's environment | The user supplies the environment; no live mutations | Not scriptable: the user says where it runs |
| `image-provider` | A provider account and the user's credential | paid per call | Prompts, reference images and brand material go to the provider | The user's authority for each call | `--credential-env NAME` (presence only) |
| `seo-data-provider` | A provider account | paid account | Site URLs and queries | Deferred: not offered | none |
| `design-engine` | A third-party linter installed by the user | none | Local | Not bundled; a user's own run is advisory | none |
| `export-video-3d` | Media engines, model weights | varies | Varies | Deferred: not offered | none |
| `third-party-site-embeds` | The service the site embeds | varies | Visitors' requests (IP address, page) go to the third party | Decided in the brief with the owner; privacy notice and consent where required | Read the built pages |

## Deferred and not offered

`seo-data-provider` and `export-video-3d` are deliberately absent (decision D-21). There is no adapter, no credential handling and no instruction for them. They are reconsidered only when a user asks for one and authorises its cost and data flow. Until then the website job does not need them.
