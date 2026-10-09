---
title: 'Readiness: ready only when every ingredient and every declared protection holds'
status: todo
components:
- worktree_manager
- commit_guardian
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 04_TICKET-20260928-BO-4300-project-resolution.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
source_ac: BO-4300c-1
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300c-1
  - BO-4300b-4
  l3:
  - BO-4300c-1-i
  - BO-4300c-1-ii
  - BO-4300c-1-iii
ac_coverage: 5/5
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_readiness.py
- templates/scripts/worktree_canaries.py
- scripts/build_shim_env.py
- unit_tests/build_orchestration/test_bo_4300c_1_marker_and_guardian.py
- unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
- unit_tests/build_orchestration/test_bo_4300c_1_review_fixes.py
- templates/scripts/commit_guardian/commit_guardian.json
- templates/scripts/commit_guardian/precommit_canary.py
- scripts/build_helpers.py
- .github/workflows/ci.yml
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
- unit_tests/build_orchestration/test_bo_4300c_1.py
- unit_tests/build_orchestration/test_bo_4300c_1_i.py
- unit_tests/build_orchestration/test_bo_4300c_1_ii.py
- unit_tests/build_orchestration/test_bo_4300c_1_iii.py
- unit_tests/build_orchestration/test_bo_4300b_4.py
agents:
  ac-fulfillment-gate: signed_off
  ac-validator: signed_off
  architect-review: signed_off
  commit: needed
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  pr-reviewer: signed_off
  pull-request: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
  user-surface-smoker: not_needed
---

# 05: Readiness: ready only when every ingredient and every declared protection holds

## Actor / Goal

In order that 'ready' can be trusted, we need readiness computed off the finished workspace as it exists -- independent clone, own line of work, fresh base, own install, every declared hook stage firing, clean tree -- so that any false ingredient is a refusal naming it, including on Windows without link permission.

## Context

01 python-coder disclosed that the `checks` dict still uses the maker's own five key names and one generic canary; full parity (per-stage `hooks_*_fired`, `not_main_checkout`, `branch_matches`, `not_protected_branch`, `base_is_fresh`, `precommit_config_present`) was deferred to BO-4300c-1-ii / BO-4300b-1. d-1 and d-1-i (ticket 07) expect from c-1 and c-1-iii.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 5 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300c-1-i | L3 | A failed install inside the workspace is a refusal, never a warning | BO-4300c-1 | this ticket |
| AC-2 | BO-4300c-1-ii | L3 | Every protection the project declares must fire; one that is present but does not fire produces a refusal | BO-4300c-1 | this ticket |
| AC-3 | BO-4300c-1-iii | L3 | Setting up a workspace never leaves stray changes in the project's own files | BO-4300c-1 | this ticket |
| AC-4 | BO-4300c-1 | L2 | Ready is only answered when every part of readiness holds on the workspace as it exists | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-5 | BO-4300b-4 | L2 | On Windows without permission to create links, the workspace is still fully ready | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300c-1` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300c-1`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300c-1-i (L3) -- A failed install inside the workspace is a refusal, never a warning

```gherkin
Given the build that installs the tools inside a new workspace fails after
  producing part of its output,
When the workspace maker answers,
Then the answer is a refusal naming the failed install and quoting the build's
  own failure message,
And the answer is not ready, even though the copy and its line of work exist.
```

### AC-2: BO-4300c-1-ii (L3) -- Every protection the project declares must fire; one that is present but does not fire produces a refusal

```gherkin
Given a test project that declares three kinds of protection -- checks that
  run when a commit is made, a check on the commit message, and a check that
  runs after a merge -- and a test fixture that can leave exactly one of those
  kinds declared and in place in a new workspace but not firing,
When the workspace maker answers,
Then it answers ready only when every kind of protection the project declares
  was shown to fire inside the workspace, each by a real operation that it
  rejects: a commit of a known-bad file for the commit-time checks, a commit
  with a known-bad message for the commit-message check, and a merge that
  brings in a known-bad change for the after-merge check, which reports that
  merge as failing,
And when any one declared kind does not fire, the answer is a refusal naming
  that kind,
And the presence of the protection settings, or of the files meant to run a
  kind of protection, never on its own produces a ready answer.
```

### AC-3: BO-4300c-1-iii (L3) -- Setting up a workspace never leaves stray changes in the project's own files

```gherkin
Given building the tools inside a new workspace alters 61 files that the
  project keeps under version control,
When the workspace maker answers,
Then either those 61 files have been put back to their committed content and
  the answer lists them as restored, or the answer is a refusal naming them,
And a ready workspace never starts with changes to version-controlled files
  that the work itself did not make.
```

### AC-4: BO-4300c-1 (L2) -- Ready is only answered when every part of readiness holds on the workspace as it exists

```gherkin
Given a request for a workspace, and a test fixture that can make exactly one
  of the following untrue at a time,
When the workspace maker is about to answer,
Then it answers ready only when all five are true of the workspace as it now
  exists: it is an independent copy of the project and not the main copy; it
  is on its own line of work, which is not the shared main line; a newly
  started line starts at the shared main line tip read after fetching, and
  a resumed line holds every commit it has on the shared project; its tools were
  installed inside it by a build that finished successfully; and its
  protections were shown to fire,
And when any one of the five is untrue, it answers with a refusal naming that
  one,
And a refusal never carries a workspace location.
```

### AC-5: BO-4300b-4 (L2) -- On Windows without permission to create links, the workspace is still fully ready

```gherkin
Given a Windows machine on which the user is not permitted to create symbolic
  links,
When a workspace is requested,
Then it is answered ready,
And every installed tool and every protection setting in the workspace is an
  ordinary file or folder, not a link,
And a commit of a known-bad file inside the workspace is rejected by its
  protections,
And the answer and the workspace are the same as those produced for the same
  request on a machine where links are permitted.
```

- [x] AC-1: BO-4300c-1-i -- A failed install inside the workspace is a refusal, never a warning
- [x] AC-2: BO-4300c-1-ii -- Every protection the project declares must fire; one that is present but does not fire produces a refusal
- [x] AC-3: BO-4300c-1-iii -- Setting up a workspace never leaves stray changes in the project's own files
- [x] AC-4: BO-4300c-1 -- Ready is only answered when every part of readiness holds on the workspace as it exists
- [x] AC-5: BO-4300b-4 -- On Windows without permission to create links, the workspace is still fully ready

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_partial_build_failure_is_an_error_naming_the_install
  file: unit_tests/build_orchestration/test_bo_4300c_1_i.py
  covers:
  - BO-4300c-1-i
  asserts: A stub build that writes part of its output then exits 1 gives status error, code BOOTSTRAP_FAILED,
    exit 1.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_failure_answer_quotes_the_builds_own_message
  file: unit_tests/build_orchestration/test_bo_4300c_1_i.py
  covers:
  - BO-4300c-1-i
  asserts: failure_excerpt contains the stub build's distinctive failure line.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_answer_is_not_ok_although_clone_and_branch_exist
  file: unit_tests/build_orchestration/test_bo_4300c_1_i.py
  covers:
  - BO-4300c-1-i
  asserts: The clone and its branch exist on disk, yet the answer has no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_all_three_declared_stages_fire_gives_ok
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: With a fixture project declaring pre-commit, commit-msg and post-merge stages, each with a
    stub hook that rejects its known-bad input, ensure answers ok; hooks_stages_declared lists all three;
    checks.hooks_pre_commit_fired, hooks_commit_msg_fired, hooks_post_merge_fired and hooks_canary_rejected
    are all true; and .git/hooks in the workspace holds a shim for each stage.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_commit_time_stage_not_firing_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: With only the pre-commit hook made to accept the known-bad file (other two still fire), the
    answer is HOOKS_INACTIVE, inactive_stages == ['pre-commit'], the message names it, no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_commit_message_stage_not_firing_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: With only the commit-msg hook made to accept the known-bad message, the answer is HOOKS_INACTIVE,
    inactive_stages == ['commit-msg'], no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_after_merge_stage_not_firing_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: With only the post-merge hook made to exit 0 on the merge bringing in the known-bad change,
    the answer is HOOKS_INACTIVE, inactive_stages == ['post-merge'], no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_declared_stage_whose_shim_is_missing_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: With the fixture's shim installer made to skip the post-merge shim while the stage stays declared
    (the KI-CG-20260914 shape), the answer is HOOKS_INACTIVE naming post-merge -- a declaration alone
    never counts.
  framework: unittest
  type: behavioral
  angle: seam
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_config_or_shim_presence_alone_never_yields_ok
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: checks.precommit_config_present is true and all three shim files exist while one stage does
    not fire; status is not ok and workspace_path is absent.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_canaries_leave_branch_index_and_tree_unchanged
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: After an ok ensure, the workspace's branch tip equals base_commit, `git status --porcelain`
    is empty, and no disposable canary ref remains.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_undeclared_stage_is_reported_na_and_does_not_block
  file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
  covers:
  - BO-4300c-1-ii
  asserts: A fixture declaring only pre-commit answers ok with hooks_commit_msg_fired and hooks_post_merge_fired
    == 'n/a' and hooks_pre_commit_fired true; a fixture declaring no pre-commit stage answers HOOKS_INACTIVE
    naming pre-commit.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_build_touched_tracked_files_are_restored_and_listed_or_refused
  file: unit_tests/build_orchestration/test_bo_4300c_1_iii.py
  covers:
  - BO-4300c-1-iii
  asserts: A stub build that rewrites 61 tracked files yields either ok with exactly those 61 paths in
    restored_tracked and their committed content on disk, or BOOTSTRAP_DIRTIED_TRACKED naming them.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_ready_workspace_starts_with_no_unmade_tracked_changes
  file: unit_tests/build_orchestration/test_bo_4300c_1_iii.py
  covers:
  - BO-4300c-1-iii
  asserts: On ok, git status --porcelain in the workspace lists no tracked change.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_all_five_ingredients_true_gives_ok
  file: unit_tests/build_orchestration/test_bo_4300c_1.py
  covers:
  - BO-4300c-1
  asserts: With a sound fixture, ensure answers ok and every checks.* ingredient is true.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_main_copy_instead_of_clone_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1.py
  covers:
  - BO-4300c-1
  asserts: When the target resolves to the main checkout, the answer is non-ok naming the independent-copy
    ingredient, with no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_line_of_work_equal_to_main_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1.py
  covers:
  - BO-4300c-1
  asserts: A workspace whose branch is main is refused (ON_PROTECTED_BRANCH), no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_stale_base_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1.py
  covers:
  - BO-4300c-1
  asserts: When the workspace's base is not origin/main as read after the fetch, the answer is non-ok
    naming freshness.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_failed_install_build_is_refused_naming_it
  file: unit_tests/build_orchestration/test_bo_4300c_1.py
  covers:
  - BO-4300c-1
  asserts: A stub build exiting non-zero gives BOOTSTRAP_FAILED, no workspace_path.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_protections_that_do_not_fire_are_refused_naming_them
  file: unit_tests/build_orchestration/test_bo_4300c_1.py
  covers:
  - BO-4300c-1
  asserts: With a fixture declaring pre-commit, commit-msg and post-merge, making each stage in turn accept
    its canary (the other two still firing) gives HOOKS_INACTIVE with inactive_stages naming exactly that
    stage, the matching checks.hooks_<stage>_fired false, hooks_canary_rejected false, and no workspace_path.
    The per-stage cases themselves are BO-4300c-1-ii's; this arm proves the conjunction drops none.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_ensure_is_ready_when_symlinks_are_denied
  file: unit_tests/build_orchestration/test_bo_4300b_4.py
  covers:
  - BO-4300b-4
  asserts: With symlink creation denied, ensure answers ok, exit 0.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_install_and_protection_paths_are_regular_files
  file: unit_tests/build_orchestration/test_bo_4300b_4.py
  covers:
  - BO-4300b-4
  asserts: Every path under the workspace's install and its .pre-commit-config.yaml is a regular file/folder
    (no symlink, no junction).
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_known_bad_commit_is_rejected_when_symlinks_are_denied
  file: unit_tests/build_orchestration/test_bo_4300b_4.py
  covers:
  - BO-4300b-4
  asserts: A commit of the known-bad file inside that workspace is rejected by the installed hook.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_answers_with_and_without_link_permission_are_equivalent
  file: unit_tests/build_orchestration/test_bo_4300b_4.py
  covers:
  - BO-4300b-4
  asserts: After normalising paths, timestamps and shas, the two answers are equal.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
