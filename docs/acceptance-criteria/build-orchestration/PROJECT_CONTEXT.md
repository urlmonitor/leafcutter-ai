---
description: Accumulated conventions for the build-orchestration AC namespace — L0 numbering, scope boundaries vs. neighbouring components, and concurrency/parity/registry distinctions for BO-series authoring agents.
---

# build-orchestration — Project Context for Authoring Agents

Accumulated conventions for the `build-orchestration` AC namespace (prefix `BO`).
Read this before authoring or decomposing ACs in this component.

## ID numbering

- L0s occupy hundreds: 100, 200, 201, 202, 300, 400, 500, 700, 800, 900, 1100,
  1200, 1300, 1400, 1500, 1600.
- Next free L0 hundred after BO-1500 was **BO-1600** (assigned to the
  safe-concurrent-dispatch goal). Pick the next free hundred for any new L0.
- Deprecated/superseded IDs are reserved permanently — never reuse a numeric slot.

## Concurrency / atomicity scope boundaries (avoid duplication)

Three SEPARATE concurrency-adjacent concepts live across build-orchestration —
do not conflate or duplicate when authoring near any of them:

- **BO-100c** — file-conflict ISOLATION: separates tickets whose `files_touched`
  sets overlap into sequential rounds BEFORE dispatch (scheduling concern).
- **BO-200** — atomic delivery of a SINGLE ticket's commit (all-or-nothing,
  clean rollback of one supervisor's commit; does not address shared-store races).
- **BO-1600** — git-OBJECT-STORE / index protection when MULTIPLE supervisors
  commit CONCURRENTLY into ONE shared worktree (origin: EPIC-FinalizeFeatureHardening
  retro KI-1 — parallel ticket-supervisors produced a 0-byte loose object that
  corrupted the worktree index). PREVENTION ONLY by design — no recovery L1.

BO-100c = "don't let same-file tickets run together" (pre-dispatch scheduling).
BO-200  = "make one ticket's commit atomic" (single-supervisor).
BO-1600 = "don't let concurrent commits corrupt the shared git store" (multi-supervisor, storage layer).

## Cross-component placement notes (parity & registry — NOT build-orchestration)

Two EPIC-FinalizeFeatureHardening retro items deliberately did NOT land here —
they extend existing trees in other components. Record this so future agents
don't recreate them under BO:

- **Workflow-script mirror parity (KI-3)** → `BP-1000e` (build-pipeline). It is
  the SAME byte-parity mechanism as BP-1000a (source ↔ shipped) applied to the
  `templates/workflows-js/*.js` ↔ `scripts/workflows/*.js` pair set. Added as a
  sibling L1 under BP-1000, NOT a new BO goal.
- **Registry tolerates workflow spawners (KI-4)** → `INF-600k` (infrastructure).
  Refines the registry validator (INF-600g family) to accept non-agent external
  callers (workflow `*.js` filenames, `user`) in `spawned_by` without "unknown
  agent" errors.

## Authored-but-prevention-only convention

When a retrospective Known-Issue is framed as PREVENTION ONLY by the user
(e.g. BO-1600), do NOT add a "detect-and-recover" sibling L1 on your own
initiative — recovery is a separate capability that must be explicitly requested.
The goal text should state the prevention scope and cite the neighbouring ACs it
is distinct from.
