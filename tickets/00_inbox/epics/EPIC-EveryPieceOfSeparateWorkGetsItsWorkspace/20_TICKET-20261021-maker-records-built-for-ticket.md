---
title: "The workspace maker records which ticket a single-ticket workspace's branch is built for (BO-400e-3-ix)"
ac_traceability:
  id: BO-400e-3-ix
  path: docs/acceptance-criteria/build-orchestration/BO-400-ticket-status-source-of-truth/BO-400e-3-ix.yaml
status: todo
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-21'
last_updated: '2026-10-21'
depends_on: []
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: medium
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - found-at-main-merge-b5b958875
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: needed
---

# 20: The workspace maker records which ticket a single-ticket workspace's branch is built for

## Actor / Goal
In order for finalization to know exactly which ticket a single-ticket branch delivers (BO-400e-3-ii, -viii and -ix), the workspace maker must record that ticket against the branch it makes. The record and the refusals main added to the retired setup script must not be lost when the epic merges.

## Context
- **Found:** 2026-10-21, merging origin/main (87 commits, merge b5b958875).
- **What main added to the retired script:** commits ec7236705 and a740aa5c6 added a built-for-ticket record to `setup_ticket_worktree.py`'s `cmd_setup_ticket`, through the new sibling module `scripts/build_orchestration/_setup_ticket_branch_record.py` (`_ticket_record_rel`, `_refuse_conflicting_record`, `_record_built_for_ticket`).
  - It writes `git config branch.<branch>.leafcutterTicket <ticket path>`, the ticket path relative to the repo.
  - It refuses to reuse a same-slug branch that already records a different ticket.
  - The `create-only`, `create-fastlane-worktree` and `create-ac-worktree` subcommands write no record.
- **Who reads it:** main's finalize now runs `finalize_closable_set.py`, which reads this record. Without it, finalization halts with `built_for_unknown`.
- **What the epic did:** it deleted the setup script (BO-4300f-2). The maker (`templates/scripts/worktree.py ensure --kind ticket`) does not write the record.
- **Broken test:** main's test `unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py` imports the deleted `_bo2400f13_fixtures` and drives the old script.
  - It and the now-orphaned `scripts/build_orchestration/_setup_ticket_fastlane_occupancy.py`, used only by the deleted script, are the BO-4300f-2 census's three hits.
  - Main also moved the fast-lane occupancy refusal (BO-2400f-13) into that module. The maker has its own occupancy refusal (`WORKSPACE_OCCUPIED`); confirm it covers the same cases.

## Scope
1. `worktree.py ensure --kind ticket` writes `branch.<branch>.leafcutterTicket` in the workspace it makes. It is read where finalization runs, i.e. the workspace clone. The value is the ticket path relative to the repository, the same form `_ticket_record_rel` produced. Use the module `_setup_ticket_branch_record.py` if it fits the maker's layout; otherwise move its logic into a `worktree_*.py` module.
2. A reused same-slug workspace whose branch already records a different ticket is refused by name, before any write. Recording the same ticket again is a no-op.
3. The kinds feature, fastlane, ac and scratch write no record.
4. Migrate `test_bo_400e_3_ix_setup_record.py` to drive the deployed maker, keeping every promise:
   - the record is written;
   - a conflicting ticket is refused;
   - no record is written for other kinds;
   - finalize reads the record back.
   Its linked checkouts use the exempt `link_checkout` helper. Never skip.
5. Delete `scripts/build_orchestration/_setup_ticket_fastlane_occupancy.py` if nothing but the retired script uses it. Show that the maker's occupancy refusal and its BO-4300 tests cover BO-2400f-13's promises (target path occupied; branch checked out elsewhere; refused before any write; discriminated payload). Report any gap instead of deleting.
6. The BO-4300f-2 census prints nothing.

## Acceptance Criteria
- [ ] AC-1: A maker-made ticket workspace records its ticket against its branch, and finalization reads it (BO-400e-3-ix).
- [ ] AC-2: A conflicting record is refused by name before any write; other kinds write none.
- [ ] AC-3: On Linux, the migrated test_bo_400e_3_ix_setup_record.py, main's BO-400e-3 finalize tests and the BO-4300 tests pass, and the census is empty.

## Test Requirements

```yaml
tests:
- name: test_ticket_workspace_records_its_ticket_against_its_branch
  file: unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
  covers:
  - BO-400e-3-ix
  asserts: The deployed maker's ensure --kind ticket leaves branch.<branch>.leafcutterTicket naming the ticket's repo-relative path in the workspace.
  framework: unittest
  type: behavioral
  angle: deployed
```

## Sign-offs
- [x] test-writer — 2026-10-21 14:00
- [x] python-coder — 2026-10-21 16:30
- [x] pr-reviewer — 2026-10-21 17:10
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-21 14:00 — test-writer (status: ok)
feedback-id: fb_2026-10-21_401322b0

