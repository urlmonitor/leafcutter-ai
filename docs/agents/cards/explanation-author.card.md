---
agent_id: explanation-author
title: "Agent Card: explanation-author"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# explanation-author

**Diataxis "understand" specialist. Produces understanding-oriented explanation
docs — concept explainers and "why-it-works-this-way" discussions — by loading
the canonical how-to before writing. Applies a genre guard and hands back to
the correct specialist when the request is not "understand".
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
    explanation_author["explanation-author\n(phase tier, priority 10)"]:::target

    ticket_supervisor -->|dispatches| explanation_author
    documentation_expert -->|dispatches| explanation_author
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
