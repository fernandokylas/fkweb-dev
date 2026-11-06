# Choosing a direction

## How much to invent

Decide the invention level before choosing colours or fonts. It follows from the authority source and the request.

| Level | When | What you do |
|---|---|---|
| Extend | A design system, brand guide or existing site governs | Reuse its tokens and patterns; add only what is missing, in its own idiom |
| Place within | The brand has some fixed elements (logo, one colour, a typeface) but no system | Build a system around the fixed elements; they lead, everything else supports |
| Create | No brand material, new business or explicit fresh start | Derive a direction from the subject, audience and content |
| Replace | The user explicitly asked for a redesign | Keep content, information architecture and anything the user says to keep; replace the visual layer, and record what changed |

Never move up a level silently. Turning an extend job into a replace job is a scope change.

## Grounding a new direction

When you create, ground the direction in the subject rather than in fashion:

- What does the business physically deal in? Materials, places, tools and rhythms suggest colour, texture and type character (a bakery's flour and crust, a ferry operator's charts and signage).
- How does the audience arrive and read? A tradesperson's site is read one-handed on a phone in a hurry; a gallery's in long sessions on a laptop.
- What does the content look like? Long text wants a comfortable measure and serious body type; menus and timetables want tabular clarity; portfolios want images to lead.

Write `selected_direction` as one paragraph that names these links: "Warm, plain and legible, because …". A direction that could describe any site is not finished.

## Exploring alternatives

When direction is genuinely open (create level, nothing supplied, no stated taste), it can help to sketch two or three directions internally, as short written descriptions or token sets, and compare them against the brief. Choose one, and record in `accepted_decisions` why it won and what the others were. Show alternatives to the user only if they asked for options. Picking between concepts is never a compulsory step.

## Internal dials

Some choices sit on a spectrum. Set them deliberately and write them into `layout_rules` or `selected_direction`:

- **Density**: airy and editorial ↔ compact and informational.
- **Contrast of scale**: gentle type scale ↔ dramatic display sizes.
- **Ornament**: plain ↔ decorative (rules, textures, illustration).
- **Motion**: still ↔ expressive (see `motion-intent.md`).

The brief decides where each dial sits. A booking-heavy site sits towards compact, plain and still; a portfolio may go further on scale and ornament.

## Every page type gets the direction

A direction written for the home page alone turns into stock blocks on every other page. Before the full build, write one line per template type in `layout_rules`:

```
home: statement / split / grid / form; focal: the ferry timetable; reuses header, timetable, booking form
article: narrow text / full-bleed figure / list; focal: the headline and lead image; reuses header, figure, related list
404: statement / list; focal: the search box; reuses header, footer, search
```

- **Pages the supplied design leaves out** (the 404, article and legal pages, empty and error states) get their line too, in the same idiom. They are often the pages a reviewer notices as unfinished.
- **The 404 page** belongs to the site: header and footer, a plain sentence about what happened, a way on (search, the main sections, the home page), in the direction's voice.
- **Legal and long-text pages** use the reading measure and type scale from `type_rules`, with headings a reader can scan; they are not a raw text dump.
- **Vary the layouts within the system.** Adjacent sections with the same layout word, or one word used three times on a page, show the template; change the layout of one of them before adding decoration.

## Existing identity stays put

On an existing site, or under a supplied system, keep these unless the user asked to change them: brand colours and logo, typefaces, navigation structure and labels, the URLs of existing pages, and content meaning. If the direction really needs one of them to change, record it as a proposal in `open_issues` and keep the current value.
