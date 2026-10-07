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
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: signed_off
  test-runner: signed_off
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
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
| AC-1 | test_independent_later_batch_ticket_is_built_after_halt, test_ticket_sharing_a_dirty_file_is_withheld | | ok — 2026-10-07 |
| AC-2 | test_dependant_of_halted_ticket_is_withheld_and_names_it, test_ticket_sharing_a_dirty_file_is_withheld | | ok — 2026-10-07 |
| AC-3 | test_staged_leftovers_stop_the_run_and_name_paths, test_unreadable_dirty_facts_stop_the_run, test_dirty_subcommand_reports_staged_unstaged_untracked, test_dirty_subcommand_outside_a_repo_reports_unreadable | | ok — 2026-10-07 |
| AC-4 | test_halted_ticket_is_not_redriven_in_a_later_look | | ok — 2026-10-07 |
| AC-5 | test_final_return_carries_halt_fields_and_epic_incomplete, test_all_work_behind_failed_prerequisite_ends_without_claiming_done | | ok — 2026-10-07 |
| AC-6 | test_ticket_sharing_a_dirty_file_is_withheld (files_touched read back) | | ok — 2026-10-07 |
| AC-7 | pr-reviewer reads the three doc diffs | | ok — 2026-10-07 |

## Implementation Tasks

### architect-review
- [x] Review the single-final-return shape (`halted_tickets`, `unbuilt`, `ended_because`, `halted_at_batch`) and confirm that every consumer of the old halted return still reads what it needs. Confirm the contamination guard and the fail-closed read.

### test-writer
- [x] Add a dirty-facts label to the harness (`harness_build_ticket_guard.mjs`), answering from the scenario. A missing scenario value must not read as clean.
- [x] Write `unit_tests/workflows/test_bo_100e_4_continue_past_halt.py` (driver harness `epic_scenario`) and `unit_tests/workflows/test_bo_100e_4_dirty_facts.py` (real git).
- [x] Update fixtures whose premise changes:
  - `unit_tests/prompt_assembly/test_unbuilt_work_count.py`: its 19 "batch 3, which the halt never reaches" tickets must now depend on the failing ticket, so BO-300d-1's count of 20 still holds;
  - re-check `test_epic_removed_work_verdict.py:351-373`, `test_epic_outcome_value_agreement.py:279` and `unit_tests/workflows/test_bo3900c_unrecognised_path_refusal.py:50`;
  - fix the stale premise in `unit_tests/workflows/test_bo_100e_1_i.py`'s docstring (15-30).

  Apply the test-file ratchet.

### python-coder
- [x] `templates/scripts/worktree_repo_facts.py`: add the `dirty` subcommand.
- [x] `build-feature.js`:
  - merge the halted return into the final return;
  - add the dirty-facts read after a halt, the staged-leftovers stop, the `withheld_by_shared_files` overlap check in the eligibility step, and the `hasOwnProperty` dedupe at 3133.
- [x] Both twins: add the optional `files_touched` to `RECORD_READBACK_SCHEMA` and the read-back prompt.
- [x] Run `python scripts/build.py` and stage the tracked outputs.

### llm-expert
- [x] `templates/skills/building-epics/SKILL.md` §1.3 / §6.2: state that the driver now continues past a halted ticket, withholds dependants and tickets sharing leftover-modified files, and stops on staged leftovers or an unreadable worktree state.
- [x] `templates/skills/build-feature-ops-notes/SKILL.md`: say how to read `unbuilt`, `withheld_by`, `withheld_by_shared_files` and the staged-leftovers stop, and how to recover.

### documentation-expert
- [x] `docs/architecture/components/build-epic-workflow-dispatch.md`:
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

### 2026-10-06 15:37 — architect-review (status: ok)

feedback-id: (submit-failed)

**Classification: large (judgment; no always-large trigger fires).** 15 files, 2 components (build_orchestration, supervisor_system), the workflow's return contract changes, and this is the largest ticket in the epic. Reviewed against HEAD 119fca8e2 by reading the code directly (no research-agent fan-out; the surface is two files plus one helper). requires_adr stays false (see decisions). Line numbers below are build-feature.js at HEAD and will shift once tickets 01-03 land.

