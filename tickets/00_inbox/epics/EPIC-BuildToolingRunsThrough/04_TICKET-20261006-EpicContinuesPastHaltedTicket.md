---
title: "An epic run continues past a halted ticket and withholds only the work behind it"
status: todo
components:
  - build_orchestration
  - supervisor_system
created: 2026-10-06
depends_on:
  - 02_TICKET-20261006-HandoffContinuesTheTicket.md
  - 03_TICKET-20261006-RedBaselineVerdictRecordedAndReused.md
priority: high
complexity: high
roadmap_phase: phase_1
advances_current_outcome: true
source_ac: BO-100e-4
ac_traceability:
  id: BO-100e-4
  path: docs/acceptance-criteria/build-orchestration/BO-100-smart-sequencing/BO-100e-4.yaml
requires_diagram: true
requires_adr: false
change_target:
  - pipeline
  - code
  - prompt
  - docs
risk_surface: contract_boundary
files_touched:
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/scripts/worktree_repo_facts.py
  - unit_tests/prompt_assembly/harness_build_ticket_guard.mjs
  - unit_tests/prompt_assembly/_driver_harness.py
  - unit_tests/workflows/test_bo_100e_4_continue_past_halt.py  # new
  - unit_tests/workflows/test_bo_100e_4_dirty_facts.py  # new
  - unit_tests/prompt_assembly/test_unbuilt_work_count.py
  - unit_tests/prompt_assembly/test_epic_removed_work_verdict.py
  - unit_tests/prompt_assembly/test_epic_outcome_value_agreement.py
  - unit_tests/workflows/test_bo3900c_unrecognised_path_refusal.py
  - unit_tests/workflows/test_bo_100e_1_i.py
  - docs/architecture/components/build-epic-workflow-dispatch.md
  - templates/skills/building-epics/SKILL.md
  - templates/skills/build-feature-ops-notes/SKILL.md
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  llm-expert: needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
---

# 04: An epic run continues past a halted ticket and withholds only the work behind it

## Actor / Goal

As the epic build driver, I want a halted ticket to cost only the work that depends
on it, or that shares a file it left modified. Then one failure no longer stops every
later batch, and a run keeps going until there is genuinely nothing further it can
build. It must still stop at once when the halted ticket left staged changes that the
next commit would sweep in.

## Context

Part of EPIC-BuildToolingRunsThrough (design section 1b, user decision F4 Option A).
Implements BO-100e-4, "One branch failing does not withhold the later layers of an
unrelated branch", under the approved L1 BO-100e, together with building-epics §1.3
and §6.2.

**What the code does today**
- Siblings in the **same batch do finish**: every chunk of a batch runs through `parallel()` (`templates/workflows-js/build-feature.js:3297-3478`) before the halt check (3497).
- What stops is every **later batch and every later look**: the halted return (3507-3662, return at 3627-3661) ends the run.
- In the DK-400 E1 epic, almost every ticket shares `files_touched` entries (`decision-forming.flow.json`, ADR-053). The planner splits tickets that share files into separate batches (3011), so every ticket sat in its own batch, and one halt stopped everything.
- This contradicts:
  - building-epics §1.3 (`templates/skills/building-epics/SKILL.md:234`) and §6.2 (1089-1093);
  - the approved L1 BO-100e: "a run keeps going until there is genuinely nothing further it can build";
  - BO-100e-2-i's closing clause, which says the same for unsatisfiable prerequisites.

**Intended behaviour**
1. A halted ticket H costs only:
   - (i) its transitive dependants. The BO-100e-1-i gate already withholds them, because `completedTicketOutcomes[H]` is not true;
   - (ii) tickets whose `files_touched` intersect files H left modified in the worktree.
2. Contamination guard (F4 Option A). The commit agent commits whatever is staged and does not scope to the ticket's files (`templates/agents/commit.md:199-209`). So:
   - before continuing past a halt, read the worktree's dirty/staged state once;
   - if H left **staged** changes, stop the run as today and name the paths;
   - if the state cannot be read, stop (fail closed).
