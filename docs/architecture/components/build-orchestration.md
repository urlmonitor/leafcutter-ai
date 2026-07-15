---
title: "Build Orchestration — Epic & Ticket Dispatch Sequencing"
description: "Build orchestration: pre-dispatch sequencing gates, dependency-cycle detection, parallelism limits, file-conflict isolation, and pre-drive reachability checks."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-07-10
components:
  - build_orchestration
---

# Build Orchestration

## Overview

Build Orchestration governs how epics and tickets are dispatched to supervisors and phase agents. It sequences work before dispatch: building the dependency graph from `depends_on` (logical) and `files_touched` (physical) edges, detecting dependency cycles, enforcing parallelism limits, isolating file-conflicting tickets into serial batches, and running pre-drive reachability checks (e.g. telemetry sink writability) before a drive begins.

## Responsibilities

- Compute the maximal next-ready ticket batch that is parallel-safe under both logical and physical edges
- Detect and surface dependency cycles before dispatch
- Enforce parallelism limits and file-conflict isolation across concurrent supervisors
- Run pre-drive reachability / precondition checks before starting an epic drive

## Entry Points

- `templates/workflows-js/build-epic.js` — epic dispatch workflow

## Integration

Build Orchestration sits above the supervisor spawn topology: it decides *what* to dispatch and in *what order*, then hands each ready ticket to a `ticket-supervisor`. See `docs/architecture/components/build-epic-workflow-dispatch.md` and `docs/architecture/components/supervisor-spawn-topology.md` for the dispatch mechanics it drives.
