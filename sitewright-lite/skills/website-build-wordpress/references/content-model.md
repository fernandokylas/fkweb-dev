# Content model

Decide where each piece of content lives before building pages. The owner edits content in WordPress; the theme only presents it.

| Content | Home | Notes |
|---|---|---|
| Page body copy, sections, calls to action | Post content (blocks) of the Page | Each section a Group/Columns/Heading/Paragraph/Buttons composition; editable in the block editor |
| Repeated section on several pages | A theme pattern (copied on insert) or a synced pattern (shared, edited once) | Synced when the page contracts say the copy must stay identical |
| Site-wide header and footer | Template parts | Opening hours or contact details that change go in the part, not hard-coded per page |
| Structured, repeated items (menu items, events, staff) | Blocks in post content for a handful; a custom post type only when the brief needs listing, filtering or many entries | A custom post type belongs in a plugin, not the theme |
| Fields beyond title and content | Core custom fields or block bindings; ACF only when the site already uses it | Never make ACF a requirement of a new site |
| Headless delivery | REST API (core); GraphQL only when the site already uses it | Out of scope unless the brief says headless |
| Meta description | The site's SEO plugin when one is active; otherwise the excerpt, printed by a theme fallback that steps aside for SEO plugins | Never duplicate tags an SEO plugin already prints |
| Fixture copy | A local content export (block markup files, WXR) used to load a disposable site | Never in theme files or patterns that ship |

## Editability

- Content is blocks, not one Custom HTML block holding a whole page. A Custom HTML block is acceptable only for a contained exception the editor can't build (for example a simulated form while no form plugin is chosen); record it and expect a warning from the theme check.
- No classic (freeform) chunks in block content, and no blocks from plugins that aren't installed.
- Block attributes are valid JSON and the saved markup matches what the block would save; otherwise the editor shows "invalid content" and the owner can't edit it. The browser check `browser.wp-editor-valid` confirms this in a real editor.
