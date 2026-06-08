---
title: "Fix pre-commit auto-fix hooks that modify files and exit non-zero (infinite loop on large commits)"
status: todo
components:
  - build_pipeline
created: 2026-06-08
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
files_touched:
  - scripts/commit_guardian/check_ac_governance.py
  - scripts/commit_guardian/check_ac_parent_covered_by.py
  - scripts/commit_guardian/check_placeholder_defaults.py
  - templates/commit-guardian/hooks/check_ac_limits.py
  - templates/scripts/commit_guardian/check_ac_limits.py
---

# Fix pre-commit auto-fix hooks that modify files and exit non-zero (infinite loop on large commits)

## Actor / Goal

In order to commit batches of files without infinite-loop failures, we need to fix 4 pre-commit hooks that currently modify files AND exit non-zero, so that large batch commits (such as the observed 251-file commit) complete without requiring SKIP overrides.

## Context

During a 251-file batch commit, 4 hooks had to be manually SKIPped because they caused an infinite loop:

- `check-ac-tree-limits` (`check_ac_limits.py`): writes advisory comments into AC YAML, exits 1 on advisory-only findings.
- `check-placeholder-defaults` (`check_placeholder_defaults.py`): auto-fixes placeholder patterns, exits 1.
- `check-ac-governance` (`check_ac_governance.py`): auto-fixes governance fields, exits 1.
- `check-ac-parent-covered-by` (`check_ac_parent_covered_by.py`): auto-fixes `covered_by`, exits 1. Also cannot handle stash conflicts on large batches.

**Root cause**: pre-commit's stash-and-restore mechanism runs hooks against the _staged_ snapshot. When a hook modifies a file on disk AND exits non-zero, pre-commit restores the stash (reverting the modification), then retries — the hook fires again, modifies again, exits 1 again. This never converges.

**Secondary failure**: pre-commit's stash/restore mechanism itself breaks on large batches with many unstaged files — the patch fails to apply on restore, corrupting the working tree.

**Required fix** — each hook must follow exactly one of two patterns:

- **Pattern A (auto-fix)**: modify files, then exit 0. pre-commit detects the file change, re-runs the hook on the modified file, and the commit proceeds when the hook exits 0 on the clean file.
- **Pattern B (report-only)**: do NOT modify files; exit 1 with an actionable error message that tells the developer exactly what to fix manually.

**The current hybrid (modify + exit 1) must be eliminated from all 4 hooks.**

Note: `check_ac_limits.py` exists in two locations — both the template source (`templates/commit-guardian/hooks/check_ac_limits.py`) and the generated copy (`templates/scripts/commit_guardian/check_ac_limits.py`) must be updated. Check the build pipeline to confirm which file is canonical and update that one; the other may be regenerated or require a parallel update.

## Acceptance Criteria

- [ ] AC-1: `check_ac_governance.py` — when it detects a governance violation, it either (a) modifies the file and exits 0, OR (b) does not modify the file and exits 1 with an actionable message. It does NOT do both.
- [ ] AC-2: `check_ac_parent_covered_by.py` — when it detects a missing `covered_by` back-link, it either (a) modifies the parent file and exits 0, OR (b) does not modify any file and exits 1 with an actionable message. It does NOT do both.
- [ ] AC-3: `check_placeholder_defaults.py` — when it detects the combined placeholder-default signal, it either (a) modifies the file and exits 0, OR (b) does not modify any file and exits 1 with an actionable message. It does NOT do both.
- [ ] AC-4: `check_ac_limits.py` — when it detects AC count limit violations or writes advisory comments, it either (a) modifies the file and exits 0, OR (b) does not modify any file and exits 1 with an actionable message. It does NOT do both.
- [ ] AC-5: A previously-failing 3-file batch commit (simulating the infinite-loop scenario) completes without requiring any `SKIP=` override after these fixes land. The test uses a fixture directory and verifies the hooks converge (exit 0 after at most one auto-fix cycle).
- [ ] AC-6: Unit tests for each fixed hook verify the new single-pattern behavior: for Pattern A hooks, the test confirms the file is modified and the exit code is 0; for Pattern B hooks, the test confirms the file is NOT modified and the exit code is 1.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Audit each hook's current behavior: document whether it currently modifies files (and where) and under what conditions it exits non-zero.
- [ ] For each hook, decide Pattern A or Pattern B based on whether auto-fix is safe (idempotent, deterministic, non-destructive). Document the decision as a comment in the module's DECISION HISTORY block.
- [ ] Implement Pattern A or B for `check_ac_governance.py`.
- [ ] Implement Pattern A or B for `check_ac_parent_covered_by.py`.
- [ ] Implement Pattern A or B for `check_placeholder_defaults.py`.
- [ ] Implement Pattern A or B for `check_ac_limits.py` (template canonical source first; verify whether the other copy is regenerated by build or must be updated manually).
- [ ] Write/update unit tests for each hook verifying the single-pattern contract (AC-6).
- [ ] Write an integration-style test or fixture that verifies convergence on a simulated multi-file batch (AC-5).

## Risk & Safety

- Touches money? No.
- Touches data? No — only pre-commit hook scripts.
- Reversibility? Yes — hook script changes are fully reversible via git revert. No database migrations or schema changes.
- Risk: choosing Pattern A (auto-fix + exit 0) means the hook silently "fixes" files the developer may not have intended to change. Prefer Pattern B (report-only) when the auto-fix involves writing to files that aren't exclusively controlled by the hook (e.g. files the developer is actively editing). Document the pattern choice per hook in the DECISION HISTORY block.
- Secondary risk: `check_ac_limits.py` has two copies. If only the template is updated and the generated copy is not regenerated, the deployed hook will retain the old behavior. Verify build.py regeneration coverage before closing this ticket.
