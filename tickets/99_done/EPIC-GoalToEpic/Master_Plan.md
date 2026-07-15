---
title: "EPIC: Goal to Epic — Turn any goal into a ready-to-build work package with one command (ACD-1200)"
type: epic
status: done
components:
  - ac_driven_dev
created: 2026-06-05
depends_on:
  - ACD-700
  - ACD-1000a
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: true
requires_adr: false
source_ac: ACD-1200
---

# EPIC: Goal to Epic (ACD-1200)

## Goal

After this epic lands, a developer can point `/build-ac` at any goal (L0) or
feature (L1) AC and receive a complete, ordered, dependency-wired epic folder
with one command — no manual ticket creation, no dependency discovery, no
approval hunting, and no target_epic bookkeeping.

The gap between "requirements are defined" and "work is buildable" is closed
by automation.

## Problem

Today `/build-ac` only handles leaf ACs (L2/L3): one command, one ticket, one
build. When a user wants to ship an entire feature family defined in the AC
store (an L0 with 25 ACs beneath it, for example), they must:

1. Manually identify all leaf ACs in the tree.
2. Manually generate a ticket per leaf.
3. Manually wire `depends_on` between tickets from the AC dependency graph.
4. Manually check which ACs are approved before building.
5. Manually stamp `target_epic` on each AC YAML file.
6. Manually assemble the tickets into a numbered epic folder.

This takes 30–60 minutes of error-prone bookkeeping per epic and produces
inconsistent results across different developers.

## Solution

Extend `/build-ac` to detect goal-level ACs (L0 or L1 with children) and
switch to an epic-generation mode that automates all six steps above:

- **Tree traversal** walks the AC store depth-first and collects every leaf.
- **Readiness gate** surfaces unapproved ACs and lets the user proceed with
  only the approved subset, bulk-review via IT PO v3, or cancel.
- **Dependency wiring** resolves transitive AC depends_on chains into
  ticket-level depends_on edges.
- **Folder assembly** assigns numeric prefixes from topological order and
  writes the EPIC- folder ready for ticket-supervisor.
- **target_epic stamping** writes the epic name into each included AC YAML.
- **Backward compatibility** — leaf-level `/build-ac` calls remain unchanged.

## AC Tree

L0: ACD-1200 — Turn any goal into a ready-to-build work package with one command

| L1 | Title | Leaf ACs | Ticket |
|----|-------|----------|--------|
| ACD-1200a | Get a full epic from a single goal reference | a-1, a-1-i, a-2, a-3, a-3-i | [01_tree-traversal-ticket-generation.md](./01_tree-traversal-ticket-generation.md) |
| ACD-1200b | See what needs approval before you can build | b-1, b-1-i, b-2 | [02_readiness-gate.md](./02_readiness-gate.md) |
| ACD-1200c | Tickets arrive in the right build order | c-1, c-1-i, c-2 | [03_dependency-wiring.md](./03_dependency-wiring.md) |
| ACD-1200d | Every touched AC knows which epic it ships in | d-1, d-1-i, d-2 | [04_target-epic-stamping.md](./04_target-epic-stamping.md) |
| ACD-1200e | The existing command just gets smarter | e-1, e-2, e-2-i | [05_goal-detection-mode-switch.md](./05_goal-detection-mode-switch.md) |
| (docs) | How-to guides and sequence diagram | a-4, a-5, b-3, e-3 | [06_documentation-and-diagram.md](./06_documentation-and-diagram.md) |

Total leaf ACs: 25 across 5 L1 features + 4 documentation ACs.

## Sub-Ticket Table

