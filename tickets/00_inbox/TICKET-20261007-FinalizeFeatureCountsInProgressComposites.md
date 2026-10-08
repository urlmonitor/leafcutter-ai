---
title: "finalize-feature: a composite AC left in_progress is not counted as closed"
status: todo
components:
  - finalize
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target:
  - pipeline
  - prompt
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - finalize-feature
  - ac-closure
  - composite-ac
last_updated: 2026-10-07
files_touched:
  - templates/workflows-js/finalize-feature.js
  - tests/test_finalize_feature_closure.js
  - unit_tests/workflows/test_finalize_closure_composite_counts.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# finalize-feature: a composite AC left in_progress is not counted as closed

## Actor / Goal
In order that the finalize report says how many source ACs really reached `done`, we need
finalize-feature's AC-closure step to run `mark_ac_done.py` the way the fulfillment gate does, with
`--test-root`, and to report `in_progress` composites on their own. Then a composite whose children
are done is closed, and one that is not is never counted as closed.

## Context
- **Source.** pr-reviewer finding M-3 on EPIC-BuildToolingRunsThrough ticket 06
  (`tickets/00_inbox/epics/EPIC-BuildToolingRunsThrough/06_TICKET-20261006-CompositeAcGoesInProgress.md`,
  Comments, 2026-10-06 16:45).
- **The call.** SUB-STEP D of the closure prompt (`templates/workflows-js/finalize-feature.js:1605-1614`)
  runs `mark_ac_done.py --ticket <ticket_path> --ac-root ...` without `--test-root` (:1611). Exit 0
  increments `acs_closed` (:1613). Any other exit logs a WARNING and increments `acs_skipped` (:1614).
- **What that does since ticket 06.** Without `--test-root`, no covers tag is collected, so no child
  is ever proven (`scripts/ac_store/mark_ac_done.py:103`, :123). Then:
  - a composite whose children really are done goes `in_progress`: stdout `marked <id>
    work_status=in_progress (unfinished children: ...)`, exit 0. It is counted in `acs_closed`, which
    overstates.
  - an already-done composite is refused: exit 3, a WARNING, counted in `acs_skipped`.
- **Where the counters go.** The reply shape (:1655-1656), the parse and its defaults (:1667-1670,
  :1695-1696), the log line (:1702) and the final result (:2345-2346).
- **With `--test-root`**, `mark_ac_done.py` also runs the coverage gate (`verify_done_eligible`) for a
  leaf (:187-198). A leaf without a passing, covers-tagged test is then refused with exit 3 instead of
  being marked `done`. That is the rule the required proof-of-done CI check applies anyway, but it is a
  change in what finalize closes.
- **No AC covers this.** BO-202's it-po amendment (2026-10-06): "finalize-feature.js and build-ac call
  mark_ac_done without --test-root. No existing AC covers that". So the ACs below are ticket-local.
- **Analogous callers without `--test-root`**, out of scope (the pr-reviewer judged that neither
  needs a ticket):
  - `templates/agents/build-ac.md:546` and :600, a command printed for the user to run; exit 3
    simply surfaces;
  - `templates/scripts/commit_guardian/hooks/check_ac_done_on_merge.py:137-175` (ACD-600b), which logs
    a warning and always exits 0.
- **Size.** `finalize-feature.js` has 2380 raw lines; check-file-size measures 1802 of them against
  the 1000-line limit (2026-10-07), so it is over. Under the ratchet a
  changed line counts as an added line, so the file must end shorter by at least the number of lines
  added or changed. Keep the JS change to reading one more counter; put the counting rule in the
  prompt text.

## Acceptance Criteria
- [ ] AC-1: SUB-STEP D runs `mark_ac_done.py --ticket <ticket_path> --ac-root ... --test-root ${WORKTREE_ROOT}`. A composite whose children are all done and proven becomes `done` and is counted in `acs_closed`.
- [ ] AC-2: A composite that `mark_ac_done.py` leaves `in_progress` is counted in a new `acs_in_progress` counter, never in `acs_closed`. The step logs the unfinished children the script names.
- [ ] AC-3: An already-done composite refused with exit 3 is still counted in `acs_skipped`, logged with the script's `REFUSED:` line. Finalize does not fail on it (the non-fatal rule is unchanged).
- [ ] AC-4: The closure reply shape, the log line at :1702 and the final result carry `acs_in_progress` next to `acs_closed` and `acs_skipped`. A reply without the field is read as 0, as the other two are.
- [ ] AC-5: A leaf with a passing, covers-tagged test is still closed and counted in `acs_closed`. A leaf the coverage gate refuses is counted in `acs_skipped` with its `REFUSED:` reason, and finalize continues.

