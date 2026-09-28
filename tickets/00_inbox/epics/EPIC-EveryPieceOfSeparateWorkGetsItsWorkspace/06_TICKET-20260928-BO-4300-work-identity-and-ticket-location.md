---
title: Work identity, ticket location, occupied locations and resumed lines
status: todo
components:
- worktree_manager
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 05_TICKET-20260928-BO-4300-readiness.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
source_ac: BO-4300a-2
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300a-2
  - BO-4300d-3
  - BO-4300d-4
  l3:
  - BO-4300a-1-ii
  - BO-4300d-3-i
ac_coverage: 0/5
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_identity.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
- unit_tests/build_orchestration/test_bo_4300a_2.py
- unit_tests/build_orchestration/test_bo_4300a_1_ii.py
- unit_tests/build_orchestration/_bo_4300a_1_ii_fixtures.py
- unit_tests/build_orchestration/test_bo_4300d_3.py
- unit_tests/build_orchestration/test_bo_4300d_3_i.py
- unit_tests/build_orchestration/test_bo_4300d_4.py
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

# 06: Work identity, ticket location, occupied locations and resumed lines

## Actor / Goal

In order that the same piece of work always maps to the same workspace, we need one naming table, a ticket location stated inside the workspace, and safe handling of locations that already hold different or legacy work and of lines that already exist on the hub, so that no request abandons, overwrites or silently adopts work.

## Context

a-2, d-3 and d-4 all decide 'which workspace/line is this request for' and share the ensure path's identity step; a-1-ii adds the ticket fields to the same step. a-1-ii is a child of BO-4300a-1 (ticket 01), which closes only after this ticket.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 5 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300a-2 | L2 | The same piece of work is always recognised as the same workspace | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-2 | BO-4300a-1-ii | L3 | A ready workspace made for a ticket states where that ticket is inside the workspace | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-3 | BO-4300d-3-i | L3 | A workspace for the same work made the old way is not quietly taken over | BO-4300d-3 | this ticket |
| AC-4 | BO-4300d-3 | L2 | A location already holding different work is left untouched and reported | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-5 | BO-4300d-4 | L2 | Asking for work whose line already exists on the shared project resumes that line | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300d-3` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300a-2`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300a-2 (L2) -- The same piece of work is always recognised as the same workspace

```gherkin
Given the epic "Files Stay Workable" has a ready workspace that was obtained
  through the long-running build route, and its line of work carries two
  commits,
When the same epic is asked for again through the feature skill's epic route,
  which today names epics differently, and again through the long-running
  build route,
Then both requests are answered ready with the location of the existing
  workspace,
And afterwards exactly one workspace and exactly one line of work exist for
  that epic,
And the two commits are still on the line of work the workspace is on,
And given a different epic, "Files Stay Portable", is requested, it is answered
  with a workspace of its own, at a different location from the first.
```

### AC-2: BO-4300a-1-ii (L3) -- A ready workspace made for a ticket states where that ticket is inside the workspace

```gherkin
Given a test project whose main copy holds the ticket
  "tickets/TICKET-20260925-demo.md",
And a workspace is requested for that ticket, naming the ticket by its
  location in the main copy,
When the workspace maker answers ready with workspace location L,
Then the answer states the ticket's location inside L,
And at the moment the answer is given, a file exists at that stated location
  and holds the content of the ticket named in the request,
And the answer never presents the ticket's location in the main copy, or any
  other location outside L, as the workspace's copy of the ticket,
And a ready answer never states a ticket location at which no file exists.
```

### AC-3: BO-4300d-3-i (L3) -- A workspace for the same work made the old way is not quietly taken over

```gherkin
Given a workspace for "alpha" that was made the old way, sharing the main copy's
  version history, with one commit not on the shared main line, exists either at
  the location for "alpha" or in the folder where the old way put it, under the
  old way's name for "alpha",
When "alpha" is requested,
Then the answer is a refusal stating that an old-style workspace for this work
  exists, where it is, and that it must be brought over first,
And no second workspace for "alpha" is made,
And that workspace, its commit and its registration are identical before and
  after.
```

