<!-- Generated from content/checklists/faq.json by tools/build_checklists.py. Do not edit. -->

Checklist text © 2026 Fernando Kylas (fkweb-dev), licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

# FAQ page

How to make a frequently asked questions page that answers real questions and that people, search engines and AI answer engines can read.

Use when: A page or section that lists questions with answers.

Updated 2026-11-25. 13 items, checked by hand. Record each item on its own row as passed, failed, skipped (with the reason) or unavailable (with what would settle it), and no other word. No score. An item whose heading ends "Pro checks this automatically" keeps that note on its own row; the other items do not get it.

## faq-01 · warning

The questions come from real customer contact (support messages, sales calls, search queries), not invented to fill space.

- Check: Ask where each question came from.
- Pass: Each question can be traced to a real source.
- Sources: [Google Search Central: creating helpful, reliable, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content); fkweb-dev house rule: no invented proof (claims, quotes, ratings and numbers need a supplied, checkable source)

## faq-02 · info

Each question is worded the way customers ask it.

- Check: Compare the wording with the source messages or queries.
- Pass: Questions use the customers' words, not internal or marketing terms.
- Sources: [GOV.UK: content design, planning, writing and managing content](https://www.gov.uk/guidance/content-design/writing-for-gov-uk)

## faq-03 · warning

Each answer opens with the direct answer in its first sentence.

- Check: Read the first sentence of every answer.
- Pass: The first sentence answers the question (yes, no, a number, a step); the detail follows.
- Sources: [GOV.UK: content design, planning, writing and managing content](https://www.gov.uk/guidance/content-design/writing-for-gov-uk)

## faq-04 · info · Pro checks this automatically

Answers are short and link to the full page for detail instead of copying it.

- Check: Look for long answers and for text repeated from other pages.
- Pass: No answer repeats a whole section of another page; it links to it.
- Sources: [GOV.UK: content design, planning, writing and managing content](https://www.gov.uk/guidance/content-design/writing-for-gov-uk)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## faq-05 · warning

Questions about cost, timing, cancellation and limits get honest, specific answers.

- Check: Read the answers to money and commitment questions.
- Pass: Each gives a figure, a period or a clear rule, or says plainly where to find it. No dodging and no self-praise questions ("Why are you the best?").
- Sources: [ASA CAP Code, section 3: misleading advertising (substantiation, testimonials, comparisons)](https://www.asa.org.uk/type/non_broadcast/code_section/03.html); fkweb-dev house rule: no invented proof (claims, quotes, ratings and numbers need a supplied, checkable source)

## faq-06 · info

More than about ten questions are grouped under topic headings with jump links.

- Check: Count the questions and look for groups.
- Pass: Ten or fewer questions, or topic groups with links to each group.
- Sources: [Nielsen Norman Group: accordions on desktop](https://www.nngroup.com/articles/accordions-on-desktop/)

## faq-07 · warning · Pro checks this automatically

Collapsible answers work by keyboard and announce whether they are open.

- Check: Tab to each question and open it with Enter or Space. Inspect the markup.
- Pass: Native details and summary elements, or buttons with aria-expanded that change state. Every answer opens by keyboard.
- Sources: [WCAG 2.2, 4.1.2 Name, Role, Value](https://www.w3.org/WAI/WCAG22/Understanding/name-role-value); [WCAG 2.2, 2.1.1 Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard); [GOV.UK Design System: details](https://design-system.service.gov.uk/components/details/); [GOV.UK Design System: accordion](https://design-system.service.gov.uk/components/accordion/)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## faq-08 · warning · Pro checks this automatically

All answers are in the page's HTML when it loads, not fetched after a click.

- Check: View the page source, or load the page with JavaScript off.
- Pass: Every answer's text is in the delivered HTML.
- Sources: [Google Search Central: JavaScript SEO basics](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## faq-09 · info · Pro checks this automatically

The browser's find in page reaches text inside collapsed answers.

- Check: Use find in page for a word that only appears inside a collapsed answer.
- Pass: The match is found and its answer opens, using details elements or hidden="until-found", or all answers are open by default.
- Sources: [MDN: the hidden attribute (including until-found)](https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/hidden)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## faq-10 · info · Pro checks this automatically

FAQPage structured data, where used, matches the visible questions and answers word for word.

- Check: Run the JSON-LD check and compare it with the page text.
- Pass: Every marked-up question and answer is visible on the page. Nobody expects FAQ rich results: Google limits them to well-known government and health sites.
- Sources: [Google Search Central: FAQ (FAQPage) structured data](https://developers.google.com/search/docs/appearance/structured-data/faqpage); [Google Search Central Blog: changes to HowTo and FAQ rich results (August 2023)](https://developers.google.com/search/blog/2023/08/howto-faq-changes)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## faq-11 · info

Each question has a stable anchor so it can be linked from emails and other pages.

- Check: Look for an id on each question heading and try a link to it.
- Pass: A link such as /faq#delivery-times opens at that question.
- Sources: [Nielsen Norman Group: accordions on desktop](https://www.nngroup.com/articles/accordions-on-desktop/)

## faq-12 · info

The page ends with a contact route for questions it does not answer.

- Check: Look below the last question.
- Pass: A link to contact, or contact details.
- Sources: [GOV.UK Design System: contact a department or service team](https://design-system.service.gov.uk/patterns/contact-a-department-or-service-team/); [WCAG 2.2, 3.2.6 Consistent Help](https://www.w3.org/WAI/WCAG22/Understanding/consistent-help)

## faq-13 · warning

Answers are checked against current prices, policies and processes.

- Check: Compare answers with the pricing, terms and policy pages.
- Pass: No answer contradicts another page of the site.
- Sources: [Google Search Central: creating helpful, reliable, people-first content](https://developers.google.com/search/docs/fundamentals/creating-helpful-content)
