# Reduced motion

`prefers-reduced-motion: reduce` is a request to remove motion that isn't essential. Treat it as a complete alternative design, not a partial switch.

## What changes

| Motion | With reduced motion |
|---|---|
| Movement, scaling, rotation, parallax | Removed; elements are in their final position |
| Pinned or sticky storytelling, scroll-linked effects | Removed; content becomes a normal readable flow |
| Auto-playing animation or video backgrounds | Paused, with a visible control to play |
| Short opacity or colour changes on controls | May stay, 150 ms or less |
| Smooth scrolling | Off (`scroll-behavior: auto`) |

Nothing important may appear only through animation. Content hidden before an entrance animation must be visible when the animation is off.

## CSS

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

The blanket rule is a safety net. Also write specific rules for each animated component (unpin the sticky visual, show all steps), because a zero-length animation can still leave elements in their start state.

## JavaScript

- Read the preference with `matchMedia("(prefers-reduced-motion: reduce)")` and listen for `change`, so switching it while the page is open takes effect without a reload.
- When it's on, don't start observers or animations for decorative motion at all; render the static version.
- `element.animate()` calls are not covered by the CSS rule. Check the preference before calling them.
- In a component framework, keep the preference in state (for example via `useSyncExternalStore` in React) and include it in the effect's dependencies.

## Checking it

- Static: `sw_site_check.py --checks motion.reduced` fails a page whose CSS or scripts animate without any `prefers-reduced-motion` handling. It can't tell whether the handling is complete.
- Browser: emulate reduced motion, reload and also switch it while open, then confirm the static version, no running animations (`document.getAnimations()`), no pinning and full content.
