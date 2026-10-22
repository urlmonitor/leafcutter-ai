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
status: todo
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
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
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
- [ ] AC-1: BO-4300c-1 (A3 read-only re-check). `verify` of a ready workspace whose `gc.auto` was re-enabled
  answers refused, `VERIFY_FAILED`, exit 2, with `failed_ingredients == ["gc_auto_disabled"]` and no
  `workspace_path`. A ready workspace with an uncommitted change and a hub that moved on still answers ok.
  Verify fetches nothing (hub refs unchanged, no `FETCH_HEAD` written).
- [ ] AC-2: BO-4300c-1 (A3 identity). `verify --path W --kind feature --slug other` of W (feature/x) answers
  `VERIFY_FAILED` with `failed_ingredients == ["identity"]`. `--kind bogus` answers USAGE, exit 64.
- [ ] AC-3: BO-4300b-4. When the stub build leaves `.leafcutter/scripts` (or a hook) as a symlink, ensure
  refuses `VERIFY_FAILED` naming `install_paths_regular`. A later verify reports
  `checks.install_paths_regular == false` and refuses.
- [ ] AC-4: BO-4300c-1 IT0 (A3) / BO-4300c-2 checks (N8). Every ensure and verify ok answer carries
  `checks.same_project`, `is_independent_repo`, `origin_matches_hub`, `gc_auto_disabled` and
  `install_paths_regular`, each a boolean. A workspace with an `objects/info/alternates` file verifies as
  `is_independent_repo: false` and is refused.
- [ ] AC-5: BO-4300c-2 (A2 item 6). The locate and verify ok answers carry top-level `kind`, `slug`,
  `branch`, `checks`, `workspace_action == "located"`, `line_of_work == "existing"`, `created == false`,
  `fetch == "skipped"`, `origin_main_commit` and `base_matches_origin_main`. Each list entry has exactly
  `{kind, slug, branch, workspace_path, workspace_path_posix, state}`, with state in {ready, incomplete}.
- [ ] AC-6: BO-4300a-2 IT1 / BO-4300e-1 IT0 (M12). `locate --kind epic --slug EPIC-Alpha` and
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
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
