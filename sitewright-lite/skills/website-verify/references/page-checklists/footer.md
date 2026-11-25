<!-- Generated from content/checklists/footer.json by tools/build_checklists.py. Do not edit. -->

Checklist text © 2026 Fernando Kylas (fkweb-dev), licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).

# Site footer

What the footer on every page should hold and how it should behave.

Use when: The site-wide footer, checked once on a sample of templates.

Updated 2026-11-25. 14 items, checked by hand. Record each as passed, failed, skipped (with the reason) or unavailable (with what would settle it). No score.

## footer-01 · warning

The footer holds what people look for there: a contact route, the key pages and the legal pages.

- Check: List the footer links.
- Pass: Contact (link or details), the main sections, and the privacy notice. Plus cookie and terms pages where the site needs them.
- Sources: [Nielsen Norman Group: footers 101](https://www.nngroup.com/articles/footers/); [GOV.UK Design System: footer](https://design-system.service.gov.uk/components/footer/)

## footer-02 · critical

Legal identity details the law requires are shown, for example a UK limited company's registered name, company number, registered office and place of registration.

- Check: Check which law applies to the business and compare the footer or legal page with it.
- Pass: Every required detail is present on the site, usually in the footer or on a linked legal page.
- Sources: [GOV.UK: running a limited company, signs, stationery and promotional material](https://www.gov.uk/running-a-limited-company/signs-stationery-and-promotional-material)

## footer-03 · warning

A link to the privacy notice is on every page.

- Check: Look at the footer on a sample of templates.
- Pass: A visible privacy notice link on every sampled page.
- Sources: [Regulation (EU) 2016/679 (GDPR), Articles 7 and 13](https://eur-lex.europa.eu/eli/reg/2016/679/oj)

## footer-04 · warning

Where non-essential cookies or trackers are used, a link lets people change or withdraw consent at any time.

- Check: Look for a cookie settings link and use it.
- Pass: A visible link reopens the consent choices, and withdrawing is as easy as agreeing.
- Sources: [Regulation (EU) 2016/679 (GDPR), Articles 7 and 13](https://eur-lex.europa.eu/eli/reg/2016/679/oj)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-05 · warning

The business name, address and phone in the footer match the contact page and the structured data exactly.

- Check: Compare the footer, the contact page and the JSON-LD.
- Pass: Same name, address and phone, in the same form, everywhere.
- Sources: [Google Search Central: local business structured data](https://developers.google.com/search/docs/appearance/structured-data/local-business)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-06 · warning

Footer links are real links with clear text.

- Check: Inspect the markup and read the link text.
- Pass: Each one is an a element with an href that resolves, with text saying where it goes.
- Sources: [Google Search Central: make your links crawlable](https://developers.google.com/search/docs/crawling-indexing/links-crawlable); [WCAG 2.2, 2.4.4 Link Purpose (In Context)](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-07 · info

The footer is marked up as a footer landmark, and its groups of links have headings or labels.

- Check: Inspect the markup.
- Pass: A footer element at page level (contentinfo). Link groups have a heading, or sit in a nav with an aria-label.
- Sources: [WCAG 2.2, 1.3.1 Info and Relationships](https://www.w3.org/WAI/WCAG22/Understanding/info-and-relationships)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-08 · warning

Footer text and links meet minimum contrast.

- Check: Run the contrast check over the footer, including any text on images or gradients.
- Pass: At least 4.5:1, or 3:1 for large text.
- Sources: [WCAG 2.2, 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-09 · warning

Footer links and icons are big enough to tap or have enough space around them.

- Check: Run the target-size check at 320 px.
- Pass: Each target is at least 24 by 24 CSS px, or has the spacing the WCAG exception allows.
- Sources: [WCAG 2.2, 2.5.8 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-10 · info

The footer is the same on every page.

- Check: Compare the footer across templates.
- Pass: Same links in the same order. Contact help is in the same place on every page.
- Sources: [WCAG 2.2, 3.2.3 Consistent Navigation](https://www.w3.org/WAI/WCAG22/Understanding/consistent-navigation); [WCAG 2.2, 3.2.6 Consistent Help](https://www.w3.org/WAI/WCAG22/Understanding/consistent-help)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-11 · info

There are no template leftovers or stale details.

- Check: Read the footer text.
- Pass: No theme or builder credits the owner did not choose, no placeholder text, and no out-of-date year or address.
- Sources: [Nielsen Norman Group: footers 101](https://www.nngroup.com/articles/footers/)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-12 · info

Social and icon-only links have accessible names and point to active official profiles.

- Check: Inspect each icon link and open it.
- Pass: Each one has a name such as "LinkedIn" and opens a live profile of the business.
- Sources: [WCAG 2.2, 1.1.1 Non-text Content](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content); [WCAG 2.2, 2.4.4 Link Purpose (In Context)](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-13 · warning

The footer has no blocks of keyword links, such as lists of towns or near-duplicate service pages.

- Check: Read the footer link lists.
- Pass: Every link is one a visitor would use. No lists made for search engines.
- Sources: [Google Search Central: spam policies](https://developers.google.com/search/docs/essentials/spam-policies)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.

## footer-14 · info

A newsletter sign-up, if present, has a visible label and says what people will get and how often.

- Check: Look at the form and submit a test address on a preview.
- Pass: A visible label, one line on content and frequency, and a clear success or error message.
- Sources: [WCAG 2.2, 3.3.2 Labels or Instructions](https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions)
- Sitewright (Pro, in fkweb-dev-pro) checks this automatically.