**Findings (build-feature.js)**
1. The run stops in THREE returns, not one. (a) The halted return, 3507-3662, guarded by `haltedTickets.length > 0 || withheldResults.length > 0`. (b) The incomplete-member return, about 3664-3725 (a ticket ran, was not `ticket_completed`, but was not halted; `ended_because: "halted"`, `incomplete_tickets`). (c) The final return, 3744-3796. The ticket text only names (a). Fold (b) into the same continue path, or the run still stops at the first unconfirmed ticket and AC-1 is not met. Keep the `incomplete_tickets` key in the final return (test_empty_needed_phase_set_completion.py:111 reads `incomplete_tickets` or `halted_tickets`).
2. The guard fires on a WITHHELD ticket alone, not only on a halt, so a withheld dependant ends the run today. Under the new flow withheld and halted are both accumulated and the loop continues. `unbuiltSummary` is built per batch today; it must become a run-level accumulator.
3. The accounting in the halted return (`cmpForHalt`, `notYetAttemptedPaths`, `unbuiltNamedPaths`, `unbuiltCount`, the message) should run once at the end over run-level accumulators, not be duplicated. Today the BO-400e-2 block (`succeededInBatch`) pushes a batch's successes into `completedBatches` only inside the halted branch, and the bottom `completedBatches.push` (about 3818) records the batch otherwise. With the halted branch no longer returning, record each batch exactly once (successes only), or the batch is double-counted.
4. Dirty read. `repoFactsCall` (1614) dispatches `agentType: "status-checker"`; status-checker has Bash, and the helper already carries the other `worktree_repo_facts.py` subcommands (calls at 1624-1639). It returns null on a non-zero exit or unparseable output, which is the fail-closed marker needed. Caveats: (i) `phase: "Resolve Target"` is hard-coded in `repoFactsCall`; accept the mislabel (a new parameter costs lines). (ii) `realWorktreePath` can be null; treat that as unreadable and stop. (iii) The driver must require `readable === true` and array-typed `staged`/`unstaged`/`untracked`; null, a missing key or a non-array stops the run, and a missing key is never read as an empty list. (iv) Use label `worktree-dirty`. Ticket 05's F5 swap only touches guardrail cells and does not affect this dispatch.
5. Dirty semantics. Read once per batch that contains a halted or incomplete ticket (after the whole batch has settled, not once per ticket). Staged non-empty on any read: stop and name the staged paths (add a field such as `staged_leftovers: [paths]`; keep `ended_because: "halted"`). Otherwise REPLACE the run-level leftover set with `unstaged + untracked` from that read (dirty state is whole-worktree: replace, do not union). Use `git status --porcelain -uall` so untracked directories expand to files, and handle rename entries (`R  old -> new`) and path normalisation in Python, not JS. H's own ticket-file and sign-off edits will show as dirty; harmless, since no `files_touched` lists a ticket file.
6. Overlap check. The candidate's `files_touched` is available cheaply: `dependencyRecord = await readTicketRecordBack(...)` (3352ff) runs per ticket before the prerequisite loop, so the optional `files_touched` in RECORD_READBACK_SCHEMA (185-231) plus the prompt (1270ff) gives it. Intersect in JS against the run-level leftover set (a few lines). Same-batch siblings are never overlap-withheld (the planner already separates tickets sharing files), so `withheld_by_shared_files` only fires on a later batch or look. A read-back with no `files_touched` means no overlap is detectable; say so in the ops notes rather than treating it as failure.
7. Dedupe at 3133: change `=== true` to `Object.prototype.hasOwnProperty.call(completedTicketOutcomes, normalized)`. Withheld tickets are also written into `completedTicketOutcomes` as `false` (3473/3486; `r.result` is null), so a withheld ticket is never re-evaluated in a later look either. Acceptable (leftovers persist, so the verdict would not change); document it in the ops notes. The planner prompt only receives the true-set (`completedBeforeThisLook`), so it re-offers H every look; this dedupe is what bounds the looks (BO-100e-2). Confirm the terminating-look `break` treats "offered but all deduped" as nothing new.
8. Final return. `status: epicOutcomeStatus(finalRecheck)` (about 3752) derives from the recheck only. With any halt it must be forced to "blocked" with `epic_complete: false` (test_epic_outcome_value_agreement requires the outcome value never to read success when the completion verdict is withheld). The message, BO-300d-1 count line and `suggested_action` move from the old halted return. `halted_at_batch` is the first halt only. `ended_because` is "halted" with any halt or any stop for staged/unreadable state, and stays "no_further_work_eligible" otherwise.
9. Interaction with ticket 02 (handoff continues the ticket). 02 changes the per-ticket drive (`driveTicketPhases`, build-ticket.js and the twin); the repeated-pair and loop-cap halts it keeps still arrive here as ordinary `halt/blocked` results, and 04 does not edit `driveTicketPhases`, so there is no logic overlap. The conflict risk is textual: RECORD_READBACK_SCHEMA and the read-back prompt, which 02 (handoff target confirmation) and 03 (the reader recording its own pass) may also edit. Land 04 last and rebase on those hunks. A ticket that now continues past a handoff runs more phases before halting, so it is more likely to leave staged changes; the F4 stop matters more, not less. No contradiction with the design.
10. build-epic.js is not changed and diverges: templates/workflows-js/build-epic.js:480-504 still halts the whole run at the first halt. The documentation target build-epic-workflow-dispatch.md actually describes build-epic.js (title, mermaid, line 85), while the live epic driver is build-feature.js. See the diagram decision.

