---
title: "Read-only verbs: verify refuses, and locate, verify and list answer in the contract's shape"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-1
  - BO-4300c-2
  - BO-4300b-4
  - BO-4300e-1
  - BO-4300a-2
  l3: []
status: done
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on:
  - 05_TICKET-20261022-ensure-clones-main-checkout-contract-shape.md
  - 06_TICKET-20261022-work-identity-safe-slugs-canonical-first.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
ac_coverage: 6/6
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M5
  - M7
  - M8
  - N8
  - M9b
  - N2
  - M12
files_touched:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_readiness.py
  - docs/reference/workspace-maker-answer.md
  - unit_tests/build_orchestration/test_bo_4300c_1.py
  - unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
  - unit_tests/build_orchestration/test_bo_4300b_4.py
  - unit_tests/build_orchestration/test_bo_4300e_1.py
  - unit_tests/build_orchestration/test_bo_4300e_1_i.py
  - unit_tests/build_orchestration/test_bo_4300c_1_independence.py
  - unit_tests/build_orchestration/test_bo_4300b_4_links.py
  - unit_tests/build_orchestration/test_bo_4300e_1_shapes.py
  - unit_tests/build_orchestration/test_bo_4300e_1_i_alias.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_remove.py
  - unit_tests/build_orchestration/test_bo_4300a_1_same_location.py
  - unit_tests/build_orchestration/test_bo_4300c_1_verify_readonly.py
  - unit_tests/build_orchestration/test_bo_4300d_1.py
# out_of_scope: changed by tickets 01, 03, 04, 05, 06 and 09, merged into the epic commit
# (210ed8dc5) this lane starts from; the scope guard diffs the whole branch against main.
out_of_scope:
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/suite_performance/_shared_layout_producer.py
  - scripts/suite_performance/_shared_layout_seed.py
  - templates/scripts/commit_guardian/ensure_precommit_config.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_answer.py
  - templates/scripts/worktree_canaries.py
  - templates/scripts/worktree_ensure_state.py
  - templates/scripts/worktree_ensure_steps.py
  - templates/scripts/worktree_identity.py
  - templates/scripts/worktree_log_root.py
  - templates/scripts/worktree_ticket_record.py
  - unit_tests/build_orchestration/_bo_4300a_2_probe.py
  - unit_tests/build_orchestration/_bo_4300f_2_fixtures.py
  - unit_tests/build_orchestration/_workspace_maker_builders.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
  - unit_tests/build_orchestration/test_bo_400e_3_ix_setup_record.py
  - unit_tests/build_orchestration/test_bo_4300a_1_budgets.py
  - unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
  - unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
  - unit_tests/build_orchestration/test_bo_4300a_1_marker_survival.py
  - unit_tests/build_orchestration/test_bo_4300a_1_route_shape.py
  - unit_tests/build_orchestration/test_bo_4300a_2.py
  - unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  - unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
  - unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  - unit_tests/build_orchestration/test_bo_4300e_2.py
  - unit_tests/build_orchestration/test_bo_4300e_2_i.py
  - unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  - unit_tests/build_orchestration/test_bo_4300e_3.py
  - unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  - unit_tests/build_orchestration/test_bo_4300f_4.py
  - unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
---

# 07: Read-only verbs: verify refuses, and locate, verify and list answer in the contract's shape

## Actor / Goal
A caller re-checks or looks up a workspace. An ok answer from `verify` must mean the workspace is ready.
`locate`, `verify` and `list` must answer in the field shape BO-4300c-2 states, finding the workspace
whichever declared spelling the caller used.

## Context
References are verified against the current tree. One correction to DECISIONS.md: `_STRUCTURAL` is not in
`worktree.py`. It is `templates/scripts/worktree_readiness.py:189`, and ensure's `prove_ready` (line 204)
uses it as well. `templates/scripts/worktree_repo_facts.py` does NOT apply. It is the build-feature loop's
read-only dirty-state helper (BO-100e-4) and computes no readiness check, so it is not in `files_touched`.

