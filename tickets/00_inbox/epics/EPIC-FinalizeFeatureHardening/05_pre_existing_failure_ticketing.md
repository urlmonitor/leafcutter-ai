---
title: "Auto-create tracking tickets for pre-existing failures discovered during triage"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 03_test_failure_triage_agent.md
  - 04_wire_triage_into_workflow.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
  - templates/agents/test-failure-triage.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Auto-create tracking tickets for pre-existing failures discovered during triage

## Actor / Goal

In order to ensure pre-existing test failures are not silently ignored after
finalization, we need `finalize-feature.js` step 5 to dispatch `create-ticket`
for each `pre_existing` and `flaky` entry in the triage report, so that every
known breakage on main has a corresponding inbox ticket before the feature
branch is considered finalized.

## Context

When `triage_report.blocks_finalization` is `false` (all failures are
pre-existing), ticket 04 allows the workflow to proceed to step 5. But
"allowed to proceed" does not mean "silently ignored." Each pre-existing
failure must have a ticket before finalization completes.

This ticket adds a ticket-creation sub-step to step 5 (the existing
"close tickets / archive epic" step). The sub-step:

1. Iterates over `triage_report.triage_report` entries where `category` is
   `pre_existing` or `flaky`.
2. For each entry, dispatches `create-ticket` with a structured request:
   `"Tracked pre-existing test failure: <test_id>. Failing on main at
   SHA <baseline_sha>. Triage category: <category>. See finalize-feature
   triage report from <ISO timestamp>."`.
3. Records the resulting ticket filename in the workflow's completion summary.
4. If `create-ticket` fails for any entry, logs a warning and continues
   (ticket creation failure must not block finalization).

### Flaky failures

For `flaky` failures, the ticket request includes an additional note:
`"Intermittent failure detected. Failing in some runs but not others.
Needs investigation to determine root cause before adding a known-flaky
marker."`.

## Acceptance Criteria

```gherkin
Given triage_report contains one pre_existing failure
When step 5 processes the triage report
Then create-ticket is dispatched once for that failure
 And the ticket request includes test_id, baseline_sha, and category
 And the resulting ticket filename is recorded in the workflow summary

Given triage_report contains zero pre_existing and zero flaky entries
When step 5 processes the triage report
Then create-ticket is NOT dispatched
 And no new tickets are created

Given create-ticket dispatch fails for a pre_existing entry
When step 5 processes the error
Then a warning is logged with the failure details
 And the workflow continues to complete steps 5 (archive) and 6 (worktree removal)
 And finalization is not blocked by the ticket creation failure

Given finalize-feature.js returns status: "ok"
When the result is read
Then created_tracking_tickets lists the paths of any tickets created during step 5
 And the list is empty when no pre-existing failures were found
```

## Sign-offs

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] In `templates/workflows-js/finalize-feature.js`, in the step 5 block,
  before the existing "close tickets / archive epic" logic:
  - Check if `triage_report` is non-null and has entries where
    `category === "pre_existing" || category === "flaky"`.
  - For each such entry, dispatch `create-ticket` agent with the structured
    request string described in Context above.
  - Collect resulting ticket filenames (or errors) into `created_tracking_tickets`.
  - On per-entry error: log warning, push `null` to `created_tracking_tickets`,
    continue.
- [ ] Add `created_tracking_tickets` to the `status: "ok"` return value.
- [ ] Update the `const meta` phases entry for step 5 to include
  `"create_pre_existing_tickets"` as a sub-label.

## Risk & Safety

- Touches money? No.
- Touches data? No. New inbox tickets are additive.
- Reversibility? Removing the tracking-ticket sub-step from step 5 is a
  one-block deletion in the JS file. Any tickets already created remain
  in the inbox and must be cleaned up manually.
- Ticket creation failures are non-fatal. The key safety invariant (steps 5
  and 6 only run when no regressions exist) is enforced in ticket 04 and
  is not affected by this ticket.
