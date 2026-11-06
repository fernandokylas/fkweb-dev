# Harbour Lane story fixture [fixture]

React 19 + TypeScript + Vite fixture for the `website-build-code` React path and the `website-motion`
scroll narrative (scenario V12). Fictional content; not a template.

- Versions are pinned exactly in `package.json`. `node_modules/` and `dist/` are never committed.
- Build in a scratch copy: `npm ci && npm run build` (or `npm install` the first time to write the lock file).
- Motion: IntersectionObserver marks the step being read; the illustration crossfades with the Web
  Animations API. Reduced motion (or no IntersectionObserver) shows every step in full, unpins the
  illustration and removes all transitions. Observers and animations are cleaned up on unmount;
  `<html data-story-observers>` counts live observers so a browser check can confirm it returns to 0.
