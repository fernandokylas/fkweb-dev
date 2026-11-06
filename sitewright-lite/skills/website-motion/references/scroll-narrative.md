# Scroll narrative

A section where a visual changes as the reader scrolls through a series of steps. Built so that it reads well with no motion, no JavaScript and no visual.

## Structure

```html
<section class="story" aria-labelledby="story-title">
  <h2 id="story-title">How our bread is made</h2>
  <div class="story__visual" aria-hidden="true">
    <figure class="story__figure" data-stage="feed"><!-- decorative visual --></figure>
  </div>
  <ol class="story__steps">
    <li data-step="0"><h3>Feed the starter</h3><p>…</p></li>
    <li data-step="1"><h3>Mix and rest</h3><p>…</p></li>
  </ol>
</section>
```

- The steps are the content: an ordered list with headings, in source order.
- The visual is decorative (`aria-hidden="true"`) or repeats what the steps say. If it carries information the steps don't, give it a text alternative instead.
- On wide screens the visual can be `position: sticky` beside the steps; on narrow screens it sits above the steps or is hidden.

## Tracking the active step

Use one `IntersectionObserver` for all steps, with a root margin that narrows the viewport to a band across the middle (for example `rootMargin: "-45% 0px -45% 0px"`). When a step enters the band, it becomes active:

- set `aria-current="step"` on it and remove it from the others;
- set the visual's state (`data-stage`), and let CSS or a short WAAPI animation do the change;
- keep inactive steps readable; reduced emphasis (lower opacity) is fine, hidden is not.

Don't use a scroll listener to compute positions every frame when an observer will do. If progress must follow scroll continuously, use CSS scroll-driven animations with a fallback, or one passive listener that reads layout once per animation frame.

## Behaviour rules

- Never take over scrolling: no scroll-jacking, smooth-scroll overrides, forced snapping or changes to scroll speed.
- Keyboard and screen-reader users reach every step in order; nothing depends on scroll position to become focusable.
- A long narrative gets a toggle ("Read as a list") that switches to the plain version and unmounts the scroll machinery. Use a real button with `aria-pressed`.
- Without JavaScript the list renders in full (for static sites); in client-rendered apps the `<noscript>` message offers an alternative.

## Reduced motion

With `prefers-reduced-motion: reduce`: no sticky positioning, no observer, every step at full opacity, the visual in its final or a neutral state. Switch live when the preference changes. See `reduced-motion.md`.

## What to verify in a browser

| Check | Expected |
|---|---|
| Scroll each step to the centre | `aria-current="step"` and the visual stage follow in order |
| Reduced motion, switched while open | static version; observer count 0; no running animations |
| Unmount and remount several times (toggle, route change) | count returns to the unmounted baseline (0) after each unmount, and is the same each time it is mounted (1 here); no growth |
| 320px width, both modes | no horizontal scroll |
| Console | no errors |

The lifecycle check needs a count of live observers; `lifecycle.md` gives the ways to get one without changing production behaviour.
