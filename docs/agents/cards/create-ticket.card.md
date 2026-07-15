---
agent_id: create-ticket
title: "Agent Card: create-ticket"
type: card
status: active
created: 2026-06-05
card_version: "generated"
components:
  - supervisor_system
---
# create-ticket

**Orchestrates ticket creation from any user request — small or large.
Always runs business-analyst first, then routes: ≤3 deliverables spawns
refinement + architect-review in parallel and finalises one ticket;
>3 deliverables defers to create-epic which owns the fanout.
Use when: user types /create-ticket; asks "create a ticket for X";
says "I need a ticket to add Y"; or describes any feature / fix / task
that needs to be captured in tickets/.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | supervisor |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `user`
- `create-epic`
- `product-owner-agent`
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

    user["user\n(phase tier)"]:::phase
    create_epic["create-epic\n(phase tier)"]:::phase
    product_owner_agent["product-owner-agent\n(phase tier)"]:::phase
    create_ticket["create-ticket\n(supervisor tier, priority ?)"]:::target
    business_analyst["business-analyst\n(phase tier)"]:::phase
    refinement["refinement\n(phase tier)"]:::phase
    architect_review["architect-review\n(phase tier)"]:::phase
    create_epic["create-epic\n(phase tier)"]:::phase
    it_po["it-po\n(phase tier)"]:::phase
    brainstorm_lead["brainstorm-lead\n(phase tier)"]:::phase

    user -->|dispatches| create_ticket
    create_epic -->|dispatches| create_ticket
    product_owner_agent -->|dispatches| create_ticket
    create_ticket -->|spawns| business_analyst
    create_ticket -->|spawns| refinement
    create_ticket -->|spawns| architect_review
    create_ticket -->|spawns| create_epic
    create_ticket -->|spawns| it_po
    create_ticket -->|spawns| brainstorm_lead
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
| `Edit` |
| `Write` |
| `Agent` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `ticket-authoring` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
