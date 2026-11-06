# Page contract → custom code

How each page-contract field (see `../../website-workflow/references/project-records.md`) becomes code. Follow the project's existing framework conventions; the examples are for plain HTML/CSS/JS and a React/Vite app.

| Field | Custom-code realisation |
|---|---|
| `route` | A file or route entry (`about/index.html`, a router path); every internal link resolves to a real route |
| `page_job` | Drives section order and what the first viewport shows; not rendered as text |
| `audience` | Copy register and reading level; not rendered as text |
| `primary_action` | A real link or button to a working destination, visible without hunting, consistent across breakpoints |
| `content_source` | Copy in the page file, a content file (Markdown/JSON) or fetched data; fixture copy carries a `data-fixture` marker that the release check rejects |
| `sections_and_hierarchy` | Landmarks (`header`, `nav`, `main`, `footer`), one `h1`, headings in order, sections as shared components where reused |
| `navigation_relationships` | Shared navigation component; `aria-current="page"` on the active item; footer links; a custom 404 route |
| `required_components` | Shared components with all states from the design record, styled through tokens (CSS custom properties) |
| `form_or_data_integrations` | Labelled controls, native validation plus messages, keyboard submit, loading/error/success feedback; a real endpoint, or a clearly labelled simulated handler |
| `states` | Rendered empty, loading, error and success states reachable in tests (query flags or fixtures excluded from production build) |
| `metadata_and_indexing_intent` | `<title>`, meta description, canonical link, robots meta, JSON-LD where intended, sitemap entry |
| `responsive_intent` | Mobile-first CSS with breakpoints from the design record; no horizontal scroll at 320 px; reflow at 400% zoom |
| `acceptance_checks` | Check IDs recorded in `verification.json` against the built page file |
