---
agent_id: it-po
title: "Agent Card: it-po"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# it-po

**IT Product Owner (Opus-tier). Translates business ACs from the business-analyst
into per-agent technical contracts with explicit "Delivers to" / "Depends on"
blocks. Reads architecture-level documentation only — never raw source files.
Requires at least one clarifying question before producing contracts.
Activates only when >1 coder agent is needed; falls through to refinement otherwise.
Handles oversized-ticket splits via §7 Split Protocol when check_ac_limits fires.
Use when: create-ticket routes a multi-coder ticket to the IT PO phase.**

| Field | Value |
|-------|-------|
| Model | opus |
| Tier | utility |
| Priority | 3.5 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `create-ticket`
- `create-ticket-v2`
- `ticket-supervisor`
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
    create_ticket_v2["create-ticket-v2\n(phase tier)"]:::phase
    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    it_po["it-po\n(utility tier, priority 3.5)"]:::target

    create_ticket -->|dispatches| it_po
    create_ticket_v2 -->|dispatches| it_po
    ticket_supervisor -->|dispatches| it_po
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

| Skill | Mode | Condition |
|-------|------|-----------|
| `signoff` | — | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
