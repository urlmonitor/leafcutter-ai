---
agent_id: business-analyst
title: "Agent Card: business-analyst"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# business-analyst

**Clarifies business intent, value, and success criteria for any ticket
creation request. Always spawned as the first stage of create-ticket.
Returns a structured JSON payload including summary, routing_decision
(standard_ticket or epic), deliverables_count, open_questions,
success_criteria, and test_requirements (produced by test-planner).
Use when: create-ticket needs to understand the scope and business value of
a user request before routing it.**

| Field | Value |
|-------|-------|
| Model | opus |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `create-ticket`
- `create-epic`
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

    create_ticket["create-ticket\n(phase tier)"]:::phase
    create_epic["create-epic\n(phase tier)"]:::phase
    business_analyst["business-analyst\n(utility tier, priority ?)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility
    test_planner["test-planner\n(phase tier)"]:::phase

    create_ticket -->|dispatches| business_analyst
    create_epic -->|dispatches| business_analyst
    business_analyst -->|spawns| research_agent
    business_analyst -->|spawns| test_planner
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
| `Agent` |
---

## Skills Used

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
