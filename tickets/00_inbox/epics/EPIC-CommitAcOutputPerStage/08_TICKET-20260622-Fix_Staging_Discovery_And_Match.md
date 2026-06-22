---
advances_current_outcome: true
agents:
  commit: signed_off
  documentation-expert: not_needed
  pr-reviewer: signed_off
  pull-request: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
components:
- ac-driven-dev
created: '2026-06-22'
depends_on:
- 03_TICKET-20260618-ACD-300g-2.md
files_touched:
- scripts/workflows/plan-feature.js
- templates/workflows-js/plan-feature.js
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: ACD-300g-2
status: in_progress
title: 'Fix stage staging: discover all untracked AC files and match AC IDs exactly'
---

# Fix stage staging: discover all untracked AC files and match AC IDs exactly

## Actor / Goal

As the /plan-feature workflow, I want `commitStageOutput()` to stage exactly the
current stage's AC files — no more, no fewer — so that ACD-300g-2 ("the commit
includes ONLY AC files from the current stage") holds under realistic inputs
including fresh AC stores and prefix-nested AC IDs.

## Context

Post-build angle-testing (2026-06-22) found two HIGH staging defects in
`commitStageOutput()`, both defeating ACD-300g-2 under realistic inputs and
neither caught by the existing tests (which only exercise top-level, already-tracked
files with non-colliding IDs):

1. **Untracked files in new subfolders are invisible.** The discovery command
   `git status --porcelain -- docs/acceptance-criteria/` collapses an untracked
   directory to a single `?? <dir>/` line — the individual `.yaml` files are never
   emitted, so the `.yaml`-suffix filter never sees them. A fresh AC store (entirely
   untracked) collapses to one line and commits NOTHING, masked as a benign "skip."
   Fix: use `git status --porcelain --untracked-files=all` (`-uall`).

2. **AC-ID match is ambiguous (substring/prefix false-match).** The filter prose says
   the filename stem "matches one of the AC IDs." Read as substring/prefix, `written=["ACD-300"]`
   wrongly stages `ACD-300g.yaml` and `ACD-300g-2.yaml` — files from LATER stages.
   The AC IDs in this very epic are prefix-nested (`ACD-300` / `ACD-300g` / `ACD-300g-2`),
   so the bug is live. Fix: require EXACT string equality between the filename stem
   and an AC ID in `written`; add an explicit counter-example in the prose.

(Lower-severity, fix opportunistically: porcelain rename lines `R old -> new` are
mis-parsed by the fixed `line[3:]` + rsplit rule.)

## AC References

- Hardens AC ACD-300g-2 (stage-scoped staging) in the executable surface.

## Acceptance Criteria

