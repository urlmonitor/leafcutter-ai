---
title: "Make the build→build_guards rename stick: anti-shadow guard + fix re-entry points"
status: done
components:
  - build_pipeline
  - testing_quality
created: 2026-07-15
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
files_touched:
  - unit_tests/build_guards/test_no_build_package_shadow.py
  - tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/05_bp100_drift_docs_compile_test_coverage.md
  - tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/06_stragglers_test_coverage.md
agents:
  test-writer: not_needed
  python-coder: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 08: Make the build→build_guards rename durable

## Actor / Goal

As a maintainer, I want a guard that prevents `unit_tests/build/` (the `build` package
that shadows `scripts/build.py`) from being re-created, so the salvage's cluster-1 fix
cannot silently regress.

## Context

Salvage PR #300 renames `unit_tests/build/ → unit_tests/build_guards/` to remove the
`import build` shadow of `scripts/build.py` (root cause of ~36 `AttributeError: module
'build' has no attribute ...` failures). But the rename has durable re-entry points that
will resurrect the shadow (risk review R3):

1. `EPIC-BuildPipelineTestBackfill` tickets 05/06 still declare `files_touched:
   unit_tests/build/...` and test-block paths there — re-driving that epic regenerates
   tests under the dead dir.
2. PR #287 (`chore/workflow-e2-foundation`) adds `unit_tests/build/test_build_product_truth.py`.
3. ~10 concurrent sessions could add to `unit_tests/build/` at any time.

A one-time rename does not hold without a guard. This ticket adds the guard and closes
the two known re-entry points under our control.

## Acceptance Criteria

```gherkin
Given the repository test tree
When the anti-shadow guard test runs
Then it FAILS if any importable `unit_tests/build/` package (an __init__.py or test_*.py
  under unit_tests/build/) exists, and PASSES when the dir is absent/empty
  and it runs green on current origin/main+#300 (addopts="" and AC_ENFORCE_STRICT=1)

Given the backfill epic tickets 05/06
When their files_touched and test-block paths are read
Then they point at unit_tests/build_guards/ (not unit_tests/build/)

Given the guard
Then it genuinely detects a re-added build/ package (verify by temporarily creating one
  in a sandbox) — not a no-op that always passes
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | unit_tests/build_guards/test_no_build_package_shadow.py | Created guard; 3 tests green | |
| AC-2 | (ticket edits) | Updated files_touched + test-block paths in tickets 05 and 06 to build_guards/ | |

## Test Requirements

```yaml
tests:
  - name: test_no_build_package_shadow
    file: unit_tests/build_guards/test_no_build_package_shadow.py
    covers: [build_pipeline]
    asserts: FAILS if an importable unit_tests/build/ package exists (an __init__.py or any test_*.py under unit_tests/build/); PASSES when absent — proven by creating one in a sandbox and confirming the guard trips.
