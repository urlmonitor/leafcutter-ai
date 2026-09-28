---
title: 'Finding and clearing a workspace: definite locate, complete remove, authorised loss only'
status: todo
components:
- worktree_manager
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 07_TICKET-20260928-BO-4300-safe-re-request.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
source_ac: BO-4300e-2
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300e-1
  - BO-4300e-2
  - BO-4300e-3
  l3:
  - BO-4300e-1-i
  - BO-4300e-2-i
  - BO-4300e-2-ii
  - BO-4300e-3-i
ac_coverage: 0/7
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_admin.py
- templates/scripts/worktree_remove.py
- scripts/worktree/sweep_processes.py
- scripts/build_phases_script_deploy.py
- tests/test_sweep_processes.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
- unit_tests/build_orchestration/test_bo_4300e_1.py
- unit_tests/build_orchestration/test_bo_4300e_1_i.py
- unit_tests/build_orchestration/test_bo_4300e_2.py
- unit_tests/build_orchestration/test_bo_4300e_2_i.py
- unit_tests/build_orchestration/test_bo_4300e_2_ii.py
- unit_tests/build_orchestration/test_bo_4300e_3.py
- unit_tests/build_orchestration/test_bo_4300e_3_i.py
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  architect-review: needed
  commit: needed
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
---

# 08: Finding and clearing a workspace: definite locate, complete remove, authorised loss only

## Actor / Goal

In order that workflows can trust a location and clear workspaces unattended, we need locate/verify that answer definitely and read-only, and a remove that clears everything or nothing and never loses unsent work unless authorised up front, so that finalize and cleanup can never stall or silently destroy work.

## Context

e-1 delivers the locate/verify answers BO-4300c-4-i (ticket 11) confirms a handed-in location with; e-2 delivers the remove that BO-4300e-4 (ticket 11) and the cut-over (ticket 12) use. In the failed run 43, 45, 46 and 48 edited `worktree_admin.py` in parallel.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 7 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300e-1-i | L3 | Looking a workspace up never creates or changes one | BO-4300e-1 | this ticket |
| AC-2 | BO-4300e-1 | L2 | Asking where a piece of work's workspace is gets a definite answer from the same maker | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-3 | BO-4300e-2-i | L3 | A workspace with very long file paths on Windows is cleared completely | BO-4300e-2 | this ticket |
| AC-4 | BO-4300e-2-ii | L3 | A workspace with a program still running inside it is never left half-cleared | BO-4300e-2 | this ticket |
| AC-5 | BO-4300e-2 | L2 | Clearing a workspace answers at once and never waits for someone to say yes | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-6 | BO-4300e-3-i | L3 | A discard token clears only the workspace and the unsent work it was issued for | BO-4300e-3 | this ticket |
| AC-7 | BO-4300e-3 | L2 | Loss of unsent work happens only when authorised up front | BO-4300e-2 | this ticket |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300e-1`, `BO-4300e-2`, `BO-4300e-3` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300e-2`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300e-1-i (L3) -- Looking a workspace up never creates or changes one

```gherkin
Given no workspace exists for "gamma", and a half-made workspace exists for
  "delta",
When "gamma" and "delta" are looked up,
Then no workspace for "gamma" exists afterwards,
And "delta" is reported as incomplete, not as ready,
And "delta"'s files are identical before and after the lookup.
```

### AC-2: BO-4300e-1 (L2) -- Asking where a piece of work's workspace is gets a definite answer from the same maker

```gherkin
Given a project with ready workspaces for "alpha", "alpha-v2" and "beta", none
  for "gamma", and version control's own list of linked workspaces for the
  project empty,
When "alpha", "beta" and "gamma" are each looked up through the workspace
  maker, from the project's top folder and from the folder above it,
Then "alpha" and "beta" are each answered with their own location, the same
  from both starting folders,
And "gamma" is answered with a definite statement that no workspace exists for
  it,
And the lookup of "alpha" never returns the location of "alpha-v2".
```

### AC-3: BO-4300e-2-i (L3) -- A workspace with very long file paths on Windows is cleared completely

```gherkin
Given a Windows machine, and a workspace holding nothing unsent whose contents
  include a file path longer than 260 characters,
When the workspace is cleared,
Then the answer states it was cleared,
And no folder or file of it remains at its location.
```

