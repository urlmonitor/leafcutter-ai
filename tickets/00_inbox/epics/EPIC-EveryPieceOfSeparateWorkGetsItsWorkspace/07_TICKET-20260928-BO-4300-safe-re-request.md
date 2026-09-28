---
title: 'Asking again is safe: re-readying, one workspace under concurrency, finishing half-made ones'
status: todo
components:
- worktree_manager
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 06_TICKET-20260928-BO-4300-work-identity-and-ticket-location.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
source_ac: BO-4300d-2
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300d-1
  - BO-4300d-2
  l3:
  - BO-4300d-1-i
  - BO-4300d-1-ii
  - BO-4300d-2-i
  - BO-4300d-2-ii
  - BO-4300d-2-iii
ac_coverage: 0/7
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_ensure_state.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
- unit_tests/build_orchestration/test_bo_4300d_1.py
- unit_tests/build_orchestration/test_bo_4300d_1_i.py
- unit_tests/build_orchestration/test_bo_4300d_1_ii.py
- unit_tests/build_orchestration/test_bo_4300d_2.py
- unit_tests/build_orchestration/test_bo_4300d_2_i.py
- unit_tests/build_orchestration/test_bo_4300d_2_ii.py
- unit_tests/build_orchestration/test_bo_4300d_2_iii.py
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

# 07: Asking again is safe: re-readying, one workspace under concurrency, finishing half-made ones

## Actor / Goal

In order that callers can always just ask again, we need ensure to re-ready a healthy workspace without touching its work, serialise concurrent requests for the same work, and finish a workspace an interrupted request left half-made, so that no request ever produces two workspaces, overwrites work, or answers ready early.

## Context

d-1 expects from c-1 and d-1-i from c-1-iii (ticket 05); d-2 from the marker's `state` (ticket 01). All seven ACs are the ensure state machine that `docs/architecture/diagrams` will draw in ticket 13 (d-5).

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 7 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300d-1-i | L3 | Re-readying never overwrites a change the work made to a file the set-up also writes | BO-4300c-1-iii | 05_TICKET-20260928-BO-4300-readiness.md |
| AC-2 | BO-4300d-1-ii | L3 | Two requests for the same work at the same moment never make two workspaces | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-3 | BO-4300d-1 | L2 | Asking again for a healthy workspace hands it back re-readied, with the work in it untouched | BO-4300c-1 | 05_TICKET-20260928-BO-4300-readiness.md |
| AC-4 | BO-4300d-2-i | L3 | A half-made workspace is never answered ready while the cause remains | BO-4300d-2 | this ticket |
| AC-5 | BO-4300d-2-ii | L3 | Whatever stage an interruption hit, the next request ends fully ready | BO-4300d-2 | this ticket |
| AC-6 | BO-4300d-2-iii | L3 | A half-made workspace in which work has since been done is not wiped to finish it | BO-4300d-2 | this ticket |
| AC-7 | BO-4300d-2 | L2 | A workspace left half-made by an interrupted request is finished by the next one | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300d-1`, `BO-4300d-2` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300d-2`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300d-1-i (L3) -- Re-readying never overwrites a change the work made to a file the set-up also writes

```gherkin
Given a ready workspace in which the work has changed, and not yet committed, a
  version-controlled file that setting up the workspace also rewrites,
When the same work is requested again,
Then the work's change to that file is identical before and after,
And the answer is either ready with the change intact, or a refusal naming the
  file whose change would otherwise have been lost.
```

### AC-2: BO-4300d-1-ii (L3) -- Two requests for the same work at the same moment never make two workspaces

```gherkin
Given no workspace exists for "alpha",
When two requests for "alpha" are started at the same moment from two different
  routes,
Then exactly one workspace for "alpha" exists afterwards, and it meets every
  part of readiness,
And each request is answered either ready with that one workspace's location,
  or refused stating that the same work is already being prepared,
And neither request is answered ready with a location other than that one.
```

### AC-3: BO-4300d-1 (L2) -- Asking again for a healthy workspace hands it back re-readied, with the work in it untouched

