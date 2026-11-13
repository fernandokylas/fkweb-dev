# Easing curves and component recipes

## Curves

Define once in `:root`, reference everywhere. Two or three curves per project — not one per component. There is exactly one `--ease-out` token in the project, and it is the value below (the same curve as Sitewright Full's motion-craft guide).

| Token | Value | Feel | Use for |
|---|---|---|---|
| `--ease-out` | `cubic-bezier(0.23, 1, 0.32, 1)` | Fast start, long soft landing | Hover-in, reveals, and every UI enter and exit |
| `--ease-out-quart` | `cubic-bezier(0.25, 1, 0.5, 1)` | Slightly less dramatic than expo | Hover-in on small elements (chips, list rows) |
| `--ease-in-out-quart` | `cubic-bezier(0.76, 0, 0.24, 1)` | Symmetric, weighty | Toggles, accordions, things that move A→B and back |
| `--ease-out-back` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Overshoots then settles | Pop-ins (badges, checkmarks), menus opening — use sparingly |
| `--ease-in-quart` | `cubic-bezier(0.5, 0, 0.75, 0)` | Slow start, fast exit | Only an element leaving the viewport over distance (an off-canvas panel or sheet sliding away), at most 200ms. UI exits otherwise use `--ease-out` |
| `--ease-spring` | `linear(0, 0.009, 0.035 2.1%, 0.141, 0.281 6.7%, 0.723 12.9%, 0.938 16.7%, 1.017, 1.077 20.4%, 1.121, 1.149 24.3%, 1.159, 1.163 27.8%, 1.154, 1.129 32.8%, 1.051 39.6%, 1.017 43.1%, 0.991, 0.977 51%, 0.974 53.8%, 0.975 57.1%, 0.997 69.8%, 1.003 76.9%, 1)` | Real spring | Drawers, sheets, drag release — modern browsers; falls back to `ease-out` |

Durations that feel right on a pointer device:

| Interaction | Duration |
|---|---|
| Hover in | 200–300ms |
| Hover out | 150–200ms (always ≤ hover-in) |
| Press (`:active`) | 60–100ms |
| Release | 200ms on the base rule handles it |
| Toggle / switch | 200–250ms |
| Menu / dropdown open | 180–240ms |
| Modal / sheet enter | 250–350ms; exit 150–200ms |
| Page-level reveal | 400–600ms, stagger children 30–50ms |

Anything over ~350ms for a direct response to a click starts to read as lag. Exits use `--ease-out` too, with a shorter duration.

## Recipes

All assume the tokens below are in `:root`:

```css
:root {
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
  --ease-in-out: cubic-bezier(0.76, 0, 0.24, 1);
  --dur-in: 260ms;
  --dur-out: 180ms;
  --dur-press: 80ms;
  --shadow-rest: 0 1px 2px rgb(0 0 0 / 0.04);
  --shadow-hover: 0 4px 12px rgb(0 0 0 / 0.08);
}
```

### Primary button
The hover shadow is a pseudo-element whose `opacity` fades, so no `box-shadow` value is ever transitioned (that repaints every frame).
```css
.btn {
  position: relative;
  transition: transform var(--dur-out) var(--ease-out),
              background-color 150ms linear;
  box-shadow: var(--shadow-rest);
}
.btn::after {                       /* the hover shadow, faded in with opacity */
  content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
  box-shadow: var(--shadow-hover);
  opacity: 0;
  transition: opacity var(--dur-out) var(--ease-out);
}
@media (hover: hover) and (pointer: fine) {
  .btn:hover {
    transform: translateY(-1px);
    transition-duration: var(--dur-in);
  }
  .btn:hover::after { opacity: 1; transition-duration: var(--dur-in); }
}
.btn:active {
  transform: translateY(0.5px) scale(0.97);
  transition-duration: var(--dur-press);
}
.btn:active::after { opacity: 0; transition-duration: var(--dur-press); }
.btn:focus-visible { outline: 2px solid var(--accent-text); outline-offset: 2px; }
```
Gate hover with `(hover: hover) and (pointer: fine)`, not `(hover: hover)` alone: some touch-first devices report hover support, and `:hover` then sticks after a tap.

For a handful of small controls (a few buttons on a page) a direct `box-shadow` transition is acceptable and shorter to write. Use the pseudo-element approach for cards, lists and anything repeated many times.

### Clickable card
Same as the button but lift `-2px`, hover shadow one step larger, press `scale(0.985)` — big surfaces need less compression to feel the same.

### List row / menu item
No lift (rows don't float); background tint only, `120–150ms linear`; `:active` `scale(0.995)` or none. Rows that scale on hover feel jittery in a list.

### Toggle / switch
The knob: `transform var(--dur-in) var(--ease-in-out)`. The track colour: `150ms linear`. Add `scale(0.9)` on the knob during `:active` for a "grabbed" feel.

### Dropdown / popover
```css
.menu { transform-origin: top; opacity: 0; transform: translateY(-4px) scale(0.98);
        transition: opacity 150ms linear, transform 220ms var(--ease-out); }
.menu[data-open] { opacity: 1; transform: none; }
```
Exit: keep `--ease-out` and shorten to 140ms. An accelerate curve is only for an element that leaves the viewport over distance.

### Modal / sheet
Backdrop `opacity 200ms linear`; panel `transform 300ms var(--ease-out)` from `translateY(12px) scale(0.98)` (modal) or `translateY(100%)` (sheet). Exit at 180ms, still `--ease-out` (a sheet that slides fully off screen may use `--ease-in-quart`, at most 200ms).

### Staggered reveal
```css
.reveal > * { opacity: 0; transform: translateY(8px);
              transition: opacity 400ms linear, transform 500ms var(--ease-out); }
.reveal.is-in > * { opacity: 1; transform: none; }
.reveal > :nth-child(2) { transition-delay: 40ms; }
.reveal > :nth-child(3) { transition-delay: 80ms; }
```

## Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    /* Only non-spatial properties may animate: the hover tint and shadow fade survive, the lift doesn't */
    transition-property: opacity, color, background-color, border-color, box-shadow, fill, stroke !important;
    transition-duration: 150ms !important;
    animation: none !important;
  }
}
```
Keep the *state* change (colour, shadow) — only the motion collapses. Don't remove hover feedback entirely. (Same block as `reduced-motion-enforcer`; the `!important` here is deliberate — it must beat every layer.)
