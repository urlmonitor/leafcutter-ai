---
agent_id: brainstorm-worker
title: "Agent Card: brainstorm-worker"
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# brainstorm-worker

**Internal-only single-perspective analyst. Spawned exclusively by
`brainstorm-lead` (never by the user, never by a supervisor, never by
any other agent) as part of the design-escalation tier from
`building-epics` §3.3. Receives a design question plus a single
perspective parameter (e.g. `simplicity`, `robustness`,
`reversibility`, `performance`, `usability`, `maintainability`) and
reasons about the question through that lens only. Returns a strictly
structured `{perspective, recommendation, rationale, risks}` block —
the parent lead parses on these keys. Does NOT spawn sub-agents; this
is a single-shot read-only analyst.**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | utility |
| Priority | — |
| Portable | Yes |
| Sign-off capable | No |

---

## When to Use

### Spawned By

- `brainstorm-lead`
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

    brainstorm_lead["brainstorm-lead\n(phase tier)"]:::phase
    brainstorm_worker["brainstorm-worker\n(utility tier, priority ?)"]:::target

    brainstorm_lead -->|dispatches| brainstorm_worker
```
---

## Input / Output Contract

*No structured I/O contract declared.*
---

## Tools Available

| Tool |
|------|
| `Read` |
| `Bash` |
---

## Skills Used

*No skills declared.*
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

No conditional behaviors — this agent follows a single fixed execution path
