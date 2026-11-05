---
title: "The cut-over clones the main checkout, uses the canonical identity, defers readiness and loses nothing silently"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300f-3
  - BO-4300a-2
  l3:
  - BO-4300f-3-iii
  - BO-4300f-3-iv
status: done
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
ac_coverage: 5/5
depends_on:
  - 04_TICKET-20261022-clearing-stays-inside-project.md
  - 06_TICKET-20261022-work-identity-safe-slugs-canonical-first.md
  - 07_TICKET-20261022-read-only-verbs-refuse-and-answer-contract-shape.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M2
  - M4
  - M6
  - N6
  - M10
  - M17
  - N7
  - P9
files_touched:
  - templates/scripts/worktree_migrate.py
  - templates/scripts/worktree.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/worktree_migrate_guards.py
  - templates/scripts/worktree_migrate_carry.py
  - templates/scripts/worktree_remove.py
  - docs/components.json
  - scripts/build_phases_script_deploy_standalone.py
  - docs/architecture/components/worktree-manager.md
  - unit_tests/build_orchestration/test_bo_4300f_3.py
  - unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
  - unit_tests/build_orchestration/test_bo_4300f_3_iii.py
  - unit_tests/build_orchestration/test_bo_4300f_3_iv.py
  - unit_tests/build_orchestration/_bo_4300f_3_keep_fixtures.py
  - unit_tests/build_orchestration/test_bo_4300f_3_carry.py
  - unit_tests/build_orchestration/test_bo_4300f_3_keep.py
  - unit_tests/build_orchestration/test_bo_4300f_3_states.py
# out_of_scope: changed by tickets 01-07 and 09, merged into the epic commit (27c095a2d)
# this lane starts from; the scope guard diffs the whole branch against main.
out_of_scope:
  - scripts/suite_performance/_shared_layout_producer.py
  - scripts/suite_performance/_shared_layout_seed.py
  - templates/scripts/commit_guardian/ensure_precommit_config.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_canaries.py
  - templates/scripts/worktree_ensure_state.py
  - templates/scripts/worktree_ensure_steps.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_identity.py
  - templates/scripts/worktree_log_root.py
  - templates/scripts/worktree_ticket_record.py
  - templates/workflows-js/_shared/workspace-answer.js
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/quick-fix.js
  - unit_tests/_plan_feature_e2_runner.py
  - unit_tests/_workflow_engine_defaults.py
  - unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
  - unit_tests/build_orchestration/_bo_4300a_2_probe.py
  - unit_tests/build_orchestration/_bo_4300f_2_fixtures.py
  - unit_tests/build_orchestration/_workspace_maker_builders.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
  - unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
  - unit_tests/build_orchestration/test_bo_4300a_1_budgets.py
  - unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  - unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia_marker.py
  - unit_tests/build_orchestration/test_bo_4300a_1_marker_survival.py
  - unit_tests/build_orchestration/test_bo_4300a_1_route_shape.py
  - unit_tests/build_orchestration/test_bo_4300a_1_same_location.py
  - unit_tests/build_orchestration/test_bo_4300a_2.py
  - unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  - unit_tests/build_orchestration/test_bo_4300b_4_links.py
  - unit_tests/build_orchestration/test_bo_4300c_1_independence.py
  - unit_tests/build_orchestration/test_bo_4300c_1_verify_readonly.py
  - unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
  - unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  - unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  - unit_tests/build_orchestration/test_bo_4300c_4_i.py
  - unit_tests/build_orchestration/test_bo_4300d_1.py
  - unit_tests/build_orchestration/test_bo_4300e_1_i_alias.py
  - unit_tests/build_orchestration/test_bo_4300e_1_shapes.py
  - unit_tests/build_orchestration/test_bo_4300e_2.py
  - unit_tests/build_orchestration/test_bo_4300e_2_i.py
  - unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  - unit_tests/build_orchestration/test_bo_4300e_3.py
  - unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  - unit_tests/build_orchestration/test_bo_4300f_4.py
  - unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
  - unit_tests/prompt_assembly/test_build_feature_flatten_wiring.py
  - unit_tests/test_bp_900g_6_paths.py
  - unit_tests/test_finalize_feature_preflight_branch_detection.py
  - unit_tests/test_workflow_dual_engine.py
  - unit_tests/workflows/_bo2400f5iii_fixtures.py
  - unit_tests/workflows/_bo4000_fixtures.py
  - unit_tests/workflows/test_acd_2100a_1.py
  - unit_tests/workflows/test_acd_2100a_5.py
  - unit_tests/workflows/test_bo2400f5iii_declined_step_core.py
  - unit_tests/workflows/test_bo2400f_13_workspace_refusal_workflow.py
  - unit_tests/workflows/test_bo2400f_3_i_worktree_verify_workflow.py
  - unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py
  - unit_tests/workflows/test_bo_1500a_5_i_dual_engine.py
  - unit_tests/workflows/test_fast_lane_ship_structure.py
  - unit_tests/workflows/test_fin_100h_refusal_not_success.py
  - unit_tests/workflows/test_finalize_feature_preflight.py
  - unit_tests/workflows/test_finalize_pre_merge_safety_gate.py
  - unit_tests/workflows/test_quick_fix_escalation_and_topology.py
  - unit_tests/workflows/test_quick_fix_guard_halts.py
  - unit_tests/workflows/test_quick_fix_worktree_invariant.py
  - unit_tests/workflows/test_tq_600a_13_xx_finalize_hold.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 08: The cut-over clones the main checkout, uses the canonical identity, defers readiness and loses nothing silently