### AC-4: BO-4300e-2-ii (L3) -- A workspace with a program still running inside it is never left half-cleared

```gherkin
Given a workspace holding nothing unsent, in which a program started from the
  workspace is still running and holding files open,
When the workspace is cleared,
Then either the program is stopped and no part of the workspace remains, or
  the request is refused naming the program and the workspace is identical
  before and after,
And the answer never states the workspace was cleared while any part of it
  remains.
```

### AC-5: BO-4300e-2 (L2) -- Clearing a workspace answers at once and never waits for someone to say yes

```gherkin
Given an unattended run, with no person available to answer questions, asks the
  workspace maker to clear two workspaces: "alpha", holding nothing that has
  not reached the shared project, and "beta", holding one unpushed commit and
  one uncommitted change, with no authorisation to lose work given,
When each clearing request is made,
Then each request ends with an answer without waiting for any input,
And "alpha" is gone completely,
And "beta" is refused, and the refusal names the unpushed commit by identifier
  and the uncommitted file by path,
And "beta"'s files and commits are identical before and after.
```

### AC-6: BO-4300e-3-i (L3) -- A discard token clears only the workspace and the unsent work it was issued for

```gherkin
Given an unattended clean-up clears "alpha" and "beta", both holding unsent
  work, and holds the one-time token returned by the refusal to clear "alpha",
When clearing "beta" is requested with alpha's token, and clearing "alpha" is
  requested with its own token,
Then "alpha" is gone,
And "beta" is refused, and its files and commits are identical before and after.

Given a request to clear "gamma" was refused with a one-time token,
And one more commit is then made in "gamma",
When clearing "gamma" is requested with that token,
Then the request is refused, listing both unsent commits,
And "gamma" is identical before and after.
```

### AC-7: BO-4300e-3 (L2) -- Loss of unsent work happens only when authorised up front

```gherkin
Given a workspace holding one unpushed commit and one uncommitted change,
And a request to clear it was refused, listing that commit and that file and
  returning a one-time token bound to that workspace and exactly that unsent
  work,
When clearing it is requested again with that token given in the request
  itself,
Then the workspace is gone completely, without any question being asked,
And the answer lists what was discarded: the unpushed commit by identifier and
  the uncommitted file by path,
And the line of work on the shared project and the shared main line are
  identical before and after.
```

