---
title: "Trustworthy gate: the blocking test job must not be fooled by AC-enforcement xfail-masking"
status: todo
components:
  - testing_quality
  - commit_guardian
created: 2026-07-15
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
files_touched:
  - scripts/ac_store/pytest_ac_enforcement.py
  - .github/workflows/ci.yml
  - unit_tests/ac_store/test_pytest_ac_enforcement_strict_on_ci.py
agents:
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 09: Make the blocking gate immune to xfail-masking

## Actor / Goal

As a maintainer, I want the CI `test` job to run so that genuinely-failing tests cannot be
hidden as xfail by the AC-enforcement plugin, so a "green" blocking gate actually means the
suite is green.

## Context

`pytest.ini` loads `-p scripts.ac_store.pytest_ac_enforcement`, which **downgrades any
failing test to `xfail`** when its covering AC's `work_status != "done"` (unless
`AC_ENFORCE_STRICT=1`). The review proved this hides real failures: `test_readiness_gate`,
`test_check_ac_done_on_merge`, `test_generate_ticket_from_ac`, and 13 `test_check_ac_schema`
cases are RED but land in the "27 xfailed" bucket, so CI's `81 failed` under-reports true
health. If BP-1200b flips the gate while this mask is active, the gate can read GREEN over
broken code — defeating the entire purpose of a blocking gate. This is the exact
phantom-done failure mode this repo exists to prevent, one level up.

(Related: EPIC-BuildPipelinePhantomRemediation mentions fixing the xfail-masking enabler
"in the same PR" — confirm whether that lands it; if so, this ticket becomes verification
only. As of this authoring it is unowned as a standalone, gate-integrity concern.)

## Acceptance Criteria

```gherkin
Given the CI test job that will become blocking (BP-1200b)
When it runs the suite
Then AC-enforcement xfail-masking is disabled for the gate (e.g. AC_ENFORCE_STRICT=1 in
  ci.yml) so a masked real failure makes the job RED, not green

Given a deliberately-failing test whose covering AC is not done
When the gate runs
Then the job fails (proving the mask cannot hide a real regression) — verified by a probe

Given the change
Then normal local/dev pytest behavior (mask on) is preserved for non-gate runs; only the
  gate runs strict. The mask is not deleted wholesale unless that is the agreed design.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_pytest_ac_enforcement_strict_on_ci.py | ci.yml / pytest_ac_enforcement.py | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Decide the mechanism: set `AC_ENFORCE_STRICT=1` on the CI `test` job (smallest
      change) vs disabling the plugin for the gate. Coordinate with the phantom epic's
      xfail-masking fix to avoid double-work.
- [ ] Add a test asserting the gate runs strict (env/flag present) so the protection can't
      silently regress.
- [ ] Probe: a temporary always-failing test with a non-done AC must turn the gate RED.

## Risk & Safety
- Touches money? No.
- Touches data? No — CI config + test-enforcement plugin behavior.
- Reversibility? Fully reversible.
