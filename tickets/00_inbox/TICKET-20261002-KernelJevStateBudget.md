---
title: "Kernel: a large decision fits Jev's state budget instead of failing the run"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - decision-basis
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: a large decision fits Jev's state budget instead of failing the run

## Actor / Goal
In order that a well-researched decision with many options can still be ranked, we need the assessment state sent to Jev to be budgeted as a whole and trimmed to fit, so the run never fails with `payload_too_large`.

## Context
- **Live reproduction:** run `run-5bd2023780654292` (2026-10-02) ended `failed` with `payload_too_large: jev state too large: 63571 > 60000`. It had 25 options (4 proposed plus 21 the owner added), 8 criteria, 85 evidence items and 12 host findings. The re-run `run-35ecc5ce9780442d` only completed with a run-local override `jev.max_state_chars: 90000`.
- **Cause:** design part 4 says "a state serialized above `jev.max_state_chars` raises `JevPayloadTooLarge`, and the caller truncates excerpts". `decision/jev_support.py` (~line 151) only shares half the cap across evidence excerpts (`max_state_chars // (2 * count)`). Options, criteria, findings, constraints and human inputs are not budgeted, so a decision with many options can exceed the cap while the evidence share alone fits.
- The provider limit is 32k tokens for the state plus the longest question, so 60000 characters is the kernel's own conservative guard.
- The two fixes of PR #987 (every human-added option researched; claim evidence cited) make large evidence sets normal.

## Scope (no acceptance criteria by user decision)
- Budget the whole assess state against `jev.max_state_chars`, not only evidence excerpts. On overflow, degrade in a defined order (e.g. shorten excerpts, then drop the lowest-relevance evidence not cited by any option, then shorten option descriptions and findings) and name each trim in the limitations. Never fail the run for size alone.
- If the state still cannot fit, split the options across assessment batches that share the same criteria and evidence, and combine the results deterministically. This is an alternative, not a requirement; pick one and document it.
- Tests: a decision whose state exceeds the cap is assessed (not failed) with a named trim limitation; the trimmed state stays under the cap; a small decision is unchanged.

## Comments