**Existing tests: what changes, what stays**
- Scripted `reads` (planner/recheck replies) assume a halt returns after one planner look and one recheck. After the change a halt is followed by another planner look (terminating, `{"batches": [], ...}` as in scenario_nothing_missing) and then the final recheck. Every halted fixture in these files needs an extra terminating-look read: mechanical, not semantic.
- Must change: test_unbuilt_work_count.py (`drive_multi_batch_halt`: batch-3 tickets are independent today and must depend on the failing ticket so the count of 20 holds; docstrings at 24-36, 185, 249-258, 346). test_bo_100e_1_i.py docstring 15-30 (stale premise); its withhold-by-prerequisite tests (147-251) must pass unchanged and keep pinning the `completedTicketOutcomes` gate.
- Must stay: test_epic_removed_work_verdict.py `site: "halted"` cases (351-373 want `halted_at_batch` on the payload; keep it; only the extra read changes). test_epic_outcome_value_agreement.py:279 (same check). BO-300a-5 and BO-300d-1: the count equals the named set; removed-work and discovered-after-planning partitions unchanged. test_bo3900c_unrecognised_path_refusal.py:50 reads `halted_tickets`; an unrecognised-path refusal is a `blocked` outcome and must stay in `halted_tickets`. Those tests must not start failing on the dirty read, so the harness needs an explicit clean default for scenarios that declare no dirty facts.
- Harness: for the NEW tests, an absent dirty value must read as unreadable (never clean). For pre-existing halt fixtures, the default must keep their outcome. Resolve with one explicit scenario key (for example `dirty`), whose absence for legacy scenarios answers clean in the .mjs and whose explicit null marker answers unreadable. test-writer decides the exact form; both defaults must be tested.

**Diagram and ADR decisions**
- Diagram: yes. Update docs/architecture/components/build-epic-workflow-dispatch.md (agent_flow, L3-Component). It must show: after `batch_results`, a halt/withhold branch that accumulates halted, withheld and incomplete tickets; a decision `read dirty state once (worktree_repo_facts.py dirty, via status-checker)` with three exits: unreadable -> stop (reason named), staged non-empty -> stop (staged paths named), clean or unstaged/untracked only -> record leftovers and continue; the per-ticket eligibility step (dependants and shared-file overlap -> withheld, listed in `unbuilt`); the look dedupe (a ticket with a verdict is never re-driven); and one final return carrying halted/unbuilt/epic_complete false. Remove the `STOP — do not start next batch` node and the line-83 text. Because the doc is titled for `build-epic.js`, documentation-expert should rescope it to the live driver build-feature.js's epic loop (preferred; add build-feature.js to related_diagrams and note build-epic.js is the legacy halt-all variant), or state explicitly that the legacy script keeps halt-all. Do not leave the doc claiming both. Bump `last_updated`. suggested_diagrams: none new (existing file updated), so no next_diagram_seq run.
- ADR: not needed. No new cross-cutting policy; it implements the approved BO-100e / BO-100e-4 and user decision F4 inside one workflow, and ADR-030's E2 constraint is honoured because the body reads nothing itself (an agent runs the helper). requires_adr: false stands.