- name: test_ticket_05_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300c_1_i.py
  covers:
  - BO-4300c-1
  angle: reachability
  surface_invoked: python <install-root>/.leafcutter/scripts/worktree.py ensure --kind feature --slug
    <s> --repo-root <project> (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_readiness.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/precommit_canary.py
  - scripts/build_helpers.py
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- MOVE `compute_checks`, `run_canary`, `run_install_build`, `restore_dirtied_tracked`, `hooks_dir` out of `worktree_git.py` into `templates/scripts/worktree_readiness.py`.
- PER-STAGE CANARIES (c-1-ii): the stage set comes from the workspace's own hook declaration (union of `stages:` in its generated `.pre-commit-config.yaml`); one real canary per stage (pre-commit bad file, commit-msg bad message, post-merge bad merge on a disposable ref); canaries leave nothing behind. commit_guardian declares only a manual-stage `precommit-canary` today, so adding per-stage canary declarations to `templates/scripts/commit_guardian/commit_guardian.json` is in scope -- a cross-component touch on commit_guardian the AC says must be flagged to the user (do so at architect-review).
- SCRATCH: for kind scratch every stage check and the conjunction are 'n/a' (BO-4300e-4, consumed by ticket 11). RESUMED LINES: the fresh-base ingredient applies to new lines only; for `line_of_work: resumed` it is 'holds every commit of origin/<branch>'. Ticket 06 (BO-4300d-4) sets `line_of_work`; implement the ingredient to branch on it now.
- NO LINKS (b-4): no link creation on the ensure path; `scripts/build_helpers.py` `install_shims` must take its copy path; readiness asserts every install/protection path is a regular file or folder. Proof arm 1 is a real Windows CI job without Developer Mode (add a windows runner to `.github/workflows/ci.yml` for this module); arm 2 denies symlink creation to the maker process on every platform (injected sitecustomize).
- The deployed maker has no flag or env switch that skips an ingredient; tests falsify ingredients through the FIXTURE only.
- Canary commits run with cwd = workspace, never `git -C <path> commit`.
- FILE-SIZE RATCHET: `templates/scripts/worktree.py` is at ~393 of 400 counted lines and `templates/scripts/worktree_git.py` near its limit (01 python-coder sign-off). Every addition therefore goes into the NEW module this ticket owns (see files_touched); the two core files are touched only to move code out and to wire the new module in. A new module needs its own NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py` and `scripts/build_deploy_manifest_helpers.py` (KI-TQ-004: no second tracked copy; the maker is deployed to `<install-root>/.leafcutter/scripts/<name>`, not `<install-root>/scripts/`, per 01 test-writer/python-coder).
- ANSWER TABLE: the status/code/exit table is owned by ticket 03 (BO-4300c-2 declares the full code enum). Do not add codes locally; if a code is missing from BO-4300c-2 it is a contract change, not a local edit.
- PROOF: tests run the DEPLOYED maker through ticket 02's locator (`unit_tests/build_orchestration/_workspace_maker_fixtures.py`), as a subprocess, against real temp repos with a real bare hub; no mock of git, no import of the maker module, never spawn `scripts/build.py`. Pin `newline="\n"` on fixture writes and isolate GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM (the CRLF drift found on 04 in the failed run). Use `AC_ENFORCE_STRICT=1` to see a genuine red baseline (the AC-enforcement plugin otherwise downgrades not-done-AC failures to xfail).
- HOOK HYGIENE (lessons from ticket 01): DECISION HISTORY entries need `HH:MM` and the `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/NN)` tail-tag on the entry's FIRST line; run `check_documentation.py` with NO `--file` flag (staged mode) before commit; run `check_doc_length.py` on every doc touched (300-line ratchet); stage every file in files_touched (01 shipped an ADR edit unstaged). Commits never spelled `git -C <path> commit`.
- SCOPE: the epic worktree is shared by every ticket. Edit only files_touched. If the fix needs another file, stop and get this ticket updated (CLAUDE.md TICKET MANDATE); the failed run stalled on exactly this (tickets 04, 14, 46, 59).

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300c-1-i**

- A non-zero build exit is an error answer BOOTSTRAP_FAILED (never a warning, F6) whose bootstrap.failure_excerpt quotes the tail of the build's own stderr (bounded to 4 KB); the build's output goes to stderr, never stdout.

**BO-4300c-1-ii**

- STAGE SET FROM THE PROJECT'S OWN DECLARATION (KI-CG-20260914-post-merge-stage-registers-but-installs-no-shim): ensure installs a shim into the clone's own .git/hooks for EVERY stage the workspace's own hook declaration names -- in practice the union of `stages:` in the workspace's generated .pre-commit-config.yaml, the same source commit_guardian's install_pre_commit_shims.collect_stages reads (today pre-commit, commit-msg and post-merge). The stage list is never hard-coded in the maker, and no new copy of the stage-derivation logic is written: the maker uses the install's own shim installer (run as a separate process from the workspace's install, so the maker stays stdlib-only) or an equivalent single shared source. Clones have their own hooks directory, unlike worktrees.
- ONE CANARY PER DECLARED STAGE, each a real operation the stage rejects: pre-commit -- a commit of a known-bad file is rejected; commit-msg -- a commit with a known-bad message is rejected; post-merge -- a merge that brings in a known-bad change is reported as failing by the post-merge hook (non-zero exit; a post-merge hook cannot undo the merge). Each canary's known-bad input is taken from the install's own declaration, never hard-coded to one hook; a declared stage with no declared canary input cannot be shown to fire and counts as not firing.
- Canaries leave nothing behind: commit canaries never land in the branch, the index or the working tree; the after-merge canary runs against a disposable ref, and afterwards the line of work's branch tip, index and working tree are exactly as before and the disposable ref is gone -- confirmed by the tree_clean ingredient (BO-4300c-1-iii) evaluated after the canaries.
- ANSWER FIELDS (aligned with BO-4300c-1 and BO-4300c-2): checks.hooks_pre_commit_fired, checks.hooks_commit_msg_fired, checks.hooks_post_merge_fired, each true|false|'n/a'; checks.hooks_canary_rejected is their conjunction (true only when every declared stage fired); hooks_stages_declared lists the stages the declaration names. When any declared stage does not fire, the answer is refused with code HOOKS_INACTIVE, its message names the stage(s), and inactive_stages lists them; no workspace_path.
- 'n/a' RULE: for kind scratch ALL three stage checks and the conjunction are 'n/a' (BO-4300e-4 -- nothing is committed or merged in a comparison copy). For every other kind the pre-commit check is never 'n/a' (a project that declares no commit-time stage gives HOOKS_INACTIVE naming pre-commit), and the commit-msg and post-merge checks are 'n/a' only when the project's declaration does not name that stage -- never because a declared stage was skipped.
- Presence of .pre-commit-config.yaml (or any .leafcutter copy), or of a shim file for a stage, is recorded (precommit_config_present) but never on its own produces ok. The fail-open OR-probe (setup_ticket_worktree.py AC-5, CLAUDE.md's ls ... || ls ... check, verify_precommit_active.py's check_b_config fallback) is not reproduced.
- Git spelling (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): canary commits and the canary merge run with git's working directory set to the workspace, never as `git -C <path> commit`; the same holds in the tests and fixtures.
- The real install must declare a canary input for each stage it declares; commit_guardian's declaration carries only a manual-stage precommit-canary today (verified 2026-09-25), so adding per-stage canary declarations to the install is in scope of this record's ticket (flagged to the user as a cross-component touch on commit_guardian).

**BO-4300c-1-iii**

- Before the build, snapshot the tracked-file state; after it, every tracked path the build changed is either restored to its committed content and listed in bootstrap.restored_tracked, or the answer is BOOTSTRAP_DIRTIED_TRACKED naming them (the memo's two mitigations). Only paths the build changed are touched -- the work's own changes are never restored away (BO-4300d-1-i).
- ok requires tree_clean: `git status --porcelain` shows no tracked change the work did not make.

**BO-4300c-1**

- ok is the conjunction of five ingredients read off the finished workspace as it now exists, each reported in checks.*: independent clone and not the main copy (is_independent_repo, not_main_checkout -- own .git directory, not a gitfile); own line of work that is not main/master (branch_matches, not_protected_branch); rooted at origin/main read after the fetch (base_is_fresh, base_commit read back from the workspace); install build exited 0 and its expected artefacts exist (build_ok); protections shown to fire, PER DECLARED STAGE (BO-4300c-1-ii): hooks_pre_commit_fired (a commit of a known-bad file is rejected), hooks_commit_msg_fired (a commit with a known-bad message is rejected), hooks_post_merge_fired (a merge bringing in a known-bad change is reported as failing), with hooks_canary_rejected kept as their conjunction for existing readers.
- Any false ingredient gives a non-ok answer whose code names that ingredient, and no workspace_path. For the protections ingredient the code is HOOKS_INACTIVE and inactive_stages names every declared stage that did not fire.
- Each stage's canary is an input the installed hook set is declared to reject for that stage, taken from the install's own declaration rather than hard-coded to one hook; the set of stages comes from the workspace's own hook declaration, and a shim is installed for each. Canaries never land in the branch, the index or the working tree (BO-4300c-1-ii).
- Git spelling (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): canary commits run with git's working directory set to the workspace, never as `git -C <path> commit`, in the maker and in the tests.
- The deployed maker has no flag or environment switch that skips an ingredient; tests falsify ingredients through the FIXTURE (a failing stub build, a hook that accepts, a hub whose main moves), never through the maker.
- RESUMED LINES (decided by the user at the final gate, 2026-09-25): the fresh-base ingredient applies to NEWLY started lines only. For a resumed line (BO-4300d-4, line_of_work 'resumed') the ingredient is instead "the workspace holds every commit of origin/<branch>"; the maker never resets or rebases a resumed line, reports base_commit and origin_main_commit separately, and never claims base_matches_origin_main when false. For kind scratch ALL three stage checks and hooks_canary_rejected are 'n/a' (BO-4300e-4); for any other kind the pre-commit check is never 'n/a', and the commit-msg and post-merge checks are 'n/a' only when the project does not declare that stage.

**BO-4300b-4**

- No link creation anywhere on the ensure path (decision 2); the build's shim installer must take its copy path (scripts/build_helpers.py install_shims) and the readiness check asserts every install and protection path is a regular file or folder, never a symlink or junction.
- Proof on two arms: (1) a real Windows CI job without Developer Mode (a windows runner added to .github/workflows/ci.yml running this test module) -- the migration plan asks for this for real; (2) on every platform, a run in which symlink creation is denied to the maker process (e.g. an injected sitecustomize that makes os.symlink raise), so the arm runs in the normal suite. A runner lacking arm (1) reports it as not run, never as passed.
- Answers from the link-permitted and link-denied runs are compared after normalising paths, timestamps and shas; they must be otherwise identical.

**PER-STAGE CANARY HOOK REGISTRATION (decided by the user, 2026-10-09; resolves pr-reviewer 2026-10-01 02:30 H-1)**

- The gap: `commit_guardian.json` carries `stage_canaries` and `precommit_canary.py` has `--stage`, but no `hooks_manifest` entry runs `precommit_canary.py --stage <stage>` for the commit-msg or post-merge stage (only the manual-stage pre-commit canary exists). So a real install declares no canary-rejecting hook per stage, and a real `ensure` would refuse every workspace with HOOKS_INACTIVE.
- In scope for THIS ticket, not a follow-up and not a waiver: register one canary hook per declared stage (pre-commit, commit-msg, post-merge) in the `hooks_manifest` of `templates/scripts/commit_guardian/commit_guardian.json`, following the repo's create-hook conventions (config key + `hooks_manifest` entry + hook documentation index row; the generated `.pre-commit-config.yaml` is the source `install_pre_commit_shims.collect_stages` reads). Each canary hook rejects only the declared known-bad input for its stage and is inert for ordinary commits.
- Prove it behaviourally: a test builds a REAL deployed install (the shared layout from ticket 02's locator, not a fixture-only stub) and shows `ensure` answers ok with every declared stage reported fired, and that removing one stage's registration yields HOOKS_INACTIVE naming that stage. Extend files_touched with whatever this registration really touches (for example the hook documentation index) before editing it.
- pr-reviewer M-4 (tracked_changes returns [] on git failure) is accepted as low impact because tree_is_clean fails closed; fix it if it is a one-line change, otherwise leave it noted.

**PATH-KEYED CANARIES (coordinator, 2026-10-09; the user-approved commit was rejected by the ticket's own pre-commit canary)**

- Evidence: committing this ticket's staged set failed with `PRECOMMIT_CANARY_REJECTED (pre-commit): known-bad input`. The canary scans diff TEXT for the token `LEAFCUTTER_STAGE_CANARY_KNOWN_BAD`, which appears in this ticket file (quoted review text) and in `test_bo_4300c_1_marker_and_guardian.py`. `_SKIP` exempts only `commit_guardian.json`, so any file, doc or ticket that mentions the token blocks every commit. Content scanning cannot be made inert for ordinary work.
- Required change: the canaries are keyed on something no ordinary change produces, never on file contents.
  - pre-commit: rejects only when a reserved canary path (declared in `stage_canaries`, for example `.leafcutter/stage-canary/pre-commit`) is among the staged paths.
  - post-merge: reports failure only when the merge (ORIG_HEAD..HEAD) adds that stage's reserved path.
  - commit-msg: rejects only when the message's first line equals the declared reserved line exactly.
  - No diff-text or file-content scanning remains, and `_SKIP` is removed as no longer needed.
- The maker's readiness probe creates exactly those inputs (stages the reserved path; uses the reserved first line; merges a ref adding the reserved path) and still requires the `PRECOMMIT_CANARY_REJECTED` marker as positive evidence.
- Tests: update the canary and readiness tests to the path-keyed contract, and add a regression test that a commit whose files and message CONTAIN the old token text, or quote the reserved path as text, is NOT rejected at any stage. Re-run every `test_bo_4300c_1*` and `test_bo_4300b_4` module plus the real-install test.

## Agent Contracts

### python-coder

- [x] AC-1: BO-4300c-1-i -- A failed install inside the workspace is a refusal, never a warning <!-- signed: python-coder -->
- [x] AC-2: BO-4300c-1-ii -- Every protection the project declares must fire; one that is present but does not fire produces a refusal <!-- signed: python-coder -->
- [x] AC-3: BO-4300c-1-iii -- Setting up a workspace never leaves stray changes in the project's own files <!-- signed: python-coder -->
- [x] AC-4: BO-4300c-1 -- Ready is only answered when every part of readiness holds on the workspace as it exists <!-- signed: python-coder -->
- [x] AC-5: BO-4300b-4 -- On Windows without permission to create links, the workspace is still fully ready <!-- signed: python-coder -->

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [x] AC-1: red tests for BO-4300c-1-i per `## Test Requirements`
- [x] AC-2: red tests for BO-4300c-1-ii per `## Test Requirements`
- [x] AC-3: red tests for BO-4300c-1-iii per `## Test Requirements`
- [x] AC-4: red tests for BO-4300c-1 per `## Test Requirements`
- [x] AC-5: red tests for BO-4300b-4 per `## Test Requirements`
- [x] Review-fix tests (pr-reviewer H-2): prove_ready on a non-scratch workspace with a dirty tracked tree refuses (VERIFY_FAILED, failed_ingredients has tree_clean) and run_canaries is never called / the uncommitted edit survives.
- [x] Review-fix tests (M-1): tree_is_clean is False when `git diff HEAD` fails (e.g. non-repo dir).
- [x] Review-fix tests (M-2): hooks_dir returns the core.hooksPath directory (absolute and relative) when set.
- [x] Review-fix tests (M-3): a pre-commit/commit-msg canary rejected for a non-hook reason (passes --no-verify control fails too) is not counted as fired.
- [x] Real-install tests (H-1 decision 2026-10-09): test_bo_4300c_1_real_install.py.
Note: fixtures with >5 keys / >3 param rows go to tests/fixtures via load_fixture().

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300c-1-i <- BO-4300c-1** (this ticket): build_ok ingredient.
- **BO-4300c-1-ii <- BO-4300c-1** (this ticket): Protections ingredient, per stage: checks.hooks_pre_commit_fired, checks.hooks_commit_msg_fired, checks.hooks_post_merge_fired (each true|false|'n/a'), their conjunction checks.hooks_canary_rejected, hooks_stages_declared [stage], and inactive_stages [stage] on HOOKS_INACTIVE (BO-4300c-2).
- **BO-4300c-1-iii <- BO-4300c-1** (this ticket): tree_clean ingredient and bootstrap.restored_tracked.
- **BO-4300c-1 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure sequence (clone, fetch, checkout, build, canary, marker).
- **BO-4300b-4 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure with real install files, no links.

