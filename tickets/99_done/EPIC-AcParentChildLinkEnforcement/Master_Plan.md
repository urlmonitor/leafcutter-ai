---
title: "EPIC: AC Parent-Child Link Enforcement"
type: epic
status: todo
components:
  - ac_store
  - ac_driven_dev
created: 2026-06-07
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: AC Parent-Child Link Enforcement

## Goal

Enforce parent-child link integrity in the AC store and improve epic generation
quality. Every child AC must appear in its parent's `covered_by` list — enforced
at commit time, detectable via store-wide scan, and maintained automatically by
authoring agents. Additionally, `goal_to_epic.py` must produce concise folder
names and generate `Master_Plan.md` files for fully automated epic drives.

Source ACs:
- `ACS-100i` — Cross-field constraints and relational references are enforced together
- `ACD-1200a` — Goal-to-epic pipeline improvements

## Tickets

| # | File | Title | Source AC | Status |
|---|------|-------|-----------|--------|
| 01 | [01_TICKET-20260607-ACS-100i-1.md](./01_TICKET-20260607-ACS-100i-1.md) | Parent ID is derived from child ID by stripping the last segment | ACS-100i-1 | todo |
| 02 | [02_TICKET-20260607-ACS-100i-2.md](./02_TICKET-20260607-ACS-100i-2.md) | Pre-commit hook blocks a child AC whose parent covered_by omits it | ACS-100i-2 | todo |
| 03 | [03_TICKET-20260607-ACS-100i-3.md](./03_TICKET-20260607-ACS-100i-3.md) | Validation traverses the full ancestry chain, not just the immediate parent | ACS-100i-3 | todo |
| 04 | [04_TICKET-20260607-ACS-100i-4.md](./04_TICKET-20260607-ACS-100i-4.md) | Existing orphaned children are detected and reported by a store-wide scan | ACS-100i-4 | todo |
| 05 | [05_TICKET-20260607-ACS-100i-5.md](./05_TICKET-20260607-ACS-100i-5.md) | Authoring agents update parent covered_by when creating a child AC | ACS-100i-5 | todo |
| 06 | [06_TICKET-20260607-ACD-1200a-6.md](./06_TICKET-20260607-ACD-1200a-6.md) | Epic folder name is concise and descriptive, not a naive title concatenation | ACD-1200a-6 | todo |
| 07 | [07_TICKET-20260607-ACD-1200a-7.md](./07_TICKET-20260607-ACD-1200a-7.md) | goal_to_epic.py generates a Master_Plan.md in the epic folder | ACD-1200a-7 | todo |

## Dependencies

```
01 (ID derivation)             no deps
├── 02 (pre-commit hook)       depends_on: 01
│   └── 03 (ancestry chain)   depends_on: 01, 02
├── 04 (store-wide scan)       depends_on: 01
└── 05 (agent auto-update)     depends_on: 01

06 (epic folder naming)        no deps (independent of 01-05)
└── 07 (Master_Plan.md gen)    depends_on: 06
```

## Batch Plan

- **Batch 1:** 01, 06 (no mutual deps — can run in parallel)
- **Batch 2:** 02, 04, 05, 07 (02/04/05 depend on 01; 07 depends on 06)
- **Batch 3:** 03 (depends on 01 + 02)

## Out of Scope

- Retroactive repair of all existing orphans (ticket 04 detects them; repair is a follow-up).
- Changes to the AC ID format itself (only enforcement of existing conventions).
- Modifications to `create-epic` agent behaviour (only `goal_to_epic.py` is in scope).
