# Continuous build

How an authorised website job keeps moving from brief to handoff without routine approvals, and how it stops for the right reasons only.

## Phase checkpoints

Each phase ends when its exit condition holds, not when someone approves it.

| Phase | Exit condition | Saved before moving on |
|---|---|---|
| context | Known facts are distinguishable from assumptions | Brief |
| structure | Every page has a job; the main journey is coherent | Site map and page contracts |
| direction | Direction is clear enough to implement without guessing | Design record (and assets record when assets matter) |
| prototype | The risky question it was built for is answered | Findings in the design record; skip when nothing is risky |
| implement | Planned routes, content, states and integrations exist | Build files; `completed_artifacts` with fingerprints |
| verify | Required checks have fresh evidence; critical defects repaired | `verification.json` |
| handoff | Another maintainer could run and change the result | Handoff summary |

After each checkpoint, update `state.json` (`current_phase`, `completed_artifacts`, `next_action`, and `next_owner`, the skill that owns the next action) so a new session can resume. When a checkpoint supersedes a decision, review the open issues linked to it.

Record verification at checkpoints, not after every edit: at the end of a phase, before any deploy, at final QA, and when a named regression is being checked. Between them, run the helpers without `--record` to iterate, then let `sw_records.py status` say what the next recorded run must cover. Fingerprint artifacts with `scripts/sw_records.py fingerprint <path>`.

Optional records check per phase: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" check-records docs/website --phase <next phase>` confirms that the records the next phase needs exist and have no empty required fields.

## Decisions and assumptions

- Make routine design and implementation choices from the brief and project evidence. Record consequential ones in `accepted_decisions` (what, why) and guesses in `assumptions` (what, which pages or records it affects).
- Ask the user only when a decision is genuinely blocking and the brief, project and sensible defaults cannot settle it responsibly. One precise question beats a questionnaire.
- Progress updates are one or two lines at phase boundaries, not requests.

## Repair loop

A failing check is diagnosed, not retried blindly. There is no fixed attempt limit; what ends a loop is success, evidence that the approach cannot work, or a genuine blocker.

1. **Read the evidence.** Re-run the failing check and read its output; do not rely on memory of an earlier run.
2. **Find the cause before editing.** Trace where the failing value actually comes from: later CSS rules, media queries, inline styles, generated files, cached build output, a template or block override, a plugin setting, the checker's own input.
3. **Make one change that addresses that cause**, then re-run the same check.
4. **Compare.** If the result did not move, the hypothesis was wrong. Do not repeat the same kind of edit. Change strategy instead:
   - widen the search (the value may be set somewhere else, or overridden);
   - check the checker (is it reading the file you changed, a stale build, the right URL?);
   - simplify (remove the conflicting rule or component rather than patching around it);
   - take a different route to the same outcome (another accessible pattern, another layout technique).
5. **Record** each strategy change briefly in the state's `open_issues` or decisions so a later session does not repeat it.
6. If every reasonable strategy is exhausted, or the fix needs something outside the authorised scope, record the defect with its evidence, mark the check `failed`, finish the rest of the work and report it plainly. Never mark it passed.

A note in the project saying "we tried three times" is information about what not to repeat. It is not a reason to stop.

## Narrow blockers

A blocker stops only the work that depends on it.

- Identify exactly what is blocked (one form endpoint, one API key, one licensed font, one asset) and what is not.
- Record it in `blocked_dependencies` as `{dependency, needed_for, action_needed}` and in `open_issues` with `blocking: true`.
- Keep building everything else. Where the blocked piece has a visible place on the site, build it with a clearly marked simulated or placeholder state (a form that says it is not yet connected, a labelled image placeholder), never a fake credential, fake endpoint or invented content.
- Ask the user once, precisely, for the blocking input, and say what will happen when it arrives.

## Optional human feedback

Design feedback the user or a client may give later is not a blocker.

- Record it as an open issue with `blocking: false`.
- Continue with independent work. Keep the current direction unless evidence says it fails the brief.
- Do not describe the design as approved, preferred, "client-ready" or better than alternatives on the strength of your own review. Say that human review is pending.
- When feedback arrives, treat it as a brief change: update the affected records and invalidate only the evidence that depends on them.

## When to stop

Stop when the requested outcome is complete and its acceptance checks pass, when the user asks, when a real runtime or resource limit intervenes, or when every remaining item needs input or authority you do not have. Do not stop because a number of rounds has passed, and do not keep polishing after the acceptance checks pass.
