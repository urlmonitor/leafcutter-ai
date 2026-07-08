---
title: "Decide whether ruff should lint templates/ directly (currently excluded)"
status: todo
components:
  - build-pipeline
created: 2026-07-07
depends_on: []
priority: low
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - pyproject.toml
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/2
---

# Decide whether ruff should lint templates/ directly (currently excluded)

## Goal
In order to be sure the "restored green CI baseline" actually gates code quality
for all shipped Python, we need to decide — and then encode — whether the ruff
lint gate should cover `templates/` directly, so that source templates are not
silently exempt from the required lint check.

## Context
Surfaced by the code review of PR #217 / TICKET-20260707-restore-ci-test-baseline
(finding L-3, second half). The ruff config excludes `templates/`. The BA's
analysis (BO-1000 / source↔template parity) suggests this may be **intentional**:
`scripts/` is byte-for-byte mirrored by `templates/scripts/` under BP-1000, so
linting `scripts/` already covers `templates/scripts/` by proxy. But that
coverage-by-proxy only holds for the mirrored subtree — any Python under
`templates/` that is NOT part of the `scripts/` mirror (e.g. templated agent/skill
helper code) would be unlinted.

This ticket is a **decision + minimal follow-through**, not a large change:
confirm the intent, and either (a) document the exclusion as deliberate with the
proxy-coverage rationale, or (b) narrow the ruff exclude so non-mirrored
`templates/` Python is linted.

Related, out of scope here: making the pytest job blocking is BP-1200b-1.

## Acceptance Criteria
- [ ] AC-1 (decision recorded): Determine whether all Python under `templates/`
  is covered by the `scripts/` ↔ `templates/scripts/` byte-parity mirror (BP-1000).
  If fully covered, record the exclusion as intentional (with the proxy-coverage
  rationale) in the ruff config comment and/or the relevant docs. If NOT fully
  covered, proceed to AC-2.
- [ ] AC-2 (scope corrected, only if AC-1 finds a gap): Narrow the ruff `exclude`
  so that non-mirrored `templates/` Python is linted, and confirm `ruff check`
  passes (or the surfaced violations are fixed) with no new required-gate failures.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |

## Comments

<!-- Append-only log — leave blank when authoring. -->

## Implementation Tasks
- [ ] Enumerate Python files under `templates/` and cross-check against the
  `scripts/` ↔ `templates/scripts/` mirror set (BP-1000d-1 in-scope list).
- [ ] If fully mirrored: add a rationale comment to the ruff `exclude` entry
  (and/or a note in the build/quality docs) and close AC-2 as not-needed.
- [ ] If a gap exists: narrow the `exclude`, run `ruff check`, and resolve or
  triage any newly-surfaced violations.

## Risk & Safety
- Touches money? No.
- Touches data? No — lint-config only.
- Reversibility? Fully reversible (single config entry).
