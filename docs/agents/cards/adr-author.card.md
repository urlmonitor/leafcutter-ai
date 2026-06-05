---
agent_id: adr-author
title: "Agent Card: adr-author"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# adr-author

**Authors a new Architecture Decision Record under docs/architecture/.
Loads docs/how-to/documentation/write-adr.md at runtime and lists
docs/architecture/ to pick the next free ADR number before writing.
Produces a correctly-numbered, correctly-templated ADR with all required
sections: Status, Context, Decision, Consequences, Alternatives
(internal — invoked by documentation-expert only).**

| Field | Value |
|-------|-------|
| Model | opus |
| Tier | phase |
| Priority | 2 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `ticket-supervisor`
- `documentation-expert`
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
    documentation_expert["documentation-expert\n(phase tier)"]:::phase
    adr_author["adr-author\n(phase tier, priority 2)"]:::target

    ticket_supervisor -->|dispatches| adr_author
    documentation_expert -->|dispatches| adr_author
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

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
