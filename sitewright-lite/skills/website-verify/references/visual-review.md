# Visual composition review

Static checks can't see composition. A page can pass every check and still have a heading that sits closer to the paragraph above than to its own text, a decorative rule that has become a grid item and pushed a row out of line, or a column whose edge drifts by a few pixels. This review finds those. It has three parts, recorded separately:

| Check ID | Method | What it is |
|---|---|---|
| `layout.grid-items`, `layout.spacing-reset` | `automated` (`sw_design_check.py`) | Source warnings that point the review at likely problems. They never fail on their own |
| `visual.measure` | `browser` | Numbers from the rendered page: gaps, edges, grid cells, overflow, clipped, edge and invisible text, framed media, template devices, shared components. No judgement |
| `visual.review` | `manual` | A judgement from screenshots and the measurements, against the project's own rules |

Keep measurement and judgement apart. A gap of 20px is a fact; whether it is wrong depends on the design record. Without a browser, record `visual.measure` and `visual.review` as `unavailable` with an issue ID (see `no-browser.md`); a source review can't stand in for either.

## What to judge against

Read the design record first: `layout_rules` (grid, rhythm, breakpoints, density) and the space tokens in `semantic_tokens`. Judge the page against those, never against a universal minimum gap or a house style. When the design record says nothing about a property, say so in the finding and judge only obvious breakage (overlap, clipping, an item outside its grid).

## Screenshot set

One page of each template type (home, a content page, a listing, a form, any page with its own layout), each at 320px, 768px and at least 1280px wide, full page, in the light scheme and, when the site has a dark theme, the dark one. Before each full-page shot, evaluate `scripts/visual-measure.js` and `await swRevealSweep()`: it scrolls down the page and back so scroll-triggered reveals and lazy images have loaded; without it they come out blank. Add the states the page contract names (open menu, error state) at the widths where they change the layout. Save them under `docs/website/evidence/visual/`, named by route, width and scheme. Say in `sample_scope` which pages and widths you covered; the rest is unverified.

Screenshots are large in context. Take the set as files, judge from the `visual.measure` numbers first, and open only the shots a finding needs, as viewport-sized crops rather than whole pages. For a full pass, hand the set to a reviewer agent when the session has one, so the images stay out of the main context; record its judgement as `visual.review` with the agent in `tool_and_version`. Delete superseded screenshots with `prune-evidence` once the gate passes.

## Measuring (`visual.measure`)

Run `scripts/visual-measure.js` in the rendered page with whatever browser tool the session already has: evaluate the file's contents, then call

```js
swVisualMeasure({scale: [0, 4, 8, 16, 24, 32, 48, 64], tolerance: 1, root: "main"})
```

with `scale` taken from the design record's space tokens in px. Run it after `swRevealSweep()` at each width and scheme in the screenshot set, and once more per template type under print emulation without the sweep (a printed page was never scrolled). Switch the scheme and print with the session browser's media emulation (for example Playwright `emulateMedia` or the DevTools emulate tool); when the tool can't emulate print, record the print pass as `unavailable` in `limitations`. Save the JSON next to the screenshots. Each result names the `media` it was measured in and whether it was `swept`. It reports:

- `gaps`: the vertical distance between consecutive stacked siblings, border box to border box. Container padding is never counted as a gap between items, and collapsed margins are measured as the reader sees them.
- `off_scale`: gaps that match no scale value within the tolerance.
- `heading_rhythm`: the space above and below each heading. `tighter_above: true` means the heading sits closer to the block before it than to its own content.
- `alignment`: per container, the left edges of its children grouped within the tolerance, and the children that line up with neither the container's content edge nor the most common edge.
- `tracking`: elements with their own text and a computed letter-spacing above 0.05em or below -0.03em, with tag, classes, font size, letter-spacing in em, text-transform, font-variant-caps and text length (at most 200; `tracking_more` counts the rest). It measures and doesn't judge. Use it to settle the role of selectors that `style.tracking` reported as `unclassified`: a long lower-case run in a `p` is running text, a short uppercase line is a label. Record the decision with the review.
- `grid_items`: per grid, the column tracks, the real children, any generated `::before`/`::after` box that takes a cell, the rows used, and how far the first child sits from the content edge.
- `overflow`: page-wide, how far the page scrolls sideways (`amount`, 0 when it fits) and up to 5 `culprits`, the deepest elements past the right edge that no ancestor clips.
- `clipped`: boxes with hidden or clipped overflow (or an ellipsis) that cut off part of their own text: axis, px hidden, `ellipsis`, `line_clamp` and the start of the cut text.
- `edge_text`: text closer to the left or right screen edge than `edge_margin` (12px below 600px wide, otherwise 16px).
- `invisible_text`: text inside `root` that is laid out but not drawn, with the `reason`: `opacity` (an ancestor at opacity 0), `visibility`, `clipped` (every line cut away by clipping boxes) or `offscreen` (moved off the page by a transform). Collapsed accordions, closed `<details>` and dialogs, `[hidden]`, `aria-hidden` and screen-reader-only helpers are not listed.
- `tells`: repeated template devices inside `root`: `eyebrows` (short uppercase labels at 15px or less, tracked 0.06em or more), `numbering` (01, 02, 03 as labels), `trailing_arrows` (link and button text ending in an arrow) and `card_kit` (one radius and shadow pair on many boxes), each with a count, samples and `repeated`.
- `components`: page-wide, the computed look of the shared parts: `header`, `nav`, `footer`, `buttons` grouped by style (most used first) and `cta_panels` (a heading and a button on their own background). Each carries its `style` and a `digest`; heights are reported but left out of the digest.
- `framed_media`: an image, video, canvas, svg or iframe that is the only content of a bordered, filled or shadowed frame, with the four insets and `unequal` when opposite insets differ by more than the tolerance.

