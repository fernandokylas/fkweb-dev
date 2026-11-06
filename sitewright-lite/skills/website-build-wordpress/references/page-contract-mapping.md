# Page contract → WordPress

How each page-contract field (see `../../website-workflow/references/project-records.md`) becomes WordPress structure. Use the adapter that matches the site: block theme (templates, template parts, patterns, `theme.json`) or Elementor (containers, widgets, templates, global styles). Content stays editable in the editor.

| Field | Block theme | Elementor |
|---|---|---|
| `route` | A Page (or post type archive) with its slug; template chosen by hierarchy (`page-{slug}.html` only when the page needs its own template) | A Page with its slug, edited with Elementor; theme template conditions where a Theme Builder template is used (Pro: record the requirement) |
| `page_job` | Drives pattern order; not rendered as text | Drives section order; not rendered as text |
| `audience` | Copy register; not rendered as text | Copy register; not rendered as text |
| `primary_action` | Buttons block linking to a real destination; reusable in a synced pattern when repeated | Button widget in a global/saved template when repeated |
| `content_source` | Post content, synced patterns or custom fields; fixture copy stays in a local fixture export, never in shipped theme files | Page content in Elementor data; fixture copy only in local export fixtures |
| `sections_and_hierarchy` | Patterns composed of Group/Columns blocks; heading blocks in order; one H1 (usually the post title) | Containers in order; Heading widgets with correct HTML tag; one H1 |
| `navigation_relationships` | Navigation block in a header template part; `404.html` template | Nav Menu widget or theme header; a 404 template or theme 404 |
| `required_components` | Block patterns and template parts using `theme.json` presets; block styles for variants | Saved templates/global widgets using global colours and fonts |
| `form_or_data_integrations` | A form plugin already on the site or a recorded choice; never a fake form presented as live | Elementor Form widget (Pro) or the site's form plugin; record which |
| `states` | Form plugin states; query loop "no results" block; empty states in patterns | Form widget messages; empty-state sections |
| `metadata_and_indexing_intent` | The site's SEO plugin fields, or core title support; never replace an existing SEO plugin | Same as block theme |
| `responsive_intent` | `theme.json` fluid type/spacing, block layout settings; minimal scoped CSS in the theme | Responsive controls per breakpoint; global breakpoint settings |
| `acceptance_checks` | Check IDs in `verification.json` against template/pattern files and, when a runtime exists, rendered pages | Check IDs against the export/fixture and, when a runtime exists, rendered pages |

Without a WordPress runtime, checks against rendered pages are `unavailable`, not `passed`. Checks against theme files and exports can still run.
