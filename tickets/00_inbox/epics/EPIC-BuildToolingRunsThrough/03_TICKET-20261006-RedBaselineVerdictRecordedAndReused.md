---
title: "The red-baseline gate records its own pass on the ticket and a resumed run reuses it"
status: todo
components:
  - build_orchestration
  - testing_quality
created: 2026-10-06
depends_on:
  - 01_TICKET-20261006-GateUsesProjectInterpreter.md
  - 02_TICKET-20261006-HandoffContinuesTheTicket.md
priority: high
complexity: high
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: TQ-500f-3-ii
ac_traceability:
  id: TQ-500f-3-ii
  path: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml
requires_diagram: false
requires_adr: false
change_target:
  - pipeline
  - code
risk_surface: contract_boundary
files_touched:
  - scripts/build_orchestration/_fl_heavy_lane_gate.py
  - scripts/build_orchestration/_fl_cli.py
  - scripts/build_orchestration/fast_lane.py
  - scripts/build_orchestration/_fl_red_baseline_support.py
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
  - unit_tests/workflows/test_tq500f3ii_heavy_lane_red_baseline_gate.py
  - unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py  # new in 01
  - templates/skills/ticket-authoring/SKILL.md
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  llm-expert: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
---

# 03: The red-baseline gate records its own pass on the ticket and a resumed run reuses it

## Actor / Goal

As the build driver, I want the red-baseline reader to record its own pass in the
ticket, and a resumed run to reuse that record under strict conditions. Then a ticket
that halted after its coder started can be resumed. Today the coder's uncommitted
code turns the new tests green, and the gate wrongly halts the ticket as
"green at baseline". A ticket whose tests really are green before any coding still
halts, with a clear `green_at_baseline` message that says what to do.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 2). Implements TQ-500f-3-ii as
amended on this branch: F2 (record and reuse) and F3 Option A (the
`green_at_baseline` halt). Both are user decisions of 2026-10-06.

**Root cause**
- `redBaselineGateChecked` exists only in memory for one drive:
  - `templates/workflows-js/build-feature.js:1914`, set at 2107-2108;
  - `templates/workflows-js/build-ticket.js:1547`, set at 1743-1744.

  Every re-run with a coder still `needed` runs the reader again.
- `verify_red_baseline` (`scripts/build_orchestration/fast_lane.py:263-421`) runs the new tests against the current working tree. Once the coder's uncommitted code is there they pass, so it returns `all_new_tests_green_at_baseline` (403-410), and the JS halts (2135-2141 / 1771-1777).
- Any halt after the coder ran triggers this: today's handoff halt, a blocker, a retry cap, a crash.

**Why not "red at the test-writer's commit"**
- No per-phase commit exists. Tests and code stay uncommitted until the commit phase (priority 12).
- Running against merge-base or HEAD in a temporary checkout has three problems:
  - in an epic, merge-base predates earlier tickets, so the tests go red by import error, which TQ-500f-3-i refuses as absence-only red;
  - it costs a full checkout per gate run;
  - it changes the reader's inputs, which breaks TQ-500f-3-ii's rule that both lanes give an identical verdict.

**Rule: a durable record written by the reader alone**
- `heavy_lane_gate` takes `--ticket <path>`.
- On `gate_passed`, it alone (never the test-writer) writes one frontmatter line with an anchored atomic write. Use the `scripts/ac_store/mark_ac_done.py::_atomic_write` pattern (200-260):

  ```
  red_baseline_gate: {"passed": true, "recorded_at": "<iso>", "head": "<sha>", "source_ac": [...], "red": [{"file": "...", "function": "..."}]}
  ```

  `ticket_frontmatter_guard` ignores unknown keys.
- A later run reuses the record, without running pytest, only when all of these hold:
  - the record exists;
  - its `source_ac` equals the ticket's current ids;
  - every recorded red `(file, function)` is still among the newly-added covers-tagged tests. This is a subset check, because a later test-writer handoff may add tests.

  It then returns `gate_passed: true, reused: true` and an outcome naming `recorded_at` and `head`. The newly-added partition is computed without running pytest (`scripts/ac_store/done_proof.py::_scan_test_root_for_covers_tags` plus `scripts/build_orchestration/_fl_red_baseline_support.py::_partition_newly_added`).
- In every other case the reader runs as today and fails closed.
- If the record cannot be written, the gate still passes, and reports `recorded: false` and `record_error`.

**`green_at_baseline` (F3 Option A, no automatic pass)**
- Keep the halt for `all_new_tests_green_at_baseline`, but classify it `green_at_baseline`.
- List the green tests and suggest: set the coder phase `not_needed` with a comment naming the ticket or commit that delivered the behaviour.
- The driver never flips the phase itself (TKT-600b-4).
- The gate runs only before a coder dispatch. test-runner, pr-reviewer and ac-fulfillment still verify the tests.

## Constraints

