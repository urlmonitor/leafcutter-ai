---
agent_id: create-epic
title: "Agent Card: create-epic"
type: card
status: active
created: 2026-06-05
card_version: "generated"
components:
  - supervisor_system
---
# create-epic

**Scaffolds an epic folder (tickets/00_inbox/epics/EPIC-<Name>/), writes a
Master_Plan.md, generates N stub ticket files, fans out N parallel
create-ticket calls to harden each stub, merges open_questions into one
consolidated user prompt, then runs a final hardening pass with the user's
answers. Invoked by create-ticket when business-analyst sets 
routing_decision to epic (internal — invoked by parent agents only).**

| Field | Value |
|-------|-------|
| Model | haiku |
| Tier | supervisor |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `user`
- `create-ticket`
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
    create_ticket["create-ticket\n(phase tier)"]:::phase
    create_epic["create-epic\n(supervisor tier, priority ?)"]:::target
    business_analyst["business-analyst\n(phase tier)"]:::phase
    create_ticket["create-ticket\n(phase tier)"]:::phase

    user -->|dispatches| create_epic
    create_ticket -->|dispatches| create_epic
    create_epic -->|spawns| business_analyst
    create_epic -->|spawns| create_ticket
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
