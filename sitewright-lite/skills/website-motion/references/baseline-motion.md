# Baseline motion

Defaults for motion built with CSS and the Web Animations API. The selected design system's tokens override every value here.

## Purpose first

Each animation has one job you can name: showing where something came from, confirming an action, keeping orientation during a change, or telling a planned story. If you can't name it, remove it. How often the visitor sees it decides how much is acceptable: controls used many times a session change instantly or with a very short fade; a once-per-visit sequence can take longer.

## Duration and easing defaults

| Kind | Duration | Easing |
|---|---|---|
| Colour, opacity feedback on controls | 100–150ms | `ease-out` or linear |
| Small element entering or leaving (menu, tooltip, accordion) | 150–250ms | `ease-out` on enter, slightly faster on exit |
| Larger panel, dialog, step change in a story | 250–400ms | a decelerating curve, e.g. `cubic-bezier(0.2, 0, 0, 1)` |
| Anything over 500ms | only for planned narrative moments, never on controls | |

Use the design record's duration and easing tokens (`--duration-short`, `--ease-standard` and so on) rather than literal values in components.

## What to animate

- Prefer `transform` and `opacity`; they don't trigger layout. Animate `width`, `height`, `top` or `left` only when there's no alternative, and on small elements.
- Entrances that grow begin close to full size (around 0.95) and fade in alongside; growing from nothing looks like a glitch rather than an arrival.
- Avoid animating large blurred or shadowed areas and huge images; they're expensive to paint.
- `will-change` only on elements that are about to animate, removed afterwards.

## Interruption

People click again, scroll back, or change their mind. Motion must cope:

- CSS transitions retarget smoothly from the current value; prefer them for toggles.
- With WAAPI, keep a reference to the running animation and `cancel()` or `reverse()` it before starting a new one on the same element.
- Never block input while an animation runs; the end state must be reachable immediately.
- Don't chain animations with timers that keep running after the element is gone.

## Release blockers

- Motion with no reduced-motion handling.
- Content that appears only through an animation, so it's missing if the animation fails or is disabled.
- Scroll hijacking, scroll-speed changes or forced snapping on reading content.
- Flashing more than three times a second.
- Autoplaying motion longer than five seconds without a pause control.