- **Twins.** The gate command and halt message change in both `build-feature.js` and `build-ticket.js`, in the same commit.
- **File-size ratchet (GE-127b-1, GE-127f-2).** `build-feature.js` measures 2964 / 1000 and `build-ticket.js` 1647 / 1000. Each staged file may measure at most `previous − gross measured lines added`, and a changed line counts as added.
  - Appending `--ticket ${worktreeTicketPath}` (build-ticket.js: `${ticketPath}`) to the existing gate line changes 1 line in each twin.
  - Changing the halt message changes more.
  - Pay each of these back by removing at least as many further measured lines in the same file.
  - Compute the `green_at_baseline` classification, the green-test list and the remedy text in Python (`heavy_lane_gate` verdict fields), and have the JS echo them inside its existing halt return.
- **Python size.** Measured / limit at bc8e6c62:
  - `fast_lane.py` 387 / 400: only a pass-through of `--ticket`; crossing 400 is refused;
  - `_fl_heavy_lane_gate.py` 36 / 400: the record and reuse logic goes here, or in a new `_fl_*` module registered for deployment;
  - `_fl_cli.py` 262 / 400;
  - `_fl_red_baseline_support.py` 305 / 400.
- **Test-file size.** `test_tq500f3ii_heavy_lane_red_baseline_gate.py` measures 346 / 400; only change its `wrapper_only_keys` there. New driver-side tests go in `test_tq500f3ii_gate_driver_contract.py`, which ticket 01 creates.
- **Build mirrors.** After the template edits, run `python scripts/build.py` and stage every tracked output it changes.
- **Lane parity (TQ-500f-3-ii).** Whenever the reader runs, its verdict is identical in both lanes. The fast lane's `verify_red_baseline` invocation does not change. The heavy lane's extra keys (`reused`, `recorded`, `record_error`, the halt classification) are wrapper keys only.

## Acceptance Criteria

- [ ] AC-1: When `heavy_lane_gate --ticket <path>` passes, it writes exactly one `red_baseline_gate:` frontmatter line (passed, recorded_at, head, source_ac, red) with an anchored atomic write. The real `ticket_frontmatter_guard.validate` and `check_doc_frontmatter` accept the ticket afterwards. The test-writer never writes this line.
- [ ] AC-2: A later gate run on the same ticket reuses the record without running pytest only when the record exists, its `source_ac` equals the current ids, and every recorded red `(file, function)` is among the newly-added covers-tagged tests (subset). It then returns `gate_passed: true`, `reused: true`, and an outcome naming `recorded_at` and `head`.
- [ ] AC-3: In every other case the reader runs as today and its verdict decides: no record, a different `source_ac`, a recorded red test renamed or removed, or only a test-writer `red_baseline_verified` claim.
- [ ] AC-4: If the record cannot be written (missing or unwritable ticket), the gate still passes and reports `recorded: false` with `record_error`.
- [ ] AC-5: Both twins pass `--ticket <ticket path>` on the gate command. The fast lane's `verify_red_baseline` command is unchanged, and whenever the reader runs, its verdict keys are identical across lanes apart from the wrapper keys.
- [ ] AC-6: An `all_new_tests_green_at_baseline` verdict halts the ticket before the coder with classification `green_at_baseline`. The halt lists every green newly-added covering test and suggests setting the coder phase `not_needed` with a comment naming the implementing commit. The driver never changes the phase itself.
- [ ] AC-7: `templates/skills/ticket-authoring/SKILL.md` documents `red_baseline_gate` as a field written only by the gate, which authors and agents must not write or edit.

## Test Requirements

