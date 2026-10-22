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
status: todo
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
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
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
- [ ] AC-1: BO-4300e-2-iii.
  - Setup: "shop" and "blog" each have a ready workspace "alpha", and a folder "stray" outside both landing
    places holds a copy of shop's marker.
  - `remove` requested from shop for blog's "alpha" is refused `NOT_FOUND`, stating that shop has no
    workspace there. So is `remove` for "stray".
  - Both folders are byte-identical before and after.
  - `remove` of shop's own "alpha" still answers ok/cleared.
- [ ] AC-2: BO-4300e-3-ii. With a hub that refuses ref deletion, `remove --delete-remote-branch` of a
  workspace holding nothing unsent answers status error, code `GIT_FAILED`, exit 1, with a `step` naming
  the deletion on the shared project. The workspace folder and the hub branch are identical before and
  after.
- [ ] AC-3: BO-4300c-2 (no tool text in the answer; `step`). When the hub is unreachable during `remove`'s
  unsent-work check, the answer is `FETCH_FAILED` with a `step` field. Neither `message` nor `step` contains
  any line of the maker's stderr (no `fatal:`).
- [ ] AC-4: BO-4300c-2 (`holders [{pid, name}]`). A PROCESS_HOLDS_FILES refusal carries `holders`, a list of
  objects with exactly the keys `pid` (int) and `name` (str), and no `processes` field.
- [ ] AC-5: BO-4300e-2 IT1 / e-2-i (M17). The shared status parser reports both paths of an X-side and a
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
```

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