- **M5 verify (HIGH; BO-4300c-1 IT0 and the new read-only re-check IT from A3; BO-4300c-2 `VERIFY_FAILED`).**
  - `templates/scripts/worktree.py:289` `cmd_verify` answers `status: ok` even when checks are false.
  - It parses `--kind`/`--slug` (build_parser, verify sub-parser) but never uses them.
  - Fix (A3):
    - verify judges the ingredients read-only: no fetch, build or commit (BO-4300e-1-i).
    - It refuses `VERIFY_FAILED` with `failed_ingredients` when any of the following is false:
      `is_independent_repo`, `not_main_checkout`, `same_project`, `origin_matches_hub`, `gc_auto_disabled`,
      `install_paths_regular`, `branch_matches`, `not_protected_branch`, `build_ok`, or a hook-stage result
      recorded by the readiness proof (`stored_checks`, `worktree_readiness.py:251`).
    - `base_is_fresh` and `tree_clean` are reported and NEVER refused on by verify (user decision). Give
      verify its own refusal set; ensure's `_STRUCTURAL` keeps `base_is_fresh`.
    - A marker in state `creating` is INCOMPLETE, as already done via `worktree_remove.incomplete_answer`.
    - Validate `--kind` against `wg.VALID_KINDS`; an unknown kind is USAGE. With `--kind K --slug S`, a
      marker holding a different canonical identity (`wi.resolve(K, S)`) is `VERIFY_FAILED` with
      `failed_ingredients: ["identity"]`.
  - Port source: v1 4ff8e251a and 13f88da31 `verb_verify`.
- **M7 (MEDIUM; BO-4300b-4).** No `islink`/`lstat` check exists. `compute_checks` (`worktree_readiness.py:154`)
  lacks `install_paths_regular`.
  - Add an lstat walk of `.leafcutter/`, `.pre-commit-config.yaml` and `.git/hooks` that treats a symlink
    or a Windows `FILE_ATTRIBUTE_REPARSE_POINT` as a link.
  - Add the check to the ensure and verify refusal sets.
  - Port source: v1 2449b08a5.
- **M8 / N8 (MEDIUM; BO-4300c-1 IT0 as amended by A3; BO-4300c-2 checks; ADR-018 A1.1).**
  - `is_independent_repo` is only `(workspace / ".git").is_dir()` (line 162). Make it require all of:
    - `.git` is a directory and not a link;
    - `rev-parse --git-common-dir` resolves to the workspace's own `.git`;
    - no `objects/info/alternates` exists.
  - Add `same_project`: `workspace_root.resolve(str(ws))` yields the same project as the marker's
    `project_root`. Keep `wg.same_location`.
  - `origin_matches_hub` and `gc_auto_disabled` are computed (lines 182-183) but not refused on. Add them,
    together with `same_project`, to both refusal sets.
  - Port source: v1 4ff8e251a and 94dd8d533.
