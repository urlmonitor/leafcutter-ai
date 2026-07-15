---
title: "Add psutil to requirements-dev.txt so test_sweep_processes passes"
status: todo
components:
  - testing_quality
created: 2026-07-15
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: dependency
risk_surface: internal
agents:
  test-writer: not_needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 04: Add psutil dev-dependency for test_sweep_processes

## Actor / Goal

As a maintainer, I want `psutil` available in the CI dev environment so
`test_sweep_processes` runs its real assertion instead of failing on the
missing-dependency guard.

## Context

Residual subset of Cluster 6 (2026-07-15 gap analysis). On CI (`origin/main` run
`29403216629`) `tests/test_sweep_processes.py::test_sweep_result_shape` fails:

```
AssertionError: Expected None, got 'psutil is not installed — cannot sweep
processes. Install it with: pip install psutil'
```

The code under test degrades gracefully when `psutil` is absent (returns the
"not installed" message), but the test asserts the real sweep result shape, which
requires `psutil` to be installed. It is not in `requirements-dev.txt`, so CI
never installs it.

Not owned by any epic or the `c990bb89` salvage. This is the simplest cluster —
a one-line dependency addition — but keep it a discrete ticket so the dependency
change is reviewable in isolation.

## Acceptance Criteria

```gherkin
Given a fresh CI environment that installs requirements-dev.txt
When test_sweep_processes runs
Then psutil is importable and test_sweep_result_shape asserts the real result
  shape (not the "psutil is not installed" fallback) and passes
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | tests/test_sweep_processes.py | requirements-dev.txt | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Add a pinned `psutil` entry to `requirements-dev.txt`.
- [ ] Confirm `test_sweep_processes.py` passes with psutil installed.
- [ ] Sanity-check no other test relies on psutil being ABSENT (grep for the
      "not installed" fallback assertion elsewhere).

## Risk & Safety

- Touches money? No.
- Touches data? No — dev-dependency only.
- Reversibility? Fully reversible.
