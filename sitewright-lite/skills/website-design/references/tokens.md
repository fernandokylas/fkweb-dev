# Tokens and type

## Layers, sized to the project

Tokens can have up to three layers. Use only as many as the project needs.

1. **Primitive**: the palette and scales themselves (`--sand-100: #f6f1e7`). Skip this layer unless several roles draw on the same palette.
2. **Semantic**: roles (`--color-text`, `--color-surface`, `--color-accent`, `--color-focus`, `--space-3`, `--radius-sm`, `--duration-fast`). **Every project has this layer.** Build code and WordPress both map from it.
3. **Component**: a token scoped to one component (`--nav-link-underline`), added only where that component really needs a value the semantic roles don't give it.

A five-page site usually needs a semantic layer and nothing else. Record tokens in `semantic_tokens` by role, with their values.

Write each as `--name: value`, comma-separated, using the exact custom-property names the build will define (`--color-ink: #1f2a30, --space-1..3, --radius-1: 4px`). A range such as `--space-1..3` names the steps without values. `website-verify` compares these names and values with the built CSS or `theme.json` (`design.token-drift`), so a token renamed or retuned during the build is updated here as well.

## Roles to cover

- Colour: text, muted text, surface, raised surface, border, accent, accent text (text on accent), focus ring, error, success. Add a dark scheme only if the brief needs one.
- Space: a short scale (for example 4 to 7 steps) used for both padding and gaps.
- Type: body, small, and three or four heading sizes. A fluid scale with `clamp()` is fine; record its minimum and maximum.
- Shape: one or two radii; shadow only if the direction uses elevation.
- Motion: duration and easing tokens, if `motion_intent` uses any motion.

## Contrast as you go

Check contrast when you choose a pairing, not after the build:

- body and small text against its surface: at least 4.5:1;
- large text (24px, or 19px bold) and essential icons or borders: at least 3:1;
- the focus indicator against its surroundings: at least 3:1, and visible on every surface it can appear on;
- accent text on the accent colour, and error text on its background.

Compute ratios with the WCAG relative-luminance formula, and record the key pairs and their ratios in the design record. A palette that fails here is changed now, not patched later.

## Type sources and licences

- **System stacks** need no licence and load instantly; a good default for small sites.
- **Open-licence fonts** (SIL Open Font License and similar) are fine to self-host. Record the family, version or source, and the licence.
- **Client-supplied or commercial fonts**: use only with the client's licence. Record who supplied them and for what use.
- Self-host font files in the project for the final build. A CDN or hotlink in a prototype is fine if the design record says so.
- If a font's licence is unknown, use a system or open-licence alternative and record the open issue.

Record families, weights actually used, the scale, line heights and measure (aim for roughly 60 to 75 characters for body text) in `type_rules`.
