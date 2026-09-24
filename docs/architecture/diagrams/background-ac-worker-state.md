---
title: "Background AC worker state transitions"
description: "Feature lifecycle, pause, blocker and delivery transitions for the background worker."
type: explanation
status: active
created: 2026-09-24
last_updated: 2026-09-24
components:
  - ac_driven_dev
flight_level: L3-Component
diagram_type: state
related_code:
  - scripts/background_worker_cli.py
  - scripts/background_worker/engine.py
  - scripts/background_worker/store.py
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/how-to/background-ac-worker.md
  - docs/reference/background-ac-worker.md
---

# Background AC worker state transitions

This view describes the worker control policy. Displayed state names may be
more specific in a persisted run; the inbox retains the blocking reason.

```mermaid
stateDiagram-v2
    [*] --> Disabled
    Disabled --> Waiting: explicit enable
    Waiting --> Claimed: eligible dependency-ready feature
    Claimed --> Implementing: reserve isolated workspace
    Implementing --> Implementing: next AC or bounded repair
    Implementing --> Validating: all required AC evidence available
    Validating --> Reviewing: checks pass at current head
    Validating --> Implementing: checks fail and budget remains
    Reviewing --> Implementing: first review requests repair
    Reviewing --> Publishing: positive review at validated head
    Publishing --> Delivered: draft PR and durable handoff
    Implementing --> Blocked: question or exhausted budget
    Validating --> Blocked: validation cannot be repaired
    Reviewing --> Blocked: failure or unresolved second review
    Publishing --> Blocked: failed or uncertain publication
    Blocked --> Claimed: explicit answer and successful revalidation
    Claimed --> Paused: disabled
    Implementing --> Paused: off then bounded action drains
    Validating --> Paused: off then bounded action drains
    Reviewing --> Paused: off then bounded action drains
    Publishing --> Paused: off then bounded action drains
    Paused --> Claimed: enabled and checkpoint revalidated
    Delivered --> [*]: human disposition
```

Restart does not reset budgets or authorize unresolved blockers. A delivered
reservation remains until explicitly reconciled; reaching a draft PR does not
mark the target branch complete or merge the proposal.