- **M9b / N2 (BO-4300c-2, A2 item 6, option i).** The locate, verify and list ok answers nest identity
  inside `marker`:
  - `worktree_admin.py:57`, `:71` and `:76` (locate);
  - `worktree_admin.py:82-93` (list);
  - `worktree.py` `cmd_verify` (verify).

  The contract wants:
  - top-level `kind`, `slug`, `branch` and `checks` (locate too);
  - `workspace_action: "located"`, `line_of_work: "existing"`, `created: false` and `fetch: "skipped"`;
  - `origin_main_commit`: the workspace's last-fetched `origin/main`, or null;
  - `base_matches_origin_main` comparing `base_commit` with that;
  - list entries `{kind, slug, branch, workspace_path, workspace_path_posix, state: "ready"|"incomplete"}`.

  Keep `marker` as an extra field. That is compatible, and it means `worktree_remove.cmd_locate`
  (`worktree_remove.py:59`, ticket 04's file) needs no change. `bootstrap` and `hooks_stages_declared`
  stay on ensure answers only.
- **M12 (MEDIUM; BO-4300a-2 IT1; BO-4300e-1 IT0).**
  - `worktree_admin.cmd_locate` (line 50) calls `wg.normalize_slug(args.slug)` without the kind (line 65)
    and does not validate `--kind`.
  - `locate --branch` (lines 74-76) compares `marker["branch"] == args.branch` exactly.
  - Fix:
    - use `wi.resolve(args.kind, args.slug).slug`;
    - answer USAGE for an invalid kind;
    - match `--branch` through `Identity(marker kind, marker slug).matches_branch`.
- **Reference doc.** `docs/reference/workspace-maker-answer.md`:
  - Remove the `REFUSED` row (line 88); ticket 05 drops the code.
  - Document `step`, `recorded_ticket`, `failed_ingredients`, `holders`, the new checks, the new ensure ok
    fields and the locate/verify/list shapes. `BUILT_FOR_OTHER_TICKET` is already listed (line 85).
- `worktree.py` is 477 lines. If `cmd_verify` grows past the file-size ratchet, move it into
  `worktree_admin.py`, which this ticket owns.
- `worktree_admin.py` importing `worktree_identity` and `worktree_readiness` creates no cycle. Neither
  imports `worktree_admin`.

## Scope
1. A3 read-only verify refusals, identity check and kind validation.
2. The `install_paths_regular`, strengthened `is_independent_repo` and `same_project` checks in
   `compute_checks`. Separate refusal sets for ensure and verify.
3. The contract shapes for locate, verify and list (A2 item 6, option i).
4. Alias-aware locate (by slug and by branch).
5. Update the reference doc.

## Acceptance Criteria
- [x] AC-1: BO-4300c-1 (A3 read-only re-check). `verify` of a ready workspace whose `gc.auto` was re-enabled
  answers refused, `VERIFY_FAILED`, exit 2, with `failed_ingredients == ["gc_auto_disabled"]` and no
  `workspace_path`. A ready workspace with an uncommitted change and a hub that moved on still answers ok.
  Verify fetches nothing (hub refs unchanged, no `FETCH_HEAD` written).
- [x] AC-2: BO-4300c-1 (A3 identity). `verify --path W --kind feature --slug other` of W (feature/x) answers
  `VERIFY_FAILED` with `failed_ingredients == ["identity"]`. `--kind bogus` answers USAGE, exit 64.
- [x] AC-3: BO-4300b-4. When the stub build leaves `.leafcutter/scripts` (or a hook) as a symlink, ensure
  refuses `VERIFY_FAILED` naming `install_paths_regular`. A later verify reports
  `checks.install_paths_regular == false` and refuses.
- [x] AC-4: BO-4300c-1 IT0 (A3) / BO-4300c-2 checks (N8). Every ensure and verify ok answer carries
  `checks.same_project`, `is_independent_repo`, `origin_matches_hub`, `gc_auto_disabled` and
  `install_paths_regular`, each a boolean. A workspace with an `objects/info/alternates` file verifies as
  `is_independent_repo: false` and is refused.
- [x] AC-5: BO-4300c-2 (A2 item 6). The locate and verify ok answers carry top-level `kind`, `slug`,
  `branch`, `checks`, `workspace_action == "located"`, `line_of_work == "existing"`, `created == false`,
  `fetch == "skipped"`, `origin_main_commit` and `base_matches_origin_main`. Each list entry has exactly
  `{kind, slug, branch, workspace_path, workspace_path_posix, state}`, with state in {ready, incomplete}.
- [x] AC-6: BO-4300a-2 IT1 / BO-4300e-1 IT0 (M12). `locate --kind epic --slug EPIC-Alpha` and
  `locate --branch EPIC-Alpha` find the workspace made by `ensure --kind epic --slug alpha`, and
  `locate --kind bogus --slug x` answers USAGE.

## Test Requirements

```yaml
tests:
- name: test_verify_refuses_a_false_ingredient_and_never_on_freshness_or_clean_tree
  file: unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
  covers:
  - BO-4300c-1
  - BO-4300c-2
  asserts: >-
    make_project and ensure. Run `git config gc.auto 1` in the workspace, then run_maker verify, which
    answers refused/VERIFY_FAILED/exit 2 with failed_ingredients ['gc_auto_disabled'] and no
    workspace_path. Reset gc.auto to 0, add an uncommitted file and advance the hub; verify answers ok,
    and the hub's refs and the workspace's FETCH_HEAD mtime are unchanged.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_verify_with_mismatched_identity_is_verify_failed_and_bad_kind_is_usage
  file: unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
  covers:
  - BO-4300c-1
  asserts: >-
    For an ensured feature/x, verify --kind feature --slug other gives VERIFY_FAILED with
    failed_ingredients ['identity'], and verify --kind bogus gives USAGE with exit 64.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_link_left_by_the_build_is_refused_as_install_paths_regular
  file: unit_tests/build_orchestration/test_bo_4300b_4.py
  covers:
  - BO-4300b-4
  asserts: >-
    make_project with a stub_build that leaves one symlink under .leafcutter/ (skipped with a reason
    where the OS denies symlink creation). ensure answers VERIFY_FAILED and failed_ingredients contains
    install_paths_regular.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_alternates_file_makes_workspace_not_independent
  file: unit_tests/build_orchestration/test_bo_4300c_1.py
  covers:
  - BO-4300c-1
  - BO-4300c-2
  asserts: >-
    After ensure, the ok answer has boolean checks same_project, is_independent_repo, origin_matches_hub,
    gc_auto_disabled and install_paths_regular. After writing .git/objects/info/alternates, verify gives
    VERIFY_FAILED naming is_independent_repo.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_locate_verify_list_answer_in_the_contract_shape
  file: unit_tests/build_orchestration/test_bo_4300e_1.py
  covers:
  - BO-4300c-2
  - BO-4300e-1
  asserts: >-
    After ensure, locate and verify answers carry top-level kind, slug, branch and checks, with
    workspace_action 'located', line_of_work 'existing', created False, fetch 'skipped',
    origin_main_commit and base_matches_origin_main. Each list workspaces entry's key set is exactly
    {kind, slug, branch, workspace_path, workspace_path_posix, state}.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_locate_finds_a_workspace_by_a_declared_alias_spelling
  file: unit_tests/build_orchestration/test_bo_4300e_1_i.py
  covers:
  - BO-4300a-2
  - BO-4300e-1
  asserts: >-
    After ensure --kind epic --slug alpha, locate --kind epic --slug EPIC-Alpha and locate --branch
    EPIC-Alpha both answer ok with the same workspace_path, and locate --kind bogus --slug x answers USAGE.
  framework: unittest
  type: behavioral
  angle: deployed
```

## Sign-offs
- [x] test-writer — 2026-10-22 15:00
- [x] python-coder — 2026-10-22 16:10
- [x] pr-reviewer — 2026-10-22 17:00
- [x] ac-validator — 2026-10-22 21:00
- [x] ac-fulfillment-gate — 2026-10-22 22:00
- [x] commit — 2026-10-22 23:00

## Comments

### 2026-10-22 15:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written: true
  tests_red_on_linux_for_assertion_reasons: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "deployed worktree.py verbs (ensure writes the marker and checks) in a real subprocess"
    consuming_side: "deployed worktree.py locate/verify/list reading that marker, and its refusals"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <deployed>/worktree.py verify|locate|list|ensure (CLI via subprocess)"
red_baseline:
  - test_name: TestVerifyRefuses.test_verify_refuses_a_false_ingredient_and_never_on_freshness_or_clean_tree
    file: unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
    kind: assertion
    error: "AssertionError: Tuples differ: ('ok', 'OK', 0) != ('refused', 'VERIFY_FAILED', 2)"
  - test_name: TestVerifyRefuses.test_verify_with_mismatched_identity_is_verify_failed_and_bad_kind_is_usage
    file: unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
    kind: assertion
    error: "AssertionError: Tuples differ: ('ok', 'OK', 0) != ('refused', 'VERIFY_FAILED', 2)"
  - test_name: TestIndependence.test_alternates_file_makes_workspace_not_independent
    file: unit_tests/build_orchestration/test_bo_4300c_1_independence.py
    kind: assertion
    error: "AssertionError: None is not True : ensure checks.same_project: {...}"
  - test_name: TestInstallPathsRegular.test_link_left_by_the_build_is_refused_as_install_paths_regular
    file: unit_tests/build_orchestration/test_bo_4300b_4_links.py
    kind: assertion
    error: "AssertionError: Tuples differ: ('ok', 'OK', 0) != ('refused', 'VERIFY_FAILED', 2)"
  - test_name: TestInstallPathsRegular.test_later_verify_reports_and_refuses_a_link
    file: unit_tests/build_orchestration/test_bo_4300b_4_links.py
    kind: assertion
    error: "AssertionError: None is not True (checks.install_paths_regular absent from verify ok answer)"
  - test_name: TestContractShape.test_locate_verify_list_answer_in_the_contract_shape
    file: unit_tests/build_orchestration/test_bo_4300e_1_shapes.py
    kind: assertion
    error: "AssertionError: Tuples differ: (None, None, None) != ('feature', 'x', 'feature/x') : locate name"
  - test_name: TestLocateAliases.test_locate_finds_a_workspace_by_a_declared_alias_spelling
    file: unit_tests/build_orchestration/test_bo_4300e_1_i_alias.py
    kind: assertion
    error: "AssertionError: 'refused' != 'ok' : slug alias (NOT_FOUND at .../epic/epic-alpha)"
  - test_name: TestLocateAliases.test_locate_refuses_an_empty_or_invalid_slug_as_usage
    file: unit_tests/build_orchestration/test_bo_4300e_1_i_alias.py
    kind: assertion
    error: "AssertionError: Tuples differ: ('NOT_FOUND', 2) != ('USAGE', 64)"
Wrote 5 NEW test files instead of growing test_bo_4300c_1.py (350 lines), test_bo_4300b_4.py, test_bo_4300e_1.py and test_bo_4300e_1_i.py (file-size ratchet); the coder should add the new files to files_touched. Deviation: none of the existing named files was edited. Run on Linux (Docker) only.

### 2026-10-22 16:10 — python-coder (status: ok)
feedback-id: (submit-failed)
red_baseline_results: all 8 green on Linux (Docker), none skipped
  - test_verify_refuses_a_false_ingredient...: green
  - test_verify_with_mismatched_identity...: green
  - test_alternates_file...: green
  - test_link_left_by_the_build...: green
  - test_later_verify_reports_and_refuses_a_link...: green
  - test_locate_verify_list_answer_in_the_contract_shape...: green
  - test_locate_finds_a_workspace_by_a_declared_alias...: green
  - test_locate_refuses_an_empty_or_invalid_slug...: green
Linux family run (unit_tests/build_orchestration -k "bo_4300 or bo_400e", manual or not manual): rc=0, no FAILED.
Changes: worktree_readiness.py (is_independent/same_project/install_paths_regular checks, own VERIFY_REFUSALS + failed_for_verify, ensure's set gains the four new ingredients, not_main_checkout no longer tied to own_git); worktree_admin.py (cmd_verify moved here from worktree.py, located-shape fields, alias-aware locate, USAGE for bad kind/slug, list entries); worktree.py (cmd_verify removed, dispatch points to worktree_admin; 459 -> 436 lines). worktree_remove.py untouched. No new deployed module.
Notes: verify's tree_clean also counts untracked files (the red test requires it); ensure's tree_clean is unchanged (tracked only). Added the four new test filenames to files_touched.

### 2026-10-22 17:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
High: none. Medium: (1) tree_clean differs between verify (counts untracked) and ensure/BO-4300c-1-iii (tracked only); the reference doc says tracked or untracked, which is wrong for ensure. Recommend tracked-only everywhere. (2) origin_matches_hub uses Path.resolve on URLs via wg.same_location: no file:// or .git handling; safe on ensure (origin is set to the hub string) but fragile on verify. (3) nothing_uncommitted runs git status without --no-optional-locks, so the 'read-only' verify may refresh the index. (4) verify refuses a marker whose stored checks lack build_ok (older or migrated markers). Low: incomplete_answer duplicated in worktree_remove (remove already imports admin, so it can alias admin's); reference doc does not document the extra marker field on locate/verify or the 'identity' failed ingredient. Windows local run of the new tests cannot run (fcntl); Linux run reported green by python-coder.

### 2026-10-22 18:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Follow-up for pr-reviewer mediums M-1..M-3 and the locate --branch ambiguity. (classification: test_drift) for the earlier expectation that an untracked file makes verify's tree_clean false: production is right per BO-4300c-1-iii, so test_bo_4300c_1_verify_refuses.py now expects an untracked file to leave tree_clean true and a modified tracked file to make it false with verify still ok.
New tests (unit_tests/build_orchestration/): test_bo_4300c_1_verify_readonly.py (tracked-only tree_clean and ensure/verify agreement; origin respellings tolerated and a different hub refused; .git/index bytes and mtime unchanged across verify), test_bo_4300a_1_same_location.py (in-process worktree_git.same_location, deployed module, sys.modules restored), and test_locate_by_branch_is_ambiguous_when_two_workspaces_match_the_alias in test_bo_4300e_1_i_alias.py (AMBIGUOUS_LINE with two candidates).
Run on Linux (Docker) against the coder's staged changes: all pass except test_tree_clean_is_tracked_only_and_ensure_and_verify_agree, which stays red: with a modified tracked README.md, a repeat ensure answers ok / workspace_action re-readied with checks.tree_clean true (README itself is preserved), while verify reports false. Ensure's reported tree_clean is stale or wrong on the resume path.

### 2026-10-22 17:30 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework after pr-reviewer (4 mediums) and the stale-tree_clean defect, templates/scripts only.
- M-1/M-3: one tree_clean everywhere (tracked changes only, tree_is_clean). nothing_uncommitted and the verify override removed; no `git status` runs in the read-only verbs any more (so no index rewrite).
- Stale tree_clean on re-ready: worktree.py now calls wr.with_restored_tree(...) after the rescue restore, so the ensure answer AND the marker's stored checks carry the recomputed tracked-only tree_clean. Ensure stays ok.
- M-2: worktree_git.same_location: equal strings first, then canonical forms (trailing '/' and '.git' stripped; file:// URLs, incl. file:///C:/x, to local paths; local absolute paths normpath'd, resolved + case-folded only on Windows; non-file URLs exact; relative paths never resolved against cwd).
- M-4 finding: ensure today and ensure on origin/main both store checks.build_ok (True) in every ready marker (prove_ready starts its checks with build_ok True). worktree_migrate._marker writes NO checks block at all, so cut-over ready markers lack build_ok (and hooks_*, base_is_fresh). Handled: stored_checks reports build_ok null when absent, and verify refuses on build_ok only when it is False; absent hook keys are never refused.
- incomplete_answer: worktree_remove.incomplete_answer is now a one-line delegate to worktree_admin.incomplete_answer (a direct alias binds at import and fails: worktree_admin -> worktree_identity -> worktree_remove cycle). Unused wes import dropped there.
- locate --branch: more than one alias match answers AMBIGUOUS_LINE with candidates.
Linux family run: only failure is test_bo_4300d_1.py::TestReReady::test_rerequest_rebuilds_install_and_reproves_protections (subTest tree_clean): classification test_drift. The test edits README.md (tracked) before the re-request and asserts tree_clean True in the re-ready answer via CHECK_KEYS; the new contract says False. Needs test-writer: drop tree_clean from that loop (or assert False).

### 2026-10-22 19:00 — test-writer (status: ok)
feedback-id: (submit-failed)
(classification: test_drift) test_bo_4300d_1.py::TestReReady::test_rerequest_rebuilds_install_and_reproves_protections edited a tracked README.md before the re-request and asserted tree_clean True. Under the tracked-only rule, computed after the restore, the re-ready answer correctly reports False; the test now asserts tree_clean False and keeps True for every other CHECK_KEYS entry (file 267 -> 269 lines, under the ratchet). Whole family on Linux (Docker): unit_tests/build_orchestration -k "bo_4300 or bo_400e" -m "manual or not manual": exit 0, no FAILED lines (2 skips).

### 2026-10-22 20:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Re-review: M-1 to M-4 and the duplicate incomplete_answer, locate ambiguity and doc gaps are resolved in the code (no git status in the read-only verbs; same_location keeps remote URLs unresolved; build_ok refused only on explicit False). No new high findings; sign-off kept. New low/medium: (a) reference doc says verify may answer ON_PROTECTED_BRANCH, but cmd_verify always answers VERIFY_FAILED; (b) docs do not mention checks.build_ok is null when no build result is recorded; (c) same_location trims a .git suffix on local paths too, so /a/b and /a/b.git compare equal (acceptable); (d) import re is out of alphabetical order in worktree_git.py. Windows branches of same_location are untested here (relies on the Linux run).

### 2026-10-22 21:00 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 6 ACs covered (store alignment script rc=0; no AC Coverage table in this ticket, so 4b skipped).
AC-1 covered: impl worktree_admin.py cmd_verify + worktree_readiness.py VERIFY_REFUSALS/failed_for_verify (base_is_fresh, tree_clean excluded); test test_verify_refuses_a_false_ingredient_and_never_on_freshness_or_clean_tree, test_verify_does_not_rewrite_the_index (test_bo_4300c_1_verify_refuses.py, test_bo_4300c_1_verify_readonly.py)
AC-2 covered: impl worktree_admin.py cmd_verify (_identity_mismatch -> failed ['identity'], VALID_KINDS -> USAGE); test test_verify_with_mismatched_identity_is_verify_failed_and_bad_kind_is_usage
AC-3 covered: impl worktree_readiness.py install_paths_regular (line 169), in _SHARED refusal set; test test_link_left_by_the_build_is_refused_as_install_paths_regular, test_later_verify_reports_and_refuses_a_link (test_bo_4300b_4_links.py)
AC-4 covered: impl worktree_readiness.py is_independent (alternates check, line 189), same_project (196), compute_checks (225-226); test test_alternates_file_makes_workspace_not_independent (test_bo_4300c_1_independence.py)
AC-5 covered: impl worktree_admin.py line 77-78 (workspace_action, line_of_work, created, fetch, origin_main_commit, base_matches_origin_main), cmd_list entries; test test_locate_verify_list_answer_in_the_contract_shape (test_bo_4300e_1_shapes.py)
AC-6 covered: impl worktree_admin.py cmd_locate (wi.resolve, matches_branch line 106, USAGE line 136-137, AMBIGUOUS_LINE line 150); test test_locate_finds_a_workspace_by_a_declared_alias_spelling, test_locate_refuses_an_empty_or_invalid_slug_as_usage, test_locate_by_branch_is_ambiguous... (test_bo_4300e_1_i_alias.py)
Reference doc docs/reference/workspace-maker-answer.md: REFUSED row removed, failed_ingredients/holders/recorded_ticket/new checks/located shapes documented. Test evidence as reported: bo_4300/bo_400e family green on Linux (2 skips), doc/components tests 96 green, pr-reviewer re-signed.
Minor non-blocking: pr-reviewer low items (doc says verify may answer ON_PROTECTED_BRANCH; build_ok null undocumented) remain.

### 2026-10-22 22:00 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  store_fields_verified: true
  auto_fixes_append_only: true
5 ACs resolved (BO-4300c-1, c-2, b-4, e-1, a-2). b-4, e-1 and e-1-i were already work_status done; left unchanged. c-1, c-2, a-2 stay in_progress (ticket 08 still builds parts of them), not marked done as instructed.
Auto-fixes (append-only): covered_by gained tagged tests (c-1: independence, verify_refuses, verify_readonly, a_1_same_location; c-2: independence, verify_refuses, e_1_shapes; a-2: e_1_i_alias; b-4: b_4_links; e-1: e_1_shapes, e_1_i_alias); c-1 implemented_by gained worktree_admin.py. AC YAML staged with git add.

### 2026-10-22 23:00 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committing ticket 07 as one commit on hardening/h07 (22 files).
