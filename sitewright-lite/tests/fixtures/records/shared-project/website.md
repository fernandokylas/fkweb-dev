# Website records: Harbour Lane Bakery (fictional test business)

All business details below are `[fixture]` data for testing Sitewright lite. They describe no real company.

# Brief

- audience: local residents and office workers within walking distance who want to order cakes or check opening hours `[fixture]`
- purpose: increase advance cake orders and reduce phone calls about opening hours `[fixture]`
- primary_action: send a cake order enquiry through the order form
- claims_and_evidence: "Baked on site every morning" `[fixture]`, no evidence needed for test data; no awards, ratings or testimonials are claimed
- scope: four pages (home, menu, order, contact) and a 404 page; out of scope: online payment, accounts, blog
- delivery_route: undecided; both build paths must be able to consume these records
- constraints: WCAG 2.2 AA target for tested checks; no third-party trackers; works without JavaScript for reading content
- unknowns: real opening hours (OPEN-1, non-blocking, fixture hours used); order email recipient (OPEN-2, blocks live form delivery)

# Site map

- routes: /, /menu, /order, /contact
- navigation: primary menu Home, Menu, Order, Contact in that order; footer repeats contact details and hours
- missing_page_behaviour: custom 404 page with links to Home and Menu
- global_components: header with primary menu, footer with hours and address

### Page: /

- route: /
- page_job: show what the bakery offers and get visitors to the order form or menu within one screen
- audience: first-time visitors
- primary_action: "Order a cake" button to /order
- content_source: fixture copy in this record
- sections_and_hierarchy: h1 hero with value statement; h2 this week's specials; h2 opening hours
- navigation_relationships: links to /menu and /order; Home is the active menu item
- required_components: header, hero, product card, hours table, footer
- form_or_data_integrations: n/a: no forms on this page
- states: n/a: static content only
- metadata_and_indexing_intent: title "Harbour Lane Bakery", description of bakery and order service, index, LocalBusiness schema intent
- responsive_intent: single column below 40rem; specials in a two- or three-column grid above
- acceptance_checks: nav.internal-links, a11y.landmarks, meta.basics

### Page: /menu

- route: /menu
- page_job: let visitors scan products and prices quickly
- audience: returning customers
- primary_action: link to /order from each cake category
- content_source: fixture product list in this record
- sections_and_hierarchy: h1 Menu; h2 per category (bread, pastries, celebration cakes)
- navigation_relationships: Menu is active; each category links to /order
- required_components: header, product card, price list, footer
- form_or_data_integrations: n/a: no forms on this page
- states: empty category text "Nothing in this category today"
- metadata_and_indexing_intent: title "Menu | Harbour Lane Bakery", index
- responsive_intent: price list stays a readable two-column table down to 320px
- acceptance_checks: nav.internal-links, a11y.landmarks, meta.basics

### Page: /order

- route: /order
- page_job: collect a complete cake order enquiry with no phone call needed
- audience: customers planning an event
- primary_action: submit the order enquiry
- content_source: fixture copy in this record
- sections_and_hierarchy: h1 Order a cake; form; h2 what happens next
- navigation_relationships: Order is active; success state links back to /menu
- required_components: header, form fields, button, status message, footer
- form_or_data_integrations: order enquiry form; delivery endpoint unknown (OPEN-2) so the fixture handler is labelled simulated
- states: loading while submitting; error with field-level messages; success with summary of the request; empty n/a: form always present
- metadata_and_indexing_intent: title "Order a cake | Harbour Lane Bakery", index
- responsive_intent: fields stack in one column; labels stay above fields at every width
- acceptance_checks: form.labels, form.states, nav.internal-links

### Page: /contact

- route: /contact
- page_job: give address, hours and phone in a form that copies easily
- audience: visitors planning a visit
- primary_action: tap-to-call link
- content_source: fixture contact details in this record
- sections_and_hierarchy: h1 Contact; address; h2 opening hours
- navigation_relationships: Contact is active
- required_components: header, address block, hours table, footer
- form_or_data_integrations: n/a: no forms; no map embed (privacy constraint)
- states: n/a: static content only
- metadata_and_indexing_intent: title "Contact | Harbour Lane Bakery", index
- responsive_intent: single column at all widths
- acceptance_checks: nav.internal-links, a11y.landmarks

# Design

- authority_source: toolkit default (no brand supplied)
- design_family: none
- selected_direction: warm, plain and legible; flour-white ground, dark crust-brown text and one accent for actions, because the audience scans for hours and orders
- semantic_tokens: --color-ground, --color-ink, --color-accent, --color-focus, --space-1..6, --radius-1, --duration-short
- type_rules: system UI stack for body; one serif from the system stack for headings; 1.25 scale; 65ch measure
- layout_rules: centred column max 72rem; 8px spacing grid; breakpoints 40rem and 64rem
- component_states: buttons and links have hover, focus-visible (2px outline using --color-focus), active, disabled; form fields have error and success states
- responsive_intent: reflow to one column; no horizontal scroll at 320px or 400% zoom
- motion_intent: none beyond 150ms colour transitions; reduced motion removes them

# Assets

- assets: none (text-led fixture; no images supplied)