```yaml
tests:
  - name: test_gate_pass_writes_record_accepted_by_real_guards
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      On the _tq500f3i_fixtures real git fixture with red new tests,
      heavy_lane_gate --ticket <tmp ticket> passes and the ticket gains exactly
      one red_baseline_gate line holding passed true, recorded_at, head equal to
      the fixture HEAD sha, the source_ac list and the red (file, function)
      pairs. The real ticket_frontmatter_guard.validate returns no errors and
      check_doc_frontmatter accepts the file.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_rerun_after_coding_reuses_record_without_pytest
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      After a recorded pass, the fixture's production code is changed so the
      new tests pass ("coding"), and heavy_lane_gate is run again. It returns
      gate_passed true and reused true, with an outcome naming recorded_at and
      head, and the pytest runner is never invoked.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_renamed_recorded_red_test_runs_reader_and_fails
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      After a recorded pass and coding, one recorded red test function is
      renamed. The next run does not reuse the record, the reader runs, and it
      returns gate_passed false with reason all_new_tests_green_at_baseline.
    framework: pytest
    type: integration
    angle: failure
  - name: test_different_source_ac_runs_reader
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      With a record made for source_ac [A], a run with --source-ac A,B does not
      reuse it (reused absent or false), and the reader's verdict is returned.
    framework: pytest
    type: integration
    angle: boundary
  - name: test_test_writer_claim_without_record_runs_reader
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      A ticket whose test-writer sign-off claims red_baseline_verified but which
      has no red_baseline_gate line gets a run in which the reader runs, and its
      verdict decides (the K1 guarantee is preserved).
    framework: pytest
    type: integration
    angle: failure
  - name: test_missing_ticket_passes_with_recorded_false
    file: unit_tests/build_orchestration/test_tq500f3ii_heavy_lane_gate_subcommand.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      heavy_lane_gate --ticket <nonexistent path> with red new tests returns
      gate_passed true, recorded false and a non-empty record_error, and writes
      no file.
    framework: pytest
    type: integration
    angle: failure
  - name: test_both_twins_gate_command_carries_ticket_flag
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      For build-feature.js and build-ticket.js, the captured red-baseline-gate
      command contains "--ticket <the worktree ticket path>", and the fast-lane
      verify_red_baseline command is unchanged.
    framework: pytest
    type: integration
    angle: seam
  - name: test_green_at_baseline_halt_lists_tests_and_suggests_not_needed
    file: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
    covers:
      - TQ-500f-3-ii
    asserts: >-
      Both twins, with a stubbed gate verdict of gate_passed false and reason
      all_new_tests_green_at_baseline listing two green tests: the ticket halts
      before python-coder with classification green_at_baseline, the halt
      message names both tests and tells the user to set the coder phase
      not_needed with a comment naming the implementing commit, and the
      ticket's agents map still reads python-coder needed.
    framework: pytest
    type: integration
    angle: criterion
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_gate_pass_writes_record_accepted_by_real_guards | | |
| AC-2 | test_rerun_after_coding_reuses_record_without_pytest | | |
| AC-3 | test_renamed_recorded_red_test_runs_reader_and_fails, test_different_source_ac_runs_reader, test_test_writer_claim_without_record_runs_reader | | |
| AC-4 | test_missing_ticket_passes_with_recorded_false | | |
| AC-5 | test_both_twins_gate_command_carries_ticket_flag, seam test in test_tq500f3ii_heavy_lane_red_baseline_gate.py | | |
| AC-6 | test_green_at_baseline_halt_lists_tests_and_suggests_not_needed | | |
| AC-7 | pr-reviewer reads the skill diff | | |

## Implementation Tasks

### architect-review
- [ ] Review the durable `red_baseline_gate` frontmatter field: its trust level matches sign-offs, and `head` and `recorded_at` support audit. Decide whether it needs an ADR. If yes, flip `requires_adr` to true and dispatch adr-author.

### test-writer
- [ ] Extend `test_tq500f3ii_heavy_lane_gate_subcommand.py` with the six reader tests, on the real git fixture `unit_tests/build_orchestration/_tq500f3i_fixtures.py`.
- [ ] Add the two driver tests to `unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py`.
- [ ] In `test_tq500f3ii_heavy_lane_red_baseline_gate.py`, add the new keys (`reused`, `recorded`, `record_error`, and any halt-classification key) to the seam test's `wrapper_only_keys` (line 309).

### python-coder
- [ ] `_fl_heavy_lane_gate.py` (38-77): add record write, reuse check, `recorded`/`record_error`, and the `green_at_baseline` classification with the green-test list and the remedy text.
- [ ] `_fl_cli.py` (128-130): add `--ticket`. `fast_lane.py` (485-493): pass it through.
- [ ] Add a helper that computes the newly-added covers-tagged partition without running pytest (`_scan_test_root_for_covers_tags` + `_partition_newly_added`).
- [ ] Both twins:
  - append `--ticket` to the gate line (build-feature.js:2114-2116 `${worktreeTicketPath}`; build-ticket.js:1750-1752 `${ticketPath}`);
  - make the halt return echo the verdict's classification and remedy (2135-2141 / 1771-1777);
  - pay back every changed line.
- [ ] Run `python scripts/build.py` and stage the tracked outputs.

### documentation-expert
- [ ] `templates/skills/ticket-authoring/SKILL.md`: add `red_baseline_gate` to the frontmatter field table. It is written only by the gate; authors and agents must not write or edit it; describe what it holds and when it is reused.

### test-runner / pr-reviewer / commit
- [ ] Run all `test_tq500f3ii_*` and `test_tq500f3i*` suites and the fast-lane workflow tests. pr-reviewer checks twin parity, lane parity and check-file-size.

## Risk & Safety

- Touches money? No.
- Touches data? Writes one frontmatter line into the ticket being built, with an anchored atomic write.
- A hand-edited record could forge a pass. That is the same trust level as sign-offs; `head` and `recorded_at` support audit.
- The gate's executor is status-checker, which has `permits_shell: false` (known issue KI-BO-20260927). This ticket does not change that.
- Sequenced after ticket 01, which changes the same command line and module.
- Reversibility: revert the commit. Tickets that already carry a record keep a harmless unknown key.

## Out of Scope

- Option C (the reader checks red at the implementing commit's parent).
- Any automatic pass for green-at-baseline tests.
- Changing the gate's executor agent (KI-BO-20260927).

## Comments

_(Append-only log — leave blank when authoring.)_
