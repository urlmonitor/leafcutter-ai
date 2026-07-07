---
title: "EPIC-Phase1ReadyHardening — build all ready-but-unimplemented Phase 1 ACs"
type: epic
status: in_progress
components:
  - ac-store
  - build_pipeline
  - guardrail-engine
  - infrastructure
created: 2026-07-07
depends_on: []
---

# EPIC-Phase1ReadyHardening

## Goal

Implement every acceptance criterion that is currently **approved and ready but
not yet implemented**, batched by component into one ticket each. This drains the
ready queue for Phase 1 (Stable MVP — portable, self-onboarding, reliable) in a
single coordinated epic.

Source: `scan_ac_store.py --level leaf --work-status todo` (16 ready ACs) plus the
freshly-approved BP-100i hook-parity family (9 leaf ACs, blocked in the scanner
only by parent-in-`depends_on` hierarchy modeling, substantively ready). Total: 25 ACs.

## Sub-tickets

| # | Ticket | Component | ACs | Count |
|---|--------|-----------|-----|-------|
| 00 | ComponentGovernance | ac-store | ACS-300g-1, ACS-300g-2, ACS-300h-1, ACS-300i-1, ACS-300i-2, ACS-300j-1, ACS-300k-1, ACS-100i-2-i | 8 |
| 01 | BuildPipelineFixes | build_pipeline | BP-811, BP-812, BP-901 | 3 |
| 02 | GuardrailEngineFixes | guardrail-engine | GE-103, GE-105, GE-110 | 3 |
| 03 | InfrastructureFixes | infrastructure | INF-100c-1, INF-100c-3 | 2 |
| 04 | HookParityCheck | build_pipeline | BP-100i-1..5, BP-100i-1-i, BP-100i-1-ii, BP-100i-2-i, BP-100i-3-i | 9 |

## Execution notes

- **Serial batching.** Tickets 00, 01, 02, 04 all touch files under
  `scripts/commit_guardian/` and/or `commit_guardian.json` and `build_phases.py`;
  their `files_touched` overlap, so the supervisor will batch them serially
  (no parallel supervisors in a shared worktree — avoids git object-store races).
- Every ticket is code+test: `test-writer → python-coder → test-runner →
  pr-reviewer → commit → pull-request`.
- Each ticket wires to its ACs via `source_acs`; the coder marks each AC
  `work_status: done` + `implemented_by` on completion (ac-fulfillment-gate).

## Acceptance

All 26 ACs move to `work_status: done` with `implemented_by` set, all sub-ticket
sign-offs green, epic PR merged.
