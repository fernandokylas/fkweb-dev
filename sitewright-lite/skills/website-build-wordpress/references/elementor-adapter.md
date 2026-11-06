# Elementor adapter

**Status: unverified.** No Elementor runtime has been available to Sitewright's tests. Use this as a mapping guide, record every Elementor-specific check as `unavailable` until a matching local environment runs it, and don't claim the result works in Elementor.

Use it only when the site already uses Elementor or the user chose it (`adapter-discovery.md`).

## Mapping

| Shared record | Elementor |
|---|---|
| Colour, type tokens | Site Settings → Global Colors and Global Fonts, named after the design record's roles |
| Spacing, layout width | Site Settings → Layout (content width, container padding); container gaps from the spacing scale |
| Breakpoints | Site Settings → Breakpoints, matching the design record; don't add extra breakpoints |
| Sections and hierarchy | Containers (flexbox/grid) in page order; Heading widgets with the correct HTML tag; one H1 per page |
| Repeated components | Saved templates or global widgets that use the global colours and fonts |
| Header, footer, 404, archive | Theme Builder templates with display conditions (**Pro**); on free Elementor, the theme's own header/footer and 404 |
| Forms | Form widget (**Pro**) or the site's existing form plugin; record which. No fake success message |
| Motion | Entrance animations only where the design record plans them; respect reduced motion |

## Constraints to record

- **Edition**: list every feature the build needs that is Pro-only (Theme Builder, Form widget, global widgets, custom CSS per widget, motion effects). If the site is on free Elementor, either build without them or record the Pro requirement as an open decision.
- **Containers vs sections**: new layouts use containers. A site still on legacy sections/columns keeps them unless conversion is requested.
- **Content lives in Elementor data**: copy edited in the Elementor editor, not inline HTML widgets. An HTML widget is a contained exception, recorded like a Custom HTML block.
- **Theme pairing**: Elementor pages still need a theme for the parts it doesn't build (a lightweight or block theme). Record which.

## Checks when a runtime exists

Open each page in the Elementor editor and confirm it loads without errors and that its widgets appear in the navigator; check the rendered front end with the usual browser checks. These are browser checks recorded with the Elementor version and edition. Without that environment they are `unavailable`.

Original Sitewright work (ledger row B09, no upstream source). Wording original.
