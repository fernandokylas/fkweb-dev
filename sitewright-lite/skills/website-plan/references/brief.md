# Writing the brief

How to fill each brief field from what the user gave you, without inventing what they did not.

## Two kinds of information

Keep **product facts** (who the business is, what it sells, what is true about it) apart from **per-surface decisions** (what this page or this site should emphasise). Facts belong to the brief and change rarely; per-surface decisions belong to page contracts and design. Mixing them leads to pages that "decide" facts, such as a hero that invents a founding year because the layout wanted a number.

## Field by field

| Field | How to fill it |
|---|---|
| `audience` | Name the visitor and what they need to decide. "Parents choosing a swim school for a 5-year-old" is useful; "everyone" is not. If several audiences exist, rank them. |
| `purpose` | The business outcome, in one sentence: more phone enquiries, table bookings, applications, newsletter sign-ups. |
| `primary_action` | One action with its destination (`tap-to-call 555-0142`, `booking form → email`). Secondary actions go in page contracts. |
| `claims_and_evidence` | One line per public claim: claim, status marker, source. "Family-run since 1998 [supplied] (owner's email)". A claim with no source is either cut or rewritten as something checkable. |
| `scope` | Pages and features asked for, plus what is explicitly out (e-commerce, accounts, translations). |
| `delivery_route` | `custom-code`, `wordpress` or `undecided`, with the discovery facts actually found. |
| `constraints` | Only constraints that were stated or are visible in the project: brand rules, accessibility targets, hosting, deadline, budget, legal text. |
| `unknowns` | `OPEN-n: question; impact; blocking yes/no; recommended: the default you build on`. Every unknown also appears in `open_issues` in the state record. |
| `confidence` | Optional. How solid each field is; see "Confidence and questions for the client". |

## Sparse briefs

A one-line request ("a site for my plumbing business") is enough to start. Infer, record, continue:

1. Infer the likely audience and primary action from the business type (a mobile plumber: local householders in a hurry, so call or message).
2. Infer a modest page set that fits that action (often one to four pages; resist padding).
3. Record each inference as `[assumption]` in the brief and in `assumptions` with the records it affects, so it can be revised cheaply.
4. Mark every missing business fact (service area, hours, prices, accreditations, reviews) as `unknown (OPEN-n)` and plan a visible placeholder for it, never a plausible-looking value.

Ask a question only if the answer changes what gets built and no reasonable default exists, for example which of two named businesses the site is for. One precise question, not a form.

## Confidence and questions for the client

The brief closes by telling the owner where it is solid and what only they can settle.

- **Confidence per field.** The optional `confidence` field rates each brief field `high`, `medium` or `low`, with the reason in a few words:
  - `high`: the owner or a supplied document says so, and nothing contradicts it;
  - `medium`: inferred from one source (the existing site, one email, a competitor the owner named), or two sources that disagree on a detail;
  - `low`: inferred from the business type alone, or the sources conflict.

  Example: `confidence: audience high (owner's email); primary_action medium (existing contact page); constraints low (nothing stated)`. Check the `low` fields first when the owner replies: that is where a change of direction usually starts.
- **Questions for the client.** List the `unknowns`, blocking ones first. Each carries a recommendation, so the owner confirms or overrides it rather than starting from nothing: `OPEN-3: Do you also cover Gozo? Impact: service-area copy and the map. Blocking: no. Recommended: Malta only, as on the van livery.` If no recommendation is possible, say what would make one possible (a price list, a yes or no, a document).
- These questions go into the handover and the owner's next reply. They are not a questionnaire sent before work starts: the build carries on with the recommendations recorded as assumptions, and the rule above still holds (ask straight away only when the answer blocks the work).

## Proof and invented content

The site must not state what nobody told you. This covers testimonials and reviewer names, star ratings and review counts, client logos, "trusted by" numbers, years in business, awards and accreditations, prices, guarantees, legal and policy text, addresses, phone numbers, emails and opening hours.

- Supplied: use it, marked `[supplied]`.
- Missing but needed: a placeholder that reads as one ("Customer quote to come"), plus an open issue.
- Test fixtures: keep `[fixture]` labels; fixture data never moves into a real client's output.

## Delivery route discovery

Use project signals before asking. A `wp-content/`, `theme.json`, `style.css` theme header or builder export means WordPress; `package.json` with a framework, or static HTML files, means custom code. Record what was found (framework and version, theme type, builder, plugins) and what was not checked. For a new project with no stated preference, recommend a route with a one-line reason and record it as an assumption; static HTML is the plain default for small brochure sites.

## Existing sites

When the request is a change to an existing site, the existing site is the brief's main evidence: its content, navigation, brand and conventions are `[fact]` unless the user says otherwise. Plan only the change asked for, and record anything you would change but were not asked to as a suggestion, not a decision.