3. Never re-drive a ticket that already has a verdict in this run. The look dedupe at 3133 must test `hasOwnProperty`, not `=== true`. This keeps the number of looks bounded (BO-100e-2).
4. End with one final return carrying:
   - `halted_tickets`;
   - `unbuilt`: withheld tickets, each with `withheld_by` and/or `withheld_by_shared_files`;
   - `completed_batches`, including successes after the halt;
   - `ended_because: "halted"`, and `halted_at_batch` (the first halt, kept for compatibility);
   - the BO-300d-1 unbuilt count;
   - `epic_complete: false`.

**Minimal change (build-feature.js holds the epic loop; build-ticket.js has none)**
- Merge the halted return (3507-3662) into the single final return (3744-3796). This is net-negative in lines.
- Add an optional `files_touched` field to `RECORD_READBACK_SCHEMA` (`build-feature.js:185-231`, `build-ticket.js:196-235`) and to the read-back prompt (1270-1290), in both twins for schema parity.
- Add a file-overlap check in the eligibility step (3352-3417).
- Add a `dirty` subcommand to `templates/scripts/worktree_repo_facts.py`. It runs `git status --porcelain` and returns `{staged, unstaged, untracked}` (or an unreadable marker). Call it through `repoFactsCall` (1614).

## Constraints

- **Twins.** The read-back schema and prompt change in both `build-feature.js` and `build-ticket.js`, in the same commit. Only build-feature.js gets the epic-loop changes.
- **File-size ratchet (GE-127b-1, GE-127f-2).** `build-feature.js` measures 2964 / 1000 and `build-ticket.js` 1647 / 1000.
  - Each staged file may measure at most `previous − gross measured lines added`, and a changed line counts as added.
  - Merging the halted return into the final return must shrink build-feature.js by at least the lines added for the overlap check, the dirty-facts call and the schema field.
  - build-ticket.js's schema field must be paid back inside build-ticket.js.
  - Put set and overlap logic in Python (`worktree_repo_facts.py`, measured 182 / 400) wherever it can be.
- **Test-file ratchet.** These are already over 400, so any edit must leave them shorter by at least the lines it adds or changes:
  - `test_unbuilt_work_count.py` (467);
  - `test_epic_removed_work_verdict.py` (715);
  - `test_epic_outcome_value_agreement.py` (452);
  - `_driver_harness.py` (542). Prefer passing the dirty facts through the existing scenario dictionary so that `_driver_harness.py` does not change.

  `harness_build_ticket_guard.mjs` measures 873 / 1000 and must stay at or below 1000.
- **Build mirrors.** After the template edits, run `python scripts/build.py` and stage every tracked output it changes.
- **Lane parity (TQ-500f-3-ii).** The red-baseline gate is unchanged. A ticket built after a halt still passes through the same gate.

## Acceptance Criteria

- [ ] AC-1: When a ticket H halts, the run does not end. Later batches and looks still build every ticket that neither depends on H (transitively) nor lists in `files_touched` a file H left modified in the worktree.
- [ ] AC-2: H's transitive dependants, and tickets whose `files_touched` intersect H's leftover modified files, are not built. Each appears in `unbuilt` with `withheld_by` (naming H) or `withheld_by_shared_files` (naming the shared paths).
- [ ] AC-3: Before continuing past a halt, the driver reads the worktree's dirty state once, through `worktree_repo_facts.py dirty`. If H left staged changes, the run stops and names the staged paths. If the state cannot be read, the run stops.
- [ ] AC-4: A ticket that already has a verdict in this run, success or halt, is never driven again in a later look (`hasOwnProperty` dedupe).
- [ ] AC-5: The run ends with one final return carrying `halted_tickets`, `unbuilt`, `completed_batches` (including successes after the halt), `ended_because: "halted"`, `halted_at_batch` (the first halt), the BO-300d-1 unbuilt count and `epic_complete: false`. When every remaining ticket is behind the failure, the run ends without reporting the work finished.
- [ ] AC-6: `RECORD_READBACK_SCHEMA` and the read-back prompt carry an optional `files_touched` in both twins. build-ticket.js gains no epic loop.
- [ ] AC-7: Three documents describe the continuation, the staged-leftovers stop and the withheld reporting:
  - `docs/architecture/components/build-epic-workflow-dispatch.md`, whose agent_flow diagram no longer says "STOP — do not start next batch";
  - `templates/skills/building-epics/SKILL.md`;
  - `templates/skills/build-feature-ops-notes/SKILL.md`.

