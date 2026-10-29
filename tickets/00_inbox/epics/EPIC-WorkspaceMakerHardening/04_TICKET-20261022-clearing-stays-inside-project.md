---
title: "Clearing stays inside the project, keeps git's text out of the answer, and fails before deleting"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300e-2
  - BO-4300e-3
  - BO-4300c-2
  l3:
  - BO-4300e-2-i
  - BO-4300e-2-iii
  - BO-4300e-3-ii
status: done
ac_coverage: 5/5
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: medium
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M4
  - M5
  - M9a
  - M17
files_touched:
  - templates/scripts/worktree_remove.py
  - templates/scripts/worktree_ensure_state.py
  - unit_tests/build_orchestration/test_bo_4300e_2.py
  - unit_tests/build_orchestration/test_bo_4300e_2_i.py
  - unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  - unit_tests/build_orchestration/test_bo_4300e_3.py
  - unit_tests/build_orchestration/test_bo_4300e_3_ii.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 04: Clearing stays inside the project, keeps git's text out of the answer, and fails before deleting

## Actor / Goal
A user or workflow clears a workspace. The request should only ever remove one of this project's own
workspaces. It should answer in the contract's own words, and it should leave everything in place when
deleting the line on the shared project fails.

## Context
All references below are verified against the current tree, in `templates/scripts/worktree_remove.py`
unless stated otherwise.

- **M5 remove scope (HIGH; new AC BO-4300e-2-iii, A6).**
  - `cmd_remove` (line 242) accepts any `--path` that holds `.leafcutter/workspace.json`, including another
    project's workspace or a stray folder holding a copied marker.
  - It violates BO-4300e-2 and BO-4300b-2-i.
  - Fix:
    - Resolve the project: `--repo-root`, else the marker's `project_root`.
    - Require the path to be inside that project's landing place (`wl.landing_for(...)`, honouring a
      `--landing-root` override), with `wl.other_project_occupant(...)` None.
    - Anything else is `NOT_FOUND`, and nothing is deleted, fetched or pushed.
  - Port source: v1 13f88da31 `_find` / `verb_remove`.
- **Remote deletion failure (new AC BO-4300e-3-ii, A7).** At line 260, `wg.run_git(["push", "origin",
  "--delete", branch])` ignores its return code, and the local folder is deleted anyway.
  - Fix: delete the hub branch BEFORE any local deletion.
  - A failed push answers `GIT_FAILED` (status error, exit 1) with `step: "push origin --delete <branch>"`,
    and nothing local is deleted.
