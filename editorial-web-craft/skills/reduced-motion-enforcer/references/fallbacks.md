# Motion → reduced-motion fallback map

What to keep, what to strip. The principle: remove *displacement* (things travelling across the eye), keep *state change* (the user still needs to know something happened).

| Motion | Vestibular risk | Reduced-motion version |
|---|---|---|
| Entrance slide/scale (`y: 30`, `scale(0.95)` → rest) | Low–medium | Opacity-only fade, ≤200ms, zero displacement |
| Hover lift (`translateY(-4px) scale(1.02)`) | Low | No transform; keep the shadow/colour/border change |
| Press compression (`scale(0.97)`) | Low | No transform; keep background/shadow change or none |
| Staggered cascade | Low–medium | Fade all at once (drop the stagger), or show the end state with no transition |
| Parallax (`background-attachment: fixed`, scroll-speed layers) | **High** | `background-attachment: scroll`; all layers move together (i.e. not at all relative to content) |
| Scroll-driven / scrubbed animation | **High** | Show final state; no scrub |
| Smooth scroll (`scroll-behavior: smooth`, `scrollIntoView({behavior:'smooth'})`) | Medium–high | `auto` / instant jump |
| Zoom / scale transitions (page, image, modal grow-from-point) | **High** | Cross-fade in place |
| 3D flips, rotations, perspective | **High** | Cross-fade between faces |
| Infinite spinners / pulsing | Medium | Static indicator, or a slow ≤1/s opacity pulse; never rotation |
| Marquee / auto-scrolling carousel | **High** | Stop; show static slide with manual controls |
| Autoplay background video | **High** | `video.pause()` and show poster, or `autoplay` removed when the query matches |
| Sticky/fixed elements shifting on scroll (shrinking headers) | Medium | Fix them at one size |
| Skeleton shimmer | Low–medium | Static skeleton, no sweep |
| Toast/notification slide-in | Low | Fade in place |
| Modal / drawer slide | Medium | Fade; drawer appears in final position |
| Page transitions (view transitions, route slides) | Medium–high | Cross-fade, or none |
| Cursor followers, magnetic buttons | Medium | Off |
| Number count-ups | Low | Show final value |

## Duration guidance under reduce

- Opacity fades: 100–200ms are fine and help orientation. Do not collapse them to a near-zero duration (for example `0.01ms`): that also removes the fades that are allowed to stay, and it is not the recommended safety net.
- Anything with displacement: 0. Not "smaller", zero.
- Colour / shadow / border changes: unchanged — they aren't motion.

## How to get there

1. **Default: author the motion inside `@media (prefers-reduced-motion: no-preference)`.** Then the reduced case is simply no motion and nothing has to be undone.
2. **Safety net: the whitelist form** (`SKILL.md`, section 1): under `reduce`, only `opacity`, colour, border, fill and stroke may transition, at about 150ms, and keyframe animation is switched off. Use this for anything a component forgot, not as a replacement for step 1.
3. **End states:** because the net switches animations off, every element that is hidden before an animation (`opacity: 0`, a `from` keyframe, a skeleton delay, a `data-reveal` start) needs an explicit end state under `reduce` (`opacity: 1; transform: none`), or it stays invisible.

## Not vestibular triggers (don't strip these)

Colour changes, opacity changes, shadow changes, border changes, focus rings, underline reveals, small icon swaps. Removing these under `reduce` makes the UI *less* accessible, not more.
