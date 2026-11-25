<!-- Generated from content/checklists/features.json by tools/build_checklists.py. Do not edit. -->

Checklist text © 2026 Fernando Kylas (fkweb-dev), licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

# Features page

How to present what a product or service does so readers understand the value and can trust the claims.

Use when: A features, services overview or "what you get" page or section.

Updated 2026-11-25. 12 items, checked by hand. Record each as passed, failed, skipped (with the reason) or unavailable (with what would settle it). No score.

## features-01 · warning

Each feature is described by what the reader can do or get, with its name second.

- Check: Read each feature heading and the first line under it.
- Pass: The outcome comes first ("Send invoices in two clicks"), not just a label ("Smart invoicing").
- Sources: [Nielsen Norman Group: 10 usability heuristics for user interface design](https://www.nngroup.com/articles/ten-usability-heuristics/)

## features-02 · info

Features are in order of importance to the audience.

- Check: Compare the order with what the brief or customers say matters most.
- Pass: The most important features come first.
- Sources: [Google Search Central: creating helpful, reliable, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)

## features-03 · critical

Every claim is specific and supported.

- Check: List claims such as numbers, "fastest" or "best", and ask for their source.
- Pass: Each claim has a supplied source or is reworded into a checkable fact. Superlatives without proof are removed.
- Sources: [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html); fkweb-dev house rule: no invented proof (claims, quotes, ratings and numbers need a supplied, checkable source)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## features-04 · warning

Limits and requirements are stated: what each plan includes, supported platforms, what is not included.

- Check: Look for the conditions a buyer needs before deciding.
- Pass: Material limits are on the page or one clear link away.
- Sources: [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html)

## features-05 · warning

The product or service is shown with real screenshots, photos or demos, not generic illustrations.

- Check: Look at the images.
- Pass: Images show the actual product or work, with captions where needed.
- Sources: [Nielsen Norman Group: 10 usability heuristics for user interface design](https://www.nngroup.com/articles/ten-usability-heuristics/)

## features-06 · warning

Meaningful images and icons have text alternatives. Decorative ones are hidden from screen readers.

- Check: Run the accessibility checks and inspect the alt text.
- Pass: Alt text describes the information in each meaningful image. Decorative icons have empty alt or aria-hidden.
- Sources: [WCAG 2.2, 1.1.1 Non-text Content](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## features-07 · warning

The layout avoids the generic AI look: not a grid of identical icon cards with vague three-word headings.

- Check: Look at the section as a whole, and run the tells and visual review checks.
- Pass: Features vary in emphasis according to their importance, and the copy is specific.
- Sources: fkweb-dev house rule: no generic AI-look tells (stock phrases, identical icon cards, vague adjectives)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## features-08 · info

Plain language: jargon is avoided or explained.

- Check: Read it as a newcomer to the field.
- Pass: Every technical term is explained or replaced.
- Sources: [GOV.UK: content design, planning, writing and managing content](https://www.gov.uk/guidance/content-design/writing-for-gov-uk)

## features-09 · warning

A comparison table, if present, is real table markup with headers, and its facts about others are current and dated.

- Check: Inspect the table and check the comparison facts.
- Pass: A table element with th headers. Competitor facts are sourced and carry a check date, or the comparison is removed.
- Sources: [WCAG 2.2, 1.3.1 Info and Relationships](https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships); [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html)

## features-10 · info

One primary action follows the features and is repeated where the reader is ready.

- Check: Find the calls to action.
- Pass: One main action (try, book or buy), the same wherever it appears.
- Sources: fkweb-dev house rule: one primary action per page, repeated where the reader is ready
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## features-11 · warning

Feature grids reflow at 320 px without sideways scrolling.

- Check: Run the reflow check.
- Pass: No horizontal scroll and no clipped text at 320 CSS px.
- Sources: [WCAG 2.2, 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## features-12 · info

Separate feature pages, if any, each have unique, useful content, not near-copies with a swapped keyword.

- Check: Compare the feature pages with each other.
- Pass: Each page has its own substance.
- Sources: [Google Search Central: spam policies](https://developers.google.com/search/docs/essentials/spam-policies)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.
