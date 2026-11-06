# Preparing and placing assets

## Formats

| Content | Format |
|---|---|
| Logo, icons, simple illustration | SVG; check it has no embedded raster, scripts or external references, and give an inline SVG a `<title>` or `aria-hidden="true"` |
| Photographs | AVIF or WebP with a JPEG fallback when the project supports older browsers |
| Screenshots, flat graphics with text | PNG or lossless WebP |
| Favicon set | SVG plus a 32px PNG and a 180px touch icon |

Keep the original supplied file outside the published folder (or in the WordPress media library) and publish derived sizes.

## Sizes and responsive sources

- Export each image at the largest rendered size times two, not larger.
- Use `srcset` and `sizes` for images that change width across breakpoints. On WordPress, registered image sizes and the core image block do this; don't hand-write `srcset` in templates.
- Always set `width` and `height` (or an `aspect-ratio`) so the space is reserved before the file loads.
- Load the first large image of a page eagerly; lazy-load the rest with `loading="lazy"`.

## Alt text

- Describe what the image contributes in this place, in a sentence or less. The same photo can need different alt text on different pages.
- A decorative image (pure texture, a repeated visual) gets `alt=""`, and the record says `decorative`.
- A logo that links home gets the business name as its alt text, not "logo".
- Don't start with "image of" or repeat the caption next to it.

## Placeholders

- Same aspect ratio as the planned asset.
- Neutral fill with a short visible label such as "Photo to come: bakery counter". No stock face, no fake product, no generated likeness of a real person.
- In the record: `status: placeholder`, with an item in `state.json` `open_issues` until the real file replaces it. The static check's `content.placeholders` only catches placeholder text such as lorem ipsum or TODO, not a labelled stand-in image, so the open issue is what keeps it visible.

## WordPress

Theme-owned images (logo fallback, decorative patterns) go in the theme's `assets/` folder and are referenced with theme functions. Content images go through the media library so editors can replace them; the build skill decides which is which and records it.