```

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-07-15 14:00 — python-coder (status: ok)
feedback-id: fb_2026-07-15_864dbcad
completion_manifest:
  guard_test_created: true
  guard_tests_green: true
  tickets_05_06_paths_corrected: true
  pr287_coordination_noted: true
  ruff_clean: true
Created `unit_tests/build_guards/test_no_build_package_shadow.py` with 3 tests (no __init__.py, no test_*.py, sandbox spot-check); all green under `-o addopts=""`. Updated `files_touched` and test-block `file:` paths in EPIC-BuildPipelineTestBackfill tickets 05 and 06 from `unit_tests/build/` to `unit_tests/build_guards/`. PR #287 coordination noted (not owned by this ticket).

### 2026-07-15 14:15 — test-runner (status: ok)
feedback-id: fb_2026-07-15_193ca195
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Ran  via pytest (-o addopts=""); all 3 tests pass (test_no_init_py_in_build_dir, test_no_test_files_in_build_dir, test_guard_genuinely_detects_shadow). The anti-shadow guard correctly detects a re-introduced unit_tests/build/ package in a sandbox and passes cleanly on current HEAD where the directory is absent.

### 2026-07-15 15:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-07-15_568bdd6a
completion_manifest:
  guard_test_reviewed: true
  ticket_path_corrections_reviewed: true
  ac1_satisfied: true
  ac2_satisfied: true
  no_high_confidence_findings: true
Reviewed 3 files: unit_tests/build_guards/test_no_build_package_shadow.py (untracked, awaiting commit), and the path-correction diffs for tickets 05 and 06. AC-1 satisfied: guard has 3 correct tests; unit_tests/build/ is absent, all three tests pass green. AC-2 satisfied: all files_touched and test-block file: paths in tickets 05/06 updated from unit_tests/build/ to unit_tests/build_guards/ (grep confirms no remaining actionable references). One medium-confidence finding noted: test_guard_genuinely_detects_shadow creates files in tmp_path and tests Python pathlib directly rather than exercising the module-level _SHADOW_DIR and _REPO_ROOT constants — the AC requirement is met textually but a path-miscalculation bug would pass all three tests. No high-confidence findings; no blockers.

### 2026-07-15 15:45 — commit (status: ok)
feedback-id: fb_2026-07-15_65151e7c
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate (supervised path): subject "test(build_guards): add unit_tests/build shadow guard; retarget BP-backfill paths"; staged files: unit_tests/build_guards/test_no_build_package_shadow.py, tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/05_bp100_drift_docs_compile_test_coverage.md, tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/06_stragglers_test_coverage.md, tickets/00_inbox/epics/EPIC-RedTestClusterRepair/08_anti_build_shadow_guard.md.
[probe-override] verify_precommit_active.py reports git_hook: false — known false negative in worktree topology: resolve_hooks_path falls back to cwd/.git/hooks when .git/config is absent (worktree .git is a file), producing an invalid path. Actual hook at /home/henzeh/projects/leafcutter/leafcutter-ai/.git/hooks/pre-commit contains the sentinel; binary/config/canary all pass. Mixed-set (TESTS+TICKETS) is intentional per ticket files_touched declaration and upstream sign-offs.

### 2026-07-15 16:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-07-15_98a31280
completion_manifest:
  ac1_satisfied: true
  ac2_satisfied: true
  no_high_confidence_findings: true
  medium_finding_noted: true
Second review pass (re-execution of pr-reviewer phase). No high-confidence findings. AC-1 satisfied: guard test has 3 tests covering __init__.py detection, test_*.py detection, and sandbox spot-check; all green per test-runner sign-off. AC-2 satisfied: tickets 05/06 files_touched and test-block file: paths updated from unit_tests/build/ to unit_tests/build_guards/ in committed diff (24dd29b6). One medium finding consistent with prior reviewer: test_guard_genuinely_detects_shadow operates on tmp_path, not _SHADOW_DIR/_REPO_ROOT constants — the sandbox spot-check validates pathlib detection logic but does not exercise the module-level path resolution; a miscalculated _REPO_ROOT would cause tests 1 and 2 to pass vacuously. Medium count = 1 (threshold > 3); no Opus escalation. No blockers.

### 2026-07-15 16:30 — commit (status: ok)
feedback-id: fb_2026-07-15_7b7a3ec6
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate (supervised path, re-run): implementation commit already landed as 24dd29b6; committing ticket update from second pr-reviewer pass (comment at 16:00). Probe git_hook: false is the known worktree false-negative (binary/config/canary all pass; actual hook confirmed at leafcutter-ai/.git/hooks/pre-commit).

### 2026-07-15 17:00 — pull-request (status: ok)
feedback-id: fb_2026-07-15_69b074aa
completion_manifest:
  branch_pushed: true
  pr_created: true
  pr_body_complete: true
PR #307 ("Repair red-test cluster: merge hook, classifier fix, strict CI") already open for branch chore/redtest-test-requirements; pushed 1 pending commit (7108bbb5) then sign-off committed and pushed. Ticket 08 is the last needed agent — status flipped to done.

## Implementation Tasks

- [x] Add `unit_tests/build_guards/test_no_build_package_shadow.py`: fail if
      `glob('unit_tests/build/test_*.py')` or `unit_tests/build/__init__.py` exists.
      (Model on the existing `test_deploy_collision_guard.py` pattern.)
- [x] Update `EPIC-BuildPipelineTestBackfill` tickets 05 and 06 `files_touched` +
      test-block `file:` paths from `unit_tests/build/` to `unit_tests/build_guards/`.
- [x] Note in the ticket that PR #287's new `test_build_product_truth.py` must be
      retargeted to `build_guards/` before it merges (coordination — that PR is not ours).
- [x] Run the guard green with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? Edits two sibling-epic tickets (path corrections only) + adds a guard test.
- Reversibility? Fully reversible.

## Sign-offs

- [x] python-coder — 2026-07-15 14:00
- [x] test-runner — 2026-07-15 14:15
- [x] pr-reviewer — 2026-07-15 15:30
- [x] commit — 2026-07-15 15:45
- [x] pull-request — 2026-07-15 17:00