- **M4 remove (HIGH; BO-4300c-2 criterion "the underlying tools' own messages ... never appear in the
  answer").** Git's stderr is pasted into `message` at three sites:
  - line 81 (`git status failed: ...`);
  - line 107 (`git rev-list failed: ...`);
  - lines 120-121 (`git fetch origin failed ...: <stderr>`).
  - Fix: the message names the step, and a `step` field carries its short name (A2 item 4). `run_git`
    already forwards git's own output to stderr.
  - `wa.error_answer` / `_err` take extra fields, so this needs NO change to `worktree_answer.py`. This
    ticket must NOT edit `worktree_answer.py`; ticket 05 owns it.
- **M9a (BO-4300c-2: `holders [{pid, name}]` on PROCESS_HOLDS_FILES).** Lines 257-258 emit
  `processes=holders`, which carry psutil-shaped dicts. Answer `holders: [{"pid": int, "name": str}]`
  instead.
- **M17 (BO-4300e-2 IT1, e-2-i, e-2 criteria).**
  - This module becomes the one home of two shared helpers:
    - **Delete helper:** `_rmtree_onerror` (line 205) and `_delete_tree` (line 211). These already use
      `_long_path` (line 69, the `\\?\` extended-length prefix) and `onexc`. Expose them as a public
      whole-folder delete helper that tickets 06 (`worktree_identity.discard_new_clone`) and 08
      (`worktree_migrate._drop` / `_retire`) will call.
    - **`status -z` parser:** `_status_entries` (line 77) treats only an X-side `R`/`C` as having a source
      record (P11). It must also handle a Y-side rename, and return the source path. Expose it publicly
      for ticket 08, which replaces `worktree_migrate._status_paths`.
    - Port source: v1 13f88da31 `_changed_files`.
  - Dead code: `templates/scripts/worktree_ensure_state.py:389` `locate_ready_only` has no caller.
    `worktree_remove.cmd_locate` (line 59) is the live equivalent. Delete it.
- Tests use `make_project`, `run_maker` and `deployed_maker_path` from `_workspace_maker_fixtures.py`.
  The A7 fixture is a bare hub whose `hooks/update` rejects ref deletions (`$3` all zeros -> exit 1).

## Scope
1. Project-scoped `remove`, as in Context (A6).
2. Hub-branch deletion first, failing closed (A7).
3. Step-named messages plus a `step` field at the three git sites, with no git text in `message`.
4. `holders [{pid, name}]` on PROCESS_HOLDS_FILES.
5. One public delete helper and one public `status -z` parser (with the Y-side rename) in
   `worktree_remove.py`. Remove `locate_ready_only`.

## Acceptance Criteria
- [x] AC-1: BO-4300e-2-iii.
  - Setup: "shop" and "blog" each have a ready workspace "alpha", and a folder "stray" outside both landing
    places holds a copy of shop's marker.
  - `remove` requested from shop for blog's "alpha" is refused `NOT_FOUND`, stating that shop has no
    workspace there. So is `remove` for "stray".
  - Both folders are byte-identical before and after.
  - `remove` of shop's own "alpha" still answers ok/cleared.
- [x] AC-2: BO-4300e-3-ii. With a hub that refuses ref deletion, `remove --delete-remote-branch` of a
  workspace holding nothing unsent answers status error, code `GIT_FAILED`, exit 1, with a `step` naming
  the deletion on the shared project. The workspace folder and the hub branch are identical before and
  after.
- [x] AC-3: BO-4300c-2 (no tool text in the answer; `step`). When the hub is unreachable during `remove`'s
  unsent-work check, the answer is `FETCH_FAILED` with a `step` field. Neither `message` nor `step` contains
  any line of the maker's stderr (no `fatal:`).
- [x] AC-4: BO-4300c-2 (`holders [{pid, name}]`). A PROCESS_HOLDS_FILES refusal carries `holders`, a list of
  objects with exactly the keys `pid` (int) and `name` (str), and no `processes` field.
- [x] AC-5: BO-4300e-2 IT1 / e-2-i (M17). The shared status parser reports both paths of an X-side and a
  Y-side rename, and a workspace whose only change is a Y-side rename is refused `UNSENT_WORK`. Exactly one
  rmtree helper exists across `worktree_remove.py` and `worktree_ensure_state.py`, and `locate_ready_only`
  is gone.

## Test Requirements

```yaml
tests:
- name: test_clearing_another_projects_or_a_stray_folder_is_not_found_and_changes_nothing
  file: unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  covers:
  - BO-4300e-2-iii
  asserts: >-
    Two make_project fixtures "shop" and "blog" side by side, each ensuring "alpha", plus a "stray" folder
    holding a copy of shop's marker. run_maker remove from shop for blog's alpha and for stray answers
    NOT_FOUND. Both folders are byte-identical (tree digest) after, and remove of shop's alpha answers ok.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_failed_remote_branch_deletion_leaves_workspace_and_hub_line_in_place
  file: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  covers:
  - BO-4300e-3-ii
  asserts: >-
    make_project. The hub gets hooks/update rejecting deletions, and alpha's line is pushed. remove
    --delete-remote-branch answers error/GIT_FAILED, exit 1, and step names the deletion. The workspace
    tree digest is unchanged, and hub `rev-parse <branch>` is unchanged.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_remove_fetch_failure_message_carries_no_git_text
  file: unit_tests/build_orchestration/test_bo_4300e_2.py
  covers:
  - BO-4300c-2
  - BO-4300e-2
  asserts: >-
    A ready workspace whose origin is repointed to a missing path. remove answers FETCH_FAILED with a step
    field. No stderr line of the run appears in message or step, and 'fatal:' is absent from both.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_process_holds_files_names_holders_pid_and_name
  file: unit_tests/build_orchestration/test_bo_4300e_2.py
  covers:
  - BO-4300c-2
  - BO-4300e-2
  asserts: >-
    With a child process whose cwd is the workspace, remove refuses PROCESS_HOLDS_FILES, with holders ==
    [{pid, name}] (exact key set) and no processes key.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_y_side_rename_is_unsent_work_and_names_both_paths
  file: unit_tests/build_orchestration/test_bo_4300e_2_i.py
  covers:
  - BO-4300e-2-i
  asserts: >-
    A tracked file is renamed in the working tree and recorded with `git add -N` (status ' R'). The shared
    parser returns both the old and the new path, and remove refuses UNSENT_WORK listing them.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_one_delete_helper_and_no_dead_locate
  file: unit_tests/build_orchestration/test_bo_4300e_3.py
  covers:
  - BO-4300e-2
  asserts: >-
    An AST scan of the deployed worktree_remove.py and worktree_ensure_state.py finds exactly one function
    calling shutil.rmtree, and no locate_ready_only definition.
  framework: unittest
  type: behavioral
- name: test_forged_marker_branch_that_is_not_the_checked_out_branch_is_not_found
  file: unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  covers:
  - BO-4300e-2-iii
  asserts: >-
    A marker whose branch differs from the folder's checked-out branch is NOT_FOUND (exit 2), with and
    without --delete-remote-branch; the folder (.git digest) and the hub refs are unchanged.
  framework: unittest
  type: behavioral
  angle: failure
- name: test_a_folder_off_the_landing_slot_is_not_found_and_unchanged
  file: unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  covers:
  - BO-4300e-2-iii
  asserts: >-
    Copies of a ready workspace one level too deep, one too shallow, under an unknown kind, or without
    their own .git are NOT_FOUND (exit 2) and unchanged.
  framework: unittest
  type: behavioral
  angle: boundary
- name: test_holder_entry_never_raises_when_psutil_errors
  file: unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  covers:
  - BO-4300c-2
  asserts: >-
    In-process against the deployed module, _holder_entry returns {pid:int, name:str} when psutil raises
    NoSuchProcess or AccessDenied (Exception subclasses, not OSError).
  framework: unittest
  type: behavioral
  angle: failure
- name: test_protected_branches_are_never_deleted_on_the_hub
  file: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  covers:
  - BO-4300e-3-ii
  asserts: >-
    With --delete-remote-branch, a marker branch of main, master or the hub default is refused
    ON_PROTECTED_BRANCH (exit 2, `branch` field) before any fetch or push; the hub is unchanged.
  framework: unittest
  type: behavioral
  angle: discrimination
- name: test_an_unprotected_branch_is_deleted_on_the_hub_then_the_folder
  file: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  covers:
  - BO-4300e-3-ii
  asserts: >-
    Control: an ordinary pushed branch answers ok; the hub branch and the folder are gone.
  framework: unittest
  type: behavioral
  angle: criterion
- name: test_an_empty_marker_branch_is_not_found
  file: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  covers:
  - BO-4300e-3-ii
  asserts: >-
    A detached folder whose marker has no branch, with --delete-remote-branch, is NOT_FOUND (exit 2) and unchanged.
  framework: unittest
  type: behavioral
  angle: boundary
- name: test_an_option_like_marker_branch_is_not_found
  file: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  covers:
  - BO-4300e-3-ii
  asserts: >-
    A folder on branch "-x" with a marker saying "-x", with --delete-remote-branch, is NOT_FOUND (exit 2); the hub's "-x" survives.
  framework: unittest
  type: behavioral
  angle: boundary
- name: test_failed_local_delete_after_the_hub_branch_went_says_so
  file: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  covers:
  - BO-4300e-3-ii
  asserts: >-
    In-process, with the local delete forced to report a leftover after the hub branch was deleted, the
    answer is PROCESS_HOLDS_FILES with hub_branch_deleted true and a message saying the shared project's
    branch was already deleted; without the flag the hub branch survives and no such field appears.
  framework: unittest
  type: behavioral
  angle: failure
```

## Sign-offs
- [x] test-writer — 2026-10-22 10:31
- [x] python-coder — 2026-10-22 11:40
- [x] pr-reviewer — 2026-10-22 13:40
- [x] ac-validator — 2026-10-22 14:10
- [x] ac-fulfillment-gate — 2026-10-22 12:21
- [x] commit — 2026-10-22 14:30

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-22 10:31 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written_and_red: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "worktree.py ensure (writes the real workspace marker, hub and landing place)"
    consuming_side: "worktree_remove.cmd_remove (reads that marker for project, branch, unsent verdict)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <deployed layout>/.leafcutter/scripts/worktree.py remove --path ... (CLI via subprocess, shared deployed layout)"
red_baseline:
  - test_name: test_clearing_another_projects_or_a_stray_folder_is_not_found_and_changes_nothing
    file: unit_tests/build_orchestration/test_bo_4300e_2_iii.py
    kind: assertion
    error: "AssertionError: 'OK' != 'NOT_FOUND' (remove from shop deleted blog's alpha and answered ok)"
  - test_name: test_failed_remote_branch_deletion_leaves_workspace_and_hub_line_in_place
    file: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
    kind: assertion
    error: "AssertionError: Tuples differ: ('ok', 'OK') != ('error', 'GIT_FAILED')"
  - test_name: test_remove_fetch_failure_message_carries_no_git_text
    file: unit_tests/build_orchestration/test_bo_4300e_2.py
    kind: assertion
    error: "AssertionError: False is not true : no step field: {'status': 'refused', 'code': 'FETCH_FAILED', 'message': \"git fetch origin failed in ...; cannot tell what is unsent: fatal: ... does not appear to be a git repository ...\"}"
  - test_name: test_remove_status_failure_message_carries_no_git_text
    file: unit_tests/build_orchestration/test_bo_4300e_2.py
    kind: assertion
    error: "AssertionError: False is not true : no step field: {'status': 'error', 'code': 'GIT_FAILED', 'message': \"Could not classify the work in ...: git status failed: fatal: bad boolean config value 'not-a-boolean' for 'status.aheadbehind'\"}"
  - test_name: test_process_holds_files_names_holders_pid_and_name
    file: unit_tests/build_orchestration/test_bo_4300e_2.py
    kind: assertion
    error: "AssertionError: 'processes' unexpectedly found in {'status': 'refused', 'code': 'PROCESS_HOLDS_FILES', ...}"
  - test_name: test_y_side_rename_is_unsent_work_and_names_both_paths
    file: unit_tests/build_orchestration/test_bo_4300e_2_i.py
    kind: assertion
    error: "AssertionError: Lists differ: ['LD_STAMP.txt', 'RENAMED_STAMP.txt'] != ['BUILD_STAMP.txt', 'RENAMED_STAMP.txt']"
  - test_name: test_one_delete_helper_and_no_dead_locate
    file: unit_tests/build_orchestration/test_bo_4300e_3.py
    kind: assertion
    error: "AssertionError: Lists differ: ['worktree_ensure_state.py:locate_ready_only'] != [] : dead code still defined"
Seven tests (new files test_bo_4300e_2_iii.py and test_bo_4300e_3_ii.py; additions to test_bo_4300e_2.py, _2_i.py, _3.py) are red for assertion reasons against the deployed maker. Run with AC_ENFORCE_STRICT=1: without it the FAC-ENFORCEMENT plugin downgrades the two tests covering the not-done ACs (BO-4300e-2-iii, BO-4300e-3-ii) to xfail. Not testable as written: (1) the shared status -z parser and the public delete helper have no declared public names, so they are proven through remove's behaviour (UNSENT_WORK listing both paths; AST scan for one rmtree caller) rather than by calling them; (2) the git rev-list failure site (M4 site 2) cannot be provoked reliably without corrupting refs, so only the fetch and status sites are covered; (3) the A6 message wording is only pinned to name the requested path, not the project name (both fixtures are dirs named "project"). Q1 wrong versions caught: push result ignored then folder deleted (3-ii); marker-only check without landing-place scope (2-iii, stray); X-side-only R/C source skip (2-i); a second rmtree function (3, AST count).

### 2026-10-22 11:40 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  red_baseline_green: true
  no_prior_passing_test_red: true
  worktree_answer_worktree_identity_untouched: true
red_baseline_results:
  - test_name: test_clearing_another_projects_or_a_stray_folder_is_not_found_and_changes_nothing
    result: green
  - test_name: test_failed_remote_branch_deletion_leaves_workspace_and_hub_line_in_place
    result: green
  - test_name: test_remove_fetch_failure_message_carries_no_git_text
    result: green
  - test_name: test_remove_status_failure_message_carries_no_git_text
    result: green
  - test_name: test_process_holds_files_names_holders_pid_and_name
    result: green
  - test_name: test_y_side_rename_is_unsent_work_and_names_both_paths
    result: green
  - test_name: test_one_delete_helper_and_no_dead_locate
    result: green
Edited worktree_remove.py and worktree_ensure_state.py only. Public shared helpers in worktree_remove: delete_whole_folder(path) -> str | None, parse_status_z(raw), status_entries(workspace). Remote branch absent on the hub is treated as already deleted (ls-remote exit 2); the verdict fetch uses --no-write-fetch-head so a refused remove leaves .git byte-identical. Duplicates left for tickets 06/08: worktree_identity.discard_new_clone rmtree, worktree_migrate._rmtree_onerror/rmtree and _status_paths; worktree_migrate also calls wrm._delete_tree (kept).


### 2026-10-22 12:10 — pr-reviewer (status: blocker)
feedback-id: (submit-failed)
[H-1] test_bo_4300e_3_ii.py run alone fails: circular import _workspace_maker_builders <-> _workspace_maker_fixtures (import _workspace_maker_fixtures first, or break the cycle).
[H-2] worktree_remove._holder_entry does not catch psutil.Error (NoSuchProcess/AccessDenied are not OSError): remove can crash with a traceback instead of PROCESS_HOLDS_FILES.
Sign-off withheld (pr-reviewer stays needed) until H-1 and H-2 are fixed. Full report returned to the caller.

### 2026-10-22 12:40 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  rework_h2_m1_m2_m3_m4_done: true
  linux_suite_green: true
Rework in templates/scripts/worktree_remove.py only (H-1 is a test-side import cycle, left to test-writer). H-2: _holder_entry never raises (int(pid) and psutil inside the try, broad except with fallback to the command-line name). M-1: remove acts only on <landing>/<kind>/<slug> (depth exactly 2, kind in worktree_git.VALID_KINDS), folder has its own .git, marker names the project, and `git branch --show-current` equals marker["branch"]; else NOT_FOUND. delete_whole_folder gets the resolved path. M-2: hub branch deleted then local delete fails: PROCESS_HOLDS_FILES gets hub_branch_deleted: true and the sentence "The branch on the shared project was already deleted." M-3: DECISION HISTORY entry for the ls-remote exit-2 rule. M-4: _fetch_origin retries a plain fetch when git says "unknown option" and restores/removes FETCH_HEAD.
Contract for new tests (with --delete-remote-branch): marker branch main, master, or the hub default (origin/HEAD) -> status refused, code ON_PROTECTED_BRANCH, exit 2, field branch; marker branch empty or starting with '-' -> NOT_FOUND (refused, exit 2). Forged marker branch differing from the checked-out branch, a folder not at depth 2 under the landing place, an unknown kind, or no own .git -> NOT_FOUND (exit 2). All refusals happen before any fetch, push or delete. Local delete failure after hub deletion: code PROCESS_HOLDS_FILES, hub_branch_deleted true. Linux ci_docker: 60 passed, 9 deselected.

### 2026-10-22 13:10 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written_and_green_guards: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "worktree.py ensure (writes the real marker, clone, hub)"
    consuming_side: "worktree_remove.cmd_remove (reads that marker; slot, branch and protected-branch rules)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <deployed layout>/.leafcutter/scripts/worktree.py remove --path ... (CLI via subprocess); the local-delete-failure and _holder_entry cases run the deployed worktree_remove in-process because a failed local delete / a psutil error cannot be forced reliably through the CLI on Linux"
H-1 fixed in test_bo_4300e_3_ii.py only: _workspace_maker_fixtures is imported before _workspace_maker_builders (as the sibling tests do); all five touched test files import and pass when run alone on Linux (ci_docker, AC_ENFORCE_STRICT=1): _2 7, _2_i 2, _2_iii 4, _3 7, _3_ii 6 (+3 subtests).
These are guard tests: production already exists, so they are green. Each was proven to go red by mutating templates/scripts/worktree_remove.py (restored afterwards, git diff clean): all six mutants below turned the named tests red (8 failures).
Wrong versions caught:
- no checked-out-vs-marker branch comparison -> test_forged_marker_branch_that_is_not_the_checked_out_branch_is_not_found (observed red)
- prefix-only landing check / no kind check / no own-.git check -> test_a_folder_off_the_landing_slot_is_not_found_and_unchanged (observed red; all four cases share one mutant, so the individual case guards are reasoned)
- `except OSError` in _holder_entry -> test_holder_entry_never_raises_when_psutil_errors (observed red)
- protecting only "main" -> test_protected_branches_are_never_deleted_on_the_hub (observed red: master and the hub default "trunk" subtests); deleting before the check or fetching first is reasoned (hub refs + .git digest incl. an unfetched "victim" branch)
- hub_branch_deleted flag dropped -> test_failed_local_delete_after_the_hub_branch_went_says_so (observed red); sentence dropped / hub branch deleted only after the local delete is reasoned
- empty / "-"-leading branch not refused -> test_an_empty_marker_branch_is_not_found, test_an_option_like_marker_branch_is_not_found (observed red; the "-x" case reached `git push origin --delete -x`)
- guard refusing every --delete-remote-branch -> control test_an_unprotected_branch_is_deleted_on_the_hub_then_the_folder (reasoned)
Notes: the local-delete failure is forced by mock.patch of delete_whole_folder (and _holding_programs -> []) in-process; it cannot be made to fail reliably through the CLI on Linux (the test user is root in the CI image and ignores read-only folders). The "-x" branch is created with update-ref/symbolic-ref because git refuses it porcelain-side. Vacuity: exact status/code/exit asserted; control rows present (unprotected branch, no-flag run); new inputs distinct from old (forged branch "victim" unknown to the workspace); the call count of the patched local delete is asserted == 1.
Not edited: any _workspace_maker_*.py helper, any production file.

### 2026-10-22 13:40 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Re-review: H-1 (import cycle) and H-2 (psutil.Error) resolved; each touched test imports alone; test_bo_4300e_3_ii + _2_iii pass (10 passed, AC_ENFORCE_STRICT=1). M-1..M-4 addressed. No new high findings.
Residual medium, non-blocking: detached-HEAD workspace is NOT_FOUND on remove (checked-out branch is None); "unknown option" fallback matches English git text only.

### 2026-10-22 14:10 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 5 ACs covered (store alignment script exit 0; no delivers_to/expects_from contract gaps: BO-4300e-2-iii and e-3-ii expect only e-2 / e-3, both in this diff). Test run reported by caller: Linux Docker, whole test_bo_4300* and bo_400e family green (2 skips, 0 failures), each touched test file also green alone.
AC-1 covered (BO-4300e-2-iii):
  implementation: templates/scripts/worktree_remove.py - _own_workspace (project = --repo-root else marker project_root; landing_for honouring --landing-root; other_project_occupant; _is_workspace_slot depth 2, valid kind, own .git; checked-out branch == marker branch), cmd_remove answers NOT_FOUND "This project has no workspace at <path>; nothing was changed." before any fetch, push or delete.
  test: test_clearing_another_projects_or_a_stray_folder_is_not_found_and_changes_nothing (unit_tests/build_orchestration/test_bo_4300e_2_iii.py:68); guards test_forged_marker_branch_that_is_not_the_checked_out_branch_is_not_found (:136), test_a_folder_off_the_landing_slot_is_not_found_and_unchanged (:162).
  clause check: criteria (blog alpha and stray refused with "no workspace at that location", both unchanged, shop's own alpha still cleared) matched; it_requirements 1 (resolve project, path in landing place, marker names project, else NOT_FOUND with nothing deleted/fetched/pushed) matched; it_requirements 2 and 3 (deployed maker via run_maker subprocess, real bare hub, isolated temp dirs) matched by tests using make_project/run_maker.
AC-2 covered (BO-4300e-3-ii):
  implementation: worktree_remove.py - cmd_remove calls _delete_hub_branch before _delete_tree; failed push returns GIT_FAILED (status error, exit 1) with step "push origin --delete <branch>"; no local deletion happens. Extras: _unsafe_hub_branch (protected/empty/option-like branch), hub_branch_deleted flag when the later local delete fails.
  test: test_failed_remote_branch_deletion_leaves_workspace_and_hub_line_in_place (test_bo_4300e_3_ii.py:55), plus :110, :131, :145, :156, :186.
  clause check: criteria (error naming the hub deletion, folder and hub line identical before/after) and it_requirements 1 (hub branch deleted first, GIT_FAILED/exit 1/step, update-hook-rejects-deletions fixture) matched; it_requirements 2 and 3 as above (the :186 local-delete-failure test is in-process by design, extra to the deployed test).
AC-3 covered (BO-4300c-2 no tool text, step):
  implementation: worktree_remove.py - unsent_work (FETCH_FAILED with step "git fetch origin"), status_entries / _unsent_commits return step names only.
  test: test_remove_fetch_failure_message_carries_no_git_text (test_bo_4300e_2.py:251).
AC-4 covered (BO-4300c-2 holders):
  implementation: worktree_remove.py - _holder_entry, cmd_remove emits holders=[{pid, name}], no processes.
  test: test_process_holds_files_names_holders_pid_and_name (test_bo_4300e_2.py:280); test_holder_entry_never_raises_when_psutil_errors (test_bo_4300e_2_iii.py:188).
AC-5 covered (BO-4300e-2 IT1 / e-2-i):
  implementation: worktree_remove.py - parse_status_z (R/C in either column returns both paths), status_entries, delete_whole_folder (sole shutil.rmtree); worktree_ensure_state.py - locate_ready_only and unused import worktree_admin removed.
  test: test_y_side_rename_is_unsent_work_and_names_both_paths (test_bo_4300e_2_i.py:65); test_one_delete_helper_and_no_dead_locate (test_bo_4300e_3.py:162).
Notes: ticket has no ## AC Coverage table, so only checkboxes, ac_coverage: 5/5 and sign-offs were updated. scripts/feedback/feedback_categories.yaml is absent, so submit_feedback was not run. Non-blocking (from pr-reviewer): detached-HEAD workspace is NOT_FOUND on remove; "unknown option" fallback matches English git text only. git commit not run.

### 2026-10-22 12:21 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
Resolved 6 ACs. BO-4300e-2-iii and BO-4300e-3-ii: implemented_by (worktree_remove.py, worktree_ensure_state.py) and covered_by (their test files, which carry the covers tags) added; mark_ac_done.py marked both done; schema check passed. e-2-i: worktree_remove.py appended to implemented_by, status left done. e-2 and e-3: worktree_remove.py appended to implemented_by; they stay in_progress, although all their children are now done so they would derive done. c-2 untouched (in_progress; later tickets still build its amendments). 5 AC files staged.

### 2026-10-22 14:30 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "fix(worktree): clearing stays inside the project and fails before deleting"; 13 staged files per orchestrator request. feedback_categories.yaml absent, so submit_feedback not run.