Record it with method `browser`, one record per route with the page as target and `--inputs-from-page`, as for any `browser.*` check.

## Reviewing (`visual.review`)

Review each page and width with its measurements and the design record, opening the screenshot where a measurement or the design record calls for it, and check:

1. **Spacing rhythm.** Gaps come from the scale. Related items sit closer together than unrelated ones. A heading belongs to the content below it: if `tighter_above` is true, look for a later rule that reset its top margin (`layout.spacing-reset` points at it).
2. **Alignment.** Text, images and controls in a column share an edge. An outlier in `alignment` is a defect unless the design deliberately offsets it (a pull quote, a hanging number).
3. **Hierarchy.** The order of size, weight and space matches the page contract's order of importance. One clear primary action per view.
4. **Unintended grid items.** A generated box in `grid_items` that takes a cell is almost always a mistake: decoration meant to sit behind or above the grid. The fix is to position it, move it to a wrapper or give it `grid-column: 1 / -1`.
5. **Responsive composition.** At each width the layout still reads in order: no orphaned single item on a last row unless intended, no collapsed column that keeps desktop spacing, nothing clipped or overlapping.
6. **Breakage.** A sideways scroll (`overflow.amount` above 0), text cut off without an ellipsis or line clamp the design asks for (`clipped`), text inside `edge_margin` (`edge_text`) and a frame with `unequal` insets are defects, whatever the design record says, unless the design deliberately bleeds that element past the edge. Fix the culprit, not the symptom: constrain the wide element rather than hiding overflow on `body`.
7. **Hidden content.** Text in `invisible_text` after the sweep is content a visitor never sees: a reveal that never fires, a dark-theme rule that hides it, or a print stylesheet that leaves reveal start states at opacity 0. Each is a defect unless the design record says the element is decorative. Compare the light, dark and print results: text listed in one and not the others is the usual sign of a theme or print rule gone wrong.
8. **Template devices.** A device in `tells` marked `repeated` (and `content.tells` for copy) is a question, not a ban: keep it when the design direction names it, otherwise replace it with something the project's own rules call for. Swapping one symbol for another (an arrow for a chevron, 01 for I) is not a fix. When it stays without being named in the direction, record the reason in the review; for a helper warning the user decides with `accept-finding`.
9. **Consistency across page types.** Compare `components` between the template types in the sample. A header, nav or footer whose `digest` differs from one page type to another is a defect unless the design record gives that page its own variant. More than two or three button groups on a page, or a primary button that changes style between pages, usually means a component was restyled locally instead of through its tokens. CTA panels that repeat on every page with the same look are worth a sameness question (item 8).

Record each problem as a finding with the route, width, screenshot file, the measurement it rests on and the design rule it breaks. Record `visual.review` with method `manual`, the reviewer in `tool_and_version` (for example `manual: Claude from screenshots`), the screenshots and the measure output as `--input`, one `--judged ROUTE,WIDTH,THEME,SCREENSHOT` per screenshot judged (for example `--judged /,320,light,docs/website/evidence/visual/home-320-light.png`), and `sample_scope`. A screenshot that is judged but not an input is refused; one replaced after the review makes it stale, so a new screenshot needs a new look. It passes only when every page and width in the sample was reviewed and no finding is left open.
