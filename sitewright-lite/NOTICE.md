# Notices

Sitewright lite is © 2026 Fernando Kylas and released under the MIT licence in `LICENSE`. That licence covers the original work in this package. It does not change the terms of the third-party material listed below.

The full record for every upstream part (ledger, extraction cards and source hashes) is kept in the author's development workspace and is not published with this package.

## Bundled material

No third-party text, code, images, fonts, audio or model weights are included in this package.

## Concept credits

The projects below were studied while designing Sitewright lite. Ideas from them shaped the original guidance and helpers named in each row.

- **What was used:** concepts only, with no upstream text or code included. The wording and code are new.
- **How that was checked:** item 08 ran a six-word phrase-overlap scan of `skills/` against every candidate repository and found only standard idioms.
- **Why they are listed:** these credits are given as acknowledgement. No upstream licence text has to be carried, because nothing was copied. Each project's own licence still applies to the original project.

| Project (snapshot) | Licence | Ideas credited | Where the original Sitewright work lives |
|---|---|---|---|
| banana-claude (AgriciDaniel) | MIT | Brief before imagery; an explicit outcome per image candidate | `skills/website-assets/references/image-direction.md` |
| Emil Kowalski skills | MIT | Build helpers, touch and responsive handling, stress cases, motion review, motion removal hazards (`remove-animations`, `animation-performance`) | `skills/website-build-code/`, `skills/website-motion/`, `skills/website-verify/` references |
| WordPress skills (Jorge Rosal) | MIT | Block-theme structure, content model, review domains, Playground as an optional runtime | `skills/website-build-wordpress/` references; `scripts/sw_wp_theme_check.py` |
| Taste skill (Leonxlnx) | MIT | Motion intent, brief and redesign prompts; layout breakage measures (overflow culprits, clipped and edge text, re-implemented); critique rounds, fix order and the sameness pass (`critique.md`, rewritten) | `skills/website-design/` and `skills/website-plan/` references; `skills/website-verify/scripts/visual-measure.js` |
| Impeccable | Apache-2.0 | Brief shape and context, direction modes, review references, the idea of static design checks, triage of checker warnings (`skill/reference/hooks.md`), a critique closed only by a later pass (`skill/reference/polish.md`, concept), the reveal sweep (`crates/browser/src/lib.rs`, adapted), the aphoristic-cadence idea (`crates/detect/src/regex_matchers.rs`) | `skills/website-plan/references/brief.md`, `skills/website-design/references/`; `skills/website-verify/scripts/visual-measure.js` (`swRevealSweep`); `scripts/sw_site_check.py` (`content.tells`); `skills/website-verify/SKILL.md` and `references/evidence-contract.md` ("Accepted findings"); `scripts/sw_design_check.py` (new stdlib code, not derived from the engine source) |
| Anthropic skills: frontend-design, webapp-testing | Apache-2.0 | Design direction and review, browser check practice | `skills/website-design/references/`, `skills/website-verify/references/browser-checks.md` |
| UI/UX Pro Max (Next Level Builder) | MIT | Token records compared with built output; brand intake | `skills/website-design/references/tokens.md`, `skills/website-assets/references/intake.md`; `scripts/sw_design_check.py` |
| Huashu design (alchaincyf) | MIT | Brand asset protocol, direction exploration, template-device counts (Huashu's `design_lint.py`, re-implemented) and the rule that they need a decision, not a ban (`references/evolution.md`) | `skills/website-assets/references/intake.md`, `skills/website-design/references/direction.md`, `skills/website-verify/scripts/visual-measure.js` (`tells`), `skills/website-verify/references/visual-review.md` (no Huashu wording translated or adopted) |
| claude-blog (AgriciDaniel) | MIT | Content references, delivery contract, hidden-text measure and reviews bound to the files they judged (concepts) | `skills/website-plan/references/site-structure.md`; `scripts/sw_records.py gate`; `skills/website-verify/scripts/visual-measure.js` (`invisible_text`); `scripts/sw_records.py` (`judged`) |
| claude-seo (AgriciDaniel) | MIT | Page-level technical checks; `<` written as `\u003c` in embedded JSON (`seo-cluster`) | `skills/website-build-code/references/delivery.md` |
| img2threejs | Apache-2.0 | Resumable state with evidence | `scripts/sw_records.py` (`check-state`, `gate`) |
| Anthropic knowledge-work-plugins: brand-voice guideline generation | Apache-2.0 | A confidence rating per section; open questions that each carry a recommended answer | `skills/website-plan/references/brief.md` |

## Left out

Some candidate material was not adopted, deferred, or excluded because its rights were unclear. None of it is in this package. The development repository records why for each:

- generated or bundled audio
- slide template packs
- the web-artifacts tarball with shadcn/ui code
- GSAP skill text
- UI/UX Pro Max data catalogues
- paid image and SEO provider integrations
- 3D reconstruction tools

## Things this package does not bundle

Sitewright lite can use tools the user already has, such as:

- browser automation (Chrome DevTools or Playwright tools)
- Node, Playwright and browser binaries
- WordPress Playground
- a licensed page builder

Each of these has its own licence and terms. The package never installs or downloads them. `skills/website-workflow/references/optional-integrations.md` describes each one: what it costs, what data it sends off the machine, and what it falls back to when missing.

Websites built with Sitewright lite can load fonts, images or scripts chosen in the project. Those assets carry their own licences, recorded per asset in the project's assets record.
