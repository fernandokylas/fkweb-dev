# Image direction

Write the brief for an image before anyone shoots, licenses or generates it. The same brief serves a photographer, a stock search and an image generator.

## The brief

For each needed asset:

- **Job:** what the visitor should understand from it (the van is local and branded; the bread is baked on site). An image with no job is a candidate for removal.
- **Subject and setting:** concrete and true to the business. Don't depict staff, premises, products or customers the business doesn't have.
- **Placement and crop:** route, section, aspect ratio at each breakpoint, and the area that must survive cropping.
- **Relation to the direction:** light, colour temperature, framing and density that fit the design record. Name a reference image only if the user supplied it or it is licensed for reference.
- **Text in the image:** avoid it. Headings and prices belong in HTML, where they can be read, translated and edited.
- **Alt text draft:** written with the brief, so the image's job and its description agree.

## Choosing a route

| Route | When | Record |
|---|---|---|
| Supplied | The business has or can take the photo | `source` names the supplier; `permitted_use` as they state it |
| Licensed library or stock | Generic scenes where authenticity isn't the point | `source` names the service and author; `permitted_use` quotes the licence name; `attribution` as required |
| Generated | Illustration or abstract imagery, never as a stand-in for real people, premises or products the business claims are real | `source` names the tool and version; `permitted_use` follows that tool's terms; the decision is recorded |
| Placeholder | Nothing usable yet | `status: placeholder` and an open issue |

Paid or external services are called only with the user's authority for that use. Without it, the brief is the deliverable.

## Review outcomes

Every candidate image ends its review with one of these outcomes, recorded in `status` (the other statuses are defined in `intake.md`):

- `approved`: matches the brief, rights are known, alt text written.
- `rejected`: say which part of the brief it fails, so the next attempt can change that.
- `placeholder`: kept only to hold the layout.

Stop iterating on an image when it meets the brief, or change the route (a different source, a simpler subject, a placeholder) when repeated attempts fail the same way.
