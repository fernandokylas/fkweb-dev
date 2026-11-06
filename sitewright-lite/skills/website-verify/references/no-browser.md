# When no browser is available

Verification still has value without a browser, but its claims shrink. Say exactly what was and wasn't checked.

## Still do

- Run `sw_site_check.py` on the built HTML and record its results. These are real `passed` or `failed` results for what the static checks cover.
- Run the project's build, typecheck and unit tests, if it has them, and record them.
- Review the source for the browser checks' concerns: focus styles exist, the reduced-motion block covers each animated component, the form has its states, cleanup functions exist for each observer and listener. Record findings from this under `source.*` IDs (`source.focus-styles`, `source.reduced-motion`, `source.form-states`, `source.cleanup`) with method `manual` and the limitation "source review; not run in a browser". A `browser.*` ID only ever carries method `browser`; the record helper rejects anything else, so a source review can never stand in for a browser check.

## Record each browser check as unavailable

For every required `browser.*` check, from the project root:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" record docs/website/verification.json --root . --check-id browser.keyboard --target <built-site> --result unavailable --method browser --tool-and-version "none available" --evidence-path docs/website/evidence/static-check.json --finding "No browser automation tool in this session" --limitations "Keyboard order and focus visibility not observed" --issue-id ISSUE-browser-unavailable --require
```

and add the issue to `state.json` `open_issues` with what would be needed to run it (any browser automation tool, or a person following the procedure in `check-catalogue.md`).

The gate will not pass while required checks are `unavailable`. That's correct: report the site as built and statically checked, with browser verification outstanding.

## Never claim

- how the site looks, at any width;
- that keyboard navigation, focus, forms, motion, reduced motion or no-JS behaviour works;
- that there are no console errors;
- that a screenshot or visual comparison was taken.

A user can run the browser checks later, or accept the limitation by name; record either outcome.
