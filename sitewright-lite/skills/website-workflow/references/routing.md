# Routing

The workflow decides four things before any specialist loads: scope, phase, delivery route and design family. Record each in `state.json`.

## 1. Requested scope

| Request looks like | `requested_scope` | Boundary |
|---|---|---|
| "Build / make / create a site or page" with enough brief to start | `end-to-end-build` | Plan, design, build, verify, repair and hand off without routine approvals |
| "Plan / outline / sitemap / content strategy only", "don't build yet" | `plan-only` | Brief and site map; stop before design tokens or code |
| "Design / art-direct / mock up" without building | `design-only` | Design record and optional prototype; no production build |
| "Review / audit / check" | `review-only` | Evidence-backed findings; change files only if the user also asked for fixes |
| "Fix / tweak / restyle this component or page" | `refine-component` | Touch only the named target and what it depends on; no redesign |
| "Verify / test / is it ready" | `verify-only` | Run checks and report; no new features |

When wording is ambiguous, pick the narrower scope that still answers the request and say so. A planning-only or review-only request never turns into implementation by default.

## 2. Current phase

Phases: `context → structure → direction → prototype → implement → verify → handoff`.

Detect from `state.json` when present (after reconciling it, see project-records "Resume"); otherwise from the evidence in the project:

| Evidence | Phase to start |
|---|---|
| No brief or record of audience/purpose | `context` |
| Brief, but no site map/page contracts | `structure` |
| Page contracts, no design direction or tokens | `direction` |
| Direction settled; risky layout or interaction untested | `prototype` (skip when nothing is risky) |
| Direction settled; site incomplete | `implement` |
| Site built; required checks missing, failed or stale | `verify` |
| Required checks passed | `handoff` |

Skip a phase only when its exit condition is already met by existing material, and record why.

## 3. Delivery route

| Signal in the project or request | `build_path` |
|---|---|
| `wp-content/`, `wp-config.php`, a theme `style.css` with `Theme Name:`, `theme.json`, `functions.php`, Elementor data/exports, or the user says WordPress | `wordpress` |
| `package.json`, framework config, static HTML/CSS/JS, or the user names a framework | `custom-code` |
| New project and no stated preference | `custom-code` with `selected_framework_or_builder: static-html`, recorded as an assumption |
| Both present (headless WordPress, a static export) | Ask only if the brief cannot settle which side owns templates and content; otherwise record the decision |

Never replace the user's chosen builder, theme, framework, SEO plugin or host. A WordPress project is built as a WordPress project (templates, patterns, builder structures and editable content), not as static HTML with a WordPress label.

## 4. Design family

- `none` is the default. Do not impose editorial rails, type pairs, metadata strips or palettes.
- An edition may bundle named families (listed in its extensions); use one only when the brief, the user or the design record selects it.
- A client design system named in the brief is the family; record its name.

## 5. Skills to load per phase

| Phase | Load | Do not load |
|---|---|---|
| context, structure | `website-plan` | build, motion, assets providers |
| direction, prototype | `website-design`; `website-assets` when assets matter | build skills |
| implement | `website-build-code` or `website-build-wordpress` (one, matching `build_path`); `website-motion` only for planned motion | the other build path |
| verify | `website-verify` | planning references |
| handoff | `website-verify` (report section) | everything else |

Load references inside a skill only for the task at hand.

## Not this toolkit

Do not route here: slide decks, native mobile apps, long-form blog or article production pipelines, backlink or rank-tracking analysis, narration or video, general programming unrelated to a website, and email campaigns. A website request may mention these; handle only the website part and say what is out of scope.