Migrated `unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py` from the retired `setup-ticket` (and the deleted `_bo2400f13_fixtures`) to the DEPLOYED maker. It uses the BO-4300f-4 locator, `make_project`, and the `_bo_4300a_1_ii_fixtures` helpers. The one old-style checkout uses the exempt `link_checkout`, and the file spells no raw add/remove command. All 7 tests carry `# covers: BO-400e-3-ix`, and every promise is kept:
- `test_ticket_workspace_records_its_ticket_against_its_branch` (deployed): after `ensure --kind ticket --slug close-x --ticket <abs path>`, the workspace config holds `branch.ticket/close-x.leafcutterTicket = tickets/00_inbox/TICKET-20261015-Close_X.md`. The tree shows no diff, no commits ahead of origin/main and no ticket in the status.
- `test_record_round_trips_into_the_derivation_under_a_slug_that_hides_the_ticket` (seam): `--slug my-fix`, a sign-off commit in the workspace, then the REAL `finalize_closable_set.py derive` in that workspace. `built_for_ticket` is the recorded path, and the set is that ticket plus its source AC.
- `test_same_slug_different_ticket_is_refused_by_name_before_any_write` (discrimination): the answer is refused / `BUILT_FOR_OTHER_TICKET` / exit 2. It names `ticket/close-x` and the first ticket and has no `workspace_path`. The workspace files and marker, its `.git/config` bytes and the landing place are all byte-identical, and the record is kept.
- `test_same_ticket_after_moving_lanes_updates_the_record` (boundary, review M-7 kept): the same file name in a new lane gets an ok answer and the record is updated. A different file name is still refused, and the updated record is kept.
- `test_repeat_ensure_is_a_no_op_for_the_record`: the second ensure is re-readied, and exactly one record remains.
- `test_ticketless_kinds_record_nothing`: feature, fastlane and ac (each given `--ticket`) and scratch record nothing. A control row in the same project does record.
- `test_branch_without_record_is_not_guessed` (failure): a `feature/close-x` linked checkout with no record gives `undeterminable` / `built_for_unknown` and empty records.

Red baseline (Linux, ci_docker runner, AC_ENFORCE_STRICT=1): 6 failed, 1 passed. Each of the 6 failed on an assertion about the record being absent. Examples: `Lists differ: [] != ['tickets/00_inbox/TICKET-20261015-Close_X.md']`, and derive `built_for_ticket: None` / `built_for_unknown`. The passing test is the finalize-side not-guessed guard, which is already true. No collection or setup errors. Contract change: none. The BO-400e-3-ix criteria are unchanged; only the surface under test moved from the retired script to the maker, and the branch spelling moved from `feature/<slug>` to the maker's `ticket/<slug>`. Next: python-coder.

### 2026-10-21 16:30 — python-coder (status: ok)
feedback-id: fb_2026-10-21_2c83dfb2

Design:
- New stdlib maker module `templates/scripts/worktree_ticket_record.py`. It imports only `worktree_git`, `worktree_answer` and `worktree_identity`.
  - `conflict_refusal()` runs first in `_resume_workspace`, chained after the read-only `rescue_refusal` and before `clear_torn_markers` or any fetch, install or marker write. It refuses a ticket workspace whose config already records a ticket with a different file name. The code is the new `BUILT_FOR_OTHER_TICKET` (refused, exit 2), and the answer names `branch`, `recorded_ticket` and `ticket_path`. It returns nothing for other kinds or without `.git`, so INCOMPLETE still answers a torn folder and git never reads a parent repository. A failed read is `GIT_FAILED`.
  - `finish()` replaces `wi.attach_ticket(...) or answer` in `_install_and_mark`. On an ok ticket answer it writes `branch.<answer branch>.leafcutterTicket = <ticket project-relative POSIX path>`, the `_ticket_record_rel` form, with `--replace-all`. That is a no-op when the value is already exactly that. A write failure fails the request with `GIT_FAILED`.
