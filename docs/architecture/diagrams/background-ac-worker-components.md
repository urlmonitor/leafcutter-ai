---
title: "Background AC worker components"
description: "Runtime components and persistence boundaries of the opt-in background worker."
type: explanation
status: active
created: 2026-09-24
last_updated: 2026-09-24
components:
  - ac_driven_dev
flight_level: L3-Component
diagram_type: component
related_code:
  - scripts/background_worker_cli.py
  - scripts/background_worker/engine.py
  - scripts/background_worker/store.py
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/how-to/background-ac-worker.md
  - docs/reference/background-ac-worker.md
---

# Background AC worker components

```mermaid
flowchart TD
    User[User or external supervisor] --> CLI[Installed Python CLI]
    CLI --> Settings[Settings validation]
    CLI --> Service[Local scheduler]
    CLI --> Store[(SQLite settings, claims, runs, inbox)]
    AC[AC YAML and linked references] --> Planner[Deterministic feature planner]
    Target[Target branch evidence] --> Planner
    Planner --> Service
    Service --> Engine[LangGraph feature engine]
    Service --> Store
    Engine --> Store
    Engine --> Capacity[Shared agent-call capacity]
    Capacity --> Impl[Codex CLI implementation adapter]
    Impl --> Ollama[Loopback Ollama / local model]
    Capacity --> Bridge[JavaScript reviewer bridge]
    Bridge --> Codex[Codex SDK / chosen model]
    Bridge --> Claude[Claude Agent SDK / chosen model]
    Engine --> Workspace[Isolated feature worktree and project checks]
    Engine --> Publish[Git push and draft PR publication]
    Service --> Notice[Desktop notification adapter]
    Notice --> Store
```

LangGraph controls feature execution transitions. It does not select a model
implicitly, replace the coding harness, or provide the local inference server.
SQLite owns durable admission and recovery data. The existing regular workflow
engine and its model tiers remain separate from this opt-in lane.
