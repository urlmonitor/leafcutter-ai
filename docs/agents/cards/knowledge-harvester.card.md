---
agent_id: knowledge-harvester
title: "Agent Card: knowledge-harvester"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# knowledge-harvester

**Runs the knowledge-emission harvester for a worktree. Reads unprocessed
knowledge_captured events from debugging/logs/knowledge_emissions.jsonl
(per ADR-011), routes each to the correct knowledge surface via the
capture-learning write protocol, marks events as processed, and reports
a summary. Invoked by ticket-supervisor or by the user after a batch of
phase agents have signed off.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `ticket-supervisor`
- `user`
---

## Knowledge Flow

*No knowledge channels declared.*

---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    user["user\n(phase tier)"]:::phase
    knowledge_harvester["knowledge-harvester\n(utility tier, priority ?)"]:::target

    ticket_supervisor -->|dispatches| knowledge_harvester
    user -->|dispatches| knowledge_harvester
```
---

## Input / Output Contract

*No structured I/O contract declared.*
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
---

## Skills Used

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