- The record lives in the workspace clone's own config, which is where `finalize_closable_set.py` runs `git config --get-all`. A brand-new clone carries no record, so only a reused workspace can conflict.
- `_setup_ticket_branch_record.py` could not be imported from both layouts: it deploys under `scripts/build_orchestration/`, while the maker sits in `templates/scripts/` in the source layout and `<install>/scripts/` in the deployed one. Its logic moved into the new module and the sibling was deleted; `git grep` found no other user.
- Added `BUILT_FOR_OTHER_TICKET` to `worktree_answer.ALL_CODES`/`REFUSED_CODES`, and the code row plus the record note to `docs/reference/workspace-maker-answer.md`. Added the NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py`.

BO-2400f-13 occupancy: deleted `scripts/build_orchestration/_setup_ticket_fastlane_occupancy.py`, because `git grep` shows no user. The maker's own refusals and their BO-4300 tests cover the four promises:
- Occupied target path: `OCCUPIED` with `occupant.kind` other-line, other-project or plain-folder (`test_bo_4300d_3.py`, three cases).
- Branch checked out elsewhere: `OCCUPIED_LEGACY_WORKTREE` when the work's line is checked out in a linked worktree in its old folder while the location is free (`test_bo_4300d_3_i.py::test_legacy_worktree_in_its_old_folder_under_legacy_name_is_refused_not_twinned`).
- Refused before any write: occupant files, HEAD, commit and admin registration are unchanged, and no twin appears in the landing place (`test_occupant_files_and_line_of_work_unchanged`, `test_no_workspace_is_made_elsewhere_instead`, `test_legacy_worktree_commit_and_registration_unchanged`).
- Discriminated payload: `code` plus `occupant{path,kind,branch}`, never a `workspace_path` (BO-4300d-3 and c-2 tests).

No `# covers:` tags were added: no done BO-2400f-13* AC lost its proof. `unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py` still tags all five, and it passes.

Residual note for the AC owner (unchanged by this deletion; ticket 14 raised it already): parts of BO-2400f-13-i/-ii have no maker equivalent. These are the own-prior-attempt facts (uncommitted changes, pushed or PR state), the per-option `destructive` flags, and -i's "does not step back into its own leftover". The maker re-readies its own workspace by design (BO-4300d). These need superseding in the AC store. `BO-400e-3-ix.yaml`'s `implemented_by` still lists the deleted script and sibling; that is the same as the 68 other ACs that name the retired script, and is left for the ac-fulfillment-gate.

Ratchets (after `git add`): `check_file_size.py` passes, with `worktree.py` at 397 lines, under the 400 limit; the change is one line of wiring, one import and a 3-line history entry. `check_complexity.py` passes, and `check_docstrings.py` is clean. The census (`python -m unit_tests.build_orchestration.test_bo_4300f_2 --census`) prints nothing.

Linux verification (the ci_docker runner, with one added in-container `git add -A` so the build's tracked-source guard accepts the new staged module):
- The migrated test passes 7/7.
- The *400e_3* files, the `_bo400e3_finalize_harness` users, `test_bo_4300*.py`, `test_bo2400f_13_workspace_refusal_workflow.py`, `unit_tests/workflows/` and `unit_tests/ac_store/`: 2689 passed, 6 failed.
  - Five failures reproduce on origin/main 53c20b589 (container uid 0, so the unwritable-store setup cannot block a write): `test_acd_2100a_4::test_reported_write_failure_matches_what_is_on_disk` and four in `test_bo2400e_3_i_unwritable_store.py`.
  - One was a nested-pytest 580 s timeout under `-n 8` (`test_bo4500a_5_viii...::test_fast_lane_ac_id_requests_behave_as_before`). It passes in isolation on this tree.
- Rerun after the final `.git` guard: the migrated test, `test_bo_4300c_2.py`, `test_bo_4300_docs.py` and that bo4500a test give 22 passed.

### 2026-10-21 17:10 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-21_3b741d9c

No high-confidence findings. Checked against the staged diff and origin/main:
- Location: the record goes in the workspace clone's own config; `_fcs_derive.recorded_ticket` runs `git config --get-all branch.<b>.leafcutterTicket` with `-C <worktree>`, so it reads the same place. Migrated seam test (derive under a hiding slug) passes.
- Value form: `ticket.rel.as_posix()` is the project-relative POSIX path, the same as main's `_ticket_record_rel`; `--ticket` absolute (build-ticket.js, skill) or relative both resolve to it.
- Refusal order: `conflict_refusal` runs in `_resume_workspace` right after the read-only `rescue_refusal` and before any write; the test checks files, marker, `.git/config` bytes and landing place byte-identical.
- Lane move: compared by file name as main did; the record is rewritten by `--replace-all`. Other kinds return before any write; the control-row test covers it.
- Test: all 7 of main's promises kept, none weakened; dropped the deployed/template dual loop (template script is gone) and the "no second worktree" count, replaced by the stronger byte-identical snapshot. 7 passed locally.
- Occupancy deletion: no remaining user; OCCUPIED / OCCUPIED_LEGACY_WORKTREE tests (4300c_2, 4300d_3, 4300d_3_i) cover target occupied, branch elsewhere, refused before write, discriminated payload.
[medium, noted] BO-2400f-13-i/-ii own-prior-attempt facts (uncommitted/pushed state, destructive option flags) have no maker equivalent; the ticket already records this for the AC owner.
[low, noted] A ticket outside the project is now a USAGE refusal instead of main's warning and no record; stricter and consistent with `resolve_ticket`.
