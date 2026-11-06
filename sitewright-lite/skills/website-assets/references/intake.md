# Asset intake

Before any design work depends on an image, find out what the business already has and what it is allowed to use.

## Where to look

1. Files the user supplied in this conversation or put in the project.
2. The existing site or repository: `public/`, `assets/`, `static/`, the theme's `assets/`, the WordPress media library export if one is present. Note each file's path and dimensions.
3. Brand material the user names: a brand guide, logo files, a photo library. Ask for the files; don't reconstruct them.

Never take a logo, product image or photo of the client's premises from a search engine, social profile, review site or another website, even if it looks official. If it's needed, the entry is `needed` with a note of who can supply it.

## What to capture per file

| Field | How to fill it |
|---|---|
| `asset_id` | short stable name, e.g. `logo-primary`, `hero-bakery-counter` |
| `local_path` | where it sits in the project; a file only on someone else's server isn't local |
| `source` | who made or supplied it: "supplied by owner (email 2026-10-02)", "existing site `/img/van.jpg`", "Unsplash photo by <name>, file supplied by the user" |
| `permitted_use` | what the supplier or licence allows, in their terms; `standing:<id>` under a standing permission (below); `unknown` until someone says |
| `supplied_by` | optional: `owner`, `client`, `third-party`, `generated` or `unknown`; who holds the rights, which `source` may not show |
| `attribution` | required credit text and where it goes, or `none required` with the reason |
| `crop_and_size` | planned crop and the largest rendered size |
| `placement` | route and section from the page contract |
| `alt_text` | what the image tells the visitor, or `decorative` |
| `status` | one of the statuses below |

### Three kinds of supplied material

- **Owner or client material:** their own work, photos of them, their logo. They can authorise it themselves.
- **Third-party material:** stock, a photographer's or agency's work, another company's logo, a customer's photo. It needs its own licence or written permission, even when the owner supplied the file.
- **Unknown:** nobody has said. It stays `unknown`, and in a mock-up it stays a labelled placeholder.

"Supplied" alone is not "authorised". When the owner or client says that a whole class of their own material may be used (for example "all my portfolio work and portraits, on this site"), record it once as a standing permission in the assets record, then give each covered asset `permitted_use: standing:<id>` and `supplied_by: owner` (or `client`):

```markdown
### Permission: owner-material

- scope: the owner's own portfolio work, portraits and logo, on this site
- granted_by_role: owner
- date: 2026-10-27
- source: owner's message in the project chat, 27 Oct 2026
```

Only the owner or client grants a permission; you record who granted it, when and where, and never grant one yourself or read one into silence. A standing permission never covers third-party material: the design check fails a `standing:` asset whose `supplied_by` isn't `owner` or `client`, and a citation of a permission that isn't recorded.

Statuses:

- `supplied`: the file is in the project but hasn't been reviewed against its brief and rights.
- `needed`: the brief calls for it and no file or stand-in exists yet.
- `placeholder`: a stand-in holds its place in the layout.
- `missing`: someone said it exists (a logo file, a photo shoot) but it hasn't arrived or can't be found; kept visible instead of replaced by an invented one.
- `approved` or `rejected`: the review outcome (see `image-direction.md`).

## Quality notes on supplied files

Note problems without silently fixing them: a logo only available as a small raster, a photo too small for its planned size, a screenshot that shows personal data, visible watermarks. Each one is either repaired with the user's material, replaced, or recorded as an open issue.

## Identity facts

A logo's colours, clear space and minimum size, when the brand guide states them, go to the design record as constraints. Don't infer a brand palette from a logo and present it as the client's palette; if colours are derived, the design record says so.