- [ ] AC-1: BO-4300e-1-i -- Looking a workspace up never creates or changes one
- [ ] AC-2: BO-4300e-1 -- Asking where a piece of work's workspace is gets a definite answer from the same maker
- [ ] AC-3: BO-4300e-2-i -- A workspace with very long file paths on Windows is cleared completely
- [ ] AC-4: BO-4300e-2-ii -- A workspace with a program still running inside it is never left half-cleared
- [ ] AC-5: BO-4300e-2 -- Clearing a workspace answers at once and never waits for someone to say yes
- [ ] AC-6: BO-4300e-3-i -- A discard token clears only the workspace and the unsent work it was issued for
- [ ] AC-7: BO-4300e-3 -- Loss of unsent work happens only when authorised up front

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_lookup_of_absent_work_creates_nothing
  file: unit_tests/build_orchestration/test_bo_4300e_1_i.py
  covers:
  - BO-4300e-1-i
  asserts: After locating gamma, no gamma folder, lock or branch exists.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_half_made_workspace_is_reported_incomplete_not_ready
  file: unit_tests/build_orchestration/test_bo_4300e_1_i.py
  covers:
  - BO-4300e-1-i
  asserts: delta is answered INCOMPLETE with remnant_path and no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_lookup_leaves_half_made_workspace_byte_identical
  file: unit_tests/build_orchestration/test_bo_4300e_1_i.py
  covers:
  - BO-4300e-1-i
  asserts: delta's files (including .git) are identical before and after.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_locate_answers_each_ready_workspace_with_its_own_location_from_both_folders
  file: unit_tests/build_orchestration/test_bo_4300e_1.py
  covers:
  - BO-4300e-1
  asserts: alpha and beta are each answered ok with their own workspace_path, identical from the top folder
    and the parent folder, while git worktree list is empty.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_locate_of_absent_work_is_a_definite_not_found
  file: unit_tests/build_orchestration/test_bo_4300e_1.py
  covers:
  - BO-4300e-1
  asserts: gamma is answered refused, code NOT_FOUND, no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_locate_alpha_never_returns_alpha_v2
  file: unit_tests/build_orchestration/test_bo_4300e_1.py
  covers:
  - BO-4300e-1
  asserts: The answer for alpha names alpha's location, not alpha-v2's.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_workspace_with_path_over_260_chars_is_removed_completely
  file: unit_tests/build_orchestration/test_bo_4300e_2_i.py
  covers:
  - BO-4300e-2-i
  asserts: The answer is ok and nothing remains at the location.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_workspace_with_running_program_is_removed_fully_or_refused_untouched
  file: unit_tests/build_orchestration/test_bo_4300e_2_ii.py
  covers:
  - BO-4300e-2-ii
  asserts: With a child process holding a file open in the workspace, the result is either ok with nothing
    left, or PROCESS_HOLDS_FILES naming the process with the workspace identical.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_removed_is_never_claimed_while_any_part_remains
  file: unit_tests/build_orchestration/test_bo_4300e_2_ii.py
  covers:
  - BO-4300e-2-ii
  asserts: Whenever the answer is ok, the location does not exist.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_remove_answers_without_waiting_for_input
  file: unit_tests/build_orchestration/test_bo_4300e_2.py
  covers:
  - BO-4300e-2
  asserts: With stdin closed and a timeout, both remove requests return an answer.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_clean_workspace_is_removed_completely
  file: unit_tests/build_orchestration/test_bo_4300e_2.py
  covers:
  - BO-4300e-2
  asserts: alpha's folder no longer exists and the answer is ok with removed_path.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_workspace_with_unsent_work_is_refused_naming_commit_and_file
  file: unit_tests/build_orchestration/test_bo_4300e_2.py
  covers:
  - BO-4300e-2
  asserts: beta is refused UNSENT_WORK with unsent.commits containing the unpushed sha and unsent.files
    the uncommitted path.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_refused_workspace_is_unchanged
  file: unit_tests/build_orchestration/test_bo_4300e_2.py
  covers:
  - BO-4300e-2
  asserts: beta's files and commits are identical before and after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_authorisation_for_alpha_removes_alpha_only
  file: unit_tests/build_orchestration/test_bo_4300e_3_i.py
  covers:
  - BO-4300e-3-i
  asserts: alpha, requested with the token from its own refusal, is removed (ok, folder gone).
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_token_for_alpha_cannot_clear_beta
  file: unit_tests/build_orchestration/test_bo_4300e_3_i.py
  covers:
  - BO-4300e-3-i
  asserts: beta, requested with alpha's token, is refused UNSENT_WORK with its own lists and a different
    fresh token, and beta's files, commits and marker are byte-identical before and after.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_beta_without_its_own_authorisation_is_refused_and_unchanged
  file: unit_tests/build_orchestration/test_bo_4300e_3_i.py
  covers:
  - BO-4300e-3-i
  asserts: beta, requested next without a token, is UNSENT_WORK and byte-identical.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_token_is_invalid_after_a_new_commit
  file: unit_tests/build_orchestration/test_bo_4300e_3_i.py
  covers:
  - BO-4300e-3-i
  asserts: gamma refused with token T; one more commit is made in gamma; remove with T is refused UNSENT_WORK
    listing both shas, and gamma is byte-identical.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_token_is_invalid_after_an_uncommitted_file_is_edited
  file: unit_tests/build_orchestration/test_bo_4300e_3_i.py
  covers:
  - BO-4300e-3-i
  asserts: gamma refused with token T; the already-listed uncommitted file's content is edited (same path
    set); remove with T is refused and gamma is unchanged.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_token_for_a_remade_workspace_at_the_same_path_is_invalid
  file: unit_tests/build_orchestration/test_bo_4300e_3_i.py
  covers:
  - BO-4300e-3-i
  asserts: delta refused with token T, then delta is removed with T; delta is re-made at the same path
    with equivalent uncommitted content; remove with the old T is refused and the new workspace is unchanged.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_authorised_remove_deletes_without_any_question
  file: unit_tests/build_orchestration/test_bo_4300e_3.py
  covers:
  - BO-4300e-3
  asserts: With the discard_token from the preceding UNSENT_WORK refusal given as --discard-token and
    stdin closed, the folder is gone and the answer is ok.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_refusal_returns_a_discard_token_with_the_unsent_lists
  file: unit_tests/build_orchestration/test_bo_4300e_3.py
  covers:
  - BO-4300e-3
  asserts: remove without a token on the workspace is refused UNSENT_WORK (exit 2) listing the unpushed
    sha and the uncommitted path, carries a non-empty discard_token, and leaves the workspace byte-identical.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_token_is_not_taken_from_the_environment_or_config
  file: unit_tests/build_orchestration/test_bo_4300e_3.py
  covers:
  - BO-4300e-3
  asserts: With the valid token placed in environment variables and in the project's config, remove without
    --discard-token is refused UNSENT_WORK and the workspace is byte-identical.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_token_is_not_persisted_anywhere
  file: unit_tests/build_orchestration/test_bo_4300e_3.py
  covers:
  - BO-4300e-3
  asserts: After the refusal, the token string appears in no file under the test's temp directory (project,
    hub, landing root, workspace, isolated HOME) and not on stderr.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_answer_lists_discarded_commit_and_file
  file: unit_tests/build_orchestration/test_bo_4300e_3.py
  covers:
  - BO-4300e-3
  asserts: discarded.commits contains the unpushed sha and discarded.files the uncommitted path.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_hub_line_and_main_unchanged_by_authorised_remove
  file: unit_tests/build_orchestration/test_bo_4300e_3.py
  covers:
  - BO-4300e-3
  asserts: The hub's branch ref and main ref are identical before and after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
