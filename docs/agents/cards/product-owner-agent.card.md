---
agent_id: product-owner-agent
title: "Agent Card: product-owner-agent"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# product-owner-agent

**Performs a structured product-owner audit: reads docs/vision.md and
docs/roadmap.json, invokes the roadmap-steward skill to produce an
audit_result JSON, presents findings (starved items, off-roadmap tickets,
phase progress), holds an interactive PO dialogue, and proposes a
confirmation-gated action list. Never modifies documents without explicit
per-action user confirmation.
Invoke via /po-review or directly: Agent(name='product-owner-agent').**

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

    user["user\n(phase tier)"]:::phase
    product_owner_agent["product-owner-agent\n(utility tier, priority ?)"]:::target
    create_ticket["create-ticket\n(phase tier)"]:::phase
    research_agent["research-agent\n(utility tier)"]:::utility

    user -->|dispatches| product_owner_agent
    product_owner_agent -->|spawns| create_ticket
    product_owner_agent -->|spawns| research_agent
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
| `roadmap-steward` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