### AC-4: BO-4300d-3 (L2) -- A location already holding different work is left untouched and reported

```gherkin
Given the location the workspace maker would use for "alpha" is already
  occupied, in turn, by: a copy of the project on a different line of work; a
  copy of a different project; and an ordinary folder of files that is not a
  workspace,
When "alpha" is requested in each case,
Then the answer is a refusal stating that the location is occupied and what
  occupies it,
And the occupant's files and, where it has one, its line of work are identical
  before and after,
And no workspace for "alpha" is made at any other location instead.
```

### AC-5: BO-4300d-4 (L2) -- Asking for work whose line already exists on the shared project resumes that line

```gherkin
Given the line of work "alpha" exists on the shared project with three commits
  that are not on the shared main line, and no workspace for "alpha" exists on
  this machine,
When "alpha" is requested,
Then the ready workspace is on the line of work "alpha" and contains those
  three commits,
And the ready answer says the line of work was resumed, not newly started,
And no workspace for "alpha" is made on a freshly started line of work while
  those three commits exist only on the shared project,
And the line of work "alpha" on the shared project is identical before and
  after.
```

- [ ] AC-1: BO-4300a-2 -- The same piece of work is always recognised as the same workspace
- [ ] AC-2: BO-4300a-1-ii -- A ready workspace made for a ticket states where that ticket is inside the workspace
- [ ] AC-3: BO-4300d-3-i -- A workspace for the same work made the old way is not quietly taken over
- [ ] AC-4: BO-4300d-3 -- A location already holding different work is left untouched and reported
- [ ] AC-5: BO-4300d-4 -- Asking for work whose line already exists on the shared project resumes that line

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_same_epic_requested_via_other_spelling_returns_existing_location
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: With a ready workspace for 'Files Stay Workable' obtained as kind epic, requests using the
    feature skill's EPIC-FilesStayWorkable spelling and the build route's spelling are both answered ok
    with the existing workspace_path.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_one_workspace_and_one_line_of_work_exist_after_rerequests
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: Afterwards the landing place holds one workspace for the epic and the hub and workspace hold
    one line of work for it.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_existing_commits_survive_rerequests
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: Both commits remain on the workspace's line of work, with unchanged shas.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_distinct_epic_gets_its_own_location
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: '''Files Stay Portable'' is answered ok with a different workspace_path.'
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_legacy_epic_spelling_lands_on_the_canonical_epic_workspace
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: With no workspace yet, ensure --kind epic --slug EPIC-FilesStayPortable is answered ok with
    kind epic, slug files-stay-portable, branch epic/files-stay-portable and workspace_path at <landing-root>/epic/files-stay-portable;
    a second request spelled epic/files-stay-portable returns the same workspace_path.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_every_declared_legacy_alias_resolves_to_its_canonical_identity
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: Table-driven over the declared aliases -- EPIC-X (epic), ac-authoring/x (ac), fast-lane/x (fastlane),
    feature/x (ticket) -- each request is answered ok with the canonical <kind>/<slug> and the same workspace_path
    as the canonical spelling of the same work.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_legacy_line_on_the_hub_is_resumed_never_twinned
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: With the hub carrying EPIC-FilesStayPortable (two commits) and no epic/files-stay-portable,
    a request for the epic is answered ok with line_of_work resumed and branch EPIC-FilesStayPortable,
    both commits are in the workspace, and afterwards the hub has no epic/files-stay-portable ref and
    the legacy ref is unchanged.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_two_spellings_with_lines_on_the_hub_are_refused_ambiguous_line
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: With the hub carrying both EPIC-FilesStayPortable and epic/files-stay-portable, each with commits,
    the request is refused AMBIGUOUS_LINE (exit 2) whose lines name both branches, no workspace_path is
    emitted, no folder is created and both hub refs are unchanged.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ready_answer_states_ticket_location_inside_the_workspace
  file: unit_tests/build_orchestration/test_bo_4300a_1_ii.py
  covers:
  - BO-4300a-1-ii
  asserts: With tickets/TICKET-20260925-demo.md committed on the hub's main and the request naming it
    by its main-copy path (absolute, then project-relative, each from a different starting folder), the
    ok answer's ticket_path_in_worktree equals workspace_path joined with tickets/TICKET-20260925-demo.md,
    and ticket_path_in_worktree_posix is its posix spelling.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_stated_ticket_location_holds_the_requested_tickets_content
  file: unit_tests/build_orchestration/test_bo_4300a_1_ii.py
  covers:
  - BO-4300a-1-ii
  asserts: At the moment the answer is read, a regular file exists at ticket_path_in_worktree and its
    bytes equal the requested ticket's bytes.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_answer_never_presents_a_location_outside_the_workspace_as_the_ticket
  file: unit_tests/build_orchestration/test_bo_4300a_1_ii.py
  covers:
  - BO-4300a-1-ii
  asserts: ticket_path_in_worktree is inside workspace_path, differs from the main-copy path passed in,
    and the answer carries no ticket_path_final or ticket_path_new field.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ticket_absent_from_the_base_never_yields_an_ok_answer
  file: unit_tests/build_orchestration/test_bo_4300a_1_ii.py
  covers:
  - BO-4300a-1-ii
  asserts: With the ticket present only in the main copy (never pushed to the hub), the answer is status
    refused, code TICKET_NOT_ON_BASE, reason 'absent', exit 2, with ticket_path equal to the requested
    path; it carries neither ticket_path_in_worktree field nor workspace_path, no ticket file was written
    into any workspace, the stub build never ran, and no folder or INCOMPLETE remnant is left at the workspace
    location.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ticket_that_differs_from_the_base_is_refused_not_on_base
  file: unit_tests/build_orchestration/test_bo_4300a_1_ii.py
  covers:
  - BO-4300a-1-ii
  asserts: With the ticket pushed to the hub's main and then edited (not pushed) in the main copy, the
    answer is status refused, code TICKET_NOT_ON_BASE, reason 'differs', exit 2, with no workspace_path
    and no ticket_path_in_worktree field; no folder is left at the workspace location, and the hub's copy
    of the ticket and the main copy's edited ticket are both byte-unchanged.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ticket_fields_absent_without_ticket_request_and_on_every_refusal
  file: unit_tests/build_orchestration/test_bo_4300a_1_ii.py
  covers:
  - BO-4300a-1-ii
  asserts: An ok ensure without --ticket, and an OCCUPIED refusal with --ticket, both lack ticket_path_in_worktree
    and ticket_path_in_worktree_posix entirely (not null, not blank).
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_legacy_worktree_for_same_work_is_refused_as_legacy_occupant
  file: unit_tests/build_orchestration/test_bo_4300d_3_i.py
  covers:
  - BO-4300d-3-i
  asserts: The answer is refused, code OCCUPIED_LEGACY_WORKTREE, message naming the bring-over step.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_legacy_worktree_commit_and_registration_unchanged
  file: unit_tests/build_orchestration/test_bo_4300d_3_i.py
  covers:
  - BO-4300d-3-i
  asserts: The legacy worktree's files, its extra commit and the main checkout's .git/worktrees entry
    are identical before and after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_legacy_worktree_in_its_old_folder_under_legacy_name_is_refused_not_twinned
  file: unit_tests/build_orchestration/test_bo_4300d_3_i.py
  covers:
  - BO-4300d-3-i
  asserts: With a legacy git worktree on branch EPIC-Alpha registered in the main checkout at <parent>/worktrees/EPIC-Alpha
    (outside the new landing root), a request for kind epic slug alpha is refused OCCUPIED_LEGACY_WORKTREE
    with occupant.path that folder, and no folder exists at <landing-root>/epic/alpha afterwards.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_occupant_on_another_line_is_refused_and_described
  file: unit_tests/build_orchestration/test_bo_4300d_3.py
  covers:
  - BO-4300d-3
  asserts: A clone of the project on another branch at alpha's location gives OCCUPIED with occupant.kind
    'other-line'.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_occupant_from_another_project_is_refused_and_described
  file: unit_tests/build_orchestration/test_bo_4300d_3.py
  covers:
  - BO-4300d-3
  asserts: A clone of a different project gives OCCUPIED, occupant.kind 'other-project'.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_plain_folder_occupant_is_refused_and_described
  file: unit_tests/build_orchestration/test_bo_4300d_3.py
  covers:
  - BO-4300d-3
  asserts: An ordinary folder gives OCCUPIED, occupant.kind 'plain-folder'.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_occupant_files_and_line_of_work_unchanged
  file: unit_tests/build_orchestration/test_bo_4300d_3.py
  covers:
  - BO-4300d-3
  asserts: Each occupant's files and HEAD are identical before and after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_no_workspace_is_made_elsewhere_instead
  file: unit_tests/build_orchestration/test_bo_4300d_3.py
  covers:
  - BO-4300d-3
  asserts: The landing place gains no new entry in any of the three cases.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_existing_hub_line_is_resumed_with_its_commits
  file: unit_tests/build_orchestration/test_bo_4300d_4.py
  covers:
  - BO-4300d-4
  asserts: With alpha on the hub carrying three commits, the ok workspace is on alpha and contains all
    three shas.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_answer_reports_line_resumed
  file: unit_tests/build_orchestration/test_bo_4300d_4.py
  covers:
  - BO-4300d-4
  asserts: line_of_work is 'resumed'.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_no_fresh_line_replaces_existing_hub_commits
  file: unit_tests/build_orchestration/test_bo_4300d_4.py
  covers:
  - BO-4300d-4
  asserts: The workspace HEAD is not origin/main and none of the three commits is dropped.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_hub_line_unchanged_by_the_request
  file: unit_tests/build_orchestration/test_bo_4300d_4.py
  covers:
  - BO-4300d-4
  asserts: The hub's alpha ref sha is identical before and after.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ticket_06_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  angle: reachability
  surface_invoked: python <install-root>/.leafcutter/scripts/worktree.py ensure --kind ticket --slug <s>
    --ticket <path> --repo-root <project> (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- IDENTITY (a-2): one naming table in `templates/scripts/worktree_identity.py` (move `normalize_slug` there); `EPIC-<Name>`, `epic/<kebab>` and the display title normalise to one identity; match on the exact identity, never prefix/substring. Q4 DECIDED (user, 2026-09-28): one scheme `<kind>/<slug>` for every kind (ticket, feature, ac, fastlane, epic, scratch); the table declares the legacy spellings as per-kind aliases -- epic <- `EPIC-<Name>`, ac <- `ac-authoring/<slug>`, fastlane <- `fast-lane/<slug>`, ticket <- `feature/<slug>` (setup-ticket's old ticket lines) -- each entry with its reason. A hub line held only under a legacy spelling is RESUMED on that branch (never renamed, never twinned by a new canonical line); two spellings that both hold lines are refused `AMBIGUOUS_LINE` with `lines` (code and field declared by ticket 03). Legacy git worktrees registered in the main checkout under any alias are refused `OCCUPIED_LEGACY_WORKTREE` wherever their folder is (d-3-i; the landing root moved with Q5, ticket 04), read-only on git's admin files. Retiring finalize's branch-substring match is workflow text and lands with ticket 11 (f-1).
- TICKET LOCATION (a-1-ii): `ticket_path_in_worktree(_posix)` only on an ok answer and only when --ticket was given; TICKET_NOT_ON_BASE for 'absent'/'differs'; a refused clone this request just made is discarded before answering. The failed run implemented this (`_check_ticket_on_base`, `resolve_ticket_paths`, `ticket_on_base_reason`, `_git_show_bytes`, `discard_new_clone`) and pr-reviewer + ac-validator BLOCKED it on a real gap: it_requirements[0] demands USAGE for a --ticket path outside the resolved project (today it silently drops the ticket and answers ok) and for --kind scratch combined with --ticket. Both refusals are in scope here.
- CONSUMERS of the ticket fields: build-single-ticket skill (ticket 09, BO-4300a-1-ib) and worktree-agent charter (ticket 14, BO-4300f-2-ia). Both still read the old `ticket_path_new`/`ticket_path_final` today (04 pr-reviewer).
- OCCUPIED (d-3, d-3-i): a location holding different work is left untouched and reported (OCCUPIED / OCCUPIED_LEGACY_WORKTREE); precedent ADR-039 and the `test_bo2400f_13*` family.
- RESUMED LINE (d-4): a request whose branch already exists on the hub resumes it (`line_of_work: resumed`), never resets or rebases it; ticket 05's readiness ingredient branches on this value.
- The generated ticket for a-1-ii named only `scripts/build.py` in files_touched; the real surface is the maker (04 python-coder, ac-fulfillment-gate x3). That is why the gate could never auto-set work_status.
- STARTING POINT (re-verify): `git show refs/wip/bo4300-attempt1:unit_tests/build_orchestration/test_bo_4300a_1_ii.py`, `refs/wip/bo4300-attempt1:unit_tests/build_orchestration/_bo_4300a_1_ii_fixtures.py` and the ticket-location hunks of `git show refs/wip/bo4300-attempt1 -- templates/scripts/worktree.py templates/scripts/worktree_git.py`.
- FILE-SIZE RATCHET: `templates/scripts/worktree.py` is at ~393 of 400 counted lines and `templates/scripts/worktree_git.py` near its limit (01 python-coder sign-off). Every addition therefore goes into the NEW module this ticket owns (see files_touched); the two core files are touched only to move code out and to wire the new module in. A new module needs its own NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py` and `scripts/build_deploy_manifest_helpers.py` (KI-TQ-004: no second tracked copy; the maker is deployed to `<install-root>/.leafcutter/scripts/<name>`, not `<install-root>/scripts/`, per 01 test-writer/python-coder).
- ANSWER TABLE: the status/code/exit table is owned by ticket 03 (BO-4300c-2 declares the full code enum). Do not add codes locally; if a code is missing from BO-4300c-2 it is a contract change, not a local edit.
- PROOF: tests run the DEPLOYED maker through ticket 02's locator (`unit_tests/build_orchestration/_workspace_maker_fixtures.py`), as a subprocess, against real temp repos with a real bare hub; no mock of git, no import of the maker module, never spawn `scripts/build.py`. Pin `newline="\n"` on fixture writes and isolate GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM (the CRLF drift found on 04 in the failed run). Use `AC_ENFORCE_STRICT=1` to see a genuine red baseline (the AC-enforcement plugin otherwise downgrades not-done-AC failures to xfail).
- HOOK HYGIENE (lessons from ticket 01): DECISION HISTORY entries need `HH:MM` and the `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/NN)` tail-tag on the entry's FIRST line; run `check_documentation.py` with NO `--file` flag (staged mode) before commit; run `check_doc_length.py` on every doc touched (300-line ratchet); stage every file in files_touched (01 shipped an ADR edit unstaged). Commits never spelled `git -C <path> commit`.
- SCOPE: the epic worktree is shared by every ticket. Edit only files_touched. If the fix needs another file, stop and get this ticket updated (CLAUDE.md TICKET MANDATE); the failed run stalled on exactly this (tickets 04, 14, 46, 59).

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300a-2**

- ONE SCHEME (Q4, DECIDED user 2026-09-28): the maker's single naming table normalises every request to the identity <kind>/<slug> for every kind (ticket, feature, ac, fastlane, epic, scratch); the slug is a deterministic lower-case kebab form of the raw identity, so EPIC-FilesStayWorkable, epic/files-stay-workable and the display title Files Stay Workable all give epic/files-stay-workable. A new line of work is named by the identity; the workspace lands at <landing-root>/<kind>/<slug> (landing root per BO-4300b-2); the answer's kind and slug are always the canonical ones. Distinct works never collide.
- LEGACY ALIASES (Q4): the legacy spellings are declared in that same table, keyed by kind, each entry with its reason -- epic <- EPIC-<Name> (feature skill); ac <- ac-authoring/<slug> (create-ac-worktree); fastlane <- fast-lane/<slug> (create-fastlane-worktree); ticket <- feature/<slug> (the retiring setup-ticket sub-command named ticket lines feature/<slug>; for kind feature that spelling is already canonical). A request in a legacy spelling resolves to the canonical identity and the same workspace; there is no second table or per-caller mapping.
- NEVER ORPHANED: when the hub carries a line of work for the identity only under a legacy spelling, ensure resumes THAT line (BO-4300d-4 semantics: line_of_work 'resumed', every commit kept, never reset, never pushed) and never starts a line under the canonical name beside it; the hub branch is never renamed. The answer's branch and the marker's branch name the actual branch; kind and slug stay canonical.
- NEVER TWINNED: when more than one spelling of the same identity already carries a line of work on the hub, the maker refuses with code AMBIGUOUS_LINE (status refused, exit 2; field lines [branch], added to the BO-4300c-2 contract) naming every such branch, and creates, moves, merges or renames nothing. A legacy git worktree registered in the main checkout for any spelling of the identity is refused OCCUPIED_LEGACY_WORKTREE wherever its folder is (BO-4300d-3-i), so a new clone is never made beside it.
- Matching is on the exact normalised identity, never a prefix or substring (the '_worktree_exists' prefix table and finalize's branch-substring match are retired).
- A re-request never abandons an existing line of work for a freshly named twin and never moves or resets its commits (F10, KI-BO-20260921 'abandons the epic worktree branch').

**BO-4300a-1-ii**

- The in-workspace location is the ticket's project-relative path (computed against the resolved project, never against cwd) re-rooted under workspace_path. The request's path must lie inside the resolved project; one outside it is a usage error (code USAGE) naming it, and --ticket with --kind scratch is a usage error.
- Existence and identity are checked on the finished workspace immediately before the answer is emitted: a regular file exists at ticket_path_in_worktree, and its bytes equal the ticket named in the request as it exists on the base the workspace was made from. An ok answer is never emitted with a ticket field that fails either check.
- Decision 3 governs content: the workspace takes the ticket only from its own base (origin/main for a new line, the resumed line for a resumed one). The maker never copies, writes or edits a ticket file from the main copy into a workspace.
- UNPUSHED TICKET (DECIDED, user 2026-09-27): when the requested ticket is absent from the workspace's base (reason 'absent') or present there with bytes that differ from the main copy's (reason 'differs'), the maker refuses with code TICKET_NOT_ON_BASE (status refused, exit 2). The message names the ticket's project-relative path and tells the caller to push it and ask again; the answer carries ticket_path (the path as requested) and reason, and -- like every non-ok answer -- neither workspace_path nor either ticket_path_in_worktree field. The maker never copies unpushed or uncommitted content in, and never treats 'differs' as ok with a warning.
- Order and clean-up for TICKET_NOT_ON_BASE: the check runs after the workspace's fetch and before its install build, so no build runs for a refused request. When the clone was made by THIS request it holds no work by construction, and the maker clears it before emitting the answer: the refusal leaves no folder at the workspace location and no INCOMPLETE remnant. A resumed line compares against the resumed line, not origin/main, and a pre-existing workspace is never cleared by this check.
- The answer fields are named ticket_path_in_worktree and ticket_path_in_worktree_posix (BO-4300c-2); the retiring set-up script's ticket_path_final and the charter's ticket_path_new are not emitted by the maker, not even as aliases, because both have been read as "the ticket inside the workspace" while meaning the input path.
- Caller fixes land in the SAME change set as this record (KI fix direction: "Fix the two prompt sites in the same change"): build-single-ticket's step-1 prompt via BO-4300a-1-ib and worktree-agent's ticket_path_new parsing via BO-4300f-2-ia. This record is not signed off while either caller still reads another field.

**BO-4300d-3-i**

- An old-style worktree (its .git is a gitfile pointing into the main checkout's .git/worktrees) at the location is refused OCCUPIED_LEGACY_WORKTREE with a message that it must be brought over first (BO-4300f-3); its folder, its commit and the main checkout's registration entry are untouched. Detecting it may read git metadata but must not run any git command that rewrites worktree admin state.
- NEVER TWINNED ACROSS THE MOVE (Q4 + Q5, DECIDED user 2026-09-28): the new landing root (BO-4300b-2) differs from where the old way put workspaces (<parent>/worktrees/<name>, a sibling EPIC-<Name> folder), so a check "at the location" alone would make a twin beside the old one. Before creating, ensure reads the main checkout's legacy worktree registrations (read-only) and refuses OCCUPIED_LEGACY_WORKTREE, with occupant.path the legacy folder, when any registration is on the canonical branch or on a declared legacy alias of the requested identity (BO-4300a-2), wherever its folder is. Matching is on the exact normalised identity, never a prefix or substring.

**BO-4300d-3**

- An occupied location is refused OCCUPIED with occupant {path, kind, branch}; the occupant is never modified, adopted, converted or reset, and the maker never picks another location (no suffixing) -- the substitute-location fallback is closed on the maker side.

**BO-4300d-4**

- When origin/<branch> exists with commits not on origin/main, ensure checks out that line (tracking origin/<branch>) and answers line_of_work 'resumed'; it never uses a force reset (-B onto origin/main) and never pushes. Only the hub's refs are consulted, never the main checkout's local branches (memo step 8). The fast lane's force-reset behaviour is retired by the migration (BO-4300f-1).
- Fresh lines still start at origin/main after the fetch (decision 3). See the resumed-line caveat recorded on BO-4300c-1.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300a-2 -- The same piece of work is always recognised as the same workspace
- [ ] AC-2: BO-4300a-1-ii -- A ready workspace made for a ticket states where that ticket is inside the workspace
- [ ] AC-3: BO-4300d-3-i -- A workspace for the same work made the old way is not quietly taken over
- [ ] AC-4: BO-4300d-3 -- A location already holding different work is left untouched and reported
- [ ] AC-5: BO-4300d-4 -- Asking for work whose line already exists on the shared project resumes that line

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300a-2 per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300a-1-ii per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300d-3-i per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300d-3 per `## Test Requirements`
- [ ] AC-5: red tests for BO-4300d-4 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300a-2 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure/locate CLI with --kind epic --slug <raw identity>; the maker performs normalisation.
- **BO-4300a-1-ii <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure --kind <kind> --slug <identity> --ticket <main-copy ticket path, absolute or project-relative>; the ready answer follows the BO-4300c-2 result contract, which carries the two ticket fields.
- **BO-4300d-3-i <- BO-4300d-3** (this ticket): Occupant refusal.
- **BO-4300d-3 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure CLI and landing-place rule.
- **BO-4300d-4 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure CLI.

### Delivers To

- **BO-4300a-1-ii -> llm-expert**: On an ok ensure answer requested with --ticket <path>: ticket_path_in_worktree (absolute, native spelling) and ticket_path_in_worktree_posix, both inside workspace_path, naming a file that existed when the answer was emitted. Both fields are ABSENT on every non-ok answer and on any answer to a request without --ticket. Consumers: build-single-ticket's step-1 prompt (BO-4300a-1-ib) and worktree-agent's answer parsing (BO-4300f-2-ia) take the ticket's working location ONLY from these fields -- never from the path they passed in, never from ticket_path_final or ticket_path_new.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

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