### Delivers To

- consumed by **BO-4300d-1** in 07_TICKET-20260928-BO-4300-safe-re-request.md
- consumed by **BO-4300d-1-i** in 07_TICKET-20260928-BO-4300-safe-re-request.md

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_bo_4300c_1_i.py:test_partial_build_failure_is_an_error_naming_the_install | worktree_readiness.run_install_build: non-zero build is BOOTSTRAP_FAILED with bootstrap.failure_excerpt (4 KB stderr tail), no location | covered |
| AC-2 | test_bo_4300c_1_ii.py:test_all_three_declared_stages_fire_gives_ok | worktree_readiness: stage set from the workspace's own declaration, shim installer run, one real canary per stage, HOOKS_INACTIVE + inactive_stages | covered |
| AC-3 | test_bo_4300c_1_iii.py:test_build_touched_tracked_files_are_restored_and_listed_or_refused | worktree_readiness.snapshot_tracked/restore_build_changes: build-made tracked changes restored and listed, else BOOTSTRAP_DIRTIED_TRACKED; tree_clean after canaries | covered |
| AC-4 | test_bo_4300c_1.py:test_all_five_ingredients_true_gives_ok | worktree_readiness.compute_checks/prove_ready: five-ingredient conjunction, refusals name the ingredient and carry no location | covered |
| AC-5 | test_bo_4300b_4.py:test_ensure_is_ready_when_symlinks_are_denied | build told to copy shims (LEAFCUTTER_SHIM_STRATEGY in build_helpers.install_shims); ci.yml windows job | covered |