## Actor / Goal
A user runs the one-off cut-over of old-style (linked) workspaces. Each old workspace should end up in one
of three states:
- brought over to its canonical place under its canonical identity, but not called ready until it is
  proven ready;
- retired, with any ignored content it deletes reported;
- left exactly as it is and listed for a decision, when it cannot be carried over exactly.

## Context
All references are verified against the current tree, in `templates/scripts/worktree_migrate.py` unless
stated otherwise.

- **M2 migrate (HIGH; ADR-018 Amendment 1 A1.1; BO-4300a-1 IT3 as amended by A1).** `_git_steps`
  (line 225) clones the HUB with `--local` (line 229).
  - Fix: clone `str(ctx.repo_root)`, then re-point origin at `ctx.hub` and run a pruning fetch from the hub,
    as ticket 05 does for ensure.
  - The following `fetch <repo_root> +refs/heads/<b>:refs/heads/<b>` (line 230) is still needed after the
    prune, because a local-only legacy line has no hub ref.
- **M4 migrate (BO-4300c-2 criterion).** At line 236, `git {cmd[0]} failed: {proc.stderr.strip()}` puts
  git's text into the report's `reason`. Name the step instead; git's text stays on stderr.
- **M6 / N6 (MEDIUM-HIGH; BO-4300f-3 criteria as amended by A8, option 1, plus the new IT;
  BO-4300c-1-ii).** `_marker` (line 213) writes `state: "ready"` (line 219) with no install build and no
  canary.
  - Fix:
    - Write `state: "creating"`.
    - Add `next: "ensure --kind <k> --slug <s>"` to the `brought_over` entry. The report names, for each
      brought-over workspace not yet shown ready, the one request that makes it ready.
  - That ensure must answer `workspace_action: "completed"` and `line_of_work: "resumed"`, and keep every
    brought-over commit and every uncommitted and untracked file byte-identical. Its clean-tree check and
    canaries never refuse on, or touch, the brought-over content.
  - Today a `creating` marker that is already checked out takes `worktree.py` `_resume_workspace`'s
    `head_state` path (lines 236-243), and `line_of_work` comes from `head_state`. The marker's recorded
    `resumed` must win there. That is why this ticket owns `worktree.py` in wave 4.
  - `worktree_readiness.tree_is_clean` (line 92) only looks at tracked changes, which `work_set_aside` puts
    aside. Edit `worktree_readiness.py` only if the canaries prove otherwise; it is listed so that the
    edit is owned.
