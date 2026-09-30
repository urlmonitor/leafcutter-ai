---
epic_name: EPIC-StartingNewWorkTheProperWayAlways
title: "Starting new work the proper way always succeeds"
type: epic
created: 2026-08-26
status: todo
depends_on: []
requires_diagram: false
requires_adr: false
change_target: pipeline
risk_surface: contract_boundary
components:
  - ac_driven_dev
  - agent_registry
  - build_pipeline
  - documentation_system
  - worktree_manager
source_ac: ACD-2100
---
# EPIC-StartingNewWorkTheProperWayAlways

## Goal

This epic implements AC ACD-2100: Starting new work the proper way always succeeds. It consists of 25 ticket(s) generated from the approved leaf ACs beneath ACD-2100, assembled in topological build order with all inter-ticket dependencies derived from the AC `depends_on` graph.

`/plan-feature` is the mandated entry point for new work under ADR-012, and it is currently the one route that cannot be relied on to start. Two of the three originally-diagnosed blockers were fixed on `main` in PR #454 — the pause-persist read-back and the dropped edit `feedback`. This epic covers what remains: the working-directory sensitivity of the startup path, the startup check that cannot distinguish an unreadable registry from a denied agent, the decisions recorded as the user's that no user made, the gap between the source copy and the installed one, and the absence of any written route from a waiting run back to a running one.

## Provenance of this file

**This `Master_Plan.md` was written by hand, and the ticket `depends_on` edges were repaired by hand.** `goal_to_epic.py --ac ACD-2100` exited before its final phase on 2026-08-26 after ~50 minutes, having written and placed all 25 tickets. It did not write this plan, did not remove the loose pre-move copies, and left every dependency edge unusable. No log survived the exit and the cause is unknown.

Three defects were repaired to produce the state you are reading:

- **11 tickets carried dangling `depends_on` references** naming the pre-move filename (`TICKET-…md`) rather than the ordinal-prefixed one (`NN_TICKET-…md`). Every edge resolved to nothing and `ticket_frontmatter_guard` rejects the set. This is KI-ACD-018, reproduced exactly — it also occurred on all 27 edges of the GE-120 epic.
- **All four Roman-suffix (`-i`) tickets had their sibling edge dropped entirely**, leaving `depends_on: []` where the AC record declares a real dependency. This is *not* KI-ACD-018 — a mis-named edge is visible, an absent one is not. A technical-constraint record built before the behaviour it constrains is backwards, and nothing would have reported it.
- **The plan itself was absent**, and this file's frontmatter carries the six fields the generator omits even on a successful run (KI-ACD-012).

The repaired set was verified in both directions: every `depends_on` reference resolves to a file that exists in this folder, and every AC-to-AC edge the store declares between two in-epic leaves is present in the ticket frontmatter. 31 edges, 0 dangling, 0 missing. A one-directional check would have passed on the broken set.

## Known gaps in the generated tickets

Not repaired here, and worth knowing before a driver picks these up:

- **`files_touched` is empty on `19`, `21` and `22`.** An empty `files_touched` is a phantom-done vector — it drives the surface that `change-scope-reviewer` and the fulfillment gate reason about. Fill it before building those three.
- **`ACD-2100d-3` has no `delivers_to` in its AC record.** No AC owns the consumer that reads its verdict; where that verdict lands (finalize, the build, or a required CI check) is still an open decision.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260826-ACD-2100a-1.md](./01_TICKET-20260826-ACD-2100a-1.md) | The worktree step runs the copy of the setup script that belongs to the repository being worked on | ACD-2100a-1 | — |
| 02 | [02_TICKET-20260826-ACD-2100a-2.md](./02_TICKET-20260826-ACD-2100a-2.md) | The setup step finds the repository it operates on even when the script itself lives outside it | ACD-2100a-2 | — |
| 03 | [03_TICKET-20260826-ACD-2100a-2-i.md](./03_TICKET-20260826-ACD-2100a-2-i.md) | An ambiguous repository location stops the setup step instead of being guessed | ACD-2100a-2-i | 02_TICKET-20260826-ACD-2100a-2.md |
| 04 | [04_TICKET-20260826-ACD-2100a-3.md](./04_TICKET-20260826-ACD-2100a-3.md) | The startup charter check finds the agent registry when the run starts inside a worktree | ACD-2100a-3 | — |
| 05 | [05_TICKET-20260826-ACD-2100a-4.md](./05_TICKET-20260826-ACD-2100a-4.md) | A pause record written from inside a worktree is found again by the run that resumes | ACD-2100a-4 | — |
| 06 | [06_TICKET-20260826-ACD-2100a-5.md](./06_TICKET-20260826-ACD-2100a-5.md) | A run reaches its first question to the user from any working directory | ACD-2100a-5 | 01_TICKET-20260826-ACD-2100a-1.md, 02_TICKET-20260826-ACD-2100a-2.md, 04_TICKET-20260826-ACD-2100a-3.md, 05_TICKET-20260826-ACD-2100a-4.md |
| 07 | [07_TICKET-20260826-ACD-2100b-1.md](./07_TICKET-20260826-ACD-2100b-1.md) | A registry the startup check cannot read is reported as unreadable and names what it tried to read | ACD-2100b-1 | — |
| 08 | [08_TICKET-20260826-ACD-2100b-2.md](./08_TICKET-20260826-ACD-2100b-2.md) | A registry whose contents cannot be understood is reported as unusable and not as a permission verdict | ACD-2100b-2 | — |
| 09 | [09_TICKET-20260826-ACD-2100b-3.md](./09_TICKET-20260826-ACD-2100b-3.md) | An agent missing from the registry and an agent denied permission produce different reports | ACD-2100b-3 | — |
| 10 | [10_TICKET-20260826-ACD-2100b-3-i.md](./10_TICKET-20260826-ACD-2100b-3-i.md) | A registry that holds no agent entries is reported as unusable rather than as a missing agent | ACD-2100b-3-i | 09_TICKET-20260826-ACD-2100b-3.md |
| 11 | [11_TICKET-20260826-ACD-2100b-4.md](./11_TICKET-20260826-ACD-2100b-4.md) | Every unresolved outcome of the startup check still stops the run before any authoring work begins | ACD-2100b-4 | 07_TICKET-20260826-ACD-2100b-1.md, 08_TICKET-20260826-ACD-2100b-2.md, 09_TICKET-20260826-ACD-2100b-3.md |
| 12 | [12_TICKET-20260826-ACD-2100b-5.md](./12_TICKET-20260826-ACD-2100b-5.md) | The startup check reads the registry itself instead of asking an agent to read it | ACD-2100b-5 | — |
| 13 | [13_TICKET-20260826-ACD-2100c-1.md](./13_TICKET-20260826-ACD-2100c-1.md) | Every decision the route records as the user's is put to the user and to no agent | ACD-2100c-1 | — |
| 14 | [14_TICKET-20260826-ACD-2100c-2.md](./14_TICKET-20260826-ACD-2100c-2.md) | A run that cannot reach a person waits with a durable record instead of proceeding or discarding | ACD-2100c-2 | 05_TICKET-20260826-ACD-2100a-4.md |
| 15 | [15_TICKET-20260826-ACD-2100c-3.md](./15_TICKET-20260826-ACD-2100c-3.md) | A paused run picks up at the decision it was waiting on when the answer arrives | ACD-2100c-3 | 14_TICKET-20260826-ACD-2100c-2.md |
| 16 | [16_TICKET-20260826-ACD-2100c-3-i.md](./16_TICKET-20260826-ACD-2100c-3-i.md) | An answer naming a different decision than the one being waited on is not applied | ACD-2100c-3-i | 15_TICKET-20260826-ACD-2100c-3.md |
| 17 | [17_TICKET-20260826-ACD-2100c-4.md](./17_TICKET-20260826-ACD-2100c-4.md) | An answer that did not come from the person is refused even when it is well formed | ACD-2100c-4 | 13_TICKET-20260826-ACD-2100c-1.md |
| 18 | [18_TICKET-20260826-ACD-2100c-5.md](./18_TICKET-20260826-ACD-2100c-5.md) | Work is thrown away only when the person chooses to throw it away | ACD-2100c-5 | 14_TICKET-20260826-ACD-2100c-2.md, 17_TICKET-20260826-ACD-2100c-4.md |
| 19 | [19_TICKET-20260826-ACD-2100d-1.md](./19_TICKET-20260826-ACD-2100d-1.md) | The installed copy of the route reaches the first user question exactly as the source copy does | ACD-2100d-1 | 06_TICKET-20260826-ACD-2100a-5.md |
| 20 | [20_TICKET-20260826-ACD-2100d-2.md](./20_TICKET-20260826-ACD-2100d-2.md) | A repair that is missing from the source an installed file is generated from is reported as not delivered | ACD-2100d-2 | — |
| 21 | [21_TICKET-20260826-ACD-2100d-2-i.md](./21_TICKET-20260826-ACD-2100d-2-i.md) | An install that replaces a locally changed generated file says so rather than replacing it silently | ACD-2100d-2-i | 20_TICKET-20260826-ACD-2100d-2.md |
| 22 | [22_TICKET-20260826-ACD-2100d-3.md](./22_TICKET-20260826-ACD-2100d-3.md) | Installing into a project where the route starts leaves the route still able to start | ACD-2100d-3 | 19_TICKET-20260826-ACD-2100d-1.md |
| 23 | [23_TICKET-20260826-ACD-2100d-4.md](./23_TICKET-20260826-ACD-2100d-4.md) | A reference page states which copy of the route runs and where a repair has to land | ACD-2100d-4 | 06_TICKET-20260826-ACD-2100a-5.md, 09_TICKET-20260826-ACD-2100b-3.md, 11_TICKET-20260826-ACD-2100b-4.md, 19_TICKET-20260826-ACD-2100d-1.md, 20_TICKET-20260826-ACD-2100d-2.md |
| 24 | [24_TICKET-20260826-ACD-2100e-1.md](./24_TICKET-20260826-ACD-2100e-1.md) | A sequence diagram shows every point where the route stops to ask and what follows from each answer | ACD-2100e-1 | 13_TICKET-20260826-ACD-2100c-1.md, 14_TICKET-20260826-ACD-2100c-2.md, 17_TICKET-20260826-ACD-2100c-4.md, 18_TICKET-20260826-ACD-2100c-5.md |
| 25 | [25_TICKET-20260826-ACD-2100e-2.md](./25_TICKET-20260826-ACD-2100e-2.md) | A how-to guide takes an operator from a waiting run back to a running one | ACD-2100e-2 | 15_TICKET-20260826-ACD-2100c-3.md, 16_TICKET-20260826-ACD-2100c-3-i.md, 05_TICKET-20260826-ACD-2100a-4.md, 24_TICKET-20260826-ACD-2100e-1.md |