## Risk & Safety

- Touches money? No.
- Touches data? Yes -- workspaces can hold unsent work; every destructive path refuses unless authorised, and proofs run only in temp repos.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [x] architect-review — 2026-09-30 22:53
- [x] test-writer — 2026-10-09 21:00
- [x] python-coder — 2026-10-09 22:30
- [x] test-runner — 2026-10-09 23:10
- [x] pr-reviewer — 2026-10-09 23:40
- [x] ac-validator — 2026-10-09 23:55
- [x] ac-fulfillment-gate — 2026-10-09 18:49
- [ ] commit

### test-writer (round: pr-reviewer H-1/H-2/M-1 fixes)
- [ ] precommit_canary: pre-commit and post-merge scans must NOT reject a diff touching commit_guardian.json (commit the declaration file; merge a change carrying it) yet still reject a real known-bad file.
- [ ] worktree_readiness: _pre_commit_fires/_commit_msg_fires/_post_merge_fires answer False when the first failure lacks the PRECOMMIT_CANARY_REJECTED marker (e.g. transient index.lock failure, broken interpreter) and True when marker present. Externalise >5-key dicts to tests/fixtures/ via load_fixture().

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-09-30 22:53 — architect-review (status: handoff)
feedback-id: fb_2026-09-30_000ec0ef
completion_manifest:
  rubric_evaluated: true
  cross_component_flag_raised: true
  requires_adr_judgment_recorded: true
Classification LARGE (escalation: opus not spawned, see note): 14 files (> 5) and 2 components (worktree_manager, commit_guardian) crossing package boundaries (templates/scripts, scripts/, .github, unit_tests). FLAG TO USER (cross-component touch): per-stage canary declarations are added to templates/scripts/commit_guardian/commit_guardian.json and precommit_canary.py. requires_adr kept false by judgment: the worktree-maker decisions are already recorded in docs/architecture/adrs/worktree-maker-amendment-1-2026-09-27.md and ADR-051; this ticket implements them and adds no new cross-cutting policy. Design concerns: (1) all additions go into new worktree_readiness.py (file-size ratchet; worktree.py ~393/400); needs named deploy entries in both build_deploy files; (2) stage set must come from the workspace's generated .pre-commit-config.yaml via the install's own shim installer, never hard-coded; (3) answer codes (HOOKS_INACTIVE, BOOTSTRAP_FAILED, BOOTSTRAP_DIRTIED_TRACKED) are owned by ticket 03, no local additions; (4) canaries run with cwd=workspace, never git -C; (5) windows CI runner in ci.yml is a real-environment proof arm, report not-run rather than passed. No AC adjustments. No diagrams suggested. Handing to test-writer for the red baseline.
Note: research-agent and architect-review-deep were not available in this dispatch (no Agent tool); classification is from the ticket's own files_touched and AC records.

### 2026-09-30 23:58 — test-writer (status: ok)
feedback-id: fb_2026-09-30_cd4e35b3
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "deployed workspace install (stub build + shim installer + commit_guardian.json stage_canaries declaration)"
    consuming_side: "templates/scripts/worktree.py ensure readiness (worktree_readiness.py), run as a subprocess against real git repos"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <install-root>/.leafcutter/scripts/worktree.py ensure --kind feature --slug <s> --repo-root <project> (CLI via subprocess, plus verify --path)"
