---
title: "EPIC: GE-122 uniqueness pass and repair"
type: epic
status: todo
change_target: pipeline
risk_surface: contract_boundary
components:
- commit_guardian
- ticket_lifecycle
created: 2026-08-18
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: GE-122 uniqueness pass and repair

A deliberately small slice of the 22-leaf `GE-122` tree: **build the detection,
repair what it finds, prove the repaired collection passes the guard itself.**
Detection plus repair plus verification, self-contained.

## Why these five and not the whole tree

`goal_to_epic.py --ac GE-122` produces 21 tickets. That is the entire goal, and
it front-loads every remediation and enforcement behaviour behind a pass that
does not exist yet. The five here are the dependency-unblocked core:

| # | AC | Size | What it does |
|---|---|---|---|
| 01 | `GE-122a-1` | L | The whole-collection uniqueness pass. **Gates 13 of the tree's 22 leaves.** |
| 02 | `GE-122a-1-i` | S | A collision is found even when only one claimant is in the change set. |
| 03 | `GE-122a-2` | M | The work-item half of the same pass. |
| 04 | `GE-122e-2` | S | Repair the five twice-held work items. |
| 05 | `GE-122e-3` | S | The exit gate: the repaired collection passes, with nothing excused. |

Everything in `GE-122c` (remediation) and `GE-122d` (three-stage enforcement)
sits behind `01`. Nothing else in the tree unlocks more than three records.

## Ordering, and why it is not negotiable

Two constraints are stated in the ACs themselves, not invented here:

- **`04` must land before the work-item stage becomes blocking.** Otherwise five
  pre-existing duplicates stop every commit by an author who did not create them.
- **`05` must run after `04` and before `GE-122d-2` makes the CI gate required.**
  `05` is the check that this ordering worked.

`GE-122d-2` is deliberately **not** in this epic for that reason. The gate gets
built here; making it required is a later, separate decision.

## What is already true before this epic starts

- `GE-122e-1` is done and merged — the `GE-119` collision is resolved, and the AC
  store holds no duplicate identifiers.
- `ADR-029` was amended on 2026-08-18 so its fail-open rule no longer contradicts
  `GE-122d-3`. That unblocks adopting `check_adr_collision.py` into the pass.
- **Three whole-collection detectors already exist and are registered nowhere**, so
  none has ever run: `check_adr_collision.py` (270 lines),
  `check_ticket_state_integrity.py`, `check_ticket_no_branch_move.py`. Tickets 01
  and 03 are extract-and-harden, **not** greenfield. Registering them is part of
  the work.

## The trap this epic is most likely to fall into

A guard that is built, tested green, and registered nowhere. That is the exact
state of all three detectors above, and it is why `05` exists: it runs the real
gate through its production entry point and then **reintroduces a collision in
each of the four namespaces** to prove the pass is not inert. A passing result
over a clean collection is indistinguishable from a pass that inspected nothing.

`.pre-commit-config.yaml` is a build output regenerated from
`commit_guardian.json`. A hook added by hand to the generated file works locally
and is stripped in CI. An `"enabled": false` entry in the manifest removes a hook
silently and leaves no trace in the file a reader would inspect.

## Sub-Tickets

| # | Ticket | AC | Depends On |
|---|--------|----|-----------|
| 01 | [01_TICKET-20260818-GE-122a-1.md](./01_TICKET-20260818-GE-122a-1.md) | GE-122a-1 | — | `[ ]` |
| 02 | [02_TICKET-20260818-GE-122a-1-i.md](./02_TICKET-20260818-GE-122a-1-i.md) | GE-122a-1-i | 01 | `[ ]` |
| 03 | [03_TICKET-20260818-GE-122a-2.md](./03_TICKET-20260818-GE-122a-2.md) | GE-122a-2 | 01 | `[ ]` |
| 04 | [04_TICKET-20260818-GE-122e-2.md](./04_TICKET-20260818-GE-122e-2.md) | GE-122e-2 | 03 | `[ ]` |
| 05 | [05_TICKET-20260818-GE-122e-3.md](./05_TICKET-20260818-GE-122e-3.md) | GE-122e-3 | 01, 03, 04 | `[ ]` |

## Success Criteria

- One whole-collection uniqueness pass, registered in `commit_guardian.json` and
  reachable through its production entry point — not a second inert detector.
- The five twice-held work items reduced to one copy each, survivor chosen from
  `ticket_lifecycle.json` rather than from a completed-folder-wins rule of thumb.
- `05`'s reintroduce-and-re-run pair executed in **all four** namespaces, with each
  reintroduction removed afterwards.
- No allowlist, no known-bad list, no `enabled: false` anywhere that would let a
  contested number report clean.