```gherkin
Given a ready workspace for "alpha" whose line of work carries two commits, and
  which has one uncommitted change and one new file not yet under version
  control,
When "alpha" is requested again,
Then the answer is ready, gives the same location, and states that an existing
  workspace was re-readied,
And during this request the tools inside it were rebuilt from its own contents
  and its protections were shown to fire again,
And the two commits, the uncommitted change and the new file are identical
  before and after,
And exactly one workspace for "alpha" exists afterwards.
```

### AC-4: BO-4300d-2-i (L3) -- A half-made workspace is never answered ready while the cause remains

```gherkin
Given the same half-made workspace for "alpha", and the cause of the install
  failure still present,
When "alpha" is requested again,
Then the answer is a refusal naming the install failure,
And the answer is never ready and never states that the workspace was reused,
And no second workspace for "alpha" is created beside it.
```

### AC-5: BO-4300d-2-ii (L3) -- Whatever stage an interruption hit, the next request ends fully ready

```gherkin
Given four half-made workspaces, each left by a request interrupted at a
  different stage: after the copy was made but before its line of work existed;
  after the line of work existed but before the install; after the install but
  before the protections were shown to fire; and while the maker was recording
  that it made the workspace,
When each is requested again with the cause removed,
Then each is answered ready, and every part of readiness from BO-4300c-1 holds
  for each,
And none of the four is answered ready at any point while a part of readiness
  is missing.
```

### AC-6: BO-4300d-2-iii (L3) -- A half-made workspace in which work has since been done is not wiped to finish it

```gherkin
Given a half-made workspace for "alpha" in which a file has since been changed
  by hand,
When "alpha" is requested again,
Then the changed file is identical before and after,
And the answer is either ready with the change intact, or a refusal naming the
  changed file,
And the folder is never deleted and made again while it holds that change.
```

### AC-7: BO-4300d-2 (L2) -- A workspace left half-made by an interrupted request is finished by the next one

```gherkin
Given an earlier request for "alpha" made the copy of the project and its line
  of work and then failed during the install, leaving a folder holding only the
  project's committed files and no installed tools,
And the cause of that failure has since been removed,
When "alpha" is requested again,
Then the answer is ready only after the install has completed in that folder and
  its protections have been shown to fire there,
And the answer states that an incomplete workspace was completed, not that a
  healthy one was reused,
And exactly one workspace for "alpha" exists afterwards, at the same location.
```

