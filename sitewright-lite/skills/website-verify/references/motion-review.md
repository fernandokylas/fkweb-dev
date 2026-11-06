# Motion review

Reviewing a site's motion has three modes. Pick the one the request needs; don't run all three by default.

| Mode | When | Output |
|---|---|---|
| **Critique** | One animation or component, often while it's being built | Short notes on purpose, timing, easing and interruption, each with a concrete change. Often used by `website-motion` while building |
| **Audit** | Before hand-over, or when asked to check all motion | Every animated element listed with its purpose, trigger, frequency, duration, reduced-motion behaviour and lifecycle; each problem recorded as a finding |
| **Opportunities** | The user asks where motion could help | A short list of places where motion would clarify a change of state, each tied to a purpose. Listed as suggestions in the verification report; `website-design` decides whether to plan any of them |

## What an audit checks

For each animated element:

1. **Purpose**: can it be named (orientation, feedback, continuity, planned story)? If not, it's a removal candidate.
2. **Frequency**: something seen many times per visit should be short or instant.
3. **Timing and easing**: within the design record's tokens, or `baseline-motion.md` defaults if the record has none.
4. **Interruption**: clicking again or scrolling back mid-animation behaves sensibly.
5. **Reduced motion**: the static alternative exists and is complete (browser check `browser.reduced-motion`).
6. **Lifecycle**: observers, listeners and animations are cleaned up (browser check `browser.lifecycle`).
7. **Performance**: animates `transform` and `opacity`; no long tasks or layout thrashing during scroll, where a profiler is available.
8. **Safety**: nothing flashes more than three times a second; long autoplay has a pause control.

The motion skill's references (`../../website-motion/references/baseline-motion.md`, `lifecycle.md`, `reduced-motion.md`) hold the rules these checks apply.

## Removing motion

Removing an animation is a code change, not a search-and-replace. Before taking one out, check for:

- **A start state left behind.** An element that begins at `opacity: 0`, off-screen or scaled down and waits for the animation or an observer to show it stays hidden once the animation is gone. Remove the start state together with the animation; check print and reduced motion too, where the animation may never run.
- **Code waiting for the end.** `animationend` or `transitionend` listeners, exit callbacks and timers sized to a duration. Delete or move the work they did; otherwise the page still stalls for an animation that has gone.
- **Unmounting held back by an exit.** When an exit animation kept an element in the page until it finished, its removal now happens at once; whatever ran after the exit (focus, clean-up) runs at the close instead.
- **A jump the motion was hiding.** A layout or FLIP animation can mask a layout shift. If the shift appears when the motion goes, keep the motion for now and record the shift as a finding.
- **Focus moved in a callback.** Focus that moved after the animation must move straight away.
- **Tests and selectors** tied to an animation's class names or timings.

Afterwards, grep for the animation's names and classes to confirm nothing still refers to them.

## Recording

Audit findings are `manual` records, or `browser` records when observed in a browser, with the element and the measured values. Each performance finding says how it was established: "from code" (a property that triggers layout, for example) or "needs a device recording" (dropped frames, long tasks). Desktop CPU throttling doesn't stand in for a mid-range phone. A motion audit done from source alone says so in its limitations.
