---
title: "GE-109a is_test_file is in the wrong template tree (legacy only) — build would drop the test-file exemption"
status: todo
components:
  - commit_guardian
  - precommit_hooks
created: 2026-06-18
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/commit_guardian/check_exception_handling.py
  - templates/commit-guardian/check_exception_handling.py
  - unit_tests/commit_guardian/test_check_exception_handling.py
agents:
  architect-review: not_needed
  adr-author: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
---

# GE-109a is_test_file is in the wrong template tree

## Actor / Goal

As a leafcutter maintainer, I need GE-109a's test-file exemption (`is_test_file`
helper + the `main()` short-circuit) to live in the **canonical** guard template
tree so that `build.py` actually deploys it — otherwise a build silently drops
the exemption and test files get checked again.

## Context

Discovered during the EPIC-Exceptionhandlingguardenforcestheerror (GE-108) finalize
spot-check, 2026-06-18.

The exception-handling guard has **two** template trees:
- `templates/scripts/commit_guardian/check_exception_handling.py` — **CANONICAL**
  (build.py reads this; see scripts/build_phases.py).
- `templates/commit-guardian/check_exception_handling.py` — legacy/secondary copy.

GE-109a (PR that renamed GE-107→GE-109 and added the test-file exemption) added the
`is_test_file(path)` pure helper and the `main()` short-circuit **only to the legacy
tree**. On `origin/main` today:

- `templates/commit-guardian/check_exception_handling.py` HAS `is_test_file` (lines ~258, 480).
- `templates/scripts/commit_guardian/check_exception_handling.py` does NOT have it.

This is the **exact same defect class** that GE-108c hit (fix applied to the wrong
tree, build would drop it) — caught and fixed for GE-108c during the GE-108 finalize,
but GE-109a was not in that scope.

### Impact

A `build.py` run deploys the canonical tree to `.leafcutter/scripts/commit_guardian/`.
Because the canonical tree lacks `is_test_file`, the deployed guard will NOT exempt
test files — re-introducing the false positives GE-109a was created to fix (test files
legitimately use `open()` and broad `except` and would be flagged again).

Note: like GE-108, the deployed `.leafcutter/` copy is currently stale (pre-GE-108/109),
so this is latent until the next build/deploy.

## Acceptance Criteria

```gherkin
Scenario: The canonical guard tree exempts test files
  Given the canonical template templates/scripts/commit_guardian/check_exception_handling.py,
  When a test file (path component tests/ or unit_tests/, or basename test_*.py / *_test.py / conftest.py)
    with E722/BLE001/IO-001 patterns is analysed,
  Then the guard skips AST analysis and emits no violation (exit 0),
    matching the behavior already present in the legacy tree.

Scenario: Production files are still checked by the canonical tree
  Given a production .py file (no test path/name) with the same violation patterns,
  When the canonical guard analyses it,
  Then the violations are still emitted (exit 1) — the exemption does not widen.

Scenario: Both template trees are in sync
  Given both check_exception_handling.py template trees,
  When their is_test_file logic and main() short-circuit are compared,
  Then they are functionally identical (no tree-drift on the exemption).
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Out of Scope

- The GE-108b BLE001 self-hosting regression (tracked in
  TICKET-20260618-GE-108b-BLE001-SelfHosting-Regression.md).
- Broader investigation of WHY fixes keep landing in only one tree — if this recurs,
  consider a build-time parity guard between the two trees, or collapsing them to one
  source (separate design ticket).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — additive port of an existing, tested helper from
  one tree to the other.
- Low risk: the legacy tree already contains the reference implementation and tests;
  this is a port + sync + a parity assertion.
