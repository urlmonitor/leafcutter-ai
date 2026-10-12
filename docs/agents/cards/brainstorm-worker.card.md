---
agent_id: brainstorm-worker
title: 'Agent Card: brainstorm-worker'
description: Internal-only single-perspective analyst. Spawned exclusively by `brainstorm-lead`
  (never by the user, never by a supervisor, never by any other agent) as part of
  the design-escalation tier from `building-epics` §3.3. Receives a design question
  plus a single perspective parameter (e.g. `simplicity`, `robustness`, `reversibility`,
  `performance`, `usability`, `maintainability`) and reasons about the question through
  that lens only. Returns a strictly structured `{perspective, recommendation, rationale,
  risks}` block — the parent lead parses on these keys. Does NOT spawn sub-agents;
  this is a single-shot read-only analyst.
type: card
status: active
created: 2026-08-13
card_version: generated
last_updated: '2026-08-13'
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

| Channel | Source | Injection Mode | Description |
|---------|--------|----------------|-------------|
| 1 | template description field | — | — |
| 6 | project files read during execution | — | — |
| 7 | bash command output (git, build, tests) | — | — |
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

### Inputs

| Name | Type | Description |
|------|------|-------------|
| `question` | string | Design question to reason about |
| `perspective` | string | Single reasoning lens (simplicity, robustness, etc.) |

### Outputs

| Name | Type | Description |
|------|------|-------------|
| `completion_report` | structured_response | Structured completion payload or sign-off comment |

### Mutates (Side Effects)

| Name | Type | Description |
|------|------|-------------|
| `none` | — | Read-only agent — no filesystem mutations |
---

## Tools Available

| Tool |
|------|
| `Read` |
| `Bash` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `building-epics` | always | — |
| `signoff` | always | — |
---

## Configuration

*No configuration keys declared.*
---

## Contributor Notes

### Key Behavioral Patterns

| Pattern | Trigger | Behavior | Related Agent |
|---------|---------|----------|---------------|
| Stop-and-Ask | condition requiring user decision or out-of-scope action | refuse
politely and point them at `brainstorm-lead`. | `None` |
| Conditional Behavior | either field is missing or unparseable | return the malformed-input | `None` |