**File-size ratchet**
The measure excludes block comments and docstrings but counts blank lines and `//` comments; every changed line counts as added. It fits if built as designed. Lines out: the halted return (3507-3662) is about 155 lines (roughly 60 are `//` comments) and the incomplete-member return about 60; replace both with run-level accumulators plus the existing final return. Lines in: schema field and prompt clause about 3, dirty read and decision about 18, overlap check about 8, dedupe 1 changed, accumulators and final-return fields about 15. Net is clearly negative once the two old returns go. Do not convert saved lines into long `//` blocks. build-ticket.js: the schema field and prompt clause add about 3 lines, which must be paid inside build-ticket.js: trim the 10+ line comment blocks on `handoff_target` and `failed_phases` in its RECORD_READBACK_SCHEMA without losing the contract statements. worktree_repo_facts.py (182/400) has room. Over-limit test files: put new scenarios only in the two new test files, shorten docstrings in the three existing ones as they are edited, and do not touch `_driver_harness.py`; handle the dirty label in the .mjs (873/1000, stay under 1000).

**Acceptance adjustments**
- AC-1/AC-5: treat incomplete-member tickets as halts for continuation; keep the `incomplete_tickets` key. AC-5 also carries `staged_leftovers` (paths) when the run stopped for staged state and a reason string when it stopped for an unreadable state.
- AC-3: the dirty read happens once per batch containing a halt/incomplete ticket, after the batch settles; null, unparseable, non-array, missing-key and null-worktree-path all stop the run.
- AC-4: also assert a withheld ticket is not re-dispatched in a later look.
- AC-7: scope the architecture doc to the live driver (see diagram decision); ops notes also say a read-back without `files_touched` means no overlap detection, and that a same-batch parallel sibling's commit can sweep up H's staged files before the F4 check (pre-existing, out of scope).
- Run `python scripts/build.py` and stage every mirror it changes.

### 2026-10-07 07:45 — test-writer (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  tests_written_and_red_for_the_right_reason: true
  existing_tests_adjusted_mechanically_only: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "templates/scripts/worktree_repo_facts.py `dirty` subcommand, run as a real subprocess against a real temporary git repository"
    consuming_side: "templates/workflows-js/build-feature.js epic loop, executed under the driver harness (test_real_dirty_script_output_drives_the_epic_loop pipes the producer's real JSON into the real loop)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "build-feature.js top-level body (workflow dispatch with args target=<epic folder>) run through unit_tests/prompt_assembly/harness_build_ticket_guard.mjs; and `python templates/scripts/worktree_repo_facts.py dirty <repo>` as a CLI subprocess"