- name: test_ticket_08_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300e_1_i.py
  covers:
  - BO-4300e-2
  angle: reachability
  surface_invoked: python <install-root>/.leafcutter/scripts/worktree.py locate|verify|remove ... (CLI
    via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_remove.py
  - scripts/worktree/sweep_processes.py
  - scripts/build_phases_script_deploy.py
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- LOCATE (e-1-i): a marker whose `state` is not `ready` answers INCOMPLETE with `remnant_path` and no `workspace_path`; locate never creates or changes anything. The failed run did this via `_locate_found()`/`_incomplete_answer()` (43 python-coder).
- VERIFY (carried from 43 architect-review): `cmd_verify` in `worktree.py` also answers ok regardless of `state`. Ticket 11's BO-4300c-4-i confirms locations with `verify --path`, so fix it here to the same rule as locate.
- REMOVE (e-2): never reads stdin; classifies unsent work with the BO-4100c-1 verdict AFTER A FETCH. Carried finding 01 pr-reviewer M-2: `_branch_pushed()` checks `refs/remotes/origin/<branch>` without fetching first. Whole folder removed (Windows extended-length prefix where needed, e-2-i: the failed run added `_long_path_target()`), no prune, nothing changed in the main checkout, ok only after a post-check. Move remove into `templates/scripts/worktree_remove.py` (`worktree_admin.py` grows past the ratchet otherwise); export the unsent-work verdict for ticket 12's cut-over.
- PROCESSES (e-2-ii): `cmd_remove` never calls `sweep_processes.sweep()` before `shutil.rmtree` (46 test-writer/python-coder), and `scripts/worktree/sweep_processes.py` is deployed to NO layout (only `check_workspace_setup_permission.py` is in `AGENT_SUPPORT_SCRIPT_FILES`; its `config_loader` import keeps it out -- see `scripts/build_phases_script_deploy.py`). Fix the deploy path and wire the sweep in; refuse PROCESS_HOLDS_FILES naming the processes with the workspace untouched. The failed run's ticket 46 had only `sweep_processes.py` in files_touched and correctly refused to edit `worktree_admin.py`.
- AUTHORISATION (e-3, e-3-i) -- Q8 DECIDED (user, 2026-09-28): a remove refused `UNSENT_WORK` returns `discard_token` (field declared by ticket 03), a ONE-TIME token bound to exactly what would be lost -- the workspace (canonical path plus its maker record, so a re-made workspace at the same path rejects an old token), its unsent commit shas, and its uncommitted/untracked files including content. Only `remove --path <same> --discard-token <token>` discards; the maker recomputes the binding on every request and accepts only an exact match. A token for another workspace or for a changed unsent set is refused `UNSENT_WORK` with the current lists and a fresh token, changing nothing. Clean workspaces need no token. The token is never read from env, config, stdin or a file, never written anywhere but the refusal's stdout, and nothing is remembered between invocations (a stateless digest satisfies this; how it is computed is the coder's call). Implement in `templates/scripts/worktree_remove.py`. Never delete/push the hub branch unless `--delete-remote-branch`.
- STARTING POINT (re-verify): `git show refs/wip/bo4300-attempt1:unit_tests/build_orchestration/test_bo_4300e_1_i.py`, `test_bo_4300e_2_i.py`, `test_bo_4300e_2_ii.py`, `test_bo_4300e_3_i.py` in that ref, and `git show refs/wip/bo4300-attempt1 -- templates/scripts/worktree_admin.py scripts/worktree/sweep_processes.py`.
- FILE-SIZE RATCHET: `templates/scripts/worktree.py` is at ~393 of 400 counted lines and `templates/scripts/worktree_git.py` near its limit (01 python-coder sign-off). Every addition therefore goes into the NEW module this ticket owns (see files_touched); the two core files are touched only to move code out and to wire the new module in. A new module needs its own NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py` and `scripts/build_deploy_manifest_helpers.py` (KI-TQ-004: no second tracked copy; the maker is deployed to `<install-root>/.leafcutter/scripts/<name>`, not `<install-root>/scripts/`, per 01 test-writer/python-coder).
- ANSWER TABLE: the status/code/exit table is owned by ticket 03 (BO-4300c-2 declares the full code enum). Do not add codes locally; if a code is missing from BO-4300c-2 it is a contract change, not a local edit.
- PROOF: tests run the DEPLOYED maker through ticket 02's locator (`unit_tests/build_orchestration/_workspace_maker_fixtures.py`), as a subprocess, against real temp repos with a real bare hub; no mock of git, no import of the maker module, never spawn `scripts/build.py`. Pin `newline="\n"` on fixture writes and isolate GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM (the CRLF drift found on 04 in the failed run). Use `AC_ENFORCE_STRICT=1` to see a genuine red baseline (the AC-enforcement plugin otherwise downgrades not-done-AC failures to xfail).
- HOOK HYGIENE (lessons from ticket 01): DECISION HISTORY entries need `HH:MM` and the `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/NN)` tail-tag on the entry's FIRST line; run `check_documentation.py` with NO `--file` flag (staged mode) before commit; run `check_doc_length.py` on every doc touched (300-line ratchet); stage every file in files_touched (01 shipped an ADR edit unstaged). Commits never spelled `git -C <path> commit`.
- SCOPE: the epic worktree is shared by every ticket. Edit only files_touched. If the fix needs another file, stop and get this ticket updated (CLAUDE.md TICKET MANDATE); the failed run stalled on exactly this (tickets 04, 14, 46, 59).

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300e-1-i**

- locate/list/verify are strictly read-only: no fetch, no lock, no folder, no marker write, no repair.

**BO-4300e-1**

- locate and list scan the landing place and the maker's records, never `git worktree list` (no git command lists clones); matching is on the exact normalised identity, so 'alpha' never returns 'alpha-v2'.
- Not found is a definite refused NOT_FOUND answer (no workspace_path); a half-made entry is refused INCOMPLETE with remnant_path.

**BO-4300e-2-i**

- Paths longer than 260 characters are removed using the extended-length prefix on Windows (close-worktree.md's \\?\ escape, kept per the decision memo).
- Runs for real on the Windows CI job (see BO-4300b-4); on other platforms the long-path arm still runs and must pass.

**BO-4300e-2-ii**

- Before deleting anything, find processes started from the workspace or holding files in it (reuse scripts/worktree/sweep_processes.py's sweep, fixing its deploy path which matches neither layout); either stop them and then remove everything, or refuse PROCESS_HOLDS_FILES naming them with the workspace untouched. No partial deletion is ever reported as removed.

**BO-4300e-2**

- remove never reads stdin or prompts (finalize's teardown deadlock); it classifies unsent work with the BO-4100c-1 verdict -- commits on the workspace's branch reachable from neither origin/<branch> nor origin/main after a fetch, plus uncommitted and untracked changes -- and refuses UNSENT_WORK listing unsent.commits and unsent.files unless discard was authorised up front (BO-4300e-3).
- Deletion removes the whole folder (Windows extended-length path prefix where needed), runs no prune and changes nothing in the main checkout; the answer is ok only after a post-check finds nothing left at the location.

**BO-4300e-3-i**

- Q8 (DECIDED user 2026-09-28): the token authorises only the remove request for the workspace it was issued for, and only while that workspace's unsent set is exactly the one it was issued for (BO-4300e-3); nothing is persisted between invocations, so there is no remembered authorisation to leak into the next request.

**BO-4300e-3**

- DISCARD TOKEN (Q8, DECIDED user 2026-09-28): remove on a workspace holding unsent work is refused UNSENT_WORK (exit 2) listing unsent.commits and unsent.files and carrying discard_token (BO-4300c-2): a one-time token bound to exactly what would be lost -- that workspace (its canonical path and its maker record, so a workspace re-made at the same path never accepts an older token), its unsent commit shas, and its uncommitted and untracked files including their content. Only `remove --path <same> --discard-token <that token>` discards it; the maker recomputes the binding at request time and accepts the token only on an exact match.
- A token presented for another workspace, or after the unsent set changed (a commit added or pushed, a file added, removed or edited), authorises nothing: the request is refused UNSENT_WORK with the current lists and a fresh token, its message states that the presented token does not match, and nothing is changed. A workspace with nothing unsent is removed without a token; a token is never required to remove clean work.
- The token is never read from an environment variable, a config setting, stdin or any file, and the maker stores nothing between invocations: the binding is recomputed from the workspace's current state on every request, and the token string is written only to the refusal's stdout answer. Never asked interactively.
- An authorised remove answers ok with discarded.commits and discarded.files; it never deletes or pushes the hub branch unless --delete-remote-branch is also given.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300e-1-i -- Looking a workspace up never creates or changes one
- [ ] AC-2: BO-4300e-1 -- Asking where a piece of work's workspace is gets a definite answer from the same maker
- [ ] AC-3: BO-4300e-2-i -- A workspace with very long file paths on Windows is cleared completely
- [ ] AC-4: BO-4300e-2-ii -- A workspace with a program still running inside it is never left half-cleared
- [ ] AC-5: BO-4300e-2 -- Clearing a workspace answers at once and never waits for someone to say yes
- [ ] AC-6: BO-4300e-3-i -- A discard token clears only the workspace and the unsent work it was issued for
- [ ] AC-7: BO-4300e-3 -- Loss of unsent work happens only when authorised up front

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300e-1-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300e-1 per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300e-2-i per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300e-2-ii per `## Test Requirements`
- [ ] AC-5: red tests for BO-4300e-2 per `## Test Requirements`
- [ ] AC-6: red tests for BO-4300e-3-i per `## Test Requirements`
- [ ] AC-7: red tests for BO-4300e-3 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300e-1-i <- BO-4300e-1** (this ticket): locate semantics.
- **BO-4300e-1 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): Marker record and landing-place rule.
- **BO-4300e-2-i <- BO-4300e-2** (this ticket): remove semantics.
- **BO-4300e-2-ii <- BO-4300e-2** (this ticket): remove semantics.
- **BO-4300e-2 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): Marker record identifying a maker-made workspace.
- **BO-4300e-3-i <- BO-4300e-3** (this ticket): Up-front discard authorisation: the discard_token binding (workspace path and maker record, unsent shas, uncommitted files with content) and exact-match acceptance on remove --discard-token.
- **BO-4300e-3 <- BO-4300e-2** (this ticket): UNSENT_WORK verdict and unsent lists.

### Delivers To

- **BO-4300e-1 -> python-coder**: locate/verify answers used by workflows to confirm a supplied location (BO-4300c-4-i): ok with workspace_path only for a ready workspace; refused NOT_FOUND / INCOMPLETE otherwise.
- consumed by **BO-4300c-4-i** in 11_TICKET-20260928-BO-4300-workflow-routes.md
- consumed by **BO-4300e-4** in 11_TICKET-20260928-BO-4300-workflow-routes.md
- consumed by **BO-4300e-5** in 13_TICKET-20260928-BO-4300-docs-and-diagrams.md

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? Yes -- workspaces can hold unsent work; every destructive path refuses unless authorised, and proofs run only in temp repos.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
