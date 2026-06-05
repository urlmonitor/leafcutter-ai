---
agent_id: sql-procedure-creator
title: "Agent Card: sql-procedure-creator"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# sql-procedure-creator

**Specialist that authors new database stored procedures following the project's
procedure pattern. Produces the procedure SQL file and the matching
rollback-only test file in one pass. Reads PROJECT_CONTEXT.md for
project-specific paths and deploy commands.
(internal — invoked by parent agents only)**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | utility |
| Priority | — |
| Portable | No |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `sql-coder`
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

    sql_coder["sql-coder\n(phase tier)"]:::phase
    sql_procedure_creator["sql-procedure-creator\n(utility tier, priority ?)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    sql_coder -->|dispatches| sql_procedure_creator
    sql_procedure_creator -->|spawns| research_agent
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
