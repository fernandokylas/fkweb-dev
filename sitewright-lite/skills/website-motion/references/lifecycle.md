# Motion lifecycle

Motion code leaks when it outlives its element: observers keep firing, listeners pile up after each route change, animations keep running on detached nodes. Every setup has a matching teardown.

## Checklist

| You started | You stop it with |
|---|---|
| `IntersectionObserver`, `ResizeObserver`, `MutationObserver` | `observer.disconnect()` |
| `addEventListener` | `removeEventListener` with the same function and options, or an `AbortController` signal passed to every listener and aborted once |
| `element.animate()` | `animation.cancel()` |
| `requestAnimationFrame` loop | `cancelAnimationFrame(id)` and a stop flag |
| `setTimeout`, `setInterval` | `clearTimeout`, `clearInterval` |
| `matchMedia(...).addEventListener("change", …)` | `removeEventListener` |
| A library timeline or scroll trigger | the library's kill or revert method, called for everything created in that scope |

## In component frameworks

- Create motion in an effect that runs after mount, never during render.
- Return a cleanup that undoes everything in the table. Frameworks may run setup twice in development (React StrictMode mounts, unmounts and mounts again); a correct cleanup makes that harmless.
- Put the reduced-motion preference and any other inputs in the effect's dependencies, so a change tears down and rebuilds the motion.
- Scope queries to the component's own root element, not `document`, so two instances don't fight.

## In plain scripts

- Initialise once per element; mark initialised elements (`data-motion-ready`) so a second script run doesn't double-bind.
- If the page swaps content without a reload (a client-side router, a partial update), expose an `init(root)` and `destroy(root)` pair and call both.

## How to test it

1. Count live observers or listeners. Best: measure from outside, so the production build is tested unchanged: before page scripts run, have the browser tool inject a script that wraps `IntersectionObserver` (and `addEventListener` where needed) and counts live instances. If the tool can't inject scripts, the component may expose a count (for example `document.documentElement.dataset.storyObservers`) in a fixture or behind a verification flag that the release check catches. If the count exists only in a development build, run the check there and say so in the record's limitations (React StrictMode mounts twice in development).
2. In a browser: mount, unmount and remount the component several times (route change, toggle, conditional render). The baseline is the count with the component unmounted (normally 0). After each unmount the count returns to it; while mounted it equals the number of observers the component owns and never grows across remounts.
3. Check `document.getAnimations()` after unmount: nothing should be running on removed elements.
4. Switch reduced motion while the page is open: the motion must tear down without a reload.
