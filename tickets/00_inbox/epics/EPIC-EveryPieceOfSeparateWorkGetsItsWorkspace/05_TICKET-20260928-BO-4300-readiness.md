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
ac_coverage: 0/5
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_readiness.py
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

- [ ] AC-1: BO-4300c-1-i -- A failed install inside the workspace is a refusal, never a warning
- [ ] AC-2: BO-4300c-1-ii -- Every protection the project declares must fire; one that is present but does not fire produces a refusal
- [ ] AC-3: BO-4300c-1-iii -- Setting up a workspace never leaves stray changes in the project's own files
- [ ] AC-4: BO-4300c-1 -- Ready is only answered when every part of readiness holds on the workspace as it exists
- [ ] AC-5: BO-4300b-4 -- On Windows without permission to create links, the workspace is still fully ready

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

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300c-1-i -- A failed install inside the workspace is a refusal, never a warning
- [ ] AC-2: BO-4300c-1-ii -- Every protection the project declares must fire; one that is present but does not fire produces a refusal
- [ ] AC-3: BO-4300c-1-iii -- Setting up a workspace never leaves stray changes in the project's own files
- [ ] AC-4: BO-4300c-1 -- Ready is only answered when every part of readiness holds on the workspace as it exists
- [ ] AC-5: BO-4300b-4 -- On Windows without permission to create links, the workspace is still fully ready

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300c-1-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300c-1-ii per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300c-1-iii per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300c-1 per `## Test Requirements`
- [ ] AC-5: red tests for BO-4300b-4 per `## Test Requirements`

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
