---
agent_id: change-scope-reviewer
title: "Agent Card: change-scope-reviewer"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# change-scope-reviewer

**Scope-integrity reviewer dispatched by ticket-supervisor after the coder
phase and before pr-reviewer. Reads the ticket's files_touched + out_of_scope
lists and the staged diff, classifies each unexpected file as soft/hard/ambiguous
using the three-tier disagreement model, and returns an actionable comment
without auto-promoting to ADR or rewriting ticket frontmatter.
(internal — invoked by ticket-supervisor only)**

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
    change_scope_reviewer["change-scope-reviewer\n(phase tier, priority 10)"]:::target

    ticket_supervisor -->|dispatches| change_scope_reviewer
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