## Test Requirements

```yaml
tests:
  - name: test_closure_step_passes_test_root_and_counts_in_progress_apart
    location: tests/test_finalize_feature_closure.js
    type: unit
    covers: [AC-1, AC-2, AC-3]
    description: |
      Following the file's existing pattern (it reads SUB-STEP D from finalize-feature.js): the
      mark_ac_done.py command carries --test-root; an in_progress outcome increments
      acs_in_progress and not acs_closed; exit 3 still increments acs_skipped as non-fatal.
      Red today: there is no --test-root and no acs_in_progress.
  - name: test_final_result_reports_in_progress_separately
    location: unit_tests/workflows/test_finalize_closure_composite_counts.py
    type: integration
    covers: [AC-4]
    description: |
      Drive the real finalize-feature.js closure step with a stubbed closure reply carrying
      acs_closed 1, acs_in_progress 1 and acs_skipped 0 (for example with the stubbed-globals driver
      harness in unit_tests/prompt_assembly/_driver_harness.py). The log line and the final result
      show 1 / 1 / 0. A reply without acs_in_progress gives 0.
  - name: test_mark_ac_done_with_test_root_closes_a_proven_composite_and_refuses_an_unproven_leaf
    location: unit_tests/workflows/test_finalize_closure_composite_counts.py
    type: integration
    covers: [AC-1, AC-5]
    description: |
      In a temporary store, run the exact command form from SUB-STEP D (with --test-root): a
      composite with done, covered children ends done (exit 0); a covered leaf ends done (exit 0);
      a leaf with no covers tag is refused with exit 3 and its file is unchanged.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_closure_step_passes_test_root_and_counts_in_progress_apart; test_mark_ac_done_with_test_root_closes_a_proven_composite_and_refuses_an_unproven_leaf | | |
| AC-2 | test_closure_step_passes_test_root_and_counts_in_progress_apart | | |
| AC-3 | test_closure_step_passes_test_root_and_counts_in_progress_apart | | |
| AC-4 | test_final_result_reports_in_progress_separately | | |
| AC-5 | test_mark_ac_done_with_test_root_closes_a_proven_composite_and_refuses_an_unproven_leaf | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### test-writer
- [ ] Extend `tests/test_finalize_feature_closure.js` and write
  `unit_tests/workflows/test_finalize_closure_composite_counts.py`.

### llm-expert
- [ ] SUB-STEP D (1605-1614): add `--test-root ${WORKTREE_ROOT}`; count an `in_progress` outcome in
  `acs_in_progress` and log its unfinished children; add `acs_in_progress` to the reply shape (1655-1656)
  and to the scope-violation reply (1637-1638).

### python-coder
- [ ] Read `acs_in_progress` with a 0 default (1667-1670, 1695-1696), and add it to the log line (1702)
  and the final result (2345-2346). Pay back every added or changed line under the ratchet.
- [ ] Run `python scripts/build.py` and stage every tracked output it changes.

### test-runner / pr-reviewer / commit
- [ ] Run the two test files and the existing finalize tests (`unit_tests/workflows/test_bo_1000a_*.py`).
- [ ] pr-reviewer: name the leaf behaviour change (AC-5) in the PR description.

## Risk & Safety
- Touches money? No.
- Touches data? AC `work_status` at finalize. Leaves without proof are no longer marked `done` here;
  they stay open, which is what proof-of-done CI demands.
- Reversibility: revert the commit.

## Out of Scope
- `build-ac.md` and `check_ac_done_on_merge.py` (see Context).
- SUB-STEP C and D still call `python3` (:1601, :1611). That is the interpreter question the epic left
  for a `{{config.python_command}}` ticket.
- ACD-600a's wording for composites (`TICKET-20261007-AcdSixHundredAWordingForComposites`).
