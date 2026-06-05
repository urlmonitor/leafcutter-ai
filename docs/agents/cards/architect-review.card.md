---
agent_id: architect-review
title: "Agent Card: architect-review"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# architect-review

**Structural impact gatekeeper for proposed changes. Receives a refined ticket
from create-ticket, calls research-agent for blast-radius analysis, classifies
impact as small or large using a documented rubric, and either writes an
inline architectural note (Sonnet only) or escalates to an Opus sub-agent.
(internal — invoked by parent agents only)**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 4 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `ticket-supervisor`
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

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    create_ticket["create-ticket\n(phase tier)"]:::phase
    architect_review["architect-review\n(phase tier, priority 4)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility
    architect_review_deep["architect-review-deep\n(phase tier)"]:::phase

    ticket_supervisor -->|dispatches| architect_review
    create_ticket -->|dispatches| architect_review
    architect_review -->|spawns| research_agent
    architect_review -->|spawns| architect_review_deep
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
| `signoff` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
