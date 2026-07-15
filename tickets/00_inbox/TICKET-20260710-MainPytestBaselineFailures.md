---
title: "Investigate and fix the pre-existing pytest baseline failing on main"
status: todo
components:
  - build_orchestration
created: '2026-07-10'
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - tests/test_build_artifact_parity.py
  - tests/test_build_phases.py
  - tests/test_setup_ticket_worktree.py
  - unit_tests/commit_guardian/test_check_ac_schema.py
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# Investigate and fix the pre-existing pytest baseline failing on main

## Summary

The CI "Test suite (pytest)" job fails on `main` itself — the latest main commits
(e.g. 1b5b9f9a, PR #267) show the pytest job conclusion as `failure`, with ~67 failing
tests. Because pytest is a non-required check (only "Lint (ruff)" and "schema-diff" gate
merges), the overall run still reports "success" and PRs merge over a red suite. This
masks real regressions: every PR inherits 67 failures, so a genuinely new failure is
easy to miss in the noise.

## Background

Confirmed 2026-07-10 during EPIC-LiveSurfaceTesting (PR #266): captured the failing-test
set on main (67) and on the PR (67) — identical, `comm -13` empty — which is how the PR
was cleared for merge. That comparison is only possible because someone does it by hand;
the baseline should be green (or explicitly quarantined) so the diff is automatic.

The 67 failures span many unrelated subsystems, so this is systemic, not one bug:

- `tests/test_build_artifact_parity.py` — a `config` template dir not listed in
  `_USER_FACING_CATEGORIES`/`_INTERNAL_CATEGORIES`; `check-output-drift` hook not found
  in `commit_guardian.json`.
- `tests/test_build_phases.py` — deployed `plan-feature.js` size/hash differs from source
  (`61383` vs `82834` bytes) — possible stale/truncated deploy.
- `tests/test_setup_ticket_worktree.py` — many `TypeError: the JSON object must be str,
  bytes or bytearray, not MagicMock` (mock wiring drift).
- `tests/test_sweep_processes.py`, `unit_tests/commit_guardian/test_check_ac_schema.py`,
  `test_check_components_minimum_schema.py`, `test_ensure_precommit_config.py`,
  `test_build_changelog_placeholder.py`, `test_build_guard_real_package.py`,
  `test_build_package_version.py`, and others.

## Acceptance Criteria

- [ ] AC-1: Every failing test in the current main pytest baseline is triaged into one of:
  (a) real product defect to fix, (b) stale/incorrect test to update, or (c) intentionally
  quarantined with an explicit skip marker and a tracking reference. The triage is recorded.
- [ ] AC-2: After remediation, `python -m pytest tests/ unit_tests/ -q` on `main` exits 0
  (or exits 0 excluding only tests explicitly quarantined in AC-1).
- [ ] AC-3: The pytest job is either promoted to a required check once green, or a
  documented rationale is recorded for why it remains non-required — so the "green means
  green" invariant is restored for future PRs.

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