| # | File | Description | Agent | ACs | Depends On | Status |
|---|------|-------------|-------|-----|------------|--------|
| 01 | [01_tree-traversal-ticket-generation.md](./01_tree-traversal-ticket-generation.md) | Tree traversal, ticket generation, folder assembly, zero-leaf error | python-coder | a-1, a-1-i, a-2, a-3, a-3-i | — | `[ ]` |
| 02 | [02_readiness-gate.md](./02_readiness-gate.md) | Readiness report, approval gate, all-approved fast-path | python-coder + llm-expert | b-1, b-1-i, b-2 | 01 | `[ ]` |
| 03 | [03_dependency-wiring.md](./03_dependency-wiring.md) | AC depends_on → ticket depends_on, cycle detection, multi-hop ordering | python-coder | c-1, c-1-i, c-2 | 01 | `[ ]` |
| 04 | [04_target-epic-stamping.md](./04_target-epic-stamping.md) | target_epic field stamping, conflict detection, exclusion guard | python-coder | d-1, d-1-i, d-2 | 01, 02 | `[ ]` |
| 05 | [05_goal-detection-mode-switch.md](./05_goal-detection-mode-switch.md) | leaf-vs-goal detection, mode switch, backward compat, L1-no-children | llm-expert | e-1, e-2, e-2-i | 01, 02, 03, 04 | `[ ]` |
| 06 | [06_documentation-and-diagram.md](./06_documentation-and-diagram.md) | How-to guides (goal-to-epic, approval gate, unified command), sequence diagram | documentation-expert + architecture-diagram-author | a-4, a-5, b-3, e-3 | 01, 02, 05 | `[ ]` |

## Dependency Graph

```
01_tree-traversal-ticket-generation   (foundation — traversal, ticket gen, folder assembly)
        |
        +---> 02_readiness-gate        (needs leaf set from 01)
        |
        +---> 03_dependency-wiring     (needs leaf set from 01)
        |
        +---> 04_target-epic-stamping  (needs epic folder from 01; needs readiness gate from 02)
        |           |
        |           v
        +---> 05_goal-detection-mode-switch  (integrates all sub-features; needs 01-04 complete)
                    |
                    v
             06_documentation-and-diagram    (documents completed 01, 02, 05 behaviors)
```

Parallel batches:
- **Batch 1**: 01 alone (foundation)
- **Batch 2**: 02, 03 (both depend only on 01; run in parallel)
- **Batch 3**: 04 (depends on 01 + 02)
- **Batch 4**: 05 (integrates 01–04)
- **Batch 5**: 06 (documents completed system)

## Agent Assignments

| Agent | Tickets | AC Count |
|-------|---------|----------|
| python-coder | 01, 02 (partial), 03, 04 | 12 ACs |
| llm-expert | 02 (partial), 05 | 4 ACs |
| documentation-expert | 06 (partial) | 3 ACs |
| architecture-diagram-author | 06 (partial) | 1 AC |

## Files to Touch

```
scripts/ac_store/scan_ac_store.py          # tree traversal (new or extend)
scripts/ac_store/generate_ticket_from_ac.py # reused; called per leaf
scripts/ac_store/ac_prioritizer.py         # may expose leaf detection util
scripts/goal_to_epic.py                    # new orchestrator script
templates/agents/build-ac.md               # extend with goal detection + mode switch
.claude/skills/build-ac/SKILL.md           # extend skill doc (v2 pipeline reads this)
docs/how-to/goal-to-epic.md                # new (ACD-1200a-4)
docs/how-to/approval-gate.md               # new (ACD-1200b-3)
docs/how-to/build-ac-unified.md            # new (ACD-1200e-3)
docs/architecture/diagrams/seq-goal-to-epic-dispatch.md  # new (ACD-1200a-5)
```

## Exit Criteria

- All 25 leaf ACs in ACD-1200a through ACD-1200e have `work_status: done`
- All 4 documentation ACs (a-4, a-5, b-3, e-3) have `work_status: done`
- `/build-ac --ac ACD-1200` (self-referential smoke test) produces a valid EPIC folder
- `/build-ac --ac <leaf-id>` single-ticket path is unbroken (no regression)
- `build-self.sh` passes with no errors

## Risk & Safety

- Touches money? No.
- Touches data? Yes — `target_epic` stamping modifies AC YAML files on disk.
  All mutations are targeted field updates (no full yaml.dump round-trips).
  Mutations are gated behind epic folder creation success; partial stamping
  on failure is blocked by design (ACD-1200d-1 it_requirement).
- Reversibility? High — `target_epic` is a metadata field. Removing it
  restores the AC to its pre-epic state. The epic folder is a new directory;
  removing it reverts the ticket side. The build-ac agent update is
  additive (backward compat guaranteed by ACD-1200e).
- Risk of regressions: medium — the mode-switch logic must not alter the
  leaf-AC single-ticket path. ACD-1200e-1 is specifically designed to guard
  this regression surface.
