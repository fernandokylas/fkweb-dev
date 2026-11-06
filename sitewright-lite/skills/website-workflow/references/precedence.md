# Precedence and rule records

## Who decides

When instructions or rules conflict, the higher level wins:

1. **Platform permissions and the user's direct requirements** govern what may be done at all (tools, approvals, publication, spending, scope such as plan-only or review-only).
2. **Accepted project facts and constraints** (brief, supplied brand, existing codebase or WordPress setup, legal and content facts) govern product decisions.
3. **The selected design system or family** (the client's design system) governs visual implementation.
4. **Toolkit defaults** in these skills fill gaps that nothing above settles.
5. **Upstream opinions** from sources the toolkit learned from are candidates only. They never override levels 1–4.

Accessibility and honest reporting are not style preferences: a visual preference at any level does not make an inaccessible pattern acceptable, and no level can turn missing evidence into a pass.

## Conflicts the toolkit settles by default

| Conflict | Default |
|---|---|
| Editorial labels, rails or numbering vs plain layouts | Plain layouts by default; use editorial devices only when the user or the supplied design system asks for them, and only where they serve the content |
| Animate everything vs instant feedback | Purpose and frequency first; an instant state change is valid; reduced-motion users keep all content |
| GSAP vs Motion vs CSS | Choose by required control, existing stack and cost; native CSS/Web Animations is the baseline |
| Banned fonts, colours or components | Treat as context-sensitive warnings; supplied brand direction wins |
| Several design concepts | Explore alternatives only where direction is genuinely open |
| Quality score vs evidence | A score helps comparison; checks and open issues decide readiness |
| Keep polishing vs stop | Repair until acceptance checks pass; stop when the requested outcome is complete |
| Several project-context documents | Link the existing authority; create only what is missing |

## Rule record

Each toolkit rule is stated once, in the reference that owns it, with:

- `id` and one-sentence `statement`
- `rationale`: why it improves the outcome
- `applicability`: when it applies, and when it does not
- `severity`: `blocker` (stops delivery), `defect` (must fix or record as an open issue), `warning`, `advice`
- `kind`: `objective` (a check can decide it) or `subjective` (needs judgement; never reported as a measured result)
- `exception_path`: how a project overrides it (brand authority, user requirement, recorded decision)
- `source`: `original` or the name of the source it was adapted from
- `verification`: the check ID or manual method that confirms it
