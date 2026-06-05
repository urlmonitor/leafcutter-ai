---
agent_id: reference-author
title: "Agent Card: reference-author"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# reference-author

**Diataxis "look up" specialist. Produces lookup-oriented reference docs —
API tables, schema dictionaries, configuration enums, parameter glossaries —
by loading the canonical how-to before writing. Applies a genre guard and
hands back to the correct specialist when the request is not "look up".
(internal — invoked by documentation-expert only)**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 10 |
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
    reference_author["reference-author\n(phase tier, priority 10)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    ticket_supervisor -->|dispatches| reference_author
    documentation_expert -->|dispatches| reference_author
    reference_author -->|spawns| research_agent
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
