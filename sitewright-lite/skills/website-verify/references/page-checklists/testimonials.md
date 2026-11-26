<!-- Generated from content/checklists/testimonials.json by tools/build_checklists.py. Do not edit. -->

Checklist text © 2026 Fernando Kylas (fkweb-dev), licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

# Testimonials and reviews

How to show customer quotes and ratings honestly and accessibly.

Use when: Any page or section that shows testimonials, quotes, ratings or review widgets.

Updated 2026-11-25. 12 items, checked by hand. Record each item on its own row as passed, failed, skipped (with the reason) or unavailable (with what would settle it), and no other word. No score. An item whose heading ends "Pro checks this automatically" keeps that note on its own row; the other items do not get it.

## testimonials-01 · critical · Pro checks this automatically

Every testimonial comes from a real customer who agreed to it being published, and the record is kept.

- Check: Ask for the source and the permission of each testimonial.
- Pass: Each one is traceable to a person and a written permission. Anything else is removed.
- Sources: [FTC: Endorsement Guides, what people are asking](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking); [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html); fkweb-dev house rule: no invented proof (claims, quotes, ratings and numbers need a supplied, checkable source)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## testimonials-02 · critical

Quotes are not edited in a way that changes their meaning.

- Check: Compare each quote with the original.
- Pass: Shortened quotes keep the original sense.
- Sources: [FTC: Endorsement Guides, what people are asking](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking); [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html)

## testimonials-03 · critical

Any connection between the reviewer and the business is disclosed: staff, family, paid or gifted reviewers.

- Check: Ask about each reviewer's relationship with the business.
- Pass: Each connection is stated next to the quote.
- Sources: [FTC: Endorsement Guides, what people are asking](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking)

## testimonials-04 · warning

Each testimonial is attributed with a name, role and company or location. A photo is used only with consent.

- Check: Read the attributions.
- Pass: A name (or initials with a reason) plus role and company or location. Photos have consent on record.
- Sources: [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html)

## testimonials-05 · warning

Ratings and selections give a fair picture: a shown average covers all reviews, and the selection does not mislead.

- Check: Compare the shown rating with the source platform.
- Pass: The average and count match the source. The selection is not used to suggest a rating the business does not have.
- Sources: [FTC: Endorsement Guides, what people are asking](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking); [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html)

## testimonials-06 · info

Reviews from third-party platforms link to their source so they can be checked.

- Check: Look for links next to imported reviews.
- Pass: Each imported review or rating links to the platform page.
- Sources: [FTC: Endorsement Guides, what people are asking](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking)

## testimonials-07 · warning · Pro checks this automatically

There is no review or rating structured data for the business's own reviews of itself, and no marked-up rating that is not visible.

- Check: Run the JSON-LD check.
- Pass: No self-serving review markup on LocalBusiness or Organization, and no invented ratings.
- Sources: [Google Search Central: review snippet structured data](https://developers.google.com/search/docs/appearance/structured-data/review-snippet)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## testimonials-08 · info

Testimonials are specific: they name the problem and the result.

- Check: Read each one.
- Pass: Each says what changed for the customer, not only "Great service!".
- Sources: fkweb-dev house rule: no invented proof (claims, quotes, ratings and numbers need a supplied, checkable source)

## testimonials-09 · info

Testimonials sit next to the decision they support, such as pricing or sign-up, not only on a separate page.

- Check: Look where the quotes appear.
- Pass: At least one relevant quote sits near the main action.
- Sources: fkweb-dev house rule: one primary action per page, repeated where the reader is ready

## testimonials-10 · warning · Pro checks this automatically

A rotating carousel can be paused and does not move on its own faster than people read. Every quote is reachable by keyboard.

- Check: Watch the carousel, use its controls, and tab through it.
- Pass: Auto-rotation lasting over 5 seconds has a pause control (or there is none), and every slide is reachable and readable by keyboard.
- Sources: [WCAG 2.2, 2.2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide); [WCAG 2.2, 2.1.1 Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## testimonials-11 · info

Quotes are marked up as quotations with their attribution.

- Check: Inspect the markup.
- Pass: A blockquote or figure, with the attribution in a figcaption or clearly tied to the quote.
- Sources: [WCAG 2.2, 1.3.1 Info and Relationships](https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships)

## testimonials-12 · info

Old testimonials that no longer reflect the business are removed, or dated.

- Check: Check the dates and what each quote promises.
- Pass: Each quote is current, or carries a date.
- Sources: [FTC: Endorsement Guides, what people are asking](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking)
