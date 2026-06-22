---
title: "EPIC: goal_to_epic leaf-filter & cycle-resilient scan"
type: epic
status: in_progress
components:
  - ac-driven-dev
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
source_ac: ACD-1200
---

# EPIC: goal_to_epic Leaf-Filter & Cycle-Resilient Scan

## Goal

`scripts/ac_store/scan_ac_store.py` — the leaf-collection engine behind `/build-ac`
goal mode (`goal_to_epic.py`) — has two correctness gaps that surfaced while
building the EPIC-CodeQualityHooks retrospective findings:

1. **`traverse_ac_tree()` filters on `level` only.** It emits any L2/L3 leaf
   regardless of `work_status` or `status`, so goal mode regenerates tickets for
   work that is already `done` and emits `superseded_by` ACs that were split into
   children. (Observed live: `BO-100d-1`/`-2` superseded ACs would have produced
   duplicate/contradictory tickets.)

2. **A dependency cycle in ONE subtree crashes the whole store-wide scan.** A
   pre-existing cycle (`BO-1100a-3 ↔ BO-1100d-1`) makes `scan_ac_store.py`
   hard-abort, blocking `/build-ac` ranking for every unrelated tree.

This epic fixes both so goal mode produces a correct, minimal work package and a
single bad subtree never takes down store-wide ranking.

## Solution

Both fixes map to acceptance criteria approved on `main` (PR #133) under
`docs/acceptance-criteria/ac-driven-dev/ACD-1200-goal-to-epic/`:

- **ACD-1200a-10** (+ edge ACD-1200a-10-i) — `traverse_ac_tree()` excludes
  `work_status: done` and `status: superseded_by` leaves by default, while still
  recursing into a superseded AC's `covered_by` so the replacement children are
  collected. Parameterizable via `exclude_done` / `exclude_superseded` flags
  (default True) so the prior behavior is reproducible and unit-testable.
- **ACD-1200c-3** (+ edge ACD-1200c-3-i) — an out-of-scope subtree cycle degrades
  the store-wide scan to a warning (continue ranking the acyclic remainder,
  exit 0), while a genuine intra-scope cycle in a scoped goal build still hard-fails
  via `topological_sort` raising `CyclicDependencyError` (the ACD-1200c-1-i
  pre-write guard is preserved, not weakened).

## Sub-Ticket Table

| # | File | Description | Agent | ACs | Depends On | Status |
|---|------|-------------|-------|-----|------------|--------|
| 01 | [01_TICKET-20260622-ACD-1200a-10.md](./01_TICKET-20260622-ACD-1200a-10.md) | Exclude done/superseded leaves in traverse_ac_tree; recurse into superseded covered_by; exclude_done/exclude_superseded flags | python-coder | ACD-1200a-10 (+ -10-i) | — | `[ ]` |
| 02 | [02_TICKET-20260622-ACD-1200c-3.md](./02_TICKET-20260622-ACD-1200c-3.md) | Store-wide scan degrades to warning on an out-of-scope cycle; scoped build still hard-fails | python-coder | ACD-1200c-3 (+ -3-i) | — | `[ ]` |

## Dependency Graph

```
01_ACD-1200a-10   (leaf-collection exclusion filter)
02_ACD-1200c-3    (cycle-resilient store-wide scan)
```

No logical dependency between the two. Both edit
`scripts/ac_store/scan_ac_store.py`, so the supervisor serializes them under the
files-touched parallelism gate even though there is no `depends_on` edge.

## Files to Touch

```
scripts/ac_store/scan_ac_store.py   # both fixes land here (traverse_ac_tree + scan main)
scripts/goal_to_epic.py             # caller wiring / preserved scoped-cycle guard
```

## Exit Criteria

- ACD-1200a-10, ACD-1200a-10-i, ACD-1200c-3, ACD-1200c-3-i all reach
  `work_status: done`.
- A goal-mode `/build-ac` dry-run over a tree containing done/superseded leaves
  omits those leaves and still includes the superseded ACs' replacement children.
- `scan_ac_store.py` run against the store (which currently contains the
  `BO-1100a-3 ↔ BO-1100d-1` cycle) exits 0 with a warning and ranks the acyclic
  remainder, instead of aborting.
- A scoped goal build whose own leaf set contains a cycle still exits non-zero
  with the full cycle path (regression guard on ACD-1200c-1-i).
- New unit tests cover both behaviors; `build-self.sh` passes.

## Risk & Safety

- Touches money? No.
- Touches data? No — behavior-only changes to read-side traversal/scan logic.
  No AC YAML schema change, no migration.
- Reversibility? High — the exclusion is flag-gated (defaults can be flipped),
  and the cycle change only downgrades a fatal to a warning for out-of-scope cycles.