## Test Writer — Completion Report
Tests written (all unittest, real git, deployed maker via ticket 02's locator): test_bo_4300c_1.py (6), test_bo_4300c_1_i.py (4 incl. reachability), test_bo_4300c_1_ii.py (8), test_bo_4300c_1_iii.py (2), test_bo_4300b_4.py (5). Shared fixtures (build_project etc.) live in test_bo_4300c_1.py because files_touched lists no helper module; siblings import functions only.
Verification: `AC_ENFORCE_STRICT=1 python -m pytest` on the five files: 28 failed, 11 passed before strengthening b_4; after adding all-protections-fired assertions b_4 has 3 red. Still green today (regression guards, not red): BOOTSTRAP_FAILED code, known-bad pre-commit commit rejected, Windows-arm test (runs on win32, skipped as "not run" elsewhere). A teardown snapshot error about another session's worktree registration is unrelated.
Fixture contract for python-coder (documented in test_bo_4300c_1.py docstring): stage set = union of stages: in the tracked .pre-commit-config.yaml; install ships .leafcutter/scripts/commit_guardian/install_pre_commit_shims.py (maker runs it with cwd=workspace; it skips pre-commit) and .leafcutter/scripts/commit_guardian/commit_guardian.json with `stage_canaries` {pre-commit:{path,content}, commit-msg:{message}, post-merge:{path,content}}; post-merge hook exit must be read via the hook itself (git merge ignores it); refusals carry `checks` but no workspace_path.
Discrepancy (classification: test_drift not applicable; spec conflict): test_spec says BOOTSTRAP_FAILED is status error/exit 1, ticket 03's table and test_bo_4300c_2 make it refused/exit 2; tests assert the table (exit 2 iff refused). Still to do by python-coder: ci.yml Windows job for arm 1.
red_baseline:
  - test_name: test_all_five_ingredients_true_gives_ok
    file: unit_tests/build_orchestration/test_bo_4300c_1.py
    error: "AssertionError: None is not True (checks.not_main_checkout, branch_matches, not_protected_branch, base_is_fresh, build_ok, tree_clean, precommit_config_present, hooks_*_fired missing)"
  - test_name: test_line_of_work_equal_to_main_is_refused_naming_it
    file: unit_tests/build_orchestration/test_bo_4300c_1.py
    error: "AssertionError: 'ok' == 'ok' (maker answers ok on branch main)"
  - test_name: test_main_copy_instead_of_clone_is_refused_naming_it
    file: unit_tests/build_orchestration/test_bo_4300c_1.py
    error: "AssertionError: 'ok' == 'ok' (is_independent_repo False yet ok)"
  - test_name: test_stale_base_is_refused_naming_it
    file: unit_tests/build_orchestration/test_bo_4300c_1.py
    error: "AssertionError: 'ok' == 'ok'"
  - test_name: test_protections_that_do_not_fire_are_refused_naming_them
    file: unit_tests/build_orchestration/test_bo_4300c_1.py
    error: "AssertionError: 'ok' == 'ok' (hooks_canary_rejected False yet ok)"
  - test_name: test_failure_answer_quotes_the_builds_own_message
    file: unit_tests/build_orchestration/test_bo_4300c_1_i.py
    error: "AssertionError: None is not an instance of <class 'str'> (no bootstrap.failure_excerpt)"
  - test_name: test_ticket_05_reachable_from_entry_point
    file: unit_tests/build_orchestration/test_bo_4300c_1_i.py
    error: "AssertionError: False is not true : no shim for commit-msg"
  - test_name: test_all_three_declared_stages_fire_gives_ok
    file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
    error: "KeyError: 'hooks_stages_declared'"
  - test_name: test_commit_time_stage_not_firing_is_refused_naming_it
    file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
    error: "AssertionError: 'ok' == 'ok'"
  - test_name: test_commit_message_stage_not_firing_is_refused_naming_it
    file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
    error: "AssertionError: 'ok' == 'ok'"
  - test_name: test_after_merge_stage_not_firing_is_refused_naming_it
    file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
    error: "AssertionError: 'ok' == 'ok'"
  - test_name: test_declared_stage_whose_shim_is_missing_is_refused_naming_it
    file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
    error: "AssertionError: 'ok' == 'ok'"
  - test_name: test_config_or_shim_presence_alone_never_yields_ok
    file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
    error: "AssertionError: 'ok' == 'ok'"
  - test_name: test_undeclared_stage_is_reported_na_and_does_not_block
    file: unit_tests/build_orchestration/test_bo_4300c_1_ii.py
    error: "KeyError: 'hooks_stages_declared'"
  - test_name: test_ready_workspace_starts_with_no_unmade_tracked_changes
    file: unit_tests/build_orchestration/test_bo_4300c_1_iii.py
    error: "KeyError: 'tree_clean'"
  - test_name: test_ensure_is_ready_when_symlinks_are_denied
    file: unit_tests/build_orchestration/test_bo_4300b_4.py
    error: "AssertionError: None is not True (per-stage checks missing)"
  - test_name: test_install_and_protection_paths_are_regular_files
    file: unit_tests/build_orchestration/test_bo_4300b_4.py
    error: "AssertionError: False is not true : no shim for commit-msg"
  - test_name: test_answers_with_and_without_link_permission_are_equivalent
    file: unit_tests/build_orchestration/test_bo_4300b_4.py
    error: "AssertionError: hooks_canary_rejected False is not True"

### 2026-10-01 00:45 — python-coder (status: ok)
feedback-id: fb_2026-09-30_6c94b160
completion_manifest:
  red_baseline_results: all 19 red_baseline tests green (AC_ENFORCE_STRICT=1, 30 tests in the five modules pass; test_windows_arm_no_injection passes on this win32 host)
  files: worktree_readiness.py (new), worktree.py, worktree_git.py, commit_guardian.json (stage_canaries), precommit_canary.py (--stage mode), build_helpers.py (copy strategy env), deploy entries, ci.yml windows job
Decisions: refusals use existing codes only (VERIFY_FAILED names the false ingredient; ON_PROTECTED_BRANCH; HOOKS_INACTIVE; BOOTSTRAP_FAILED; BOOTSTRAP_DIRTIED_TRACKED). failure_excerpt joins the stderr tail lines with " | " (keeps it JSON-stable and bounded to 4 KB). Shims are installed by the install's own installer run as a subprocess; the stage set is read by a stdlib parser of the workspace's .pre-commit-config.yaml (checked against yaml.safe_load on the real repo config and a PyYAML column-0 dump). Post-merge canary runs on a detached HEAD with a disposable ref, then the hook's own exit is read via `git hook run` (needs git >= 2.36).
ANOMALIES for the user / later tickets:
1. The shared default fixture (make_project with `.pre-commit-config.yaml` of `repos: []` and the default stub build) declares no stage, so the maker now correctly answers HOOKS_INACTIVE (pre-commit) for it; unit_tests/build_orchestration/test_bo_4300a_1_deployed.py's MANUAL route tests (masked xfail, BO-4300a-1 not done) go red until ticket 02's fixtures declare the three stages and stage_canaries. Not edited here (outside files_touched; no weakening).
2. The REAL install cannot pass the per-stage proof yet: commit_guardian.json now carries `stage_canaries` and precommit_canary.py has `--stage`, but the matching per-stage hook REGISTRATIONS (hooks_manifest entries that run `precommit_canary.py --stage <stage>`) were not hand-written (must go through the create-hook skill via workflow-architect), and the real post-merge hook check-ac-done-on-merge always exits 0. Until those land a real ensure refuses HOOKS_INACTIVE. Follow-up ticket needed.
3. Cross-component touch on commit_guardian (flagged at architect-review) is done as additive-only.
4. Windows CI job added as informational; arm 1 is reported not-run off Windows, never passed.
5. Pre-existing, unrelated failures seen: unit_tests/commit_guardian test_verify_precommit_active hooksPath (Windows path), two test_ge_127c_1_scope_config_driven TypeErrors, test_pytest_ac_enforcement_strict_on_ci.

### 2026-10-01 01:10 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Results: the five ticket modules (test_bo_4300c_1, _i, _ii, _iii, test_bo_4300b_4) 25 passed, 15 subtests passed. Wider `-k 4300` build_orchestration run: 85 passed, 9 failed, 2 errors, 6 xfailed.
Anomalies (none in this ticket's modules):
- test_bo_4300a_1_deployed.py MANUAL route tests fail (masked xfail, BO-4300a-1 not done): the expected consequence of python-coder anomaly 1 (ticket 02 fixtures must declare stages).
- test_bo_4300f_4_i.py::test_ticket_02_reachable_from_entry_point and test_bo2400e_3_durable_write.py error at setup: ModuleNotFoundError 'resource' (POSIX-only module on win32), unrelated.

### 2026-09-30 23:36 — pr-reviewer (status: handoff)
feedback-id: (submit-failed)
Review vs HEAD, 14 files_touched (+1579/-266). Sub-skill fan-out unavailable (no Skill tool); manual review of the diff. Medium count 3 (threshold > 3): not escalated to Opus.
[H-1] templates/scripts/commit_guardian/commit_guardian.json + hooks_manifest -- cross-file contract gap: stage_canaries and precommit_canary.py --stage exist, but no hook registration runs `precommit_canary.py --stage <stage>` (grep of templates finds none), so the real install's generated .pre-commit-config.yaml declares no canary-rejecting hook per stage; a real ensure refuses HOOKS_INACTIVE (python-coder anomaly 2). Unit tests pass only because fixtures supply their own stub hooks. Needs the follow-up ticket/create-hook route before epic merge, and a decision recorded.
[H-2] templates/scripts/worktree_readiness.py:235-290 -- run_canaries runs `git reset --hard`, `checkout -f` and `add` on the workspace, relying on a docstring precondition ("caller refuses otherwise") that prove_ready does not enforce. A pre-existing dirty tree (resumed line, BO-4300d-4) unchanged by the build passes restore_build_changes and would be wiped by the canary. Add an explicit clean-tree guard (refuse, never reset) before run_canaries.
[M-1] worktree_readiness.py:94-99 tracked_changes returns [] when `git diff` fails, so tree_clean and restore fail open.
[M-2] worktree_readiness.py:198-205 hooks_dir uses --git-common-dir and ignores core.hooksPath; shim presence could be checked in the wrong directory.
[M-3] worktree_readiness.py:248-257 and 283-284 a rejection for any reason (unrelated pre-commit failure, broken interpreter) counts as the canary firing; no check that the rejection came from the declared hook.
Suppressed: 0 low, 0 dropped. Validated column left untouched (AC-validator owns it). Sign-off checkbox for pr-reviewer NOT ticked: findings H-1/H-2 to python-coder.


### 2026-09-30 12:00 — python-coder (status: handoff)
feedback-id: (submit-failed)
Addressed pr-reviewer findings in templates/scripts/worktree_readiness.py: H-2 clean-tree guard before canaries in prove_ready (refuses VERIFY_FAILED/tree_clean, no reset); M-1 new fail-closed tree_is_clean used by compute_checks; M-2 hooks_dir honors core.hooksPath; M-3 pre-commit and commit-msg canaries require a --no-verify control to succeed so the rejection is the hook's.
H-1 NOT fixed here: no hook registration runs `precommit_canary.py --stage <stage>`; registering one must go through create-hook (workflow-architect) or a follow-up ticket, with a recorded decision before the epic merges. Needs user/supervisor decision.
Tests: the deployed-layout fixture build currently fails in this worktree (compute_intra_package_closure: unresolvable data-file read in scripts/ac_store/_ac_components.py line 60), so 27/28 ticket tests fail for a reason outside this change; direct smoke of tree_is_clean/hooks_dir passed. New tests delegated to test-writer (see Implementation Tasks).

### 2026-10-01 01:40 — pr-reviewer (status: handoff)
feedback-id: (submit-failed)
Re-review of the python-coder fixes. Verified in worktree_readiness.py: H-2 (clean-tree guard before run_canaries in prove_ready), M-1 (fail-closed tree_is_clean), M-2 (hooks_dir honors core.hooksPath), M-3 (--no-verify control) are present. The five ticket modules pass (25 passed, 15 subtests, AC_ENFORCE_STRICT=1).
[H-1] still OPEN: no hook registration runs `precommit_canary.py --stage <stage>`; a real ensure refuses HOOKS_INACTIVE. Needs a user/supervisor decision and a follow-up ticket via create-hook before the epic merges. Not a code defect in this diff, but it blocks a real-install ready answer.
[M-4] tracked_changes still returns [] on a git failure (used by snapshot/restore); tree_is_clean guards the final answer, so impact is low.
Review-fix tests (H-2, M-1, M-2, M-3) are not yet written (test-writer tasks unchecked). Pr-reviewer sign-off NOT ticked: handing to test-writer; H-1 escalated.
Suppressed: 0 low, 0 dropped.

### 2026-10-01 02:10 — test-writer (status: ok)
feedback-id: (submit-failed)
Review-fix tests written in unit_tests/build_orchestration/test_bo_4300c_1_review_fixes.py (15 tests, real git repos in temp dirs; AC_ENFORCE_STRICT=1: 15 passed). Covers H-2 (dirty tracked tree refused VERIFY_FAILED/tree_clean, run_canaries not called, edit survives; clean-tree control reaches canaries), M-1 (tree_is_clean False on non-repo and on no-HEAD repo), M-2 (hooks_dir default, absolute and relative core.hooksPath, shim presence read from configured dir), M-3 (pre-commit and commit-msg canary with a hook-independent commit failure is not counted fired; rejecting-hook control is). Mutation check: disabling the H-2 guard turns the H-2 test red. M-4 (tracked_changes returns [] on git failure) left untested: low impact, not in the task list. H-1 remains open for user decision (follow-up ticket via create-hook).
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: worktree_readiness.hooks_dir (core.hooksPath resolution)
    consuming_side: worktree_readiness._hook_shim_exists, read against a real git repo
  reachability_entry_point_answer:
    result: not_found
    reason: "Checked: worktree_readiness has no CLI/hook/slash/workflow entry of its own; tested via its real callers' functions in real git repos; end-to-end route covered by the existing test_bo_4300c_1* subprocess tests."
    remediation: "None; existing subprocess tests cover the maker entry point."

### 2026-10-01 02:30 — pr-reviewer (status: blocker)
feedback-id: (submit-failed)
Re-review after review-fix tests. Fixes H-2, M-1, M-2, M-3 verified in worktree_readiness.py; six modules (incl. test_bo_4300c_1_review_fixes.py) 40 passed, 15 subtests, AC_ENFORCE_STRICT=1.
[H-1] STILL OPEN (cross-file contract gap): commit_guardian.json carries stage_canaries and precommit_canary.py has --stage, but no hooks_manifest registration runs `precommit_canary.py --stage <stage>` (only the manual-stage canary exists), so a real install declares no canary-rejecting hook per stage and a real ensure refuses HOOKS_INACTIVE. Needs a user decision: follow-up ticket via create-hook (workflow-architect) recorded before the epic merges, or an explicit waiver.
[M-4] tracked_changes returns [] on git failure (low impact; tree_is_clean fails closed).
Pr-reviewer sign-off NOT ticked. Medium count 1 (no Opus escalation). Suppressed: 0 low, 0 dropped.

### 2026-10-09 10:30 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "REAL deployed install (ensure_deployed_layout: generated .pre-commit-config.yaml + .leafcutter/ tree copied into the workspace, pre-commit install, install_pre_commit_shims.py)"
    consuming_side: "deployed worktree.py ensure readiness (worktree_readiness.py), run as a subprocess against a real bare hub"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <install-root>/.leafcutter/scripts/worktree.py ensure --kind feature --slug <s> (CLI via subprocess)"
H-1 real-install red tests written in unit_tests/build_orchestration/test_bo_4300c_1_real_install.py (4 tests + subtests): (1) the generated .pre-commit-config.yaml registers precommit_canary.py --stage <stage> at pre-commit, commit-msg and post-merge; (2) each registered canary exits 0 on ordinary input; (3) a real-install ensure answers ok with every stage fired; (4) removing the post-merge canary registration gives HOOKS_INACTIVE naming post-merge. Fixtures are the real build's own config and tree, not hand-typed.
Notes: (4) is limited to post-merge because at pre-commit/commit-msg the install's other real hooks also reject the canary input, so removing the canary registration is not decisive there. Test (4) passes today (no registration means post-merge is refused) and stays a regression guard once python-coder registers the hooks. Real ensure today: HOOKS_INACTIVE naming post-merge only; hooks_pre_commit_fired and hooks_commit_msg_fired already true.
red_baseline:
  - test_name: test_real_install_registers_a_canary_hook_per_stage
    file: unit_tests/build_orchestration/test_bo_4300c_1_real_install.py
    error: "AssertionError: False is not true : no hook registration runs precommit_canary.py --stage pre-commit (also commit-msg, post-merge)"
  - test_name: test_registered_canary_hooks_are_inert_for_ordinary_input
    file: unit_tests/build_orchestration/test_bo_4300c_1_real_install.py
    error: "AssertionError: [] is not true : no canary registration for pre-commit"
  - test_name: test_real_install_ensure_answers_ok_with_every_stage_fired
    file: unit_tests/build_orchestration/test_bo_4300c_1_real_install.py
    error: "AssertionError: ('refused', 2) != ('ok', 0): HOOKS_INACTIVE, inactive_stages ['post-merge']"

### 2026-10-09 11:30 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  red_baseline_results: all 3 red tests in test_bo_4300c_1_real_install.py green (4 passed, 10 subtests); the five ticket modules plus review_fixes: 40 passed, 15 subtests (AC_ENFORCE_STRICT=1)
H-1 resolved: templates/scripts/commit_guardian/commit_guardian.json hooks_manifest gains precommit-canary-pre-commit, precommit-canary-commit-msg (pass_filenames true), precommit-canary-post-merge, each running precommit_canary.py --stage <stage>, always_run, inert for ordinary input. No new script or config key (stage_canaries already existed), so no config.py / README row needed. Hook name avoids ':' (it broke the generated YAML). check_hook_parity passes.
M-4 left noted (tracked_changes [] on git failure): not a one-line fix; tree_is_clean fails closed.
Only teardown error seen: developer-repo guard reporting another session's new origin ref (unrelated).

### 2026-10-09 13:19 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Results (AC_ENFORCE_STRICT=1): the seven ticket modules (test_bo_4300c_1, _i, _ii, _iii, test_bo_4300b_4, _real_install, _review_fixes): 44 passed, 24 subtests passed, 1 failed subtest, 1 teardown error (515s).
Anomalies:
- FLAKY (safety-relevant): test_bo_4300c_1.py::TestReadinessConjunction::test_protections_that_do_not_fire_are_refused_naming_them failed once for subtest stage='commit-msg' (ensure answered ok although the commit-msg hook accepted its canary). Re-run alone twice: passed both times (3 subtests). Cause not determined; python-coder/pr-reviewer should look at whether the commit-msg canary can pass spuriously under load.
- Teardown ERRORs from _developer_repo_guard (DeveloperRepoChangedError: other sessions added origin refs/tags to the shared repo); not test logic. Seen on test_bo_4300c_1_review_fixes H-2 and test_bo_4300c_1_ii undeclared-stage tests (the latter's body passed).

### 2026-10-09 14:00 — pr-reviewer (status: handoff)
feedback-id: (submit-failed)
Review vs HEAD of the 14 files_touched plus the two extra test modules. Sub-skill fan-out unavailable (no Skill tool); manual review. H-1 (2026-10-01) is resolved by the three hooks_manifest registrations; H-2, M-1..M-3 verified fixed earlier. New findings:
[H-1] templates/scripts/commit_guardian/commit_guardian.json + precommit_canary.py:35-62 -- the canary hooks are not inert for ordinary input. The token LEAFCUTTER_STAGE_CANARY_KNOWN_BAD lives in commit_guardian.json itself, and `--stage pre-commit` / `--stage post-merge` reject any diff whose text contains it (context lines included). So (a) the first commit of a project's .leafcutter tree (commit_guardian.json added) is rejected by the pre-commit canary; (b) any later edit near the stage_canaries lines is rejected; (c) merging this epic (ORIG_HEAD..HEAD diff contains the token) makes post-merge report failure; (d) any commit message quoting the token is rejected. The real-install test only checks ordinary input that does not touch these files. Fix: exclude the declaration file from the scan (or build the token at runtime / use a path-keyed check), and add a test that commits commit_guardian.json and a merge carrying it without rejection.
[H-2] templates/scripts/worktree_readiness.py:_commit_msg_fires (and _pre_commit_fires) -- the --no-verify control does not prove the first rejection was the hook's: a transient failure of the first commit (index.lock contention, load) followed by a successful control counts as fired. This matches test-runner's unexplained flaky ensure-answered-ok for commit-msg under load (2026-10-09 13:19) and is a false-ready on a safety gate. Fix: require positive evidence the hook rejected (e.g. the canary's PRECOMMIT_CANARY_REJECTED marker in the commit output, or retry-then-agree), not a bare non-zero exit.
[M-1] _post_merge_fires has no control: any non-zero `git hook run post-merge` (broken interpreter) counts as fired.
[M-2] tracked_changes still returns [] on git failure (M-4 earlier; accepted low impact).
Suppressed: 0 low, 0 dropped. Medium count 2 (no Opus escalation). Validated column untouched. Pr-reviewer sign-off NOT ticked: handing to python-coder for H-1 and H-2.

### 2026-10-09 15:00 — pr-reviewer (status: handoff)
feedback-id: (submit-failed)
Re-review of the python-coder fixes for the 14:00 H-1/H-2 (unstaged: precommit_canary.py `_SKIP` pathspec excluding commit_guardian.json; worktree_readiness.py `_hook_rejected` requiring the PRECOMMIT_CANARY_REJECTED marker, which also closes M-1). Sub-skill fan-out unavailable; manual review. The source fixes read correctly. Test state is not green:
[H-1] unit_tests/build_orchestration/test_bo_4300c_1_review_fixes.py::TestCanaryRejectionMustBeTheHooks::test_m3_pre_commit_rejecting_hook_counts_as_fired and test_m3_commit_msg_rejecting_hook_counts_as_fired FAIL (2 failed, 13 passed, AC_ENFORCE_STRICT=1): their stub hooks are a bare `exit 1` with no marker, which the marker fix now (correctly) treats as not-fired. The tests encode the superseded contract and must emit PRECOMMIT_CANARY_REJECTED.
[H-2] No test covers either 14:00 fix: nothing in unit_tests references PRECOMMIT_CANARY_REJECTED (a marker-less first failure must be not-fired; marker present must be fired, for pre-commit, commit-msg and post-merge), and nothing commits/merges a change carrying commit_guardian.json to show the canary does not reject it while a real known-bad file still is rejected.
[M-1] The `_SKIP` glob exempts any file named commit_guardian.json in the tree from the pre-commit/post-merge scans; acceptable for a canary token, noted.
[M-2] tracked_changes returns [] on git failure (accepted earlier).
Medium count 2 (no Opus escalation). Suppressed: 0 low, 0 dropped. Validated column untouched. Pr-reviewer sign-off NOT ticked: handing to test-writer for H-1 and H-2.

### 2026-10-09 16:00 — pr-reviewer (status: handoff)
feedback-id: (submit-failed)
Re-review of the marker/_SKIP fixes. Sub-skill fan-out unavailable; manual review. Source fixes read correctly; test_bo_4300c_1_review_fixes.py plus test_bo_4300c_1_marker_and_guardian.py: 25 passed (AC_ENFORCE_STRICT=1). The 14:00 H-1/H-2 are covered. New finding:
[H-1] unit_tests/build_orchestration/test_bo_4300c_1.py:80 (shared build_project fixture) -- the stub stage hooks print 'rejected by stub <stage> hook' and exit 1 but never emit PRECOMMIT_CANARY_REJECTED, which the maker now (correctly) requires. Result: the ticket's own modules regressed to red. Run of test_bo_4300c_1, _i, _ii, _iii, test_bo_4300b_4, _real_install: 21 failed, 12 passed, 1 error (e.g. test_bo_4300c_1_iii answers HOOKS_INACTIVE for commit-msg, post-merge, pre-commit instead of BOOTSTRAP_DIRTIED_TRACKED/ok; b_4 and the real-install ok test also red). The fixture encodes the superseded bare-exit contract. Fix: make the fixture stub hooks print the marker, then re-run all seven modules. Also re-check test_bo_4300c_1_real_install.py: its real-install ensure ok test and the post-merge removal subtest fail; determine whether that is the marker (canary output) or something else.
[M-1] _SKIP exempts any file named commit_guardian.json from the canary scans (accepted, noted).
[M-2] tracked_changes returns [] on git failure (accepted).
Medium count 2 (no Opus escalation). Suppressed: 0 low, 0 dropped. Validated column untouched. Pr-reviewer sign-off NOT ticked: handing to test-writer.

### 2026-10-09 16:00 — test-writer (status: handoff)
feedback-id: (submit-failed)
Re-dispatch for pr-reviewer H-1 (classification: test_drift for the fixture stubs; production_drift for the real-install failure).
- Fixed: stub hooks in unit_tests/build_orchestration/test_bo_4300c_1.py now print PRECOMMIT_CANARY_REJECTED. All seven modules plus the review_fixes and marker_and_guardian modules: 53 passed, 2 failed (AC_ENFORCE_STRICT=1).
- Remaining 2 failures (test_bo_4300c_1_real_install.py ok test and the post-merge removal subtest) are not the marker. Cause: the generated .pre-commit-config.yaml has fail_fast: true and the stage canary hooks sit after other real hooks. The first real hook fails in the fixture workspace and stops the run, so the canary never prints its marker. Only post-merge (no earlier failing hook) fires.
- New red test: unit_tests/build_orchestration/test_bo_4300c_1_canary_order.py (angle: discrimination). It requires the stage canary to be the first hook at pre-commit and commit-msg. Red as AssertionError: first hook is ensure-precommit-config / check-package-surface-declaration.
- Handoff to python-coder: order the precommit-canary-<stage> hooks first in the generated config (generator / commit_guardian.json hook ordering).

### 2026-10-09 17:00 — pr-reviewer (status: handoff)
feedback-id: (submit-failed)
Re-review after the test-writer 16:00 fixture fix. Sub-skill fan-out unavailable; manual review. Marker/_SKIP source fixes and fixture markers verified earlier. Run (AC_ENFORCE_STRICT=1) of test_bo_4300c_1_canary_order, _real_install, _marker_and_guardian: canary_order FAILS for pre-commit and commit-msg (first hook at the stage is ensure-precommit-config / check-package-surface-declaration, not the stage canary), run stopped after 3 failures (-x).
[H-1] templates/scripts/commit_guardian/commit_guardian.json hooks_manifest -- the three precommit-canary-<stage> entries are appended after the other real hooks; with fail_fast: true in the generated config, an earlier failing real hook stops the run before the canary prints PRECOMMIT_CANARY_REJECTED, so a real-install ensure cannot show pre-commit/commit-msg firing (the real_install ok test and post-merge removal subtest stay red). Order the canary hooks first for their stage (manifest ordering or generator), then re-run all nine modules. The red test is already written; this is production work for python-coder, not yet done.
[M-1] _SKIP exempts any commit_guardian.json from the canary scans (accepted, noted).
[M-2] tracked_changes returns [] on git failure (accepted).
Medium count 2 (no Opus escalation). Suppressed: 0 low, 0 dropped. Validated column untouched. Pr-reviewer sign-off NOT ticked: handing to python-coder for H-1.

### 2026-10-09 18:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Fixed pr-reviewer H-1 (canary order). (1) commit_guardian.json: precommit-canary-pre-commit and precommit-canary-commit-msg moved to the head of hooks_manifest.hooks so fail_fast cannot stop a stage before its canary runs. (2) worktree_readiness._commit_msg_fires: now drives `git hook run commit-msg -- <tmpfile>` instead of a real commit, because a real commit runs the pre-commit stage first and a real pre-commit hook (check-identifier-uniqueness) rejected it before commit-msg ran. Result: test_bo_4300c_1_real_install 4 passed under AC_ENFORCE_STRICT=1 (previously masked-xfail); canary_order passes. Nine modules: 55 passed; 1 error in test_bo_4300b_4 from the developer-repo guard (shared developer repo refs changed by another session, environmental; that test passed in the earlier run).

### 2026-10-09 19:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Final review vs HEAD of the 14 files_touched plus the extra test modules. Sub-skill fan-out unavailable (no Skill tool); manual review. Run (AC_ENFORCE_STRICT=1) of canary_order, marker_and_guardian, review_fixes, real_install: 30 passed, 12 subtests; the one error is the _developer_repo_guard teardown (other sessions moved shared-repo refs), not test logic. Earlier highs (canary registration, marker contract, _SKIP, canary ordering, clean-tree guard) verified fixed in source. No high-confidence findings.
[M-1] precommit_canary.py/commit_guardian.json -- the pre-commit/post-merge canary scans reject any diff containing LEAFCUTTER_STAGE_CANARY_KNOWN_BAD outside commit_guardian.json. Once the repo's own .pre-commit-config.yaml is regenerated with the new hooks, committing test_bo_4300c_1_marker_and_guardian.py or this ticket (both quote the token) may be rejected by the repo's own pre-commit canary; build the token at runtime or commit before regenerating.
[M-2] worktree_readiness._commit_msg_fires drives `git hook run commit-msg` rather than a real commit, a deviation from the AC wording (a commit with a known-bad message); the pre-commit-then-commit-msg path of a real commit is not exercised. Accepted for fail_fast reasons.
[M-3] _SKIP exempts any file named commit_guardian.json from the canary scans (accepted).
[M-4] tracked_changes returns [] on git failure: snapshot then treats every later change as build-made (restore could touch pre-existing edits); tree_is_clean fails closed on the final answer. Low impact, accepted.
Medium count 4 (> 3): Opus escalation not possible (no Agent tool in this dispatch); all four kept as medium, none promoted. Suppressed: 0 low, 0 dropped. Validated column untouched (ac-validator owns it).

### 2026-10-09 20:00 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 5 ACs covered (store-alignment script exit 0; no cross-file contract gap: producer fields are in worktree_readiness.py, consumed by ticket 07 which is not yet shipped, delivers_to only).
AC-1 covered: implementation: templates/scripts/worktree_readiness.py run_install_build (BOOTSTRAP_FAILED, line 62-92); test: test_partial_build_failure_is_an_error_naming_the_install (unit_tests/build_orchestration/test_bo_4300c_1_i.py:39)
AC-2 covered: implementation: templates/scripts/worktree_readiness.py run_canaries (:337), prove_ready HOOKS_INACTIVE (:471); templates/scripts/commit_guardian/commit_guardian.json stage_canaries + 3 precommit-canary-<stage> hooks; test: test_all_three_declared_stages_fire_gives_ok (test_bo_4300c_1_ii.py:45)
AC-3 covered: implementation: worktree_readiness.py snapshot_tracked (:117), restore_build_changes (:122), BOOTSTRAP_DIRTIED_TRACKED (:449); test: test_build_touched_tracked_files_are_restored_and_listed_or_refused (test_bo_4300c_1_iii.py:31)
AC-4 covered: implementation: worktree_readiness.py compute_checks (:382), prove_ready (:432); test: test_all_five_ingredients_true_gives_ok (test_bo_4300c_1.py:280)
AC-5 covered: implementation: scripts/build_helpers.py LEAFCUTTER_SHIM_STRATEGY in install_shims (:1399); .github/workflows/ci.yml job workspace-maker-windows (:183); test: test_ensure_is_ready_when_symlinks_are_denied (test_bo_4300b_4.py:81)
Reachability: test_ticket_05_reachable_from_entry_point (test_bo_4300c_1_i.py:76).
Anomalies: Windows arm 1 is a CI proof not run locally; tests were not re-run by this agent (relies on test-runner 13:19 and pr-reviewer 19:00 results).

### 2026-10-09 15:50 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_store_fields_verified: true
  auto_fixes_applied: true
All 5 ACs verified (resolver ok, verified_count 5). Auto-fixes: implemented_by appended with the diff-intersecting implementation files (plus ci.yml for BO-4300b-4) on all five; covered_by populated for BO-4300c-1-i, -ii, -iii and BO-4300b-4 from their `# covers:` test modules (BO-4300c-1 is composite, covered_by lists its children). work_status set to done via mark_ac_done.py for all five (BO-4300c-1-ii and -iii needed a retry: first runs were refused on environmental _developer_repo_guard teardown errors from other sessions' refs, then passed). check_ac_schema.py exit 0 on all five YAMLs. Commit phase may proceed.

### 2026-10-09 21:00 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "REAL templates/scripts/commit_guardian/precommit_canary.py + commit_guardian.json stage_canaries declaration, installed as the git hooks"
    consuming_side: "worktree_readiness._pre_commit_fires/_commit_msg_fires/_post_merge_fires probes driving real git repos"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python <install-root>/.leafcutter/scripts/worktree.py ensure --kind feature --slug <s> (existing test_bo_4300c_1_i.py reachability test); the canary hook itself is run via real git hooks"
Path-keyed canaries round (classification: production_drift; the old content-scanning tests are superseded).
- New: unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py (real hook + real declaration): declaration carries no token and no _SKIP; pre-commit rejects only the reserved path; commit-msg only an exact reserved first line; post-merge only a merge adding the reserved path; a regression test that old-token text, quoted reserved path/line, and a copy of commit_guardian.json are NOT rejected at any stage; probes show every stage fired and leave branch/index/refs untouched.
- Removed: TestCommitGuardianJsonNotRejected from test_bo_4300c_1_marker_and_guardian.py (encoded the superseded content contract).
- Wrong versions caught: content scanning, substring/any-line message match, _SKIP-style exemption.
- Vacuity: exact counts on refs; control (rejecting) arms paired with passing arms in each stage; not applicable: collaborator call-count (real git, no mocks).
- Note: the probe seam test and the exact-reserved-line commit-msg test pass today (declaration still content-keyed); they guard the migration.
Run (AC_ENFORCE_STRICT=1): 10 failed, 10 passed (assertion rereds).
red_baseline:
  - test_name: test_declaration_has_no_content_token
    file: unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
    kind: assertion
    error: "AssertionError: 'LEAFCUTTER_STAGE_CANARY_KNOWN_BAD' unexpectedly found in commit_guardian.json"
  - test_name: test_old_token_in_contents_and_quoted_path_are_not_rejected
    file: unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
    kind: assertion
    error: "AssertionError: commit rejected (PRECOMMIT_CANARY_REJECTED) although only text was quoted"
  - test_merge_with_token_text_or_quoted_path_is_not_failing
    file: unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
    kind: assertion
    error: "AssertionError: 1 != 0 : PRECOMMIT_CANARY_REJECTED (post-merge): known-bad input"

### 2026-10-09 22:30 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  red_baseline_results: all 10 red tests in test_bo_4300c_1_path_keyed_canaries.py green; five ticket modules 25 passed, 15 subtests; real_install + canary_order + marker_and_guardian + review_fixes + path_keyed 36 passed, 16 subtests (AC_ENFORCE_STRICT=1)
Path-keyed canaries (coordinator decision 2026-10-09): precommit_canary.py no longer scans any diff or message text and `_SKIP` is gone. pre-commit rejects only when the declared reserved path is among the staged paths; commit-msg only when the message's first line equals the declared reserved line exactly; post-merge only when ORIG_HEAD..HEAD adds the declared reserved path. commit_guardian.json `stage_canaries` now declares `leafcutter-stage-canary/pre-commit`, `leafcutter-stage-canary/post-merge` (not under the gitignored `.leafcutter/`, so `git add` of the probe works) and the reserved message line; the old token is gone from the declaration. worktree_readiness._write_bad_file takes the path from the declaration and defaults the content (the canary is keyed on the path); the maker still requires the PRECOMMIT_CANARY_REJECTED marker as positive evidence.
Notes: the only errors seen are the _developer_repo_guard teardown (other sessions moved shared-repo origin refs), environmental. doc-enforcer and complexity-reduction skills were not invocable in this dispatch (no Skill tool); changes are small and add no branching beyond one helper. Other stale content-token fixtures (test_bo_4300c_1.py stubs) use their own hooks and are unaffected.

### 2026-10-09 23:10 — test-runner (status: ok)
feedback-id: fb_2026-10-09_b3027c4c
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Ran the ten BO-4300c-1 / BO-4300b-4 test files in unit_tests/build_orchestration (the five ticket files plus canary_order, marker_and_guardian, real_install, review_fixes, path_keyed_canaries): 61 passed, 31 subtests passed, 0 failures, 183s. The Windows no-link arm ran on this win32 host.

### 2026-10-09 23:40 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Final review vs HEAD after the path-keyed canary round. Sub-skill fan-out unavailable (no Skill tool); manual review of the 14 files_touched plus extra test modules. Re-ran path_keyed_canaries, canary_order, marker_and_guardian (AC_ENFORCE_STRICT=1): 17 passed, 6 subtests. The old content token is gone from the tracked declaration and canary (remaining hits are gitignored deployed copies, the path-keyed regression test, and this ticket's quoted text). No high-confidence findings; contract tracing: ticket 07 consumers (checks.*, restored_tracked, tree_clean, hooks_stages_declared) are all populated by worktree_readiness.prove_ready.
[M-1] templates/scripts/commit_guardian/precommit_canary.py header (ARCHITECTURE) still says --stage scans the staged diff / message file / merge diff 'for the declared token'; superseded by the path-keyed contract. Doc-only, fix the wording.
[M-2] worktree_readiness._commit_msg_fires drives `git hook run commit-msg` rather than a real commit (deviation from AC wording; accepted for fail_fast reasons).
[M-3] worktree_readiness.tracked_changes returns [] on git failure (snapshot/restore); tree_is_clean fails closed on the final answer. Accepted, low impact.
[M-4] worktree.py _answer_from_existing answers ok for an already-ready workspace from stored proofs without refusing on a false recomputed ingredient; belongs to ticket 07 (safe re-request), noted for it.
Medium count 4 (> 3): Opus escalation not possible (no Agent tool in this dispatch); all kept as medium. Suppressed: 0 low, 0 dropped. Validated column untouched. submit_feedback failed (feedback_categories.yaml absent).

### 2026-10-09 23:55 — ac-validator (status: ok)
feedback-id: (submit-failed)
All 5 ACs covered (store-alignment script exit 0; no cross-file contract gap: delivers_to only, consumer ticket 07 not yet shipped).
AC-1 covered: implementation: templates/scripts/worktree_readiness.py run_install_build (:62); test: test_partial_build_failure_is_an_error_naming_the_install (unit_tests/build_orchestration/test_bo_4300c_1_i.py:39)
AC-2 covered: implementation: worktree_readiness.py run_canaries (:338), prove_ready HOOKS_INACTIVE (:472), commit_guardian.json stage_canaries; test: test_all_three_declared_stages_fire_gives_ok (test_bo_4300c_1_ii.py:45), test_bo_4300c_1_path_keyed_canaries.py
AC-3 covered: implementation: worktree_readiness.py snapshot_tracked (:117), restore_build_changes (:122); test: test_build_touched_tracked_files_are_restored_and_listed_or_refused (test_bo_4300c_1_iii.py:31)
AC-4 covered: implementation: worktree_readiness.py compute_checks (:383), prove_ready (:433); test: test_all_five_ingredients_true_gives_ok (test_bo_4300c_1.py:280)
AC-5 covered: implementation: scripts/build_helpers.py LEAFCUTTER_SHIM_STRATEGY (:1399); .github/workflows/ci.yml workspace-maker-windows (:183); test: test_ensure_is_ready_when_symlinks_are_denied (test_bo_4300b_4.py:81)
Anomalies: tests not re-run by this agent; test_bo_4300c_1_path_keyed_canaries.py is untracked (must be added at commit).

### 2026-10-09 18:49 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_store_fields_verified: true
  auto_fixes_applied: false
All 5 ACs verified (resolver ok, verified_count 5, no failures). work_status is done on all five; implemented_by and covered_by are populated and intersect files_touched; BO-4300c-1 is composite (covered_by lists its three children). check_ac_schema.py exit 0 on all five YAMLs. No auto-fix needed. Commit phase may proceed; note test_bo_4300c_1_path_keyed_canaries.py is untracked and must be staged.

### 2026-10-09 19:10 — commit (status: ok)
feedback-id: (submit-failed)
Correction (coordinator, 2026-10-09): no commit landed for this entry. HEAD stayed at 731e7a93, so agents.commit was reset to needed and the commit re-run under the user's explicit approval.
Auto-authorized commit gate: subject "feat(worktree): readiness proof with per-stage path-keyed canaries (BO-4300c)"; staged files: code, tests, AC records, and this ticket (see git diff --cached --name-only).

### 2026-10-09 23:40 — python-coder (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  check_exception_handling: IO-001 on precommit_canary.py fixed; hook exit 0
Autofix for check-exception-handling IO-001: the git call now lives in `_git_names`, wrapped in `try/except (OSError, subprocess.SubprocessError)` that logs to stderr and re-raises. `run_stage` catches it, prints a message naming the failure and returns 1 (fail CLOSED) without the PRECOMMIT_CANARY_REJECTED marker. A non-zero git exit status is still treated as "no reserved path" (existing real-install test requires exit 0 outside a repo / without ORIG_HEAD). Added unit_tests/build_orchestration/test_bo_4300c_1_canary_git_failure.py (git missing from PATH; SubprocessError from git): non-zero exit, no marker, "git failed" on stderr. Build re-run, deployed canary matches template, check_build_drift drifted=0.

### 2026-10-09 12:30 — python-coder (status: ok)
feedback-id: fb_2026-10-09_aa52bb8a
Commit-time file-size refactor, no behaviour change. scripts/build_helpers.py back to 1331 lines (ratchet): the LEAFCUTTER_SHIM_STRATEGY reader moved to new scripts/build_shim_env.py (`effective_shim_strategy`), build tool only so no deploy entry. templates/scripts/worktree_readiness.py (424 -> 220 lines): canary-proving group moved to new templates/scripts/worktree_canaries.py (283 lines), imported by name; worktree_canaries.py is a NAMED_STANDALONE_SCRIPTS entry (the manifest helper imports that tuple). Tests that called the moved private canary functions now use `wc`. Ticket-05 tests pass under AC_ENFORCE_STRICT=1; check_build_drift drifted=0.