red_baseline:
  - test_name: test_independent_later_batch_ticket_is_built_after_halt
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: D was never dispatched; touched=['.../EPIC-Continue/01_a.md']"
  - test_name: test_dependant_of_halted_ticket_is_withheld_and_names_it
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: B missing from unbuilt: []"
  - test_name: test_ticket_sharing_a_dirty_file_is_withheld[unstaged]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: E missing from unbuilt: []"
  - test_name: test_ticket_sharing_a_dirty_file_is_withheld[untracked]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: E missing from unbuilt: []"
  - test_name: test_staged_leftovers_stop_the_run_and_name_paths
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: {\"completed_batches\": [], \"ended_because\": \"halted\", ... no staged_leftovers key}"
  - test_name: test_unreadable_dirty_facts_stop_the_run[builder_default_is_unreadable]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: the return never says the worktree state could not be read: {\"completed_batches\": [], \"ended_because\": \"halted\", ...}"
  - test_name: test_unreadable_dirty_facts_stop_the_run[null_marker]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: the return never says the worktree state could not be read: {...}"
  - test_name: test_unreadable_dirty_facts_stop_the_run[unparseable_text]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: the return never says the worktree state could not be read: {...}"
  - test_name: test_unreadable_dirty_facts_stop_the_run[readable_false]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: the return never says the worktree state could not be read: {...}"
  - test_name: test_unreadable_dirty_facts_stop_the_run[missing_untracked_key]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: the return never says the worktree state could not be read: {...}"
  - test_name: test_unreadable_dirty_facts_stop_the_run[staged_not_an_array]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: the return never says the worktree state could not be read: {...}"
  - test_name: test_unreadable_dirty_facts_stop_the_run[no_readable_flag]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: the return never says the worktree state could not be read: {...}"
  - test_name: test_absent_dirty_key_answers_clean_for_legacy_halt_fixtures
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: a scenario with no dirty key should read clean: {\"completed_batches\": [], \"ended_because\": \"halted\", ...}"
  - test_name: test_halted_ticket_is_not_redriven_in_a_later_look
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: expected one further, terminating look; got 1"
  - test_name: test_withheld_ticket_is_not_redispatched_or_rereported_in_a_later_look
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: [] (unbuilt is empty; B was never evaluated)"
  - test_name: test_final_return_carries_halt_fields_and_epic_incomplete
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: unbuilt: [] (expected [B])"
  - test_name: test_all_work_behind_failed_prerequisite_ends_without_claiming_done
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: unbuilt: [] (expected B and C)"
  - test_name: test_leftover_set_is_replaced_not_unioned_at_each_read
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: one read per batch that halted"
  - test_name: test_one_dirty_read_covers_every_halt_in_a_batch
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: 0 reads for one batch"
  - test_name: test_real_dirty_script_output_drives_the_epic_loop[staged]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: `dirty` failed: rc=2 ... argument command: invalid choice: 'dirty'"
  - test_name: test_real_dirty_script_output_drives_the_epic_loop[unstaged]
    file: unit_tests/workflows/test_bo_100e_4_continue_past_halt.py
    error: "AssertionError: `dirty` failed: rc=2 ... argument command: invalid choice: 'dirty'"
  - test_name: test_dirty_subcommand_reports_staged_unstaged_untracked
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 out='' err=\"... invalid choice: 'dirty'\""
  - test_name: test_dirty_subcommand_outside_a_repo_reports_unreadable
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."
  - test_name: test_dirty_subcommand_reports_a_clean_repository_as_readable_and_empty
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."
  - test_name: test_dirty_subcommand_expands_untracked_directories_to_files
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."
  - test_name: test_dirty_subcommand_names_the_new_path_of_a_staged_rename
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."
  - test_name: test_dirty_subcommand_reports_a_file_staged_and_then_modified_in_both_lists
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."
  - test_name: test_dirty_subcommand_reports_awkward_filenames_unquoted[my file.txt]
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."
  - test_name: test_dirty_subcommand_reports_awkward_filenames_unquoted[caf\xe9.txt]
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."
  - test_name: test_dirty_subcommand_is_read_only
    file: unit_tests/workflows/test_bo_100e_4_dirty_facts.py
    error: "AssertionError: `dirty` printed no JSON object: rc=2 ..."

Wrote 31 tests in two new files and left 30 red by assertion (0 errors); the 31st, `test_same_batch_sibling_sharing_the_leftover_file_is_not_withheld`, is `green_at_baseline (guard)` on purpose (a same-batch sibling runs before any leftover is known, so it must stay built and unreported; it is not in `red_baseline`).
- Harness: `harness_build_ticket_guard.mjs` (907/1000 measured) gained a `worktree-dirty` label answered from `scenario["dirty"]` (absent key = clean for every pre-existing halt fixture; `null` = unreadable; string = unparseable; object = verbatim; array = one answer per read), a `dirty_reads` observation, and `files_touched` in the read-back record. `_driver_harness.py` is untouched; the new file's `drive()` always writes the key, so a missing `dirty=` becomes `null`, i.e. unreadable, never clean.
- Existing tests, mechanical only (extra terminating-look read, batch-3 dependency, premise docstrings): `test_unbuilt_work_count.py` 467 -> 459 (batch-3 tickets now depend on the failing ticket; their stubs are declared so the gate can read them); `test_epic_removed_work_verdict.py` 715 -> 713 (two halted scenarios); `test_bo_100e_1_i.py` 383 (pair fixture + docstring). `test_epic_outcome_value_agreement.py` and `test_bo3900c_unrecognised_path_refusal.py` re-checked and left unchanged (no halted fixture / reads `halted_tickets`, which both stop and continue paths still fill). All pass against the CURRENT driver; they flip only where the ticket says so.
- Validation: I built throwaway prototypes of the new loop and of the `dirty` subcommand in the scratchpad (never in the repo) and confirmed all 31 new tests and every adjusted file pass against them, and that union / fail-open-on-missing-flag / `=== true` dedupe mutations each turn a named test red. The incomplete-member return (architect finding 1) cannot be reached through the harness (every exit now reports a failure status), so it has no test of its own; the `halted_tickets` / `incomplete_tickets` key is read by `test_empty_needed_phase_set_completion.py`, which is unchanged and passes.
- Contract the tests pin for python-coder: label `worktree-dirty`; command text contains `worktree_repo_facts.py dirty`; reply requires `readable === true` and array-typed `staged`/`unstaged`/`untracked`; unreadable stop says "could not be read" (or unreadable / cannot be read); staged stop sets `staged_leftovers: [paths]`; an overlapping ticket is withheld with `withheld_by_shared_files == [shared paths]` read from the record read-back's `files_touched`; the `dirty` subcommand prints one JSON object with `readable` and answers a non-repo as `readable: false` (exit 0), expands untracked directories, unquotes names, names a rename's new path, never mutates the index.

### 2026-10-07 09:30 — llm-expert (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true

- `templates/skills/building-epics/SKILL.md`: §1.3 gains a workflow-driver paragraph (continues past a halt, withholds dependants and shared-file tickets, stops only on staged leftovers or an unreadable worktree state, final return blocked / epic_complete false / halted_at_batch = first halt, build-epic.js legacy keeps halt-all); §6.2 gains two sentences naming the same two driver stops and the `unbuilt` reporting.
- `templates/skills/build-feature-ops-notes/SKILL.md`: new KI-9 after KI-8 covering how to read `halted_tickets`, `unbuilt`, `withheld_by`, `withheld_by_shared_files`, the no-`files_touched` caveat, replace-not-union leftovers, the staged-leftovers stop (commit or unstage, then re-run), the unreadable-state stop, and the no-re-drive / withheld-not-re-evaluated note.
- Tests: skill-pinning tests (tests/knowledge/test_native_skill.py, tests/test_skill_registry.py, unit_tests/test_check_skill_refs.py, test_build_ticket_workflow.py, test_bo_2200b_6.py, test_bo_2100a_3_phase_order_gates.py, test_implementation_notes_emission.py) pass under AC_ENFORCE_STRICT=1. The ticket has no `## Sign-offs` section, so there was no checkbox to tick.

### 2026-10-07 08:01 — architecture-diagram-author (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  diagram_created: true
  flight_level_correct: true
  cross_links_added:
    result: false
    reason: "The doc now has a prose Parent: link and Related links, but its parent supervisor-spawn-topology.md still has no children: entry for it. This gap was already there before this ticket. The installed .leafcutter hook copy resolves its root to .leafcutter/ and passes; the scripts/ copy reports ARCH-BIDIRECTIONAL."
    remediation: "In a follow-up ticket, add docs/architecture/components/build-epic-workflow-dispatch.md to children: of supervisor-spawn-topology.md. That file is outside this ticket's files_touched."

- The architect assigned the doc work to documentation-expert. architecture-diagram-author did it, so the `documentation-expert` row is set to `signed_off` and its task is ticked.
- `docs/architecture/components/build-epic-workflow-dispatch.md` (L3-Component, agent_flow; flight level and file name unchanged) is rescoped to the build-feature.js epic loop. build-epic.js is named as the legacy halt-all variant that /build-feature does not route to. Both .js files are listed under `related_code`, a validated path field; `related_diagrams` keeps only diagrams.
- The Epic Loop diagram covers:
  - the look dedupe: a ticket with any verdict is never re-driven;
  - accumulation of halted, incomplete and withheld tickets;
  - one dirty read per halted or incomplete batch, via `worktree_repo_facts.py dirty` through a status-checker repo-facts call, with three exits: unreadable stops the run, staged leftovers stop it and name the paths, otherwise the leftover set is REPLACED with unstaged + untracked;
  - one final return: blocked, epic_complete false, ended_because halted, halted_at_batch = first halt.
- A second diagram, the Eligibility Gate, shows the dependant withhold and the shared-file withhold. Both lists are computed for every candidate, and the ticket is withheld if either is non-empty. The Halt Handling text states that same-batch siblings are never overlap-withheld.
- Removed: the "STOP — do not start next batch" node, the halt-stops-the-outer-loop text and the stale "/build-feature routes to build-epic.js" note.
- Frontmatter: added `type: architecture` and `source_ticket`. Changed `status: accepted` (invalid) to `active` and `last_updated` to 2026-10-07.
- Checks: check_doc_frontmatter passes (it failed before this change), check_doc_length passes (200 body lines, limit 300) and check_mermaid_complexity passes (13 nodes / 17 edges and 8 / 8).
- The diagram was checked against python-coder's build-feature.js edits as they stood in the worktree at 08:03 and aligned with them:
  - a batch that only withheld work also marks the run halted;
  - an unreadable stop sets `dirty_state_unreadable`.

  pr-reviewer should re-confirm it against the final driver.

### 2026-10-07 08:08 — python-coder (status: ok)

feedback-id: (submit-failed)

Summary: the epic loop in build-feature.js now continues past a halted ticket. `worktree_repo_facts.py dirty` is new (`git status --porcelain -uall -z`, rename new-path, unquoted names, `readable:false` outside a repo; `_run_git` now decodes utf-8). The three returns (halted, incomplete-member, final) are merged into one continue path with run-level accumulators (`haltedAll`, `incompleteAll`, `unbuiltAll`, `firstHaltBatch`, `leftoverFiles`, `haltStop`); each batch is recorded once; one `worktree-dirty` read per halting or incomplete batch, fail closed (null / readable !== true / non-array / null worktree path), staged leftovers stop with `staged_leftovers`, otherwise the leftover set is replaced by unstaged + untracked; later candidates whose read-back `files_touched` meets the leftovers are withheld with `withheld_by_shared_files`; dedupe uses hasOwnProperty. Final return on any halt: `status: blocked`, `epic_complete: false`, `ended_because: halted`, `halted_at_batch` = first halt, `halted_tickets`, `incomplete_tickets`, `unbuilt`, BO-300d-1 count. `files_touched` added to RECORD_READBACK_SCHEMA and read-back prompt in both twins. build-epic.js unchanged. No tracked build mirrors exist for these files, so build.py was not needed. The doc-enforcer and complexity-reduction skills could not be invoked (no Skill tool in this run); new Python has a full docstring and the loop is straight-line.

Tests (strict, lfopen + lfposix): the ticket's file set 143 passed, 2 failed (both test_bo_3000a_3700_dispatch_defects handoff-target tests, identical on build-tooling-gate-record). Full unit_tests/workflows + prompt_assembly: 68 failing/erroring ids, an identical set to build-tooling-gate-record (diffed, empty). All 31 BO-100e-4 tests pass, including the guard.

Ratchet (check_file_size): build-feature.js 2784 -> 2643 (limit allows 2643, added 141); build-ticket.js 1470 -> 1460 (added 10); worktree_repo_facts.py 221/400.

## Escalation

Branch: none
Reason: no always-large trigger fired (no migration, hypertable, FastAPI or ADR contract change). Large by threshold (more than 5 files, 2 components, return-contract change), handled inline: one workflow loop plus one helper script; no Opus escalation needed.

```json
{"architectural_note":"see comment","acceptance_adjustments":["fold incomplete-member return into continue path","report staged_leftovers and unreadable reason","assert withheld tickets are not re-dispatched"],"escalation":"none","escalation_reason":"","suggested_adr":null,"suggested_diagrams":[]}
```


### 2026-10-07 10:05 — pr-reviewer (status: ok)

feedback-id: (submit-failed)

No high-confidence findings. Verdict: ok to commit (F4 option A held; node --check passes on both twins).

Medium:
- [M-1] templates/workflows-js/build-feature.js:~3470-3500 (chunk loop) vs ~3585 (dirty read): the dirty read and the staged-leftovers stop run only after the WHOLE batch settles. A batch over BATCH_SIZE (12) is run as sequential chunks, so a ticket that halts in chunk 1 and leaves staged files does not stop chunk 2 tickets, whose commit phase could commit those staged files. Pre-existing batch shape, and documented ("dirty read happens only after they have settled"), but it is the one path where F4 option A does not stop a later ticket before it runs.
- [M-2] build-feature.js:~3426: the shared-file check is an exact string match of files_touched against git paths, and a null/unreadable read-back or a reader that omits files_touched gives no overlap (documented as "not a failure"). Directory or glob entries and `./` forms never match. Fails open for overlap only; staged leftovers and unreadable dirty state still fail closed.

Low (not blocking):
- worktree_repo_facts.py worktree_dirty: a worktree-side rename/copy (` R`, intent-to-add) is not skipped as two fields; its old name is parsed as a bogus entry and lands in staged, which fails closed. `git status` may refresh index stat data; `--no-optional-locks` would make read-only literal.
- `_run_git` now decodes utf-8 with errors=replace (was locale encoding, strict). Newline translation is unchanged. Other subcommands only gain correct non-ASCII paths.
- KI-9 says a withheld ticket is not re-evaluated "because the leftovers persist", but the leftover set is replaced at later dirty reads, so a leftover can clear. Not re-driving is still the specified behaviour.

Checks done: halted ticket verdict is recorded false (also withheld ones), so dependants, including transitive ones, are withheld via prerequisite state; the dedupe uses hasOwnProperty so a halted ticket is not re-driven in a later look; a null reply, readable !== true, non-array lists or a null realWorktreePath all stop the run; the leftover set is replaced, not unioned; a withheld-only batch does no read, which is safe because withheld tickets never ran; one final return (status blocked, epic_complete false, ended_because halted, halted_at_batch = first halt); incomplete_tickets kept; BO-300d-1 count de-duplicated once from one named set; the `detail` key on incomplete tickets is now `error`, with no reader found in templates/, scripts/, tests/ or unit_tests/ (test_empty_needed_phase_set_completion.py:123 reads detail OR error OR message). The legacy build-epic.js keeps its own halted return and is untouched. Ratchet: build-feature.js -141 lines, build-ticket.js -10; every AC or requirement id removed from a comment is still present elsewhere in its file; no executable line joined. Twin schemas agree: both gained the same optional files_touched array. Docs (building-epics, KI-9, component doc) match the implemented behaviour.

### 2026-10-07 10:40 — test-runner (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "Full step-2 run (workflows + prompt_assembly + build_orchestration, -n auto, strict, lfopen + lfposix): 53 failed, 1300 passed, 4 xfailed, 43 errors. The baseline worktree build-tooling-gate-record gives 50 failed, 1271 passed, 43 errors. All 95 failing/erroring nodes are pre-existing or flake; 0 are attributable to this ticket."
    remediation: "None for this ticket. Pre-existing failures (93 nodes, identical in both worktrees: test_acd_2100*, test_inf_700a_5*, test_bo2400* errors, test_tq500f3* and others) belong to separate tickets."
  failure_report_structured: true

Counts:
- Step 1 (ticket file set, 7 files incl. test_bo_100e_4_continue_past_halt, test_bo_100e_4_dirty_facts, test_bo_100e_1_i, test_unbuilt_work_count, test_epic_removed_work_verdict, test_epic_outcome_value_agreement, test_bo3900c, test_empty_needed_phase_set_completion): 74 passed, 23 subtests passed, 0 failed.
- Step 2 here: 53 failed, 1300 passed, 4 xfailed, 43 errors (95 ids). Baseline: 50 failed, 1271 passed, 4 xfailed, 43 errors (93 ids).
- worktree_repo_facts references: all in unit_tests/workflows (covered by step 2); none in tests/.
- Split: attributable 0; pre-existing 93; flake 2 (test_tq500f3i_absence_red_refusal::TestGateFailClosed::test_red_baseline_gate_fails_when_any_declared_test_is_absence_only and test_tq500f3i_h1_kind_pairing_bug::TestH1aMixedDeclaredBatchWithBareAssert::test_h1a_declared_absence_plus_declared_bare_assert_in_one_batch; failed only here under -n auto, pass serially in both worktrees).
- Real check: `worktree_repo_facts.py dirty .` returned readable true with the 7 staged ticket files and empty unstaged/untracked; against a non-repo temp dir returned readable false with empty lists (exit 0).

### 2026-10-07 08:22 — commit (status: ok)

feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

Subject: fix(build-orchestration): continue an epic run past a halted ticket
