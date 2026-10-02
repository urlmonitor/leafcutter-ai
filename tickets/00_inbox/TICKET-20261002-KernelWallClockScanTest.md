---
title: "Kernel tests: the scan-cost test asserts wall-clock seconds and fails under load"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: low
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - tests
  - flaky
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel tests: the scan-cost test asserts wall-clock seconds and fails under load

## Actor / Goal
In order to keep the local kernel suite a reliable merge gate (pytest no longer runs in CI), we need `test_candidate_counts_and_scan_cost_stay_bounded` to measure scan cost in a way that doesn't depend on machine load.

## Context
- **The test:** `tests/kernel/grounding/test_sources_and_coverage.py::TestDefaultSources::test_candidate_counts_and_scan_cost_stay_bounded` asserts that scanning the real checkout takes under 30 seconds of wall-clock time.
- **Behaviour on 2026-10-02:**
  - Alone, it takes about 12 seconds and passes.
  - In the full serial suite under load, an 18-minute run, it failed.
  - It also failed under `-n 4`.
- **Cause:** its count assertions held, so only the time bound failed.

## Scope
- Bound deterministic cost instead: files scanned, bytes read, sections built, candidates offered. Or keep a generous time bound marked as a performance check outside the default suite.
- Keep the candidate-count bounds.

## Out of Scope
- Changing retrieval itself.

## Comments
