---
title: "EPIC: BO phantom-done remediation — wire orphaned code, fix opposite-behavior guards"
type: epic
status: todo
components:
  - build_orchestration
  - commit_guardian
created: 2026-07-14
depends_on: []
requires_diagram: false
requires_adr: false
---

# EPIC: BO Phantom-Done Remediation

## Goal

Close the ~40 BO-* acceptance criteria that the 2026-07-14 audit found to be
**phantom-done**: they carry green tests, but the code is orphaned (never
called), dead (unwired helpers), or implements the *opposite* of the criterion.
Each cluster is a single root-cause fix that resolves many ACs.

## Context / Root cause (audit 2026-07-14)

See [reports/BO-AC-implementation-audit-2026-07-14.md](../../../../reports/BO-AC-implementation-audit-2026-07-14.md).
The store marked these `todo`; the audit found green sign-offs on code that does
not actually run the behavior. This is the exact failure class the repo exists to
prevent (green tests on an orphaned module).

## Parallelism

The 5 tickets touch disjoint files → they are parallel-safe and can be driven by
different agents concurrently. Within each ticket the change is one root-cause fix.

## Tickets

| # | File | Fixes (leaf ACs) | Depends On | Status |
|---|------|------------------|------------|--------|
| 01 | [01_bo1100_wire_commit_routing.md](./01_bo1100_wire_commit_routing.md) | BO-1100 (21) | — | `[ ]` |
| 02 | [02_bo1700_wire_probe_helpers.md](./02_bo1700_wire_probe_helpers.md) | BO-1700 (10) | — | `[ ]` |
| 03 | [03_bo600_frontmatter_guard_require.md](./03_bo600_frontmatter_guard_require.md) | BO-600 (4) | — | `[ ]` |
| 04 | [04_bo400_donefolder_parity.md](./04_bo400_donefolder_parity.md) | BO-400 (3) | — | `[ ]` |
| 05 | [05_bo2000_reference_pattern_resolution.md](./05_bo2000_reference_pattern_resolution.md) | BO-2000 (2) | — | `[ ]` |
