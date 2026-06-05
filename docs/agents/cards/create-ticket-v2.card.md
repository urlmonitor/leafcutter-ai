---
agent_id: create-ticket-v2
title: "Agent Card: create-ticket-v2"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# create-ticket-v2

**Orchestrates v2 ticket creation — parallel pipeline for testing the new AC format.
Runs business-analyst-v2 (Opus) first, then routes by complexity:
  trivial/simple → refinement + flat AC checklist
  standard/novel → it-po + per-agent contracts with Delivers to / Depends on
Produces v2-format tickets with ac_coverage frontmatter and ## Agent Contracts section.

Parallel test path only. v1 pipeline (create-ticket) is unmodified.

Use when: user types /create-ticket-v2; or asks to test the v2 pipeline.**

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
    create_ticket_v2["create-ticket-v2\n(supervisor tier, priority ?)"]:::target
    business_analyst_v2["business-analyst-v2\n(phase tier)"]:::phase
    it_po["it-po\n(phase tier)"]:::phase

    user -->|dispatches| create_ticket_v2
    create_ticket_v2 -->|spawns| business_analyst_v2
    create_ticket_v2 -->|spawns| it_po
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
