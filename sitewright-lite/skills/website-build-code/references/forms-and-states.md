# Forms and states

Every page contract lists its `states`. Each one must be built, reachable and checked, not only the happy path.

## Form structure

- Every control has a visible `<label for>` (or wrapping label). A placeholder is a hint, not a label.
- Group related controls with `<fieldset>` and `<legend>`; required fields say so in the label text, not only with an asterisk.
- Hints and error messages are linked to their control with `aria-describedby`.
- Use the right input types and `autocomplete` values (`name`, `email`, `tel`, `street-address`), so phones show the right keyboard and browsers can fill them.
- The form submits with the keyboard (Enter in a field, Space or Enter on the button) and works at 320px.

## Validation and feedback

- Validate on submit, and again on change only for fields already marked invalid. Don't show errors while someone is still typing their first attempt.
- On error: mark each invalid control with `aria-invalid="true"`, put a specific message next to it ("Enter an email address like name@example.com", not "Invalid"), show a summary at the top with links to the fields, and move focus to the summary or the first invalid field.
- A status region (`role="status"` or `aria-live="polite"`) announces loading, error and success. Use `role="alert"` only for errors that interrupt.
- Loading: disable repeat submission, set `aria-busy="true"` on the form, and show progress in text, not only a spinner.
- Success: say what happened and what happens next, with a way forward (a link back, a reference number). Move focus to the message.

## Endpoints and honesty

| Situation | Build |
|---|---|
| A real endpoint and its recipient are recorded decisions | Wire it, handle network failure and server errors as the error state, never log or echo personal data |
| No endpoint yet | A simulated handler: `data-handler="simulated"` on the form, visible text saying submissions aren't sent yet, and a success message that says it was simulated. Log the missing endpoint as an open issue |
| A third-party form or newsletter service | Only with a recorded decision and credentials the user supplied. Otherwise build the simulated handler and record the dependency in `blocked_dependencies` |

A simulated form passes the mock-up criteria only. `sw_site_check.py --release` fails it, and a real-looking endpoint stays `unavailable` until a submission is tested: post valid input to a local capture stub on 127.0.0.1 (or the provider's test mode, with authority for that call), save the request and response, and record `integration.form-endpoint` with `--method browser` or `manual` and `--mode production`. Development tests never send a real enquiry.

Never write an API key, token or sample credential into the code, even as an example. A placeholder such as `YOUR_SERVICE_KEY` in documentation is fine; a realistic-looking value is not.

## Data states

For lists, menus, search results and anything fetched:

- **Empty**: a helpful message ("Nothing in this category today") and, where it makes sense, a next step.
- **One** and **many**: layouts that hold with a single item and with long lists.
- **Loading**: reserve space so the page doesn't jump when data arrives.
- **Error**: say what failed and offer a retry or alternative.

## Making states reviewable

Each state must be reachable without editing code: a query flag (`?state=error`), a fixture file, or a dev-only story. Keep review flags inert in production builds, or limit them to fixture pages the release check flags. Record how to reach each state in the page contract's `acceptance_checks` so verification can visit it.
