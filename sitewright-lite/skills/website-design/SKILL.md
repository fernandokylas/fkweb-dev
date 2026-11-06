---
name: website-design
description: Sets the visual direction for a website before it is built. Decides how far to depart from existing brand material, writes the design record (direction, semantic tokens, type, layout, component states, responsive and motion intent), builds a small prototype only when a risky question needs answering, and self-reviews against generic defaults. Use it for the direction and prototype phases, when the user asks for a look and feel, style direction, design tokens, colour or type system for a site, or when the website-workflow skill routes here. Not for writing production pages or WordPress templates. For a whole website job or a resumed one, `website-workflow` is the entry point and routes here.
---

# Website design

Owns the **direction** and **prototype** phases. It produces the design record that both build paths implement, using the fields in `../website-workflow/references/project-records.md`. It does not write the production site.

Read the brief and site map first. If they are missing, the plan phase is not done: go back to `website-plan`.

## Settle the authority

Precedence is in `../website-workflow/references/precedence.md`. In practice:

1. **Supplied design system or brand guide**: implement it. Your job is to fill its gaps consistently, not to restyle it.
2. **Existing site**: extend its established look unless the user asked for a redesign.
3. **Nothing supplied**: you choose the direction, grounded in the subject.

Record which one applied in `authority_source`.

## Choose the direction

Read `references/direction.md`. Decide how much invention the job wants (extend, place within an existing world, create, or replace), then write `selected_direction` as one paragraph tied to the audience, purpose and content. Explore alternatives only when direction is genuinely open, and do it internally; pick one and record why. Don't stop to make the user choose between concepts unless they asked to see options.

**Direction per page type.** Before the full build, carry the direction to every template type in the site map: home, content page, listing, article, form, legal, the 404 page and any page with its own layout. Write one line per type in `layout_rules`: a layout word for each main section, its one focal element and the components it reuses. Pages the supplied design doesn't show (often the 404, articles and legal pages) get their line too, so they are designed rather than left to defaults. See `references/direction.md`.

## Write the system

- **Tokens**: read `references/tokens.md`. Name tokens by role (text, surface, accent, border, focus, spacing steps, radius, duration). Check text and focus contrast as you choose colours, not afterwards.
- **Type**: pick families with a known source and licence (system stacks, self-hosted open-licence fonts, or fonts the client supplied). Record source and licence in `type_rules`. Never hotlink fonts or assets for the final build without saying so.
- **Layout**: grid, measure, rhythm, breakpoints and density, in `layout_rules`. Name the spacing steps the rhythm uses; the visual review judges gaps against them.
- **Label tracking**: when small uppercase or small-caps labels use letter spacing, record the largest accepted value as `label_tracking_max` (for example `0.16em`). The design check judges labels against it instead of the 0.25em default; running text stays limited to 0.12em.
- **Component states**: for each component in the page contracts, record default, hover, focus-visible, active, disabled, loading and error (or `n/a`).
- **Motion**: read `references/motion-intent.md` and write `motion_intent`. Motion is decided per interaction by purpose and frequency. "None" is a valid decision.
- **Assets**: when imagery, logos or brand files matter, load `website-assets` for the assets record. Unknown rights mean placeholder, not final.

## Prototype only when it pays

Build a prototype only to answer a specific risky question: a dense layout at small widths, an unusual navigation pattern, a type pairing at real content length. Keep it throwaway, outside the production build (for example `docs/website/prototypes/`), and remove it or mark it non-production once its question is answered. Record the question and the answer in the design record. Skip the phase when nothing is risky.

## Review before handing over

Read `references/review.md` and check the direction against it: specific to this subject rather than a generic template, readable, accessible, honest copy. Separate objective findings (contrast, missing states) from taste. Fix objective ones now. On built pages, review in critique rounds from fresh screenshots, with a sameness pass (`references/review.md`).

Then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" check-records docs/website --phase implement
```

`passed` means every design field is filled, with no placeholder values. Update `state.json` and continue to the build skill for the recorded path, without pausing for approval. If that skill is not available, follow `website-workflow` section 3: continue from the shared records and name the missing skill. For `design-only` scope, stop here and deliver the design record, plus the prototype if one was made.

Human design feedback that hasn't arrived yet is an open issue, not a blocker. Don't describe the direction as approved or better than alternatives until a person has reviewed it.