- [ ] AC-1: BO-4300d-1-i -- Re-readying never overwrites a change the work made to a file the set-up also writes
- [ ] AC-2: BO-4300d-1-ii -- Two requests for the same work at the same moment never make two workspaces
- [ ] AC-3: BO-4300d-1 -- Asking again for a healthy workspace hands it back re-readied, with the work in it untouched
- [ ] AC-4: BO-4300d-2-i -- A half-made workspace is never answered ready while the cause remains
- [ ] AC-5: BO-4300d-2-ii -- Whatever stage an interruption hit, the next request ends fully ready
- [ ] AC-6: BO-4300d-2-iii -- A half-made workspace in which work has since been done is not wiped to finish it
- [ ] AC-7: BO-4300d-2 -- A workspace left half-made by an interrupted request is finished by the next one

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_work_change_to_build_rewritten_file_is_preserved_on_rerequest
  file: unit_tests/build_orchestration/test_bo_4300d_1_i.py
  covers:
  - BO-4300d-1-i
  asserts: An uncommitted edit to a file the stub build rewrites is byte-identical after the request.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_answer_is_ok_with_change_intact_or_work_at_risk_naming_the_file
  file: unit_tests/build_orchestration/test_bo_4300d_1_i.py
  covers:
  - BO-4300d-1-i
  asserts: The answer is ok with the change intact, or refused WORK_AT_RISK whose unsent.files names that
    file.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_two_concurrent_requests_leave_exactly_one_ready_workspace
  file: unit_tests/build_orchestration/test_bo_4300d_1_ii.py
  covers:
  - BO-4300d-1-ii
  asserts: After two simultaneous ensure alpha processes, the landing place holds one workspace and it
    meets every readiness ingredient.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_each_concurrent_request_is_ok_with_that_location_or_in_progress
  file: unit_tests/build_orchestration/test_bo_4300d_1_ii.py
  covers:
  - BO-4300d-1-ii
  asserts: Each answer is ok with that one workspace_path, or refused IN_PROGRESS.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_no_concurrent_request_is_ok_with_another_location
  file: unit_tests/build_orchestration/test_bo_4300d_1_ii.py
  covers:
  - BO-4300d-1-ii
  asserts: No ok answer names any other location.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_stale_lock_from_dead_process_is_reclaimed
  file: unit_tests/build_orchestration/test_bo_4300d_1_ii.py
  covers:
  - BO-4300d-1-ii
  asserts: A lock left by a killed maker does not block the next request beyond the bounded wait.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_rerequest_of_ready_workspace_answers_ok_same_location_re_readied
  file: unit_tests/build_orchestration/test_bo_4300d_1.py
  covers:
  - BO-4300d-1
  asserts: The answer is ok, same workspace_path, workspace_action 're-readied'.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_rerequest_rebuilds_install_and_reproves_protections
  file: unit_tests/build_orchestration/test_bo_4300d_1.py
  covers:
  - BO-4300d-1
  asserts: A build counter written by the stub build increments and a fresh canary rejection is recorded
    during the request.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_commits_uncommitted_change_and_untracked_file_survive
  file: unit_tests/build_orchestration/test_bo_4300d_1.py
  covers:
  - BO-4300d-1
  asserts: Both commit shas, the uncommitted change and the untracked file are byte-identical before and
    after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_exactly_one_workspace_exists_after_rerequest
  file: unit_tests/build_orchestration/test_bo_4300d_1.py
  covers:
  - BO-4300d-1
  asserts: The landing place holds one workspace for alpha.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_half_made_with_cause_present_is_refused_naming_install
  file: unit_tests/build_orchestration/test_bo_4300d_2_i.py
  covers:
  - BO-4300d-2-i
  asserts: The answer is BOOTSTRAP_FAILED.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_half_made_is_never_answered_ok_or_reused
  file: unit_tests/build_orchestration/test_bo_4300d_2_i.py
  covers:
  - BO-4300d-2-i
  asserts: The answer has no workspace_path and no workspace_action of 're-readied'.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_no_second_workspace_is_created_beside_the_half_made_one
  file: unit_tests/build_orchestration/test_bo_4300d_2_i.py
  covers:
  - BO-4300d-2-i
  asserts: The landing place still holds exactly one entry for alpha.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_each_of_four_interruption_stages_completes_to_ok_on_next_request
  file: unit_tests/build_orchestration/test_bo_4300d_2_ii.py
  covers:
  - BO-4300d-2-ii
  asserts: For interruptions after clone, after branch, after install and during the marker write, the
    next request (cause removed) answers ok with every readiness ingredient true.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_no_interrupted_state_is_ever_answered_ok_while_an_ingredient_is_missing
  file: unit_tests/build_orchestration/test_bo_4300d_2_ii.py
  covers:
  - BO-4300d-2-ii
  asserts: verify/locate on each interrupted state before completion never answers ok.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_hand_changed_file_in_half_made_workspace_survives
  file: unit_tests/build_orchestration/test_bo_4300d_2_iii.py
  covers:
  - BO-4300d-2-iii
  asserts: The changed file is byte-identical after the request.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_answer_is_ok_with_change_or_work_at_risk_naming_it
  file: unit_tests/build_orchestration/test_bo_4300d_2_iii.py
  covers:
  - BO-4300d-2-iii
  asserts: The answer is ok with the change intact, or WORK_AT_RISK naming the file.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_folder_is_never_recreated_while_holding_the_change
  file: unit_tests/build_orchestration/test_bo_4300d_2_iii.py
  covers:
  - BO-4300d-2-iii
  asserts: The folder's identity (inode / creation time) and its .git directory are the same before and
    after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_half_made_workspace_is_completed_by_next_request
  file: unit_tests/build_orchestration/test_bo_4300d_2.py
  covers:
  - BO-4300d-2
  asserts: After a request that failed in the stub build, a second request with the cause removed answers
    ok at the same location.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_completion_answer_says_completed_not_reused
  file: unit_tests/build_orchestration/test_bo_4300d_2.py
  covers:
  - BO-4300d-2
  asserts: workspace_action is 'completed'.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ok_only_after_install_and_canary_in_that_folder
  file: unit_tests/build_orchestration/test_bo_4300d_2.py
  covers:
  - BO-4300d-2
  asserts: The install files exist in that folder and a canary rejection was recorded there before the
    ok answer.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_one_workspace_at_same_location_after_completion
  file: unit_tests/build_orchestration/test_bo_4300d_2.py
  covers:
  - BO-4300d-2
  asserts: One workspace for alpha exists, at the original location.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ticket_07_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300d_1_i.py
  covers:
  - BO-4300d-2
  angle: reachability
  surface_invoked: python <install-root>/.leafcutter/scripts/worktree.py ensure ... issued twice / concurrently
    / after an interrupted run (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_ensure_state.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- CARRIED FINDING (01 pr-reviewer M-1, unresolved through four reviews): `_answer_from_existing`'s idempotent short-circuit recomputes `checks` but does not re-fetch, re-build or re-run the canaries; it replays the marker's stored `hooks_canary_rejected`. BO-4300d-1 ('hands it back re-readied') makes this a real requirement here: re-ready through ticket 05's readiness module.
- RE-READY never overwrites a change the work made to a file the set-up also writes (d-1-i; expects from c-1-iii's no-stray-changes rule).
- LOCK (d-1-ii): exclusively created lock per (project, work identity) outside the workspace folder holding pid, host, start time; stale holder reclaimed; bounded wait then IN_PROGRESS. Proof starts two real maker processes with the stub build holding a barrier.
- HALF-MADE (d-2 family): marker `state: creating` is finished by the next request; never answered ready while the cause remains; a half-made workspace in which work was since done is not wiped to finish it (WORK_AT_RISK).
- FILE-SIZE RATCHET: `templates/scripts/worktree.py` is at ~393 of 400 counted lines and `templates/scripts/worktree_git.py` near its limit (01 python-coder sign-off). Every addition therefore goes into the NEW module this ticket owns (see files_touched); the two core files are touched only to move code out and to wire the new module in. A new module needs its own NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py` and `scripts/build_deploy_manifest_helpers.py` (KI-TQ-004: no second tracked copy; the maker is deployed to `<install-root>/.leafcutter/scripts/<name>`, not `<install-root>/scripts/`, per 01 test-writer/python-coder).
- ANSWER TABLE: the status/code/exit table is owned by ticket 03 (BO-4300c-2 declares the full code enum). Do not add codes locally; if a code is missing from BO-4300c-2 it is a contract change, not a local edit.
- PROOF: tests run the DEPLOYED maker through ticket 02's locator (`unit_tests/build_orchestration/_workspace_maker_fixtures.py`), as a subprocess, against real temp repos with a real bare hub; no mock of git, no import of the maker module, never spawn `scripts/build.py`. Pin `newline="\n"` on fixture writes and isolate GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM (the CRLF drift found on 04 in the failed run). Use `AC_ENFORCE_STRICT=1` to see a genuine red baseline (the AC-enforcement plugin otherwise downgrades not-done-AC failures to xfail).
- HOOK HYGIENE (lessons from ticket 01): DECISION HISTORY entries need `HH:MM` and the `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/NN)` tail-tag on the entry's FIRST line; run `check_documentation.py` with NO `--file` flag (staged mode) before commit; run `check_doc_length.py` on every doc touched (300-line ratchet); stage every file in files_touched (01 shipped an ADR edit unstaged). Commits never spelled `git -C <path> commit`.
- SCOPE: the epic worktree is shared by every ticket. Edit only files_touched. If the fix needs another file, stop and get this ticket updated (CLAUDE.md TICKET MANDATE); the failed run stalled on exactly this (tickets 04, 14, 46, 59).

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300d-1-i**

- Before running the build on an existing workspace, detect uncommitted work changes to files the build rewrites; either preserve them byte-identically around the build, or refuse WORK_AT_RISK naming each file BEFORE the build runs. Never discover the loss afterwards.
- The restore step of BO-4300c-1-iii excludes paths the work had changed before the build.

**BO-4300d-1-ii**

- Mutual exclusion per (project, work identity): an exclusively created lock outside the workspace folder, holding pid, host and start time; a lock whose holder is dead is detectably stale and reclaimed; a waiter waits a bounded time (configurable, default no more than the expected ensure duration) and then answers refused IN_PROGRESS -- never an indefinite block, never a second workspace.
- Proof starts two real maker processes concurrently (the stub build holds a barrier so both are genuinely in flight).

**BO-4300d-1**

- A request for a ready workspace re-runs fetch, build, clean-tree check and canary every time (decision 2) and answers workspace_action 're-readied'; it never resets, rebases or checks out over the line of work, never removes untracked files, and never re-clones.

**BO-4300d-2-i**

- While the cause persists the answer is BOOTSTRAP_FAILED every time; there is no reuse path that skips set-up (F5's 'ok, reused').

**BO-4300d-2-ii**

- The four interrupted states are produced by really interrupting the deployed maker. A stage-abort seam (an environment variable naming a stage) is permitted only if it can do nothing but abort at that stage -- it can never skip a step or yield ok -- and it is documented as a test seam.
- The marker write is atomic, so an interruption while recording leaves either the 'creating' record or the complete one, never a torn record that is accepted.

**BO-4300d-2-iii**

- The delete-and-redo remedy is used only while the folder holds nothing but what the interrupted request put there; a hand change (detected via git status against the clone's checkout, the BO-4100c-1 holds-work signal) forbids deletion: complete in place with the change intact, or refuse WORK_AT_RISK naming the file.

**BO-4300d-2**

- A folder at the work's landing location is this work's half-made workspace ONLY when it carries the maker's own 'creating' record for this identity (or is empty); anything else is an occupant (BO-4300d-3) or a leftover (BO-4100e-4). Identification never rests on name similarity.
- Completing resumes the remaining steps in place and answers workspace_action 'completed'; ok only after the install and canary succeeded in that folder.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300d-1-i -- Re-readying never overwrites a change the work made to a file the set-up also writes
- [ ] AC-2: BO-4300d-1-ii -- Two requests for the same work at the same moment never make two workspaces
- [ ] AC-3: BO-4300d-1 -- Asking again for a healthy workspace hands it back re-readied, with the work in it untouched
- [ ] AC-4: BO-4300d-2-i -- A half-made workspace is never answered ready while the cause remains
- [ ] AC-5: BO-4300d-2-ii -- Whatever stage an interruption hit, the next request ends fully ready
- [ ] AC-6: BO-4300d-2-iii -- A half-made workspace in which work has since been done is not wiped to finish it
- [ ] AC-7: BO-4300d-2 -- A workspace left half-made by an interrupted request is finished by the next one

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300d-1-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300d-1-ii per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300d-1 per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300d-2-i per `## Test Requirements`
- [ ] AC-5: red tests for BO-4300d-2-ii per `## Test Requirements`
- [ ] AC-6: red tests for BO-4300d-2-iii per `## Test Requirements`
- [ ] AC-7: red tests for BO-4300d-2 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300d-1-i <- BO-4300c-1-iii** (05_TICKET-20260928-BO-4300-readiness.md): Tracked-file snapshot and restored_tracked.
- **BO-4300d-1-ii <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure CLI.
- **BO-4300d-1 <- BO-4300c-1** (05_TICKET-20260928-BO-4300-readiness.md): Readiness conjunction re-evaluated on every request.
- **BO-4300d-2-i <- BO-4300d-2** (this ticket): Half-made identification and completion.
- **BO-4300d-2-ii <- BO-4300d-2** (this ticket): Half-made identification and completion.
- **BO-4300d-2-iii <- BO-4300d-2** (this ticket): Half-made identification and completion.
- **BO-4300d-2 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): Marker record with state 'creating'|'ready'.

### Delivers To

- consumed by **BO-4300d-5** in 13_TICKET-20260928-BO-4300-docs-and-diagrams.md

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
