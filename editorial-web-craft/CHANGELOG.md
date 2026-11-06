# Changelog

## 1.0.4 — 2026-11-06

- Six skill descriptions name HTML elements in plain words instead of angle-bracket tags, because claude.ai warns about tags and strips their brackets. No change in what the skills do.

## 1.0.3 — 2026-11-06

- Fix: `inline-svg-decorator`'s `scripts/wave.py` crashed on Python 3.9 with a `TypeError` before producing any output. It now runs on Python 3.9 and later.

## 1.0.2 — 2026-10-31

- Now installed from the `fkweb-dev` marketplace: `claude plugin marketplace add fernandokylas/fkweb-dev`, then `claude plugin install editorial-web-craft@fkweb-dev`. The plugin no longer carries its own marketplace manifest; the marketplace replaces the `fernandokylas/editorial-web-craft` repository.
- `scripts/validate.py` also checks that `hooks/hooks.json` parses and names existing scripts, and that each command has frontmatter with a description.
- `tests/run_fixtures.py` also fails on a checker reporting ERROR or UNAVAILABLE, unparseable audit output, an exit code that disagrees with the findings, and fixtures missing from `expected.json`.
- New `tests/smoke.py`, replacing the GitHub CI workflow: audits the bundled assets and examples, syntax-checks the bundled JS (with Node) and smoke-tests the hook.
- `.skill` files for Claude.ai are now built locally with `scripts/package_skills.py`.

## 1.0.1 — 2026-09-19

- Fixed: plugin.json no longer declares `hooks/hooks.json` a second time. Claude Code loads that file on its own, and the duplicate failed with "Duplicate hooks file detected", so none of the plugin's hooks loaded.

## 1.0.0 — 2026-09-17

First public release.

- Twenty skills: layout-editorial-rail, fluid-clamp-calculator, visual-weight-tuner, z-index-coordinate-matrix, cls-dimension-anchor, editorial-type-tokens, typographic-rag-tuner, accessible-ink-scale, ground-inversion-guard, adaptive-luminescent-border, inline-svg-decorator, perceived-latency-mask, tactile-interaction-curves, gsap-timeline-orchestrator, sub-pixel-inertia-scroll, magnetic-hitbox-warp, reduced-motion-enforcer, encapsulated-mockup-builder, cascading-specificity-guard, html5-native-fallback.
- `web-craft` orchestrator: routes a brief or an existing page through the set, runs the combined audit, previews with Chrome DevTools at three widths and under reduced motion.
- `/editorial-web-craft:craft` command; write-time audit hook gated on the set's layer marker; bundled Chrome DevTools MCP.
- Seven audit scripts and three generators; `scripts/audit.py` runs them all.
- Three example pages that pass every audit.
