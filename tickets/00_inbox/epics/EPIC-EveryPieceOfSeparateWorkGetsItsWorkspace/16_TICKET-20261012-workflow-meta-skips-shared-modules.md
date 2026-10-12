---
title: "check-workflow-meta treats a shared module under templates/workflows-js/_shared/ as a workflow"
status: todo
components:
  - commit_guardian
  - build_orchestration
created: '2026-10-12'
last_updated: '2026-10-12'
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
change_target: infrastructure
risk_surface: internal
complexity: low
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - found-during-ticket-10
files_touched:
  - templates/scripts/commit_guardian/check_workflow_meta.py
  - templates/scripts/commit_guardian/commit_guardian.json
  - unit_tests/commit_guardian/test_check_workflow_meta.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
---

# check-workflow-meta treats a shared module under templates/workflows-js/_shared/ as a workflow

## Actor / Goal
In order for ticket 10's shared workspace-answer block to be committed, the workflow-meta gate must check only workflow scripts, the direct children of `templates/workflows-js/`, and not the shared modules the build inlines into them.

## Context
- **Found:** 2026-10-12, at ticket 10's commit phase. The commit was refused with `no 'export const meta' block found` for `templates/workflows-js/_shared/workspace-answer.js`.
- **Design it conflicts with:** BO-4300c-3 places that block in "a single tracked source outside the deployed workflow set (e.g. templates/workflows-js/_shared/)". The block is a fragment the build inlines into each workflow (`scripts/build_phases_workflows.py` `_inline_workspace_answer`). It is not a workflow, and it has no `meta` by design.
- **Cause:** the two halves of the gate disagree about scope.
  - The staged-file filter (`check_workflow_meta.py`, `startswith("templates/workflows-js/") and endswith(".js")`) and the hook's `files:` pattern in `commit_guardian.json` (`^templates/workflows-js/.*\.js$`) match any depth.
  - The full-scan path (`_scan_all_workflow_js`) only lists the top level.
- Ticket 10 cannot commit until this lands. The hook file is outside ticket 10's `files_touched`, so it is this separate ticket (CLAUDE.md ticket mandate).

## Scope
1. Restrict both the staged-file filter and the `files:` pattern to direct children of `templates/workflows-js/` (`^templates/workflows-js/[^/]+\.js$`), so both paths agree with `_scan_all_workflow_js`.
2. Tests:
   - A staged `templates/workflows-js/_shared/x.js` with no meta is not checked, and the hook exits 0.
   - A staged top-level workflow with no meta is still refused.
   - The registered `files:` pattern does not match a `_shared/` path but does match a top-level `*.js`.
3. Rebuild so the generated `.pre-commit-config.yaml` carries the new pattern.

## Out of Scope
- What the meta block must contain, and the variant transform.

## Sign-offs
- [x] test-writer — 2026-10-12 22:14
- [x] python-coder — 2026-10-12 22:40
- [x] pr-reviewer — 2026-10-12 23:05
- [x] commit — 2026-10-12 23:20

## Comments

### 2026-10-12 22:14 — test-writer (status: ok)
feedback-id: fb_2026-10-12_b3a4a8dc
completion_manifest:
  tests_written_and_red: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "templates/scripts/commit_guardian/commit_guardian.json check-workflow-meta files: regex (read from the JSON)"
    consuming_side: "check_workflow_meta.py staged-file filter, run as a real subprocess in a temp git repo"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python templates/scripts/commit_guardian/check_workflow_meta.py with no argv, cwd = temp git repo with a staged file (CLI via subprocess)"
red_baseline:
  - test_name: TestSharedModulesOutOfScope::test_staged_shared_module_without_meta_is_not_checked
    file: unit_tests/commit_guardian/test_check_workflow_meta.py
    kind: assertion
    error: "AssertionError: 'no `export const meta` block found' unexpectedly found in 'FAIL: templates/workflows-js/_shared/x.js — no `export const meta` block found'"
  - test_name: TestSharedModulesOutOfScope::test_registered_files_pattern_excludes_shared_includes_top_level
    file: unit_tests/commit_guardian/test_check_workflow_meta.py
    kind: assertion
    error: "AssertionError: pattern '^templates/workflows-js/.*\\.js$' must not match a _shared/ module"
Added 3 tests to the existing module (400 lines). The top-level-refused regression guard is green today by design.

### 2026-10-12 22:40 — python-coder (status: ok)
feedback-id: fb_2026-10-12_7198e762
completion_manifest:
  staged_filter_direct_children_only: done
  hook_files_pattern_direct_children_only: done
  rebuilt_pre_commit_config: done
red_baseline_results:
  - test_name: TestSharedModulesOutOfScope::test_staged_shared_module_without_meta_is_not_checked
    result: green
  - test_name: TestSharedModulesOutOfScope::test_registered_files_pattern_excludes_shared_includes_top_level
    result: green
  - test_name: TestSharedModulesOutOfScope::test_staged_top_level_workflow_without_meta_is_refused
    result: green
Files: templates/scripts/commit_guardian/check_workflow_meta.py (staged filter + DECISION HISTORY, 371 lines), templates/scripts/commit_guardian/commit_guardian.json (check-workflow-meta files: `^templates/workflows-js/[^/]+\\.js$`). test_check_workflow_meta.py: 13 passed.

### 2026-10-12 23:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-12_8a552920
No high findings. Medium: M-1 the check-reachability hook `files:` still matches any depth (`templates/workflows-js/.*\.js`), so a `_shared/` module will reach it; M-2 `_shared/` does not exist on this lane tip, so the out-of-scope behaviour is verified by pattern and synthetic path only. All 8 top-level workflows still match the new pattern; no workflow lives in a subdirectory.

### 2026-10-12 23:20 — commit (status: ok)
feedback-id: fb_2026-10-12_6ae6fec9
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "fix(commit-guardian): check-workflow-meta checks only top-level workflows, not _shared/ modules"; 4 staged files (check_workflow_meta.py, commit_guardian.json, test_check_workflow_meta.py, this ticket).
