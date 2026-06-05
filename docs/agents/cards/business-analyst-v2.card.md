---
agent_id: business-analyst-v2
title: "Agent Card: business-analyst-v2"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# business-analyst-v2

**Enhanced BA (Opus) for the v2 ticket-creation pipeline. Reads INDEX.md before
asking questions, uses a comprehensive elicitation framework to avoid mechanical
question-asking, self-checks for weasel words, logs assumptions, and classifies
ticket complexity (trivial/simple/standard/novel) to drive routing.

Use when: create-ticket-v2 needs to understand the scope and business value of a
user request before routing it through the v2 AC pipeline.

Parallel test path only — does NOT replace business-analyst.md.**

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

- `create-ticket-v2`
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

    create_ticket_v2["create-ticket-v2\n(phase tier)"]:::phase
    business_analyst_v2["business-analyst-v2\n(utility tier, priority ?)"]:::target

    create_ticket_v2 -->|dispatches| business_analyst_v2
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
