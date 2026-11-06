---
name: website-motion
description: Implements planned website motion beyond simple state transitions, such as scroll-driven narratives, pinned storytelling sections, sequenced reveals and animated page sections, fade-in or parallax on scroll, using the cheapest tool that works (CSS, the Web Animations API, IntersectionObserver), with cleanup on unmount and a full reduced-motion alternative. Use it when the design record's motion_intent plans such a sequence, when the user asks for a scroll story or animated section on a website, considers an animation library such as GSAP, Framer Motion or Lottie, or reports an animation leak or janky scroll effect, or when a build skill (custom-code or WordPress) hands motion work here. Not for deciding whether a site should have motion (that is website-design), and not for video, slides or app animation outside a website.
---

# Website motion

Implements motion the design record has already planned. The decision whether to animate, and how much, belongs to the design phase (`motion_intent`). If the request adds motion the record doesn't plan, hand it to `website-design` to record as a decision (purpose and reduced-motion behaviour) before building it.

Read the design record's `motion_intent`, duration and easing tokens, and the page contract for the section. Then pick the tool.

## 1. Choose the cheapest tool that works

| Need | Tool |
|---|---|
| State change (open, select, hover, focus); owned by the build skill, listed for comparison | CSS transition on `opacity`, `transform` or colour |
| A one-off sequence, or one that must be cancelled or reversed mid-way | Web Animations API (`element.animate`) |
| Something happens when a section enters or crosses the viewport | `IntersectionObserver` setting a state, with CSS or WAAPI doing the animation |
| Progress tied continuously to scroll position | CSS scroll-driven animations where supported, with a static fallback; otherwise a single passive scroll listener throttled to animation frames |
| Complex timelines across many elements, physics, SVG morphing | An animation library, only as a recorded decision; read `references/libraries.md` |

Read `references/baseline-motion.md` for durations, easing, properties to animate and interruption.

## 2. Build scroll narratives as content first

Read `references/scroll-narrative.md`. The story is an ordered list of real content steps that reads correctly with no motion and no JavaScript; the visual follows the active step, and scrolling is never hijacked or slowed.

On the WordPress path the same rules apply: the motion lives in the theme's or block's enqueued script and style, placed where `website-build-wordpress` decides, and editors can still change the step content.

## 3. Lifecycle

Every observer, listener, animation and timer you start, you also stop. In component frameworks, set them up in an effect and return a cleanup that disconnects observers, removes listeners and cancels animations. Run the setup again when the reduced-motion preference changes while the page is open. Read `references/lifecycle.md` for the checklist and the test.

## 4. Reduced motion is a full alternative

Read `references/reduced-motion.md`. `prefers-reduced-motion: reduce` turns off movement, parallax, pinning and scroll-linked effects; short opacity changes may stay. The content and controls must be identical with motion on and off, and the preference is read live, not once at load.

## 5. Check it

- Run the static site check; `motion.reduced` fails any page that animates without a reduced-motion rule:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_site_check.py" <built-site> --checks motion.reduced
  ```

- Hand over to `website-verify` for the browser checks: the active step changes on scroll, reduced motion gives the static version, the observer count returns to its unmounted baseline, no horizontal scroll at 320px, and no console errors. If no browser is available, say so; the lifecycle and scroll behaviour are then unverified, not passed.

While building, the critique mode of the motion review in `website-verify` is a quick way to check one animation's purpose, timing and interruption.

Record the tool chosen, its reason and any added package in `state.json` `accepted_decisions`.