```gherkin
Scenario: untracked AC files in a new subfolder are staged
  Given a stage wrote new AC YAML files into a previously-untracked subfolder
    under docs/acceptance-criteria/
  When commitStageOutput() discovers files to stage
  Then every individual .yaml file is discovered (untracked-files=all)
  And a fresh, fully-untracked AC store does not silently commit nothing.

Scenario: only the current stage's AC files are staged under prefix-nested IDs
  Given written = ["ACD-300"] and the working tree also contains ACD-300g.yaml and ACD-300g-2.yaml
  When commitStageOutput() filters discovered files
  Then ONLY ACD-300.yaml is staged
  And ACD-300g.yaml and ACD-300g-2.yaml (later stages) are NOT staged.

Scenario: unrelated working-tree changes stay unstaged
  Given a dirty file outside docs/acceptance-criteria/
  When commitStageOutput() stages the stage's AC files
  Then the unrelated file is not staged.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| untracked discovery | | | |
| exact-match filter | | | |
| unrelated stays unstaged | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-22 15:30 — test-runner (status: ok)
feedback-id: fb_2026-06-22_8fe8489e
completion_manifest:
  staging_tests_pass: true
  behavioral_tests_pass: true
  full_suite_pre_existing_failures_verified: true
All 9 staging tests (TestUntrackedSubfolderDiscovery, TestExactAcIdStemMatch, TestUnrelatedChangesStayUnstaged) and all 11 behavioral tests passed. The full suite shows 24 failures, all pre-existing in unrelated files (test_tree_traversal.py, test_transform_hooks_and_autofix_emission.py, test_visualise_knowledge_graph.py) — none touch this ticket's files_touched (plan-feature.js) or test files.

### 2026-06-22 15:00 — python-coder (status: ok)
feedback-id: fb_2026-06-22_46ab7a1e
completion_manifest:
  untracked_files_all_added: true
  exact_stem_equality_with_counter_example: true
  rename_porcelain_format_handled: true
  templates_copy_updated_identically: true
  staging_tests_all_green: true
  behavioral_tests_no_regressions: true
  scripts_and_templates_byte_identical: true
Fixed three defects in `commitStageOutput()` instructions in both `scripts/workflows/plan-feature.js` and `templates/workflows-js/plan-feature.js` (byte-identical after fix). Bug 1: changed `git status --porcelain` to `git status --porcelain --untracked-files=all` so files in new untracked subfolders are discovered individually rather than collapsed to a dir-level entry. Bug 2: changed the ambiguous "matches" filter prose to "is exactly equal to one of the AC IDs" with explicit counter-example ("ACD-300g.yaml must NOT match ACD-300; ACD-300g !== ACD-300"). Bug 3 (opportunistic): added instructions for extracting the NEW path from rename porcelain lines (`R  old -> new` format). All 9 staging tests are now GREEN (2 were RED before fix); all 11 behavioral tests remain GREEN with no regressions; template-parity test confirms byte-identical function bodies.

### 2026-06-22 16:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-22_32e0b3d6
completion_manifest:
  both_js_files_changed: true
  untracked_files_all_present: true
  exact_stem_equality_with_counter_example: true
  rename_porcelain_handled: true
  both_files_byte_identical: true
  nine_tests_present_and_green: true
  unrelated_changes_isolation_confirmed: true
Diff verified against all three ACs. Both `scripts/workflows/plan-feature.js` and `templates/workflows-js/plan-feature.js` receive identical 29-line changes (byte-identical per diff index). The git status command gains `--untracked-files=all`; the filter prose is changed to "is EXACTLY equal to one of the AC IDs" with the explicit counter-example "ACD-300g.yaml must NOT match ACD-300 (stems must be identical, not merely prefix-equal; ACD-300g !== ACD-300)"; rename porcelain lines (`R  old -> new`) are handled opportunistically. `unit_tests/test_commit_stage_output_staging.py` contains 9 tests across 3 classes covering all three Gherkin scenarios; test-runner confirmed all 9 green with no regressions. No issues found.

### 2026-06-22 16:30 — commit (status: ok)
feedback-id: fb_2026-06-22_commit_08
completion_manifest:
  staged_files_verified: true
  ticket_sign_off_applied: true
  commit_issued: true
All 4 files staged (scripts/workflows/plan-feature.js, templates/workflows-js/plan-feature.js, unit_tests/test_commit_stage_output_staging.py, ticket). Frontmatter updated commit: signed_off; Sign-offs checkbox checked. Commit issued with the authorized message.

### 2026-06-22 17:00 — pull-request (status: ok)
feedback-id: fb_2026-06-22_c603ff4a
completion_manifest:
  branch_pushed_to_existing_pr: true
  pr_114_confirmed_open: true
Branch EPIC-CommitAcOutputPerStage pushed to origin (9a303a8..d2593c2). PR #114 ("feat(plan-feature): commit approved AC stage output before next dispatch (ACD-300g-1)") is confirmed OPEN and updated with ticket 08 changes.

### 2026-06-22 14:30 — test-writer (status: ok)
feedback-id: fb_2026-06-22_980056e0
completion_manifest:
  behavioral_tests_written: true
  tests_are_red_against_current_code: true
  ruff_clean: true
  scratch_git_repo_pattern_used: true
Wrote `unit_tests/test_commit_stage_output_staging.py` (9 tests across 3 classes) using the vm.Script replay pattern from ticket 07. Red baseline: 2 FAILED, 7 PASSED against current `plan-feature.js`. Failing tests: `test_instructions_specify_untracked_files_all` (Defect 1 — missing `--untracked-files=all`) and `test_instructions_require_exact_stem_equality` (Defect 2 — ambiguous "matches" language). The 7 passing tests document the buggy current behaviour (collapsed porcelain output, prefix false-match) and confirm the green path for the unrelated-changes isolation scenario. All ruff E722/BLE001/TRY checks pass.

## Implementation Tasks
- [x] Add `--untracked-files=all` to the porcelain discovery command.
- [x] Change the AC-ID filter to exact stem equality (not substring/prefix); add a prose counter-example (`ACD-300g.yaml` must NOT match `ACD-300`).
- [x] (Opportunistic) handle the `R old -> new` rename porcelain format.
- [x] Apply identical changes to `templates/workflows-js/plan-feature.js`.
- [x] Add a behavioral test replaying the prefix-nested + untracked-subfolder cases in a scratch git repo.

## Sign-offs
- [x] test-writer — 2026-06-22 14:30
- [x] python-coder — 2026-06-22 15:00
- [x] test-runner — 2026-06-22 15:30
- [x] pr-reviewer — 2026-06-22 16:00
- [x] commit — 2026-06-22 16:30
- [x] pull-request — 2026-06-22 17:00

## Risk & Safety
- Touches money? No.
- Touches data? Affects which files the AC-authoring workflow stages; no destructive ops.
- Reversibility? Fully reversible.
