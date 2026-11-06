# Animation libraries (optional)

Sitewright works without any animation library. CSS, the Web Animations API and `IntersectionObserver` cover state changes, entrances and scroll narratives. A library is an optional, per-project decision, never a toolkit requirement.

## When a library is justified

- Many elements on a shared timeline that must stay in sync, with scrubbing or reversal.
- Physics-based motion (springs with velocity carried between gestures).
- SVG path morphing, or text splitting with complex staggering.
- The project already uses a library: keep using it rather than adding a second.

"It's easier" or "it's smoother" alone isn't a reason. Measure first.

## If you add one

1. **Record the decision** in `accepted_decisions`: which library, which need it serves, and why the baseline wasn't enough.
2. **Check its licence** for this use, and record it. Some animation libraries have their own licence terms that differ from the licence of tutorials or skills written about them. If the terms are unclear for the project's use, don't add it; build with the baseline tools and log the open question.
3. **Install locally with an exact version** (`npm install --save-exact <package>@<version>`) and commit the lockfile. Never load it from a CDN without recording that dependency.
4. **Read the installed version's documentation**, not examples written for another version. APIs change between minor versions.
5. **Scope and clean up**: create everything inside a context or scope object tied to the component, and kill or revert it in the cleanup (see `lifecycle.md`). Use the library's media-query helper, or your own `matchMedia` check, so reduced motion builds no timeline at all.
6. **Lazy-load** the library when the animated section is near the viewport if it is large and only one section uses it.

## Verification is the same

A library doesn't change the checks: active state follows scroll, reduced motion gives the static version, no growth in live triggers after repeated mount and unmount, no horizontal scroll, no console errors.

Note on sources: Third-party GSAP skill text was reviewed but not adopted, because the GSAP library's own licence terms are not contained in that material and remain unresolved. This file is original guidance that applies to any library.