- **M10 cut-over (MEDIUM; BO-4300f-3 IT2 as amended by A4; BO-4300a-2).** `identity_for` (line 117) tries
  the declared aliases BEFORE the canonical prefixes. So `feature/x` became kind `ticket` and landed in
  `<landing>/ticket/x`, and a later `ensure --kind feature --slug x` made a second workspace on the same
  line.
  - Fix: canonical prefixes first, declared aliases second, and never two identities.
  - A slug that `wi.slugify` cannot normalise (ticket 06) is unmappable. It goes to `needs_decision`, never
    a guess.
  - Ticket 06 removes the `ticket <- feature/` alias itself.
- **M17 (BO-4300e-2 IT1).** Replace `_rmtree_onerror` (line 101) and `_drop` (line 107) with the shared
  delete helper, and `_status_paths` (line 160, X-side rename only) with the shared `status -z` parser.
  Ticket 04 exposes both from `worktree_remove.py`.
- **N7 (new AC BO-4300f-3-iv, A9b, option R).** `_retire` (line 274) deletes the folder via
  `wrm._delete_tree` without reporting its git-ignored content.
  - Fix: list that content from git's own ignored listing (`status --ignored --porcelain=v1 -z`), naming a
    wholly ignored folder as that folder.
  - Report it as `ignored_removed: [path]` on the retired entry. `--preview` lists the same paths before
    anything is deleted.
