# Responsive layout and input

## Layout

- Write mobile-first CSS with the breakpoints from the design record's `layout_rules`. Add a breakpoint where the content breaks, not at device widths.
- No horizontal scroll at 320px CSS width. Long words, URLs and email addresses need `overflow-wrap: anywhere` or a layout that allows them to wrap.
- Text reflows at 400% zoom without overlapping or clipping; avoid fixed heights on anything that holds text.
- Keep the reading measure from the design record (around 60–75 characters for body text).
- Images and embeds get `width` and `height` (or `aspect-ratio`) so space is reserved before they load; use `srcset`/`sizes` for large raster images.

## Touch and pointer are capabilities, not widths

- Use `@media (hover: hover) and (pointer: fine)` for hover-only effects. A narrow window on a laptop still has a mouse; a large tablet still has touch.
- Nothing important lives only on hover: menus, tooltips with essential text and card actions need a tap or focus path too.
- Touch targets are at least 24×24 CSS pixels with spacing (44×44 for primary actions is a safer default).
- Keep pinch-zoom available: no `user-scalable=no` and no `maximum-scale=1` in the viewport tag.
- Inputs use a font size of at least 16px so mobile browsers don't zoom on focus.
- Respect safe areas on full-bleed fixed elements (`env(safe-area-inset-*)`) and use dynamic viewport units (`dvh`) for full-height sections, so browser toolbars don't hide content.

## Navigation at small widths

- If the navigation collapses into a menu button, the button is a real `<button>` with `aria-expanded` and `aria-controls`, the menu is reachable by keyboard, Escape closes it and focus returns to the button.
- With four or five short items, a wrapping inline navigation is often better than a menu button. Choose by content, and record it in the design record.

## Worst-case content

Test layouts with the longest plausible content the site will receive: a long business name, a translated label that is 40% longer, a missing image, a list with one item and with fifty. Put such data through the real content source (the content file, the API fixture), not by editing the component. `website-verify` has the stress-case checklist.
