# Design self-review

Run this review before the design record goes to a build skill, and again on the built pages during verify. It's a self-check. It doesn't replace human review, and passing it isn't approval.

## Objective findings (fix now)

These can be checked and are not matters of taste:

- every text and focus pair meets its contrast threshold (`tokens.md`);
- every interactive component has focus-visible, hover, active and disabled states, and every form has error and success states;
- the type scale has a readable body size (around 16px or more on small screens) and a sensible measure;
- the primary action is visible without scrolling on small screens, on the pages where it matters;
- nothing depends on hover alone, colour alone or motion alone to carry meaning;
- motion has a reduced-motion behaviour;
- every font and asset has a recorded source and permitted use.

Record any remaining objective failure as a defect in `open_issues`, with its evidence.

## Generic defaults (question them)

AI-generated sites drift towards the same look. For each item below, ask whether the brief chose it or it just appeared:

- a centred hero with a gradient blob, a big headline, two buttons and a stock illustration;
- three identical feature cards with icons;
- purple-to-blue gradients, glassmorphism, neon glows on a dark background;
- an "as seen in" logo band or a testimonial carousel with no supplied testimonials;
- random section animations that fade up on scroll;
- interchangeable sans-serif type everywhere, with no relation to the subject.

None of these is banned. A brand guide may ask for any of them, and then the brand wins. But each needs a reason in the direction. If you can't give one, replace it with something grounded in the subject.

## Copy that does a job

- A button or link label names its outcome ("Call 555-0142", "Book a table", "Send enquiry"); a vague label such as "Learn more" is only acceptable when nothing more precise is true.
- Each form error sits beside its field and gives the problem and the repair in everyday language.
- Empty and success states tell the visitor what to do next.
- Headings describe the content below them. Clever headings are fine when the content beneath stays clear.
- No invented facts slip in through copy: no years, numbers, guarantees or quotes that the brief does not support.

## Critique rounds on built pages

During verify, judge the built pages in rounds, from screenshots taken after the reveal sweep (`../../website-verify/references/visual-review.md`):

1. **Start from fresh screenshots** of the current build. A round never judges from memory or from the previous round's shots; its findings belong to the screenshots it looked at.
2. **Write the round down** in the same shape every time, so one round can be set beside the next:

   ```
   Round 2 (screenshots: home-1280-light.png, home-320-light.png, article-1280-light.png)
   At a glance: the timetable, then the photo of the harbour
   Idea in one sentence: a ferry company that reads like its own printed timetable
   Layout words: home = statement / split / grid / split / form; article = text / figure / list
   The three problems a visitor would see first, each with screenshot, measurement and fix:
   1. ...
   ```

3. **Fix the top three**, take new screenshots and start the next round. Work in this order, because a later fix can't rescue an earlier problem: the idea, hierarchy, composition (edges, spacing, layout variety, empty holes), type, imagery, colour, detail and states, motion.
4. **Stop** when a round finds nothing a first-time visitor would notice, and after the third round at the latest. Problems that remain go into `open_issues` as they are, without softening. A critique is closed only by a fresh round that finds its top problems gone.

**Sameness pass.** In every round, compare the layout words: the same word in adjacent sections, or three times on a page, is the template showing. Then compare page types with `visual.measure` (`components`, `tells`): a header that changes between pages, or the same CTA band on every page, is a finding.

**Removing is not finishing.** When a generic device goes, the page must not become thin: tighten the spacing around it, give the remaining elements more room, or let real content fill it; don't refill it with ornament. A richer page with a few template devices still reads better than an empty one.

Helper warnings that the review keeps (a named device, a deliberate exception) follow the triage rule in `website-verify`: fix real problems; a sanctioned exception gets the narrowest `accept-finding`, decided by the user.

## Taste (record, don't block)

Subjective judgements, such as "the accent might be too loud" or "a serif heading could suit the bakery", are suggestions. Record them as `advice` in `open_issues` or in the handoff. Don't present them as defects, and don't claim the chosen direction is better than alternatives without human review.
