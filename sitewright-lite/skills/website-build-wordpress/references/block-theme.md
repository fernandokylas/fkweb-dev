# Block-theme adapter

## Files

```
<theme-slug>/
  style.css        header: Theme Name, Version, Requires at least, Tested up to, Requires PHP, License, Text Domain (= slug)
  theme.json       version 3 (WordPress 6.6+) or 2; "$schema" set
  functions.php    ABSPATH guard; enqueue scoped CSS/JS; no output on load
  templates/       index.html (required), page.html, 404.html, others only when a page contract needs them
  parts/           header.html, footer.html (declared in theme.json templateParts with their areas)
  patterns/        <slug>.php with Title, Slug (<theme-slug>/<name>), Categories
  assets/          scoped CSS/JS the presets can't express
```

## Tokens to `theme.json`

| Design record | `theme.json` |
|---|---|
| Colour roles | `settings.color.palette` (slug per role, e.g. `ink`, `paper`, `accent`, `muted`) |
| Type families and scale | `settings.typography.fontFamilies`, `fontSizes` (fluid where the design asks) |
| Spacing scale | `settings.spacing.spacingSizes` (slug = step, e.g. `30`) |
| Radius, durations | `settings.custom` (→ `--wp--custom--*`) |
| Layout width | `settings.layout.contentSize` / `wideSize` |

Turn off `defaultPalette`, `custom` colours and `defaultFontSizes` when the design is closed, so editors stay on the design's tokens. Element and block styles (`styles.elements.link`, `button`, headings) carry the design's states, including `:focus` where supported.

Name slugs after the design record's tokens so `sw_design_check.py --theme` can match them: `--color-ink` → palette slug `ink`, `--space-2` → spacing slug `2` (or record `--space-30` for slug `30`), `--font-size-body` → `fontSizes` slug `body`, `--radius` → `custom.radius`. A one-step scale recorded as `--radius-1` and built as `custom.radius` passes with a warning; rename one side to clear it.

Blocks reference presets (`"textColor":"muted"`, `var:preset|spacing|30`), never raw values. When the custom-code build shares the design, keep the CSS custom properties and the presets equal; the theme check compares them with `--tokens`.

## Templates and parts

- Each template has exactly one `main` (a Group with `"tagName":"main"`), with the skip link target WordPress adds.
- Page templates render `core/post-content`; the H1 is the post title unless the page contract says the template hides it (then the content supplies one H1).
- Template-part blocks name parts that exist in this theme. Patterns referenced from templates exist in this theme.
- Navigation: the Navigation block in the header part. Menus are content: the theme ships a fallback (page list or a pattern), never a hard-coded menu of fixture URLs.

## Patterns

Use patterns for sections repeated across pages or offered to editors. Slugs are namespaced to the theme. Text in patterns uses translation functions with the theme's text domain and escaping on output. Synced patterns (reusable blocks) are content, not theme files.

## Scoped assets

Enqueue theme CSS with the theme version. Load scripts only where they're needed (for example, from a `render_block` filter when a specific block is present) and in the footer. No remote CDNs for fonts or scripts unless the design record asked for them.
