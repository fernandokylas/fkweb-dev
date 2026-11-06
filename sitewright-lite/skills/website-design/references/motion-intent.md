# Motion intent

Motion is decided per interaction, by what it does for the visitor and how often they will see it. The design record's `motion_intent` lists where motion is used, the duration and easing tokens, and what happens under reduced motion.

## Decide by purpose and frequency

| Interaction | Typical frequency | Default decision |
|---|---|---|
| Filter, tab, toggle, sort, form input feedback | Many times a session | **Instant**, or a very short colour or opacity change (under about 150ms). The visitor wants the result, not a performance. |
| Menu open and close, accordion, dialog | Several times | Short and functional (about 150 to 250ms), showing where things came from and went |
| Page-level reveal, hero entrance | Once per visit | Optional. Only if it supports the direction, and never delaying content or the primary action |
| Scroll-driven narrative, pinned storytelling sequences | Explicitly requested | Planned as a feature with its own page contract states. Handled by `website-motion` at build time |

Instant feedback is a deliberate choice, not a missing feature. For something used many times a day (a timetable filter, a menu category switch), animation becomes friction.

## Reduced motion

Every motion entry states its reduced-motion behaviour: removed, replaced by an instant change, or reduced to a short fade. Content and controls must work identically with motion off. Nothing important may appear only through animation.

## What to avoid

- Animating every section on scroll by default.
- Motion that delays reading, input or the primary action.
- Parallax or large movement without a reduced-motion alternative.
- Motion libraries added to the build for effects CSS transitions handle. The baseline is CSS transitions and, where needed, the Web Animations API. An animation library is an explicit decision recorded with its reason, and never a requirement of the toolkit.

## Recording it

```
- motion_intent: filters and tabs switch instantly; menu and accordion open with
  --duration-fast (180ms) --ease-standard; no entrance or scroll animation;
  reduced motion removes the menu/accordion transitions.
```

If the brief asks for a scroll story or another expressive sequence, record the sequence, its trigger, its states and its reduced-motion fallback here, and note that `website-motion` implements it.
