---
title: "Background AC worker state transitions"
description: "Feature lifecycle, pause, blocker and delivery transitions for the background worker."
type: explanation
status: active
created: 2026-09-24
last_updated: 2026-09-26
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
    Claimed --> Discovering: reserve isolated workspace
    Discovering --> InputGate: readiness assessment accepted
    Discovering --> Blocked: missing input or failed reply
    InputGate --> Implementing: answers and workspace proof valid
    InputGate --> Discovering: proof missing or stale
    Implementing --> Discovering: next AC or bounded check repair
    Discovering --> Validating: all required AC evidence available
    Validating --> Reviewing: checks pass at current head
    Validating --> Blocked: feature validation fails
    Reviewing --> Discovering: first review requests repair
    Reviewing --> Publishing: positive review at validated head
    Publishing --> Delivered: draft PR and durable handoff
    Implementing --> Blocked: question, failed reply or exhausted budget
    Reviewing --> Blocked: failure or unresolved second review
    Publishing --> Blocked: failed or uncertain publication
    Blocked --> Paused: explicit resolution and revalidation
    Claimed --> Paused: disabled at phase boundary
    Discovering --> Paused: off then bounded action drains
    InputGate --> Paused: disabled at phase boundary
    Implementing --> Paused: off then bounded action drains
    Validating --> Paused: off then bounded action drains
    Reviewing --> Paused: off then bounded action drains
    Publishing --> Paused: off then bounded action drains
    Paused --> Resuming: enabled and checkpoint revalidated
    Resuming --> Discovering: answered input or invalidated proof
    Resuming --> Claimed: workspace preparation still pending
    Resuming --> Validating: validation checkpoint
    Resuming --> Reviewing: review checkpoint
    Resuming --> Publishing: publication checkpoint
    Delivered --> [*]: human disposition
```

Restart does not reset budgets or authorize unresolved blockers. A delivered
reservation remains until explicitly reconciled; reaching a draft PR does not
mark the target branch complete or merge the proposal.

Declared missing inputs block before a model call. Discovery consumes time but
no writable attempt. Malformed, refused, error and unsupported replies create
durable blockers without automatic redispatch; ordinary failed AC checks may
use the remaining repair budget through fresh discovery. Unknown in-flight
outcomes require explicit reconciliation before resuming.
