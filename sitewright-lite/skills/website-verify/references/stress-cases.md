# Stress cases

Pages built against tidy sample content break on real content. Run these cases on each page type that shows variable content.

## Cases

| Case | How to create it | Look for |
|---|---|---|
| Long text | The longest plausible name, title or label the site will receive; a word with no break points (a long URL or email) | Overflow, clipped buttons, headings that push actions off screen |
| Translation | Labels and headings about 40% longer, and a language with longer words, if the site is or may be translated | Fixed-width buttons, navigation that wraps into two rows badly |
| Missing image | Remove or break one image reference | Collapsed layout, broken-image icon, alt text overflowing its box |
| Empty list | Zero items in a menu, list or result set | A helpful empty state, not a blank area |
| One item | A single item | Layouts that assume a grid of several |
| Many items | Far more items than the design shows (for example 50) | Performance, scroll length, pagination or grouping |
| Zoom | 200% and 400% browser zoom (or 640px and 320px viewport) | Reflow without horizontal scroll, nothing hidden |
| Slow network | Throttled loading, where a browser tool supports it | Loading states visible, layout reserved |

## Rules

- Feed the stress values in where real content comes from (the content file, API fixture or CMS entry) and leave the component code alone, so what you test is what will ship.
- Pick extremes this site could really receive, or that its data schema permits: a café name of 60 characters is a fair test, one of 10,000 is not.
- Restore the normal content afterwards, or keep the stress set as a separate fixture.
- Record each case run as a manual or browser check (for example `stress.long-text`, `stress.empty-list`) with the values used. A case not run is not recorded as passed.
