---
title: "Background AC worker sequence"
description: "Interactions between the CLI, scheduler, execution adapters and durable state."
type: explanation
status: active
created: 2026-09-24
last_updated: 2026-09-24
components:
  - ac_driven_dev
flight_level: L3-Component
diagram_type: sequence
related_code:
  - scripts/background_worker_cli.py
  - scripts/background_worker/engine.py
  - scripts/background_worker/store.py
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/how-to/background-ac-worker.md
  - docs/reference/background-ac-worker.md
---

# Background AC worker sequence

```mermaid
sequenceDiagram
    actor User
    participant CLI
    participant Store as Local SQLite state
    participant Scheduler
    participant Graph as LangGraph worker
    participant Local as Codex CLI / local Ollama
    participant Reviewer as Selected reviewer SDK
    participant Git as Git / PR publication
    User->>CLI: configure, then on
    CLI->>Store: persist validated settings and enabled state
    CLI->>Scheduler: start background process
    Scheduler->>Store: read enablement and reserved features
    Scheduler->>Scheduler: group approved ACs and resolve dependencies
    Scheduler->>Store: atomically claim feature
    Scheduler->>Graph: resume feature checkpoint
    Graph->>Git: prepare isolated accumulating worktree
    loop Required ACs within persisted budgets
        Graph->>Store: check enabled state and acquire shared capacity
        Graph->>Local: implement with inherited requirements and evidence
        Local-->>Graph: execution result
        Graph->>Store: save outcome and release capacity
        Graph->>Graph: execute configured project checks
    end
    Graph->>Reviewer: review complete validated feature head
    Reviewer-->>Graph: findings and disposition
    alt Approval at current validated head
        Graph->>Git: push and create draft PR
        Graph->>Store: save delivery and attention record
    else Blocker or exhausted review repair
        Graph->>Store: save blocker, evidence and pending request
    end
    Scheduler-->>User: attempt desktop notification
    User->>CLI: inbox and status
    CLI->>Store: load durable outcome
    User->>CLI: answer run and request explicitly
    CLI->>Store: persist answer for revalidation
```

Repair returns to the local implementation harness and shared budgets. No phase
is authorized merely by another phase reporting success: validation, review and
publication retain their own evidence and exact revision checks.