- **P9 (new AC BO-4300f-3-iii, A9).** Not detected today:
  - An operation in progress: merge, rebase (both backends), cherry-pick, revert or bisect, read from the
    registration's own admin dir (`registrations`, line 84).
  - Stash entries. These are repository-wide, so a stash counts for the workspace whose branch it was made
    on.
  - Staged changes. `_carry` (line ~187) copies bytes only, so the index is lost. Either carry the index or
    send the entry to `needs_decision`.
  - A user lock, i.e. a `locked` reason other than WSL's `initializing` (line 96 handles only the stuck
    `initializing` case). v1 sends it to `needs_decision`.
  - Each of these sends the entry to `needs_decision` with its reason. No folder, register entry, stash
    entry or branch changes, and the preview reports the same reasons.
  - Port source: v1-UNCOMMITTED `workspace_migrate.py` (`_OPERATIONS`, `_operation`, stash detection, the
    `_blocker` cases, locked -> needs_decision). It exists only in the WSL worktree
    `/home/henzeh/projects/leafcutter/worktrees/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, which was
    not verifiable from this checkout.
- **Fixtures.** Use `legacy_worktree(project, name, unsent=...)` (the one exempt creator of old-style
  workspaces) and `start_merge` from `_workspace_maker_fixtures`. Write the user lock as the registration's
  `locked` file directly. Test files must not spell the raw linked-checkout add/remove command (BO-4300f-2
  census).

## Scope
1. Clone the main checkout in `_git_steps` (A1), with step-named reasons.
2. Deferred readiness (A8): a `creating` marker, the `next` hint, and ensure's completion as
   `completed`/`resumed` with the content byte-identical.
3. Canonical-first identity resolution.
4. Use the shared delete helper and status parser.
5. `ignored_removed` on retired entries, and in the preview (A9b).
6. The P9 blockers, sent to `needs_decision` with their reasons, in both the run and the preview (A9).

## Acceptance Criteria
- [x] AC-1: BO-4300f-3 (A8). After the cut-over brings over a legacy `feature/a` with an unpushed commit, an
  uncommitted edit and an untracked file:
  - its marker state is `creating`, and `verify` answers `INCOMPLETE`;
  - its report entry carries `next == "ensure --kind feature --slug a"`;
  - running that ensure answers ok, `workspace_action == "completed"`, `line_of_work == "resumed"`;
  - the commit, the edit and the untracked file are byte-identical afterwards.
- [x] AC-2: BO-4300f-3 IT2 / BO-4300a-2 (A4). After the cut-over of a legacy `feature/x`,
  `ensure --kind feature --slug x` answers the same `workspace_path` the cut-over reported, with
  `workspace_action` in {completed, re-readied}. The hub and the workspace hold exactly one line for x.
- [x] AC-3: BO-4300f-3-iii (A9). Legacy workspaces "m" (merge with an unresolved conflict), "s" (a stash
  made on its branch), "i" (a staged, uncommitted change) and "l" (locked, reason "on USB drive") are
  handled as follows:
  - "m", "s" and "l" are listed in `needs_decision`, each with its reason;
  - "i" is either brought over with the change still staged and its content identical, or listed;
  - no folder, registration, stash entry or branch of the four changes;
  - the preview reports the same reasons.
- [x] AC-4: BO-4300f-3-iv (A9b). Retiring a legacy workspace holding nothing unsent but holding ignored
  `.env.local` and `build/` removes its folder. Its retired entry lists `ignored_removed` containing
  `.env.local` and `build/`, and `--preview` run first lists the same paths and deletes nothing.
- [x] AC-5: BO-4300a-1 IT3 (A1) / BO-4300c-2 (M2, M4 migrate). A brought-over clone's origin is the hub,
  some object file under its `.git/objects` has a link count greater than 1, and no `needs_decision` reason
  contains a line of git's stderr (no `fatal:`).

## Test Requirements

```yaml
tests:
- name: test_brought_over_workspace_is_not_ready_until_proven
  file: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
  covers:
  - BO-4300f-3
  asserts: >-
    make_project, then legacy_worktree(project, 'feature/a', unsent=True), plus an uncommitted edit and an
    untracked file. run_maker migrate-legacy, then:
    the marker state is 'creating';
    verify answers INCOMPLETE;
    the brought_over entry next == 'ensure --kind feature --slug a';
    run_maker that ensure answers ok with workspace_action 'completed' and line_of_work 'resumed';
    the commit sha, the edit bytes and the untracked bytes are unchanged.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_legacy_feature_line_is_one_workspace_whichever_kind_finds_it
  file: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
  covers:
  - BO-4300f-3
  - BO-4300a-2
  asserts: >-
    Cut over a legacy feature/x holding unsent work, then run_maker ensure --kind feature --slug x. The
    workspace_path equals the cut-over's reported path (under <landing>/feature/x, never ticket/x), the
    landing place holds one folder for x, and the hub and workspace hold one branch for x.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_work_that_cannot_be_carried_exactly_keeps_the_old_workspace
  file: unit_tests/build_orchestration/test_bo_4300f_3_iii.py
  covers:
  - BO-4300f-3-iii
  asserts: >-
    Four legacy_worktree fixtures: m (start_merge with an unresolved conflict), s (git stash on its
    branch), i (a staged change) and l (the registration's locked file reads 'on USB drive'). The preview
    and then the run list m, s and l in needs_decision with distinct reasons, and list i either there or
    as brought over with `git diff --cached` identical. The folder digests, registration files,
    `git stash list` and branch tips of all four are unchanged.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_retiring_reports_the_ignored_files_it_deletes
  file: unit_tests/build_orchestration/test_bo_4300f_3_iv.py
  covers:
  - BO-4300f-3-iv
  asserts: >-
    A legacy_worktree with nothing unsent, a .gitignore listing .env.local and build/, and both present.
    --preview lists ignored_removed ['.env.local', 'build/'] and the folder still exists. The real run
    removes the folder, and its retired entry has the same ignored_removed.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_brought_over_clone_is_hardlinked_from_main_checkout_and_reasons_carry_no_git_text
  file: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
  covers:
  - BO-4300f-3
  asserts: >-
    After bringing over feature/a, the brought-over clone's remote.origin.url equals the hub and some file
    under .git/objects has st_nlink > 1. With a legacy line whose checkout is forced to fail, the
    needs_decision reason names the step and contains no 'fatal:'.
  framework: unittest
  type: behavioral
  angle: deployed
```

## Sign-offs
- [x] test-writer — 2026-10-22 18:30
- [x] python-coder — 2026-10-22 20:10
- [x] pr-reviewer — 2026-10-22 16:42
- [x] ac-validator — 2026-10-22 17:10
- [x] ac-fulfillment-gate — 2026-10-22 18:40
- [x] commit — 2026-10-22 21:00

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-22 18:30 — test-writer (status: ok)
feedback-id: (submit-failed)
Tests written (all RED on Linux via ci_docker_add.sh, all assertion-kind reds). The three BO-4300f-3 tests live in the NEW
file test_bo_4300f_3_cutover.py (MigrateCase's home test_bo_4300f_3.py is imported by f_3_i/_ii and kept untouched).
Extra tests beyond the table: empty-slug guard (feature/---), and an ast check that the cut-over no longer defines
_rmtree_onerror/_drop/_status_paths (M17). NOT red today: test_legacy_feature_line_is_one_workspace_whichever_kind_finds_it
(ticket 06 already removed the ticket<-feature/ alias, so canonical-first has no remaining observable difference); it guards
against regression only.
red_baseline:
  - test_name: test_brought_over_workspace_is_not_ready_until_proven
    file: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
    kind: assertion
    error: "AssertionError: 'ready' != 'creating'"
  - test_name: test_legacy_line_with_no_usable_name_is_left_for_a_decision
    file: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
    kind: assertion
    error: "feature/--- is not in needs_decision (it was brought_over to <landing>/feature)"
  - test_name: test_cut_over_uses_the_shared_delete_and_status_helpers_not_its_own_copies
    file: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
    kind: assertion
    error: "Items in the first set but not the second: '_drop' '_status_paths' '_rmtree_onerror'"
  - test_name: test_brought_over_clone_is_hardlinked_from_main_checkout_and_reasons_carry_no_git_text
    file: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
    kind: assertion
    error: "False is not true : no object file has st_nlink > 1: not a clone of the main checkout (and, with that line bypassed, 'fatal:' found in the reason)"
  - test_name: test_work_that_cannot_be_carried_exactly_keeps_the_old_workspace
    file: unit_tests/build_orchestration/test_bo_4300f_3_iii.py
    kind: assertion
    error: "m is not listed for a decision (m brought over; s and l retired)"
  - test_name: test_retiring_reports_the_ignored_files_it_deletes
    file: unit_tests/build_orchestration/test_bo_4300f_3_iv.py
    kind: assertion
    error: "Lists differ: [] != ['.env.local', 'build/']"
reachability_entry_point_answer: resolved (CLI via subprocess: worktree.py migrate-legacy / ensure / verify, deployed copy)
cross_layer_seam_answer: covered -- producing side migrate-legacy's brought-over marker, consuming side ensure/verify on that marker

### 2026-10-22 19:40 — python-coder (status: handoff)
feedback-id: (submit-failed)
handoff_target: test-writer
Production change is in place (worktree_migrate.py, new worktree_migrate_guards.py, one line in worktree.py, NAMED entry + components.json).
5 of the 6 red_baseline tests are green on Linux. The 6th, test_brought_over_workspace_is_not_ready_until_proven, passes every
production-side assertion (marker 'creating', verify INCOMPLETE, `next`, ensure ok/completed/resumed, commit sha and bytes identical)
and fails ONLY on its own `git status --porcelain` assertion (classification: test_drift). Two defects in that assertion:
(1) the project has no .gitignore for the fixture install's output, so a completed workspace legitimately also shows
`?? .leafcutter/` and `?? INSTALLED_MARKER.txt`; (2) `self.git` strips its output, so the first status line loses its leading space
and `" M README.md"` can never match. Production stays unchanged. test-writer: filter those two install artifacts and compare
stripped lines (e.g. sorted(l.strip() ...) == ["?? UNTRACKED_NOTES.txt", "M README.md"]). A probe copy with exactly that change
passed on Linux, including assert_completed_marker_has_full_checks (build_ok True, verify ok).
red_baseline_results:
  - test_name: test_brought_over_workspace_is_not_ready_until_proven
    result: red (test_drift, status assertion only)
  - test_name: test_legacy_line_with_no_usable_name_is_left_for_a_decision
    result: green
  - test_name: test_cut_over_uses_the_shared_delete_and_status_helpers_not_its_own_copies
    result: green
  - test_name: test_brought_over_clone_is_hardlinked_from_main_checkout_and_reasons_carry_no_git_text
    result: green
  - test_name: test_work_that_cannot_be_carried_exactly_keeps_the_old_workspace
    result: green
  - test_name: test_retiring_reports_the_ignored_files_it_deletes
    result: green

### 2026-10-22 19:10 — test-writer (status: ok)
feedback-id: (submit-failed)
(classification: test_drift) test_brought_over_workspace_is_not_ready_until_proven: its final git-status check was stale. self.git strips output, so " M README.md" could never match, and the completed workspace legitimately shows the install's own untracked output. Fixed in test_bo_4300f_3_cutover.py only: stripped lines are compared, and exactly "?? .leafcutter/" and "?? INSTALLED_MARKER.txt" are filtered out by name, so the work check is ["?? UNTRACKED_NOTES.txt", "M README.md"]. No production change. Ran the three test files on Linux (ci_docker_add.sh): 7 passed against the coder's work. The _iii test accepts both listing and carrying the staged change i.

### 2026-10-22 20:10 — python-coder (status: ok)
feedback-id: (submit-failed)
The test-writer's corrected status assertion is green on Linux together with the production change from the 19:40 handoff.
red_baseline_results:
  - test_name: test_brought_over_workspace_is_not_ready_until_proven
    result: green
  - test_name: test_legacy_line_with_no_usable_name_is_left_for_a_decision
    result: green
  - test_name: test_cut_over_uses_the_shared_delete_and_status_helpers_not_its_own_copies
    result: green
  - test_name: test_brought_over_clone_is_hardlinked_from_main_checkout_and_reasons_carry_no_git_text
    result: green
  - test_name: test_work_that_cannot_be_carried_exactly_keeps_the_old_workspace
    result: green
  - test_name: test_retiring_reports_the_ignored_files_it_deletes
    result: green

### 2026-10-22 16:42 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Handoff to python-coder: two high-confidence work-loss paths in the bring-over failure branch and one lock-guard gap. Read-only review of the staged diff; the deployed tests need POSIX flock, so they were read, not run, on this Windows host.
- [H-1] worktree_migrate.py `_bring_over`: when `_retire` fails after the verified clone exists, the clone is deleted. A partial folder delete (a program holds a file) leaves the old folder incomplete, and a failed admin delete happens after the old folder is already gone. In both cases deleting the clone loses uncommitted and untracked work. Keep the clone unless the old folder is still intact.
- [H-2] worktree_migrate_guards.py `user_lock`: `startswith("initializing")` lets a user lock with a reason such as "initializing my env" through, and it also applies when the folder exists. The WSL exception should be the exact text and only when the folder is missing (the `stuck` case).
- [M-1] `stashed_on` returns False when `git stash list` fails (fail-open on a delete guard). Return unknown and keep the workspace, as `has_staged_changes` does.
- [M-2] No re-check of the old folder between the lossless proof and the delete; work saved in between is lost.
- [M-3] The `sequencer` folder (multi-commit cherry-pick or revert) is not an operation marker. Skip-worktree and assume-unchanged edits are invisible to status.
- [M-4] A9b judgement: `.env` and other ignored files are not carried over for brought-over entries. They are listed in `ignored_removed` and the preview, which satisfies the approved option R. They are gone if the user skips the preview, so carrying them over would be safer.
- A8 safe: a normal creating marker has no `line_of_work` key, so no false 'resumed'. A4, slug guard, M17, A1 and manifest registration verified. Missing tests: only the merge op state is tested (not rebase, cherry-pick, revert or bisect).

### 2026-10-22 20:40 — test-writer (status: ok)
feedback-id: (submit-failed)
Tests for the pr-reviewer work-loss findings (new files; no production edits). Red check: the three new files plus the shared base were run on Linux against the ORIGINAL branch HEAD (before any ticket-08 production code): 12 tests red, assertion-kind, and the M-6 operation-state test red for 3 of 5 states (before I required the reason to name the operation it passed by accident, because those workspaces were refused for an unrelated "no identity" reason). Against the coder's current work all 20 tests of the ticket's six files pass.
- _bo_4300f_3_keep_fixtures.py: KeepCase + a driver that runs the DEPLOYED cut-over in a separate process with one collaborator patched (delete_whole_folder, unsent_work, worktree_migrate_carry.snapshot, or worktree_git.run_git), so no module state leaks.
- test_bo_4300f_3_keep.py: H-1 (old folder / registration delete fails -> clone kept with uncommitted + untracked files, reason names both locations); H-2 (lock "initializing my env", exact "initializing" on a present folder, "on USB drive" kept; WSL exact text on a missing folder still removed); M-1 (failing `git stash list` -> "could not" reason); M-2 (file written after the proof, and after the snapshot, keeps the folder; a control is retired).
- test_bo_4300f_3_states.py: M-6 five REAL operation states as subTests (rebase-merge, rebase-apply, cherry-pick, revert, bisect); M-3 sequencer-only cherry-pick, skip-worktree edit, stash on a detached HEAD (control: a branch workspace is still retired).
- test_bo_4300f_3_carry.py: M-3 empty directory tree carried, symlink carried as a symlink (skips where symlinks cannot be made); M-4 ignored .env.local and build/ byte-identical in the new workspace, old .leafcutter/ listed in ignored_removed and not carried, a retired entry still reports and deletes, ignored_removed a list on every retired and brought_over entry.
- test_bo_4300f_3_cutover.py (test_drift fix): the M17 ast test now reads worktree_migrate.py plus its _carry and _guards siblings, since the coder moved the status helpers.
Not testable as written: a failing `status` (the unsent-work proof makes the same call, so a guard-only failure cannot be isolated); ignored_removed on needs_decision entries (contract says always present, asserted only for retired and brought_over). The M-2 hook points (unsent_work, worktree_migrate_carry.snapshot) are internal names.

### 2026-10-22 21:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework for the pr-reviewer's work-loss findings. Linux family run (bo_4300 or bo_400e): no FAILED/ERROR; only the 8 pre-existing
test_bo_4300f_1.py route SUBFAILEDs remain (identical on a clean HEAD). New module worktree_migrate_carry.py (NAMED entry, components.json,
worktree-manager.md row); worktree_remove.status_entries gained optional no_optional_locks and extra.
- H-1: the verified clone is never deleted by _bring_over. Order: build + prove clone, write marker, re-snapshot the old folder, delete the
  old folder, then its admin entry. A failed/partial delete or a failed admin delete lists needs_decision naming BOTH locations and what remains.
- H-2: WSL exception is the exact text 'initializing' and only when the folder is missing (stuck); every other lock keeps the workspace.
- M-1: every guard fails closed ("could not check <what>"): stash list, status, ls-files, ignored listing, snapshot.
- M-2: snapshot (HEAD, unsent commits/files, per-path fingerprints, ignored, empty folders) taken from the original proof and compared again
  right before any delete, retire and bring-over alike; any difference or unreadable state keeps the workspace.
- M-3: sequencer added; skip-worktree/assume-unchanged (ls-files -v) keeps; a detached-HEAD stash keeps every detached workspace; empty
  untracked folders and symlinks (as symlinks) are carried and verified (an OS that cannot make links fails the copy, so the entry is kept).
- M-4: brought-over entries carry ignored files byte-identical (fingerprint-verified), except the install folder .leafcutter/, listed in
  ignored_removed; retired entries keep option R. ignored_removed is always emitted ([] when empty).
- M-5: guards use wrm.status_entries(no_optional_locks=True); their own _status and _read are gone.
Item 8: files_touched and the components doc row updated.

### 2026-10-22 17:09 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Re-review of the reworked staged diff (static read; tests not run on this Windows host). H-1 resolved: the verified clone is never deleted after bring-over; the old folder is deleted only after a fresh snapshot equals the pre-copy snapshot, and a partial or failed delete or registration delete gives needs_decision naming both locations. H-2 resolved: the WSL exception is the exact text and applies only with the folder missing; any other lock keeps the workspace. M-1 to M-3 resolved (guards fail closed, sequencer, skip-worktree/assume-unchanged, detached-HEAD stash). M-4: ignored files are carried byte-identical (only the install folder is reported). Nothing new is high.
Residual low and medium: a change made inside the final delete window is not detectable; a carried ignored tree is fingerprinted in full (slow on huge trees, not a loss risk); an ignored file changed after a retire's snapshot is deleted per option R.

### 2026-10-22 17:10 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 5 ACs covered (ac_coverage 5/5). Store alignment script exit 0. No delivers_to/expects_from links, so no cross-file contract gaps. Tests were not re-run here (Windows host); the 20 green Linux Docker tests (12 red pre-ticket) were taken from the orchestrator's report and pr-reviewer's re-review.
AC-1 covered:
  implementation: templates/scripts/worktree_migrate_carry.py _marker (state "creating", line_of_work "resumed"); worktree_migrate.py brought entry `next: ensure --kind <k> --slug <s>`; templates/scripts/worktree.py _resume_workspace (marker's recorded "resumed" wins)
  test: test_brought_over_workspace_is_not_ready_until_proven (unit_tests/build_orchestration/test_bo_4300f_3_cutover.py:74)
AC-2 covered:
  implementation: worktree_migrate.py canonical-first identity (wi identity, empty-slug guard); ticket 06 removed the ticket<-feature/ alias
  test: test_legacy_feature_line_is_one_workspace_whichever_kind_finds_it (test_bo_4300f_3_cutover.py:124); test_legacy_line_with_no_usable_name_is_left_for_a_decision (:150). Note: the first is a regression guard, not red pre-ticket.
AC-3 covered:
  implementation: templates/scripts/worktree_migrate_guards.py blocker / user_lock / stashed_on / has_staged_changes, used by worktree_migrate.py in run and preview
  test: test_work_that_cannot_be_carried_exactly_keeps_the_old_workspace (test_bo_4300f_3_iii.py:107); extras in test_bo_4300f_3_states.py (five operation states) and test_bo_4300f_3_keep.py
AC-4 covered:
  implementation: worktree_migrate.py _retire returns `retired` entry with `ignored_removed`, listed from git's ignored listing before the delete; preview reports the same
  test: test_retiring_reports_the_ignored_files_it_deletes (test_bo_4300f_3_iv.py:54)
AC-5 covered:
  implementation: worktree_migrate_carry.py _git_steps via wst.clone_main_checkout(repo_root, target), origin re-pointed to the hub, step-named reasons (old `--local <hub>` clone removed)
  test: test_brought_over_clone_is_hardlinked_from_main_checkout_and_reasons_carry_no_git_text (test_bo_4300f_3_cutover.py:198)
Orchestrator decision beyond A9b's literal text (noted for the record): brought-over entries CARRY their ignored files byte-identical (fingerprint-verified), except the old install folder .leafcutter/, which is reported in ignored_removed. A9b governs only retired entries, so this is additive and safer. Covered by test_bo_4300f_3_carry.py. This goes beyond the AC wording and the ACs are not contradicted.
Anomalies: the 8 SUBFAILED in test_bo_4300f_1 are pre-existing on this lane's base (fixed on the epic by 58c7b0196). The ticket has no `## AC Coverage` table, so step 4b was skipped. feedback submit failed (config/knowledge_sink.json absent).


### 2026-10-22 18:00 — ac-fulfillment-gate (status: blocker)
feedback-id: (submit-failed)
BO-4300f-3-iii and BO-4300f-3-iv: implemented_by and covered_by populated from the diff (new modules worktree_migrate_guards.py and worktree_migrate_carry.py included). mark_ac_done.py REFUSED both (exit 3): linked tests fail locally because this Windows host lacks POSIX fcntl.flock (DeployedMakerNotFoundError from the shared reference layout). work_status stays todo. Re-run mark_ac_done.py on Linux/CI. f-3-i already done; f-3 not marked (children iii, iv not done). a-1, a-2, c-1, c-2 untouched.

### 2026-10-22 18:40 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
Supersedes the 18:00 blocker. The refusal was host-only: the linked deployed-maker tests need POSIX fcntl.flock and cannot run on this Windows host.
mark_ac_done.py --test-root . was run on Linux (bo4300-ci Docker, the lane's staged tree committed in-container): BO-4300f-3-iii marked done (rc 0), BO-4300f-3-iv marked done (rc 0), composite BO-4300f-3 marked done (rc 0, all children done). The resulting work_status changes were applied here verbatim.
BO-4300a-2 covered_by gains unit_tests/build_orchestration/test_bo_4300f_3_cutover.py (carries # covers: BO-4300a-2); a-2 stays in_progress for the integrated close.

### 2026-10-22 21:00 — commit (status: ok)
feedback-id: (submit-failed)
Committed the staged ticket 08 change set (20 files) with the approved message; hooks run without bypass.
