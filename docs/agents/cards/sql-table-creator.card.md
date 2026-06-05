---
agent_id: sql-table-creator
title: "Agent Card: sql-table-creator"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# sql-table-creator

**Creates all artifacts required to introduce a new database table: ORM model,
migration, model registry, idempotent schema SQL, component registration, and
per-table doc. Reads PROJECT_CONTEXT.md for project-specific how-to paths and
conventions before writing any file.
(internal — invoked by sql-coder only)**

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
    sql_table_creator["sql-table-creator\n(utility tier, priority ?)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility

    sql_coder -->|dispatches| sql_table_creator
    sql_table_creator -->|spawns| research_agent
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