## Test Requirements

```yaml
tests:
  - name: test_independent_later_batch_ticket_is_built_after_halt
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
    asserts: >-
      build-feature.js with an epic_scenario of two chains, A->B and C->D, each
      ticket in its own batch, A halting and the dirty facts clean: D is
      dispatched and completed in the same run, B is never dispatched, and the
      run does not return at A's batch.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_dependant_of_halted_ticket_is_withheld_and_names_it
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
    asserts: >-
      Same scenario: the final return lists B in unbuilt with withheld_by naming
      A, and C and D in completed_batches. The unbuilt set is exactly the work
      behind A and nothing else.
    framework: pytest
    type: integration
    angle: criterion
  - name: test_ticket_sharing_a_dirty_file_is_withheld
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
    asserts: >-
      A halts leaving file X unstaged-modified (dirty facts: unstaged [X]).
      Ticket E, which has no dependency on A but lists X in files_touched, is
      not dispatched and appears in unbuilt with withheld_by_shared_files [X].
      An unrelated ticket F is built.
    framework: pytest
    type: integration
    angle: boundary
  - name: test_staged_leftovers_stop_the_run_and_name_paths
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
    asserts: >-
      A halts and the dirty facts report staged [Y]. The run ends after A's
      batch, no later ticket is dispatched, and the return names Y as staged
      leftovers.
    framework: pytest
    type: integration
    angle: failure
  - name: test_unreadable_dirty_facts_stop_the_run
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
    asserts: >-
      A halts and the dirty-facts reply is unparseable or unreadable. The run
      ends after A's batch with no later dispatch, and the return says the
      worktree state could not be read.
    framework: pytest
    type: integration
    angle: failure
  - name: test_halted_ticket_is_not_redriven_in_a_later_look
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
      - BO-100e-2
    asserts: >-
      The planner stub offers A again in look 2 after A halted in look 1. A's
      phase agents are dispatched in exactly one look, and the number of looks
      stays bounded (the run ends when a look releases nothing new).
    framework: pytest
    type: integration
    angle: boundary
  - name: test_final_return_carries_halt_fields_and_epic_incomplete
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
    asserts: >-
      The run's single final return has halted_tickets [A], unbuilt,
      completed_batches including the post-halt C and D batches, ended_because
      "halted", halted_at_batch equal to A's batch index, the BO-300d-1
      unbuilt count, and epic_complete false.
    framework: pytest
    type: integration
    angle: seam
  - name: test_all_work_behind_failed_prerequisite_ends_without_claiming_done
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    covers:
      - BO-100e-4
    asserts: >-
      Every other ticket depends on A, and A halts. No other ticket is
      dispatched, the run ends, and the return has epic_complete false and
      ended_because "halted". It never reports the work finished.
    framework: pytest
    type: integration
    angle: failure
  - name: test_dirty_subcommand_reports_staged_unstaged_untracked
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    covers:
      - BO-100e-4
    asserts: >-
      In a real temporary git repository with one staged, one unstaged-modified
      and one untracked file, "python worktree_repo_facts.py dirty <repo>"
      exits 0 and prints JSON whose staged, unstaged and untracked lists name
      exactly those three paths.
    framework: pytest
    type: integration
    angle: real_artifact
  - name: test_dirty_subcommand_outside_a_repo_reports_unreadable
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    covers:
      - BO-100e-4
    asserts: >-
      "worktree_repo_facts.py dirty <a non-git temp dir>" never reports clean
      lists. It reports the state as unreadable, so the driver fails closed.
    framework: pytest
    type: integration
    angle: failure
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_independent_later_batch_ticket_is_built_after_halt, test_ticket_sharing_a_dirty_file_is_withheld | | |
| AC-2 | test_dependant_of_halted_ticket_is_withheld_and_names_it, test_ticket_sharing_a_dirty_file_is_withheld | | |
| AC-3 | test_staged_leftovers_stop_the_run_and_name_paths, test_unreadable_dirty_facts_stop_the_run, test_dirty_subcommand_reports_staged_unstaged_untracked, test_dirty_subcommand_outside_a_repo_reports_unreadable | | |
| AC-4 | test_halted_ticket_is_not_redriven_in_a_later_look | | |
| AC-5 | test_final_return_carries_halt_fields_and_epic_incomplete, test_all_work_behind_failed_prerequisite_ends_without_claiming_done | | |
| AC-6 | test_ticket_sharing_a_dirty_file_is_withheld (files_touched read back) | | |
| AC-7 | pr-reviewer reads the three doc diffs | | |

## Implementation Tasks

### architect-review
- [ ] Review the single-final-return shape (`halted_tickets`, `unbuilt`, `ended_because`, `halted_at_batch`) and confirm that every consumer of the old halted return still reads what it needs. Confirm the contamination guard and the fail-closed read.

### test-writer
- [ ] Add a dirty-facts label to the harness (`harness_build_ticket_guard.mjs`), answering from the scenario. A missing scenario value must not read as clean.
- [ ] Write `unit_tests/workflows/test_bo_100e_4_continue_past_halt.py` (driver harness `epic_scenario`) and `unit_tests/workflows/test_bo_100e_4_dirty_facts.py` (real git).
- [ ] Update fixtures whose premise changes:
  - `unit_tests/prompt_assembly/test_unbuilt_work_count.py`: its 19 "batch 3, which the halt never reaches" tickets must now depend on the failing ticket, so BO-300d-1's count of 20 still holds;
  - re-check `test_epic_removed_work_verdict.py:351-373`, `test_epic_outcome_value_agreement.py:279` and `unit_tests/workflows/test_bo3900c_unrecognised_path_refusal.py:50`;
  - fix the stale premise in `unit_tests/workflows/test_bo_100e_1_i.py`'s docstring (15-30).

  Apply the test-file ratchet.

### python-coder
- [ ] `templates/scripts/worktree_repo_facts.py`: add the `dirty` subcommand.
- [ ] `build-feature.js`:
  - merge the halted return into the final return;
  - add the dirty-facts read after a halt, the staged-leftovers stop, the `withheld_by_shared_files` overlap check in the eligibility step, and the `hasOwnProperty` dedupe at 3133.
- [ ] Both twins: add the optional `files_touched` to `RECORD_READBACK_SCHEMA` and the read-back prompt.
- [ ] Run `python scripts/build.py` and stage the tracked outputs.

### llm-expert
- [ ] `templates/skills/building-epics/SKILL.md` §1.3 / §6.2: state that the driver now continues past a halted ticket, withholds dependants and tickets sharing leftover-modified files, and stops on staged leftovers or an unreadable worktree state.
- [ ] `templates/skills/build-feature-ops-notes/SKILL.md`: say how to read `unbuilt`, `withheld_by`, `withheld_by_shared_files` and the staged-leftovers stop, and how to recover.

### documentation-expert
- [ ] `docs/architecture/components/build-epic-workflow-dispatch.md`:
  - update the agent_flow mermaid diagram and the "A halt from any ticket in a batch stops the outer loop immediately" text (line 83) to the continue-and-withhold flow, including the staged-leftovers stop;
  - bump `last_updated`.

### test-runner / pr-reviewer / commit
- [ ] Run `unit_tests/workflows/test_bo_100e*`, `unit_tests/prompt_assembly/test_unbuilt_work_count.py`, `test_epic_*`, `test_bo_400e_*` and `test_bo3900c_*`. pr-reviewer checks check-file-size on every touched file.

## Risk & Safety

- Touches money? No.
- Touches data? Reads `git status` only. It never stages or un-stages anything (F4 Option A).
- H's unstaged edits stay in the worktree and can disturb a later ticket's tests. That fails closed: as a test failure, never as a contaminated commit, because staged leftovers stop the run.
- This is the largest change in the epic, so it lands after tickets 02 and 03.
- Reversibility: revert the commit. The run then stops at the first halt again.

## Out of Scope

- Un-staging a halted ticket's changes and recording that on the ticket (F4 Option B, rejected).
- BO-100e-5, the sequence diagram of the repeated eligibility look.
- Any epic loop in build-ticket.js.

## Comments

_(Append-only log — leave blank when authoring.)_
